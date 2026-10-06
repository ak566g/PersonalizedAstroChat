from fastapi import APIRouter, Depends

from app.api.deps import Container, CurrentUser, get_container, get_graph, require_user
from app.api.schemas import ChatRequest, ChatResponse, MemoryUpdateOut
from app.brain.resilient_repository import ScopedGraph

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    user: CurrentUser = Depends(require_user),
    container: Container = Depends(get_container),
    graph: ScopedGraph = Depends(get_graph),
) -> ChatResponse:
    # user_id always comes from the session token; a user_id in the body is ignored.
    result = container.chat.handle_message(user.user_id, body.session_id, body.message, graph)
    return ChatResponse(
        response=result.response,
        user_id=user.user_id,
        session_id=body.session_id,
        context_used=result.context_used,
        intent=result.intent,
        memory_updates=[
            MemoryUpdateOut(action=u.action, type=u.fact_type, label=u.label, life_area=u.life_area,
                            details=u.details)
            for u in result.memory_updates
        ],
        degraded=result.degraded,
    )