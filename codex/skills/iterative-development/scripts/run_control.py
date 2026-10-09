#!/usr/bin/env python3
"""Small, standard-library run gate. It never starts tasks or renews a budget."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import tempfile
import time


CURRENT_FIELDS = {
    "scope_revision", "scope_path", "tasks", "latest_candidate",
    "last_verified_candidate", "review", "execution", "final_report",
}
ADMIN_FIELDS = {"phase", "review", "execution", "final_report"}
TOP_FIELDS = {
    "schema_version", "run_id", "revision", "coordinator_id", "project_root",
    "started_at_utc", "close_at_utc", "deadline_utc", "status", "phase", "current",
}


class Refused(Exception):
    def __init__(self, code, message, exit_code=2, **details):
        self.code, self.message, self.exit_code = code, message, exit_code
        self.details = details


class JsonParser(argparse.ArgumentParser):
    def error(self, message):
        raise Refused("arguments", message)


def stamp(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def utc(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise ValueError("UTC offset required")
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        raise Refused("invalid_timestamp", "Use an absolute UTC timestamp, e.g. 2026-10-09T12:00:00Z.")


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def text_value(value):
    return isinstance(value, str) and bool(value.strip())


def validate_field(key, value):
    if key == "scope_revision":
        valid = integer(value)
    elif key in {"phase", "scope_path", "final_report"}:
        valid = text_value(value) or (key != "phase" and value is None)
    elif key == "tasks":
        valid = isinstance(value, list)
    elif key == "execution":
        valid = isinstance(value, dict)
    else:
        valid = value is None or isinstance(value, dict)
    if not valid:
        raise Refused("invalid_field", "Invalid value for " + key + ".")
    if key == "last_verified_candidate" and value is not None:
        allowed = {"version", "report", "entry", "candidate_id"}
        if (set(value) - allowed or not text_value(value.get("version"))
                or not text_value(value.get("report"))
                or any(not text_value(item) for item in value.values())):
            raise Refused("invalid_reference", "last_verified_candidate needs exact version/report references; optional entry/candidate_id only.")


def read_state(path):
    with path.open(encoding="utf-8") as source:
        state = json.load(source)
    if (not isinstance(state, dict) or set(state) != TOP_FIELDS
            or state.get("schema_version") != 1 or not integer(state.get("revision"))
            or state.get("status") not in {"active", "paused", "stopped"}
            or not isinstance(state.get("current"), dict)
            or set(state["current"]) != CURRENT_FIELDS):
        raise Refused("invalid_state", "Unrecognized or incomplete run state.")
    for key in {"run_id", "coordinator_id", "project_root", "phase"}:
        if not text_value(state.get(key)):
            raise Refused("invalid_state", "Missing " + key + ".")
    start, close, deadline = [utc(state[key]) for key in ("started_at_utc", "close_at_utc", "deadline_utc")]
    if not start < close <= deadline:
        raise Refused("invalid_state", "Run timestamps are inconsistent.")
    for key, value in state["current"].items():
        validate_field(key, value)
    return state


@contextmanager
def file_lock(path):
    """OS-owned lock, automatically released when the process exits. Keep its inode."""
    with path.with_name(path.name + ".lock").open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        end = time.monotonic() + 3
        while True:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= end:
                    raise Refused("lock_busy", "State is busy; retry with the latest revision.", 5)
                time.sleep(0.025)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def atomic_write(path, state):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=path.parent, prefix=path.name + ".", suffix=".tmp", delete=False) as target:
            temporary = Path(target.name)
            json.dump(state, target, ensure_ascii=False, indent=2, allow_nan=False)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def view(state, now):
    remaining = (utc(state["deadline_utc"]) - now).total_seconds()
    effective = state["status"]
    if effective != "stopped" and remaining <= 0:
        effective = "expired"
    closing = effective == "active" and now >= utc(state["close_at_utc"])
    may_work = effective == "active"
    return {
        "ok": True, "run_id": state["run_id"], "revision": state["revision"],
        "status": state["status"], "effective_state": effective, "phase": state["phase"],
        "deadline_utc": state["deadline_utc"], "close_at_utc": state["close_at_utc"],
        "remaining_seconds": max(0, remaining), "closing": closing,
        "may_work": may_work, "may_start_task": may_work and not closing,
        "message": ("Closing window: finish existing work and prepare delivery."
                    if closing else "Work allowed." if may_work else "Work is not allowed; no automatic resume."),
    }


def initialize(args, now):
    if not text_value(args.run_id) or not text_value(args.coordinator_id):
        raise Refused("invalid_identity", "run_id and coordinator_id must be nonempty.")
    root = Path(args.project_root).expanduser()
    if not root.is_absolute():
        raise Refused("invalid_root", "project_root must be an absolute path.")
    if args.deadline_utc:
        deadline = utc(args.deadline_utc)
    else:
        if not math.isfinite(args.hours) or args.hours <= 0:
            raise Refused("invalid_budget", "hours must be finite and positive.")
        deadline = now + timedelta(hours=args.hours)
    duration = (deadline - now).total_seconds()
    if duration <= 0 or not math.isfinite(args.closing_minutes) or args.closing_minutes <= 0:
        raise Refused("invalid_budget", "Deadline must be in the future and closing_minutes positive.")
    # Short runs reserve at most one fifth of their budget for closing.
    closing_seconds = min(args.closing_minutes * 60, duration / 5)
    return {
        "schema_version": 1, "run_id": args.run_id, "revision": 0,
        "coordinator_id": args.coordinator_id, "project_root": str(root),
        "started_at_utc": stamp(now), "close_at_utc": stamp(deadline - timedelta(seconds=closing_seconds)),
        "deadline_utc": stamp(deadline), "status": "active", "phase": "planning",
        "current": {"scope_revision": 0, "scope_path": None, "tasks": [],
                    "latest_candidate": None, "last_verified_candidate": None,
                    "review": None, "execution": {}, "final_report": None},
    }


def apply_patch(state, patch, now):
    if not isinstance(patch, dict) or not patch or set(patch) - (CURRENT_FIELDS | {"phase"}):
        raise Refused("invalid_patch", "Patch must contain only nonempty whitelisted current fields or phase.")
    if not view(state, now)["may_work"] and set(patch) - ADMIN_FIELDS:
        raise Refused("work_not_allowed", "Paused, stopped or expired runs accept closing metadata only.", 3)
    for key, value in patch.items():
        validate_field(key, value)
    old_scope = state["current"]["scope_revision"]
    new_scope = patch.get("scope_revision", old_scope)
    if new_scope < old_scope:
        raise Refused("scope_regression", "scope_revision cannot decrease.", 4)
    if ("scope_path" in patch and patch["scope_path"] != state["current"]["scope_path"]
            and new_scope <= old_scope):
        raise Refused("scope_revision_required", "Changing scope_path needs a greater scope_revision.", 4)
    for key, value in patch.items():
        if key == "phase":
            state[key] = value
        else:
            state["current"][key] = value


def parser():
    cli = JsonParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True, parser_class=JsonParser)
    for name in ("init", "check", "update", "pause", "resume", "stop"):
        command = commands.add_parser(name)
        command.add_argument("--state", required=True, help="Path to this run's state JSON.")
        if name != "check":
            command.add_argument("--coordinator-id", required=True)
        if name not in {"init", "check"}:
            command.add_argument("--expected-revision", required=True, type=int)
        if name == "init":
            command.add_argument("--run-id", required=True)
            command.add_argument("--project-root", required=True)
            budget = command.add_mutually_exclusive_group(required=True)
            budget.add_argument("--deadline-utc")
            budget.add_argument("--hours", type=float)
            command.add_argument("--closing-minutes", type=float, default=5)
        elif name == "update":
            patch = command.add_mutually_exclusive_group(required=True)
            patch.add_argument("--patch-json")
            patch.add_argument("--patch-file")
        elif name == "resume":
            command.add_argument("--authorization", required=True, help="Reference or quotation of explicit human resume authorization.")
        elif name == "stop":
            command.add_argument("--reason", default="stopped")
    return cli


def main(argv=None, now=None):
    fixed_now = now
    now = now or datetime.now(timezone.utc)
    try:
        args = parser().parse_args(argv)
        path = Path(args.state).expanduser().absolute()
        if args.command == "check":
            result = view(read_state(path), now)
            exit_code = 0 if result["may_work"] else 3
        else:
            if args.command == "init":
                path.parent.mkdir(parents=True, exist_ok=True)
            with file_lock(path):
                # A competing writer can hold the lock across the deadline.
                now = fixed_now or datetime.now(timezone.utc)
                if args.command == "init":
                    if path.exists():
                        raise Refused("already_exists", "init will not overwrite an existing state.", 4)
                    state = initialize(args, now)
                else:
                    state = read_state(path)
                    if args.coordinator_id != state["coordinator_id"]:
                        raise Refused("wrong_coordinator", "Only the recorded coordinator may write this state.", 3)
                    if args.expected_revision != state["revision"]:
                        raise Refused("revision_conflict", "Read the latest state before retrying.", 4,
                                      current_revision=state["revision"])
                    if args.command == "update":
                        if args.patch_file:
                            with Path(args.patch_file).open(encoding="utf-8-sig") as source:
                                patch = json.load(source)
                        else:
                            patch = json.loads(args.patch_json)
                        apply_patch(state, patch, now)
                    elif args.command == "stop":
                        state["status"], state["phase"] = "stopped", "stopped"
                        state["current"]["execution"].update(stop_reason=args.reason, stopped_at_utc=stamp(now))
                    elif args.command == "pause":
                        if state["status"] != "active" or now >= utc(state["deadline_utc"]):
                            raise Refused("cannot_pause", "Only an unexpired active run can pause.", 3)
                        state["status"] = "paused"
                    elif args.command == "resume":
                        if not text_value(args.authorization):
                            raise Refused("authorization_required", "Explicit human resume authorization must be referenced.", 3)
                        if state["status"] != "paused" or now >= utc(state["deadline_utc"]):
                            raise Refused("cannot_resume", "Only a paused, unexpired run may resume; stopped runs are terminal.", 3)
                        state["status"] = "active"
                        state["current"]["execution"]["resume_authorization"] = args.authorization
                    state["revision"] += 1
                atomic_write(path, state)
                result = view(state, now)
                result["state"] = str(path)
                exit_code = 0
    except Refused as error:
        result = {"ok": False, "error": {"code": error.code, "message": error.message, **error.details}}
        exit_code = error.exit_code
    except (OSError, ValueError, OverflowError) as error:
        result = {"ok": False, "error": {"code": "io_or_json_error", "message": str(error)}}
        exit_code = 6
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
