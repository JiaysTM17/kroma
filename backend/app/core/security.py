from __future__ import annotations

import io
import os
import re
import stat
import struct
import unicodedata
import warnings
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from PIL import Image

from app.core.errors import (
    AppError,
    PayloadTooLargeError,
    SecurityError,
    UnsupportedMediaTypeError,
    ValidationAppError,
)
from app.domain.enums import ErrorCode, ImageMime

ALLOWED_MIME_TO_EXT: dict[str, str] = {
    ImageMime.JPEG.value: ".jpg",
    ImageMime.PNG.value: ".png",
    ImageMime.WEBP.value: ".webp",
}

EXT_TO_EXPECTED_MIME: dict[str, str] = {
    ".jpg": ImageMime.JPEG.value,
    ".jpeg": ImageMime.JPEG.value,
    ".jfif": ImageMime.JPEG.value,
    ".png": ImageMime.PNG.value,
    ".webp": ImageMime.WEBP.value,
}

RAW_EXTENSIONS: set[str] = {
    ".cr2",
    ".cr3",
    ".nef",
    ".nrw",
    ".arw",
    ".srf",
    ".sr2",
    ".dng",
    ".orf",
    ".raf",
    ".rw2",
    ".pef",
    ".raw",
    ".iiq",
    ".3fr",
    ".erf",
    ".kdc",
    ".dcr",
    ".mrw",
}

DEFERRED_EXTENSIONS: set[str] = {
    ".psd",
    ".psb",
    ".tif",
    ".tiff",
    ".heic",
    ".heif",
    ".avif",
}

WINDOWS_RESERVED_STEMS: set[str] = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

_DRIVE_PREFIX_RE = re.compile(r"^[A-Za-z]:")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class ValidatedImage:
    mime_type: ImageMime
    width: int
    height: int
    exif_orientation: int
    safe_filename: str


def detect_magic_mime(data: bytes) -> ImageMime | None:
    if data.startswith(b"\xff\xd8\xff"):
        return ImageMime.JPEG
    if data.startswith(_PNG_SIGNATURE):
        return ImageMime.PNG
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ImageMime.WEBP
    return None


def sanitize_upload_filename(raw_name: str) -> str:
    if not isinstance(raw_name, str):
        raise SecurityError(
            ErrorCode.PATH_TRAVERSAL_DETECTED,
            "Invalid filename",
            status_code=422,
        )
    if "\x00" in raw_name or _CONTROL_CHARS_RE.search(raw_name):
        raise SecurityError(
            ErrorCode.PATH_TRAVERSAL_DETECTED,
            "Filename contains invalid control or null bytes",
            status_code=422,
        )
    if "/" in raw_name or "\\" in raw_name or _DRIVE_PREFIX_RE.match(raw_name):
        raise SecurityError(
            ErrorCode.PATH_TRAVERSAL_DETECTED,
            "Filename must not contain directory separators or drive prefixes",
            status_code=422,
        )

    normalized = unicodedata.normalize("NFC", raw_name).strip()
    if not normalized or normalized in {".", ".."} or ".." in normalized.split("."):
        if normalized in {"", ".", ".."} or ".." in raw_name:
            raise SecurityError(
                ErrorCode.PATH_TRAVERSAL_DETECTED,
                "Path traversal detected in filename",
                status_code=422,
            )

    stem, ext = os.path.splitext(normalized)
    if not stem and not ext:
        raise SecurityError(
            ErrorCode.PATH_TRAVERSAL_DETECTED,
            "Filename cannot be empty",
            status_code=422,
        )

    safe_stem = stem.strip().rstrip(".")
    if not safe_stem:
        safe_stem = "asset"

    if safe_stem.upper() in WINDOWS_RESERVED_STEMS:
        safe_stem = f"_{safe_stem}"

    ext_lower = ext.lower()
    max_stem_len = max(1, 180 - len(ext_lower))
    if len(safe_stem) > max_stem_len:
        safe_stem = safe_stem[:max_stem_len]

    return f"{safe_stem}{ext_lower}"


