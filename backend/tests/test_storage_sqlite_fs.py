from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

import pytest

from app.core.errors import ConflictError, NotFoundError
from app.core.ids import utc_now_iso
from app.domain.enums import AssetKind, ErrorCode, ImageMime
from app.domain.models import Asset, Project, ProjectState
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
    repo_2.close()


def test_local_fs_immutable_readonly_and_sha256(tmp_path: Path) -> None:
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

    # Idempotent same-hash write succeeds
    stored_again = store.put_immutable(key, payload)
    assert stored_again.sha256 == stored.sha256

    # Mismatched-hash overwrite raises IMMUTABLE_ASSET_VIOLATION (409)
    with pytest.raises(ConflictError) as exc_info:
        store.put_immutable(key, b"different-bytes")
    assert exc_info.value.code == ErrorCode.IMMUTABLE_ASSET_VIOLATION
    assert exc_info.value.status_code == 409

    assert store.get_bytes(key) == payload
    with pytest.raises(NotFoundError):
        store.get_bytes("originals/ab/missing.bin")


def test_cloud_stubs_raise_not_implemented() -> None:
    pg = PostgresInterface("postgresql://user:pass@localhost:5432/kroma")
    with pytest.raises(NotImplementedError):
        pg.initialize()
    with pytest.raises(NotImplementedError):
        pg.ping()
    with pytest.raises(ValueError):
        PostgresInterface("mysql://invalid")

    s3 = S3Interface(bucket="kroma-bucket", region="auto")
    with pytest.raises(NotImplementedError):
        s3.initialize()
    with pytest.raises(NotImplementedError):
        s3.put_immutable("a/b.png", b"123")
    with pytest.raises(NotImplementedError):
        s3.get_bytes("a/b.png")
