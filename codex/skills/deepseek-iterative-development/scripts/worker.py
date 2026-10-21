#!/usr/bin/env python3
"""Supervise one external coding task; receipts never constitute acceptance."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

import configure_worker as configuration

FIELDS = {
    "schema_version", "task_id", "attempt", "run_id", "scope_revision", "workspace",
    "input_version", "input_fingerprint", "allowed_paths", "task_file", "task_sha256",
    "state_file", "output_dir", "timeout_seconds", "manifest_file",
}
CONTROL = None
# Dependency/cache trees are not source-scope boundaries. Tracked changes are still audited.
GENERATED_DIRS = {"node_modules", "Pods", ".build", ".venv", "venv", "__pycache__", ".gradle", "DerivedData"}


class Refused(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


class Cancelled(Exception):
    pass


def stamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def control():
    global CONTROL
    if CONTROL is None:
        path = Path(__file__).resolve().parents[2] / "iterative-development/scripts/run_control.py"
        if not path.is_file():
            raise Refused("missing_base_skill", "iterative-development/run_control.py is required.")
        spec = importlib.util.spec_from_file_location("deepseek_base_control", path)
        CONTROL = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(CONTROL)
    return CONTROL


def state_and_gate(path):
    module = control()
    state = module.read_state(Path(path))
    return state, module.view(state, datetime.now(timezone.utc))


def require_start(path):
    state, gate = state_and_gate(path)
    if not gate["may_start_task"]:
        raise Refused("work_not_allowed", "Run is paused, stopped, expired or closing; do not dispatch.")
    return state


def write_json(path, value):
    control().atomic_write(Path(path), value)


def absolute(value):
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise Refused("relative_path", "Use absolute paths in the task contract.")
    return path.resolve()


def git(workspace, *args):
    result = subprocess.run(["git", "-C", str(workspace), *args], capture_output=True, timeout=30)
    if result.returncode:
        raise Refused("git_failed", "Cannot inspect the task's Git workspace.")
    return result.stdout


def workspace_identity(workspace):
    top = Path(os.fsdecode(git(workspace, "rev-parse", "--show-toplevel")).strip()).resolve()
    if top != workspace:
        raise Refused("workspace_root", "Workspace must be the Git worktree root.")
    common = Path(os.fsdecode(git(workspace, "rev-parse", "--git-common-dir")).strip())
    return (workspace / common).resolve() if not common.is_absolute() else common.resolve()


def validate_project(workspace, state):
    if workspace_identity(workspace) != workspace_identity(absolute(state["project_root"])):
        raise Refused("wrong_project", "Worker and run project must belong to the same Git repository.")


def file_digest(path):
    if path.is_symlink():
        return "symlink:" + hashlib.sha256(os.fsencode(os.readlink(path))).hexdigest()
    if not path.exists():
        return "deleted"
    if not path.is_file():
        return "non-file"
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def under(path, parent):
    return path == parent or parent in path.parents


def snapshot(task):
    workspace = Path(task["workspace"])
    ignored = [Path(task[k]) for k in ("output_dir", "state_file", "task_file", "manifest_file")]
    ignored.append(Path(task["state_file"] + ".lock"))
    index_entries = {}
    for entry in git(workspace, "ls-files", "--stage", "-z").split(b"\0"):
        if entry:
            metadata, name = entry.split(b"\t", 1)
            index_entries.setdefault(os.fsdecode(name), []).append(metadata.decode("ascii"))
    # Porcelain -z handles spaces/newlines and includes the original name after a rename.
    entries = git(workspace, "status", "--porcelain=v1", "-z", "--untracked-files=all").split(b"\0")
    changed, index = {}, 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        code, name = entry[:2], os.fsdecode(entry[3:])
        names = [name]
        if b"R" in code or b"C" in code:
            if index < len(entries) and entries[index]:
                names.append(os.fsdecode(entries[index]))
                index += 1
        for name in names:
            path = workspace / name
            # Do not follow a tracked symlink into a different project or credentials.
            if any(under(path.absolute(), item) for item in ignored):
                continue
            changed[name] = (os.fsdecode(code) + ":" + file_digest(path)
                             + ":index=" + json.dumps(index_entries.get(name, [])))
    tracked = set(index_entries)
    excluded = []
    # Git status omits ignored files. Inventory nontracked project content as well, so an
    # ignored source/scratch file cannot silently escape the post-run scope check.
    for parent, directories, files in os.walk(workspace, topdown=True, followlinks=False):
        parent = Path(parent)
        retained = []
        for name in directories:
            path = parent / name
            relative = path.relative_to(workspace).as_posix()
            if name == ".git" or name in GENERATED_DIRS or any(under(path, item) for item in ignored):
                excluded.append(relative)
            elif path.is_symlink():
                if relative not in tracked and relative not in changed:
                    changed[relative] = "!!:" + file_digest(path)
            else:
                retained.append(name)
        directories[:] = retained
        for name in files:
            path = parent / name
            relative = path.relative_to(workspace).as_posix()
            if name == ".git" or relative in tracked or relative in changed or any(under(path, item) for item in ignored):
                continue
            changed[relative] = "!!:" + file_digest(path)
    head = git(workspace, "rev-parse", "HEAD").decode().strip()
    record = {"head": head, "changed": changed}
    fingerprint = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
    return {**record, "fingerprint": fingerprint, "audit_excluded_directories": sorted(excluded)}


def allowed_paths(values):
    result = []
    for value in values:
        path = PurePosixPath(value)
        if not path.parts or path.is_absolute() or ".." in path.parts or "\\" in value:
            raise Refused("invalid_scope", "Allowed paths must be nonempty relative paths without traversal.")
        result.append(str(path))
    if not result:
        raise Refused("invalid_scope", "Declare at least one allowed file or directory.")
    return sorted(set(result))


def path_allowed(name, scope):
    return any(name == item or name.startswith(item + "/") for item in scope)


def validate_task(task):
    if not isinstance(task, dict) or set(task) != FIELDS or task["schema_version"] != 1:
        raise Refused("invalid_contract", "Unrecognized or incomplete task contract.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", task["task_id"]):
        raise Refused("invalid_task_id", "Use a short stable task ID.")
    if type(task["attempt"]) is not int or task["attempt"] < 1:
        raise Refused("invalid_attempt", "attempt must be a positive integer.")
    if not isinstance(task["run_id"], str) or not task["run_id"] or type(task["scope_revision"]) is not int or task["scope_revision"] < 0:
        raise Refused("invalid_identity", "A run ID and nonnegative scope revision are required.")
    timeout = task["timeout_seconds"]
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise Refused("invalid_timeout", "Explicit positive finite task timeout is required.")
    for key in ("workspace", "task_file", "state_file", "output_dir", "manifest_file"):
        if str(absolute(task[key])) != task[key]:
            raise Refused("noncanonical_path", "Contract paths must be absolute and resolved.")
    if not Path(task["workspace"]).is_dir() or not Path(task["task_file"]).is_file():
        raise Refused("missing_input", "Task workspace and task file must exist.")
    if under(Path(task["workspace"]), Path(task["output_dir"])):
        raise Refused("invalid_output", "Output directory cannot contain the workspace.")
    if allowed_paths(task["allowed_paths"]) != task["allowed_paths"]:
        raise Refused("invalid_scope", "Use canonical sorted allowed paths.")
    return task


def binding(task, start=False):
    state, gate = state_and_gate(task["state_file"])
    if state["run_id"] != task["run_id"] or state["current"]["scope_revision"] != task["scope_revision"]:
        raise Refused("stale", "Task identity or scope revision no longer matches the run.")
    if not (gate["may_start_task"] if start else gate["may_work"]):
        raise Refused("stopped", "Run control does not permit this task to continue.")
    return state


def prepare(args):
    state = require_start(absolute(args.state))
    workspace = absolute(args.workspace)
    validate_project(workspace, state)
    manifest = absolute(args.manifest)
    if manifest.exists():
        raise Refused("existing_contract", "Keep old contracts; choose a new attempt/manifest path.")
    task = {
        "schema_version": 1, "task_id": args.task_id, "attempt": args.attempt,
        "run_id": state["run_id"], "scope_revision": state["current"]["scope_revision"],
        "workspace": str(workspace), "input_version": "", "input_fingerprint": "",
        "allowed_paths": allowed_paths(args.allow), "task_file": str(absolute(args.task_file)),
        "task_sha256": "", "state_file": str(absolute(args.state)),
        "output_dir": str(absolute(args.output_dir)), "timeout_seconds": args.timeout_seconds,
        "manifest_file": str(manifest),
    }
    validate_task(task)
    baseline = snapshot(task)
    task.update(input_version=baseline["head"], input_fingerprint=baseline["fingerprint"],
                task_sha256=file_digest(Path(task["task_file"])))
    manifest.parent.mkdir(parents=True, exist_ok=True)
    write_json(manifest, task)
    return {"ok": True, "manifest": str(manifest), "task_id": task["task_id"],
            "input_version": task["input_version"], "input_fingerprint": task["input_fingerprint"]}


def read_settings(path):
    settings = json.loads(Path(path).read_text(encoding="utf-8"))
    if settings.get("schema_version") != 1 or settings.get("provider") != "deepseek":
        raise Refused("invalid_settings", "Use the generated DeepSeek settings file.")
    for field in ("profile", "catalog"):
        if configuration.digest(settings[field + "_path"]) != settings[field + "_sha256"]:
            raise Refused("configuration_changed", "Generated configuration changed; inspect and reconfigure.")
    expected = Path(settings["profile_path"]).parent / (settings["profile"] + ".config.toml")
    if expected.resolve() != Path(settings["profile_path"]).resolve():
        raise Refused("profile_path", "Settings profile path and profile name disagree.")
    actual_home = configuration.codex_home()
    if expected.parent.resolve() != actual_home:
        raise Refused("codex_home_mismatch", "Settings must belong to the active CODEX_HOME.")
    if Path(settings["catalog_path"]).resolve() != actual_home / "model-catalogs" / (settings["profile"] + ".json"):
        raise Refused("catalog_path", "Catalog does not belong to this generated profile.")
    catalog = json.loads(Path(settings["catalog_path"]).read_text(encoding="utf-8"))
    try:
        configuration.build_catalog(catalog, settings["model"], settings["effort"])
    except ValueError:
        raise Refused("unsupported_model_configuration", "Model or effort is absent from the reviewed catalog.")
    profile_text = Path(settings["profile_path"]).read_text(encoding="utf-8")
    for key, value in (("model", settings["model"]), ("model_reasoning_effort", settings["effort"]),
                       ("model_provider", "deepseek"), ("model_catalog_json", settings["catalog_path"])):
        match = re.search(r"^" + key + r"\s*=\s*(.+)$", profile_text, re.MULTILINE)
        if not match or json.loads(match.group(1)) != value:
            raise Refused("settings_profile_mismatch", "Settings and the generated profile disagree.")
    if settings["auth"] not in {"env", "keychain"}:
        raise Refused("invalid_auth", "Unknown worker credential source.")
    if (settings["auth"] == "env") != ('env_key = "DEEPSEEK_API_KEY"' in profile_text):
        raise Refused("settings_profile_mismatch", "Settings credential source disagrees with the profile.")
    return settings


def credential_present(settings):
    if settings["auth"] == "env":
        return bool(os.environ.get("DEEPSEEK_API_KEY"))
    if sys.platform != "darwin":
        return False
    result = subprocess.run([
        "/usr/bin/security", "find-generic-password", "-a", settings["keychain_account"],
        "-s", settings["keychain_service"],
    ], capture_output=True, timeout=5)
    return result.returncode == 0


def doctor(settings_path, executable, check_credential=True):
    settings = read_settings(settings_path)
    binary = shutil.which(executable)
    if not binary:
        raise Refused("missing_cli", "Codex CLI is unavailable in this execution environment.")
    if os.name != "posix":
        raise Refused("unsupported_process_control", "This runner requires POSIX process groups.")
    help_result = subprocess.run([binary, "exec", "--help"], capture_output=True, timeout=15)
    text = help_result.stdout.decode(errors="replace")
    if help_result.returncode or any(flag not in text for flag in ("--profile", "--json", "--output-last-message")):
        raise Refused("unsupported_cli", "Codex CLI lacks required non-interactive options.")
    control()
    present = credential_present(settings) if check_credential else None
    return {"ok": present is not False, "cli": binary, "profile": settings["profile"],
            "requested_model": settings["model"], "requested_effort": settings["effort"],
            "effective_model": None, "effective_effort": None,
            "credential_present": present, "configuration_valid": True,
            "process_group_control": True, "api_tested": False}


@contextmanager
def workspace_lock(workspace):
    import fcntl
    directory = configuration.codex_home() / "deepseek-worker-locks"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (hashlib.sha256(str(workspace).encode()).hexdigest() + ".lock")
    with path.open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refused("workspace_busy", "Another supervised worker owns this workspace.")
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def live_group_members(pgid):
    result = subprocess.run(["ps", "-axo", "pid=,pgid=,stat="], capture_output=True, text=True, timeout=5)
    if result.returncode:
        raise RuntimeError("Cannot verify process group termination.")
    members = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1] == str(pgid) and not parts[2].startswith("Z"):
            members.append(int(parts[0]))
    return members


def end_group(proc):
    """Kill only the process group created for this invocation, including leftover children."""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        if live_group_members(proc.pid):
            raise
        proc.wait(timeout=5)
        return
    until = time.monotonic() + 1.5
    while time.monotonic() < until:
        proc.poll()
        if not live_group_members(proc.pid):
            break
        time.sleep(0.05)
    if live_group_members(proc.pid):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            if live_group_members(proc.pid):
                raise
    proc.wait(timeout=5)
    until = time.monotonic() + 1
    while live_group_members(proc.pid):
        if time.monotonic() >= until:
            raise RuntimeError("Live processes remain in the owned group.")
        time.sleep(0.05)


def command_for(task, settings, executable):
    quote = lambda value: json.dumps(str(value), ensure_ascii=False)
    return [
        executable, "exec", "--profile", settings["profile"], "--ephemeral",
        "--sandbox", "workspace-write", "--cd", task["workspace"], "--json",
        "--output-last-message", str(Path(task["output_dir"]) / "final.md"),
        "-c", 'approval_policy="never"', "-c", 'model_provider="deepseek"',
        "-c", "model=" + quote(settings["model"]),
        "-c", "model_reasoning_effort=" + quote(settings["effort"]),
        "-c", "model_catalog_json=" + quote(settings["catalog_path"]),
        "-c", "agents.enabled=false", "-c", 'web_search="disabled"',
        "-c", "features.apps=false", "-c", "features.plugins=false",
        "-c", "features.memories=false", "-c", "skills.bundled.enabled=false",
        "-c", "skills.include_instructions=false", "-",
    ]


def summary_events(path):
    result = {"turn_completed": False, "turn_failed": False, "usage": [], "thread_id": None}
    if not path.exists():
        return result
    with path.open(encoding="utf-8", errors="replace") as source:
        for line in source:
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if not isinstance(item, dict):
                continue
            if item.get("type") == "thread.started":
                result["thread_id"] = item.get("thread_id")
            if item.get("type") == "turn.completed":
                result["turn_completed"] = True
                if isinstance(item.get("usage"), dict):
                    keys = {"input_tokens", "output_tokens", "cached_input_tokens", "total_tokens", "reasoning_output_tokens"}
                    result["usage"].append({k: v for k, v in item["usage"].items()
                                            if k in keys and type(v) in (int, float) and math.isfinite(v) and v >= 0})
            if item.get("type") in {"turn.failed", "error"}:
                result["turn_failed"] = True
    return result


def execute(task, settings_path, executable):
    state = binding(task, start=True)
    validate_project(Path(task["workspace"]), state)
    baseline = snapshot(task)
    if baseline["head"] != task["input_version"] or baseline["fingerprint"] != task["input_fingerprint"]:
        raise Refused("stale_input", "Workspace changed after preparation; inspect and prepare a fresh task.")
    if file_digest(Path(task["task_file"])) != task["task_sha256"]:
        raise Refused("task_changed", "Task instructions changed after preparation.")
    output = Path(task["output_dir"])
    if output.exists():
        raise Refused("existing_output", "Keep previous results; use a fresh attempt/output directory.")
    output.mkdir(parents=True)
    receipt = {
        "schema_version": 1, "task_id": task["task_id"], "attempt": task["attempt"],
        "run_id": task["run_id"], "scope_revision": task["scope_revision"],
        "workspace": task["workspace"], "input_version": task["input_version"],
        "input_fingerprint": task["input_fingerprint"], "started_at_utc": stamp(),
        "status": "needs_codex_takeover", "reason": None, "worker_process_started": False,
        "requested_model": None, "requested_effort": None,
        "effective_model": None, "effective_effort": None, "process_group_stopped": True,
        "independent_acceptance": "not_performed", "exit_code": None,
        "context_mode": "minimal_worker",
    }
    proc, before = None, time.monotonic()
    previous_handlers = {}
    try:
        settings = read_settings(settings_path)
        checks = doctor(settings_path, executable)
        receipt.update(requested_model=settings["model"], requested_effort=settings["effort"])
        if not checks["credential_present"]:
            raise Refused("missing_credential", "DeepSeek credential is absent; no API process was started.")
        binding(task, start=True)
        if snapshot(task)["fingerprint"] != baseline["fingerprint"] or file_digest(Path(task["task_file"])) != task["task_sha256"]:
            raise Refused("stale_input", "Task changed during preflight.")
        if time.monotonic() - before >= task["timeout_seconds"]:
            raise Refused("task_timeout", "Task timeout was consumed by preflight; no API process was started.")
        # Instructions are piped, not embedded into shell command text or process arguments.
        prompt = ("Execution role: DeepSeek worker. Do not invoke the collaboration skill or spawn agents.\n"
                  "Task ID: " + task["task_id"] + "; run ID: " + task["run_id"] + "\n"
                  "Allowed modification paths: " + json.dumps(task["allowed_paths"], ensure_ascii=False) + "\n"
                  "Preserve other user work. Do not commit/push, publish, change credentials, or modify run control.\n"
                  "Report actual changes/checks and blockers; do not claim independent acceptance.\n\n"
                  + Path(task["task_file"]).read_text(encoding="utf-8"))
        environment = dict(os.environ)
        environment["CODEX_DEEPSEEK_WORKER"] = "1"
        def cancel(signum, frame):
            raise Cancelled()
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous_handlers[sig] = signal.signal(sig, cancel)
        with (output / "events.jsonl").open("wb") as events, (output / "stderr.log").open("wb") as errors, tempfile.TemporaryFile() as prompt_input:
            prompt_input.write(prompt.encode("utf-8"))
            prompt_input.seek(0)
            proc = subprocess.Popen(command_for(task, settings, checks["cli"]),
                                    stdin=prompt_input, stdout=events, stderr=errors,
                                    cwd=task["workspace"], env=environment, start_new_session=True)
            receipt["worker_process_started"] = True
            receipt["process_group_stopped"] = False
            while proc.poll() is None:
                binding(task)
                if time.monotonic() - before >= task["timeout_seconds"]:
                    raise Refused("task_timeout", "Task timeout reached while the run still permits work.")
                time.sleep(0.1)
            receipt["exit_code"] = proc.returncode
            # A process ending exactly at a stop/deadline must not become a handoff for new work.
            binding(task)
        event_summary = summary_events(output / "events.jsonl")
        receipt.update(events=event_summary)
        final = output / "final.md"
        if proc.returncode != 0 or event_summary["turn_failed"] or not event_summary["turn_completed"] or not final.is_file() or final.stat().st_size == 0:
            raise Refused("worker_failed", "Worker did not produce a complete unreviewed handoff; inspect logs.")
        receipt.update(status="completed_unreviewed", reason="handoff_requires_independent_review")
    except Cancelled:
        receipt.update(status="stopped", reason="supervisor_cancelled")
    except Refused as exc:
        receipt.update(status=exc.code if exc.code in {"stopped", "stale"} else "needs_codex_takeover", reason=exc.code)
    except Exception as exc:
        # Do not echo arbitrary tool output, environment values or provider error bodies.
        receipt.update(status="needs_codex_takeover", reason="supervisor_error:" + type(exc).__name__)
    finally:
        if proc is not None:
            try:
                end_group(proc)
                receipt["process_group_stopped"] = True
                receipt["exit_code"] = proc.returncode
            except Exception as exc:
                receipt.update(status="stopped", reason="process_stop_unconfirmed:" + type(exc).__name__)
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)
        try:
            after = snapshot(task)
        except Exception:
            after = baseline
            receipt.update(status="needs_codex_takeover", reason="output_audit_failed", output_audit_complete=False)
        changed = sorted(name for name in set(baseline["changed"]) | set(after["changed"])
                         if baseline["changed"].get(name) != after["changed"].get(name))
        outside = [name for name in changed if not path_allowed(name, task["allowed_paths"])]
        receipt.update(output_version=after["head"], output_fingerprint=after["fingerprint"],
                       changed_paths=changed, out_of_scope_paths=outside,
                       audit_excluded_directories=after.get("audit_excluded_directories", []),
                       finished_at_utc=stamp(), elapsed_seconds=round(time.monotonic() - before, 3),
                       report_path=str(output / "final.md"), events_path=str(output / "events.jsonl"))
        if (outside or after["head"] != baseline["head"]) and receipt["status"] == "completed_unreviewed":
            receipt.update(status="needs_codex_takeover", reason="scope_or_history_changed")
        # A pause/deadline during cleanup dominates a takeover request.
        try:
            binding(task)
        except Refused as exc:
            if exc.code in {"stopped", "stale"}:
                receipt.update(status=exc.code, reason=exc.code)
        except Exception:
            receipt.update(status="stopped", reason="control_unreadable")
        write_json(output / "receipt.json", receipt)
    return receipt


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    for name in ("doctor", "run"):
        sub = commands.add_parser(name)
        sub.add_argument("--settings", default=str(configuration.codex_home() / "deepseek-worker.settings.json"))
        sub.add_argument("--codex-bin", default="codex")
        if name == "run":
            sub.add_argument("--manifest", required=True)
            sub.add_argument("--dry-run", action="store_true")
    sub = commands.add_parser("prepare")
    for option in ("state", "workspace", "task-id", "task-file", "output-dir", "manifest"):
        sub.add_argument("--" + option, required=True)
    sub.add_argument("--attempt", type=int, required=True)
    sub.add_argument("--allow", action="append", required=True)
    sub.add_argument("--timeout-seconds", type=float, required=True)
    args = cli.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(args)
        elif args.command == "doctor":
            result = doctor(args.settings, args.codex_bin)
        else:
            manifest = absolute(args.manifest)
            task = validate_task(json.loads(manifest.read_text(encoding="utf-8")))
            if task["manifest_file"] != str(manifest):
                raise Refused("contract_path_changed", "Use the original task contract path.")
            with workspace_lock(Path(task["workspace"])):
                binding(task, start=True)
                if args.dry_run:
                    checks = doctor(args.settings, args.codex_bin, check_credential=False)
                    settings = read_settings(args.settings)
                    current = snapshot(task)
                    if current["fingerprint"] != task["input_fingerprint"] or file_digest(Path(task["task_file"])) != task["task_sha256"]:
                        raise Refused("stale_input", "Task or workspace changed after preparation.")
                    result = {"ok": True, "dry_run": True, "api_tested": False,
                              "command": command_for(task, settings, checks["cli"])}
                else:
                    result = execute(task, args.settings, args.codex_bin)
        print(json.dumps(result, ensure_ascii=False))
        if "status" in result:
            return {"completed_unreviewed": 0, "needs_codex_takeover": 10, "stopped": 11, "stale": 12}[result["status"]]
        return 0 if result.get("ok") else 2
    except Refused as exc:
        result = {"ok": False, "error": exc.code, "message": exc.message}
    except Exception as exc:
        result = {"ok": False, "error": type(exc).__name__, "message": "Preparation failed; inspect local inputs/configuration."}
    print(json.dumps(result, ensure_ascii=False))
    return 2


if __name__ == "__main__":
    sys.exit(main())