def assert_safe_relative_path(raw_path: str, base_dir: Path) -> Path:
    if not raw_path or "\x00" in raw_path:
        raise SecurityError(
            ErrorCode.PATH_TRAVERSAL_DETECTED,
            "Unsafe relative path",
            status_code=422,
        )
    if raw_path.startswith(("/", "\\")) or "\\" in raw_path or _DRIVE_PREFIX_RE.match(raw_path):
        raise SecurityError(
            ErrorCode.PATH_TRAVERSAL_DETECTED,
            "Path must be relative within storage root",
            status_code=422,
        )

    posix_path = PurePosixPath(raw_path)
    if posix_path.is_absolute() or any(part in {"", ".", ".."} for part in posix_path.parts):
        raise SecurityError(
            ErrorCode.PATH_TRAVERSAL_DETECTED,
            "Path traversal segments are forbidden",
            status_code=422,
        )

    base_resolved = base_dir.resolve()
    target_resolved = (base_resolved / Path(*posix_path.parts)).resolve()
    if not target_resolved.is_relative_to(base_resolved) or target_resolved == base_resolved:
        raise SecurityError(
            ErrorCode.PATH_TRAVERSAL_DETECTED,
            "Resolved path escapes base directory",
            status_code=422,
        )
    return target_resolved


def validate_archive_entry(
    member_name: str,
    dest_root: Path,
    file_size: int,
    compress_size: int,
    running_total_bytes: int,
    entry_count: int,
    max_entries: int,
    max_total_bytes: int,
    external_attr: int = 0,
) -> Path:
    if stat.S_ISLNK(external_attr >> 16):
        raise SecurityError(
            ErrorCode.ZIP_SLIP_DETECTED,
            "Symbolic links are not permitted in archives",
            status_code=422,
        )
    if entry_count > max_entries:
        raise PayloadTooLargeError(
            f"Archive exceeds maximum entry count ({max_entries})",
            code=ErrorCode.ZIP_SLIP_DETECTED,
        )
    if file_size < 0 or running_total_bytes + file_size > max_total_bytes:
        raise PayloadTooLargeError(
            f"Archive uncompressed size exceeds limit ({max_total_bytes} bytes)",
            code=ErrorCode.ZIP_SLIP_DETECTED,
        )
    if compress_size > 0 and file_size > 10_000_000 and (file_size / compress_size) > 100:
        raise PayloadTooLargeError(
            "Archive compression ratio indicates a zip bomb",
            code=ErrorCode.ZIP_SLIP_DETECTED,
        )

    if not member_name or "\x00" in member_name:
        raise SecurityError(
            ErrorCode.ZIP_SLIP_DETECTED,
            "Invalid archive member name",
            status_code=422,
        )
    if member_name.startswith(("/", "\\")) or "\\" in member_name or _DRIVE_PREFIX_RE.match(member_name):
        raise SecurityError(
            ErrorCode.ZIP_SLIP_DETECTED,
            "Archive member path escapes extraction root",
            status_code=422,
        )

    posix_member = PurePosixPath(member_name)
    if posix_member.is_absolute() or any(part in {"", ".", ".."} for part in posix_member.parts):
        raise SecurityError(
            ErrorCode.ZIP_SLIP_DETECTED,
            "Archive member contains path traversal segments",
            status_code=422,
        )

    dest_resolved = dest_root.resolve()
    target_resolved = (dest_resolved / Path(*posix_member.parts)).resolve()
    if not target_resolved.is_relative_to(dest_resolved) or target_resolved == dest_resolved:
        raise SecurityError(
            ErrorCode.ZIP_SLIP_DETECTED,
            "Archive member escapes destination root",
            status_code=422,
        )
    return target_resolved


