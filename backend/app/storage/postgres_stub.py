from __future__ import annotations

from app.domain.models import Asset, Project, ProjectState

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

    def find_asset_by_hash(self, project_id: str, sha256: str) -> Asset | None:
        raise NotImplementedError(_STUB_MESSAGE)

    def list_project_assets(self, project_id: str) -> list[Asset]:
        raise NotImplementedError(_STUB_MESSAGE)
