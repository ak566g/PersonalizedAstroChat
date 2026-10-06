from fastapi import APIRouter, Depends

from app.api.deps import Container, get_container, get_graph
from app.api.schemas import HealthResponse
from app.brain.resilient_repository import ScopedGraph

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(container: Container = Depends(get_container), graph: ScopedGraph = Depends(get_graph)) -> HealthResponse:
    graph.ping()  # probes the primary (subject to the retry interval) and updates backend status
    return HealthResponse(
        status="degraded" if graph.degraded else "ok",
        graph_backend=container.graph.backend_name,
        llm_provider=container.llm.name,
    )