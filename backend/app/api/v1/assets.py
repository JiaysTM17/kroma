from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from pydantic import BaseModel

from app.api.deps import get_asset_service, get_settings
from app.core.config import Settings
from app.core.errors import PayloadTooLargeError, ValidationAppError
from app.domain.models import Asset
from app.services.asset_service import AssetService

router = APIRouter(tags=["assets"])


class AssetResponse(BaseModel):
    id: str
    asset_id: str
    project_id: str
    kind: str
    parent_asset_id: str | None
    variant: str
    filename: str
    mime_type: str
    sha256: str
    byte_size: int
    width: int
    height: int
    exif_orientation: int
    is_readonly: bool
    metadata: dict[str, Any]
    file_url: str
    created_at: str
    updated_at: str

    @classmethod
    def from_domain(cls, asset: Asset) -> AssetResponse:
        return cls(
            id=asset.id,
            asset_id=asset.id,
            project_id=asset.project_id,
            kind=asset.kind.value,
            parent_asset_id=asset.parent_asset_id,
            variant=asset.variant,
            filename=asset.filename,
            mime_type=asset.mime_type.value,
            sha256=asset.sha256,
            byte_size=asset.byte_size,
            width=asset.width,
            height=asset.height,
            exif_orientation=asset.exif_orientation,
            is_readonly=asset.is_readonly,
            metadata=dict(asset.metadata),
            file_url=f"/v1/assets/{asset.id}/file",
            created_at=asset.created_at,
            updated_at=asset.updated_at or asset.created_at,
        )


class AssetListResponse(BaseModel):
    assets: list[AssetResponse]
    total: int


class UpdateAssetRequest(BaseModel):
    filename: str | None = None
    variant: str | None = None
    metadata: dict[str, Any] | None = None


class DeleteAssetResponse(BaseModel):
    deleted: bool
    asset_id: str


@router.post(
    "/projects/{project_id}/assets",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_project_asset(
    project_id: str,
    file: UploadFile = File(...),
    kind: str = Form(default="original"),
    parent_asset_id: str | None = Form(default=None),
    variant: str = Form(default="default"),
    metadata_json: str = Form(default="{}"),
    asset_service: AssetService = Depends(get_asset_service),
    settings: Settings = Depends(get_settings),
) -> AssetResponse:
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
        kind=kind,
        parent_asset_id=parent_asset_id,
        variant=variant,
        metadata_json=metadata_json,
    )
    return AssetResponse.from_domain(asset)


@router.get("/projects/{project_id}/assets", response_model=AssetListResponse)
def list_project_assets(
    project_id: str,
    kind: str | None = Query(default=None),
    parent_asset_id: str | None = Query(default=None),
    asset_service: AssetService = Depends(get_asset_service),
) -> AssetListResponse:
    assets = asset_service.list_project_assets(
        project_id,
        kind=kind,
        parent_asset_id=parent_asset_id,
    )
    return AssetListResponse(
        assets=[AssetResponse.from_domain(asset) for asset in assets],
        total=len(assets),
    )


@router.get("/assets/{asset_id}", response_model=AssetResponse)
def get_asset(
    asset_id: str,
    asset_service: AssetService = Depends(get_asset_service),
) -> AssetResponse:
    asset = asset_service.get_asset(asset_id)
    return AssetResponse.from_domain(asset)


@router.patch("/assets/{asset_id}", response_model=AssetResponse)
def update_asset(
    asset_id: str,
    body: UpdateAssetRequest,
    asset_service: AssetService = Depends(get_asset_service),
) -> AssetResponse:
    asset = asset_service.update_asset(
        asset_id,
        filename=body.filename,
        variant=body.variant,
        metadata=body.metadata,
        fields_set=set(body.model_fields_set),
    )
    return AssetResponse.from_domain(asset)


@router.delete("/assets/{asset_id}", response_model=DeleteAssetResponse)
def delete_asset(
    asset_id: str,
    asset_service: AssetService = Depends(get_asset_service),
) -> DeleteAssetResponse:
    asset_service.delete_asset(asset_id)
    return DeleteAssetResponse(deleted=True, asset_id=asset_id)


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