def inspect_png_header(data: bytes) -> None:
    if len(data) < 33 or not data.startswith(_PNG_SIGNATURE):
        raise ValidationAppError(
            "Invalid or truncated PNG header",
            code=ErrorCode.CORRUPT_IMAGE,
        )

    offset = 8
    chunks_seen = 0
    ihdr_seen = False

    while offset + 8 <= len(data):
        chunks_seen += 1
        if chunks_seen > 2048:
            raise ValidationAppError(
                "PNG contains excessive metadata chunks",
                code=ErrorCode.CORRUPT_IMAGE,
            )

        chunk_len = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + chunk_len
        crc_end = data_end + 4

        if crc_end > len(data):
            raise ValidationAppError(
                "Truncated PNG chunk detected",
                code=ErrorCode.CORRUPT_IMAGE,
            )

        chunk_payload = data[data_start:data_end]
        if not ihdr_seen:
            if chunk_type != b"IHDR" or chunk_len != 13:
                raise ValidationAppError(
                    "PNG missing valid leading IHDR chunk",
                    code=ErrorCode.CORRUPT_IMAGE,
                )
            ihdr_seen = True
            bit_depth = chunk_payload[8]
            if bit_depth == 16:
                raise ValidationAppError(
                    "16-bit PNG images are deferred in MVP; please convert to 8-bit sRGB PNG, JPEG, or WebP",
                    code=ErrorCode.UNSUPPORTED_BIT_DEPTH,
                )

        if chunk_type == b"acTL":
            raise ValidationAppError(
                "Animated PNG (APNG) is not supported; please upload a static image",
                code=ErrorCode.UNSUPPORTED_ANIMATED_IMAGE,
            )

        if chunk_type == b"cICP" and len(chunk_payload) >= 3:
            transfer_characteristics = chunk_payload[2]
            if transfer_characteristics in {16, 18}:
                raise ValidationAppError(
                    "HDR PNG (PQ/HLG) is not supported in MVP; please convert to standard sRGB",
                    code=ErrorCode.UNSUPPORTED_HDR_IMAGE,
                )

        if chunk_type == b"IEND":
            break

        offset = crc_end

    if not ihdr_seen:
        raise ValidationAppError(
            "PNG missing IHDR header",
            code=ErrorCode.CORRUPT_IMAGE,
        )


def inspect_webp_header(data: bytes) -> None:
    if len(data) < 16 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValidationAppError(
            "Invalid or truncated WebP header",
            code=ErrorCode.CORRUPT_IMAGE,
        )
    if data[12:16] == b"VP8X":
        if len(data) < 21:
            raise ValidationAppError(
                "Truncated WebP VP8X header",
                code=ErrorCode.CORRUPT_IMAGE,
            )
        flags = data[20]
        if (flags & 0x02) != 0:
            raise ValidationAppError(
                "Animated WebP is not supported; please upload a static WebP, PNG, or JPEG",
                code=ErrorCode.UNSUPPORTED_ANIMATED_IMAGE,
            )


def _normalize_content_type(declared_content_type: str | None) -> str:
    if not declared_content_type:
        return ""
    return declared_content_type.split(";", 1)[0].strip().lower()


