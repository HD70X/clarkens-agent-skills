"""Inspect immutable local inputs against the published H3 media limits."""
from __future__ import annotations

from pathlib import Path

from minimax_config import VideoError

MIME = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".heic": "image/heic", ".heif": "image/heif",
    ".mp4": "video/mp4", ".mov": "video/quicktime",
    ".wav": "audio/wav", ".mp3": "audio/mp3",
}
MAX_BYTES = {"image": 30_000_000, "video": 50_000_000, "audio": 15_000_000}


def dimensions(width, height):
    if not 256 <= width <= 5760 or not 256 <= height <= 5760 or not 0.4 <= width / height <= 2.5:
        raise VideoError("Local image/video dimensions must be 256–5760 px and width/height must be 0.4–2.5")


def inspect_local(path, media_type):
    path = Path(path)
    mime = MIME.get(path.suffix.lower(), "")
    if not path.is_file() or not mime.startswith(media_type + "/"):
        raise VideoError("Use a supported existing image (PNG/JPEG/WebP/HEIC/HEIF), video (MP4/MOV), or audio (WAV/MP3)")
    size = path.stat().st_size
    if not 0 < size <= MAX_BYTES[media_type]:
        raise VideoError(f"Local {media_type} is empty or exceeds the official per-file size limit")
    info = {"mime": mime, "bytes": size}
    try:
        if media_type == "image":
            from PIL import Image
            if path.suffix.lower() in (".heic", ".heif"):
                import pillow_heif
                pillow_heif.register_heif_opener()
            with Image.open(path) as image:
                width, height = image.size
                dimensions(width, height)
                format_mimes = {"PNG": ("image/png",), "JPEG": ("image/jpeg",),
                                "WEBP": ("image/webp",), "HEIF": ("image/heic", "image/heif"),
                                "HEIC": ("image/heic", "image/heif")}
                if image.format not in format_mimes:
                    raise VideoError("The local image does not decode as an official supported image format")
                if mime not in format_mimes[image.format]:
                    raise VideoError("Image content does not match its file extension; save a correctly named copy before preparing")
                image.verify()
            info.update(width=width, height=height)
        else:
            import av
            with av.open(str(path)) as container:
                streams = container.streams.video if media_type == "video" else container.streams.audio
                if not streams:
                    raise VideoError(f"Local {media_type} has no {media_type} stream")
                stream = streams[0]
                duration = float(stream.duration * stream.time_base) if stream.duration is not None and stream.time_base else None
                if duration is None and container.duration is not None:
                    duration = container.duration / av.time_base
                if duration is None or not 2 <= duration <= 15:
                    raise VideoError("Each reference video/audio must have a measurable duration of 2–15 seconds")
                info.update(duration=duration, codec=stream.codec_context.name)
                if media_type == "video":
                    width, height = stream.codec_context.width, stream.codec_context.height
                    dimensions(width, height)
                    if stream.codec_context.name not in ("h264", "hevc"):
                        raise VideoError("Reference video must use H.264/AVC or H.265/HEVC")
                    rate = float(stream.average_rate) if stream.average_rate else None
                    if rate is None or not 23.976 <= rate <= 60:
                        raise VideoError("Reference video frame rate must be 23.976–60 fps")
                    if any(s.codec_context.name not in ("aac", "mp3", "mp3float") for s in container.streams.audio):
                        raise VideoError("Audio embedded in a reference video must use AAC or MP3")
                    info.update(width=width, height=height, fps=rate)
    except ImportError:
        raise VideoError("Local media inspection needs scripts/requirements.txt in the MiniMax tooling venv") from None
    except VideoError:
        raise
    except Exception:
        raise VideoError(f"Cannot decode the local {media_type}; preserve the original and check its format") from None
    return info
