from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, BeforeValidator, Field

from app.api.deps import get_batch_worker
from app.domain.enums import BatchStatus
from app.domain.models import BatchJob, BatchJobItem, BatchRecipeInput
from app.services.batch_worker import BatchWorkerService

router = APIRouter(tags=["batches"])


def _reject_bool(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("Boolean value is not allowed for numeric field")
    return value


NoBoolInt = Annotated[int, BeforeValidator(_reject_bool)]
NoBoolFloat = Annotated[float, BeforeValidator(_reject_bool)]


class BatchAdjustmentsRequest(BaseModel):
    brightness: NoBoolFloat = 1.0
    contrast: NoBoolFloat = 1.0
    saturation: NoBoolFloat = 1.0
    sharpness: NoBoolFloat = 1.0
    exposure: NoBoolFloat | None = None


class BatchRecipeRequest(BaseModel):
    preset_id: str
    format: str | None = None
    quality: NoBoolInt = 90
    background_rgb: list[NoBoolInt] | None = None
    subject_area_ratio: NoBoolFloat | None = None
    include_shadow: bool | None = None
    watermark_text: str | None = None


class CreateBatchRequest(BaseModel):
    project_id: str
    asset_ids: list[str]
    recipes: list[BatchRecipeRequest]
    include_shadow: bool = False
    watermark_text: str | None = None
    adjustments: BatchAdjustmentsRequest | None = None
    prefer_ai_output: bool = True


class BatchJobItemResponse(BaseModel):
    id: str
    job_id: str
    seq: int
    asset_id: str
    source_asset_id: str
    preset_id: str
    preset_version: str
    format: str
    quality: int
    recipe_snapshot: dict[str, Any]
    status: str
    output_filename: str | None
    output_byte_size: int
    output_width: int
    output_height: int
    error_code: str | None
    error_message: str | None
    attempts: int
    created_at: str
    started_at: str | None
    completed_at: str | None

    @classmethod
    def from_domain(cls, item: BatchJobItem) -> BatchJobItemResponse:
        return cls(
            id=item.id,
            job_id=item.job_id,
            seq=item.seq,
            asset_id=item.asset_id,
            source_asset_id=item.source_asset_id,
            preset_id=item.preset_id,
            preset_version=item.preset_version,
            format=item.format,
            quality=item.quality,
            recipe_snapshot=dict(item.recipe_snapshot),
            status=item.status.value,
            output_filename=item.output_filename,
            output_byte_size=item.output_byte_size,
            output_width=item.output_width,
            output_height=item.output_height,
            error_code=item.error_code,
            error_message=item.error_message,
            attempts=item.attempts,
            created_at=item.created_at,
            started_at=item.started_at,
            completed_at=item.completed_at,
        )


class BatchJobSummaryResponse(BaseModel):
    job_id: str
    project_id: str
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    progress: float
    download_url: str | None
    error_message: str | None
    created_at: str
    started_at: str | None
    completed_at: str | None

    @classmethod
    def from_domain(cls, job: BatchJob) -> BatchJobSummaryResponse:
        ready = (
            job.status in (BatchStatus.COMPLETED, BatchStatus.PARTIAL_FAILED)
            and bool(job.zip_filename)
        )
        return cls(
            job_id=job.id,
            project_id=job.project_id,
            status=job.status.value,
            total_items=job.total_items,
            completed_items=job.completed_items,
            failed_items=job.failed_items,
            progress=job.progress,
            download_url=f"/v1/batches/{job.id}/download" if ready else None,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )


class BatchJobDetailResponse(BatchJobSummaryResponse):
    items: list[BatchJobItemResponse] = Field(default_factory=list)

    @classmethod
    def from_domain_detail(
        cls, job: BatchJob, items: list[BatchJobItem]
    ) -> BatchJobDetailResponse:
        summary = BatchJobSummaryResponse.from_domain(job)
        return cls(
            **summary.model_dump(),
            items=[BatchJobItemResponse.from_domain(item) for item in items],
        )


class BatchJobListResponse(BaseModel):
    jobs: list[BatchJobSummaryResponse]
    total: int


@router.post(
    "/batches",
    response_model=BatchJobDetailResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_batch_job(
    body: CreateBatchRequest,
    batch_worker: BatchWorkerService = Depends(get_batch_worker),
) -> BatchJobDetailResponse:
    recipes = [
        BatchRecipeInput(
            preset_id=r.preset_id,
            format=r.format,
            quality=r.quality,
            background_rgb=tuple(r.background_rgb) if r.background_rgb is not None else None,  # type: ignore[arg-type]
            subject_area_ratio=r.subject_area_ratio,
            include_shadow=r.include_shadow,
            watermark_text=r.watermark_text,
        )
        for r in body.recipes
    ]
    job, items = batch_worker.submit_batch_job(
        project_id=body.project_id,
        asset_ids=body.asset_ids,
        recipes=recipes,
        include_shadow=body.include_shadow,
        watermark_text=body.watermark_text,
        adjustments=body.adjustments.model_dump() if body.adjustments is not None else None,
        prefer_ai_output=body.prefer_ai_output,
    )
    return BatchJobDetailResponse.from_domain_detail(job, items)


@router.get("/projects/{project_id}/batches", response_model=BatchJobListResponse)
def list_project_batches(
    project_id: str,
    batch_worker: BatchWorkerService = Depends(get_batch_worker),
) -> BatchJobListResponse:
    jobs = batch_worker.list_project_batches(project_id)
    return BatchJobListResponse(
        jobs=[BatchJobSummaryResponse.from_domain(j) for j in jobs],
        total=len(jobs),
    )


@router.get("/batches/{job_id}", response_model=BatchJobDetailResponse)
def get_batch_job(
    job_id: str,
    batch_worker: BatchWorkerService = Depends(get_batch_worker),
) -> BatchJobDetailResponse:
    job, items = batch_worker.get_batch_job(job_id)
    return BatchJobDetailResponse.from_domain_detail(job, items)


@router.post("/batches/{job_id}/cancel", response_model=BatchJobDetailResponse)
def cancel_batch_job(
    job_id: str,
    batch_worker: BatchWorkerService = Depends(get_batch_worker),
) -> BatchJobDetailResponse:
    job, items = batch_worker.cancel_batch_job(job_id)
    return BatchJobDetailResponse.from_domain_detail(job, items)


@router.post(
    "/batches/{job_id}/retry",
    response_model=BatchJobDetailResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_batch_job(
    job_id: str,
    batch_worker: BatchWorkerService = Depends(get_batch_worker),
) -> BatchJobDetailResponse:
    job, items = batch_worker.retry_batch_job(job_id)
    return BatchJobDetailResponse.from_domain_detail(job, items)


@router.get("/batches/{job_id:path}/download")
def download_batch_zip(
    job_id: str,
    batch_worker: BatchWorkerService = Depends(get_batch_worker),
) -> FileResponse:
    job, zip_path = batch_worker.get_download_zip_path(job_id)
    return FileResponse(
        path=str(zip_path),
        filename=job.zip_filename or f"{job.id}.zip",
        media_type="application/zip",
    )
