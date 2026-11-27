from __future__ import annotations

import hashlib
import os
from typing import Any

from app.core.config import Settings
from app.core.errors import NotFoundError, ValidationAppError
from app.core.ids import new_id, utc_now_iso
from app.core.security import (
    ALLOWED_MIME_TO_EXT,
    EXT_TO_EXPECTED_MIME,
    sanitize_upload_filename,
    validate_and_inspect_image,
)
from app.domain.enums import AssetKind
from app.domain.models import Asset
from app.domain.rules import (
    parse_metadata_json,
    validate_asset_metadata,
    validate_variant_name,
)
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

    @staticmethod
    def _parse_kind(kind: str | AssetKind) -> AssetKind:
        if isinstance(kind, AssetKind):
            return kind
        if not isinstance(kind, str):
            raise ValidationAppError("Asset kind must be a string")
        cleaned = kind.strip().lower()
        try:
            return AssetKind(cleaned)
        except ValueError as exc:
            allowed = ", ".join(k.value for k in AssetKind)
            raise ValidationAppError(
                f"Invalid asset kind '{kind}'; expected one of: {allowed}"
            ) from exc

    def upload_asset(
        self,
        project_id: str,
        filename: str,
        content_type: str | None,
        data: bytes,
        *,
        kind: str | AssetKind = AssetKind.ORIGINAL,
        parent_asset_id: str | None = None,
        variant: str | None = "default",
        metadata_json: str | None = "{}",
    ) -> Asset:
        project = self._repo.get_project(project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' not found")

        asset_kind = self._parse_kind(kind)
        try:
            clean_variant = validate_variant_name(variant, allow_default=True)
            clean_metadata = parse_metadata_json(metadata_json)
        except ValueError as exc:
            raise ValidationAppError(str(exc)) from exc

        clean_parent_id: str | None = None
        if parent_asset_id is not None and parent_asset_id.strip():
            clean_parent_id = parent_asset_id.strip()
            if asset_kind == AssetKind.ORIGINAL:
                raise ValidationAppError("Original assets cannot reference a parent_asset_id")
            parent = self._repo.get_asset(clean_parent_id)
            if parent is None:
                raise NotFoundError(f"Parent asset '{clean_parent_id}' not found")
            if parent.project_id != project_id:
                raise ValidationAppError("Parent asset belongs to a different project")

        validated = validate_and_inspect_image(
            data=data,
            filename=filename,
            declared_content_type=content_type,
            max_bytes=self._settings.max_upload_bytes,
            max_pixels=self._settings.max_image_pixels,
            max_dimension=self._settings.max_image_dimension,
        )

        sha256 = hashlib.sha256(data).hexdigest()
        if asset_kind == AssetKind.ORIGINAL:
            existing = self._repo.find_asset_by_hash(
                project_id,
                sha256,
                kind=AssetKind.ORIGINAL,
                variant=clean_variant,
                parent_asset_id=None,
            )
            if existing is not None:
                return existing

        ext = ALLOWED_MIME_TO_EXT[validated.mime_type.value]
        if asset_kind == AssetKind.ORIGINAL:
            storage_key = f"originals/{sha256[:2]}/{sha256}{ext}"
            stored_blob = self._blob_store.put_immutable(storage_key, data)
        else:
            storage_key = f"derived/{asset_kind.value}/{sha256[:2]}/{sha256}{ext}"
            stored_blob = self._blob_store.put_derived(storage_key, data)

        now = utc_now_iso()
        asset = Asset(
            id=new_id(),
            project_id=project_id,
            kind=asset_kind,
            filename=validated.safe_filename,
            mime_type=validated.mime_type,
            sha256=stored_blob.sha256,
            byte_size=stored_blob.byte_size,
            width=validated.width,
            height=validated.height,
            exif_orientation=validated.exif_orientation,
            storage_key=stored_blob.storage_key,
            is_readonly=stored_blob.is_readonly,
            created_at=now,
            parent_asset_id=clean_parent_id,
            variant=clean_variant,
            metadata=clean_metadata,
            updated_at=now,
        )
        return self._repo.create_asset(asset)

    def get_asset(self, asset_id: str) -> Asset:
        asset = self._repo.get_asset(asset_id)
        if asset is None:
            raise NotFoundError(f"Asset '{asset_id}' not found")
        return asset

    def list_project_assets(
        self,
        project_id: str,
        *,
        kind: str | AssetKind | None = None,
        parent_asset_id: str | None = None,
    ) -> list[Asset]:
        project = self._repo.get_project(project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' not found")
        parsed_kind = self._parse_kind(kind) if kind is not None and str(kind).strip() else None
        clean_parent_id = (
            parent_asset_id.strip()
            if parent_asset_id is not None and parent_asset_id.strip()
            else None
        )
        return self._repo.list_project_assets(
            project_id,
            kind=parsed_kind,
            parent_asset_id=clean_parent_id,
        )

    def update_asset(
        self,
        asset_id: str,
        *,
        filename: str | None = None,
        variant: str | None = None,
        metadata: dict[str, Any] | None = None,
        fields_set: set[str] | None = None,
    ) -> Asset:
        existing = self.get_asset(asset_id)
        supplied = fields_set if fields_set is not None else {
            k
            for k, v in (
                ("filename", filename),
                ("variant", variant),
                ("metadata", metadata),
            )
            if v is not None
        }

        next_filename = existing.filename
        if "filename" in supplied:
            if filename is None or not str(filename).strip():
                raise ValidationAppError("filename cannot be empty")
            next_filename = sanitize_upload_filename(filename)
            ext = os.path.splitext(next_filename)[1].lower()
            expected_mime = EXT_TO_EXPECTED_MIME.get(ext)
            if not ext or expected_mime != existing.mime_type.value:
                raise ValidationAppError(
                    f"Filename extension '{ext or '(none)'}' does not match asset MIME type '{existing.mime_type.value}'"
                )

        next_variant = existing.variant
        if "variant" in supplied:
            try:
                next_variant = validate_variant_name(variant, allow_default=False)
            except ValueError as exc:
                raise ValidationAppError(str(exc)) from exc

        next_metadata = existing.metadata
        if "metadata" in supplied:
            if metadata is None:
                raise ValidationAppError("metadata must be a JSON object")
            try:
                next_metadata = validate_asset_metadata(metadata)
            except ValueError as exc:
                raise ValidationAppError(str(exc)) from exc

        updated = Asset(
            id=existing.id,
            project_id=existing.project_id,
            kind=existing.kind,
            filename=next_filename,
            mime_type=existing.mime_type,
            sha256=existing.sha256,
            byte_size=existing.byte_size,
            width=existing.width,
            height=existing.height,
            exif_orientation=existing.exif_orientation,
            storage_key=existing.storage_key,
            is_readonly=existing.is_readonly,
            created_at=existing.created_at,
            parent_asset_id=existing.parent_asset_id,
            variant=next_variant,
            metadata=next_metadata,
            updated_at=utc_now_iso(),
        )
        return self._repo.update_asset(updated)

    def delete_asset(self, asset_id: str) -> Asset:
        deleted = self._repo.delete_asset(asset_id)
        if deleted is None:
            raise NotFoundError(f"Asset '{asset_id}' not found")
        if self._repo.count_storage_key_refs(deleted.storage_key) == 0:
            self._blob_store.delete_blob(deleted.storage_key)
        return deleted

    def download_asset_file(self, asset_id: str) -> tuple[Asset, bytes]:
        asset = self._repo.get_asset(asset_id)
        if asset is None:
            raise NotFoundError(f"Asset '{asset_id}' not found")
        raw_bytes = self._blob_store.get_bytes(asset.storage_key)
        return asset, raw_bytes
