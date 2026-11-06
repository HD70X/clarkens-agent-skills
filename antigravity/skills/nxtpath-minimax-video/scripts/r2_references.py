"""Optional private Cloudflare R2 hosting for local reference images."""
from datetime import datetime, timedelta, timezone
import hashlib
import re
import ssl
from urllib import parse, request

from nxtpath_minimax_video import MAX_IMAGE_BYTES, NoRedirect, VideoError


def connection(config):
    values = {name: config.get("NXTPATH_R2_" + name, "") for name in ("ACCOUNT_ID", "BUCKET", "ACCESS_KEY_ID", "SECRET_ACCESS_KEY")}
    if not re.fullmatch(r"[a-f0-9]{32}", values["ACCOUNT_ID"]) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", values["BUCKET"]):
        raise VideoError("Configure NXTPATH_R2_ACCOUNT_ID and NXTPATH_R2_BUCKET for local images; HTTPS references need no R2")
    if not values["ACCESS_KEY_ID"] or not values["SECRET_ACCESS_KEY"]:
        raise VideoError("Configure NXTPATH_R2_ACCESS_KEY_ID and NXTPATH_R2_SECRET_ACCESS_KEY")
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        raise VideoError("Local image hosting needs boto3; use ~/.config/nxtpath/venv/bin/python or install scripts/requirements.txt in a tooling venv") from None
    endpoint = f"https://{values['ACCOUNT_ID']}.r2.cloudflarestorage.com"
    client = boto3.client("s3", endpoint_url=endpoint, region_name="auto", aws_access_key_id=values["ACCESS_KEY_ID"],
                          aws_secret_access_key=values["SECRET_ACCESS_KEY"], config=Config(signature_version="s3v4", connect_timeout=15,
                          read_timeout=30, retries={"total_max_attempts": 1}, s3={"addressing_style": "path"}))
    return client, values["BUCKET"], endpoint


def probe(config):
    client, bucket, _ = connection(config)
    try:
        client.list_objects_v2(Bucket=bucket, MaxKeys=1)
        return {"verified": True, "operation": "read-only list"}
    except Exception as exc:
        details = getattr(exc, "response", {})
        return {"verified": False, "http_status": details.get("ResponseMetadata", {}).get("HTTPStatusCode"),
                "error_code": str(details.get("Error", {}).get("Code", type(exc).__name__))[:80]}


def publish(config, image):
    client, bucket, endpoint = connection(config)
    data = image.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(image.suffix.lower())
    if mime is None or not 0 < len(data) <= MAX_IMAGE_BYTES:
        raise VideoError("Reference must be PNG/JPEG/WebP up to 20 MiB")
    suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[mime]
    key = "nxtpath/references/" + sha + suffix
    uploaded = False
    try:
        try:
            head = client.head_object(Bucket=bucket, Key=key)
        except Exception as exc:
            code = getattr(exc, "response", {}).get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code != 404:
                raise VideoError(f"R2 object lookup failed (HTTP {code}); check credentials, no upload attempted") from None
            client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=mime, CacheControl="private, max-age=3600", Metadata={"sha256": sha})
            uploaded = True
            head = client.head_object(Bucket=bucket, Key=key)
        if head.get("ContentLength") != len(data) or head.get("Metadata", {}).get("sha256") != sha:
            raise VideoError("Existing R2 object differs from the immutable reference; no overwrite")
        url = client.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=86400, HttpMethod="GET")
        if parse.urlsplit(url).netloc != parse.urlsplit(endpoint).netloc:
            raise VideoError("Unexpected R2 signing endpoint")
        opener = request.build_opener(NoRedirect(), request.HTTPSHandler(context=ssl.create_default_context()))
        with opener.open(request.Request(url), timeout=30) as stream:
            verified = stream.read(MAX_IMAGE_BYTES + 1)
        if hashlib.sha256(verified).hexdigest() != sha:
            raise VideoError("Anonymous reference GET differs from its snapshot")
    except VideoError:
        raise
    except Exception:
        raise VideoError("R2 upload/sign/verification failed; check the local credentials, no video task submitted") from None
    current = datetime.now(timezone.utc)
    return {"provider": "cloudflare-r2", "created_at": current.isoformat(), "expires_at": (current + timedelta(days=1)).isoformat(),
            "object_key": key, "sha256": sha, "bytes": len(data), "new_object_uploaded": uploaded, "url": url, "verified_anonymous_get": True}
