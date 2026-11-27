from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
from pathlib import Path

import pytest

from app.core.errors import ConflictError, NotFoundError, SecurityError
from app.core.ids import utc_now_iso
from app.domain.enums import AssetKind, ErrorCode, ImageMime, MarketplaceId
from app.domain.models import Asset, MarketplacePreset, Project, ProjectState, SafeZone
from app.storage.local_fs import LocalFSStore
from app.storage.postgres_stub import PostgresInterface
from app.storage.s3_stub import S3Interface
from app.storage.sqlite_repo import SQLiteRepo


def test_sqlite_wal_and_pragmas_enabled(tmp_path: Path) -> None:
    repo = SQLiteRepo(tmp_path / "wal_check.db")
    repo.initialize()
    pragmas = repo.get_pragmas()
    assert pragmas["journal_mode"] == "wal"
    assert pragmas["foreign_keys"] == 1
    assert pragmas["busy_timeout"] == 5000
    assert repo.ping() is True
    repo.close()


def test_sqlite_persistence_across_repo_reinstantiation(tmp_path: Path) -> None:
    db_file = tmp_path / "persist.db"
    now = utc_now_iso()
    repo_1 = SQLiteRepo(db_file)
    repo_1.initialize()

    project = Project(
        id="proj-1",
        name="Giày thể thao Kroma",
        description="Bộ ảnh studio",
        active_variant="default",
        created_at=now,
        updated_at=now,
    )
    initial_state = ProjectState(
        project_id="proj-1",
        schema_version=1,
        revision_id="rev-1",
        active_variant="default",
        state={"commands": [{"type": "init"}]},
        updated_at=now,
    )
    repo_1.create_project(project, initial_state)
    repo_1.create_asset(
        Asset(
            id="asset-1",
            project_id="proj-1",
            kind=AssetKind.ORIGINAL,
            filename="shoe.png",
            mime_type=ImageMime.PNG,
            sha256="a" * 64,
            byte_size=1234,
            width=800,
            height=600,
            exif_orientation=1,
            storage_key="originals/aa/" + "a" * 64 + ".png",
            is_readonly=True,
            created_at=now,
        )
    )
    repo_1.close()

    repo_2 = SQLiteRepo(db_file)
    loaded_project = repo_2.get_project("proj-1")
    loaded_state = repo_2.get_project_state("proj-1")
    loaded_assets = repo_2.list_project_assets("proj-1")

    assert loaded_project == project
    assert loaded_state == initial_state
    assert len(loaded_assets) == 1
    assert loaded_assets[0].filename == "shoe.png"
    assert loaded_assets[0].updated_at == now
    repo_2.close()


def test_sqlite_migrations_seed_and_idempotency(tmp_path: Path) -> None:
    db_file = tmp_path / "fresh_migrations.db"
    repo = SQLiteRepo(db_file)
    repo.initialize()

    with sqlite3.connect(db_file) as conn:
        versions = [
            int(r[0])
            for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        ]
        assert versions == [1, 2, 3]
        asset_cols = {r[1] for r in conn.execute("PRAGMA table_info(assets)").fetchall()}
        assert {"parent_asset_id", "variant", "metadata_json", "updated_at"}.issubset(asset_cols)

    presets = repo.list_presets()
    assert len(presets) == 5

    # Customize a system preset and re-run initialize() -> edits must persist
    shopee = repo.get_preset("shopee_1_1")
    assert shopee is not None
    edited = MarketplacePreset(
        id=shopee.id,
        marketplace=shopee.marketplace,
        name_en="Shopee Custom Edited",
        name_vi=shopee.name_vi,
        rule_description_en=shopee.rule_description_en,
        rule_description_vi=shopee.rule_description_vi,
        version="1.1.0",
        aspect_ratio=shopee.aspect_ratio,
        width=1200,
        height=1200,
        formats=shopee.formats,
        background_rgb=(250, 250, 250),
        subject_area_ratio=0.9,
        safe_zone=SafeZone(top=0.05, right=0.05, bottom=0.05, left=0.05),
        editable=True,
        is_system=True,
        created_at=shopee.created_at,
        updated_at=utc_now_iso(),
    )
    repo.update_preset(edited)
    repo.initialize()

    reloaded = repo.get_preset("shopee_1_1")
    assert reloaded is not None
    assert reloaded.name_en == "Shopee Custom Edited"
    assert reloaded.width == 1200
    assert reloaded.background_rgb == (250, 250, 250)


