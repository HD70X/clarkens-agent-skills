#!/usr/bin/env python3
"""Create a separate worker profile; never change the primary login or store a key."""
import argparse
from datetime import datetime, timezone
import getpass
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import urllib.request

SOURCE = "https://api-docs.deepseek.com/quick_start/agent_integrations/codex/"
INSTRUCTIONS = (
    "You are a coding execution agent operating for a Codex coordinator. "
    "Implement the supplied task in its workspace, preserve existing user work, "
    "respect its modification scope and acceptance criteria, and report actual checks. "
    "Do not delegate again, publish, push, alter credentials, or change task scope. "
    "A completion report is not independent acceptance."
)


class CodeBlocks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth, self.parts, self.blocks = 0, [], []

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self.depth += 1
            self.parts = []

    def handle_endtag(self, tag):
        if tag == "pre" and self.depth:
            self.blocks.append("".join(self.parts))
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def codex_home():
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().resolve()


def catalog_from_source(path=None):
    if path:
        return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    request = urllib.request.Request(SOURCE, headers={"User-Agent": "codex-deepseek-skill/1"})
    with urllib.request.urlopen(request, timeout=25) as response:
        if not response.geturl().startswith("https://api-docs.deepseek.com/"):
            raise ValueError("Unexpected documentation redirect.")
        content = response.read(4 * 1024 * 1024 + 1)
    if len(content) > 4 * 1024 * 1024:
        raise ValueError("Documentation exceeds expected size.")
    parser = CodeBlocks()
    parser.feed(content.decode("utf-8"))
    for block in parser.blocks:
        try:
            data = json.loads(block)
        except ValueError:
            continue
        if isinstance(data, dict) and isinstance(data.get("models"), list):
            return data
    raise ValueError("Official page contains no recognizable model catalog.")


def build_catalog(source, model, effort):
    models = source.get("models") if isinstance(source, dict) else None
    if not isinstance(models, list):
        raise ValueError("A catalog with a models array is required.")
    entry = next((m for m in models if isinstance(m, dict) and m.get("slug") == model), None)
    if entry is None:
        raise ValueError("Requested model is absent from supplied catalog.")
    supported = {m.get("effort") for m in entry.get("supported_reasoning_levels", []) if isinstance(m, dict)}
    if effort not in supported:
        raise ValueError("Requested reasoning effort is not declared by this model.")
    if not isinstance(entry.get("context_window"), int) or entry["context_window"] <= 0:
        raise ValueError("Model context metadata is missing.")
    result = dict(entry)
    result["base_instructions"] = INSTRUCTIONS
    result["model_messages"] = {"instructions_template": INSTRUCTIONS, "instructions_variables": {}, "approvals": None}
    result["description"] = "External coding worker; independently reviewed by Codex."
    result["auto_review_model_override"] = None
    result["supports_search_tool"] = False
    return {"models": [result]}


def install(home, model, effort, profile, auth, catalog, replace=False):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", profile):
        raise ValueError("Use a lowercase profile name with letters, digits and hyphens.")
    home = Path(home).expanduser().resolve()
    profile_path = home / (profile + ".config.toml")
    settings_path = home / (profile + ".settings.json")
    catalog_path = home / "model-catalogs" / (profile + ".json")
    paths = (profile_path, settings_path, catalog_path)
    if not replace and any(p.exists() for p in paths):
        raise ValueError("Target files exist; inspect before using --replace.")
    account = getpass.getuser()
    quote = lambda value: json.dumps(str(value), ensure_ascii=False)
    lines = [
        'model = ' + quote(model), 'model_provider = "deepseek"',
        'model_reasoning_effort = ' + quote(effort),
        'model_catalog_json = ' + quote(catalog_path), 'web_search = "disabled"',
        'sandbox_mode = "workspace-write"', 'approval_policy = "never"',
        '', '[agents]', 'enabled = false', '', '[model_providers.deepseek]',
        'name = "DeepSeek worker"', 'base_url = "https://api.deepseek.com/"',
        'wire_api = "responses"', 'requires_openai_auth = false', 'request_max_retries = 2',
    ]
    if auth == "keychain":
        if sys.platform != "darwin":
            raise ValueError("Keychain requires macOS; use --auth env elsewhere.")
        lines += ['', '[model_providers.deepseek.auth]', 'command = "/usr/bin/security"',
                  'args = ["find-generic-password", "-a", ' + quote(account) + ', "-s", "codex-deepseek", "-w"]',
                  'timeout_ms = 10000', 'refresh_interval_ms = 300000']
    else:
        lines.append('env_key = "DEEPSEEK_API_KEY"')
    lines += ['', '[shell_environment_policy.filters]',
              '"*API_KEY*" = "exclude"', '"*ACCESS_TOKEN*" = "exclude"', '']
    home.mkdir(parents=True, exist_ok=True)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    profile_path.write_text("\n".join(lines), encoding="utf-8")
    settings = {
        "schema_version": 1, "profile": profile, "model": model, "effort": effort,
        "provider": "deepseek", "auth": auth, "keychain_account": account,
        "keychain_service": "codex-deepseek", "profile_path": str(profile_path),
        "catalog_path": str(catalog_path), "profile_sha256": digest(profile_path),
        "catalog_sha256": digest(catalog_path), "catalog_source": SOURCE,
        "configured_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for path in paths:
        path.chmod(0o600)
    return {"ok": True, "settings": str(settings_path), "profile": str(profile_path),
            "catalog": str(catalog_path), "model": model, "effort": effort,
            "auth": auth, "credential_written": False, "primary_config_changed": False}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--codex-home", type=Path, default=codex_home())
    cli.add_argument("--model", default="deepseek-flash")
    cli.add_argument("--effort", default="high")
    cli.add_argument("--profile", default="deepseek-worker")
    cli.add_argument("--auth", choices=("keychain", "env"), default="keychain" if sys.platform == "darwin" else "env")
    cli.add_argument("--catalog-source", help="Reviewed local JSON instead of official documentation.")
    cli.add_argument("--replace", action="store_true")
    args = cli.parse_args()
    try:
        catalog = build_catalog(catalog_from_source(args.catalog_source), args.model, args.effort)
        result = install(args.codex_home, args.model, args.effort, args.profile, args.auth, catalog, args.replace)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
