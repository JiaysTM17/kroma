from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KROMA_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "KROMA API"
    app_version: str = "0.1.0"
    environment: Literal["local", "staging", "production"] = "local"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3005",
        "http://127.0.0.1:3005",
    ]

    database_backend: Literal["sqlite", "postgres"] = "sqlite"
    sqlite_path: Path = BACKEND_DIR / "data" / "kroma.db"
    postgres_dsn: str | None = None

    storage_backend: Literal["local", "s3"] = "local"
    local_storage_dir: Path = BACKEND_DIR / "data" / "blobs"
    exports_dir: Path = BACKEND_DIR / "data" / "exports"
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None
    s3_region: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    max_upload_bytes: int = 25 * 1024 * 1024
    max_image_pixels: int = 50_000_000
    max_image_dimension: int = 16_384
    max_state_bytes: int = 2 * 1024 * 1024
    max_archive_entries: int = 500
    max_archive_uncompressed_bytes: int = 250 * 1024 * 1024
