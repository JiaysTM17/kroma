from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.core.errors import ConflictError, NotFoundError
from app.core.ids import utc_now_iso
from app.domain.enums import AssetKind, ImageMime, MarketplaceId
from app.domain.models import Asset, MarketplacePreset, Project, ProjectState, SafeZone
from app.domain.presets import CANONICAL_SYSTEM_PRESETS

_ASSET_COLUMNS = (
    "id, project_id, kind, parent_asset_id, variant, filename, mime_type, "
    "sha256, byte_size, width, height, exif_orientation, storage_key, "
    "is_readonly, metadata_json, created_at, updated_at"
)

_PRESET_COLUMNS = (
    "id, marketplace, name_en, name_vi, rule_description_en, rule_description_vi, "
    "version, aspect_ratio, width, height, formats_json, background_rgb_json, "
    "subject_area_ratio, safe_zone_json, is_system, editable, created_at, updated_at"
)

_LEGACY_MARKETPLACE_MAP: dict[str, str] = {
    "shopee": MarketplaceId.SHOPEE.value,
    "tiktok shop": MarketplaceId.TIKTOK_SHOP.value,
    "tiktok_shop": MarketplaceId.TIKTOK_SHOP.value,
    "lazada": MarketplaceId.LAZADA.value,
    "amazon": MarketplaceId.AMAZON.value,
}


