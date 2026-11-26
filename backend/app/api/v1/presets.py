from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_preset_service
from app.domain.models import MarketplacePreset
from app.services.preset_service import PresetService

router = APIRouter(prefix="/presets", tags=["presets"])


class SafeZoneResponse(BaseModel):
    top: float
    right: float
    bottom: float
    left: float


class MarketplacePresetResponse(BaseModel):
    id: str
    marketplace: str
    name_en: str
    name_vi: str
    version: str
    aspect_ratio: str
    width: int
    height: int
    formats: list[str]
    background_rgb: list[int] | None
    subject_area_ratio: float | None
    safe_zone: SafeZoneResponse | None
    editable: bool

    @classmethod
    def from_domain(cls, preset: MarketplacePreset) -> MarketplacePresetResponse:
        return cls(
            id=preset.id,
            marketplace=preset.marketplace.value,
            name_en=preset.name_en,
            name_vi=preset.name_vi,
            version=preset.version,
            aspect_ratio=preset.aspect_ratio,
            width=preset.width,
            height=preset.height,
            formats=list(preset.formats),
            background_rgb=list(preset.background_rgb) if preset.background_rgb is not None else None,
            subject_area_ratio=preset.subject_area_ratio,
            safe_zone=(
                SafeZoneResponse(
                    top=preset.safe_zone.top,
                    right=preset.safe_zone.right,
                    bottom=preset.safe_zone.bottom,
                    left=preset.safe_zone.left,
                )
                if preset.safe_zone is not None
                else None
            ),
            editable=preset.editable,
        )


class PresetListResponse(BaseModel):
    items: list[MarketplacePresetResponse]


@router.get("", response_model=PresetListResponse)
def list_presets(
    preset_service: PresetService = Depends(get_preset_service),
) -> PresetListResponse:
    presets = preset_service.list_presets()
    return PresetListResponse(
        items=[MarketplacePresetResponse.from_domain(preset) for preset in presets]
    )
