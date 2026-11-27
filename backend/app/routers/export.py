from __future__ import annotations

import uuid
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import get_settings
from app.core.config import Settings
from app.core.security import assert_safe_relative_path

from ..models.export import BatchExportRequest, BatchExportResponse

router = APIRouter(prefix="/export", tags=["Batch Export"])


@router.post("/batch", response_model=BatchExportResponse)
def trigger_batch_export(
    data: BatchExportRequest,
    settings: Settings = Depends(get_settings),
):
    export_id = f"exp_{uuid.uuid4().hex[:12]}"
    zip_filename = f"{export_id}.zip"
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    zip_path = assert_safe_relative_path(zip_filename, settings.exports_dir)

    with zipfile.ZipFile(str(zip_path), "w", compression=zipfile.ZIP_DEFLATED) as z:
        manifest_content = (
            f"KROMA Batch Export Manifest\n"
            f"Export ID: {export_id}\n"
            f"Project ID: {data.project_id}\n"
            f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n"
            f"Total Recipes: {len(data.recipes)}\n"
        )
        z.writestr("manifest.txt", manifest_content)

        for idx, recipe in enumerate(data.recipes, start=1):
            sample_name = f"image_{idx}_{recipe.preset_id}.{recipe.format.lower()}"
            z.writestr(sample_name, b"KROMA_SAMPLE_IMAGE_DATA")

    return BatchExportResponse(
        export_id=export_id,
        total_images=len(data.recipes),
        download_url=f"/api/v1/export/download/{export_id}",
        status="completed",
    )


@router.get("/download/{export_id}")
def download_export_zip(
    export_id: str,
    settings: Settings = Depends(get_settings),
):
    zip_filename = f"{export_id}.zip"
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    zip_path = assert_safe_relative_path(zip_filename, settings.exports_dir)
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="Gói tải về không tồn tại hoặc đã hết hạn")
    return FileResponse(
        path=str(zip_path),
        filename=zip_filename,
        media_type="application/zip",
    )
