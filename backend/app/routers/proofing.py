from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import get_proofing_service
from app.api.v1.proofing import (
    ApplyDecisionRequest,
    CreateProofingSessionRequest,
    DeleteCommentResponse,
    ProofingCommentResponse,
    ProofingSessionDetailResponse,
    SubmitFeedbackRequest,
    UpdateCommentRequest,
    _to_detail,
)
from app.services.proofing_service import ProofingService

router = APIRouter(prefix="/proofing", tags=["Client Proofing"])


@router.post(
    "",
    response_model=ProofingSessionDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_proofing_session(
    data: CreateProofingSessionRequest,
    proofing_service: ProofingService = Depends(get_proofing_service),
) -> ProofingSessionDetailResponse:
    session = proofing_service.create_session(
        project_id=data.project_id,
        asset_id=data.asset_id,
        title=data.title,
        client_name=data.client_name,
        allow_comments=data.allow_comments,
        expires_hours=data.expires_hours,
    )
    return _to_detail(proofing_service, session)


@router.get("/{session_id}", response_model=ProofingSessionDetailResponse)
def get_proofing_session(
    session_id: str,
    proofing_service: ProofingService = Depends(get_proofing_service),
) -> ProofingSessionDetailResponse:
    session = proofing_service.get_session(session_id)
    return _to_detail(proofing_service, session)


@router.post("/{session_id}/feedback", response_model=ProofingSessionDetailResponse)
def submit_feedback(
    session_id: str,
    data: SubmitFeedbackRequest,
    proofing_service: ProofingService = Depends(get_proofing_service),
) -> ProofingSessionDetailResponse:
    text = data.comment if data.comment is not None else (data.body or "")
    session = proofing_service.submit_feedback(
        session_id,
        author=data.author,
        action=data.action,
        comment=text,
        pin_x=data.pin_x,
        pin_y=data.pin_y,
    )
    return _to_detail(proofing_service, session)


@router.post("/{session_id}/comments", response_model=ProofingSessionDetailResponse)
def submit_comment_alias(
    session_id: str,
    data: SubmitFeedbackRequest,
    proofing_service: ProofingService = Depends(get_proofing_service),
) -> ProofingSessionDetailResponse:
    text = data.body if data.body is not None else (data.comment or "")
    session = proofing_service.submit_feedback(
        session_id,
        author=data.author,
        action=data.action,
        comment=text,
        pin_x=data.pin_x,
        pin_y=data.pin_y,
    )
    return _to_detail(proofing_service, session)


@router.patch(
    "/{session_id}/comments/{comment_id}",
    response_model=ProofingCommentResponse,
)
def update_comment(
    session_id: str,
    comment_id: str,
    data: UpdateCommentRequest,
    proofing_service: ProofingService = Depends(get_proofing_service),
) -> ProofingCommentResponse:
    updated = proofing_service.update_comment(
        session_id,
        comment_id,
        body=data.body,
        resolved=data.resolved,
        resolved_by=data.resolved_by,
        fields_set=set(data.model_fields_set),
    )
    return ProofingCommentResponse.from_domain(updated)


@router.delete(
    "/{session_id}/comments/{comment_id}",
    response_model=DeleteCommentResponse,
)
def delete_comment(
    session_id: str,
    comment_id: str,
    proofing_service: ProofingService = Depends(get_proofing_service),
) -> DeleteCommentResponse:
    proofing_service.delete_comment(session_id, comment_id)
    return DeleteCommentResponse(deleted=True, comment_id=comment_id)


@router.post("/{session_id}/decision", response_model=ProofingSessionDetailResponse)
def apply_decision(
    session_id: str,
    data: ApplyDecisionRequest,
    proofing_service: ProofingService = Depends(get_proofing_service),
) -> ProofingSessionDetailResponse:
    session = proofing_service.apply_decision(
        session_id,
        actor=data.actor,
        decision=data.decision,
        note=data.note,
    )
    return _to_detail(proofing_service, session)
