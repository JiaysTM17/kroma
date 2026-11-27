from __future__ import annotations

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
from app.storage.ports import DeletedProjectArtifacts

_STUB_MESSAGE = (
    "PostgreSQL 16 adapter is a clean M1 interface stub; "
    "use KROMA_DATABASE_BACKEND=sqlite for local execution."
)


class PostgresInterface:
    def __init__(self, dsn: str | None = None) -> None:
        if dsn is not None and dsn.strip():
            if not (dsn.startswith("postgresql://") or dsn.startswith("postgres://")):
                raise ValueError("Invalid PostgreSQL DSN scheme; expected postgresql:// or postgres://")
        self._dsn = dsn

    def initialize(self) -> None:
        raise NotImplementedError(_STUB_MESSAGE)

    def ping(self) -> bool:
        raise NotImplementedError(_STUB_MESSAGE)

    def close(self) -> None:
        return None

    def create_project(self, project: Project, initial_state: ProjectState) -> Project:
        raise NotImplementedError(_STUB_MESSAGE)

    def list_projects(self) -> list[Project]:
        raise NotImplementedError(_STUB_MESSAGE)

    def get_project(self, project_id: str) -> Project | None:
        raise NotImplementedError(_STUB_MESSAGE)

    def update_project_name(self, project_id: str, name: str, updated_at: str) -> Project | None:
        raise NotImplementedError(_STUB_MESSAGE)

    def delete_project(self, project_id: str) -> list[str] | None:
        raise NotImplementedError(_STUB_MESSAGE)

    def delete_project_with_artifacts(
        self, project_id: str
    ) -> DeletedProjectArtifacts | None:
        raise NotImplementedError(_STUB_MESSAGE)

    def get_project_state(self, project_id: str) -> ProjectState | None:
        raise NotImplementedError(_STUB_MESSAGE)

    def put_project_state(
        self, state: ProjectState, expected_revision_id: str | None = None
    ) -> ProjectState:
        raise NotImplementedError(_STUB_MESSAGE)

    def create_asset(self, asset: Asset) -> Asset:
        raise NotImplementedError(_STUB_MESSAGE)

    def get_asset(self, asset_id: str) -> Asset | None:
        raise NotImplementedError(_STUB_MESSAGE)

    def find_asset_by_hash(
        self,
        project_id: str,
        sha256: str,
        *,
        kind: AssetKind | None = None,
        variant: str | None = None,
        parent_asset_id: str | None = None,
    ) -> Asset | None:
        raise NotImplementedError(_STUB_MESSAGE)

    def list_project_assets(
        self,
        project_id: str,
        *,
        kind: AssetKind | None = None,
        parent_asset_id: str | None = None,
    ) -> list[Asset]:
        raise NotImplementedError(_STUB_MESSAGE)

    def update_asset(self, asset: Asset) -> Asset:
        raise NotImplementedError(_STUB_MESSAGE)

    def delete_asset(self, asset_id: str) -> Asset | None:
        raise NotImplementedError(_STUB_MESSAGE)

    def count_storage_key_refs(self, storage_key: str) -> int:
        raise NotImplementedError(_STUB_MESSAGE)

    def list_presets(self) -> list[MarketplacePreset]:
        raise NotImplementedError(_STUB_MESSAGE)

    def get_preset(self, preset_id: str) -> MarketplacePreset | None:
        raise NotImplementedError(_STUB_MESSAGE)

    def create_preset(self, preset: MarketplacePreset) -> MarketplacePreset:
        raise NotImplementedError(_STUB_MESSAGE)

    def update_preset(self, preset: MarketplacePreset) -> MarketplacePreset:
        raise NotImplementedError(_STUB_MESSAGE)

    def delete_preset(self, preset_id: str) -> bool:
        raise NotImplementedError(_STUB_MESSAGE)

    def seed_system_presets(
        self, presets: tuple[MarketplacePreset, ...] | list[MarketplacePreset]
    ) -> None:
        raise NotImplementedError(_STUB_MESSAGE)

    def create_batch_job(self, job: BatchJob, items: list[BatchJobItem]) -> BatchJob:
        raise NotImplementedError(_STUB_MESSAGE)

    def get_batch_job(self, job_id: str) -> tuple[BatchJob, list[BatchJobItem]] | None:
        raise NotImplementedError(_STUB_MESSAGE)

    def list_project_batch_jobs(self, project_id: str) -> list[BatchJob]:
        raise NotImplementedError(_STUB_MESSAGE)

    def list_unfinished_batch_jobs(self) -> list[BatchJob]:
        raise NotImplementedError(_STUB_MESSAGE)

    def claim_batch_job_running(self, job_id: str, started_at: str) -> BatchJob | None:
        raise NotImplementedError(_STUB_MESSAGE)

    def reset_running_batch_items_to_pending(self, job_id: str, updated_at: str) -> None:
        raise NotImplementedError(_STUB_MESSAGE)

    def update_batch_job_item(self, item: BatchJobItem) -> BatchJobItem:
        raise NotImplementedError(_STUB_MESSAGE)

    def request_batch_job_cancel(
        self, job_id: str, updated_at: str
    ) -> tuple[BatchJob, list[BatchJobItem]] | None:
        raise NotImplementedError(_STUB_MESSAGE)

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
    ) -> tuple[BatchJob, list[BatchJobItem]] | None:
        raise NotImplementedError(_STUB_MESSAGE)

    def reset_batch_job_for_retry(
        self, job_id: str, updated_at: str
    ) -> tuple[BatchJob, list[BatchJobItem]] | None:
        raise NotImplementedError(_STUB_MESSAGE)

    def create_proofing_session(
        self, session: ProofingSession, initial_event: ProofingEvent
    ) -> ProofingSession:
        raise NotImplementedError(_STUB_MESSAGE)

    def get_proofing_session(self, session_id: str) -> ProofingSession | None:
        raise NotImplementedError(_STUB_MESSAGE)

    def list_project_proofing_sessions(self, project_id: str) -> list[ProofingSession]:
        raise NotImplementedError(_STUB_MESSAGE)

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
    ) -> ProofingSession:
        raise NotImplementedError(_STUB_MESSAGE)

    def get_proofing_comment(
        self, session_id: str, comment_id: str
    ) -> ProofingComment | None:
        raise NotImplementedError(_STUB_MESSAGE)

    def update_proofing_comment(
        self,
        comment: ProofingComment,
        *,
        updated_at: str,
        event: ProofingEvent,
    ) -> ProofingComment:
        raise NotImplementedError(_STUB_MESSAGE)

    def delete_proofing_comment(
        self,
        session_id: str,
        comment_id: str,
        *,
        updated_at: str,
        event: ProofingEvent,
    ) -> bool:
        raise NotImplementedError(_STUB_MESSAGE)

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
    ) -> ProofingSession:
        raise NotImplementedError(_STUB_MESSAGE)
