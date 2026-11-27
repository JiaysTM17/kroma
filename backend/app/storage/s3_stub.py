from __future__ import annotations

from app.storage.ports import StoredBlob

_STUB_MESSAGE = (
    "S3/R2 object storage adapter is a clean M1 interface stub; "
    "use KROMA_STORAGE_BACKEND=local for local execution."
)


class S3Interface:
    def __init__(
        self,
        bucket: str | None = None,
        endpoint_url: str | None = None,
        region: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.region = region
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key

    def initialize(self) -> None:
        raise NotImplementedError(_STUB_MESSAGE)

    def put_immutable(self, key: str, data: bytes) -> StoredBlob:
        raise NotImplementedError(_STUB_MESSAGE)

    def put_derived(self, key: str, data: bytes) -> StoredBlob:
        raise NotImplementedError(_STUB_MESSAGE)

    def get_bytes(self, key: str) -> bytes:
        raise NotImplementedError(_STUB_MESSAGE)

    def exists(self, key: str) -> bool:
        raise NotImplementedError(_STUB_MESSAGE)

    def delete_blob(self, key: str) -> bool:
        raise NotImplementedError(_STUB_MESSAGE)
