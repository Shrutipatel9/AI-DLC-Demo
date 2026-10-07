"""Photo decoding and re-encoding on write (C8 ``put``; AC5.2.3, AC5.8.1).

- The file type is read from the file's own bytes, never from the browser's claim.
- Only JPEG, PNG and HEIC are accepted; HEIC is converted to JPEG.
- Every photo is decoded, turned upright (EXIF orientation), converted to RGB, downscaled
  to ``max_dimension`` and re-encoded. Re-encoding writes no EXIF, GPS, XMP or device
  metadata, so none of it is ever stored (US5.8).
- PNG stays PNG (lossless); everything else becomes JPEG.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Literal

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

from app.face.public import RgbImage

register_heif_opener()

SourceType = Literal["image/jpeg", "image/png", "image/heic"]
StoredType = Literal["image/jpeg", "image/png"]

#: Refuse to decode anything larger than this many pixels (decompression bombs).
MAX_PIXELS = 50_000_000
JPEG_QUALITY = 92

_HEIF_BRANDS = frozenset({b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"})


class UnsupportedImageTypeError(ValueError):
    """The bytes are not a JPEG, PNG or HEIC image."""


class UnreadableImageError(ValueError):
    """The bytes claim a supported type but cannot be decoded."""


@dataclass(frozen=True)
class PreparedImage:
    """A decoded, upright, metadata-free photo and its re-encoded bytes."""

    pixels: RgbImage
    encoded: bytes
    content_type: StoredType
    width: int
    height: int


def sniff_type(data: bytes) -> SourceType | None:
    """The image type from the file signature, or ``None`` when unsupported."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in _HEIF_BRANDS:
        return "image/heic"
    return None


def _flatten(image: Image.Image) -> Image.Image:
    """RGB with any transparency composited onto white."""
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def prepare_photo(data: bytes, *, max_dimension: int) -> PreparedImage:
    """Decode, normalise and re-encode an uploaded photo.

    Raises:
        UnsupportedImageTypeError: When the bytes are not JPEG, PNG or HEIC.
        UnreadableImageError: When the image cannot be decoded or is implausibly large.
    """
    source_type = sniff_type(data)
    if source_type is None:
        raise UnsupportedImageTypeError("not a JPEG, PNG or HEIC image")
    try:
        with Image.open(io.BytesIO(data)) as opened:
            width, height = opened.size
            if width * height > MAX_PIXELS:
                raise UnreadableImageError("image has too many pixels")
            opened.load()
            upright = ImageOps.exif_transpose(opened)
            image = _flatten(upright)
    except UnreadableImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError) as exc:
        raise UnreadableImageError("image could not be decoded") from exc
    except Image.DecompressionBombError as exc:  # pragma: no cover - caught by MAX_PIXELS
        raise UnreadableImageError("image has too many pixels") from exc

    if max(image.size) > max_dimension:
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

    stored_type: StoredType = "image/png" if source_type == "image/png" else "image/jpeg"
    buffer = io.BytesIO()
    if stored_type == "image/png":
        image.save(buffer, format="PNG")
    else:
        image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    pixels: RgbImage = np.asarray(image, dtype=np.uint8)
    return PreparedImage(
        pixels=pixels,
        encoded=buffer.getvalue(),
        content_type=stored_type,
        width=image.size[0],
        height=image.size[1],
    )


def decode_stored(data: bytes) -> RgbImage:
    """Decode a photo this module stored (already upright, RGB, metadata-free).

    Raises:
        UnreadableImageError: When the stored bytes cannot be decoded.
    """
    try:
        with Image.open(io.BytesIO(data)) as opened:
            return np.asarray(opened.convert("RGB"), dtype=np.uint8)
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError) as exc:
        raise UnreadableImageError("stored image could not be decoded") from exc
