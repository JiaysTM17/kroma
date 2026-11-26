import uuid
import zipfile
import io
import os
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from ..models.export import BatchExportRequest, BatchExportResponse
from ..config import EXPORTS_DIR

router = APIRouter(prefix="/export", tags=["Batch Export"])

@router.post("/batch", response_model=BatchExportResponse)
def trigger_batch_export(data: BatchExportRequest):
    export_id = f"exp_{uuid.uuid4().hex[:12]}"
    zip_filename = f"{export_id}.zip"
    zip_path = EXPORTS_DIR / zip_filename
    
    # Create empty/sample zip archive
    with zipfile.ZipFile(str(zip_path), 'w', compression=zipfile.ZIP_DEFLATED) as z:
        manifest_content = f"KROMA Batch Export Manifest\nExport ID: {export_id}\nProject ID: {data.project_id}\nTimestamp: {datetime.now(timezone.utc).isoformat()}\nTotal Recipes: {len(data.recipes)}\n"
        z.writestr("manifest.txt", manifest_content)
        
        # Add a placeholder sample image per recipe
        for idx, recipe in enumerate(data.recipes, start=1):
            sample_name = f"image_{idx}_{recipe.preset_id}.{recipe.format.lower()}"
            z.writestr(sample_name, b"KROMA_SAMPLE_IMAGE_DATA")
            
    return BatchExportResponse(
        export_id=export_id,
        total_images=len(data.recipes),
        download_url=f"/api/v1/export/download/{export_id}",
        status="completed"
    )

@router.get("/download/{export_id}")
def download_export_zip(export_id: str):
    zip_filename = f"{export_id}.zip"
    zip_path = EXPORTS_DIR / zip_filename
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="Gói tải về không tồn tại hoặc đã hết hạn")
    return FileResponse(
        path=str(zip_path),
        filename=zip_filename,
        media_type="application/zip"
    )
