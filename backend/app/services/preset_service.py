from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Any

from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError, ValidationAppError
from app.core.ids import utc_now_iso
from app.domain.enums import ErrorCode, MarketplaceId
from app.domain.models import MarketplacePreset, SafeZone
from app.domain.presets import CANONICAL_SYSTEM_PRESETS
from app.domain.rules import (
    derive_aspect_ratio,
    validate_aspect_ratio,
    validate_background_rgb,
    validate_formats,
    validate_marketplace_id,
    validate_preset_dimensions,
    validate_preset_id,
    validate_preset_name,
    validate_preset_version,
    validate_rule_description,
    validate_safe_zone,
    validate_subject_area_ratio,
)
from app.storage.ports import DatabasePort

_SLUG_CLEAN_RE = re.compile(r"[^a-z0-9]+")


def _generate_preset_id(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    slug = _SLUG_CLEAN_RE.sub("_", ascii_name).strip("_")[:24]
    suffix = uuid.uuid4().hex[:8]
    if slug:
        return f"custom_{slug}_{suffix}"
    return f"custom_{suffix}"


class PresetService:
    def __init__(
        self,
        repo: DatabasePort,
        system_presets: tuple[MarketplacePreset, ...] = CANONICAL_SYSTEM_PRESETS,
    ) -> None:
        self._repo = repo
        self._system_by_id: dict[str, MarketplacePreset] = {p.id: p for p in system_presets}
        self._repo.seed_system_presets(system_presets)

    def list_presets(self) -> list[MarketplacePreset]:
        return self._repo.list_presets()

    def get_preset(self, preset_id: str) -> MarketplacePreset:
        preset = self._repo.get_preset(preset_id)
        if preset is None:
            raise NotFoundError(f"Preset '{preset_id}' not found")
        return preset

    def create_preset(
        self,
        *,
        preset_id: str | None = None,
        marketplace: str | MarketplaceId = MarketplaceId.CUSTOM,
        name_en: str,
        name_vi: str | None = None,
        rule_description_en: str = "",
        rule_description_vi: str = "",
        version: str = "1.0.0",
        width: int,
        height: int,
        aspect_ratio: str | None = None,
        formats: list[str] | tuple[str, ...] = ("webp", "jpeg"),
        background_rgb: list[int] | tuple[int, int, int] | None = None,
        subject_area_ratio: float | None = None,
        safe_zone: SafeZone | dict[str, Any] | None = None,
    ) -> MarketplacePreset:
        try:
            clean_name_en = validate_preset_name(name_en, "name_en")
            clean_name_vi = validate_preset_name(
                name_vi if name_vi is not None and name_vi.strip() else clean_name_en,
                "name_vi",
            )
            raw_id = preset_id.strip() if isinstance(preset_id, str) and preset_id.strip() else _generate_preset_id(clean_name_en)
            clean_id = validate_preset_id(raw_id)
            clean_marketplace = validate_marketplace_id(marketplace)
            clean_desc_en = validate_rule_description(rule_description_en, "rule_description_en")
            clean_desc_vi = validate_rule_description(rule_description_vi, "rule_description_vi")
            clean_version = validate_preset_version(version)
            clean_w, clean_h = validate_preset_dimensions(width, height)
            clean_ratio = validate_aspect_ratio(aspect_ratio, clean_w, clean_h)
            clean_formats = validate_formats(formats)
            clean_bg = validate_background_rgb(background_rgb)
            clean_subject_ratio = validate_subject_area_ratio(subject_area_ratio)
            clean_safe_zone = validate_safe_zone(safe_zone)
        except ValueError as exc:
            raise ValidationAppError(str(exc)) from exc

        if self._repo.get_preset(clean_id) is not None:
            raise ConflictError(f"Preset '{clean_id}' already exists")

        now = utc_now_iso()
        preset = MarketplacePreset(
            id=clean_id,
            marketplace=clean_marketplace,
            name_en=clean_name_en,
            name_vi=clean_name_vi,
            rule_description_en=clean_desc_en,
            rule_description_vi=clean_desc_vi,
            version=clean_version,
            aspect_ratio=clean_ratio,
            width=clean_w,
            height=clean_h,
            formats=clean_formats,
            background_rgb=clean_bg,
            subject_area_ratio=clean_subject_ratio,
            safe_zone=clean_safe_zone,
            editable=True,
            is_system=False,
            created_at=now,
            updated_at=now,
        )
        return self._repo.create_preset(preset)

    def update_preset(
        self,
        preset_id: str,
        fields_set: set[str],
        **updates: Any,
    ) -> MarketplacePreset:
        existing = self.get_preset(preset_id)
        if not existing.editable:
            raise ForbiddenError(f"Preset '{preset_id}' is not editable")

        try:
            if "marketplace" in fields_set:
                if updates.get("marketplace") is None:
                    raise ValueError("marketplace cannot be null")
                clean_marketplace = validate_marketplace_id(updates["marketplace"])
            else:
                clean_marketplace = existing.marketplace

            if "name_en" in fields_set:
                if updates.get("name_en") is None:
                    raise ValueError("name_en cannot be null")
                clean_name_en = validate_preset_name(updates["name_en"], "name_en")
            else:
                clean_name_en = existing.name_en

            if "name_vi" in fields_set:
                if updates.get("name_vi") is None:
                    raise ValueError("name_vi cannot be null")
                clean_name_vi = validate_preset_name(updates["name_vi"], "name_vi")
            else:
                clean_name_vi = existing.name_vi

            if "rule_description_en" in fields_set:
                if updates.get("rule_description_en") is None:
                    raise ValueError("rule_description_en cannot be null")
                clean_desc_en = validate_rule_description(
                    updates["rule_description_en"], "rule_description_en"
                )
            else:
                clean_desc_en = existing.rule_description_en

            if "rule_description_vi" in fields_set:
                if updates.get("rule_description_vi") is None:
                    raise ValueError("rule_description_vi cannot be null")
                clean_desc_vi = validate_rule_description(
                    updates["rule_description_vi"], "rule_description_vi"
                )
            else:
                clean_desc_vi = existing.rule_description_vi

            if "version" in fields_set:
                if updates.get("version") is None:
                    raise ValueError("version cannot be null")
                clean_version = validate_preset_version(updates["version"])
            else:
                clean_version = existing.version

            raw_w = updates["width"] if "width" in fields_set else existing.width
            raw_h = updates["height"] if "height" in fields_set else existing.height
            if raw_w is None or raw_h is None:
                raise ValueError("width and height cannot be null")
            clean_w, clean_h = validate_preset_dimensions(raw_w, raw_h)

            if "aspect_ratio" in fields_set:
                clean_ratio = validate_aspect_ratio(updates.get("aspect_ratio"), clean_w, clean_h)
            elif "width" in fields_set or "height" in fields_set:
                clean_ratio = derive_aspect_ratio(clean_w, clean_h)
            else:
                clean_ratio = existing.aspect_ratio

            if "formats" in fields_set:
                if updates.get("formats") is None:
                    raise ValueError("formats cannot be null")
                clean_formats = validate_formats(updates["formats"])
            else:
                clean_formats = existing.formats

            if "background_rgb" in fields_set:
                clean_bg = validate_background_rgb(updates.get("background_rgb"))
            else:
                clean_bg = existing.background_rgb

            if "subject_area_ratio" in fields_set:
                clean_subject_ratio = validate_subject_area_ratio(updates.get("subject_area_ratio"))
            else:
                clean_subject_ratio = existing.subject_area_ratio

            if "safe_zone" in fields_set:
                clean_safe_zone = validate_safe_zone(updates.get("safe_zone"))
            else:
                clean_safe_zone = existing.safe_zone
        except ValueError as exc:
            raise ValidationAppError(str(exc)) from exc

        updated = MarketplacePreset(
            id=existing.id,
            marketplace=clean_marketplace,
            name_en=clean_name_en,
            name_vi=clean_name_vi,
            rule_description_en=clean_desc_en,
            rule_description_vi=clean_desc_vi,
            version=clean_version,
            aspect_ratio=clean_ratio,
            width=clean_w,
            height=clean_h,
            formats=clean_formats,
            background_rgb=clean_bg,
            subject_area_ratio=clean_subject_ratio,
            safe_zone=clean_safe_zone,
            editable=existing.editable,
            is_system=existing.is_system,
            created_at=existing.created_at,
            updated_at=utc_now_iso(),
        )
        return self._repo.update_preset(updated)

    def delete_preset(self, preset_id: str) -> None:
        existing = self.get_preset(preset_id)
        if existing.is_system:
            raise ForbiddenError(f"System preset '{preset_id}' cannot be deleted")
        self._repo.delete_preset(preset_id)

    def reset_preset(self, preset_id: str) -> MarketplacePreset:
        existing = self.get_preset(preset_id)
        if not existing.is_system or preset_id not in self._system_by_id:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Preset '{preset_id}' is not a system preset and cannot be reset",
                status_code=400,
            )
        canonical = self._system_by_id[preset_id]
        now = utc_now_iso()
        restored = MarketplacePreset(
            id=canonical.id,
            marketplace=canonical.marketplace,
            name_en=canonical.name_en,
            name_vi=canonical.name_vi,
            rule_description_en=canonical.rule_description_en,
            rule_description_vi=canonical.rule_description_vi,
            version=canonical.version,
            aspect_ratio=canonical.aspect_ratio,
            width=canonical.width,
            height=canonical.height,
            formats=canonical.formats,
            background_rgb=canonical.background_rgb,
            subject_area_ratio=canonical.subject_area_ratio,
            safe_zone=canonical.safe_zone,
            editable=canonical.editable,
            is_system=canonical.is_system,
            created_at=existing.created_at or now,
            updated_at=now,
        )
        return self._repo.update_preset(restored)
