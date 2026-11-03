"""Image uploads to S3 (dish/location photos are public, profile photos are served via presigned URLs)."""

from __future__ import annotations

import base64
import binascii
import hashlib

from core import aws, config
from core.errors import BadRequest

DISHES_FOLDER = "assets/img/dishes"
LOCATIONS_FOLDER = "assets/img/locations"
PROFILE_FOLDER = "profile-img"

_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"BM", "image/bmp"),
)


def decode_base64_image(data: str) -> bytes:
    """Bytes of a base64 image; a ``data:image/...;base64,`` prefix is allowed."""
    if not isinstance(data, str) or not data.strip():
        raise BadRequest("Image data is empty.")
    if len(data) > 7_000_000:
        raise BadRequest("The image must be at most 5 MB.")
    payload = data.split(",", 1)[1] if "," in data else data
    try:
        image = base64.b64decode(payload, validate=True)
        if len(image) > 5_000_000:
            raise BadRequest("The image must be at most 5 MB.")
        return image
    except (binascii.Error, ValueError) as exc:
        raise BadRequest("Image must be a valid base64 string.") from exc


def content_type(image: bytes) -> str:
    for signature, mime in _SIGNATURES:
        if image.startswith(signature):
            return mime
    if image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        return "image/webp"
    raise BadRequest("Invalid image format. Supported formats: PNG, JPEG, GIF, BMP, WEBP.")


def upload(image: bytes, bucket: str, folder: str, file_name: str) -> str:
    key = f"{folder}/{file_name}" if folder else file_name
    aws.s3().put_object(Bucket=bucket, Key=key, Body=image, ContentType=content_type(image))
    return key


def public_url(bucket: str, key: str) -> str:
    return f"https://{bucket}.s3.{config.region()}.amazonaws.com/{key}"


def upload_public_image(image_base64: str, folder: str, file_name: str) -> str:
    """Upload a dish/location photo and return its public URL."""
    bucket = config.images_bucket()
    data = decode_base64_image(image_base64)
    # Content-addressed names keep old order snapshots and CDN caches stable.
    return public_url(bucket, upload(data, bucket, folder, f"{file_name}_{hashlib.sha256(data).hexdigest()[:16]}"))


def presigned_url(bucket: str, key: str, expires_in: int = 3600) -> str:
    return aws.s3().generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires_in)


def download(bucket: str, key: str) -> bytes | None:
    client = aws.s3()
    try:
        return client.get_object(Bucket=bucket, Key=key)["Body"].read()
    except client.exceptions.NoSuchKey:
        return None


def delete(bucket: str, key: str) -> None:
    aws.s3().delete_object(Bucket=bucket, Key=key)


def same_image(first: bytes, second: bytes) -> bool:
    return hashlib.sha256(first).digest() == hashlib.sha256(second).digest()
