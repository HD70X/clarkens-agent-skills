#!/usr/bin/env python3
"""Install the complete skill without copying credentials or task state."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


def default_target():
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    legacy = codex_home / "skills"
    modern = Path.home() / ".agents/skills"
    # Keep a device's established location, without creating duplicate discoveries.
    root = legacy if legacy.exists() or "CODEX_HOME" in os.environ else modern
    return root / "gemini-bridge"


def install(target, upgrade=False):
    source = Path(__file__).resolve().parents[1]
    target = Path(target).expanduser().absolute()
    if target.resolve() == source:
        return {"installed": str(target), "status": "already_running_from_installation"}
    if target.name != "gemini-bridge":
        raise ValueError("Target must be the full skill folder ending in gemini-bridge.")
    if source in target.resolve().parents:
        raise ValueError("Installation target cannot be inside the skill source.")
    if target.is_symlink():
        raise ValueError("Refusing to replace a symlink. Choose one explicit skill installation location.")
    if target.exists() and not upgrade:
        raise ValueError("Target exists. Use --upgrade to replace it with a backup outside skill discovery.")
    target.parent.mkdir(parents=True, exist_ok=True)
    staged_parent = Path(tempfile.mkdtemp(prefix="gemini-install-", dir=str(target.parent)))
    staged = staged_parent / "gemini-bridge"
    backup = None
    try:
        shutil.copytree(source, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
        if target.exists():
            backup_root = target.parent.parent / "skill-backups"
            backup_root.mkdir(parents=True, exist_ok=True)
            backup = backup_root / ("gemini-bridge-" + time.strftime("%Y%m%d-%H%M%S") + "-" + staged_parent.name)
            shutil.move(str(target), str(backup))
        try:
            os.replace(staged, target)
        except BaseException:
            if backup and not target.exists():
                shutil.move(str(backup), str(target))
            raise
    finally:
        shutil.rmtree(staged_parent, ignore_errors=True)
    return {"installed": str(target), "backup": str(backup) if backup else None,
            "credential_copied": False, "default_model": None}


def main():
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=default_target())
    parser.add_argument("--upgrade", action="store_true")
    parser.add_argument("--configure", action="store_true", help="Prompt locally for this device's Gemini API key")
    parser.add_argument("--gui", action="store_true", help="Use the macOS hidden-input dialog when configuring")
    args = parser.parse_args()
    result = install(args.target, args.upgrade)
    # ASCII JSON is portable even when Windows captures stdout in a legacy code page.
    print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)
    if args.configure:
        cmd = [sys.executable, str(args.target / "scripts/gemini.py"), "configure"]
        if args.gui:
            cmd.append("--gui")
        return subprocess.call(cmd)
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        sys.exit(main())
    except (ValueError, OSError) as exc:
        print("Installation failed: %s" % exc, file=sys.stderr)
        sys.exit(2)
