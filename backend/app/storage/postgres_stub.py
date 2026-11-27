from __future__ import annotations

from app.domain.enums import AssetKind
from app.domain.models import Asset, MarketplacePreset, Project, ProjectState

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

    def delete_project(self, project_id: str) -> list[str] | None:
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
