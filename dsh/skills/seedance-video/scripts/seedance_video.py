#!/usr/bin/env python3
"""Prepare, submit, recover and download official Seedance video jobs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import hashlib
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib import error, parse, request
import warnings

from ark_request import API_ROOTS, MAX_REQUEST_BYTES, RATIOS, VideoError, build_request, json_bytes, require_https


PROVIDER = "seedance-official"
TASKS_PATH = "/contents/generations/tasks"
STATUSES = {"queued", "running", "succeeded", "failed", "cancelled", "expired"}
USER_AGENT = "seedance-video-skill/1"
NETWORK_ERRORS = (OSError, HTTPException, ValueError)


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class ArkError(VideoError):
    def __init__(self, status, code, detail):
        self.status = status
        self.code = code
        self.detail = detail
        super().__init__(f"Ark HTTP {status}" + (f" ({code})." if code else "."))


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_record(path, value, exclusive=False):
    data = json_bytes(value)
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return
    write_private(path, data)


def write_private(path, data):
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def read_record(path):
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise VideoError(f"Invalid local record {path.name}.")
    return value


def key_path(region):
    return Path.home() / ".config" / "seedance" / region / "api-key"


def env_region():
    return os.environ.get("SEEDANCE_REGION", "cn")


def selected_region(args):
    region = args.region or env_region()
    if region not in API_ROOTS:
        raise VideoError("Set SEEDANCE_REGION to cn or global.")
    return region


def validate_key(key):
    key = key.strip()
    if not key or not all(33 <= ord(c) <= 126 for c in key):
        raise VideoError("Enter an official Ark API key as a single line.")
    return key


def local_key(region):
    path = key_path(region)
    if path.is_symlink():
        raise VideoError("Use a private regular file for the Seedance API key.")
    if not path.exists():
        return None
    if not path.is_file() or (os.name == "posix" and path.stat().st_mode & 0o077):
        raise VideoError("Set the Seedance API key file's permissions to 600.")
    return validate_key(path.read_text(encoding="utf-8"))


def api_key(region, required=True):
    value = os.environ.get("ARK_API_KEY") if env_region() == region else None
    key = validate_key(value) if value else local_key(region)
    if key is None and required:
        raise VideoError(f"Configure an Ark API key with --region {region} configure.")
    return key


def configure(args):
    region = selected_region(args)
    path = key_path(region)
    if local_key(region) and not args.replace_key:
        return {"region": region, "api_key_configured": True, "key_file": str(path)}
    if args.from_env:
        value = os.environ.get("ARK_API_KEY", "")
    elif args.gui:
        if sys.platform != "darwin":
            raise VideoError("Use hidden input in an interactive terminal on this platform.")
        script = '''
with timeout of 1800 seconds
    set dialogResult to display dialog "请输入所选站点的官方 Ark API Key。" default answer "" with hidden answer buttons {"取消", "保存"} default button "保存" cancel button "取消" with title "Seedance 官方视频"
    return text returned of dialogResult
end timeout
'''
        try:
            value = subprocess.run(["osascript", "-e", script], check=True, capture_output=True,
                                   text=True, timeout=1805).stdout
        except (subprocess.SubprocessError, OSError):
            raise VideoError("The hidden input dialog was cancelled or unavailable.") from None
    else:
        if not sys.stdin.isatty():
            raise VideoError("Use --gui on macOS or run configure in an interactive terminal.")
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            try:
                value = getpass.getpass(f"Ark {region} API key (hidden): ")
            except getpass.GetPassWarning:
                raise VideoError("Hidden terminal input is unavailable.") from None
    key = validate_key(value)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    write_private(path, (key + "\n").encode("utf-8"))
    return {"region": region, "api_key_configured": True, "key_file": str(path)}


def error_code(value, key=None):
    if not isinstance(value, dict):
        return None
    code = value.get("code")
    if isinstance(code, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,100}", code) and (not key or key not in code):
        return code
    return None


def error_detail(value, key):
    message = value.get("message") if isinstance(value, dict) else None
    return message.replace(key, "[redacted]")[:4000] if isinstance(message, str) else None


def ark_api(region, key, suffix="", body=None):
    headers = {"Authorization": f"Bearer {key}", "User-Agent": USER_AGENT, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    call = request.Request(API_ROOTS[region] + TASKS_PATH + suffix, data=body, headers=headers)
    try:
        with request.build_opener(NoRedirect()).open(call, timeout=45) as response:
            result = json.loads(response.read(8 * 1024 * 1024))
    except error.HTTPError as exc:
        with exc:
            try:
                details = json.loads(exc.read(16 * 1024))
            except NETWORK_ERRORS:
                details = None
        failure = details.get("error") if isinstance(details, dict) else None
        raise ArkError(exc.code, error_code(failure, key), error_detail(failure, key)) from None
    except NETWORK_ERRORS:
        raise VideoError("The Ark response was unavailable or invalid. Keep the job record.") from None
    if not isinstance(result, dict):
        raise VideoError("Ark returned an unexpected response.")
    return result


def task_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"cgt-[A-Za-z0-9_-]{1,124}", value):
        raise VideoError("An official Ark cgt- task ID is required.")
    return value


def fingerprint(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def summary(task, key=None):
    result = {"task_fingerprint": fingerprint(task_id(task.get("id"))), "status": task["status"]}
    for field in ("model", "created_at", "duration", "resolution", "ratio", "generate_audio", "output_format"):
        if task.get(field) is not None:
            result[field] = task[field]
    if code := error_code(task.get("error"), key):
        result["error_code"] = code
    return result


def list_tasks(region, key, limit):
    response = ark_api(region, key, "?" + parse.urlencode({"page_size": limit}))
    items = response.get("items")
    if items is None and "items" in response:
        return []
    if not isinstance(items, list):
        raise VideoError("Ark did not return a task list.")
    return items


def doctor(args):
    region = selected_region(args)
    key = api_key(region, required=args.check_api)
    result = {"region": region, "api_base": API_ROOTS[region], "api_key_configured": key is not None}
    if args.check_api:
        list_tasks(region, key, 1)
        result["task_list_verified"] = True
    return result


def tasks(args):
    region = selected_region(args)
    key = api_key(region)
    return {"region": region, "items": [summary(item, key) for item in list_tasks(region, key, args.limit)]}


def manifest_for(region, model, **fields):
    return {"version": 1, "provider": PROVIDER, "region": region, "model": model, "created_at": utc_now(), **fields}


def load_manifest(job, args):
    manifest = read_record(job / "manifest.json")
    if (manifest.get("provider") != PROVIDER or manifest.get("version") != 1
            or manifest.get("region") not in API_ROOTS):
        raise VideoError("Use an official Seedance job directory created by this client.")
    if args.region and args.region != manifest["region"]:
        raise VideoError("This job belongs to a different official region.")
    return manifest


def prepare(args):
    region = selected_region(args)
    body, model, mode, parameters = build_request(args, region)
    job = args.job
    job.mkdir(mode=0o700, parents=True)
    write_private(job / "request.json", body)
    manifest = manifest_for(region, model, mode=mode, parameters=parameters,
                            request_sha256=hashlib.sha256(body).hexdigest())
    write_record(job / "manifest.json", manifest)
    return {"job": str(job), "status": "prepared", "region": region, "model": model,
            "mode": mode, "parameters": parameters, "request_bytes": len(body)}


def submit(args):
    job = args.job
    manifest = load_manifest(job, args)
    submission = job / "submission.json"
    if submission.exists() or not manifest.get("request_sha256"):
        raise VideoError("This job is already sealed for submission. Use inspect, status or download.")
    body = (job / "request.json").read_bytes()
    checksum = hashlib.sha256(body).hexdigest()
    if len(body) > MAX_REQUEST_BYTES or checksum != manifest["request_sha256"]:
        raise VideoError("The prepared request changed. Prepare a fresh job for intentional edits.")
    region = manifest["region"]
    key = api_key(region)
    record = {"outcome": "unknown", "attempted_at": utc_now(), "request_sha256": checksum}
    try:
        write_record(submission, record, exclusive=True)
    except FileExistsError:
        raise VideoError("Another invocation sealed this job. Use inspect to check its state.") from None
    try:
        response = ark_api(region, key, body=body)
        identifier = task_id(response.get("id"))
    except ArkError as exc:
        if exc.status in (400, 401, 403, 404, 422, 429) and exc.code:
            record["outcome"] = "rejected"
        record.update(http_status=exc.status, error_code=exc.code, error_detail=exc.detail)
        write_record(submission, record)
        raise
    record.update(outcome="accepted", task_id=identifier)
    write_record(submission, record)
    return {"job": str(job), "status": "submitted", "task_fingerprint": fingerprint(identifier)}


def fetch_task(region, key, identifier):
    response = ark_api(region, key, "/" + task_id(identifier))
    if response.get("id") != identifier or response.get("status") not in STATUSES:
        raise VideoError("Ark returned an unexpected task ID or status.")
    return response


def save_result(job, task, key):
    # Preserve provider details and signed URLs only in the private job record.
    failure = task.get("error")
    result = dict(task)
    if isinstance(failure, dict):
        result["error"] = {"code": error_code(failure, key), "message": error_detail(failure, key)}
    write_record(job / "result.json", result)


def recover(args):
    region = selected_region(args)
    key = api_key(region)
    job = args.job
    if job.exists():
        raise VideoError("Recover into a new job directory.")
    task = fetch_task(region, key, args.task_id)
    job.mkdir(mode=0o700, parents=True)
    write_record(job / "submission.json", {"outcome": "accepted", "task_id": task["id"], "recovered_at": utc_now()})
    write_record(job / "manifest.json", manifest_for(region, task.get("model"), mode="recovered"))
    save_result(job, task, key)
    return {"job": str(job), "region": region, **summary(task, key)}


def fetch_status(job, manifest):
    submission = job / "submission.json"
    record = read_record(submission) if submission.exists() else {}
    if record.get("outcome") != "accepted":
        raise VideoError("No accepted task ID is saved. Use inspect, or recover a verified official task ID in a new directory.")
    region = manifest["region"]
    key = api_key(region)
    task = fetch_task(region, key, record.get("task_id"))
    save_result(job, task, key)
    return task, key


def status(args):
    task, key = fetch_status(args.job, load_manifest(args.job, args))
    return {"job": str(args.job), **summary(task, key)}


def inspect_job(args):
    job = args.job
    manifest = load_manifest(job, args)
    submission = job / "submission.json"
    result = {"job": str(job), "region": manifest["region"], "model": manifest["model"], "status": "prepared"}
    if manifest.get("parameters"):
        result["parameters"] = manifest["parameters"]
    if submission.exists():
        try:
            record = read_record(submission)
        except (VideoError, ValueError):
            record = {"outcome": "unknown"}
        result.update(status=record.get("outcome", "unknown"), http_status=record.get("http_status"),
                      error_code=record.get("error_code"))
        if record.get("task_id"):
            result["task_fingerprint"] = fingerprint(record["task_id"])
    if (job / "result.json").exists():
        result.update(summary(read_record(job / "result.json")))
    if (job / "download.json").exists():
        result["download"] = read_record(job / "download.json")
    return result


def open_media(url):
    transport = request.build_opener(NoRedirect())
    for _ in range(6):
        require_https(url)
        try:
            return transport.open(request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=60)
        except error.HTTPError as exc:
            with exc:
                location = exc.headers.get("Location")
                if exc.code not in (301, 302, 303, 307, 308) or not location:
                    raise VideoError(f"Media HTTP {exc.code}. Retry download to fetch the current Ark result.") from None
        url = parse.urljoin(url, location)
    raise VideoError("Too many redirects while downloading the media.")


def verify_media(path, filename):
    size = path.stat().st_size
    with path.open("rb") as stream:
        if filename == "last-frame.jpg":
            if size >= 4 and stream.read(2) == b"\xff\xd8":
                stream.seek(-2, os.SEEK_END)
                if stream.read() == b"\xff\xd9":
                    return
        else:
            # Check top-level ISO BMFF boxes and their bounds, including extended lengths.
            boxes = set()
            offset = 0
            while offset + 8 <= size:
                stream.seek(offset)
                header = stream.read(8)
                length = int.from_bytes(header[:4], "big")
                header_size = 8
                if length == 1:
                    length = int.from_bytes(stream.read(8), "big")
                    header_size = 16
                elif length == 0:
                    length = size - offset
                if length < header_size or offset + length > size:
                    break
                if length > header_size:
                    boxes.add(header[4:])
                offset += length
            if offset == size and {b"moov", b"mdat"} <= boxes:
                return
    raise VideoError(f"The downloaded {filename} is incomplete or has an unexpected format.")


def sha256_file(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def save_media(job, filename, url, previous_sha=None):
    destination = job / filename
    if destination.is_symlink():
        raise VideoError(f"Use a regular file for {filename}.")
    if destination.exists():
        if not destination.is_file():
            raise VideoError(f"Use a regular file for {filename}.")
        verify_media(destination, filename)
        checksum = sha256_file(destination)
    else:
        if not url:
            raise VideoError(f"Ark did not return a download URL for {filename}.")
        fd, name = tempfile.mkstemp(dir=job, prefix=".media-")
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as output:
                with open_media(url) as response:
                    length = response.headers.get("Content-Length")
                    if response.status != 200:
                        raise VideoError("Ark media did not return a complete response.")
                    shutil.copyfileobj(response, output, length=1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
                if length is not None and output.tell() != int(length):
                    raise VideoError("The media transfer was incomplete. Retry download.")
            verify_media(temporary, filename)
            checksum = sha256_file(temporary)
            if previous_sha and checksum != previous_sha:
                raise VideoError(f"The downloaded {filename} differs from its recorded checksum.")
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if destination.is_symlink() or not destination.is_file() or sha256_file(destination) != checksum:
                    raise VideoError(f"A different {filename} already exists in this job.") from None
        finally:
            temporary.unlink(missing_ok=True)
    if previous_sha and checksum != previous_sha:
        raise VideoError(f"The saved {filename} differs from its recorded checksum.")
    return checksum


def download(args):
    job = args.job
    manifest = load_manifest(job, args)
    receipt_path = job / "download.json"
    receipt = read_record(receipt_path) if receipt_path.exists() else {}
    files = receipt.get("files", {})
    if files and set(files) <= {"video.mp4", "video.mov", "last-frame.jpg"} and all((job / name).exists() for name in files):
        for name, checksum in files.items():
            save_media(job, name, None, checksum)
    else:
        task, key = fetch_status(job, manifest)
        if task["status"] != "succeeded":
            code = error_code(task.get("error"), key)
            detail = f" ({code})" if code else ""
            raise VideoError(f"Ark task is {task['status']}{detail}.")
        parameters = manifest.get("parameters", {})
        output_format = task.get("output_format") or parameters.get("output_format", "mp4")
        if output_format not in ("mp4", "mov"):
            raise VideoError("Ark returned an unexpected video output format.")
        content = task.get("content") or {}
        filename = "video." + output_format
        outputs = {filename: content.get("video_url")}
        if content.get("last_frame_url") or parameters.get("return_last_frame"):
            outputs["last-frame.jpg"] = content.get("last_frame_url")
        files = {name: save_media(job, name, url, files.get(name)) for name, url in outputs.items()}
        receipt = {"files": files, "task": summary(task, key)}
        write_record(receipt_path, receipt)
    return {"job": str(job), **receipt["task"],
            "artifacts": [{"path": str(job / name), "sha256": checksum} for name, checksum in files.items()]}


def parser():
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--region", choices=API_ROOTS, help="Official region. New jobs default to cn.")
    commands = command.add_subparsers(dest="command", required=True)
    config = commands.add_parser("configure", help="Save a private key using hidden input.")
    source = config.add_mutually_exclusive_group()
    source.add_argument("--gui", action="store_true", help="Use the macOS hidden-input dialog.")
    source.add_argument("--from-env", action="store_true", help="Use the current ARK_API_KEY.")
    config.add_argument("--replace-key", action="store_true")
    commands.add_parser("doctor", help="Check local configuration or the read-only Ark task list.").add_argument(
        "--check-api", action="store_true"
    )
    commands.add_parser("tasks", help="List recent Ark tasks by fingerprint.").add_argument(
        "--limit", type=int, choices=range(1, 51), default=10, metavar="1..50"
    )
    new = commands.add_parser("prepare", help="Freeze a request locally.")
    new.add_argument("--prompt-file", type=Path)
    new.add_argument("--model", help="2.5 (default), 2.0, 2.0-fast, 2.0-mini, or the official model ID.")
    new.add_argument("--endpoint-id", help="Use an Ark ep- ID backed by the explicit --model.")
    new.add_argument("--first-frame")
    new.add_argument("--last-frame")
    for kind in ("image", "video", "audio"):
        new.add_argument(f"--ref-{kind}", action="append", default=[])
    new.add_argument("--omni-type", choices=("auto", "reference", "edit", "extend"))
    new.add_argument("--duration", type=int, help="Output seconds (default 4), or -1 for automatic duration.")
    new.add_argument("--resolution", type=str.lower, choices=("480p", "720p", "1080p", "4k"), default="480p")
    new.add_argument("--ratio", choices=RATIOS)
    new.add_argument("--no-audio", action="store_true")
    new.add_argument("--watermark", action="store_true")
    new.add_argument("--return-last-frame", action="store_true")
    new.add_argument("--output-format", choices=("mp4", "mov"), default="mp4")
    imported = commands.add_parser("recover", help="Adopt a verified official task ID without generating a new video.")
    imported.add_argument("--task-id", required=True)
    for name, handler, help_text in (
        ("submit", submit, "Submit one prepared job to Ark."),
        ("inspect", inspect_job, "Inspect the local job without calling Ark."),
        ("status", status, "Query the saved task on its original Ark region."),
        ("download", download, "Download or verify the completed media."),
    ):
        commands.add_parser(name, help=help_text).set_defaults(handler=handler)
    for name, handler in (("configure", configure), ("doctor", doctor), ("tasks", tasks),
                          ("prepare", prepare), ("recover", recover)):
        commands.choices[name].set_defaults(handler=handler)
    for name in ("prepare", "submit", "inspect", "status", "recover", "download"):
        commands.choices[name].add_argument("--job", type=Path, required=True)
    return command


def main():
    args = parser().parse_args()
    os.umask(0o077)
    try:
        if getattr(args, "job", None) is not None:
            args.job = args.job.expanduser().resolve()
        print(json.dumps(args.handler(args), ensure_ascii=False))
    except VideoError as exc:
        print(exc, file=sys.stderr)
        return 1
    except FileExistsError:
        print("Use a new job directory for prepare or recover.", file=sys.stderr)
        return 1
    except (OSError, HTTPException, ValueError, EOFError, KeyboardInterrupt):
        print("The operation could not complete. Check the input, local records or connection.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
