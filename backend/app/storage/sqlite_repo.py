from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.core.errors import ConflictError, NotFoundError
from app.core.ids import new_id, utc_now_iso
from app.domain.enums import (
    AssetKind,
    BatchItemStatus,
    BatchStatus,
    ImageMime,
    MarketplaceId,
    ProofingAction,
    ProofingStatus,
)
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
    SafeZone,
)
from app.domain.presets import CANONICAL_SYSTEM_PRESETS
from app.domain.rules import compute_batch_progress
from app.storage.ports import DeletedProjectArtifacts

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

_BATCH_JOB_COLUMNS = (
    "id, project_id, status, total_items, completed_items, failed_items, "
    "progress, zip_filename, error_message, config_json, created_at, started_at, "
    "completed_at, updated_at"
)

_BATCH_ITEM_COLUMNS = (
    "id, job_id, seq, asset_id, source_asset_id, preset_id, preset_version, "
    "format, quality, recipe_snapshot_json, status, output_filename, "
    "output_byte_size, output_width, output_height, error_code, error_message, "
    "attempts, created_at, started_at, completed_at"
)

_PROOFING_SESSION_COLUMNS = (
    "id, project_id, asset_id, project_revision_id, title, client_name, "
    "status, allow_comments, approved_by, approved_at, expires_at, revoked_at, "
    "created_at, updated_at"
)

_PROOFING_COMMENT_COLUMNS = (
    "id, session_id, author, action, body, pin_x, pin_y, "
    "resolved, resolved_by, resolved_at, created_at, updated_at"
)

_PROOFING_EVENT_COLUMNS = (
    "id, session_id, actor, event_type, from_status, to_status, note, payload_json, created_at"
)

