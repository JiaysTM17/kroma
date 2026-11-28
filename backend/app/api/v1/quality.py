from __future__ import annotations

import io
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field

from app.api.deps import get_settings
from app.core.config import Settings
from app.services.quality_service import QualityInspectionService

router = APIRouter(prefix="/quality", tags=["Pre-Flight Quality Inspector"])
_quality_service = QualityInspectionService()


class ComplianceCheckItemSchema(BaseModel):
    check_id: str
    title: str
    status: str
    score: float
    message: str
    expected: str
    actual: str


class PreFlightReportSchema(BaseModel):
    marketplace: str
    preset_id: str
    is_compliant: bool
    overall_score: float
    checks: list[ComplianceCheckItemSchema]
    recommended_actions: list[str]


@router.post("/inspect", response_model=PreFlightReportSchema)
async def inspect_uploaded_image(
    file: UploadFile = File(...),
    marketplace: str = Query("shopee", description="Target marketplace (shopee, tiktok, lazada, amazon)"),
    preset_id: str | None = Query(None, description="Optional preset identifier"),
) -> PreFlightReportSchema:
    """Pre-flight quality compliance check on uploaded image bytes."""
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file payload")

    report = _quality_service.inspect_compliance(
        image_bytes=contents,
        marketplace=marketplace,
        preset_id=preset_id,
    )

    return PreFlightReportSchema(
        marketplace=report.marketplace,
        preset_id=report.preset_id,
        is_compliant=report.is_compliant,
        overall_score=report.overall_score,
        checks=[
            ComplianceCheckItemSchema(
                check_id=c.check_id,
                title=c.title,
                status=c.status,
                score=c.score,
                message=c.message,
                expected=c.expected,
                actual=c.actual,
            )
            for c in report.checks
        ],
        recommended_actions=report.recommended_actions,
    )
