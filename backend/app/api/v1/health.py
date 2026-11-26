from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import AppContainer, get_container
from app.core.errors import InternalStorageError

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(container: AppContainer = Depends(get_container)) -> dict[str, str]:
    if not container.repo.ping():
        raise InternalStorageError("Database health check failed")
    return {
        "status": "ok",
        "database": container.settings.database_backend,
        "storage": container.settings.storage_backend,
        "version": container.settings.app_version,
    }
