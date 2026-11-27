from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

from app.domain.enums import (
    BatchStatus,
    MarketplaceId,
    ProofingAction,
    ProofingDecision,
    ProofingStatus,
)
from app.domain.models import BatchAdjustments, SafeZone

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


def _validate_finite_float(
    value: Any,
    field_name: str,
    *,
    min_value: float,
    max_value: float,
    exclusive_min: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite number")
    fval = float(value)
    if not math.isfinite(fval):
        raise ValueError(f"{field_name} must be finite")
    if exclusive_min:
        if fval <= min_value or fval > max_value:
            raise ValueError(f"{field_name} must be > {min_value} and <= {max_value}")
    else:
        if fval < min_value or fval > max_value:
            raise ValueError(f"{field_name} must be between {min_value} and {max_value}")
    return fval


def validate_batch_asset_ids(
    asset_ids: list[str] | tuple[str, ...],
    max_assets: int = 100,
) -> tuple[str, ...]:
    if isinstance(asset_ids, (str, bytes)) or not isinstance(asset_ids, (list, tuple)):
        raise ValueError("asset_ids must be a non-empty list of asset IDs")
    if not asset_ids:
        raise ValueError("asset_ids must contain at least one asset ID")
    deduped: list[str] = []
    seen: set[str] = set()
    for item in asset_ids:
        if not isinstance(item, str):
            raise ValueError("Each asset_id must be a string")
        cleaned = item.strip()
        if not cleaned:
            raise ValueError("asset_ids cannot contain empty values")
        if cleaned not in seen:
            seen.add(cleaned)
            deduped.append(cleaned)
    if len(deduped) > max_assets:
        raise ValueError(f"asset_ids cannot exceed {max_assets} assets per batch job")
    return tuple(deduped)


def validate_batch_format(
    fmt: str | None,
    fallback_formats: tuple[str, ...] | list[str],
) -> str:
    if fmt is None or not str(fmt).strip():
        if fallback_formats:
            candidate = str(fallback_formats[0]).strip().lower()
        else:
            candidate = "webp"
    else:
        if not isinstance(fmt, str):
            raise ValueError("format must be a string")
        candidate = fmt.strip().lower()
    if candidate == "jpg":
        candidate = "jpeg"
    if candidate not in ALLOWED_PRESET_FORMATS:
        allowed = ", ".join(ALLOWED_PRESET_FORMATS)
        raise ValueError(f"Unsupported batch format '{fmt}'; expected one of: {allowed}")
    return candidate


def validate_batch_quality(quality: int) -> int:
    if isinstance(quality, bool) or not isinstance(quality, int):
        raise ValueError("quality must be an integer between 1 and 100")
    if not (1 <= quality <= 100):
        raise ValueError("quality must be between 1 and 100")
    return quality


def validate_watermark_text(text: str | None) -> str | None:
    if text is None:
        return None
    if not isinstance(text, str):
        raise ValueError("watermark_text must be a string")
    normalized = unicodedata.normalize("NFC", text).strip()
    if not normalized:
        return None
    if len(normalized) > 120:
        raise ValueError("watermark_text cannot exceed 120 characters")
    if _CONTROL_CHAR_RE.search(normalized):
        raise ValueError("watermark_text contains invalid control characters")
    return normalized


def validate_batch_adjustments(
    raw: BatchAdjustments | dict[str, Any] | None,
) -> BatchAdjustments:
    if raw is None:
        return BatchAdjustments()
    if isinstance(raw, BatchAdjustments):
        data = {
            "brightness": raw.brightness,
            "contrast": raw.contrast,
            "saturation": raw.saturation,
            "sharpness": raw.sharpness,
            "exposure": raw.exposure,
        }
    elif isinstance(raw, dict):
        data = raw
    else:
        raise ValueError("adjustments must be an object")

    brightness = _validate_finite_float(
        data.get("brightness", 1.0), "adjustments.brightness", min_value=0.1, max_value=3.0
    )
    contrast = _validate_finite_float(
        data.get("contrast", 1.0), "adjustments.contrast", min_value=0.1, max_value=3.0
    )
    saturation = _validate_finite_float(
        data.get("saturation", 1.0), "adjustments.saturation", min_value=0.0, max_value=3.0
    )
    sharpness = _validate_finite_float(
        data.get("sharpness", 1.0), "adjustments.sharpness", min_value=0.0, max_value=3.0
    )
    raw_exposure = data.get("exposure")
    exposure = (
        _validate_finite_float(
            raw_exposure, "adjustments.exposure", min_value=-100.0, max_value=100.0
        )
        if raw_exposure is not None
        else None
    )
    return BatchAdjustments(
        brightness=brightness,
        contrast=contrast,
        saturation=saturation,
        sharpness=sharpness,
        exposure=exposure,
    )


def compute_batch_progress(
    total_items: int,
    completed_items: int,
    failed_items: int,
    cancelled_items: int = 0,
) -> float:
    if total_items <= 0:
        return 0.0
    done = max(0, completed_items + failed_items + cancelled_items)
    pct = round((done / total_items) * 100.0, 2)
    return max(0.0, min(100.0, pct))


def derive_batch_status(
    total_items: int,
    completed_items: int,
    failed_items: int,
    cancelled_items: int,
    cancel_requested: bool,
) -> BatchStatus:
    if cancel_requested or cancelled_items > 0:
        return BatchStatus.CANCELLED
    if total_items > 0 and completed_items == total_items and failed_items == 0:
        return BatchStatus.COMPLETED
    if completed_items > 0 and failed_items > 0:
        return BatchStatus.PARTIAL_FAILED
    return BatchStatus.FAILED


def validate_proofing_title(title: str) -> str:
    if not isinstance(title, str):
        raise ValueError("Proofing title must be a string")
    normalized = unicodedata.normalize("NFC", title).strip()
    if not normalized:
        raise ValueError("Proofing title cannot be empty")
    if len(normalized) > 200:
        raise ValueError("Proofing title cannot exceed 200 characters")
    if _CONTROL_CHAR_RE.search(normalized):
        raise ValueError("Proofing title contains invalid control characters")
    return normalized


def validate_proofing_actor(
    actor: str | None,
    *,
    default: str | None = None,
    field_name: str = "author",
) -> str:
    if actor is None:
        if default is not None:
            return default
        raise ValueError(f"{field_name} cannot be empty")
    if not isinstance(actor, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = unicodedata.normalize("NFC", actor).strip()
    if not normalized:
        if default is not None:
            return default
        raise ValueError(f"{field_name} cannot be empty")
    if len(normalized) > 120:
        raise ValueError(f"{field_name} cannot exceed 120 characters")
    if _CONTROL_CHAR_RE.search(normalized):
        raise ValueError(f"{field_name} contains invalid control characters")
    return normalized


def validate_proofing_comment_body(
    body: str | None,
    *,
    allow_empty: bool = False,
) -> str:
    if body is None:
        if allow_empty:
            return ""
        raise ValueError("Comment body cannot be empty")
    if not isinstance(body, str):
        raise ValueError("Comment body must be a string")
    normalized = unicodedata.normalize("NFC", body).strip()
    if not normalized and not allow_empty:
        raise ValueError("Comment body cannot be empty")
    if len(normalized) > 2000:
        raise ValueError("Comment body cannot exceed 2000 characters")
    if _DESCRIPTION_CONTROL_CHAR_RE.search(normalized):
        raise ValueError("Comment body contains invalid control characters")
    return normalized


def validate_pin_coordinates(
    pin_x: float | None,
    pin_y: float | None,
) -> tuple[float | None, float | None]:
    if (pin_x is None) != (pin_y is None):
        raise ValueError("Both pin_x and pin_y must be provided together")
    if pin_x is None and pin_y is None:
        return None, None
    fx = _validate_finite_float(pin_x, "pin_x", min_value=0.0, max_value=1.0)
    fy = _validate_finite_float(pin_y, "pin_y", min_value=0.0, max_value=1.0)
    return fx, fy


def validate_expires_hours(expires_hours: int | float | None) -> float | None:
    if expires_hours is None:
        return None
    return _validate_finite_float(
        expires_hours,
        "expires_hours",
        min_value=0.0,
        max_value=8760.0,
        exclusive_min=True,
    )


def parse_iso_utc(raw: str) -> datetime:
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_session_expired(expires_at: str | None, now: datetime) -> bool:
    if not expires_at:
        return False
    exp_dt = parse_iso_utc(expires_at)
    now_utc = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
    return now_utc >= exp_dt


def is_revision_stale(
    session_revision_id: str | None,
    current_revision_id: str | None,
) -> bool:
    return bool(
        session_revision_id
        and current_revision_id
        and session_revision_id != current_revision_id
    )


def next_status_for_action(
    current: ProofingStatus,
    action: ProofingAction,
) -> ProofingStatus:
    if current == ProofingStatus.ARCHIVED:
        raise ValueError("Archived proofing session must be reopened before submitting feedback")
    if action == ProofingAction.APPROVE:
        return ProofingStatus.APPROVED
    if action == ProofingAction.REQUEST_CHANGE:
        return ProofingStatus.REVISION_REQUESTED
    if current == ProofingStatus.PENDING:
        return ProofingStatus.IN_REVIEW
    return current


def next_status_for_decision(
    current: ProofingStatus,
    decision: ProofingDecision,
) -> ProofingStatus:
    if decision == ProofingDecision.APPROVE:
        if current == ProofingStatus.ARCHIVED:
            raise ValueError("Archived proofing session must be reopened before approval")
        return ProofingStatus.APPROVED
    if decision == ProofingDecision.REQUEST_CHANGE:
        if current == ProofingStatus.ARCHIVED:
            raise ValueError("Archived proofing session must be reopened before requesting changes")
        return ProofingStatus.REVISION_REQUESTED
    if decision == ProofingDecision.REOPEN:
        return ProofingStatus.PENDING
    if decision == ProofingDecision.ARCHIVE:
        return ProofingStatus.ARCHIVED
    # REVOKE preserves current status while setting revoked_at
    return current
