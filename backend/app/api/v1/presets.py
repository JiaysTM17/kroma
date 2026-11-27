from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, BeforeValidator, Field

from app.api.deps import get_preset_service
from app.domain.models import MarketplacePreset
from app.services.preset_service import PresetService

router = APIRouter(prefix="/presets", tags=["presets"])


def _reject_bool(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("Boolean value is not allowed for numeric field")
    return value


NoBoolInt = Annotated[int, BeforeValidator(_reject_bool)]
NoBoolFloat = Annotated[float, BeforeValidator(_reject_bool)]


class SafeZonePayload(BaseModel):
    top: NoBoolFloat
    right: NoBoolFloat
    bottom: NoBoolFloat
    left: NoBoolFloat


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
    rule_description_en: str
    rule_description_vi: str
    version: str
    aspect_ratio: str
    width: int
    height: int
    formats: list[str]
    background_rgb: list[int] | None
    subject_area_ratio: float | None
    safe_zone: SafeZoneResponse | None
    is_system: bool
    editable: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_domain(cls, preset: MarketplacePreset) -> MarketplacePresetResponse:
        return cls(
            id=preset.id,
            marketplace=preset.marketplace.value,
            name_en=preset.name_en,
            name_vi=preset.name_vi,
            rule_description_en=preset.rule_description_en,
            rule_description_vi=preset.rule_description_vi,
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
            is_system=preset.is_system,
            editable=preset.editable,
            created_at=preset.created_at,
            updated_at=preset.updated_at,
        )


class PresetListResponse(BaseModel):
    presets: list[MarketplacePresetResponse]
    total: int


class CreatePresetRequest(BaseModel):
    id: str | None = None
    marketplace: str = "custom"
    name_en: str
    name_vi: str | None = None
    rule_description_en: str = ""
    rule_description_vi: str = ""
    version: str = "1.0.0"
    width: NoBoolInt
    height: NoBoolInt
    aspect_ratio: str | None = None
    formats: list[str] = Field(default_factory=lambda: ["webp", "jpeg"])
    background_rgb: list[NoBoolInt] | None = None
    subject_area_ratio: NoBoolFloat | None = None
    safe_zone: SafeZonePayload | None = None


class UpdatePresetRequest(BaseModel):
    marketplace: str | None = None
    name_en: str | None = None
    name_vi: str | None = None
    rule_description_en: str | None = None
    rule_description_vi: str | None = None
    version: str | None = None
    width: NoBoolInt | None = None
    height: NoBoolInt | None = None
    aspect_ratio: str | None = None
    formats: list[str] | None = None
    background_rgb: list[NoBoolInt] | None = None
    subject_area_ratio: NoBoolFloat | None = None
    safe_zone: SafeZonePayload | None = None


class DeletePresetResponse(BaseModel):
    deleted: bool
    preset_id: str


@router.get("", response_model=PresetListResponse)
def list_presets(
    preset_service: PresetService = Depends(get_preset_service),
) -> PresetListResponse:
    presets = preset_service.list_presets()
    return PresetListResponse(
        presets=[MarketplacePresetResponse.from_domain(preset) for preset in presets],
        total=len(presets),
    )


@router.get("/{preset_id}", response_model=MarketplacePresetResponse)
def get_preset(
    preset_id: str,
    preset_service: PresetService = Depends(get_preset_service),
) -> MarketplacePresetResponse:
    preset = preset_service.get_preset(preset_id)
    return MarketplacePresetResponse.from_domain(preset)


@router.post("", response_model=MarketplacePresetResponse, status_code=status.HTTP_201_CREATED)
def create_preset(
    body: CreatePresetRequest,
    preset_service: PresetService = Depends(get_preset_service),
) -> MarketplacePresetResponse:
    preset = preset_service.create_preset(
        preset_id=body.id,
        marketplace=body.marketplace,
        name_en=body.name_en,
        name_vi=body.name_vi,
        rule_description_en=body.rule_description_en,
        rule_description_vi=body.rule_description_vi,
        version=body.version,
        width=body.width,
        height=body.height,
        aspect_ratio=body.aspect_ratio,
        formats=body.formats,
        background_rgb=body.background_rgb,
        subject_area_ratio=body.subject_area_ratio,
        safe_zone=body.safe_zone.model_dump() if body.safe_zone is not None else None,
    )
    return MarketplacePresetResponse.from_domain(preset)


@router.put("/{preset_id}", response_model=MarketplacePresetResponse)
def replace_preset(
    preset_id: str,
    body: UpdatePresetRequest,
    preset_service: PresetService = Depends(get_preset_service),
) -> MarketplacePresetResponse:
    updates = body.model_dump()
    if body.safe_zone is not None:
        updates["safe_zone"] = body.safe_zone.model_dump()
    preset = preset_service.update_preset(
        preset_id,
        fields_set=set(body.model_fields_set),
        **updates,
    )
    return MarketplacePresetResponse.from_domain(preset)


@router.patch("/{preset_id}", response_model=MarketplacePresetResponse)
def patch_preset(
    preset_id: str,
    body: UpdatePresetRequest,
    preset_service: PresetService = Depends(get_preset_service),
) -> MarketplacePresetResponse:
    updates = body.model_dump()
    if body.safe_zone is not None:
        updates["safe_zone"] = body.safe_zone.model_dump()
    preset = preset_service.update_preset(
        preset_id,
        fields_set=set(body.model_fields_set),
        **updates,
    )
    return MarketplacePresetResponse.from_domain(preset)


@router.delete("/{preset_id}", response_model=DeletePresetResponse)
def delete_preset(
    preset_id: str,
    preset_service: PresetService = Depends(get_preset_service),
) -> DeletePresetResponse:
    preset_service.delete_preset(preset_id)
    return DeletePresetResponse(deleted=True, preset_id=preset_id)


@router.post("/{preset_id}/reset", response_model=MarketplacePresetResponse)
def reset_preset(
    preset_id: str,
    preset_service: PresetService = Depends(get_preset_service),
) -> MarketplacePresetResponse:
    preset = preset_service.reset_preset(preset_id)
    return MarketplacePresetResponse.from_domain(preset)
