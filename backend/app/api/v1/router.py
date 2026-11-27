from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import assets, health, presets, projects

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(health.router)
v1_router.include_router(projects.router)
v1_router.include_router(assets.router)
v1_router.include_router(presets.router)
