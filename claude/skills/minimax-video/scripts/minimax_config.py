"""Private local configuration shared by the official MiniMax video tools."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shlex
import tempfile

DEFAULT_HOST = "https://api.minimax.cn"
OFFICIAL_HOSTS = {DEFAULT_HOST, "https://api.minimaxi.com", "https://api.minimax.io"}
DEFAULT_MODEL = "MiniMax-H3"
R2_FIELDS = ("ACCOUNT_ID", "BUCKET", "ACCESS_KEY_ID", "SECRET_ACCESS_KEY")
SECRETS: set[str] = set()


class VideoError(Exception):
    pass


def redact(value):
    text = str(value)
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


def safe_error(value):
    text = redact(value)
    text = re.sub(r"https?://[^\s\"'<>]+|data:[^\s\"'<>]+", "[URL redacted]", text)
    return text[:800]


def emit(value):
    print(redact(json.dumps(value, ensure_ascii=False)))


def config_path(value=None):
    return Path(value or os.environ.get("MINIMAX_ENV_FILE") or Path.home() / ".config/minimax/env").expanduser()


def read_env(path, prefix="MINIMAX_"):
    """Parse assignments as data; never source or execute a configuration file."""
    path = Path(path)
    values = {}
    if not path.exists():
        return values
    if not path.is_file() or path.stat().st_mode & 0o077:
        raise VideoError("The credential file must be a private regular file (mode 600)")
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"\s*(?:export\s+)?([A-Z][A-Z0-9_]+)\s*=(.*)", line)
        if not match:
            raise VideoError(f"Unsupported credential-file assignment on line {number}")
        if not match[1].startswith(prefix):
            continue
        try:
            parts = shlex.split(match[2], comments=True, posix=True)
        except ValueError:
            raise VideoError(f"Invalid credential-file quoting on line {number}") from None
        if len(parts) > 1:
            raise VideoError(f"Quote the credential-file value on line {number}")
        values[match[1]] = parts[0] if parts else ""
    return values


def remember_secrets(values):
    for name in ("MINIMAX_API_KEY", "MINIMAX_R2_ACCESS_KEY_ID", "MINIMAX_R2_SECRET_ACCESS_KEY"):
        if values.get(name):
            SECRETS.add(values[name])


def load_config(value=None):
    path = config_path(value)
    values = read_env(path)
    values.update({k: v for k, v in os.environ.items() if k.startswith("MINIMAX_") and v})
    remember_secrets(values)
    return values, path


def api_host(config):
    host = config.get("MINIMAX_API_HOST", DEFAULT_HOST).rstrip("/")
    if host not in OFFICIAL_HOSTS:
        raise VideoError("MINIMAX_API_HOST must select an official MiniMax China or international API host")
    return host


def api_key(config):
    key = config.get("MINIMAX_API_KEY", "").strip()
    if not key or any(c.isspace() for c in key) or not key.isascii():
        raise VideoError("Configure an official pay-as-you-go MINIMAX_API_KEY with scripts/configure.py")
    SECRETS.add(key)
    return key


def save_config(path, values):
    path = Path(path)
    if path.is_symlink():
        raise VideoError("Refusing to replace a symlink credential file")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    data = "# Official MiniMax API; private local configuration, never commit.\n"
    data += "".join(f"export {k}={shlex.quote(v)}\n" for k, v in sorted(values.items()) if k.startswith("MINIMAX_"))
    descriptor, temporary = tempfile.mkstemp(prefix=".env-", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