def test_sqlite_migrates_legacy_assets_presets_and_proofing_without_data_loss(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "legacy.db"
    now = "2026-11-26T10:00:00Z"
    with sqlite3.connect(db_file) as conn:
        conn.executescript(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                active_variant TEXT NOT NULL DEFAULT 'default',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT 1,
                manifest_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE project_states (
                project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
                schema_version INTEGER NOT NULL,
                revision_id TEXT NOT NULL,
                active_variant TEXT NOT NULL,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE assets (
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
            CREATE TABLE presets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                marketplace TEXT NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                aspect_ratio TEXT NOT NULL,
                bg_color TEXT NOT NULL,
                subject_scale REAL NOT NULL,
                format TEXT NOT NULL,
                description TEXT
            );
            CREATE TABLE proofing_sessions (
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
            "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("proj-legacy", "Legacy Project", now, now),
        )
        conn.execute(
            "INSERT INTO project_states VALUES (?, ?, ?, ?, ?, ?)",
            ("proj-legacy", 1, "rev-legacy", "default", '{"commands":[]}', now),
        )
        conn.execute(
            "INSERT INTO assets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "asset-legacy",
                "proj-legacy",
                "original",
                "legacy.png",
                "image/png",
                "b" * 64,
                512,
                100,
                100,
                1,
                "originals/bb/" + "b" * 64 + ".png",
                1,
                now,
            ),
        )
        conn.executemany(
            "INSERT INTO presets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("shopee_square", "Shopee Standard 1:1", "Shopee", 1024, 1024, "1:1", "#FFFFFF", 0.90, "JPEG", "Shopee desc"),
                ("transparent_png", "Web PNG Transparent", "Universal", 1200, 1200, "1:1", "transparent", 0.90, "PNG", "Transparent desc"),
                ("custom_brand_hero", "Brand Hero 4:5", "TikTok Shop", 1080, 1350, "4:5", "#112233", 0.80, "JPG", "Custom legacy"),
            ],
        )
        conn.execute(
            "INSERT INTO proofing_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("proof-orphan", "proj_demo_fashion", "Orphan Proof", "Client", "pending", now, 1, "[]"),
        )
        conn.commit()

    repo = SQLiteRepo(db_file)
    repo.initialize()
    # Run twice to prove idempotency
    repo.initialize()

    assert repo.get_project("proj-legacy") is not None
    migrated_asset = repo.get_asset("asset-legacy")
    assert migrated_asset is not None
    assert migrated_asset.updated_at == now
    assert migrated_asset.variant == "default"
    assert migrated_asset.metadata == {}
    assert migrated_asset.parent_asset_id is None

    presets = {p.id: p for p in repo.list_presets()}
    # 5 canonical system presets + 3 migrated legacy rows
    assert len(presets) == 8
    assert presets["shopee_1_1"].is_system is True
    assert presets["custom_brand_hero"].is_system is False
    assert presets["custom_brand_hero"].marketplace == MarketplaceId.TIKTOK_SHOP
    assert presets["custom_brand_hero"].background_rgb == (0x11, 0x22, 0x33)
    assert presets["custom_brand_hero"].formats == ("jpeg",)
    assert presets["transparent_png"].background_rgb is None
    assert presets["transparent_png"].marketplace == MarketplaceId.CUSTOM

    with sqlite3.connect(db_file) as conn:
        proofing_count = conn.execute("SELECT COUNT(*) FROM proofing_sessions").fetchone()[0]
        assert proofing_count == 1


def test_local_fs_immutable_derived_and_delete_blob(tmp_path: Path) -> None:
    blobs_dir = tmp_path / "blobs"
    store = LocalFSStore(blobs_dir)
    store.initialize()

    payload = b"kroma-immutable-bytes"
    key = "originals/ab/sample.bin"
    stored = store.put_immutable(key, payload)
    assert stored.sha256 == hashlib.sha256(payload).hexdigest()
    assert stored.byte_size == len(payload)
    assert stored.is_readonly is True

    target_file = blobs_dir / "originals" / "ab" / "sample.bin"
    assert target_file.is_file()
    mode = os.stat(target_file).st_mode
    assert not (mode & stat.S_IWRITE)

    with pytest.raises(PermissionError):
        with open(target_file, "ab") as fh:
            fh.write(b"mutate")

    stored_again = store.put_immutable(key, payload)
    assert stored_again.sha256 == stored.sha256

    with pytest.raises(ConflictError) as exc_info:
        store.put_immutable(key, b"different-bytes")
    assert exc_info.value.code == ErrorCode.IMMUTABLE_ASSET_VIOLATION
    assert exc_info.value.status_code == 409

    # Derived blob is writable and idempotent
    derived_key = "derived/mask/cd/mask.png"
    derived_blob = store.put_derived(derived_key, b"mask-bytes")
    assert derived_blob.is_readonly is False
    assert os.stat(blobs_dir / "derived" / "mask" / "cd" / "mask.png").st_mode & stat.S_IWRITE

    # delete_blob removes both read-only immutable and derived files cleanly on Windows
    assert store.delete_blob(key) is True
    assert store.exists(key) is False
    assert store.delete_blob(key) is False
    assert store.delete_blob(derived_key) is True
    assert store.exists(derived_key) is False

    with pytest.raises(SecurityError):
        store.delete_blob("../escape.bin")

    with pytest.raises(NotFoundError):
        store.get_bytes("originals/ab/missing.bin")


def test_cloud_stubs_raise_not_implemented() -> None:
    pg = PostgresInterface("postgresql://user:pass@localhost:5432/kroma")
    with pytest.raises(NotImplementedError):
        pg.initialize()
    with pytest.raises(NotImplementedError):
        pg.ping()
    with pytest.raises(NotImplementedError):
        pg.delete_project("p1")
    with pytest.raises(NotImplementedError):
        pg.delete_asset("a1")
    with pytest.raises(NotImplementedError):
        pg.list_presets()
    with pytest.raises(ValueError):
        PostgresInterface("mysql://invalid")

    s3 = S3Interface(bucket="kroma-bucket", region="auto")
    with pytest.raises(NotImplementedError):
        s3.initialize()
    with pytest.raises(NotImplementedError):
        s3.put_immutable("a/b.png", b"123")
    with pytest.raises(NotImplementedError):
        s3.put_derived("derived/mask/a/b.png", b"123")
    with pytest.raises(NotImplementedError):
        s3.delete_blob("a/b.png")
    with pytest.raises(NotImplementedError):
        s3.get_bytes("a/b.png")
