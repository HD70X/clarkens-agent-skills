#!/usr/bin/env python3
"""Configure MiniMax with hidden input; no credential in arguments or stdout."""
from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import subprocess
import sys

from minimax_config import (DEFAULT_MODEL, R2_FIELDS, VideoError, api_host, api_key,
                            config_path, emit, read_env, remember_secrets, save_config, safe_error)


def hidden_key(gui=False):
    if gui:
        if sys.platform != "darwin":
            raise VideoError("The native hidden-input dialog is available on macOS; use terminal input instead")
        script = '''
with timeout of 1800 seconds
    set answer to display dialog "请输入 MiniMax 国内/国际站的按量付费 API Key。\n密钥仅保存到本机私有配置，不会显示在聊天或命令行。" default answer "" with hidden answer buttons {"取消", "保存"} default button "保存" cancel button "取消" with title "MiniMax 官方视频 API 配置"
    return text returned of answer
end timeout
'''
        try:
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=1805)
        except (OSError, subprocess.TimeoutExpired):
            raise VideoError("Could not complete the native credential dialog; use terminal hidden input") from None
        if result.returncode:
            raise VideoError("Credential input cancelled; existing configuration was preserved")
        return result.stdout.strip()
    if not sys.stdin.isatty():
        raise VideoError("Use --gui on macOS, an interactive terminal, or --from-env; do not send the key in chat")
    return getpass.getpass("Official MiniMax pay-as-you-go API key (hidden): ").strip()


def configure(args):
    path = config_path(args.env_file)
    values = read_env(path)
    remember_secrets(values)
    if args.region is not None:
        values["MINIMAX_API_HOST"] = "https://api.minimax.cn" if args.region == "cn" else "https://api.minimax.io"
    else:
        values.setdefault("MINIMAX_API_HOST", "https://api.minimax.cn")
    values.setdefault("MINIMAX_VIDEO_MODEL", DEFAULT_MODEL)
    if args.from_env:
        key = os.environ.get("MINIMAX_API_KEY", "")
    elif values.get("MINIMAX_API_KEY") and not args.replace_key:
        key = values["MINIMAX_API_KEY"]
    else:
        key = hidden_key(args.gui)
    values["MINIMAX_API_KEY"] = key
    api_key(values)
    api_host(values)
    copied = False
    if args.reuse_nxtpath_r2:
        old = Path(os.environ.get("NXTPATH_ENV_FILE") or Path.home() / ".config/nxtpath/env").expanduser()
        previous = read_env(old, prefix="NXTPATH_R2_")
        previous.update({k: v for k, v in os.environ.items() if k.startswith("NXTPATH_R2_") and v})
        if all(previous.get("NXTPATH_R2_" + field) for field in R2_FIELDS):
            for field in R2_FIELDS:
                values.setdefault("MINIMAX_R2_" + field, previous["NXTPATH_R2_" + field])
            copied = True
    remember_secrets(values)
    save_config(path, values)
    return {"env_file": str(path), "api_key_configured": True, "api_host": values["MINIMAX_API_HOST"],
            "default_model": values["MINIMAX_VIDEO_MODEL"], "r2_configured": all(values.get("MINIMAX_R2_" + f) for f in R2_FIELDS),
            "r2_credentials_reused": copied, "paid_task_created": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--region", choices=("cn", "global"), help="Preserve the saved region; default to China on first setup")
    parser.add_argument("--gui", action="store_true", help="Use a native macOS hidden-input dialog")
    parser.add_argument("--from-env", action="store_true", help="Read MINIMAX_API_KEY from the process environment")
    parser.add_argument("--replace-key", action="store_true")
    parser.add_argument("--reuse-nxtpath-r2", action="store_true", help="Copy only the four private R2 settings, never the gateway API key")
    args = parser.parse_args()
    try:
        emit(configure(args))
        return 0
    except (VideoError, OSError, ValueError, KeyboardInterrupt) as exc:
        print(safe_error(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
