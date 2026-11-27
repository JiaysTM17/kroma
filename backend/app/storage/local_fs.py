from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from pathlib import Path

from app.core.errors import ConflictError, InternalStorageError, NotFoundError
from app.core.security import assert_safe_relative_path
from app.domain.enums import ErrorCode
from app.storage.ports import StoredBlob


class LocalFSStore:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir

    def initialize(self) -> None:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._base_dir = self._base_dir.resolve()

    def _atomic_write(self, target: Path, data: bytes, *, readonly: bool) -> str:
        expected_sha = hashlib.sha256(data).hexdigest()
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=target.parent,
                prefix=".tmp_",
                delete=False,
            ) as tmp_file:
                tmp_path = Path(tmp_file.name)
                tmp_file.write(data)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())

            if target.exists() and not readonly:
                try:
                    os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
                except OSError:
                    pass

            os.replace(tmp_path, target)
            tmp_path = None
            if readonly:
                os.chmod(target, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
            else:
                os.chmod(target, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

            written_sha = hashlib.sha256(target.read_bytes()).hexdigest()
            if written_sha != expected_sha:
                raise InternalStorageError("Stored asset checksum verification failed")
        finally:
            if tmp_path is not None and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
        return expected_sha

    def put_immutable(self, key: str, data: bytes) -> StoredBlob:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        target = assert_safe_relative_path(key, self._base_dir)
        expected_sha = hashlib.sha256(data).hexdigest()

        if target.exists():
            existing_sha = hashlib.sha256(target.read_bytes()).hexdigest()
            if existing_sha == expected_sha:
                return StoredBlob(
                    storage_key=key,
                    sha256=expected_sha,
                    byte_size=len(data),
                    is_readonly=True,
                )
            raise ConflictError(
                "Cannot overwrite immutable original asset",
                code=ErrorCode.IMMUTABLE_ASSET_VIOLATION,
            )

        self._atomic_write(target, data, readonly=True)
        return StoredBlob(
            storage_key=key,
            sha256=expected_sha,
            byte_size=len(data),
            is_readonly=True,
        )

    def put_derived(self, key: str, data: bytes) -> StoredBlob:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        target = assert_safe_relative_path(key, self._base_dir)
        expected_sha = hashlib.sha256(data).hexdigest()

        if target.exists():
            existing_sha = hashlib.sha256(target.read_bytes()).hexdigest()
            if existing_sha == expected_sha:
                return StoredBlob(
                    storage_key=key,
                    sha256=expected_sha,
                    byte_size=len(data),
                    is_readonly=False,
                )

        self._atomic_write(target, data, readonly=False)
        return StoredBlob(
            storage_key=key,
            sha256=expected_sha,
            byte_size=len(data),
            is_readonly=False,
        )

    def get_bytes(self, key: str) -> bytes:
        target = assert_safe_relative_path(key, self._base_dir)
        if not target.is_file():
            raise NotFoundError("Stored asset bytes not found")
        return target.read_bytes()

    def exists(self, key: str) -> bool:
        target = assert_safe_relative_path(key, self._base_dir)
        return target.is_file()

    def delete_blob(self, key: str) -> bool:
        target = assert_safe_relative_path(key, self._base_dir)
        if not target.is_file():
            return False
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
        target.unlink()

        base_resolved = self._base_dir.resolve()
        parent = target.parent
        while parent != base_resolved and parent.is_relative_to(base_resolved):
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
        return True
