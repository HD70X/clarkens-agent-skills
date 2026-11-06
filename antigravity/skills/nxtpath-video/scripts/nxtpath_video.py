#!/usr/bin/env python3
"""Resumable Nxtpath Seedance jobs; only submit creates a paid video task."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import ssl
import sys
from urllib import error, parse, request
import uuid

# Keep optional helper imports on the same exception/redaction state in CLI mode.
if __name__ == "__main__":
    sys.modules.setdefault("nxtpath_video", sys.modules[__name__])

BASE = "https://api.nxtpath.ai/v1"
MODELS = {"seedance-2.5", "doubao/seedance-2.5", "seedance/seedance-2.5"}
MEDIA_HOSTS = {"ark-acg-cn-beijing.tos-cn-beijing.volces.com"}
SECRETS: set[str] = set()


class VideoError(Exception):
    pass


class APIError(VideoError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else hashlib.sha256(stream.read()).hexdigest()


def redact(text):
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, "[redacted]")
    return text


def safe_error(value):
    text = redact(str(value))
    text = re.sub(r"https?://[^\s\"'<>]+|data:[^\s\"'<>]+", "[URL redacted]", text)
    return text[:800]


def emit(value):
    print(redact(json.dumps(value, ensure_ascii=False)))


def write_json(path, value, exclusive=False):
    path = Path(path)
    data = (redact(json.dumps(value, ensure_ascii=False, indent=2)) + "\n").encode()
    target = path if exclusive else path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if not exclusive:
        os.replace(target, path)


def read_json(path):
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise VideoError("Expected a JSON object in the local job record")
    return value


def load_config(env_file=None):
    path = Path(env_file or os.environ.get("NXTPATH_ENV_FILE") or Path.home() / ".config/nxtpath/env").expanduser()
    values = {}
    if path.exists():
        if path.stat().st_mode & 0o077:
            raise VideoError("Nxtpath env file must be private: chmod 600 on the configured file")
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            match = re.fullmatch(r"\s*(?:export\s+)?(NXTPATH_[A-Z0-9_]+)\s*=(.*)", line)
            if not match:
                raise VideoError(f"Unsupported env assignment on line {number}")
            parts = shlex.split(match[2], comments=True, posix=True)
            if len(parts) > 1:
                raise VideoError(f"Quote the env value on line {number}")
            values[match[1]] = parts[0] if parts else ""
    for name, value in os.environ.items():
        if name.startswith("NXTPATH_") and value:
            values[name] = value
    SECRETS.update(values.get(name, "") for name in ("NXTPATH_API_KEY", "NXTPATH_R2_SECRET_ACCESS_KEY"))
    return values, path


def api_key(config):
    key = config.get("NXTPATH_API_KEY", "").strip()
    if not key or any(character.isspace() for character in key):
        raise VideoError("Set NXTPATH_API_KEY in the environment or ~/.config/nxtpath/env")
    return key


def https_url(url):
    try:
        parsed = parse.urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.port not in (None, 443):
            raise ValueError()
        if any(c.isspace() for c in url):
            raise ValueError()
    except (ValueError, TypeError):
        raise VideoError("Reference and artifact URLs must be HTTPS without embedded credentials or fragments") from None
    return parsed


def api(key, suffix, payload=None, idempotency=None):
    headers = {"Authorization": "Bearer " + key, "Accept": "application/json", "User-Agent": "personal-nxtpath-video/1"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if idempotency:
        headers["Idempotency-Key"] = idempotency
    req = request.Request(BASE + suffix, data=json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None,
                          headers=headers, method="POST" if payload is not None else "GET")
    opener = request.build_opener(NoRedirect(), request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(req, timeout=45) as response:
            data = json.loads(response.read(8 * 1024 * 1024))
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except error.HTTPError as exc:
        message = safe_error(exc.read(8192).decode(errors="replace"))
        raise APIError(exc.code, f"Nxtpath HTTP {exc.code}: {message}") from None
    except (error.URLError, TimeoutError, OSError, ValueError):
        raise VideoError("Gateway response unavailable; preserve this attempt and never repeat a paid POST") from None


def job_path(value):
    return Path(value).expanduser().resolve()


def load_manifest(job):
    job = Path(job).resolve()
    manifest = job / "manifest.json"
    if digest(manifest) != (job / "manifest.sha256").read_text().strip():
        raise VideoError("Prepared manifest changed; preserve the attempt and prepare a new one for intentional edits")
    result = read_json(manifest)
    for ref in result["references"]:
        if ref["kind"] == "local":
            path = (job / ref["snapshot"]).resolve()
            if job not in path.parents or digest(path) != ref["sha256"]:
                raise VideoError("Reference snapshot changed or escaped the job directory")
    return result


def prepare(args, config):
    model = args.model or config.get("NXTPATH_SEEDANCE_MODEL") or "seedance-2.5"
    if model not in MODELS:
        raise VideoError("This skill supports Seedance 2.5; choose its explicit model ID without automatic fallback")
    prompt = args.prompt_file.expanduser().read_text().strip()
    if not prompt or not 4 <= args.duration <= 30:
        raise VideoError("Provide a nonempty prompt and a Seedance 2.5 duration of 4–30 seconds")
    if args.resolution not in ("480p", "720p", "1080p"):
        raise VideoError("Unsupported resolution")
    refs = []
    for index, value in enumerate(args.reference):
        if re.match(r"https?://", value):
            https_url(value)
            refs.append({"kind": "url", "url": value})
        else:
            source = Path(value).expanduser().resolve()
            if not source.is_file() or source.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp") or not 0 < source.stat().st_size <= 7 * 1024 * 1024:
                raise VideoError("Local references must be existing PNG/JPEG/WebP files up to 7 MiB")
            refs.append({"kind": "local", "source": source, "snapshot": f"inputs/reference-{index + 1}{source.suffix.lower()}", "sha256": digest(source)})
    job = job_path(args.job)
    job.mkdir(mode=0o700, parents=True, exist_ok=False)
    (job / "inputs").mkdir(mode=0o700)
    for ref in refs:
        if ref["kind"] == "local":
            data = ref.pop("source").read_bytes()
            if hashlib.sha256(data).hexdigest() != ref["sha256"]:
                raise VideoError("Reference changed while preparing; no task submitted")
            target = job / ref["snapshot"]
            with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
                stream.write(data)
    manifest = {"schema_version": 1, "created_at": now(), "model": model, "prompt": prompt,
                "parameters": {"duration": args.duration, "resolution": args.resolution, "ratio": args.ratio}, "references": refs}
    write_json(job / "manifest.json", manifest, exclusive=True)
    with os.fdopen(os.open(job / "manifest.sha256", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        stream.write(digest(job / "manifest.json") + "\n")
    return {"job": str(job), "status": "prepared", "references": len(refs), "paid_task_created": False}


def host(args, config):
    from r2_references import publish
    job = job_path(args.job)
    manifest = load_manifest(job)
    if (job / "submission.json").exists():
        raise VideoError("A submission is already recorded; do not change its reference URLs")
    records = read_json(job / "hosting.json").get("references", {}) if (job / "hosting.json").exists() else {}
    count = 0
    for index, ref in enumerate(manifest["references"]):
        if ref["kind"] != "local":
            continue
        previous = records.get(str(index), {})
        if previous.get("sha256") == ref["sha256"] and previous.get("verified_anonymous_get") and datetime.fromisoformat(previous["expires_at"]).timestamp() > datetime.now(timezone.utc).timestamp() + 1800:
            continue
        records[str(index)] = publish(config, job / ref["snapshot"])
        write_json(job / "hosting.json", {"references": records})
        count += 1
    return {"job": str(job), "hosted_references_updated": count, "paid_video_task_created": False}


def build_payload(job):
    manifest = load_manifest(job)
    if manifest["model"] not in MODELS:
        raise VideoError("Unsupported recorded model")
    hosting = read_json(job / "hosting.json").get("references", {}) if (job / "hosting.json").exists() else {}
    content = [{"type": "text", "text": manifest["prompt"]}]
    for index, ref in enumerate(manifest["references"]):
        if ref["kind"] == "url":
            url = ref["url"]
        else:
            record = hosting.get(str(index), {})
            if record.get("sha256") != ref["sha256"] or not record.get("verified_anonymous_get"):
                raise VideoError("Local reference is not hosted and verified; run host before submit")
            if datetime.fromisoformat(record["expires_at"]).timestamp() < datetime.now(timezone.utc).timestamp() + 1800:
                raise VideoError("Hosted reference expires within 30 minutes; run host before submit")
            url = record["url"]
        https_url(url)
        content.append({"type": "image_url", "image_url": {"url": url}})
    return {"model": manifest["model"], "input": {"content": content}, "parameters": manifest["parameters"]}


def fingerprint(task):
    return hashlib.sha256(task.encode()).hexdigest()[:16]


def submit(args, config):
    key = api_key(config)
    job = job_path(args.job)
    if (job / "submission.json").exists():
        raise VideoError("Submission already recorded; use inspect/status/download, never resubmit this attempt")
    payload = build_payload(job)
    write_json(job / "request.json", payload)
    record = {"created_at": now(), "outcome": "unknown", "task_id": None, "base_url": BASE,
              "model": payload["model"], "idempotency_key": str(uuid.uuid4()), "request_sha256": digest(job / "request.json")}
    try:
        write_json(job / "submission.json", record, exclusive=True)
    except FileExistsError:
        raise VideoError("Another process reserved this submission; no duplicate POST sent") from None
    try:
        response = api(key, "/tasks/submit", payload, record["idempotency_key"])
        write_json(job / "submit-response.json", response)
        task = (response.get("output") or {}).get("task_id")
        if not isinstance(task, str) or not task:
            raise VideoError("No task ID returned; reconcile the unknown submission before any new paid task")
        record.update(outcome="accepted", task_id=task)
        write_json(job / "submission.json", record)
        return {"job": str(job), "status": "submitted", "task_fingerprint": fingerprint(task), "model": record["model"]}
    except (APIError, VideoError) as exc:
        if isinstance(exc, APIError) and 400 <= exc.code < 500:
            record["outcome"] = "rejected"
        record["error"] = safe_error(exc)
        write_json(job / "submission.json", record)
        raise


def existing(job):
    record = read_json(job / "submission.json")
    if record.get("base_url") != BASE or digest(job / "request.json") != record["request_sha256"]:
        raise VideoError("Submission provider or frozen request changed")
    if not record.get("task_id") and (job / "submit-response.json").exists():
        task = (read_json(job / "submit-response.json").get("output") or {}).get("task_id")
        if isinstance(task, str) and task:
            record.update(task_id=task, outcome="accepted", recovered_at=now())
            write_json(job / "submission.json", record)
    if not record.get("task_id"):
        raise VideoError("No retained task ID; reconcile with the provider using private submission records, never repeat the POST")
    return record


def fetch_status(job, config):
    record = existing(job)
    response = api(api_key(config), "/tasks/status?" + parse.urlencode({"task_id": record["task_id"]}))
    write_json(job / "result.json", response)
    return record, response


def status(args, config):
    job = job_path(args.job)
    record, response = fetch_status(job, config)
    output = response.get("output") or {}
    result = {"job": str(job), "task_fingerprint": fingerprint(record["task_id"]), "status": output.get("task_status")}
    if output.get("error") or response.get("error"):
        result["error"] = safe_error(json.dumps(output.get("error") or response["error"]))
    return result


def artifact_url(task, response):
    output = response.get("output") or {}
    if output.get("task_status") != "Success":
        raise VideoError("Task has not succeeded; query status later without submitting again")
    urls = output.get("urls") or []
    if not urls or not isinstance(urls[0], str):
        raise VideoError("Successful task has no download handle")
    parsed = https_url(urls[0])
    expected = "/v1/tasks/artifacts/" + parse.quote(task, safe="") + "/0"
    if parsed.netloc != "api.nxtpath.ai" or parsed.path != expected:
        raise VideoError("Unexpected artifact origin/path; no API credential sent")
    return urls[0]


def open_artifact(key, url, job):
    opener = request.build_opener(NoRedirect(), request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        return opener.open(request.Request(url, headers={"Authorization": "Bearer " + key}), timeout=45)
    except error.HTTPError as exc:
        if exc.code not in (301, 302, 303, 307, 308):
            raise VideoError(f"Artifact HTTP {exc.code}; retry download/status, never generation") from None
        location = exc.headers.get("Location", "")
        write_json(job / "artifact-redirect.json", {"observed_at": now(), "location": location})
        exc.close()
        parsed = https_url(location)
        if parsed.hostname not in MEDIA_HOSTS:
            raise VideoError("New media redirect host; inspect the private redirect record before allowing an anonymous download")
        return opener.open(request.Request(location), timeout=45)


def download(args, config):
    job = job_path(args.job)
    target = job / "video.mp4"
    if target.exists():
        metadata = read_json(job / "download.json")
        if digest(target) != metadata["sha256"]:
            raise VideoError("Downloaded video changed; preserve the local evidence")
        return {"video": str(target), "already_downloaded": True, "bytes": target.stat().st_size}
    record, response = fetch_status(job, config)
    url = artifact_url(record["task_id"], response)
    part = job / "video.mp4.part"
    try:
        with open_artifact(api_key(config), url, job) as stream, os.fdopen(os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb") as sink:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                sink.write(chunk)
            sink.flush()
            os.fsync(sink.fileno())
    except Exception as exc:
        raise VideoError("Download interrupted: " + safe_error(exc) + "; retry download only") from None
    with part.open("rb") as stream:
        if stream.read(12)[4:8] != b"ftyp":
            raise VideoError("Downloaded data is not MP4/MOV; retain the .part evidence")
    metadata = {"downloaded_at": now(), "file": target.name, "bytes": part.stat().st_size, "sha256": digest(part)}
    write_json(job / "download.json", metadata)
    os.replace(part, target)
    return {"video": str(target), "bytes": metadata["bytes"], "sha256": metadata["sha256"]}


def inspect_job(args, config):
    job = job_path(args.job)
    manifest = load_manifest(job)
    summary = {"job": str(job), "model": manifest["model"], "parameters": manifest["parameters"], "status": "prepared", "references": len(manifest["references"])}
    if (job / "submission.json").exists():
        record = read_json(job / "submission.json")
        summary["status"] = record["outcome"]
        if record.get("task_id"):
            summary["task_fingerprint"] = fingerprint(record["task_id"])
    if (job / "result.json").exists():
        summary["status"] = (read_json(job / "result.json").get("output") or {}).get("task_status")
    if (job / "video.mp4").exists():
        summary.update(status="downloaded", video=str(job / "video.mp4"))
    return summary


def doctor(args, config, path):
    result = {"env_file": str(path), "api_key_configured": bool(config.get("NXTPATH_API_KEY")), "default_model": config.get("NXTPATH_SEEDANCE_MODEL", "seedance-2.5"),
              "r2_configured": all(config.get("NXTPATH_R2_" + name) for name in ("ACCOUNT_ID", "BUCKET", "ACCESS_KEY_ID", "SECRET_ACCESS_KEY")),
              "r2_dependency_available": importlib.util.find_spec("boto3") is not None}
    if args.check_api:
        response = api(api_key(config), "/models")
        result.update(api_verified=True, seedance_models=[m["id"] for m in response.get("data", []) if isinstance(m, dict) and "seedance" in str(m.get("id", ""))])
    if args.check_hosting:
        from r2_references import probe
        result["r2_check"] = probe(config)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, help="Override ~/.config/nxtpath/env; no secrets on the command line")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("doctor", help="Check configuration; optional read-only network probes")
    check.add_argument("--check-api", action="store_true")
    check.add_argument("--check-hosting", action="store_true")
    prep = commands.add_parser("prepare", help="Freeze prompt and references offline")
    prep.add_argument("--job", required=True)
    prep.add_argument("--prompt-file", type=Path, required=True)
    prep.add_argument("--reference", action="append", default=[], help="Local image or HTTPS URL; repeat for ordinary guidance images")
    prep.add_argument("--model")
    prep.add_argument("--duration", type=int, default=4)
    prep.add_argument("--resolution", choices=("480p", "720p", "1080p"), default="480p")
    prep.add_argument("--ratio", choices=("21:9", "16:9", "4:3", "1:1", "3:4", "9:16"), default="1:1")
    for name in ("host", "submit", "status", "download", "inspect"):
        commands.add_parser(name).add_argument("--job", required=True)
    args = parser.parse_args(argv)
    try:
        config, path = load_config(args.env_file)
        handlers = {"prepare": prepare, "host": host, "submit": submit, "status": status, "download": download, "inspect": inspect_job}
        result = doctor(args, config, path) if args.command == "doctor" else handlers[args.command](args, config)
        emit(result)
        return 0
    except Exception as exc:
        message = safe_error(exc) if isinstance(exc, (VideoError, FileExistsError, FileNotFoundError)) else "Local operation failed (" + type(exc).__name__ + "); preserve this job and its records"
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
