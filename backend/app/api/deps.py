from dataclasses import dataclass
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.auth.service import AuthService, hash_token
from app.brain.resilient_repository import ResilientGraphRepository, ScopedGraph
from app.chat.service import ChatService
from app.config import Settings
from app.llm.base import LLMProvider
from app.memory.short_term import ShortTermStore


@dataclass
class Container:
    settings: Settings
    graph: ResilientGraphRepository
    short_term: ShortTermStore
    auth: AuthService
    chat: ChatService
    llm: LLMProvider


@dataclass
class CurrentUser:
    user_id: str
    token_hash: str


_bearer = HTTPBearer(auto_error=False)


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_graph(container: Container = Depends(get_container)) -> ScopedGraph:
    # One scoped view per request, so degraded reflects only this request's graph calls.
    return container.graph.scoped()


def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    container: Container = Depends(get_container),
) -> CurrentUser:
    token = credentials.credentials if credentials else None
    user_id = container.auth.user_for_token(token) if token else None
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid session token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CurrentUser(user_id=user_id, token_hash=hash_token(token))