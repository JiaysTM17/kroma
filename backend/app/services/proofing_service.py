from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.errors import ConflictError, ForbiddenError, GoneError, NotFoundError, ValidationAppError
from app.core.ids import new_id, utc_now_iso
from app.domain.enums import ProofingAction, ProofingDecision, ProofingStatus
from app.domain.models import ProofingComment, ProofingEvent, ProofingSession
from app.domain.rules import (
    is_revision_stale,
    is_session_expired,
    next_status_for_action,
    next_status_for_decision,
    validate_expires_hours,
    validate_pin_coordinates,
    validate_proofing_actor,
    validate_proofing_comment_body,
    validate_proofing_title,
)
from app.storage.ports import DatabasePort


class ProofingService:
    def __init__(self, repo: DatabasePort) -> None:
        self._repo = repo

    def _assert_session_active(self, session: ProofingSession) -> None:
        if session.revoked_at is not None:
            raise GoneError("Proofing session has been revoked")
        if is_session_expired(session.expires_at, datetime.now(timezone.utc)):
            raise GoneError("Proofing session has expired")

    def compute_session_metadata(
        self, session: ProofingSession
    ) -> tuple[str | None, bool]:
        asset_url = f"/v1/assets/{session.asset_id}/file" if session.asset_id else None
        state = self._repo.get_project_state(session.project_id)
        current_rev = state.revision_id if state is not None else None
        stale = is_revision_stale(session.project_revision_id, current_rev)
        return asset_url, stale

    def create_session(
        self,
        *,
        project_id: str,
        title: str,
        asset_id: str | None = None,
        client_name: str | None = "Client",
        allow_comments: bool = True,
        expires_hours: float | int | None = None,
    ) -> ProofingSession:
        project = self._repo.get_project(project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' not found")

        clean_asset_id: str | None = None
        if asset_id is not None and str(asset_id).strip():
            clean_asset_id = str(asset_id).strip()
            asset = self._repo.get_asset(clean_asset_id)
            if asset is None:
                raise NotFoundError(f"Asset '{clean_asset_id}' not found")
            if asset.project_id != project_id:
                raise ValidationAppError(
                    f"Asset '{clean_asset_id}' does not belong to project '{project_id}'"
                )

        try:
            clean_title = validate_proofing_title(title)
            clean_client = (
                validate_proofing_actor(client_name, default="Client", field_name="client_name")
                if client_name is not None
                else None
            )
            clean_expires = validate_expires_hours(expires_hours)
        except ValueError as exc:
            raise ValidationAppError(str(exc)) from exc

        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat().replace("+00:00", "Z")
        expires_at = (
            (now_dt + timedelta(hours=clean_expires)).isoformat().replace("+00:00", "Z")
            if clean_expires is not None
            else None
        )

        state = self._repo.get_project_state(project_id)
        project_revision_id = state.revision_id if state is not None else None

        session_id = f"proof_{new_id().replace('-', '')[:12]}"
        session = ProofingSession(
            id=session_id,
            project_id=project_id,
            asset_id=clean_asset_id,
            project_revision_id=project_revision_id,
            title=clean_title,
            client_name=clean_client,
            status=ProofingStatus.PENDING,
            allow_comments=bool(allow_comments),
            approved_by=None,
            approved_at=None,
            expires_at=expires_at,
            revoked_at=None,
            created_at=now_iso,
            updated_at=now_iso,
            comments=(),
            events=(),
        )
        initial_event = ProofingEvent(
            id=new_id(),
            session_id=session_id,
            actor=clean_client or "system",
            event_type="session_created",
            from_status=None,
            to_status=ProofingStatus.PENDING.value,
            note="Proofing session created",
            payload={
                "asset_id": clean_asset_id,
                "project_revision_id": project_revision_id,
                "allow_comments": bool(allow_comments),
                "expires_at": expires_at,
            },
            created_at=now_iso,
        )
        return self._repo.create_proofing_session(session, initial_event)

    def get_session(self, session_id: str) -> ProofingSession:
        session = self._repo.get_proofing_session(session_id)
        if session is None:
            raise NotFoundError(f"Proofing session '{session_id}' not found")
        return session

    def list_project_sessions(self, project_id: str) -> list[ProofingSession]:
        if self._repo.get_project(project_id) is None:
            raise NotFoundError(f"Project '{project_id}' not found")
        return self._repo.list_project_proofing_sessions(project_id)

    def submit_feedback(
        self,
        session_id: str,
        *,
        author: str,
        action: str | ProofingAction,
        comment: str,
        pin_x: float | None = None,
        pin_y: float | None = None,
    ) -> ProofingSession:
        session = self.get_session(session_id)
        self._assert_session_active(session)

        try:
            parsed_action = (
                action
                if isinstance(action, ProofingAction)
                else ProofingAction(str(action).strip().lower())
            )
        except ValueError as exc:
            allowed = ", ".join(a.value for a in ProofingAction)
            raise ValidationAppError(
                f"Invalid action '{action}'; expected one of: {allowed}"
            ) from exc

        try:
            clean_author = validate_proofing_actor(author, field_name="author")
            clean_body = validate_proofing_comment_body(
                comment, allow_empty=(parsed_action != ProofingAction.COMMENT)
            )
            clean_pin_x, clean_pin_y = validate_pin_coordinates(pin_x, pin_y)
        except ValueError as exc:
            raise ValidationAppError(str(exc)) from exc

        if parsed_action == ProofingAction.COMMENT and not session.allow_comments:
            raise ForbiddenError("Comments are disabled for this proofing session")

        try:
            next_status = next_status_for_action(session.status, parsed_action)
        except ValueError as exc:
            raise ConflictError(str(exc)) from exc

        now = utc_now_iso()
        approved_by = session.approved_by
        approved_at = session.approved_at
        if parsed_action == ProofingAction.APPROVE:
            approved_by = clean_author
            approved_at = now
        elif parsed_action == ProofingAction.REQUEST_CHANGE:
            approved_by = None
            approved_at = None

        comment_id = f"fb_{new_id().replace('-', '')[:8]}"
        new_comment = ProofingComment(
            id=comment_id,
            session_id=session_id,
            author=clean_author,
            action=parsed_action,
            body=clean_body,
            pin_x=clean_pin_x,
            pin_y=clean_pin_y,
            resolved=False,
            resolved_by=None,
            resolved_at=None,
            created_at=now,
            updated_at=now,
        )
        event = ProofingEvent(
            id=new_id(),
            session_id=session_id,
            actor=clean_author,
            event_type="feedback_submitted",
            from_status=session.status.value,
            to_status=next_status.value,
            note=clean_body,
            payload={
                "comment_id": comment_id,
                "action": parsed_action.value,
                "pin_x": clean_pin_x,
                "pin_y": clean_pin_y,
            },
            created_at=now,
        )
        return self._repo.add_proofing_comment(
            session_id,
            new_comment,
            new_status=next_status,
            approved_by=approved_by,
            approved_at=approved_at,
            updated_at=now,
            event=event,
        )

    def update_comment(
        self,
        session_id: str,
        comment_id: str,
        *,
        body: str | None = None,
        resolved: bool | None = None,
        resolved_by: str | None = None,
        fields_set: set[str] | None = None,
    ) -> ProofingComment:
        session = self.get_session(session_id)
        self._assert_session_active(session)

        existing = self._repo.get_proofing_comment(session_id, comment_id)
        if existing is None:
            raise NotFoundError(f"Comment '{comment_id}' not found in session '{session_id}'")

        supplied = fields_set if fields_set is not None else {
            k
            for k, v in (("body", body), ("resolved", resolved), ("resolved_by", resolved_by))
            if v is not None
        }

        if not (supplied & {"body", "resolved"}):
            raise ValidationAppError("At least one field (body or resolved) must be supplied")

        next_body = existing.body
        if "body" in supplied:
            try:
                next_body = validate_proofing_comment_body(body, allow_empty=False)
            except ValueError as exc:
                raise ValidationAppError(str(exc)) from exc

        now = utc_now_iso()
        next_resolved = existing.resolved
        next_resolved_by = existing.resolved_by
        next_resolved_at = existing.resolved_at
        actor = existing.author

        if "resolved_by" in supplied and resolved_by is not None:
            try:
                actor = validate_proofing_actor(resolved_by, field_name="resolved_by")
            except ValueError as exc:
                raise ValidationAppError(str(exc)) from exc

        if "resolved" in supplied:
            if not isinstance(resolved, bool):
                raise ValidationAppError("resolved must be a boolean")
            next_resolved = resolved
            if resolved:
                next_resolved_by = actor if "resolved_by" in supplied else (existing.resolved_by or "reviewer")
                next_resolved_at = now
            else:
                next_resolved_by = None
                next_resolved_at = None

        updated_comment = ProofingComment(
            id=existing.id,
            session_id=existing.session_id,
            author=existing.author,
            action=existing.action,
            body=next_body,
            pin_x=existing.pin_x,
            pin_y=existing.pin_y,
            resolved=next_resolved,
            resolved_by=next_resolved_by,
            resolved_at=next_resolved_at,
            created_at=existing.created_at,
            updated_at=now,
        )
        event = ProofingEvent(
            id=new_id(),
            session_id=session_id,
            actor=next_resolved_by or actor,
            event_type="comment_updated",
            from_status=session.status.value,
            to_status=session.status.value,
            note=f"Updated comment '{comment_id}'",
            payload={
                "comment_id": comment_id,
                "resolved": next_resolved,
                "body_updated": "body" in supplied,
            },
            created_at=now,
        )
        return self._repo.update_proofing_comment(
            updated_comment, updated_at=now, event=event
        )

    def delete_comment(
        self,
        session_id: str,
        comment_id: str,
        *,
        actor: str = "reviewer",
    ) -> None:
        session = self.get_session(session_id)
        self._assert_session_active(session)

        now = utc_now_iso()
        event = ProofingEvent(
            id=new_id(),
            session_id=session_id,
            actor=actor,
            event_type="comment_deleted",
            from_status=session.status.value,
            to_status=session.status.value,
            note=f"Deleted comment '{comment_id}'",
            payload={"comment_id": comment_id},
            created_at=now,
        )
        deleted = self._repo.delete_proofing_comment(
            session_id, comment_id, updated_at=now, event=event
        )
        if not deleted:
            raise NotFoundError(f"Comment '{comment_id}' not found in session '{session_id}'")

    def apply_decision(
        self,
        session_id: str,
        *,
        actor: str,
        decision: str | ProofingDecision,
        note: str | None = None,
    ) -> ProofingSession:
        session = self.get_session(session_id)
        self._assert_session_active(session)

        try:
            parsed_decision = (
                decision
                if isinstance(decision, ProofingDecision)
                else ProofingDecision(str(decision).strip().lower())
            )
        except ValueError as exc:
            allowed = ", ".join(d.value for d in ProofingDecision)
            raise ValidationAppError(
                f"Invalid decision '{decision}'; expected one of: {allowed}"
            ) from exc

        try:
            clean_actor = validate_proofing_actor(actor, field_name="actor")
            clean_note = validate_proofing_comment_body(note, allow_empty=True)
        except ValueError as exc:
            raise ValidationAppError(str(exc)) from exc

        try:
            next_status = next_status_for_decision(session.status, parsed_decision)
        except ValueError as exc:
            raise ConflictError(str(exc)) from exc

        now = utc_now_iso()
        approved_by = session.approved_by
        approved_at = session.approved_at
        revoked_at = session.revoked_at

        if parsed_decision == ProofingDecision.APPROVE:
            approved_by = clean_actor
            approved_at = now
        elif parsed_decision in (
            ProofingDecision.REQUEST_CHANGE,
            ProofingDecision.REOPEN,
        ):
            approved_by = None
            approved_at = None
        elif parsed_decision == ProofingDecision.REVOKE:
            revoked_at = now

        event_type = (
            "session_revoked"
            if parsed_decision == ProofingDecision.REVOKE
            else f"decision_{parsed_decision.value}"
        )
        event = ProofingEvent(
            id=new_id(),
            session_id=session_id,
            actor=clean_actor,
            event_type=event_type,
            from_status=session.status.value,
            to_status=next_status.value,
            note=clean_note,
            payload={"decision": parsed_decision.value},
            created_at=now,
        )
        return self._repo.apply_proofing_decision(
            session_id,
            new_status=next_status,
            approved_by=approved_by,
            approved_at=approved_at,
            revoked_at=revoked_at,
            updated_at=now,
            event=event,
        )
