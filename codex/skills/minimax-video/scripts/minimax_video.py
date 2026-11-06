#!/usr/bin/env python3
"""Resumable official MiniMax H3 video jobs. Only submit creates a paid task."""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import sys
from urllib import error, parse, request
import uuid

from minimax_config import (DEFAULT_MODEL, OFFICIAL_HOSTS, R2_FIELDS, VideoError, api_host,
                            api_key, emit, load_config, redact, safe_error)

if __name__ == "__main__":
    sys.modules.setdefault("minimax_video", sys.modules[__name__])

PROVIDER = "minimax-official"
MODELS = {
    "MiniMax-H3": {"resolutions": ("768P", "2K"), "min_duration": 4},
    "MiniMax-H3-Highspeed": {"resolutions": ("480P", "768P"), "min_duration": 4},
    "MiniMax-H3-Lite": {"resolutions": ("480P", "768P"), "min_duration": 4},
    "MiniMax-H3-Max": {"resolutions": ("480P", "768P"), "min_duration": 5},
}
RATIOS = ("adaptive", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16")
STATUSES = {"queued", "running", "succeeded", "failed", "cancelled"}
MAX_REQUEST_BYTES = 64_000_000


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
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def json_bytes(value):
    return (redact(json.dumps(value, ensure_ascii=False, indent=2)) + "\n").encode("utf-8")


def write_json(path, value, exclusive=False):
    path = Path(path)
    target = path if exclusive else path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        if not exclusive:
            os.replace(target, path)
    finally:
        if not exclusive and target.exists():
            target.unlink()


def read_json(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VideoError("Expected a JSON object in the local record")
    return value


def https_url(url):
    try:
        parsed = parse.urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.fragment or parsed.port not in (None, 443) or any(c.isspace() for c in url)):
            raise ValueError()
    except (ValueError, TypeError):
        raise VideoError("Use an HTTPS URL without embedded credentials, whitespace, or a fragment") from None
    return parsed


def opener():
    return request.build_opener(NoRedirect(), request.HTTPSHandler(context=ssl.create_default_context()))


def api(base, key, suffix, payload=None):
    if base not in OFFICIAL_HOSTS or not suffix.startswith("/v2/") or "://" in suffix:
        raise VideoError("Refusing an API request outside the official MiniMax V2 service")
    headers = {"Authorization": "Bearer " + key, "Accept": "application/json", "User-Agent": "personal-minimax-video/1"}
    body = None
    if payload is not None:
        body = json_bytes(payload)
        if len(body) > MAX_REQUEST_BYTES:
            raise VideoError("Request exceeds 64 MB; prepare a new attempt with --delivery r2 or HTTPS/mm_file inputs")
        headers["Content-Type"] = "application/json"
    req = request.Request(base + suffix, data=body, headers=headers, method="POST" if body is not None else "GET")
    try:
        with opener().open(req, timeout=45) as response:
            data = json.loads(response.read(8 * 1024 * 1024))
        if not isinstance(data, dict):
            raise ValueError()
        if data.get("error") or data.get("type") == "error":
            raise VideoError("Official API returned an error object; preserve the private response and reconcile the task")
        return data
    except error.HTTPError as exc:
        message = safe_error(exc.read(8192).decode(errors="replace"))
        code = exc.code
        exc.close()
        raise APIError(code, f"MiniMax HTTP {code}: {message}") from None
    except (error.URLError, TimeoutError, OSError, ValueError):
        raise VideoError("Official API response unavailable; retain this job and never repeat an uncertain paid POST") from None


def job_path(value):
    return Path(value).expanduser().resolve()


def summarized_parameters(parameters):
    summary = dict(parameters)
    if "callback_url" in summary:
        summary.pop("callback_url")
        summary["callback_url_configured"] = True
    return summary


def local_snapshot(job, ref):
    job = Path(job).resolve()
    path = (job / ref["snapshot"]).resolve()
    if job not in path.parents or digest(path) != ref["sha256"]:
        raise VideoError("Reference snapshot changed or escaped its job directory")
    return path


def load_manifest(job):
    job = Path(job).resolve()
    if digest(job / "manifest.json") != (job / "manifest.sha256").read_text().strip():
        raise VideoError("Prepared manifest changed; retain this job and prepare a new attempt for intentional edits")
    result = read_json(job / "manifest.json")
    if result.get("provider") != PROVIDER or result.get("schema_version") != 1 or result.get("base_url") not in OFFICIAL_HOSTS:
        raise VideoError("This is not an official MiniMax V2 job; use the original client for gateway jobs")
    if result.get("model") not in MODELS:
        raise VideoError("Unsupported recorded official model")
    for ref in result["references"]:
        if ref["kind"] == "local":
            local_snapshot(job, ref)
    return result


def prepare(args, config):
    model = args.model or config.get("MINIMAX_VIDEO_MODEL") or DEFAULT_MODEL
    if model not in MODELS:
        raise VideoError("Choose a documented official MiniMax H3 model; no automatic model fallback")
    specification = MODELS[model]
    prompt = args.prompt_file.expanduser().read_text(encoding="utf-8").strip()
    if not prompt or len(prompt) > 7000:
        raise VideoError("Provide one nonempty UTF-8 prompt of at most 7000 characters")
    duration = args.duration if args.duration is not None else specification["min_duration"]
    resolution = args.resolution.upper()
    if not specification["min_duration"] <= duration <= 15 or resolution not in specification["resolutions"]:
        raise VideoError("Duration or resolution is unavailable for the chosen official model; consult references/api.md")
    if len(args.first_frame) > 1 or len(args.last_frame) > 1:
        raise VideoError("At most one first frame and one last frame are allowed")
    references = [(v, "first_frame", "image") for v in args.first_frame]
    references += [(v, "last_frame", "image") for v in args.last_frame]
    references += [(v, "reference_image", "image") for v in args.ref_image]
    references += [(v, "reference_video", "video") for v in args.ref_video]
    references += [(v, "reference_audio", "audio") for v in args.ref_audio]
    keyframes = bool(args.first_frame or args.last_frame)
    multimodal = bool(args.ref_image or args.ref_video or args.ref_audio)
    if keyframes and multimodal:
        raise VideoError("First/last frames and multimodal references are mutually exclusive in the official API")
    if len(args.ref_image) > 9 or len(args.ref_video) > 3 or len(args.ref_audio) > 3 or len(references) > 12:
        raise VideoError("Official reference limits: 9 images, 3 videos, 3 audios, and 12 files in total")
    mode = "i2va" if keyframes else "r2va" if multimodal else "t2va"
    ratio = args.ratio or ("adaptive" if keyframes or (multimodal and model != "MiniMax-H3-Lite") else "16:9")
    if mode == "t2va" and ratio == "adaptive":
        raise VideoError("Text-only generation requires a concrete aspect ratio")
    if keyframes and ratio != "adaptive":
        raise VideoError("Official keyframe generation uses adaptive ratio determined by input images; use --ratio adaptive")
    if mode == "r2va" and model == "MiniMax-H3-Lite" and ratio == "adaptive":
        raise VideoError("MiniMax-H3-Lite reference mode requires a concrete aspect ratio")
    parameters = {"duration": duration, "resolution": resolution, "ratio": ratio}
    if args.prompt_expansion_mode:
        if model != "MiniMax-H3-Max":
            raise VideoError("prompt_expansion_mode is documented only for MiniMax-H3-Max")
        parameters["extra"] = {"prompt_expansion_mode": args.prompt_expansion_mode}
    if args.aigc_watermark is not None:
        parameters["aigc_watermark"] = args.aigc_watermark
    if args.callback_url:
        https_url(args.callback_url)
        parameters["callback_url"] = args.callback_url
    refs, sources = [], {}
    from media_inputs import inspect_local
    for index, (value, role, media_type) in enumerate(references):
        ref = {"role": role, "media_type": media_type}
        if value.startswith("https://"):
            https_url(value)
            ref.update(kind="url", url=value)
        elif value.startswith("mm_file://"):
            if not re.fullmatch(r"mm_file://[A-Za-z0-9_-]+", value):
                raise VideoError("Invalid official mm_file:// identifier")
            ref.update(kind="mm_file", url=value)
        elif re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", value):
            raise VideoError("Use a local file, HTTPS URL, or mm_file:// identifier; local files support inline Base64 delivery")
        else:
            source = Path(value).expanduser().resolve()
            info = inspect_local(source, media_type)
            if args.delivery == "inline" and source.suffix.lower() == ".mov":
                raise VideoError("Local MOV requires --delivery r2; official inline video input uses MP4")
            ref.update(kind="local", snapshot=f"inputs/reference-{index + 1}{source.suffix.lower()}",
                       sha256=digest(source), metadata=info)
            sources[index] = source
        refs.append(ref)
    for media_type in ("video", "audio"):
        if sum(r.get("metadata", {}).get("duration", 0) for r in refs if r["media_type"] == media_type) > 15:
            raise VideoError("Combined local reference video/audio duration exceeds the official 15-second limit per media type")
    estimated = len(json_bytes({"prompt": prompt, "parameters": parameters, "references": [r for r in refs if r["kind"] != "local"]})) + 8192
    if args.delivery == "inline":
        estimated += sum(4 * ((r["metadata"]["bytes"] + 2) // 3) for r in refs if r["kind"] == "local")
    if estimated > MAX_REQUEST_BYTES:
        raise VideoError("Inline inputs would exceed 64 MB; use --delivery r2 or HTTPS/mm_file references")
    job = job_path(args.job)
    job.mkdir(mode=0o700, parents=True, exist_ok=False)
    (job / "inputs").mkdir(mode=0o700)
    for index, source in sources.items():
        target = job / refs[index]["snapshot"]
        with source.open("rb") as src, os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as dst:
            shutil.copyfileobj(src, dst)
        if digest(target) != refs[index]["sha256"]:
            raise VideoError("Reference changed while preparing; no task was submitted")
    manifest = {"schema_version": 1, "provider": PROVIDER, "protocol": "video-v2", "created_at": now(),
                "base_url": api_host(config), "model": model, "mode": mode, "prompt": prompt,
                "parameters": parameters, "delivery": args.delivery, "references": refs}
    write_json(job / "manifest.json", manifest, exclusive=True)
    with os.fdopen(os.open(job / "manifest.sha256", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        stream.write(digest(job / "manifest.json") + "\n")
    return {"job": str(job), "status": "prepared", "model": model, "mode": mode, "parameters": summarized_parameters(parameters),
            "references": len(refs), "delivery": args.delivery, "paid_task_created": False}


def host(args, config):
    from r2_references import publish
    job = job_path(args.job)
    manifest = load_manifest(job)
    if (job / "submission.json").exists():
        raise VideoError("Submission already recorded; do not change reference URLs")
    if manifest["delivery"] != "r2":
        raise VideoError("This attempt uses inline delivery; hosting is unnecessary")
    records = read_json(job / "hosting.json").get("references", {}) if (job / "hosting.json").exists() else {}
    count = 0
    for index, ref in enumerate(manifest["references"]):
        if ref["kind"] != "local":
            continue
        previous = records.get(str(index), {})
        if (previous.get("sha256") == ref["sha256"] and previous.get("verified_anonymous_get")
                and datetime.fromisoformat(previous["expires_at"]).timestamp() > datetime.now(timezone.utc).timestamp() + 1800):
            continue
        records[str(index)] = publish(config, local_snapshot(job, ref), ref["media_type"])
        write_json(job / "hosting.json", {"references": records})
        count += 1
    return {"job": str(job), "hosted_references_updated": count, "paid_task_created": False}


def build_payload(job):
    manifest = load_manifest(job)
    hosting = read_json(job / "hosting.json").get("references", {}) if (job / "hosting.json").exists() else {}
    content = [{"type": "text", "text": manifest["prompt"]}]
    for index, ref in enumerate(manifest["references"]):
        if ref["kind"] != "local":
            url = ref["url"]
        elif manifest["delivery"] == "inline":
            data = local_snapshot(job, ref).read_bytes()
            url = "data:" + ref["metadata"]["mime"] + ";base64," + base64.b64encode(data).decode("ascii")
        else:
            record = hosting.get(str(index), {})
            if record.get("sha256") != ref["sha256"] or not record.get("verified_anonymous_get"):
                raise VideoError("Local input must be hosted and verified before submit")
            if datetime.fromisoformat(record["expires_at"]).timestamp() < datetime.now(timezone.utc).timestamp() + 1800:
                raise VideoError("Hosted input expires within 30 minutes; refresh with host before submit")
            url = record["url"]
            https_url(url)
        part_type = ref["media_type"] + "_url"
        content.append({"type": part_type, part_type: {"url": url}, "role": ref["role"]})
    payload = {"model": manifest["model"], "content": content, **manifest["parameters"]}
    if len(json_bytes(payload)) > MAX_REQUEST_BYTES:
        raise VideoError("Request exceeds 64 MB; prepare a new attempt using --delivery r2")
    return payload


def fingerprint(task):
    return hashlib.sha256(task.encode()).hexdigest()[:16]


def submit(args, config):
    key = api_key(config)
    job = job_path(args.job)
    manifest = load_manifest(job)
    if api_host(config) != manifest["base_url"]:
        raise VideoError("Configured API host differs from this frozen job; select the original region")
    if (job / "submission.json").exists():
        raise VideoError("Submission already recorded; use inspect/status/download, never repeat the paid POST")
    payload = build_payload(job)
    record = {"created_at": now(), "provider": PROVIDER, "outcome": "unknown", "task_id": None,
              "base_url": manifest["base_url"], "model": payload["model"], "client_request_id": str(uuid.uuid4()),
              "request_sha256": hashlib.sha256(json_bytes(payload)).hexdigest()}
    try:
        write_json(job / "submission.json", record, exclusive=True)
    except FileExistsError:
        raise VideoError("Another process reserved this submission; no duplicate POST sent") from None
    try:
        write_json(job / "request.json", payload, exclusive=True)
        response = api(record["base_url"], key, "/v2/video_generation", payload)
        write_json(job / "submit-response.json", response)
        task = response.get("task_id")
        if not isinstance(task, str) or not task.strip():
            raise VideoError("No task ID returned; reconcile this unknown submission before any new paid task")
        record.update(outcome="accepted", task_id=task)
        write_json(job / "submission.json", record)
        return {"job": str(job), "status": "submitted", "task_fingerprint": fingerprint(task), "model": record["model"]}
    except (VideoError, OSError) as exc:
        if isinstance(exc, APIError) and 400 <= exc.code < 500 and exc.code not in (408, 409):
            record["outcome"] = "rejected"
        record["error"] = safe_error(exc)
        write_json(job / "submission.json", record)
        raise


def existing(job, config):
    manifest = load_manifest(job)
    record = read_json(job / "submission.json")
    if (record.get("provider") != PROVIDER or record.get("base_url") != manifest["base_url"]
            or record.get("base_url") != api_host(config) or digest(job / "request.json") != record["request_sha256"]):
        raise VideoError("Submission provider, API region, or frozen request changed")
    if not record.get("task_id") and (job / "submit-response.json").exists():
        task = read_json(job / "submit-response.json").get("task_id")
        if isinstance(task, str) and task.strip():
            record.update(task_id=task, outcome="accepted", recovered_at=now())
            write_json(job / "submission.json", record)
    if not record.get("task_id"):
        raise VideoError("No retained task ID; reconcile with the provider using private records and tasks, never repeat the POST")
    return record


def fetch_status(job, config):
    record = existing(job, config)
    response = api(record["base_url"], api_key(config), "/v2/query/video_generation/" + parse.quote(record["task_id"], safe=""))
    write_json(job / "result.json", response)
    task = response.get("task") or {}
    if task.get("id") != record["task_id"] or task.get("status") not in STATUSES or task.get("model") != record["model"]:
        raise VideoError("Unexpected task identity, model, or status; inspect private result.json without resubmitting")
    return record, response


def status(args, config):
    job = job_path(args.job)
    record, response = fetch_status(job, config)
    task = response["task"]
    result = {"job": str(job), "task_fingerprint": fingerprint(record["task_id"]), "status": task["status"]}
    for name in ("resolution", "duration", "ratio", "usage"):
        if name in task:
            result[name] = task[name]
    if task.get("error"):
        result["error"] = safe_error(json.dumps(task["error"], ensure_ascii=False))
    return result


def open_media(url, job):
    """All media requests, including every redirect, are anonymous HTTPS."""
    transport = opener()
    redirects = []
    for _ in range(6):
        https_url(url)
        try:
            return transport.open(request.Request(url, headers={"User-Agent": "personal-minimax-video/1"}), timeout=45)
        except error.HTTPError as exc:
            if exc.code not in (301, 302, 303, 307, 308) or not exc.headers.get("Location"):
                code = exc.code
                exc.close()
                raise VideoError(f"Media HTTP {code}; retry status/download to refresh the URL, never generation") from None
            location = parse.urljoin(url, exc.headers["Location"])
            exc.close()
            https_url(location)
            redirects.append({"observed_at": now(), "location": location})
            write_json(job / "download-redirects.json", {"redirects": redirects})
            url = location
    raise VideoError("Too many media redirects; retain this job and retry download only after inspection")


@contextmanager
def download_lock(job):
    """OS-held lock survives as a file, but releases automatically on process exit."""
    descriptor = os.open(job / "download.lock", os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "r+b") as lock:
        try:
            if os.name == "nt":
                import msvcrt
                if os.fstat(lock.fileno()).st_size == 0:
                    lock.write(b"\0")
                    lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise VideoError("A download for this job is already in progress; retry download after it finishes") from None
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def download(args, config):
    job = job_path(args.job)
    load_manifest(job)
    with download_lock(job):
        return download_locked(job, config)


def download_locked(job, config):
    target = job / "video.mp4"
    if target.exists():
        metadata = read_json(job / "download.json")
        if digest(target) != metadata["sha256"]:
            raise VideoError("Downloaded video changed; retain the local evidence")
        return {"video": str(target), "already_downloaded": True, "bytes": target.stat().st_size}
    _, response = fetch_status(job, config)
    task = response["task"]
    if task["status"] != "succeeded":
        raise VideoError("Task has not succeeded; query status later without submitting again")
    url = (task.get("content") or {}).get("url")
    if not isinstance(url, str):
        raise VideoError("Successful task has no download URL; retain its records")
    part = job / "video.mp4.part"
    try:
        with open_media(url, job) as stream, os.fdopen(os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb") as sink:
            expected = stream.headers.get("Content-Length")
            size = 0
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                sink.write(chunk)
                size += len(chunk)
            sink.flush()
            os.fsync(sink.fileno())
            if expected is not None and size != int(expected):
                raise VideoError("Downloaded size differs from Content-Length")
    except Exception as exc:
        raise VideoError("Download interrupted: " + safe_error(exc) + "; retry download only") from None
    with part.open("rb") as stream:
        if stream.read(12)[4:8] != b"ftyp":
            raise VideoError("Downloaded data is not MP4/MOV; retain .part evidence")
    metadata = {"downloaded_at": now(), "file": target.name, "bytes": part.stat().st_size, "sha256": digest(part)}
    write_json(job / "download.json", metadata)
    os.replace(part, target)
    return {"video": str(target), "bytes": metadata["bytes"], "sha256": metadata["sha256"]}


def inspect_job(args, config):
    job = job_path(args.job)
    manifest = load_manifest(job)
    summary = {"job": str(job), "provider": PROVIDER, "api_host": manifest["base_url"], "model": manifest["model"],
               "mode": manifest["mode"], "parameters": summarized_parameters(manifest["parameters"]), "delivery": manifest["delivery"],
               "status": "prepared", "references": len(manifest["references"])}
    if (job / "submission.json").exists():
        record = read_json(job / "submission.json")
        summary["status"] = record["outcome"]
        if record.get("task_id"):
            summary["task_fingerprint"] = fingerprint(record["task_id"])
    if (job / "result.json").exists():
        summary["status"] = (read_json(job / "result.json").get("task") or {}).get("status", summary["status"])
    if (job / "video.mp4").exists():
        metadata = read_json(job / "download.json")
        if digest(job / "video.mp4") != metadata["sha256"]:
            raise VideoError("Downloaded video changed")
        summary.update(status="downloaded", video=str(job / "video.mp4"))
    return summary


def tasks(args, config):
    query = {"page_num": args.page, "page_size": args.page_size}
    if args.status:
        query["filter.status"] = args.status
    if args.model:
        query["filter.model"] = args.model
    response = api(api_host(config), api_key(config), "/v2/query/video_generation?" + parse.urlencode(query))
    if not isinstance(response.get("items"), list) or not isinstance(response.get("total"), int):
        raise VideoError("Unexpected official task-list response")
    if args.output:
        write_json(args.output.expanduser(), response, exclusive=True)
    return {"page": args.page, "total": response["total"], "private_record": str(args.output) if args.output else None,
            "tasks": [{"task_fingerprint": fingerprint(str(t["id"])), "model": t.get("model"),
                       "status": t.get("status"), "created_at": t.get("created_at")} for t in response["items"]]}


def doctor(args, config, path):
    model = config.get("MINIMAX_VIDEO_MODEL") or DEFAULT_MODEL
    result = {"env_file": str(path), "api_host": api_host(config), "api_key_configured": bool(config.get("MINIMAX_API_KEY")),
              "default_model": model, "model_supported": model in MODELS,
              "r2_configured": all(config.get("MINIMAX_R2_" + field) for field in R2_FIELDS),
              "dependencies": {name: importlib.util.find_spec(name) is not None for name in ("PIL", "pillow_heif", "av", "boto3")},
              "generation_verified": False, "paid_task_created": False}
    if args.check_api:
        response = api(api_host(config), api_key(config), "/v2/query/video_generation?page_num=1&page_size=1")
        if not isinstance(response.get("items"), list) or not isinstance(response.get("total"), int):
            raise VideoError("Unexpected official task-list response; authentication is not verified")
        result.update(api_verified=True, verification="read-only V2 task list", generation_permission="not tested")
    if args.check_hosting:
        from r2_references import probe
        result["r2_check"] = probe(config)
    return result


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--env-file", type=Path, help="Private MiniMax env file; credentials never belong in arguments")
    commands = root.add_subparsers(dest="command", required=True)
    check = commands.add_parser("doctor", help="Check local configuration and optional read-only API/R2 access")
    check.add_argument("--check-api", action="store_true")
    check.add_argument("--check-hosting", action="store_true")
    prep = commands.add_parser("prepare", help="Freeze prompt, official parameters, and local media offline")
    prep.add_argument("--job", required=True)
    prep.add_argument("--prompt-file", type=Path, required=True)
    for flag in ("first-frame", "last-frame", "ref-image", "ref-video", "ref-audio"):
        prep.add_argument("--" + flag, action="append", default=[], help="Repeatable local path, HTTPS URL, or mm_file:// ID")
    prep.add_argument("--model", choices=tuple(MODELS))
    prep.add_argument("--duration", type=int, help="Default is the model minimum: 4 seconds, or 5 for H3-Max")
    prep.add_argument("--resolution", type=str.upper, choices=("480P", "768P", "2K"), default="768P")
    prep.add_argument("--ratio", choices=RATIOS, help="Default: 16:9 for text, adaptive for input-led modes (Lite reference: 16:9)")
    prep.add_argument("--delivery", choices=("inline", "r2"), default="inline")
    prep.add_argument("--prompt-expansion-mode", choices=("disabled", "balanced", "quality"), help="H3-Max only")
    prep.add_argument("--aigc-watermark", action=argparse.BooleanOptionalAction, default=None)
    prep.add_argument("--callback-url", help="Only use a callback endpoint explicitly provided by the user")
    for name in ("host", "submit", "status", "download", "inspect"):
        commands.add_parser(name).add_argument("--job", required=True)
    listing = commands.add_parser("tasks", help="Read recent tasks; output fingerprints unless a private output file is requested")
    listing.add_argument("--page", type=int, default=1)
    listing.add_argument("--page-size", type=int, default=20)
    listing.add_argument("--status", choices=tuple(sorted(STATUSES)))
    listing.add_argument("--model", choices=tuple(MODELS))
    listing.add_argument("--output", type=Path)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        config, path = load_config(args.env_file)
        handlers = {"prepare": prepare, "host": host, "submit": submit, "status": status, "download": download,
                    "inspect": inspect_job, "tasks": tasks}
        result = doctor(args, config, path) if args.command == "doctor" else handlers[args.command](args, config)
        emit(result)
        return 0
    except Exception as exc:
        message = safe_error(exc) if isinstance(exc, (VideoError, OSError, ValueError)) else "Local operation failed (" + type(exc).__name__ + "); retain this job and its records"
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