_LEGACY_PROOFING_STATUS_MAP: dict[str, str] = {
    "pending": ProofingStatus.PENDING.value,
    "in_review": ProofingStatus.IN_REVIEW.value,
    "revision_requested": ProofingStatus.REVISION_REQUESTED.value,
    "changes_requested": ProofingStatus.REVISION_REQUESTED.value,
    "approved": ProofingStatus.APPROVED.value,
    "archived": ProofingStatus.ARCHIVED.value,
}

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
            if 4 not in applied:
                self._apply_migration_v4(conn)
            if 5 not in applied:
                self._apply_migration_v5(conn)

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

    def _apply_migration_v4(self, conn: sqlite3.Connection) -> None:
        now = utc_now_iso()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS batch_jobs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    status TEXT NOT NULL DEFAULT 'queued',
                    total_items INTEGER NOT NULL DEFAULT 0,
                    completed_items INTEGER NOT NULL DEFAULT 0,
                    failed_items INTEGER NOT NULL DEFAULT 0,
                    progress REAL NOT NULL DEFAULT 0.0,
                    zip_filename TEXT,
                    error_message TEXT,
                    config_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_batch_jobs_project_created ON batch_jobs(project_id, created_at DESC);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_batch_jobs_status ON batch_jobs(status);"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS batch_job_items (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES batch_jobs(id) ON DELETE CASCADE,
                    seq INTEGER NOT NULL,
                    asset_id TEXT NOT NULL,
                    source_asset_id TEXT NOT NULL,
                    preset_id TEXT NOT NULL,
                    preset_version TEXT NOT NULL,
                    format TEXT NOT NULL,
                    quality INTEGER NOT NULL DEFAULT 90,
                    recipe_snapshot_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    output_filename TEXT,
                    output_byte_size INTEGER NOT NULL DEFAULT 0,
                    output_width INTEGER NOT NULL DEFAULT 0,
                    output_height INTEGER NOT NULL DEFAULT 0,
                    error_code TEXT,
                    error_message TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_batch_job_items_job_seq ON batch_job_items(job_id, seq ASC);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_batch_job_items_job_status ON batch_job_items(job_id, status);"
            )
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (4, ?);",
                (now,),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    @staticmethod
    def _create_proofing_tables_sql() -> tuple[str, ...]:
        # CRITICAL: proofing_sessions.project_id intentionally omits SQLite REFERENCES projects(id)
        # so pre-M2 orphan rows (including kroma.db legacy rows and test_storage_sqlite_fs.py proof-orphan)
        # migrate cleanly with PRAGMA foreign_keys=ON. Runtime checks enforce project existence and
        # delete_project() cascades proofing_sessions cleanup.
        return (
            """
            CREATE TABLE IF NOT EXISTS proofing_sessions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                asset_id TEXT REFERENCES assets(id) ON DELETE SET NULL,
                project_revision_id TEXT,
                title TEXT NOT NULL,
                client_name TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                allow_comments INTEGER NOT NULL DEFAULT 1,
                approved_by TEXT,
                approved_at TEXT,
                expires_at TEXT,
                revoked_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS proofing_comments (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES proofing_sessions(id) ON DELETE CASCADE,
                author TEXT NOT NULL,
                action TEXT NOT NULL DEFAULT 'comment',
                body TEXT NOT NULL,
                pin_x REAL,
                pin_y REAL,
                resolved INTEGER NOT NULL DEFAULT 0,
                resolved_by TEXT,
                resolved_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS proofing_events (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES proofing_sessions(id) ON DELETE CASCADE,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                from_status TEXT,
                to_status TEXT,
                note TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_proofing_sessions_project ON proofing_sessions(project_id, created_at DESC);",
            "CREATE INDEX IF NOT EXISTS idx_proofing_sessions_project_status ON proofing_sessions(project_id, status);",
            "CREATE INDEX IF NOT EXISTS idx_proofing_comments_session ON proofing_comments(session_id, created_at ASC);",
            "CREATE INDEX IF NOT EXISTS idx_proofing_events_session ON proofing_events(session_id, created_at ASC);",
        )

    @staticmethod
    def _coerce_legacy_pin(raw_x: Any, raw_y: Any) -> tuple[float | None, float | None]:
        if raw_x is None or raw_y is None:
            return None, None
        if isinstance(raw_x, bool) or isinstance(raw_y, bool):
            return None, None
        try:
            fx = float(raw_x)
            fy = float(raw_y)
        except (TypeError, ValueError):
            return None, None
        if not (math.isfinite(fx) and math.isfinite(fy)):
            return None, None
        if not (0.0 <= fx <= 1.0 and 0.0 <= fy <= 1.0):
            return None, None
        return fx, fy

    def _apply_migration_v5(self, conn: sqlite3.Connection) -> None:
        now = utc_now_iso()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            proofing_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='proofing_sessions';"
            ).fetchone()

            migrated_legacy = False
            if proofing_exists is not None:
                cols = {
                    str(r["name"])
                    for r in conn.execute("PRAGMA table_info(proofing_sessions);").fetchall()
                }
                if "feedback_json" in cols or "updated_at" not in cols:
                    conn.execute(
                        "ALTER TABLE proofing_sessions RENAME TO _legacy_proofing_sessions_v0;"
                    )
                    migrated_legacy = True

            for stmt in self._create_proofing_tables_sql():
                conn.execute(stmt)

            if migrated_legacy:
                legacy_rows = conn.execute(
                    "SELECT * FROM _legacy_proofing_sessions_v0;"
                ).fetchall()
                seen_comment_ids: set[str] = set()
                for row in legacy_rows:
                    session_id = str(row["id"])
                    project_id = str(row["project_id"])
                    title = str(row["title"] or "Proofing Session")
                    client_name = (
                        str(row["client_name"]) if row["client_name"] is not None else None
                    )
                    raw_status = str(row["status"] or "pending").strip().lower()
                    mapped_status = _LEGACY_PROOFING_STATUS_MAP.get(
                        raw_status, ProofingStatus.PENDING.value
                    )
                    allow_comments = 1 if row["allow_comments"] is None else int(bool(row["allow_comments"]))
                    created_at = str(row["created_at"] or now)

                    raw_fb = row["feedback_json"] if "feedback_json" in row.keys() else "[]"
                    try:
                        parsed_fb = json.loads(str(raw_fb or "[]"))
                    except (TypeError, ValueError, json.JSONDecodeError):
                        parsed_fb = []
                    if not isinstance(parsed_fb, list):
                        parsed_fb = []

                    latest_ts = created_at
                    approved_by: str | None = None
                    approved_at: str | None = None
                    comment_rows: list[tuple[Any, ...]] = []

                    for item in parsed_fb:
                        if not isinstance(item, dict):
                            continue
                        raw_cid = str(item.get("id") or f"fb_{new_id()[:8]}")
                        cid = raw_cid if raw_cid not in seen_comment_ids else f"{raw_cid}_{new_id()[:6]}"
                        seen_comment_ids.add(cid)

                        author = str(item.get("author") or "Client")
                        raw_action = str(item.get("action") or "comment").strip().lower()
                        if raw_action not in {
                            ProofingAction.COMMENT.value,
                            ProofingAction.APPROVE.value,
                            ProofingAction.REQUEST_CHANGE.value,
                        }:
                            raw_action = ProofingAction.COMMENT.value

                        body = str(
                            item["comment"]
                            if "comment" in item and item["comment"] is not None
                            else item.get("body") or ""
                        )
                        pin_x, pin_y = self._coerce_legacy_pin(
                            item.get("pin_x"), item.get("pin_y")
                        )
                        item_created = str(item.get("created_at") or created_at)
                        if item_created > latest_ts:
                            latest_ts = item_created

                        if (
                            mapped_status == ProofingStatus.APPROVED.value
                            and raw_action == ProofingAction.APPROVE.value
                        ):
                            approved_by = author
                            approved_at = item_created

                        comment_rows.append(
                            (
                                cid,
                                session_id,
                                author,
                                raw_action,
                                body,
                                pin_x,
                                pin_y,
                                0,
                                None,
                                None,
                                item_created,
                                item_created,
                            )
                        )

                    conn.execute(
                        f"""
                        INSERT INTO proofing_sessions ({_PROOFING_SESSION_COLUMNS})
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            session_id,
                            project_id,
                            None,
                            None,
                            title,
                            client_name,
                            mapped_status,
                            allow_comments,
                            approved_by,
                            approved_at,
                            None,
                            None,
                            created_at,
                            latest_ts,
                        ),
                    )
                    for c_params in comment_rows:
                        conn.execute(
                            f"""
                            INSERT INTO proofing_comments ({_PROOFING_COMMENT_COLUMNS})
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                            """,
                            c_params,
                        )
                    conn.execute(
                        f"""
                        INSERT INTO proofing_events ({_PROOFING_EVENT_COLUMNS})
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            new_id(),
                            session_id,
                            "system",
                            "session_migrated",
                            None,
                            mapped_status,
                            "Migrated from legacy proofing_sessions",
                            json.dumps(
                                {"migrated_comments": len(comment_rows)},
                                separators=(",", ":"),
                            ),
                            created_at,
                        ),
                    )
                conn.execute("DROP TABLE _legacy_proofing_sessions_v0;")

            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (5, ?);",
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

    def update_project_name(
        self, project_id: str, name: str, updated_at: str
    ) -> Project | None:
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.execute(
                """
                UPDATE projects
                SET name = ?, updated_at = ?
                WHERE id = ?;
                """,
                (name, updated_at, project_id),
            )
            if cursor.rowcount == 0:
                conn.rollback()
                return None
            row = conn.execute(
                """
                SELECT id, name, description, active_variant, created_at, updated_at
                FROM projects
                WHERE id = ?;
                """,
                (project_id,),
            ).fetchone()
            conn.commit()
            return self._row_to_project(row) if row is not None else None

    def delete_project_with_artifacts(
        self, project_id: str
    ) -> DeletedProjectArtifacts | None:
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

            batch_job_ids: list[str] = []
            zip_filenames: list[str] = []
            has_batches = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='batch_jobs';"
            ).fetchone()
            if has_batches is not None:
                batch_rows = conn.execute(
                    "SELECT id, zip_filename FROM batch_jobs WHERE project_id = ?;",
                    (project_id,),
                ).fetchall()
                for b_row in batch_rows:
                    batch_job_ids.append(str(b_row["id"]))
                    if b_row["zip_filename"]:
                        zip_filenames.append(str(b_row["zip_filename"]))

            has_proofing = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='proofing_sessions';"
            ).fetchone()
            if has_proofing is not None:
                conn.execute("DELETE FROM proofing_sessions WHERE project_id = ?;", (project_id,))

            conn.execute("DELETE FROM projects WHERE id = ?;", (project_id,))
            conn.commit()
            return DeletedProjectArtifacts(
                storage_keys=storage_keys,
                batch_job_ids=batch_job_ids,
                zip_filenames=zip_filenames,
            )

    def delete_project(self, project_id: str) -> list[str] | None:
        artifacts = self.delete_project_with_artifacts(project_id)
        return artifacts.storage_keys if artifacts is not None else None

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

            # BR14: Advancing revision_id invalidates approved proofing sessions on older revisions
            if state.revision_id != current_revision:
                has_proofing = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='proofing_sessions';"
                ).fetchone()
                if has_proofing is not None:
                    approved_rows = conn.execute(
                        """
                        SELECT id, project_revision_id
                        FROM proofing_sessions
                        WHERE project_id = ?
                          AND status = 'approved'
                          AND revoked_at IS NULL
                          AND (project_revision_id IS NULL OR project_revision_id != ?);
                        """,
                        (state.project_id, state.revision_id),
                    ).fetchall()
                    for p_row in approved_rows:
                        session_id = str(p_row["id"])
                        prev_session_rev = (
                            str(p_row["project_revision_id"])
                            if p_row["project_revision_id"] is not None
                            else None
                        )
                        conn.execute(
                            """
                            UPDATE proofing_sessions
                            SET status = 'pending',
                                approved_by = NULL,
                                approved_at = NULL,
                                updated_at = ?
                            WHERE id = ?;
                            """,
                            (state.updated_at, session_id),
                        )
                        conn.execute(
                            f"""
                            INSERT INTO proofing_events ({_PROOFING_EVENT_COLUMNS})
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                            """,
                            (
                                new_id(),
                                session_id,
                                "system",
                                "project_revision_updated",
                                ProofingStatus.APPROVED.value,
                                ProofingStatus.PENDING.value,
                                f"Project state advanced to revision {state.revision_id}",
                                json.dumps(
                                    {
                                        "previous_revision_id": prev_session_rev,
                                        "state_previous_revision_id": current_revision,
                                        "new_revision_id": state.revision_id,
                                    },
                                    separators=(",", ":"),
                                ),
                                state.updated_at,
                            ),
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

    # ------------------------------------------------------------------
    # Batch jobs & items
    # ------------------------------------------------------------------

    def create_batch_job(self, job: BatchJob, items: list[BatchJobItem]) -> BatchJob:
        config_json = json.dumps(job.config, separators=(",", ":"), ensure_ascii=False)
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(
                f"""
                INSERT INTO batch_jobs ({_BATCH_JOB_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    job.id,
                    job.project_id,
                    job.status.value,
                    job.total_items,
                    job.completed_items,
                    job.failed_items,
                    job.progress,
                    job.zip_filename,
                    job.error_message,
                    config_json,
                    job.created_at,
                    job.started_at,
                    job.completed_at,
                    job.updated_at,
                ),
            )
            for item in items:
                snapshot_json = json.dumps(
                    item.recipe_snapshot, separators=(",", ":"), ensure_ascii=False
                )
                conn.execute(
                    f"""
                    INSERT INTO batch_job_items ({_BATCH_ITEM_COLUMNS})
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        item.id,
                        item.job_id,
                        item.seq,
                        item.asset_id,
                        item.source_asset_id,
                        item.preset_id,
                        item.preset_version,
                        item.format,
                        item.quality,
                        snapshot_json,
                        item.status.value,
                        item.output_filename,
                        item.output_byte_size,
                        item.output_width,
                        item.output_height,
                        item.error_code,
                        item.error_message,
                        item.attempts,
                        item.created_at,
                        item.started_at,
                        item.completed_at,
                    ),
                )
            conn.commit()
        return job

    def get_batch_job(self, job_id: str) -> tuple[BatchJob, list[BatchJobItem]] | None:
        with self._session() as conn:
            row = conn.execute(
                f"SELECT {_BATCH_JOB_COLUMNS} FROM batch_jobs WHERE id = ?;",
                (job_id,),
            ).fetchone()
            if row is None:
                return None
            item_rows = conn.execute(
                f"""
                SELECT {_BATCH_ITEM_COLUMNS}
                FROM batch_job_items
                WHERE job_id = ?
                ORDER BY seq ASC;
                """,
                (job_id,),
            ).fetchall()
            return self._row_to_batch_job(row), [
                self._row_to_batch_item(ir) for ir in item_rows
            ]

    def list_project_batch_jobs(self, project_id: str) -> list[BatchJob]:
        with self._session() as conn:
            rows = conn.execute(
                f"""
                SELECT {_BATCH_JOB_COLUMNS}
                FROM batch_jobs
                WHERE project_id = ?
                ORDER BY created_at DESC, id DESC;
                """,
                (project_id,),
            ).fetchall()
            return [self._row_to_batch_job(row) for row in rows]

    def list_unfinished_batch_jobs(self) -> list[BatchJob]:
        with self._session() as conn:
            rows = conn.execute(
                f"""
                SELECT {_BATCH_JOB_COLUMNS}
                FROM batch_jobs
                WHERE status IN ('queued', 'running', 'cancel_requested')
                ORDER BY created_at ASC, id ASC;
                """
            ).fetchall()
            return [self._row_to_batch_job(row) for row in rows]

    def claim_batch_job_running(self, job_id: str, started_at: str) -> BatchJob | None:
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            row = conn.execute(
                f"SELECT {_BATCH_JOB_COLUMNS} FROM batch_jobs WHERE id = ?;",
                (job_id,),
            ).fetchone()
            if row is None:
                conn.rollback()
                return None
            effective_started = str(row["started_at"]) if row["started_at"] else started_at
            conn.execute(
                """
                UPDATE batch_jobs
                SET status = ?,
                    started_at = ?,
                    updated_at = ?
                WHERE id = ?;
                """,
                (BatchStatus.RUNNING.value, effective_started, started_at, job_id),
            )
            updated = conn.execute(
                f"SELECT {_BATCH_JOB_COLUMNS} FROM batch_jobs WHERE id = ?;",
                (job_id,),
            ).fetchone()
            conn.commit()
            return self._row_to_batch_job(updated) if updated is not None else None

    def reset_running_batch_items_to_pending(self, job_id: str, updated_at: str) -> None:
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(
                """
                UPDATE batch_job_items
                SET status = 'pending', started_at = NULL
                WHERE job_id = ? AND status = 'running';
                """,
                (job_id,),
            )
            conn.execute(
                """
                UPDATE batch_jobs
                SET status = 'queued', updated_at = ?
                WHERE id = ? AND status = 'running';
                """,
                (updated_at, job_id),
            )
            conn.commit()

    def _recompute_batch_counters_on_conn(
        self, conn: sqlite3.Connection, job_id: str, updated_at: str
    ) -> tuple[int, int, int, int, float]:
        counts_row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_cnt,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_cnt,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_cnt,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_cnt
            FROM batch_job_items
            WHERE job_id = ?;
            """,
            (job_id,),
        ).fetchone()
        total = int(counts_row["total_cnt"] or 0)
        completed = int(counts_row["completed_cnt"] or 0)
        failed = int(counts_row["failed_cnt"] or 0)
        cancelled = int(counts_row["cancelled_cnt"] or 0)
        progress = compute_batch_progress(total, completed, failed, cancelled)
        conn.execute(
            """
            UPDATE batch_jobs
            SET completed_items = ?,
                failed_items = ?,
                progress = ?,
                updated_at = ?
            WHERE id = ?;
            """,
            (completed, failed, progress, updated_at, job_id),
        )
        return total, completed, failed, cancelled, progress

    def update_batch_job_item(self, item: BatchJobItem) -> BatchJobItem:
        now = utc_now_iso()
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.execute(
                """
                UPDATE batch_job_items
                SET status = ?,
                    output_filename = ?,
                    output_byte_size = ?,
                    output_width = ?,
                    output_height = ?,
                    error_code = ?,
                    error_message = ?,
                    attempts = ?,
                    started_at = ?,
                    completed_at = ?
                WHERE id = ?;
                """,
                (
                    item.status.value,
                    item.output_filename,
                    item.output_byte_size,
                    item.output_width,
                    item.output_height,
                    item.error_code,
                    item.error_message,
                    item.attempts,
                    item.started_at,
                    item.completed_at,
                    item.id,
                ),
            )
            if cursor.rowcount == 0:
                conn.rollback()
                raise NotFoundError(f"Batch item '{item.id}' not found")
            self._recompute_batch_counters_on_conn(conn, item.job_id, now)
            conn.commit()
        return item

    def request_batch_job_cancel(
        self, job_id: str, updated_at: str
    ) -> tuple[BatchJob, list[BatchJobItem]] | None:
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            row = conn.execute(
                f"SELECT {_BATCH_JOB_COLUMNS} FROM batch_jobs WHERE id = ?;",
                (job_id,),
            ).fetchone()
            if row is None:
                conn.rollback()
                return None

            current_status = BatchStatus(str(row["status"]))
            if current_status in (
                BatchStatus.COMPLETED,
                BatchStatus.PARTIAL_FAILED,
                BatchStatus.FAILED,
            ):
                conn.rollback()
                raise ConflictError(
                    f"Batch job '{job_id}' has already finished with status '{current_status.value}'"
                )

            if current_status == BatchStatus.QUEUED:
                conn.execute(
                    """
                    UPDATE batch_job_items
                    SET status = 'cancelled', completed_at = ?
                    WHERE job_id = ? AND status = 'pending';
                    """,
                    (updated_at, job_id),
                )
                self._recompute_batch_counters_on_conn(conn, job_id, updated_at)
                conn.execute(
                    """
                    UPDATE batch_jobs
                    SET status = 'cancelled',
                        completed_at = ?,
                        updated_at = ?
                    WHERE id = ?;
                    """,
                    (updated_at, updated_at, job_id),
                )
            elif current_status == BatchStatus.RUNNING:
                conn.execute(
                    """
                    UPDATE batch_jobs
                    SET status = 'cancel_requested',
                        updated_at = ?
                    WHERE id = ?;
                    """,
                    (updated_at, job_id),
                )

            job_row = conn.execute(
                f"SELECT {_BATCH_JOB_COLUMNS} FROM batch_jobs WHERE id = ?;",
                (job_id,),
            ).fetchone()
            item_rows = conn.execute(
                f"""
                SELECT {_BATCH_ITEM_COLUMNS}
                FROM batch_job_items
                WHERE job_id = ?
                ORDER BY seq ASC;
                """,
                (job_id,),
            ).fetchall()
            conn.commit()
            if job_row is None:
                return None
            return self._row_to_batch_job(job_row), [
                self._row_to_batch_item(ir) for ir in item_rows
            ]

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
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            row = conn.execute(
                "SELECT 1 FROM batch_jobs WHERE id = ?;",
                (job_id,),
            ).fetchone()
            if row is None:
                conn.rollback()
                return None

            if cancel_pending_items:
                conn.execute(
                    """
                    UPDATE batch_job_items
                    SET status = 'cancelled', completed_at = ?
                    WHERE job_id = ? AND status IN ('pending', 'running');
                    """,
                    (updated_at, job_id),
                )

            self._recompute_batch_counters_on_conn(conn, job_id, updated_at)
            conn.execute(
                """
                UPDATE batch_jobs
                SET status = ?,
                    zip_filename = ?,
                    error_message = ?,
                    completed_at = ?,
                    updated_at = ?
                WHERE id = ?;
                """,
                (
                    status.value,
                    zip_filename,
                    error_message,
                    completed_at,
                    updated_at,
                    job_id,
                ),
            )
            job_row = conn.execute(
                f"SELECT {_BATCH_JOB_COLUMNS} FROM batch_jobs WHERE id = ?;",
                (job_id,),
            ).fetchone()
            item_rows = conn.execute(
                f"""
                SELECT {_BATCH_ITEM_COLUMNS}
                FROM batch_job_items
                WHERE job_id = ?
                ORDER BY seq ASC;
                """,
                (job_id,),
            ).fetchall()
            conn.commit()
            if job_row is None:
                return None
            return self._row_to_batch_job(job_row), [
                self._row_to_batch_item(ir) for ir in item_rows
            ]

    def reset_batch_job_for_retry(
        self, job_id: str, updated_at: str
    ) -> tuple[BatchJob, list[BatchJobItem]] | None:
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            row = conn.execute(
                f"SELECT {_BATCH_JOB_COLUMNS} FROM batch_jobs WHERE id = ?;",
                (job_id,),
            ).fetchone()
            if row is None:
                conn.rollback()
                return None

            current_status = BatchStatus(str(row["status"]))
            if current_status not in (
                BatchStatus.FAILED,
                BatchStatus.PARTIAL_FAILED,
                BatchStatus.CANCELLED,
            ):
                conn.rollback()
                raise ConflictError(
                    f"Batch job '{job_id}' cannot be retried from status '{current_status.value}'"
                )

            retryable_cnt = conn.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM batch_job_items
                WHERE job_id = ? AND status IN ('failed', 'cancelled');
                """,
                (job_id,),
            ).fetchone()
            if int(retryable_cnt["cnt"] or 0) == 0:
                conn.rollback()
                raise ConflictError(f"Batch job '{job_id}' has no failed or cancelled items to retry")

            conn.execute(
                """
                UPDATE batch_job_items
                SET status = 'pending',
                    error_code = NULL,
                    error_message = NULL,
                    started_at = NULL,
                    completed_at = NULL
                WHERE job_id = ? AND status IN ('failed', 'cancelled');
                """,
                (job_id,),
            )
            self._recompute_batch_counters_on_conn(conn, job_id, updated_at)
            conn.execute(
                """
                UPDATE batch_jobs
                SET status = 'queued',
                    zip_filename = NULL,
                    error_message = NULL,
                    completed_at = NULL,
                    updated_at = ?
                WHERE id = ?;
                """,
                (updated_at, job_id),
            )
            job_row = conn.execute(
                f"SELECT {_BATCH_JOB_COLUMNS} FROM batch_jobs WHERE id = ?;",
                (job_id,),
            ).fetchone()
            item_rows = conn.execute(
                f"""
                SELECT {_BATCH_ITEM_COLUMNS}
                FROM batch_job_items
                WHERE job_id = ?
                ORDER BY seq ASC;
                """,
                (job_id,),
            ).fetchall()
            conn.commit()
            if job_row is None:
                return None
            return self._row_to_batch_job(job_row), [
                self._row_to_batch_item(ir) for ir in item_rows
            ]

    # ------------------------------------------------------------------
    # Proofing sessions, comments & events
    # ------------------------------------------------------------------

    def create_proofing_session(
        self, session: ProofingSession, initial_event: ProofingEvent
    ) -> ProofingSession:
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            conn.execute(
                f"""
                INSERT INTO proofing_sessions ({_PROOFING_SESSION_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    session.id,
                    session.project_id,
                    session.asset_id,
                    session.project_revision_id,
                    session.title,
                    session.client_name,
                    session.status.value,
                    1 if session.allow_comments else 0,
                    session.approved_by,
                    session.approved_at,
                    session.expires_at,
                    session.revoked_at,
                    session.created_at,
                    session.updated_at,
                ),
            )
            conn.execute(
                f"""
                INSERT INTO proofing_events ({_PROOFING_EVENT_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    initial_event.id,
                    initial_event.session_id,
                    initial_event.actor,
                    initial_event.event_type,
                    initial_event.from_status,
                    initial_event.to_status,
                    initial_event.note,
                    json.dumps(
                        initial_event.payload, separators=(",", ":"), ensure_ascii=False
                    ),
                    initial_event.created_at,
                ),
            )
            loaded = self._load_proofing_session_on_conn(conn, session.id)
            conn.commit()
            return loaded or session

    def get_proofing_session(self, session_id: str) -> ProofingSession | None:
        with self._session() as conn:
            return self._load_proofing_session_on_conn(conn, session_id)

    def list_project_proofing_sessions(self, project_id: str) -> list[ProofingSession]:
        with self._session() as conn:
            rows = conn.execute(
                f"""
                SELECT {_PROOFING_SESSION_COLUMNS}
                FROM proofing_sessions
                WHERE project_id = ?
                ORDER BY created_at DESC, id DESC;
                """,
                (project_id,),
            ).fetchall()
            sessions: list[ProofingSession] = []
            for row in rows:
                sid = str(row["id"])
                comments = self._load_proofing_comments_on_conn(conn, sid)
                events = self._load_proofing_events_on_conn(conn, sid)
                sessions.append(self._row_to_proofing_session(row, comments, events))
            return sessions

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
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            row = conn.execute(
                "SELECT 1 FROM proofing_sessions WHERE id = ?;",
                (session_id,),
            ).fetchone()
            if row is None:
                conn.rollback()
                raise NotFoundError(f"Proofing session '{session_id}' not found")

            conn.execute(
                f"""
                INSERT INTO proofing_comments ({_PROOFING_COMMENT_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    comment.id,
                    comment.session_id,
                    comment.author,
                    comment.action.value,
                    comment.body,
                    comment.pin_x,
                    comment.pin_y,
                    1 if comment.resolved else 0,
                    comment.resolved_by,
                    comment.resolved_at,
                    comment.created_at,
                    comment.updated_at,
                ),
            )
            conn.execute(
                """
                UPDATE proofing_sessions
                SET status = ?,
                    approved_by = ?,
                    approved_at = ?,
                    updated_at = ?
                WHERE id = ?;
                """,
                (new_status.value, approved_by, approved_at, updated_at, session_id),
            )
            conn.execute(
                f"""
                INSERT INTO proofing_events ({_PROOFING_EVENT_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    event.id,
                    event.session_id,
                    event.actor,
                    event.event_type,
                    event.from_status,
                    event.to_status,
                    event.note,
                    json.dumps(event.payload, separators=(",", ":"), ensure_ascii=False),
                    event.created_at,
                ),
            )
            loaded = self._load_proofing_session_on_conn(conn, session_id)
            conn.commit()
            if loaded is None:
                raise NotFoundError(f"Proofing session '{session_id}' not found")
            return loaded

    def get_proofing_comment(
        self, session_id: str, comment_id: str
    ) -> ProofingComment | None:
        with self._session() as conn:
            row = conn.execute(
                f"""
                SELECT {_PROOFING_COMMENT_COLUMNS}
                FROM proofing_comments
                WHERE id = ? AND session_id = ?;
                """,
                (comment_id, session_id),
            ).fetchone()
            return self._row_to_proofing_comment(row) if row is not None else None

    def update_proofing_comment(
        self,
        comment: ProofingComment,
        *,
        updated_at: str,
        event: ProofingEvent,
    ) -> ProofingComment:
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.execute(
                """
                UPDATE proofing_comments
                SET body = ?,
                    resolved = ?,
                    resolved_by = ?,
                    resolved_at = ?,
                    updated_at = ?
                WHERE id = ? AND session_id = ?;
                """,
                (
                    comment.body,
                    1 if comment.resolved else 0,
                    comment.resolved_by,
                    comment.resolved_at,
                    comment.updated_at,
                    comment.id,
                    comment.session_id,
                ),
            )
            if cursor.rowcount == 0:
                conn.rollback()
                raise NotFoundError(f"Proofing comment '{comment.id}' not found")
            conn.execute(
                "UPDATE proofing_sessions SET updated_at = ? WHERE id = ?;",
                (updated_at, comment.session_id),
            )
            conn.execute(
                f"""
                INSERT INTO proofing_events ({_PROOFING_EVENT_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    event.id,
                    event.session_id,
                    event.actor,
                    event.event_type,
                    event.from_status,
                    event.to_status,
                    event.note,
                    json.dumps(event.payload, separators=(",", ":"), ensure_ascii=False),
                    event.created_at,
                ),
            )
            row = conn.execute(
                f"""
                SELECT {_PROOFING_COMMENT_COLUMNS}
                FROM proofing_comments
                WHERE id = ? AND session_id = ?;
                """,
                (comment.id, comment.session_id),
            ).fetchone()
            conn.commit()
            return self._row_to_proofing_comment(row) if row is not None else comment

    def delete_proofing_comment(
        self,
        session_id: str,
        comment_id: str,
        *,
        updated_at: str,
        event: ProofingEvent,
    ) -> bool:
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.execute(
                "DELETE FROM proofing_comments WHERE id = ? AND session_id = ?;",
                (comment_id, session_id),
            )
            if cursor.rowcount == 0:
                conn.rollback()
                return False
            conn.execute(
                "UPDATE proofing_sessions SET updated_at = ? WHERE id = ?;",
                (updated_at, session_id),
            )
            conn.execute(
                f"""
                INSERT INTO proofing_events ({_PROOFING_EVENT_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    event.id,
                    event.session_id,
                    event.actor,
                    event.event_type,
                    event.from_status,
                    event.to_status,
                    event.note,
                    json.dumps(event.payload, separators=(",", ":"), ensure_ascii=False),
                    event.created_at,
                ),
            )
            conn.commit()
            return True

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
        with self._session() as conn:
            conn.execute("BEGIN IMMEDIATE;")
            cursor = conn.execute(
                """
                UPDATE proofing_sessions
                SET status = ?,
                    approved_by = ?,
                    approved_at = ?,
                    revoked_at = ?,
                    updated_at = ?
                WHERE id = ?;
                """,
                (
                    new_status.value,
                    approved_by,
                    approved_at,
                    revoked_at,
                    updated_at,
                    session_id,
                ),
            )
            if cursor.rowcount == 0:
                conn.rollback()
                raise NotFoundError(f"Proofing session '{session_id}' not found")
            conn.execute(
                f"""
                INSERT INTO proofing_events ({_PROOFING_EVENT_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    event.id,
                    event.session_id,
                    event.actor,
                    event.event_type,
                    event.from_status,
                    event.to_status,
                    event.note,
                    json.dumps(event.payload, separators=(",", ":"), ensure_ascii=False),
                    event.created_at,
                ),
            )
            loaded = self._load_proofing_session_on_conn(conn, session_id)
            conn.commit()
            if loaded is None:
                raise NotFoundError(f"Proofing session '{session_id}' not found")
            return loaded

    def _load_proofing_comments_on_conn(
        self, conn: sqlite3.Connection, session_id: str
    ) -> tuple[ProofingComment, ...]:
        rows = conn.execute(
            f"""
            SELECT {_PROOFING_COMMENT_COLUMNS}
            FROM proofing_comments
            WHERE session_id = ?
            ORDER BY created_at ASC, id ASC;
            """,
            (session_id,),
        ).fetchall()
        return tuple(self._row_to_proofing_comment(r) for r in rows)

    def _load_proofing_events_on_conn(
        self, conn: sqlite3.Connection, session_id: str
    ) -> tuple[ProofingEvent, ...]:
        rows = conn.execute(
            f"""
            SELECT {_PROOFING_EVENT_COLUMNS}
            FROM proofing_events
            WHERE session_id = ?
            ORDER BY created_at ASC, id ASC;
            """,
            (session_id,),
        ).fetchall()
        return tuple(self._row_to_proofing_event(r) for r in rows)

    def _load_proofing_session_on_conn(
        self, conn: sqlite3.Connection, session_id: str
    ) -> ProofingSession | None:
        row = conn.execute(
            f"SELECT {_PROOFING_SESSION_COLUMNS} FROM proofing_sessions WHERE id = ?;",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        comments = self._load_proofing_comments_on_conn(conn, session_id)
        events = self._load_proofing_events_on_conn(conn, session_id)
        return self._row_to_proofing_session(row, comments, events)

    @staticmethod
    def _row_to_batch_job(row: sqlite3.Row) -> BatchJob:
        raw_cfg = row["config_json"]
        parsed_cfg = json.loads(str(raw_cfg)) if raw_cfg else {}
        return BatchJob(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            status=BatchStatus(str(row["status"])),
            total_items=int(row["total_items"]),
            completed_items=int(row["completed_items"]),
            failed_items=int(row["failed_items"]),
            progress=float(row["progress"]),
            zip_filename=str(row["zip_filename"]) if row["zip_filename"] is not None else None,
            error_message=str(row["error_message"]) if row["error_message"] is not None else None,
            config=parsed_cfg if isinstance(parsed_cfg, dict) else {},
            created_at=str(row["created_at"]),
            started_at=str(row["started_at"]) if row["started_at"] is not None else None,
            completed_at=str(row["completed_at"]) if row["completed_at"] is not None else None,
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _row_to_batch_item(row: sqlite3.Row) -> BatchJobItem:
        raw_snap = row["recipe_snapshot_json"]
        parsed_snap = json.loads(str(raw_snap)) if raw_snap else {}
        return BatchJobItem(
            id=str(row["id"]),
            job_id=str(row["job_id"]),
            seq=int(row["seq"]),
            asset_id=str(row["asset_id"]),
            source_asset_id=str(row["source_asset_id"]),
            preset_id=str(row["preset_id"]),
            preset_version=str(row["preset_version"]),
            format=str(row["format"]),
            quality=int(row["quality"]),
            recipe_snapshot=parsed_snap if isinstance(parsed_snap, dict) else {},
            status=BatchItemStatus(str(row["status"])),
            output_filename=(
                str(row["output_filename"]) if row["output_filename"] is not None else None
            ),
            output_byte_size=int(row["output_byte_size"] or 0),
            output_width=int(row["output_width"] or 0),
            output_height=int(row["output_height"] or 0),
            error_code=str(row["error_code"]) if row["error_code"] is not None else None,
            error_message=str(row["error_message"]) if row["error_message"] is not None else None,
            attempts=int(row["attempts"] or 0),
            created_at=str(row["created_at"]),
            started_at=str(row["started_at"]) if row["started_at"] is not None else None,
            completed_at=str(row["completed_at"]) if row["completed_at"] is not None else None,
        )

    @staticmethod
    def _row_to_proofing_comment(row: sqlite3.Row) -> ProofingComment:
        created_at = str(row["created_at"])
        updated_at = str(row["updated_at"]) if row["updated_at"] else created_at
        return ProofingComment(
            id=str(row["id"]),
            session_id=str(row["session_id"]),
            author=str(row["author"]),
            action=ProofingAction(str(row["action"])),
            body=str(row["body"]),
            pin_x=float(row["pin_x"]) if row["pin_x"] is not None else None,
            pin_y=float(row["pin_y"]) if row["pin_y"] is not None else None,
            resolved=bool(row["resolved"]),
            resolved_by=str(row["resolved_by"]) if row["resolved_by"] is not None else None,
            resolved_at=str(row["resolved_at"]) if row["resolved_at"] is not None else None,
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _row_to_proofing_event(row: sqlite3.Row) -> ProofingEvent:
        raw_payload = row["payload_json"]
        parsed_payload = json.loads(str(raw_payload)) if raw_payload else {}
        return ProofingEvent(
            id=str(row["id"]),
            session_id=str(row["session_id"]),
            actor=str(row["actor"]),
            event_type=str(row["event_type"]),
            from_status=str(row["from_status"]) if row["from_status"] is not None else None,
            to_status=str(row["to_status"]) if row["to_status"] is not None else None,
            note=str(row["note"] or ""),
            payload=parsed_payload if isinstance(parsed_payload, dict) else {},
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _row_to_proofing_session(
        row: sqlite3.Row,
        comments: tuple[ProofingComment, ...],
        events: tuple[ProofingEvent, ...],
    ) -> ProofingSession:
        created_at = str(row["created_at"])
        updated_at = str(row["updated_at"]) if row["updated_at"] else created_at
        return ProofingSession(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            asset_id=str(row["asset_id"]) if row["asset_id"] is not None else None,
            project_revision_id=(
                str(row["project_revision_id"])
                if row["project_revision_id"] is not None
                else None
            ),
            title=str(row["title"]),
            client_name=str(row["client_name"]) if row["client_name"] is not None else None,
            status=ProofingStatus(str(row["status"])),
            allow_comments=bool(row["allow_comments"]),
            approved_by=str(row["approved_by"]) if row["approved_by"] is not None else None,
            approved_at=str(row["approved_at"]) if row["approved_at"] is not None else None,
            expires_at=str(row["expires_at"]) if row["expires_at"] is not None else None,
            revoked_at=str(row["revoked_at"]) if row["revoked_at"] is not None else None,
            created_at=created_at,
            updated_at=updated_at,
            comments=comments,
            events=events,
        )
