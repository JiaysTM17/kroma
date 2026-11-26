from __future__ import annotations

import io
import stat
import struct
import zlib
from pathlib import Path

import pytest
from PIL import Image

from app.core.errors import AppError
from app.core.security import (
    sanitize_upload_filename,
    validate_and_inspect_image,
    validate_archive_entry,
)
from app.domain.enums import ErrorCode, ImageMime


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", crc)


def _make_valid_png(
    width: int = 8,
    height: int = 8,
    bit_depth: int = 8,
    color_type: int = 2,
    extra_chunks: list[tuple[bytes, bytes]] | None = None,
) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0)
    bpp = 3 if color_type == 2 else 1
    row_bytes = width * bpp * (2 if bit_depth == 16 else 1)
    raw_scanlines = b"".join(b"\x00" + (b"\x80" * row_bytes) for _ in range(min(height, 16)))
    idat = zlib.compress(raw_scanlines)
    parts = [b"\x89PNG\r\n\x1a\n", _png_chunk(b"IHDR", ihdr)]
    if extra_chunks:
        for ctype, cdata in extra_chunks:
            parts.append(_png_chunk(ctype, cdata))
    parts.append(_png_chunk(b"IDAT", idat))
    parts.append(_png_chunk(b"IEND", b""))
    return b"".join(parts)


def _make_pillow_image(mode: str, fmt: str, size: tuple[int, int] = (16, 16)) -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size).save(buf, format=fmt)
    return buf.getvalue()


def _make_animated_webp() -> bytes:
    # Minimal RIFF WEBP container with VP8X chunk setting animation flag (0x02)
    vp8x_payload = struct.pack("<B3s3s3s", 0x02, b"\x0f\x00\x00", b"\x0f\x00\x00", b"\x00\x00\x00")
    # Include a minimal ANMF/VP8X payload so length >= 21
    body = b"WEBP" + b"VP8X" + struct.pack("<I", len(vp8x_payload)) + vp8x_payload
    return b"RIFF" + struct.pack("<I", len(body)) + body


def test_valid_jpeg_png_webp_accepted() -> None:
    jpeg_bytes = _make_pillow_image("RGB", "JPEG")
    png_bytes = _make_pillow_image("RGBA", "PNG")
    webp_bytes = _make_pillow_image("RGBA", "WEBP")

    r1 = validate_and_inspect_image(jpeg_bytes, "shoe.jpg", "image/jpeg", 5_000_000, 50_000_000, 16_384)
    r2 = validate_and_inspect_image(png_bytes, "shoe.png", "image/png", 5_000_000, 50_000_000, 16_384)
    r3 = validate_and_inspect_image(webp_bytes, "shoe.webp", "image/webp", 5_000_000, 50_000_000, 16_384)

    assert r1.mime_type == ImageMime.JPEG
    assert r2.mime_type == ImageMime.PNG
    assert r3.mime_type == ImageMime.WEBP


def test_mime_spoof_rejected() -> None:
    png_bytes = _make_pillow_image("RGB", "PNG")
    jpeg_bytes = _make_pillow_image("RGB", "JPEG")

    # Valid PNG bytes with .jpg extension
    with pytest.raises(AppError) as exc1:
        validate_and_inspect_image(png_bytes, "fake.jpg", "image/jpeg", 5_000_000, 50_000_000, 16_384)
    assert exc1.value.code == ErrorCode.MIME_SPOOF_DETECTED

    # HTML/SVG bytes disguised as .png
    with pytest.raises(AppError) as exc2:
        validate_and_inspect_image(b"<svg><script>alert(1)</script></svg>", "evil.png", "image/png", 5_000_000, 50_000_000, 16_384)
    assert exc2.value.code == ErrorCode.MIME_SPOOF_DETECTED

    # Valid JPEG bytes with Content-Type: image/png
    with pytest.raises(AppError) as exc3:
        validate_and_inspect_image(jpeg_bytes, "photo.jpg", "image/png", 5_000_000, 50_000_000, 16_384)
    assert exc3.value.code == ErrorCode.MIME_SPOOF_DETECTED


def test_path_traversal_and_reserved_names() -> None:
    for bad in [
        "../../etc/passwd.png",
        "..\\..\\evil.png",
        "/abs/path.png",
        "C:\\evil.png",
        "null\x00.png",
    ]:
        with pytest.raises(AppError) as exc:
            sanitize_upload_filename(bad)
        assert exc.value.code == ErrorCode.PATH_TRAVERSAL_DETECTED

    assert sanitize_upload_filename("CON.png") == "_CON.png"
    assert sanitize_upload_filename("NUL.jpg") == "_NUL.jpg"
    assert sanitize_upload_filename("Sản phẩm 01.PNG") == "Sản phẩm 01.png"


