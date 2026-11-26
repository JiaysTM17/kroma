from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.core.errors import ConflictError, NotFoundError
from app.domain.enums import AssetKind, ImageMime
from app.domain.models import Asset, Project, ProjectState


class SQLiteRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    active_variant TEXT NOT NULL DEFAULT 'default',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    schema_version INTEGER NOT NULL DEFAULT 1,
                    manifest_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS project_states (
                    project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
                    schema_version INTEGER NOT NULL,
                    revision_id TEXT NOT NULL,
                    active_variant TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    byte_size INTEGER NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    exif_orientation INTEGER NOT NULL DEFAULT 1,
                    storage_key TEXT NOT NULL,
                    is_readonly INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_assets_project_hash
                    ON assets(project_id, sha256);
                """
            )
            conn.commit()

    def get_pragmas(self) -> dict[str, Any]:
        with self._connect() as conn:
            journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            foreign_keys = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
            busy_timeout = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
            return {
                "journal_mode": str(journal_mode).lower(),
                "foreign_keys": int(foreign_keys),
                "busy_timeout": int(busy_timeout),
            }

    def ping(self) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1;").fetchone()
            return row is not None and int(row[0]) == 1

    def close(self) -> None:
        # Connections are opened and closed per unit-of-work to prevent Windows file-lock leaks.
        return None

    def create_project(self, project: Project, initial_state: ProjectState) -> Project:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(
                """
                INSERT INTO projects (id, name, description, active_variant, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    project.id,
                    project.name,
                    project.description,
                    project.active_variant,
                    project.created_at,
                    project.updated_at,
                ),
            )
            conn.execute(
                """
                INSERT INTO project_states (
                    project_id, schema_version, revision_id, active_variant, state_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    initial_state.project_id,
                    initial_state.schema_version,
                    initial_state.revision_id,
                    initial_state.active_variant,
                    json.dumps(initial_state.state, separators=(",", ":"), ensure_ascii=False),
                    initial_state.updated_at,
                ),
            )
            conn.commit()
        return project

    def list_projects(self) -> list[Project]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, description, active_variant, created_at, updated_at
                FROM projects
                ORDER BY updated_at DESC, created_at DESC;
                """
            ).fetchall()
            return [self._row_to_project(row) for row in rows]

    def get_project(self, project_id: str) -> Project | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, name, description, active_variant, created_at, updated_at
                FROM projects
                WHERE id = ?;
                """,
                (project_id,),
            ).fetchone()
            return self._row_to_project(row) if row is not None else None

    def get_project_state(self, project_id: str) -> ProjectState | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT project_id, schema_version, revision_id, active_variant, state_json, updated_at
                FROM project_states
                WHERE project_id = ?;
                """,
                (project_id,),
            ).fetchone()
            if row is None:
                return None
            return ProjectState(
                project_id=str(row["project_id"]),
                schema_version=int(row["schema_version"]),
                revision_id=str(row["revision_id"]),
                active_variant=str(row["active_variant"]),
                state=json.loads(str(row["state_json"])),
                updated_at=str(row["updated_at"]),
            )

    def put_project_state(
        self, state: ProjectState, expected_revision_id: str | None = None
    ) -> ProjectState:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            existing = conn.execute(
                "SELECT revision_id FROM project_states WHERE project_id = ?;",
                (state.project_id,),
            ).fetchone()
            if existing is None:
                raise NotFoundError(f"Project '{state.project_id}' not found")

            current_revision = str(existing["revision_id"])
            if expected_revision_id is not None and expected_revision_id != current_revision:
                raise ConflictError(
                    f"Revision conflict: expected '{expected_revision_id}', current is '{current_revision}'"
                )

            state_json = json.dumps(state.state, separators=(",", ":"), ensure_ascii=False)
            conn.execute(
                """
                UPDATE project_states
                SET schema_version = ?, revision_id = ?, active_variant = ?, state_json = ?, updated_at = ?
                WHERE project_id = ?;
                """,
                (
                    state.schema_version,
                    state.revision_id,
                    state.active_variant,
                    state_json,
                    state.updated_at,
                    state.project_id,
                ),
            )
            conn.execute(
                """
                UPDATE projects
                SET active_variant = ?, updated_at = ?
                WHERE id = ?;
                """,
                (state.active_variant, state.updated_at, state.project_id),
            )
            conn.commit()
        return state

    def create_asset(self, asset: Asset) -> Asset:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(
                """
                INSERT INTO assets (
                    id, project_id, kind, filename, mime_type, sha256,
                    byte_size, width, height, exif_orientation, storage_key,
                    is_readonly, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    asset.id,
                    asset.project_id,
                    asset.kind.value,
                    asset.filename,
                    asset.mime_type.value,
                    asset.sha256,
                    asset.byte_size,
                    asset.width,
                    asset.height,
                    asset.exif_orientation,
                    asset.storage_key,
                    1 if asset.is_readonly else 0,
                    asset.created_at,
                ),
            )
            conn.commit()
        return asset

    def get_asset(self, asset_id: str) -> Asset | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, project_id, kind, filename, mime_type, sha256,
                       byte_size, width, height, exif_orientation, storage_key,
                       is_readonly, created_at
                FROM assets
                WHERE id = ?;
                """,
                (asset_id,),
            ).fetchone()
            return self._row_to_asset(row) if row is not None else None

    def find_asset_by_hash(self, project_id: str, sha256: str) -> Asset | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, project_id, kind, filename, mime_type, sha256,
                       byte_size, width, height, exif_orientation, storage_key,
                       is_readonly, created_at
                FROM assets
                WHERE project_id = ? AND sha256 = ?
                ORDER BY created_at ASC
                LIMIT 1;
                """,
                (project_id, sha256),
            ).fetchone()
            return self._row_to_asset(row) if row is not None else None

    def list_project_assets(self, project_id: str) -> list[Asset]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, project_id, kind, filename, mime_type, sha256,
                       byte_size, width, height, exif_orientation, storage_key,
                       is_readonly, created_at
                FROM assets
                WHERE project_id = ?
                ORDER BY created_at ASC;
                """,
                (project_id,),
            ).fetchall()
            return [self._row_to_asset(row) for row in rows]

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> Project:
        return Project(
            id=str(row["id"]),
            name=str(row["name"]),
            description=str(row["description"]),
            active_variant=str(row["active_variant"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _row_to_asset(row: sqlite3.Row) -> Asset:
        return Asset(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            kind=AssetKind(str(row["kind"])),
            filename=str(row["filename"]),
            mime_type=ImageMime(str(row["mime_type"])),
            sha256=str(row["sha256"]),
            byte_size=int(row["byte_size"]),
            width=int(row["width"]),
            height=int(row["height"]),
            exif_orientation=int(row["exif_orientation"]),
            storage_key=str(row["storage_key"]),
            is_readonly=bool(row["is_readonly"]),
            created_at=str(row["created_at"]),
        )
