from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.core.config import Settings
from app.services.asset_service import AssetService
from app.services.batch_worker import BatchWorkerService
from app.services.preset_service import PresetService
from app.services.project_service import ProjectService
from app.services.proofing_service import ProofingService
from app.storage.ports import BlobStorePort, DatabasePort


@dataclass
class AppContainer:
    settings: Settings
    repo: DatabasePort
    blob_store: BlobStorePort
    project_service: ProjectService
    asset_service: AssetService
    preset_service: PresetService
    batch_worker: BatchWorkerService
    proofing_service: ProofingService


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def get_settings(request: Request) -> Settings:
    return get_container(request).settings


def get_repo(request: Request) -> DatabasePort:
    return get_container(request).repo


def get_project_service(request: Request) -> ProjectService:
    return get_container(request).project_service


def get_asset_service(request: Request) -> AssetService:
    return get_container(request).asset_service


def get_preset_service(request: Request) -> PresetService:
    return get_container(request).preset_service


def get_batch_worker(request: Request) -> BatchWorkerService:
    return get_container(request).batch_worker


def get_proofing_service(request: Request) -> ProofingService:
    return get_container(request).proofing_service
