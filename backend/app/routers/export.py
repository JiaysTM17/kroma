from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse

from app.api.deps import get_batch_worker, get_settings
from app.core.config import Settings
from app.core.errors import NotFoundError
from app.core.security import assert_safe_relative_path
from app.domain.models import BatchRecipeInput
from app.services.batch_worker import BatchWorkerService, validate_safe_archive_id

from ..models.export import BatchExportRequest, BatchExportResponse

router = APIRouter(prefix="/export", tags=["Batch Export"])


@router.post("/batch", response_model=BatchExportResponse)
def trigger_batch_export(
    data: BatchExportRequest,
    request: Request,
    batch_worker: BatchWorkerService = Depends(get_batch_worker),
) -> BatchExportResponse:
    recipes = [
        BatchRecipeInput(
            preset_id=r.preset_id,
            format=r.format,
            quality=r.quality,
            background_rgb=tuple(r.background_rgb) if r.background_rgb is not None else None,  # type: ignore[arg-type]
            subject_area_ratio=r.subject_area_ratio,
            include_shadow=r.include_shadow,
            watermark_text=r.watermark_text,
        )
        for r in data.recipes
    ]
    export_id, total_images, _zip_filename = batch_worker.execute_sync_export(
        project_id=data.project_id,
        recipes=recipes,
        asset_ids=data.asset_ids,
        adjustments=data.adjustments,
        prefer_ai_output=data.prefer_ai_output,
    )
    prefix = "/v1" if request.url.path.startswith("/v1/") else "/api/v1"
    return BatchExportResponse(
        export_id=export_id,
        total_images=total_images,
        download_url=f"{prefix}/export/download/{export_id}",
        status="completed",
    )


@router.get("/download/{export_id:path}")
def download_export_zip(
    export_id: str,
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    clean_id = validate_safe_archive_id(export_id, "export_id")
    zip_filename = f"{clean_id}.zip"
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    zip_path = assert_safe_relative_path(zip_filename, settings.exports_dir)
    if not zip_path.is_file():
        raise NotFoundError("Gói tải về không tồn tại hoặc đã hết hạn")
    return FileResponse(
        path=str(zip_path),
        filename=zip_filename,
        media_type="application/zip",
    )
