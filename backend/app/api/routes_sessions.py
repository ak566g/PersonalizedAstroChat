from dataclasses import asdict

from fastapi import APIRouter, Depends, Path

from app.api.deps import Container, CurrentUser, get_container, require_user
from app.api.schemas import MessageOut, SessionHistoryResponse, SessionOut, SessionsResponse

router = APIRouter(prefix="/me/sessions", tags=["sessions"])

_SESSION_ID = Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:\-]+$")


@router.get("", response_model=SessionsResponse)
def list_sessions(
    user: CurrentUser = Depends(require_user), container: Container = Depends(get_container)
) -> SessionsResponse:
    summaries = container.short_term.sessions(user.user_id)
    return SessionsResponse(sessions=[SessionOut(**asdict(s)) for s in summaries])


@router.get("/{session_id}/messages", response_model=SessionHistoryResponse)
def session_history(
    session_id: str = _SESSION_ID,
    user: CurrentUser = Depends(require_user),
    container: Container = Depends(get_container),
) -> SessionHistoryResponse:
    # Scoped to the caller: another user's session_id simply returns no messages.
    messages = container.short_term.history(user.user_id, session_id)
    return SessionHistoryResponse(session_id=session_id, messages=[MessageOut(**asdict(m)) for m in messages])