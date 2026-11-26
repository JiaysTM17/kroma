from __future__ import annotations

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from pydantic import BaseModel

from app.api.deps import get_asset_service, get_settings
from app.core.config import Settings
from app.core.errors import PayloadTooLargeError, ValidationAppError
from app.services.asset_service import AssetService

router = APIRouter(tags=["assets"])


class AssetUploadResponse(BaseModel):
    asset_id: str
    project_id: str
    sha256: str
    filename: str
    mime_type: str
    width: int
    height: int
    byte_size: int
    exif_orientation: int
    is_readonly: bool
    created_at: str


@router.post(
    "/projects/{project_id}/assets",
    response_model=AssetUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_project_asset(
    project_id: str,
    file: UploadFile = File(...),
    asset_service: AssetService = Depends(get_asset_service),
    settings: Settings = Depends(get_settings),
) -> AssetUploadResponse:
    if not file.filename:
        raise ValidationAppError("Uploaded file must include a filename")

    raw_bytes = await file.read(settings.max_upload_bytes + 1)
    if len(raw_bytes) > settings.max_upload_bytes:
        raise PayloadTooLargeError(
            f"Uploaded file exceeds maximum allowed size of {settings.max_upload_bytes} bytes"
        )

    asset = asset_service.upload_asset(
        project_id=project_id,
        filename=file.filename,
        content_type=file.content_type,
        data=raw_bytes,
    )
    return AssetUploadResponse(
        asset_id=asset.id,
        project_id=asset.project_id,
        sha256=asset.sha256,
        filename=asset.filename,
        mime_type=asset.mime_type.value,
        width=asset.width,
        height=asset.height,
        byte_size=asset.byte_size,
        exif_orientation=asset.exif_orientation,
        is_readonly=asset.is_readonly,
        created_at=asset.created_at,
    )


@router.get("/assets/{asset_id}/file")
def download_asset_file(
    asset_id: str,
    asset_service: AssetService = Depends(get_asset_service),
) -> Response:
    asset, raw_bytes = asset_service.download_asset_file(asset_id)
    return Response(
        content=raw_bytes,
        media_type=asset.mime_type.value,
        headers={
            "ETag": f'"{asset.sha256}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=31536000, immutable",
            "Cross-Origin-Resource-Policy": "cross-origin",
        },
    )
