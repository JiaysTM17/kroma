from __future__ import annotations

import json
import math
import re
import unicodedata
from typing import Any

from app.domain.enums import MarketplaceId
from app.domain.models import SafeZone

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_DESCRIPTION_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PRESET_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_ASPECT_RATIO_RE = re.compile(r"^(\d+):(\d+)$")

ALLOWED_PRESET_FORMATS: tuple[str, ...] = ("webp", "jpeg", "png")
MIN_PRESET_DIMENSION = 64
MAX_PRESET_DIMENSION = 16_384


def validate_project_name(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("Project name must be a string")
    normalized = unicodedata.normalize("NFC", name).strip()
    if not normalized:
        raise ValueError("Project name cannot be empty")
    if len(normalized) > 120:
        raise ValueError("Project name cannot exceed 120 characters")
    if _CONTROL_CHAR_RE.search(normalized):
        raise ValueError("Project name contains invalid control characters")
    return normalized


def validate_project_description(description: str) -> str:
    if not isinstance(description, str):
        raise ValueError("Project description must be a string")
    normalized = unicodedata.normalize("NFC", description).strip()
    if len(normalized) > 1000:
        raise ValueError("Project description cannot exceed 1000 characters")
    return normalized


def _check_depth_and_types(value: Any, depth: int, max_depth: int) -> None:
    if depth > max_depth:
        raise ValueError(f"State payload exceeds maximum nesting depth of {max_depth}")
    if value is None or isinstance(value, (bool, int, float, str)):
        return
    if isinstance(value, list):
        for item in value:
            _check_depth_and_types(item, depth + 1, max_depth)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("State object keys must be strings")
            _check_depth_and_types(item, depth + 1, max_depth)
        return
    raise ValueError(f"Unsupported value type in project state: {type(value).__name__}")


def validate_state_payload(
    state: dict[str, Any],
    schema_version: int = 1,
    max_depth: int = 16,
) -> None:
    if schema_version < 1:
        raise ValueError("schema_version must be >= 1")
    if not isinstance(state, dict):
        raise ValueError("State payload must be a JSON object")
    _check_depth_and_types(state, depth=1, max_depth=max_depth)


def check_revision_conflict(
    expected_revision_id: str | None,
    current_revision_id: str,
) -> bool:
    if expected_revision_id is None:
        return False
    return expected_revision_id != current_revision_id


def validate_variant_name(variant: str | None, *, allow_default: bool = True) -> str:
    if variant is None:
        if allow_default:
            return "default"
        raise ValueError("Variant name cannot be empty")
    if not isinstance(variant, str):
        raise ValueError("Variant name must be a string")
    normalized = unicodedata.normalize("NFC", variant).strip()
    if not normalized:
        if allow_default:
            return "default"
        raise ValueError("Variant name cannot be empty")
    if len(normalized) > 64:
        raise ValueError("Variant name cannot exceed 64 characters")
    if _CONTROL_CHAR_RE.search(normalized):
        raise ValueError("Variant name contains invalid control characters")
    return normalized


def validate_asset_metadata(
    metadata: dict[str, Any],
    *,
    max_bytes: int = 65_536,
) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        raise ValueError("Asset metadata must be a JSON object")
    _check_depth_and_types(metadata, depth=1, max_depth=8)
    try:
        encoded = json.dumps(
            metadata,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Asset metadata is not valid JSON: {exc}") from exc
    if len(encoded) > max_bytes:
        raise ValueError(f"Asset metadata exceeds maximum size of {max_bytes} bytes")
    return metadata


def parse_metadata_json(
    raw: str | None,
    *,
    max_bytes: int = 65_536,
) -> dict[str, Any]:
    if raw is None or not raw.strip():
        return {}
    if not isinstance(raw, str):
        raise ValueError("metadata_json must be a JSON string")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid metadata_json payload: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("metadata_json must decode to a JSON object")
    return validate_asset_metadata(parsed, max_bytes=max_bytes)


def validate_preset_id(preset_id: str) -> str:
    if not isinstance(preset_id, str):
        raise ValueError("Preset ID must be a string")
    normalized = unicodedata.normalize("NFC", preset_id).strip().lower()
    if not _PRESET_ID_RE.fullmatch(normalized):
        raise ValueError(
            "Preset ID must be 2-64 chars using lowercase letters, digits, '_' or '-', starting with alphanumeric"
        )
    return normalized


def validate_marketplace_id(value: str | MarketplaceId) -> MarketplaceId:
    if isinstance(value, MarketplaceId):
        return value
    if not isinstance(value, str):
        raise ValueError("Marketplace must be a string")
    normalized = unicodedata.normalize("NFC", value).strip().lower()
    try:
        return MarketplaceId(normalized)
    except ValueError as exc:
        allowed = ", ".join(m.value for m in MarketplaceId)
        raise ValueError(f"Invalid marketplace '{value}'; expected one of: {allowed}") from exc


def validate_preset_name(name: str, field_name: str = "name") -> str:
    if not isinstance(name, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = unicodedata.normalize("NFC", name).strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    if len(normalized) > 120:
        raise ValueError(f"{field_name} cannot exceed 120 characters")
    if _CONTROL_CHAR_RE.search(normalized):
        raise ValueError(f"{field_name} contains invalid control characters")
    return normalized


def validate_rule_description(desc: str, field_name: str = "rule_description") -> str:
    if not isinstance(desc, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = unicodedata.normalize("NFC", desc).strip()
    if len(normalized) > 1000:
        raise ValueError(f"{field_name} cannot exceed 1000 characters")
    if _DESCRIPTION_CONTROL_CHAR_RE.search(normalized):
        raise ValueError(f"{field_name} contains invalid control characters")
    return normalized


def validate_preset_version(version: str) -> str:
    if not isinstance(version, str):
        raise ValueError("Preset version must be a string")
    normalized = unicodedata.normalize("NFC", version).strip()
    if not normalized:
        raise ValueError("Preset version cannot be empty")
    if len(normalized) > 32:
        raise ValueError("Preset version cannot exceed 32 characters")
    if _CONTROL_CHAR_RE.search(normalized):
        raise ValueError("Preset version contains invalid control characters")
    return normalized


def validate_preset_dimensions(width: int, height: int) -> tuple[int, int]:
    if isinstance(width, bool) or not isinstance(width, int):
        raise ValueError("Preset width must be an integer")
    if isinstance(height, bool) or not isinstance(height, int):
        raise ValueError("Preset height must be an integer")
    if not (MIN_PRESET_DIMENSION <= width <= MAX_PRESET_DIMENSION):
        raise ValueError(
            f"Preset width must be between {MIN_PRESET_DIMENSION} and {MAX_PRESET_DIMENSION}"
        )
    if not (MIN_PRESET_DIMENSION <= height <= MAX_PRESET_DIMENSION):
        raise ValueError(
            f"Preset height must be between {MIN_PRESET_DIMENSION} and {MAX_PRESET_DIMENSION}"
        )
    return width, height


def derive_aspect_ratio(width: int, height: int) -> str:
    validate_preset_dimensions(width, height)
    divisor = math.gcd(width, height)
    return f"{width // divisor}:{height // divisor}"


def validate_aspect_ratio(aspect_ratio: str | None, width: int, height: int) -> str:
    if aspect_ratio is None or not str(aspect_ratio).strip():
        return derive_aspect_ratio(width, height)
    if not isinstance(aspect_ratio, str):
        raise ValueError("aspect_ratio must be a string")
    cleaned = aspect_ratio.strip()
    match = _ASPECT_RATIO_RE.fullmatch(cleaned)
    if match is None:
        raise ValueError("aspect_ratio must match '<w>:<h>' with positive integers")
    w_part = int(match.group(1))
    h_part = int(match.group(2))
    if w_part <= 0 or h_part <= 0:
        raise ValueError("aspect_ratio components must be positive integers")
    return f"{w_part}:{h_part}"


def validate_formats(formats: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    if isinstance(formats, (str, bytes)) or not isinstance(formats, (tuple, list)):
        raise ValueError("formats must be a non-empty list of format names")
    if not formats:
        raise ValueError("formats must contain at least one format")
    normalized: list[str] = []
    seen: set[str] = set()
    for entry in formats:
        if not isinstance(entry, str):
            raise ValueError("Each format entry must be a string")
        fmt = entry.strip().lower()
        if fmt == "jpg":
            fmt = "jpeg"
        if fmt not in ALLOWED_PRESET_FORMATS:
            allowed = ", ".join(ALLOWED_PRESET_FORMATS)
            raise ValueError(f"Unsupported preset format '{entry}'; expected one of: {allowed}")
        if fmt not in seen:
            seen.add(fmt)
            normalized.append(fmt)
    return tuple(normalized)


def validate_background_rgb(
    rgb: tuple[int, int, int] | list[int] | None,
) -> tuple[int, int, int] | None:
    if rgb is None:
        return None
    if isinstance(rgb, (str, bytes)) or not isinstance(rgb, (tuple, list)) or len(rgb) != 3:
        raise ValueError("background_rgb must be a 3-element [R, G, B] list or null")
    channels: list[int] = []
    for channel in rgb:
        if isinstance(channel, bool) or not isinstance(channel, int):
            raise ValueError("background_rgb values must be integers in [0, 255]")
        if not (0 <= channel <= 255):
            raise ValueError("background_rgb values must be between 0 and 255")
        channels.append(channel)
    return (channels[0], channels[1], channels[2])


def validate_subject_area_ratio(ratio: float | None) -> float | None:
    if ratio is None:
        return None
    if isinstance(ratio, bool) or not isinstance(ratio, (int, float)):
        raise ValueError("subject_area_ratio must be a number in (0.0, 1.0]")
    value = float(ratio)
    if not math.isfinite(value) or value <= 0.0 or value > 1.0:
        raise ValueError("subject_area_ratio must be > 0.0 and <= 1.0")
    return value


def validate_safe_zone(safe_zone: SafeZone | dict[str, Any] | None) -> SafeZone | None:
    if safe_zone is None:
        return None
    if isinstance(safe_zone, SafeZone):
        raw = {
            "top": safe_zone.top,
            "right": safe_zone.right,
            "bottom": safe_zone.bottom,
            "left": safe_zone.left,
        }
    elif isinstance(safe_zone, dict):
        raw = safe_zone
    else:
        raise ValueError("safe_zone must be an object with top, right, bottom, left")

    parsed: dict[str, float] = {}
    for edge in ("top", "right", "bottom", "left"):
        val = raw.get(edge)
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ValueError(f"safe_zone.{edge} must be a number in [0.0, 1.0]")
        fval = float(val)
        if not math.isfinite(fval) or fval < 0.0 or fval > 1.0:
            raise ValueError(f"safe_zone.{edge} must be between 0.0 and 1.0")
        parsed[edge] = fval

    if parsed["left"] + parsed["right"] >= 1.0:
        raise ValueError("safe_zone left + right must be < 1.0")
    if parsed["top"] + parsed["bottom"] >= 1.0:
        raise ValueError("safe_zone top + bottom must be < 1.0")

    return SafeZone(
        top=parsed["top"],
        right=parsed["right"],
        bottom=parsed["bottom"],
        left=parsed["left"],
    )
