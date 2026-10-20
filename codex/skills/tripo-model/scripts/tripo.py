#!/usr/bin/env python3
"""Private Markdown credentials and durable invocation records for Tripo CLI."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading

REGIONS = {"cn": "https://openapi.tripo3d.com", "ov": "https://openapi.tripo3d.ai"}
SECRETS = set()


class TripoError(Exception):
    def __init__(self, message, exit_code=2):
        super().__init__(message)
        self.exit_code = exit_code


def redact(value):
    text = str(value)
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text


def read_object(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise TripoError(f"Cannot read a JSON configuration object: {path}") from None
    if not isinstance(value, dict):
        raise TripoError(f"Expected a JSON configuration object: {path}")
    return value


def read_credentials(path):
    try:
        if os.name != "nt" and path.stat().st_mode & 0o077:
            raise TripoError(f"Credentials file must be private; run chmod 600 on {path}", 3)
        content = path.read_text(encoding="utf-8-sig")
    except OSError:
        raise TripoError(f"Cannot read credentials file: {path}", 3) from None
    values = {}
    for line in content.splitlines():
        match = re.fullmatch(r"\s*(?:export\s+)?(TRIPO_[A-Z_]+)\s*=\s*(.*?)\s*", line)
        if not match:
            continue
        name, value = match.groups()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if name == "TRIPO_API_KEY" and value:
            SECRETS.add(value)
        if name in values:
            raise TripoError(f"Duplicate credential assignment: {name}", 3)
        values[name] = value
    return values


def expand_path(value):
    if not isinstance(value, str) or not value:
        raise TripoError("Configured paths must be non-empty strings")
    return Path(value).expanduser().resolve()


def configuration(args, environ=None):
    env = dict(os.environ if environ is None else environ)
    if env.get("TRIPO_API_KEY"):
        SECRETS.add(env["TRIPO_API_KEY"])
    config_path = expand_path(args.config or env.get("TRIPO_SKILL_CONFIG") or
                              str(Path.home() / ".config/tripo-skill/config.json"))
    if (args.config or env.get("TRIPO_SKILL_CONFIG")) and not config_path.exists():
        raise TripoError(f"Configuration file does not exist: {config_path}")
    settings = read_object(config_path) if config_path.exists() else {}
    region = args.region or env.get("TRIPO_REGION") or settings.get("region", "cn")
    if region not in REGIONS:
        raise TripoError("Region must be cn or ov")

    explicit_file = args.credentials_file or env.get("TRIPO_CREDENTIALS_FILE")
    values = {}
    if not env.get("TRIPO_API_KEY") or explicit_file:
        credential_name = explicit_file or settings.get("credentials_file")
        if not credential_name:
            raise TripoError("Configure a credentials_file or TRIPO_API_KEY; see references/configuration.md", 3)
        values = read_credentials(expand_path(credential_name))
        file_region = values.get("TRIPO_REGION")
        if file_region and file_region != region:
            raise TripoError("Credentials region differs from the selected region; supply the matching credentials file", 3)

    key = env.get("TRIPO_API_KEY") or values.get("TRIPO_API_KEY", "")
    if not key or any(c.isspace() for c in key) or key.lower().startswith(("paste_", "replace_", "your_")):
        raise TripoError("TRIPO_API_KEY is missing, a placeholder, or contains whitespace", 3)
    SECRETS.add(key)
    configured_base = env.get("TRIPO_API_BASE_URL") or values.get("TRIPO_API_BASE_URL")
    if configured_base:
        normalized = configured_base.rstrip("/")
        if normalized.endswith("/v3"):
            normalized = normalized[:-3]
        if normalized != REGIONS[region]:
            raise TripoError("API base URL does not match the selected official Tripo region", 3)

    cli_entry = expand_path(env.get("TRIPO_CLI_ENTRY") or settings.get("cli_entry") or
                            str(Path.home() / ".local/share/tripo-skill/node_modules/tripo-cli/dist/cli.js"))
    if not cli_entry.is_file():
        raise TripoError("Official tripo-cli is not installed; see references/configuration.md")
    node = env.get("TRIPO_NODE") or settings.get("node") or shutil.which("node")
    if not node:
        raise TripoError("Node.js 20+ is required")

    state_root = expand_path(settings.get("state_dir") or str(Path.home() / ".local/share/tripo-skill/state"))
    state_dir = state_root / region
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        state_dir.chmod(0o700)
    # Credentials only enter the child environment; never persist in CLI config.
    env.update({
        "TRIPO_API_KEY": key, "TRIPO_REGION": region,
        # The CLI appends /v3 itself; Markdown config may include it.
        "TRIPO_API_BASE_URL": REGIONS[region],
        "TRIPO_PLATFORM_BASE_URL": "https://developers.tripo3d." + ("com" if region == "cn" else "ai"),
        "TRIPO_HOME": str(state_dir),
        "TRIPO_ANALYTICS_ENABLED": "0", "TRIPO_NO_UPDATE_CHECK": "1",
    })
    env.pop("TRIPO_PROFILE", None)
    return {"region": region, "node": node, "cli_entry": cli_entry, "env": env}


def requires_record(argv):
    if any(flag in argv for flag in ("--help", "-h", "--version", "-v")):
        return False
    words = []
    skip_profile = False
    for word in argv:
        if skip_profile:
            skip_profile = False
            continue
        if word == "--profile":
            skip_profile = True
            continue
        if not word.startswith("-"):
            words.append(word)
    if not words:
        return False
    command = words[0]
    if command == "make" and "--dry-run" in argv:
        return False
    return command in {"make", "generate", "model", "mesh", "anim", "redo", "batch", "ai"} or words[:2] == ["files", "upload"]


def write_private_json(path, value):
    data = (redact(json.dumps(value, ensure_ascii=False, indent=2)) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def execute(config, cli_args, record_dir=None):
    if requires_record(cli_args) and not record_dir:
        raise TripoError("This operation needs --record-dir pointing to a NEW directory before --")
    record = None
    if record_dir:
        record = expand_path(record_dir)
        record.parent.mkdir(parents=True, exist_ok=True)
        try:
            record.mkdir(mode=0o700)
        except FileExistsError:
            raise TripoError("Record directory already exists; inspect/resume that operation instead of resubmitting") from None
        version = None
        package_json = config["cli_entry"].parent.parent / "package.json"
        if package_json.exists():
            version = read_object(package_json).get("version")
        write_private_json(record / "invocation.json", {
            "started_at": timestamp(), "region": config["region"],
            "api_base_url": REGIONS[config["region"]], "cli_version": version,
            "cwd": str(Path.cwd()), "arguments": cli_args, "state": "dispatch_started",
        })

    command = [config["node"], str(config["cli_entry"]), "--no-open"] + cli_args
    logs, threads, failures = [], [], []
    process = None
    old_umask = os.umask(0o077)
    exit_code, interrupted = 1, False
    try:
        for name in ("stdout.ndjson", "stderr.log"):
            logs.append((record / name).open("x", encoding="utf-8") if record else None)
        process = subprocess.Popen(command, env=config["env"], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", bufsize=1)

        def forward(source, destination, log):
            try:
                for line in iter(source.readline, ""):
                    clean = redact(line)
                    if log:
                        log.write(clean)
                        log.flush()
                    destination.write(clean)
                    destination.flush()
            except (OSError, ValueError) as exc:
                failures.append(type(exc).__name__)
            finally:
                source.close()

        for source, destination, log in zip((process.stdout, process.stderr), (sys.stdout, sys.stderr), logs):
            thread = threading.Thread(target=forward, args=(source, destination, log), daemon=True)
            thread.start()
            threads.append(thread)
        exit_code = process.wait()
        if exit_code < 0:
            exit_code = 128 - exit_code
    except KeyboardInterrupt:
        interrupted = True
        if process:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        exit_code = 130
    except OSError:
        raise TripoError("Could not start Node/Tripo CLI; inspect this invocation before retrying", 1) from None
    finally:
        for thread in threads:
            thread.join()
        for log in logs:
            if log:
                log.close()
        os.umask(old_umask)
        if record:
            write_private_json(record / "completion.json", {
                "finished_at": timestamp(), "exit_code": exit_code,
                "state": "interrupted" if interrupted else ("cli_exited" if process else "launch_failed"),
                "output_forwarding_errors": failures,
            })
    if failures and exit_code == 0:
        raise TripoError("CLI exited successfully but output forwarding failed; inspect history before retrying", 1)
    return exit_code


def parser():
    result = argparse.ArgumentParser(description=__doc__, usage="%(prog)s [wrapper options] -- <Tripo CLI command and flags>")
    result.add_argument("--config", help="local non-secret settings JSON; default ~/.config/tripo-skill/config.json")
    result.add_argument("--credentials-file", help="private Markdown/dotenv credentials file")
    result.add_argument("--region", choices=sorted(REGIONS), help="account region; default configured region or cn")
    result.add_argument("--record-dir", help="NEW directory for a generation/processing invocation and its logs")
    result.add_argument("cli_args", nargs=argparse.REMAINDER)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    cli_args = args.cli_args
    if cli_args[:1] == ["--"]:
        cli_args = cli_args[1:]
    if not cli_args:
        cli_args = ["doctor", "--json"]
    try:
        config = configuration(args)
        return execute(config, cli_args, args.record_dir)
    except TripoError as exc:
        print(redact(json.dumps({"error": str(exc), "exit_code": exc.exit_code}, ensure_ascii=False)), file=sys.stderr)
        return exc.exit_code
    except (OSError, ValueError, TypeError):
        print('{"error":"Cannot load local configuration or write invocation records","exit_code":2}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
