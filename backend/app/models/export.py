from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator


def _reject_bool(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("Boolean value is not allowed for numeric field")
    return value


NoBoolInt = Annotated[int, BeforeValidator(_reject_bool)]
NoBoolFloat = Annotated[float, BeforeValidator(_reject_bool)]


class ExportRecipe(BaseModel):
    preset_id: str
    format: str | None = "JPEG"
    quality: NoBoolInt = 90
    background_rgb: list[NoBoolInt] | None = None
    subject_area_ratio: NoBoolFloat | None = None
    include_shadow: bool = True
    watermark_text: str | None = None


class BatchExportRequest(BaseModel):
    project_id: str
    recipes: list[ExportRecipe]
    asset_ids: list[str] | None = None
    adjustments: dict[str, Any] | None = None
    prefer_ai_output: bool = True


class BatchExportResponse(BaseModel):
    export_id: str
    total_images: int
    download_url: str
    status: str
