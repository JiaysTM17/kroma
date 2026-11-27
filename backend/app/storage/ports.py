from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.domain.enums import AssetKind, BatchStatus, ProofingStatus
from app.domain.models import (
    Asset,
    BatchJob,
    BatchJobItem,
    MarketplacePreset,
    Project,
    ProjectState,
    ProofingComment,
    ProofingEvent,
    ProofingSession,
)


@dataclass(frozen=True)
class StoredBlob:
    storage_key: str
    sha256: str
    byte_size: int
    is_readonly: bool


@dataclass(frozen=True)
class DeletedProjectArtifacts:
    storage_keys: list[str]
    batch_job_ids: list[str]
    zip_filenames: list[str]


class DatabasePort(Protocol):
    def initialize(self) -> None: ...
    def ping(self) -> bool: ...
    def close(self) -> None: ...
    def create_project(self, project: Project, initial_state: ProjectState) -> Project: ...
    def list_projects(self) -> list[Project]: ...
    def get_project(self, project_id: str) -> Project | None: ...
    def update_project_name(self, project_id: str, name: str, updated_at: str) -> Project | None: ...
    def delete_project(self, project_id: str) -> list[str] | None: ...
    def delete_project_with_artifacts(
        self, project_id: str
    ) -> DeletedProjectArtifacts | None: ...
    def get_project_state(self, project_id: str) -> ProjectState | None: ...
    def put_project_state(
        self, state: ProjectState, expected_revision_id: str | None = None
    ) -> ProjectState: ...
    def create_asset(self, asset: Asset) -> Asset: ...
    def get_asset(self, asset_id: str) -> Asset | None: ...
    def find_asset_by_hash(
        self,
        project_id: str,
        sha256: str,
        *,
        kind: AssetKind | None = None,
        variant: str | None = None,
        parent_asset_id: str | None = None,
    ) -> Asset | None: ...
    def list_project_assets(
        self,
        project_id: str,
        *,
        kind: AssetKind | None = None,
        parent_asset_id: str | None = None,
    ) -> list[Asset]: ...
    def update_asset(self, asset: Asset) -> Asset: ...
    def delete_asset(self, asset_id: str) -> Asset | None: ...
    def count_storage_key_refs(self, storage_key: str) -> int: ...
    def list_presets(self) -> list[MarketplacePreset]: ...
    def get_preset(self, preset_id: str) -> MarketplacePreset | None: ...
    def create_preset(self, preset: MarketplacePreset) -> MarketplacePreset: ...
    def update_preset(self, preset: MarketplacePreset) -> MarketplacePreset: ...
    def delete_preset(self, preset_id: str) -> bool: ...
    def seed_system_presets(
        self, presets: tuple[MarketplacePreset, ...] | list[MarketplacePreset]
    ) -> None: ...

    # Batch jobs
    def create_batch_job(self, job: BatchJob, items: list[BatchJobItem]) -> BatchJob: ...
    def get_batch_job(self, job_id: str) -> tuple[BatchJob, list[BatchJobItem]] | None: ...
    def list_project_batch_jobs(self, project_id: str) -> list[BatchJob]: ...
    def list_unfinished_batch_jobs(self) -> list[BatchJob]: ...
    def claim_batch_job_running(self, job_id: str, started_at: str) -> BatchJob | None: ...
    def reset_running_batch_items_to_pending(self, job_id: str, updated_at: str) -> None: ...
    def update_batch_job_item(self, item: BatchJobItem) -> BatchJobItem: ...
    def request_batch_job_cancel(
        self, job_id: str, updated_at: str
    ) -> tuple[BatchJob, list[BatchJobItem]] | None: ...
    def finalize_batch_job(
        self,
        job_id: str,
        *,
        status: BatchStatus,
        zip_filename: str | None,
        error_message: str | None,
        completed_at: str | None,
        updated_at: str,
        cancel_pending_items: bool = False,
    ) -> tuple[BatchJob, list[BatchJobItem]] | None: ...
    def reset_batch_job_for_retry(
        self, job_id: str, updated_at: str
    ) -> tuple[BatchJob, list[BatchJobItem]] | None: ...

    # Proofing
    def create_proofing_session(
        self, session: ProofingSession, initial_event: ProofingEvent
    ) -> ProofingSession: ...
    def get_proofing_session(self, session_id: str) -> ProofingSession | None: ...
    def list_project_proofing_sessions(self, project_id: str) -> list[ProofingSession]: ...
    def add_proofing_comment(
        self,
        session_id: str,
        comment: ProofingComment,
        *,
        new_status: ProofingStatus,
        approved_by: str | None,
        approved_at: str | None,
        updated_at: str,
        event: ProofingEvent,
    ) -> ProofingSession: ...
    def get_proofing_comment(
        self, session_id: str, comment_id: str
    ) -> ProofingComment | None: ...
    def update_proofing_comment(
        self,
        comment: ProofingComment,
        *,
        updated_at: str,
        event: ProofingEvent,
    ) -> ProofingComment: ...
    def delete_proofing_comment(
        self,
        session_id: str,
        comment_id: str,
        *,
        updated_at: str,
        event: ProofingEvent,
    ) -> bool: ...
    def apply_proofing_decision(
        self,
        session_id: str,
        *,
        new_status: ProofingStatus,
        approved_by: str | None,
        approved_at: str | None,
        revoked_at: str | None,
        updated_at: str,
        event: ProofingEvent,
    ) -> ProofingSession: ...


class BlobStorePort(Protocol):
    def initialize(self) -> None: ...
    def put_immutable(self, key: str, data: bytes) -> StoredBlob: ...
    def put_derived(self, key: str, data: bytes) -> StoredBlob: ...
    def get_bytes(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete_blob(self, key: str) -> bool: ...
