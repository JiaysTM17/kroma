from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


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


@pytest.fixture(autouse=True)
def _windows_readonly_cleanup(tmp_path: Path) -> Iterator[None]:
    yield
    _make_writable_tree(tmp_path)


@pytest.fixture()
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        sqlite_path=tmp_path / "kroma_test.db",
        local_storage_dir=tmp_path / "blobs",
    )


@pytest.fixture()
def client(test_settings: Settings) -> Iterator[TestClient]:
    application = create_app(settings=test_settings)
    with TestClient(application) as test_client:
        yield test_client
