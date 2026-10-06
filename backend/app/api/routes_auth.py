from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import Container, CurrentUser, get_container, get_graph, require_user
from app.api.schemas import LoginRequest, LoginResponse, SignupRequest, SignupResponse
from app.auth.service import InvalidCredentials
from app.brain.resilient_repository import ScopedGraph
from app.storage.auth_store import EmailAlreadyRegistered

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=SignupResponse)
def signup(
    body: SignupRequest,
    container: Container = Depends(get_container),
    graph: ScopedGraph = Depends(get_graph),
) -> SignupResponse:
    try:
        result = container.auth.signup(body.email, body.password, body.profile_values(), graph)
    except EmailAlreadyRegistered:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    return SignupResponse(session_token=result.session_token, user_id=result.user_id, degraded=graph.degraded)


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, container: Container = Depends(get_container)) -> LoginResponse:
    try:
        token = container.auth.login(body.email, body.password)
    except InvalidCredentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return LoginResponse(session_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: CurrentUser = Depends(require_user), container: Container = Depends(get_container)) -> Response:
    container.auth.logout(user.token_hash)
    return Response(status_code=status.HTTP_204_NO_CONTENT)