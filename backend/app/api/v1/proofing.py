from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, BeforeValidator, Field

from app.api.deps import get_proofing_service
from app.domain.models import ProofingComment, ProofingEvent, ProofingSession
from app.services.proofing_service import ProofingService

router = APIRouter(tags=["proofing"])


def _reject_bool(value: Any) -> Any:
    if isinstance(value, bool):
        raise ValueError("Boolean value is not allowed for numeric field")
    return value


NoBoolFloat = Annotated[float, BeforeValidator(_reject_bool)]


class CreateProofingSessionRequest(BaseModel):
    project_id: str
    asset_id: str | None = None
    title: str
    client_name: str | None = "Client"
    allow_comments: bool = True
    expires_hours: NoBoolFloat | None = None


class SubmitFeedbackRequest(BaseModel):
    author: str
    action: str = "comment"
    comment: str | None = None
    body: str | None = None
    pin_x: NoBoolFloat | None = None
    pin_y: NoBoolFloat | None = None


class UpdateCommentRequest(BaseModel):
    body: str | None = None
    resolved: bool | None = None
    resolved_by: str | None = None


class ApplyDecisionRequest(BaseModel):
    actor: str
    decision: str
    note: str | None = None


class ProofingCommentResponse(BaseModel):
    id: str
    session_id: str
    author: str
    action: str
    body: str
    comment: str
    pin_x: float | None
    pin_y: float | None
    resolved: bool
    resolved_by: str | None
    resolved_at: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_domain(cls, item: ProofingComment) -> ProofingCommentResponse:
        return cls(
            id=item.id,
            session_id=item.session_id,
            author=item.author,
            action=item.action.value,
            body=item.body,
            comment=item.body,
            pin_x=item.pin_x,
            pin_y=item.pin_y,
            resolved=item.resolved,
            resolved_by=item.resolved_by,
            resolved_at=item.resolved_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


class ProofingEventResponse(BaseModel):
    id: str
    session_id: str
    actor: str
    event_type: str
    from_status: str | None
    to_status: str | None
    note: str
    payload: dict[str, Any]
    created_at: str

    @classmethod
    def from_domain(cls, event: ProofingEvent) -> ProofingEventResponse:
        return cls(
            id=event.id,
            session_id=event.session_id,
            actor=event.actor,
            event_type=event.event_type,
            from_status=event.from_status,
            to_status=event.to_status,
            note=event.note,
            payload=dict(event.payload),
            created_at=event.created_at,
        )


class ProofingSessionResponse(BaseModel):
    id: str
    project_id: str
    asset_id: str | None
    asset_url: str | None
    project_revision_id: str | None
    revision_stale: bool
    title: str
    client_name: str | None
    status: str
    allow_comments: bool
    approved_by: str | None
    approved_at: str | None
    expires_at: str | None
    revoked_at: str | None
    comments_count: int
    created_at: str
    updated_at: str

    @classmethod
    def from_domain_summary(
        cls,
        session: ProofingSession,
        *,
        asset_url: str | None,
        revision_stale: bool,
    ) -> ProofingSessionResponse:
        return cls(
            id=session.id,
            project_id=session.project_id,
            asset_id=session.asset_id,
            asset_url=asset_url,
            project_revision_id=session.project_revision_id,
            revision_stale=revision_stale,
            title=session.title,
            client_name=session.client_name,
            status=session.status.value,
            allow_comments=session.allow_comments,
            approved_by=session.approved_by,
            approved_at=session.approved_at,
            expires_at=session.expires_at,
            revoked_at=session.revoked_at,
            comments_count=len(session.comments),
            created_at=session.created_at,
            updated_at=session.updated_at,
        )


class ProofingSessionDetailResponse(ProofingSessionResponse):
    comments: list[ProofingCommentResponse] = Field(default_factory=list)
    feedback: list[ProofingCommentResponse] = Field(default_factory=list)
    events: list[ProofingEventResponse] = Field(default_factory=list)

    @classmethod
    def from_domain_detail(
        cls,
        session: ProofingSession,
        *,
        asset_url: str | None,
        revision_stale: bool,
    ) -> ProofingSessionDetailResponse:
        summary = ProofingSessionResponse.from_domain_summary(
            session, asset_url=asset_url, revision_stale=revision_stale
        )
        comment_items = [
            ProofingCommentResponse.from_domain(c) for c in session.comments
        ]
        event_items = [ProofingEventResponse.from_domain(e) for e in session.events]
        return cls(
            **summary.model_dump(),
            comments=comment_items,
            feedback=list(comment_items),
            events=event_items,
        )


class ProofingSessionListResponse(BaseModel):
    sessions: list[ProofingSessionResponse]
    total: int


class DeleteCommentResponse(BaseModel):
    deleted: bool
    comment_id: str


def _to_detail(
    service: ProofingService, session: ProofingSession
) -> ProofingSessionDetailResponse:
    asset_url, stale = service.compute_session_metadata(session)
    return ProofingSessionDetailResponse.from_domain_detail(
        session, asset_url=asset_url, revision_stale=stale
    )


@router.get("/projects/{project_id}/proofing", response_model=ProofingSessionListResponse)
def list_project_proofing_sessions(
    project_id: str,
    proofing_service: ProofingService = Depends(get_proofing_service),
) -> ProofingSessionListResponse:
    sessions = proofing_service.list_project_sessions(project_id)
    rendered: list[ProofingSessionResponse] = []
    for session in sessions:
        asset_url, stale = proofing_service.compute_session_metadata(session)
        rendered.append(
            ProofingSessionResponse.from_domain_summary(
                session, asset_url=asset_url, revision_stale=stale
            )
        )
    return ProofingSessionListResponse(sessions=rendered, total=len(rendered))


@router.post(
    "/proofing",
    response_model=ProofingSessionDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_proofing_session(
    body: CreateProofingSessionRequest,
    proofing_service: ProofingService = Depends(get_proofing_service),
) -> ProofingSessionDetailResponse:
    session = proofing_service.create_session(
        project_id=body.project_id,
        asset_id=body.asset_id,
        title=body.title,
        client_name=body.client_name,
        allow_comments=body.allow_comments,
        expires_hours=body.expires_hours,
    )
    return _to_detail(proofing_service, session)


@router.get("/proofing/{session_id}", response_model=ProofingSessionDetailResponse)
def get_proofing_session(
    session_id: str,
    proofing_service: ProofingService = Depends(get_proofing_service),
) -> ProofingSessionDetailResponse:
    session = proofing_service.get_session(session_id)
    return _to_detail(proofing_service, session)


@router.post("/proofing/{session_id}/feedback", response_model=ProofingSessionDetailResponse)
def submit_proofing_feedback(
    session_id: str,
    body: SubmitFeedbackRequest,
    proofing_service: ProofingService = Depends(get_proofing_service),
) -> ProofingSessionDetailResponse:
    text = body.comment if body.comment is not None else (body.body or "")
    session = proofing_service.submit_feedback(
        session_id,
        author=body.author,
        action=body.action,
        comment=text,
        pin_x=body.pin_x,
        pin_y=body.pin_y,
    )
    return _to_detail(proofing_service, session)


@router.post("/proofing/{session_id}/comments", response_model=ProofingSessionDetailResponse)
def add_proofing_comment_alias(
    session_id: str,
    body: SubmitFeedbackRequest,
    proofing_service: ProofingService = Depends(get_proofing_service),
) -> ProofingSessionDetailResponse:
    text = body.body if body.body is not None else (body.comment or "")
    session = proofing_service.submit_feedback(
        session_id,
        author=body.author,
        action=body.action,
        comment=text,
        pin_x=body.pin_x,
        pin_y=body.pin_y,
    )
    return _to_detail(proofing_service, session)


@router.patch(
    "/proofing/{session_id}/comments/{comment_id}",
    response_model=ProofingCommentResponse,
)
def update_proofing_comment(
    session_id: str,
    comment_id: str,
    body: UpdateCommentRequest,
    proofing_service: ProofingService = Depends(get_proofing_service),
) -> ProofingCommentResponse:
    updated = proofing_service.update_comment(
        session_id,
        comment_id,
        body=body.body,
        resolved=body.resolved,
        resolved_by=body.resolved_by,
        fields_set=set(body.model_fields_set),
    )
    return ProofingCommentResponse.from_domain(updated)


@router.delete(
    "/proofing/{session_id}/comments/{comment_id}",
    response_model=DeleteCommentResponse,
)
def delete_proofing_comment(
    session_id: str,
    comment_id: str,
    proofing_service: ProofingService = Depends(get_proofing_service),
) -> DeleteCommentResponse:
    proofing_service.delete_comment(session_id, comment_id)
    return DeleteCommentResponse(deleted=True, comment_id=comment_id)


@router.post("/proofing/{session_id}/decision", response_model=ProofingSessionDetailResponse)
def apply_proofing_decision(
    session_id: str,
    body: ApplyDecisionRequest,
    proofing_service: ProofingService = Depends(get_proofing_service),
) -> ProofingSessionDetailResponse:
    session = proofing_service.apply_decision(
        session_id,
        actor=body.actor,
        decision=body.decision,
        note=body.note,
    )
    return _to_detail(proofing_service, session)
