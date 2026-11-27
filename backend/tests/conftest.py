from __future__ import annotations

import atexit
import os
import shutil
import stat
import tempfile
from collections.abc import Iterator
from pathlib import Path


def _make_writable_tree(root: Path) -> None:
    if not root.exists():
        return
    for dirpath, _dirnames, filenames in os.walk(root):
        current_dir = Path(dirpath)
        try:
            os.chmod(current_dir, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        except OSError:
            pass
        for name in filenames:
            file_path = current_dir / name
            try:
                os.chmod(file_path, stat.S_IWRITE | stat.S_IREAD)
            except OSError:
                pass


# Isolate module-level create_app() / app.config side effects away from live backend/data/
_IMPORT_ISOLATION_DIR = Path(tempfile.mkdtemp(prefix="kroma_pytest_import_"))
os.environ["KROMA_DATA_DIR"] = str(_IMPORT_ISOLATION_DIR)
os.environ["KROMA_SQLITE_PATH"] = str(_IMPORT_ISOLATION_DIR / "kroma_import.db")
os.environ["KROMA_LOCAL_STORAGE_DIR"] = str(_IMPORT_ISOLATION_DIR / "blobs")
os.environ["KROMA_EXPORTS_DIR"] = str(_IMPORT_ISOLATION_DIR / "exports")


def _cleanup_import_dir() -> None:
    _make_writable_tree(_IMPORT_ISOLATION_DIR)
    shutil.rmtree(_IMPORT_ISOLATION_DIR, ignore_errors=True)


atexit.register(_cleanup_import_dir)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(autouse=True)
def _windows_readonly_cleanup(tmp_path: Path) -> Iterator[None]:
    yield
    _make_writable_tree(tmp_path)


@pytest.fixture()
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        sqlite_path=tmp_path / "kroma_test.db",
        local_storage_dir=tmp_path / "blobs",
        exports_dir=tmp_path / "exports",
    )


@pytest.fixture()
def client(test_settings: Settings) -> Iterator[TestClient]:
    application = create_app(settings=test_settings)
    with TestClient(application) as test_client:
        yield test_client
