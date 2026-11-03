"""Small in-memory upload used by browser tests, so they need no frontend file mount."""

from __future__ import annotations

from base64 import b64decode

PNG_UPLOAD = {
    "name": "aqa-upload.png",
    "mimeType": "image/png",
    "buffer": b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="),
}
