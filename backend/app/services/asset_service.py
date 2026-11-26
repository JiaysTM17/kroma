from __future__ import annotations

import hashlib

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.core.ids import new_id, utc_now_iso
from app.core.security import ALLOWED_MIME_TO_EXT, validate_and_inspect_image
from app.domain.enums import AssetKind
from app.domain.models import Asset
from app.storage.ports import BlobStorePort, DatabasePort


class AssetService:
    def __init__(
        self,
        repo: DatabasePort,
        blob_store: BlobStorePort,
        settings: Settings,
    ) -> None:
        self._repo = repo
        self._blob_store = blob_store
        self._settings = settings

    def upload_asset(
        self,
        project_id: str,
        filename: str,
        content_type: str | None,
        data: bytes,
    ) -> Asset:
        project = self._repo.get_project(project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' not found")

        validated = validate_and_inspect_image(
            data=data,
            filename=filename,
            declared_content_type=content_type,
            max_bytes=self._settings.max_upload_bytes,
            max_pixels=self._settings.max_image_pixels,
            max_dimension=self._settings.max_image_dimension,
        )

        sha256 = hashlib.sha256(data).hexdigest()
        existing = self._repo.find_asset_by_hash(project_id, sha256)
        if existing is not None:
            return existing

        ext = ALLOWED_MIME_TO_EXT[validated.mime_type.value]
        storage_key = f"originals/{sha256[:2]}/{sha256}{ext}"
        stored_blob = self._blob_store.put_immutable(storage_key, data)

        asset = Asset(
            id=new_id(),
            project_id=project_id,
            kind=AssetKind.ORIGINAL,
            filename=validated.safe_filename,
            mime_type=validated.mime_type,
            sha256=stored_blob.sha256,
            byte_size=stored_blob.byte_size,
            width=validated.width,
            height=validated.height,
            exif_orientation=validated.exif_orientation,
            storage_key=stored_blob.storage_key,
            is_readonly=stored_blob.is_readonly,
            created_at=utc_now_iso(),
        )
        return self._repo.create_asset(asset)

    def list_project_assets(self, project_id: str) -> list[Asset]:
        project = self._repo.get_project(project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' not found")
        return self._repo.list_project_assets(project_id)

    def download_asset_file(self, asset_id: str) -> tuple[Asset, bytes]:
        asset = self._repo.get_asset(asset_id)
        if asset is None:
            raise NotFoundError(f"Asset '{asset_id}' not found")
        raw_bytes = self._blob_store.get_bytes(asset.storage_key)
        return asset, raw_bytes