def validate_and_inspect_image(
    data: bytes,
    filename: str,
    declared_content_type: str | None,
    max_bytes: int,
    max_pixels: int,
    max_dimension: int,
) -> ValidatedImage:
    if len(data) == 0:
        raise ValidationAppError(
            "Uploaded file is empty",
            code=ErrorCode.CORRUPT_IMAGE,
        )
    if len(data) > max_bytes:
        raise PayloadTooLargeError(
            f"Uploaded file exceeds maximum allowed size of {max_bytes} bytes"
        )

    safe_name = sanitize_upload_filename(filename)
    suffix = os.path.splitext(safe_name)[1].lower()

    if suffix in RAW_EXTENSIONS:
        raise UnsupportedMediaTypeError(
            "16-bit camera RAW is deferred in MVP; please convert to sRGB JPEG, PNG, or WebP",
            code=ErrorCode.UNSUPPORTED_RAW_FORMAT,
        )

    if suffix in DEFERRED_EXTENSIONS:
        raise UnsupportedMediaTypeError(
            f"Format '{suffix}' is not supported; please upload sRGB JPEG, PNG, or WebP",
            code=ErrorCode.UNSUPPORTED_MEDIA_TYPE,
        )

    normalized_ct = _normalize_content_type(declared_content_type)
    detected_mime = detect_magic_mime(data)
    if detected_mime is None:
        if normalized_ct in ALLOWED_MIME_TO_EXT or suffix in EXT_TO_EXPECTED_MIME:
            raise ValidationAppError(
                "Uploaded bytes do not match declared JPEG/PNG/WebP image signature",
                code=ErrorCode.MIME_SPOOF_DETECTED,
            )
        raise UnsupportedMediaTypeError(
            "Unsupported media type; only sRGB JPEG, PNG, and WebP are accepted",
            code=ErrorCode.UNSUPPORTED_MEDIA_TYPE,
        )

    if (
        normalized_ct
        and normalized_ct != "application/octet-stream"
        and normalized_ct != detected_mime.value
    ):
        raise ValidationAppError(
            f"Declared Content-Type '{normalized_ct}' does not match detected '{detected_mime.value}'",
            code=ErrorCode.MIME_SPOOF_DETECTED,
        )

    if suffix in EXT_TO_EXPECTED_MIME and EXT_TO_EXPECTED_MIME[suffix] != detected_mime.value:
        raise ValidationAppError(
            f"File extension '{suffix}' does not match detected '{detected_mime.value}'",
            code=ErrorCode.MIME_SPOOF_DETECTED,
        )

    if detected_mime is ImageMime.PNG:
        inspect_png_header(data)
    elif detected_mime is ImageMime.WEBP:
        inspect_webp_header(data)

    previous_max_pixels = Image.MAX_IMAGE_PIXELS
    try:
        Image.MAX_IMAGE_PIXELS = max_pixels
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            try:
                with Image.open(
                    io.BytesIO(data),
                    formats=["JPEG", "PNG", "WEBP"],
                ) as im:
                    width, height = im.size
                    if width <= 0 or height <= 0:
                        raise ValidationAppError(
                            "Image dimensions must be positive",
                            code=ErrorCode.CORRUPT_IMAGE,
                        )
                    if (
                        width > max_dimension
                        or height > max_dimension
                        or (width * height) > max_pixels
                    ):
                        raise ValidationAppError(
                            f"Image dimensions ({width}x{height}) exceed safety bounds",
                            code=ErrorCode.PIXEL_BOMB_DETECTED,
                        )

                    if im.mode == "CMYK":
                        raise ValidationAppError(
                            "CMYK images are deferred in MVP; please convert to sRGB JPEG, PNG, or WebP",
                            code=ErrorCode.UNSUPPORTED_COLOR_SPACE_CMYK,
                        )

                    if im.mode not in ("RGB", "RGBA", "L", "LA", "P", "PA"):
                        raise ValidationAppError(
                            f"Unsupported color/bit-depth mode '{im.mode}'; use 8-bit sRGB JPEG, PNG, or WebP",
                            code=ErrorCode.UNSUPPORTED_BIT_DEPTH,
                        )

                    if getattr(im, "is_animated", False) or getattr(im, "n_frames", 1) > 1:
                        raise ValidationAppError(
                            "Animated images are not supported",
                            code=ErrorCode.UNSUPPORTED_ANIMATED_IMAGE,
                        )

                    im.load()

                    try:
                        raw_orientation = int(im.getexif().get(274, 1))
                    except Exception:
                        raw_orientation = 1
                    exif_orientation = raw_orientation if 1 <= raw_orientation <= 8 else 1
            except AppError:
                raise
            except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
                raise ValidationAppError(
                    "Image exceeds pixel decompression safety limit",
                    code=ErrorCode.PIXEL_BOMB_DETECTED,
                ) from exc
            except (OSError, SyntaxError, ValueError) as exc:
                raise ValidationAppError(
                    "Unable to decode image file",
                    code=ErrorCode.CORRUPT_IMAGE,
                ) from exc
    finally:
        Image.MAX_IMAGE_PIXELS = previous_max_pixels

    return ValidatedImage(
        mime_type=detected_mime,
        width=width,
        height=height,
        exif_orientation=exif_orientation,
        safe_filename=safe_name,
    )