def test_zip_slip_and_zip_bomb_rejected(tmp_path: Path) -> None:
    dest = tmp_path / "extract"
    dest.mkdir()

    for bad_member in ["../escape.png", "a/../../b.png", "/etc/passwd", "C:\\win.ini"]:
        with pytest.raises(AppError) as exc:
            validate_archive_entry(
                member_name=bad_member,
                dest_root=dest,
                file_size=100,
                compress_size=50,
                running_total_bytes=0,
                entry_count=1,
                max_entries=500,
                max_total_bytes=250_000_000,
            )
        assert exc.value.code == ErrorCode.ZIP_SLIP_DETECTED

    # Symlink entry rejected
    with pytest.raises(AppError) as exc_link:
        validate_archive_entry(
            member_name="link.png",
            dest_root=dest,
            file_size=100,
            compress_size=50,
            running_total_bytes=0,
            entry_count=1,
            max_entries=500,
            max_total_bytes=250_000_000,
            external_attr=(stat.S_IFLNK << 16),
        )
    assert exc_link.value.code == ErrorCode.ZIP_SLIP_DETECTED

    # Too many entries
    with pytest.raises(AppError) as exc_count:
        validate_archive_entry(
            member_name="ok.png",
            dest_root=dest,
            file_size=100,
            compress_size=50,
            running_total_bytes=0,
            entry_count=501,
            max_entries=500,
            max_total_bytes=250_000_000,
        )
    assert exc_count.value.code == ErrorCode.ZIP_SLIP_DETECTED

    # Exceeds total uncompressed limit
    with pytest.raises(AppError) as exc_size:
        validate_archive_entry(
            member_name="huge.png",
            dest_root=dest,
            file_size=10_000,
            compress_size=1000,
            running_total_bytes=249_995_000,
            entry_count=1,
            max_entries=500,
            max_total_bytes=250_000_000,
        )
    assert exc_size.value.code == ErrorCode.ZIP_SLIP_DETECTED


def test_pixel_bomb_rejected_pre_decode() -> None:
    huge_ihdr_png = _make_valid_png(width=20000, height=20000)
    with pytest.raises(AppError) as exc:
        validate_and_inspect_image(
            huge_ihdr_png, "bomb.png", "image/png", 5_000_000, 50_000_000, 16_384
        )
    assert exc.value.code == ErrorCode.PIXEL_BOMB_DETECTED

    # Strict 1x pixel limit check (15x10 = 150 > 100)
    small_png = _make_pillow_image("RGB", "PNG", size=(15, 10))
    with pytest.raises(AppError) as exc_1x:
        validate_and_inspect_image(
            small_png, "over100.png", "image/png", 5_000_000, 100, 16_384
        )
    assert exc_1x.value.code == ErrorCode.PIXEL_BOMB_DETECTED


def test_cmyk_16bit_png_raw_animated_hdr_rejected() -> None:
    cmyk_jpeg = _make_pillow_image("CMYK", "JPEG")
    with pytest.raises(AppError) as exc_cmyk:
        validate_and_inspect_image(
            cmyk_jpeg, "print.jpg", "image/jpeg", 5_000_000, 50_000_000, 16_384
        )
    assert exc_cmyk.value.code == ErrorCode.UNSUPPORTED_COLOR_SPACE_CMYK

    png_16_rgb = _make_valid_png(width=4, height=4, bit_depth=16, color_type=2)
    with pytest.raises(AppError) as exc_16_rgb:
        validate_and_inspect_image(
            png_16_rgb, "16bit_rgb.png", "image/png", 5_000_000, 50_000_000, 16_384
        )
    assert exc_16_rgb.value.code == ErrorCode.UNSUPPORTED_BIT_DEPTH

    png_16_gray = _make_pillow_image("I;16", "PNG", size=(8, 8))
    with pytest.raises(AppError) as exc_16_gray:
        validate_and_inspect_image(
            png_16_gray, "16bit_gray.png", "image/png", 5_000_000, 50_000_000, 16_384
        )
    assert exc_16_gray.value.code == ErrorCode.UNSUPPORTED_BIT_DEPTH

    for raw_ext in [".cr2", ".nef", ".arw", ".dng"]:
        with pytest.raises(AppError) as exc_raw:
            validate_and_inspect_image(
                b"RAWDATA", f"photo{raw_ext}", "application/octet-stream", 5_000_000, 50_000_000, 16_384
            )
        assert exc_raw.value.code == ErrorCode.UNSUPPORTED_RAW_FORMAT

    apng = _make_valid_png(
        extra_chunks=[(b"acTL", struct.pack(">II", 2, 0))]
    )
    with pytest.raises(AppError) as exc_apng:
        validate_and_inspect_image(
            apng, "anim.png", "image/png", 5_000_000, 50_000_000, 16_384
        )
    assert exc_apng.value.code == ErrorCode.UNSUPPORTED_ANIMATED_IMAGE

    anim_webp = _make_animated_webp()
    with pytest.raises(AppError) as exc_webp:
        validate_and_inspect_image(
            anim_webp, "anim.webp", "image/webp", 5_000_000, 50_000_000, 16_384
        )
    assert exc_webp.value.code == ErrorCode.UNSUPPORTED_ANIMATED_IMAGE

    hdr_png = _make_valid_png(
        extra_chunks=[(b"cICP", bytes([9, 0, 16, 1]))]
    )
    with pytest.raises(AppError) as exc_hdr:
        validate_and_inspect_image(
            hdr_png, "hdr.png", "image/png", 5_000_000, 50_000_000, 16_384
        )
    assert exc_hdr.value.code == ErrorCode.UNSUPPORTED_HDR_IMAGE
