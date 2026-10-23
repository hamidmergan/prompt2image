"""Checks an input image by extension, size and the actual leading bytes."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, Set, Tuple

from .errors import InputError

ALLOWED_EXTENSIONS: Dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

# Which leading bytes match which extension.
_SIGNATURES: Dict[str, Set[bytes]] = {
    ".png": {b"\x89PNG\r\n\x1a\n"},
    ".jpg": {b"\xff\xd8\xff"},
    ".jpeg": {b"\xff\xd8\xff"},
}


def extension(name: str) -> str:
    """The extension of a file name, InputError when it is not a PNG or JPG."""
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise InputError(f"Only PNG and JPG are allowed, but {name!r} is {ext or 'without extension'}.")
    return ext


def mime(ext: str) -> str:
    """The media type of an allowed extension."""
    return ALLOWED_EXTENSIONS.get(ext.lower(), "application/octet-stream")


def validate_content(content: bytes, ext: str) -> None:
    """Checks via the leading bytes whether the content matches the extension."""
    expected = _SIGNATURES.get(ext.lower())
    if expected is None:
        return
    if not any(content.startswith(signature) for signature in expected):
        raise InputError(f"The file does not look like a {ext.lstrip('.').upper()} image.")


def check(content: bytes, name: str, max_mb: float) -> Tuple[str, str]:
    """Extension and media type of an input image, after size and content have been checked."""
    ext = extension(name)
    if not content:
        raise InputError("The image is empty.")
    if len(content) > max_mb * 1024 * 1024:
        raise InputError(f"The image is larger than {max_mb:g} MB.")
    validate_content(content, ext)
    return ext, mime(ext)


def dimensions(content: bytes) -> Tuple[int, int]:
    """Width and height of an image, InputError when it cannot be read."""
    from PIL import Image

    try:
        with Image.open(io.BytesIO(content)) as image:
            return image.width, image.height
    except Exception as e:  # noqa: BLE001 - any unreadable picture is a bad input
        raise InputError("The image could not be read.") from e