def _parse_legacy_bg_color(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in ("", "transparent", "none"):
        return None
    if text.startswith("#"):
        hex_part = text[1:]
        try:
            if len(hex_part) == 6:
                rgb = [int(hex_part[0:2], 16), int(hex_part[2:4], 16), int(hex_part[4:6], 16)]
                return json.dumps(rgb)
            if len(hex_part) == 3:
                rgb = [int(ch * 2, 16) for ch in hex_part]
                return json.dumps(rgb)
        except ValueError:
            return None
    return None


def _normalize_legacy_formats(raw: Any) -> str:
    fmt = str(raw or "").strip().lower()
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in {"webp", "jpeg", "png"}:
        fmt = "jpeg"
    return json.dumps([fmt])


class SQLiteRepo:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._session() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                """
            )
            conn.commit()

            applied = {
                int(row["version"])
                for row in conn.execute("SELECT version FROM schema_migrations;").fetchall()
            }

            if 1 not in applied:
                self._apply_migration_v1(conn)
            if 2 not in applied:
                self._apply_migration_v2(conn)
            if 3 not in applied:
                self._apply_migration_v3(conn)

            # Ensure canonical system presets are seeded even if v3 ran previously
            self._seed_presets_on_conn(conn, CANONICAL_SYSTEM_PRESETS, utc_now_iso())

    def _apply_migration_v1(self, conn: sqlite3.Connection) -> None:
        now = utc_now_iso()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(
                """
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
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS project_states (
                    project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
                    schema_version INTEGER NOT NULL,
                    revision_id TEXT NOT NULL,
                    active_variant TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
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
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_assets_project_hash
                    ON assets(project_id, sha256);
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS proofing_sessions (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    client_name TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    allow_comments INTEGER DEFAULT 1,
                    feedback_json TEXT DEFAULT '[]'
                );
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (1, ?);",
                (now,),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _apply_migration_v2(self, conn: sqlite3.Connection) -> None:
        now = utc_now_iso()
        try:
            conn.execute("BEGIN IMMEDIATE;")

            project_cols = {
                str(r["name"])
                for r in conn.execute("PRAGMA table_info(projects);").fetchall()
            }
            if "description" not in project_cols:
                conn.execute(
                    "ALTER TABLE projects ADD COLUMN description TEXT NOT NULL DEFAULT '';"
                )
            if "active_variant" not in project_cols:
                conn.execute(
                    "ALTER TABLE projects ADD COLUMN active_variant TEXT NOT NULL DEFAULT 'default';"
                )
            if "schema_version" not in project_cols:
                conn.execute(
                    "ALTER TABLE projects ADD COLUMN schema_version INTEGER NOT NULL DEFAULT 1;"
                )
            if "manifest_json" not in project_cols:
                conn.execute(
                    "ALTER TABLE projects ADD COLUMN manifest_json TEXT NOT NULL DEFAULT '{}';"
                )

            asset_cols = {
                str(r["name"])
                for r in conn.execute("PRAGMA table_info(assets);").fetchall()
            }
            if "parent_asset_id" not in asset_cols:
                conn.execute(
                    "ALTER TABLE assets ADD COLUMN parent_asset_id TEXT REFERENCES assets(id) ON DELETE SET NULL;"
                )
            if "variant" not in asset_cols:
                conn.execute(
                    "ALTER TABLE assets ADD COLUMN variant TEXT NOT NULL DEFAULT 'default';"
                )
            if "metadata_json" not in asset_cols:
                conn.execute(
                    "ALTER TABLE assets ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}';"
                )
            if "updated_at" not in asset_cols:
                conn.execute(
                    "ALTER TABLE assets ADD COLUMN updated_at TEXT NOT NULL DEFAULT '';"
                )

            conn.execute(
                "UPDATE assets SET updated_at = created_at WHERE updated_at = '' OR updated_at IS NULL;"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_assets_project_kind ON assets(project_id, kind);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_assets_parent ON assets(parent_asset_id);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_assets_storage_key ON assets(storage_key);"
            )
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (2, ?);",
                (now,),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    @staticmethod
    def _create_presets_table_sql() -> str:
        return """
        CREATE TABLE IF NOT EXISTS presets (
            id TEXT PRIMARY KEY,
            marketplace TEXT NOT NULL,
            name_en TEXT NOT NULL,
            name_vi TEXT NOT NULL,
            rule_description_en TEXT NOT NULL DEFAULT '',
            rule_description_vi TEXT NOT NULL DEFAULT '',
            version TEXT NOT NULL DEFAULT '1.0.0',
            aspect_ratio TEXT NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            formats_json TEXT NOT NULL,
            background_rgb_json TEXT,
            subject_area_ratio REAL,
            safe_zone_json TEXT,
            is_system INTEGER NOT NULL DEFAULT 0,
            editable INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """

    def _apply_migration_v3(self, conn: sqlite3.Connection) -> None:
        now = utc_now_iso()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            presets_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='presets';"
            ).fetchone()

            if presets_exists is not None:
                preset_cols = {
                    str(r["name"])
                    for r in conn.execute("PRAGMA table_info(presets);").fetchall()
                }
                if "bg_color" in preset_cols and "name_en" not in preset_cols:
                    conn.execute("ALTER TABLE presets RENAME TO _legacy_presets_v0;")
                    conn.execute(self._create_presets_table_sql())
                    legacy_rows = conn.execute("SELECT * FROM _legacy_presets_v0;").fetchall()
                    for row in legacy_rows:
                        raw_mp = str(row["marketplace"] or "").strip().lower()
                        marketplace = _LEGACY_MARKETPLACE_MAP.get(raw_mp, MarketplaceId.CUSTOM.value)
                        name = str(row["name"] or row["id"]).strip() or str(row["id"])
                        desc = str(row["description"] or "").strip()
                        bg_json = _parse_legacy_bg_color(row["bg_color"])
                        formats_json = _normalize_legacy_formats(row["format"])
                        ratio = (
                            float(row["subject_scale"])
                            if row["subject_scale"] is not None
                            else None
                        )
                        conn.execute(
                            f"""
                            INSERT OR IGNORE INTO presets ({_PRESET_COLUMNS})
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                            """,
                            (
                                str(row["id"]),
                                marketplace,
                                name,
                                name,
                                desc,
                                desc,
                                "1.0.0",
                                str(row["aspect_ratio"] or "1:1"),
                                int(row["width"]),
                                int(row["height"]),
                                formats_json,
                                bg_json,
                                ratio,
                                None,
                                0,
                                1,
                                now,
                                now,
                            ),
                        )
                    conn.execute("DROP TABLE _legacy_presets_v0;")
            else:
                conn.execute(self._create_presets_table_sql())

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_presets_system_created ON presets(is_system DESC, created_at ASC);"
            )
            self._insert_system_presets_on_conn(conn, CANONICAL_SYSTEM_PRESETS, now)
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (3, ?);",
                (now,),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _insert_system_presets_on_conn(
        self,
        conn: sqlite3.Connection,
        presets: tuple[MarketplacePreset, ...] | list[MarketplacePreset],
        now: str,
    ) -> None:
        for preset in presets:
            created_at = preset.created_at or now
            updated_at = preset.updated_at or now
            conn.execute(
                f"""
                INSERT OR IGNORE INTO presets ({_PRESET_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                self._preset_to_params(
                    preset,
                    created_at=created_at,
                    updated_at=updated_at,
                ),
            )

    def _seed_presets_on_conn(
        self,
        conn: sqlite3.Connection,
        presets: tuple[MarketplacePreset, ...] | list[MarketplacePreset],
        now: str,
    ) -> None:
        try:
            conn.execute("BEGIN IMMEDIATE;")
            self._insert_system_presets_on_conn(conn, presets, now)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def get_pragmas(self) -> dict[str, Any]:
        with self._session() as conn:
            journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            foreign_keys = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
            busy_timeout = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
            return {
                "journal_mode": str(journal_mode).lower(),
                "foreign_keys": int(foreign_keys),
                "busy_timeout": int(busy_timeout),
            }

    def ping(self) -> bool:
        with self._session() as conn:
            row = conn.execute("SELECT 1;").fetchone()
            return row is not None and int(row[0]) == 1

    def close(self) -> None:
        # Connections are opened and closed per unit-of-work to prevent Windows file-lock leaks.
        return None

    def create_project(self, project: Project, initial_state: ProjectState) -> Project:
        with self._session() as conn:
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
        with self._session() as conn:
            rows = conn.execute(
                """
                SELECT id, name, description, active_variant, created_at, updated_at
                FROM projects
                ORDER BY updated_at DESC, created_at DESC;
                """
            ).fetchall()
            return [self._row_to_project(row) for row in rows]

    def get_project(self, project_id: str) -> Project | None:
        with self._session() as conn:
            row = conn.execute(
                """
                SELECT id, name, description, active_variant, created_at, updated_at
                FROM projects
                WHERE id = ?;
                """,
                (project_id,),
            ).fetchone()
            return self._row_to_project(row) if row is not None else None

    def delete_project(self, project_id: str) -> list[str] | None:
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            exists = conn.execute(
                "SELECT 1 FROM projects WHERE id = ?;",
                (project_id,),
            ).fetchone()
            if exists is None:
                conn.rollback()
                return None

            key_rows = conn.execute(
                "SELECT DISTINCT storage_key FROM assets WHERE project_id = ?;",
                (project_id,),
            ).fetchall()
            storage_keys = [str(row["storage_key"]) for row in key_rows]

            has_proofing = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='proofing_sessions';"
            ).fetchone()
            if has_proofing is not None:
                conn.execute("DELETE FROM proofing_sessions WHERE project_id = ?;", (project_id,))

            conn.execute("DELETE FROM projects WHERE id = ?;", (project_id,))
            conn.commit()
            return storage_keys

    def get_project_state(self, project_id: str) -> ProjectState | None:
        with self._session() as conn:
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
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            existing = conn.execute(
                "SELECT revision_id FROM project_states WHERE project_id = ?;",
                (state.project_id,),
            ).fetchone()
            if existing is None:
                conn.rollback()
                raise NotFoundError(f"Project '{state.project_id}' not found")

            current_revision = str(existing["revision_id"])
            if expected_revision_id is not None and expected_revision_id != current_revision:
                conn.rollback()
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
        updated_at = asset.updated_at or asset.created_at
        metadata_json = json.dumps(asset.metadata, separators=(",", ":"), ensure_ascii=False)
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(
                f"""
                INSERT INTO assets ({_ASSET_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    asset.id,
                    asset.project_id,
                    asset.kind.value,
                    asset.parent_asset_id,
                    asset.variant,
                    asset.filename,
                    asset.mime_type.value,
                    asset.sha256,
                    asset.byte_size,
                    asset.width,
                    asset.height,
                    asset.exif_orientation,
                    asset.storage_key,
                    1 if asset.is_readonly else 0,
                    metadata_json,
                    asset.created_at,
                    updated_at,
                ),
            )
            conn.commit()
        return Asset(
            id=asset.id,
            project_id=asset.project_id,
            kind=asset.kind,
            filename=asset.filename,
            mime_type=asset.mime_type,
            sha256=asset.sha256,
            byte_size=asset.byte_size,
            width=asset.width,
            height=asset.height,
            exif_orientation=asset.exif_orientation,
            storage_key=asset.storage_key,
            is_readonly=asset.is_readonly,
            created_at=asset.created_at,
            parent_asset_id=asset.parent_asset_id,
            variant=asset.variant,
            metadata=dict(asset.metadata),
            updated_at=updated_at,
        )

    def get_asset(self, asset_id: str) -> Asset | None:
        with self._session() as conn:
            row = conn.execute(
                f"SELECT {_ASSET_COLUMNS} FROM assets WHERE id = ?;",
                (asset_id,),
            ).fetchone()
            return self._row_to_asset(row) if row is not None else None

    def find_asset_by_hash(
        self,
        project_id: str,
        sha256: str,
        *,
        kind: AssetKind | None = None,
        variant: str | None = None,
        parent_asset_id: str | None = None,
    ) -> Asset | None:
        clauses = ["project_id = ?", "sha256 = ?"]
        params: list[Any] = [project_id, sha256]
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind.value)
            if parent_asset_id is None:
                clauses.append("parent_asset_id IS NULL")
            else:
                clauses.append("parent_asset_id = ?")
                params.append(parent_asset_id)
        elif parent_asset_id is not None:
            clauses.append("parent_asset_id = ?")
            params.append(parent_asset_id)

        if variant is not None:
            clauses.append("variant = ?")
            params.append(variant)

        where_sql = " AND ".join(clauses)
        with self._session() as conn:
            row = conn.execute(
                f"""
                SELECT {_ASSET_COLUMNS}
                FROM assets
                WHERE {where_sql}
                ORDER BY created_at ASC
                LIMIT 1;
                """,
                tuple(params),
            ).fetchone()
            return self._row_to_asset(row) if row is not None else None

    def list_project_assets(
        self,
        project_id: str,
        *,
        kind: AssetKind | None = None,
        parent_asset_id: str | None = None,
    ) -> list[Asset]:
        clauses = ["project_id = ?"]
        params: list[Any] = [project_id]
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind.value)
        if parent_asset_id is not None:
            clauses.append("parent_asset_id = ?")
            params.append(parent_asset_id)

        where_sql = " AND ".join(clauses)
        with self._session() as conn:
            rows = conn.execute(
                f"""
                SELECT {_ASSET_COLUMNS}
                FROM assets
                WHERE {where_sql}
                ORDER BY created_at ASC;
                """,
                tuple(params),
            ).fetchall()
            return [self._row_to_asset(row) for row in rows]

    def update_asset(self, asset: Asset) -> Asset:
        metadata_json = json.dumps(asset.metadata, separators=(",", ":"), ensure_ascii=False)
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.execute(
                """
                UPDATE assets
                SET filename = ?, variant = ?, metadata_json = ?, updated_at = ?
                WHERE id = ?;
                """,
                (
                    asset.filename,
                    asset.variant,
                    metadata_json,
                    asset.updated_at,
                    asset.id,
                ),
            )
            if cursor.rowcount == 0:
                conn.rollback()
                raise NotFoundError(f"Asset '{asset.id}' not found")
            conn.commit()
        return asset

    def delete_asset(self, asset_id: str) -> Asset | None:
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            row = conn.execute(
                f"SELECT {_ASSET_COLUMNS} FROM assets WHERE id = ?;",
                (asset_id,),
            ).fetchone()
            if row is None:
                conn.rollback()
                return None
            asset = self._row_to_asset(row)
            conn.execute("DELETE FROM assets WHERE id = ?;", (asset_id,))
            conn.commit()
            return asset

    def count_storage_key_refs(self, storage_key: str) -> int:
        with self._session() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM assets WHERE storage_key = ?;",
                (storage_key,),
            ).fetchone()
            return int(row["cnt"]) if row is not None else 0

    def list_presets(self) -> list[MarketplacePreset]:
        with self._session() as conn:
            rows = conn.execute(
                f"""
                SELECT {_PRESET_COLUMNS}
                FROM presets
                ORDER BY is_system DESC, created_at ASC, id ASC;
                """
            ).fetchall()
            return [self._row_to_preset(row) for row in rows]

    def get_preset(self, preset_id: str) -> MarketplacePreset | None:
        with self._session() as conn:
            row = conn.execute(
                f"SELECT {_PRESET_COLUMNS} FROM presets WHERE id = ?;",
                (preset_id,),
            ).fetchone()
            return self._row_to_preset(row) if row is not None else None

    def create_preset(self, preset: MarketplacePreset) -> MarketplacePreset:
        now = utc_now_iso()
        created_at = preset.created_at or now
        updated_at = preset.updated_at or now
        with self._session() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    f"""
                    INSERT INTO presets ({_PRESET_COLUMNS})
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    self._preset_to_params(
                        preset,
                        created_at=created_at,
                        updated_at=updated_at,
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise ConflictError(f"Preset '{preset.id}' already exists") from exc
            except Exception:
                conn.rollback()
                raise
        return self.get_preset(preset.id) or preset

    def update_preset(self, preset: MarketplacePreset) -> MarketplacePreset:
        now = utc_now_iso()
        updated_at = preset.updated_at or now
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.execute(
                """
                UPDATE presets
                SET marketplace = ?,
                    name_en = ?,
                    name_vi = ?,
                    rule_description_en = ?,
                    rule_description_vi = ?,
                    version = ?,
                    aspect_ratio = ?,
                    width = ?,
                    height = ?,
                    formats_json = ?,
                    background_rgb_json = ?,
                    subject_area_ratio = ?,
                    safe_zone_json = ?,
                    editable = ?,
                    updated_at = ?
                WHERE id = ?;
                """,
                (
                    preset.marketplace.value,
                    preset.name_en,
                    preset.name_vi,
                    preset.rule_description_en,
                    preset.rule_description_vi,
                    preset.version,
                    preset.aspect_ratio,
                    preset.width,
                    preset.height,
                    json.dumps(list(preset.formats)),
                    json.dumps(list(preset.background_rgb))
                    if preset.background_rgb is not None
                    else None,
                    preset.subject_area_ratio,
                    json.dumps(
                        {
                            "top": preset.safe_zone.top,
                            "right": preset.safe_zone.right,
                            "bottom": preset.safe_zone.bottom,
                            "left": preset.safe_zone.left,
                        }
                    )
                    if preset.safe_zone is not None
                    else None,
                    1 if preset.editable else 0,
                    updated_at,
                    preset.id,
                ),
            )
            if cursor.rowcount == 0:
                conn.rollback()
                raise NotFoundError(f"Preset '{preset.id}' not found")
            conn.commit()
        return self.get_preset(preset.id) or preset

    def delete_preset(self, preset_id: str) -> bool:
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.execute("DELETE FROM presets WHERE id = ?;", (preset_id,))
            conn.commit()
            return cursor.rowcount > 0

    def seed_system_presets(
        self, presets: tuple[MarketplacePreset, ...] | list[MarketplacePreset]
    ) -> None:
        with self._session() as conn:
            self._seed_presets_on_conn(conn, presets, utc_now_iso())

    @staticmethod
    def _preset_to_params(
        preset: MarketplacePreset,
        *,
        created_at: str,
        updated_at: str,
    ) -> tuple[Any, ...]:
        return (
            preset.id,
            preset.marketplace.value,
            preset.name_en,
            preset.name_vi,
            preset.rule_description_en,
            preset.rule_description_vi,
            preset.version,
            preset.aspect_ratio,
            preset.width,
            preset.height,
            json.dumps(list(preset.formats)),
            json.dumps(list(preset.background_rgb))
            if preset.background_rgb is not None
            else None,
            preset.subject_area_ratio,
            json.dumps(
                {
                    "top": preset.safe_zone.top,
                    "right": preset.safe_zone.right,
                    "bottom": preset.safe_zone.bottom,
                    "left": preset.safe_zone.left,
                }
            )
            if preset.safe_zone is not None
            else None,
            1 if preset.is_system else 0,
            1 if preset.editable else 0,
            created_at,
            updated_at,
        )

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
        raw_meta = row["metadata_json"]
        parsed_meta = json.loads(str(raw_meta)) if raw_meta else {}
        created_at = str(row["created_at"])
        updated_at = str(row["updated_at"]) if row["updated_at"] else created_at
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
            created_at=created_at,
            parent_asset_id=(
                str(row["parent_asset_id"]) if row["parent_asset_id"] is not None else None
            ),
            variant=str(row["variant"]) if row["variant"] else "default",
            metadata=parsed_meta if isinstance(parsed_meta, dict) else {},
            updated_at=updated_at,
        )

    @staticmethod
    def _row_to_preset(row: sqlite3.Row) -> MarketplacePreset:
        formats = tuple(json.loads(str(row["formats_json"])))
        bg_raw = row["background_rgb_json"]
        background_rgb: tuple[int, int, int] | None = None
        if bg_raw is not None:
            parsed_bg = json.loads(str(bg_raw))
            if isinstance(parsed_bg, list) and len(parsed_bg) == 3:
                background_rgb = (int(parsed_bg[0]), int(parsed_bg[1]), int(parsed_bg[2]))

        sz_raw = row["safe_zone_json"]
        safe_zone: SafeZone | None = None
        if sz_raw is not None:
            parsed_sz = json.loads(str(sz_raw))
            if isinstance(parsed_sz, dict):
                safe_zone = SafeZone(
                    top=float(parsed_sz["top"]),
                    right=float(parsed_sz["right"]),
                    bottom=float(parsed_sz["bottom"]),
                    left=float(parsed_sz["left"]),
                )

        ratio_raw = row["subject_area_ratio"]
        return MarketplacePreset(
            id=str(row["id"]),
            marketplace=MarketplaceId(str(row["marketplace"])),
            name_en=str(row["name_en"]),
            name_vi=str(row["name_vi"]),
            rule_description_en=str(row["rule_description_en"] or ""),
            rule_description_vi=str(row["rule_description_vi"] or ""),
            version=str(row["version"]),
            aspect_ratio=str(row["aspect_ratio"]),
            width=int(row["width"]),
            height=int(row["height"]),
            formats=formats,
            background_rgb=background_rgb,
            subject_area_ratio=float(ratio_raw) if ratio_raw is not None else None,
            safe_zone=safe_zone,
            editable=bool(row["editable"]),
            is_system=bool(row["is_system"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
