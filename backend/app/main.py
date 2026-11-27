from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.deps import AppContainer
from app.api.v1 import health as v1_health
from app.api.v1.router import v1_router
from app.core.config import Settings
from app.core.errors import AppError
from app.core.ids import sanitize_correlation_id
from app.domain.enums import ErrorCode
from app.routers import export as export_router
from app.routers import presets as legacy_presets_router
from app.routers import projects as legacy_projects_router
from app.routers import proofing as proofing_router
from app.services.asset_service import AssetService
from app.services.preset_service import PresetService
from app.services.project_service import ProjectService
from app.storage.local_fs import LocalFSStore
from app.storage.sqlite_repo import SQLiteRepo

APP_TITLE = "KROMA Intelligent Image Studio API"
APP_VERSION = "0.1.0"


def build_container(settings: Settings) -> AppContainer:
    repo = SQLiteRepo(settings.sqlite_path)
    repo.initialize()
    blob_store = LocalFSStore(settings.local_storage_dir)
    blob_store.initialize()
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    project_service = ProjectService(
        repo=repo,
        blob_store=blob_store,
        max_state_bytes=settings.max_state_bytes,
    )
    asset_service = AssetService(
        repo=repo,
        blob_store=blob_store,
        settings=settings,
    )
    preset_service = PresetService(repo=repo)
    return AppContainer(
        settings=settings,
        repo=repo,
        blob_store=blob_store,
        project_service=project_service,
        asset_service=asset_service,
        preset_service=preset_service,
    )


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    current_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield

    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        description="Backend API phục vụ Kroma Web Hybrid AI E-Commerce Image Studio",
        lifespan=lifespan,
    )

    app.state.settings = current_settings
    app.state.container = build_container(current_settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        corr_id = sanitize_correlation_id(request.headers.get("x-correlation-id"))
        request.state.correlation_id = corr_id
        response = await call_next(request)
        response.headers["x-correlation-id"] = corr_id
        return response

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        corr_id = getattr(
            request.state,
            "correlation_id",
            sanitize_correlation_id(request.headers.get("x-correlation-id")),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code.value if hasattr(exc.code, "value") else str(exc.code),
                "message": exc.message,
                "correlation_id": corr_id,
                "retryable": exc.retryable,
            },
            headers={"x-correlation-id": corr_id},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        corr_id = getattr(
            request.state,
            "correlation_id",
            sanitize_correlation_id(request.headers.get("x-correlation-id")),
        )
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": code,
                "message": str(exc.detail),
                "correlation_id": corr_id,
                "retryable": False,
            },
            headers={"x-correlation-id": corr_id},
        )

    def _format_validation_errors(exc: RequestValidationError) -> str:
        parts: list[str] = []
        errors = exc.errors()
        for err in errors[:5]:
            loc = ".".join(str(item) for item in err.get("loc", ()) if item != "body")
            msg = str(err.get("msg", "Invalid value"))
            if msg.startswith("Value error, "):
                msg = msg[len("Value error, "):]
            parts.append(f"{loc}: {msg}" if loc else msg)
        if not parts:
            return "Request validation failed"
        extra = len(errors) - len(parts)
        summary = "; ".join(parts)
        if extra > 0:
            summary = f"{summary} (+{extra} more)"
        return summary

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        corr_id = getattr(
            request.state,
            "correlation_id",
            sanitize_correlation_id(request.headers.get("x-correlation-id")),
        )
        return JSONResponse(
            status_code=422,
            content={
                "code": ErrorCode.VALIDATION_ERROR.value,
                "message": _format_validation_errors(exc),
                "correlation_id": corr_id,
                "retryable": False,
            },
            headers={"x-correlation-id": corr_id},
        )

    @app.get("/health", tags=["Health"])
    def health_check():
        return {
            "status": "healthy",
            "service": "kroma-api",
            "version": APP_VERSION,
            "mode": "local-first-sqlite",
        }

    # Clean Architecture v1 endpoints (/v1/health, /v1/projects, /v1/presets, /v1/projects/{id}/assets, etc.)
    app.include_router(v1_router)

    # Proofing & Export endpoints under /v1
    app.include_router(proofing_router.router, prefix="/v1")
    app.include_router(export_router.router, prefix="/v1")

    # Studio & compatibility routers under /api/v1
    app.include_router(v1_health.router, prefix="/api/v1")
    app.include_router(legacy_projects_router.router, prefix="/api/v1")
    app.include_router(legacy_presets_router.router, prefix="/api/v1")
    app.include_router(proofing_router.router, prefix="/api/v1")
    app.include_router(export_router.router, prefix="/api/v1")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
