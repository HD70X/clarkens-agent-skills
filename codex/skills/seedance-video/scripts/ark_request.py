"""Validate and encode a request for the official Seedance 2.x models."""
from __future__ import annotations

import base64
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


class VideoError(Exception):
    pass


API_ROOTS = {
    "cn": "https://ark.cn-beijing.volces.com/api/v3",
    "global": "https://ark.ap-southeast.bytepluses.com/api/v3",
}
MODEL_PREFIXES = {"cn": "doubao-seedance-", "global": "dreamina-seedance-"}
# Model suffix, maximum duration, resolutions, and reference counts by media type.
MODELS = {
    "2.5": ("2-5-260628", 30, ("480p", "720p", "1080p"), (30, 10, 10)),
    "2.0": ("2-0-260128", 15, ("480p", "720p", "1080p", "4k"), (9, 3, 3)),
    "2.0-fast": ("2-0-fast-260128", 15, ("480p", "720p"), (9, 3, 3)),
    "2.0-mini": ("2-0-mini-260615", 15, ("480p", "720p"), (9, 3, 3)),
}
RATIOS = ("adaptive", "21:9", "16:9", "4:3", "1:1", "3:4", "9:16")
MAX_REQUEST_BYTES = 64_000_000
LOCAL_MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
    ".bmp": "image/bmp", ".tif": "image/tiff", ".tiff": "image/tiff", ".gif": "image/gif",
    ".heic": "image/heic", ".heif": "image/heif", ".wav": "audio/wav", ".mp3": "audio/mp3",
}


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def require_https(url):
    try:
        if not isinstance(url, str) or any(ord(c) < 33 or c.isspace() for c in url):
            raise ValueError()
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or "#" in url or parsed.port not in (None, 443)):
            raise ValueError()
    except ValueError:
        raise VideoError("Use an HTTPS URL without embedded credentials, whitespace, or a fragment.") from None


def model_selection(region, requested, endpoint):
    model_ids = {name: MODEL_PREFIXES[region] + spec[0] for name, spec in MODELS.items()}
    if requested is None and endpoint:
        raise VideoError("With --endpoint-id, specify its Seedance model using --model.")
    requested = requested or "2.5"
    for family, model_id in model_ids.items():
        if requested in (family, model_id):
            if endpoint and not re.fullmatch(r"ep-[A-Za-z0-9_-]+", endpoint):
                raise VideoError("Use an official Ark ep- endpoint ID.")
            return family, endpoint or model_id
    raise VideoError("Select a Seedance 2.x model for the chosen region. See references/api.md.")


def generation_parameters(args, family, has_frames, has_refs):
    _, maximum, resolutions, counts = MODELS[family]
    if args.last_frame and not args.first_frame:
        raise VideoError("A last frame requires a first frame.")
    if has_frames and has_refs:
        raise VideoError("Use either keyframes or multimodal references in one request.")
    if any(len(values) > limit for values, limit in zip(
        (args.ref_image, args.ref_video, args.ref_audio), counts
    )):
        raise VideoError(f"This model accepts at most {counts[0]} images, {counts[1]} videos and {counts[2]} audio clips.")
    if family != "2.5" and args.ref_audio and not (args.ref_image or args.ref_video):
        raise VideoError("Seedance 2.0 requires an image or a video alongside audio references.")
    task_type = args.omni_type
    if task_type and (family != "2.5" or not has_refs):
        raise VideoError("--omni-type applies to Seedance 2.5 multimodal references.")
    if task_type in ("edit", "extend") and not args.ref_video:
        raise VideoError("Video editing and extension require a video reference.")
    requires_adaptive = family == "2.5" and (has_frames or task_type in ("edit", "extend"))
    ratio = args.ratio or ("adaptive" if has_frames or has_refs else "16:9")
    if requires_adaptive and ratio != "adaptive":
        raise VideoError("Seedance 2.5 keyframes, editing and extension use --ratio adaptive.")
    duration = args.duration if args.duration is not None else (-1 if task_type == "edit" else 4)
    if task_type == "edit" and duration != -1:
        raise VideoError("Seedance 2.5 editing uses --duration -1 to follow the source video.")
    if duration != -1 and not 4 <= duration <= maximum:
        raise VideoError(f"Use an output duration of 4–{maximum} seconds or -1.")
    if args.resolution not in resolutions:
        raise VideoError(f"This model supports {', '.join(resolutions)}.")
    if family != "2.5" and args.output_format == "mov":
        raise VideoError("MOV output is available with Seedance 2.5.")
    parameters = {
        "duration": duration, "ratio": ratio, "resolution": args.resolution,
        "generate_audio": not args.no_audio, "watermark": args.watermark,
        "return_last_frame": args.return_last_frame,
    }
    if task_type:
        parameters["omni_reference_task_type"] = task_type
    if family == "2.5":
        parameters["output_format"] = args.output_format
    return parameters


def media_source(value, media_type):
    if value.startswith("https://"):
        require_https(value)
        return value, None, 0
    if re.fullmatch(r"asset://[A-Za-z0-9_-]+", value):
        return value, None, 0
    if media_type == "video":
        raise VideoError("Ark video references require an accessible HTTPS URL or an asset:// ID.")
    path = Path(value).expanduser()
    mime = LOCAL_MIME.get(path.suffix.lower(), "")
    if not mime.startswith(media_type + "/") or not path.is_file():
        raise VideoError(f"Provide a supported local {media_type}, HTTPS URL or asset:// ID.")
    size = path.stat().st_size
    limit = 29_999_999 if media_type == "image" else 15_000_000
    if not 0 < size <= limit:
        raise VideoError(f"Local {media_type} is empty or exceeds Ark's per-file limit. Use an HTTPS URL or asset:// ID.")
    return f"data:{mime};base64,", path, size


def build_request(args, region):
    family, model = model_selection(region, args.model, args.endpoint_id)
    has_frames = bool(args.first_frame or args.last_frame)
    has_refs = bool(args.ref_image or args.ref_video or args.ref_audio)
    parameters = generation_parameters(args, family, has_frames, has_refs)
    prompt = args.prompt_file.expanduser().read_text(encoding="utf-8-sig").strip() if args.prompt_file else ""
    content = [{"type": "text", "text": prompt}] if prompt else []
    sources = [(args.first_frame, "image", "first_frame"), (args.last_frame, "image", "last_frame")]
    for media_type, values in (("image", args.ref_image), ("video", args.ref_video), ("audio", args.ref_audio)):
        sources.extend((value, media_type, f"reference_{media_type}") for value in values)
    inline = []
    for value, media_type, role in sources:
        if value:
            url, path, size = media_source(value, media_type)
            field = media_type + "_url"
            part = {"url": url}
            content.append({"type": field, field: part, "role": role})
            if path is not None:
                inline.append((part, path, size))
    if not content:
        raise VideoError("Provide a nonempty UTF-8 prompt file or at least one supported reference.")
    payload = {"model": model, "content": content, **parameters}
    encoded_size = len(json_bytes(payload)) + sum(4 * ((size + 2) // 3) for _, _, size in inline)
    if encoded_size > MAX_REQUEST_BYTES:
        raise VideoError("The request would exceed 64 MB. Use HTTPS URLs or asset:// IDs for larger inputs.")
    for part, path, size in inline:
        with path.open("rb") as stream:
            data = stream.read(size + 1)
        if len(data) != size:
            raise VideoError("A local reference changed during preparation. Prepare a new snapshot.")
        part["url"] += base64.b64encode(data).decode("ascii")
    mode = "keyframes" if has_frames else "references" if has_refs else "text"
    return json_bytes(payload), model, mode, parameters
