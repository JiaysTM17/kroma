from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_preset_service
from app.core.errors import NotFoundError
from app.domain.models import MarketplacePreset as DomainPreset
from app.services.preset_service import PresetService

from ..models.preset import MarketplacePreset

router = APIRouter(prefix="/presets", tags=["Marketplace Presets"])

LEGACY_MARKETPLACE_DISPLAY: dict[str, str] = {
    "shopee": "Shopee",
    "tiktok_shop": "TikTok Shop",
    "lazada": "Lazada",
    "amazon": "Amazon",
    "custom": "Custom",
}

LEGACY_PRESET_ID_ALIASES: dict[str, str] = {
    "shopee_square": "shopee_1_1",
    "tiktok_shop_feed": "tiktok_3_4",
    "tiktok_shop_square": "tiktok_1_1",
    "lazada_square": "lazada_1_1",
    "amazon_hero": "amazon_white_85",
}


def _to_legacy_model(
    preset: DomainPreset,
    override_id: str | None = None,
) -> MarketplacePreset:
    bg_color = (
        f"#{preset.background_rgb[0]:02X}{preset.background_rgb[1]:02X}{preset.background_rgb[2]:02X}"
        if preset.background_rgb is not None
        else "transparent"
    )
    return MarketplacePreset(
        id=override_id or preset.id,
        name=preset.name_en,
        marketplace=LEGACY_MARKETPLACE_DISPLAY.get(preset.marketplace.value, "Custom"),
        width=preset.width,
        height=preset.height,
        aspect_ratio=preset.aspect_ratio,
        bg_color=bg_color,
        subject_scale=preset.subject_area_ratio if preset.subject_area_ratio is not None else 0.9,
        format=(preset.formats[0] if preset.formats else "jpeg").upper(),
        description=preset.rule_description_vi or preset.rule_description_en or None,
    )


@router.get("", response_model=list[MarketplacePreset])
def list_presets(
    preset_service: PresetService = Depends(get_preset_service),
) -> list[MarketplacePreset]:
    presets = preset_service.list_presets()
    by_id = {preset.id: preset for preset in presets}
    result = [_to_legacy_model(preset) for preset in presets]
    for alias_id, canonical_id in LEGACY_PRESET_ID_ALIASES.items():
        if alias_id not in by_id and canonical_id in by_id:
            result.append(_to_legacy_model(by_id[canonical_id], override_id=alias_id))
    return result


@router.get("/{preset_id}", response_model=MarketplacePreset)
def get_preset(
    preset_id: str,
    preset_service: PresetService = Depends(get_preset_service),
) -> MarketplacePreset:
    try:
        preset = preset_service.get_preset(preset_id)
        return _to_legacy_model(preset)
    except NotFoundError:
        alias_target = LEGACY_PRESET_ID_ALIASES.get(preset_id)
        if alias_target is not None:
            try:
                target_preset = preset_service.get_preset(alias_target)
                return _to_legacy_model(target_preset, override_id=preset_id)
            except NotFoundError:
                pass
        raise HTTPException(status_code=404, detail="Preset không tồn tại")
