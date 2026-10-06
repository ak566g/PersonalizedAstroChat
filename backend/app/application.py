import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import routes_auth, routes_chat, routes_health, routes_profile, routes_sessions
from app.api.deps import Container
from app.auth.service import AuthService
from app.brain.in_memory_repository import InMemoryGraphRepository
from app.brain.repository import GraphRepository
from app.brain.resilient_repository import ResilientGraphRepository
from app.chat.service import ChatService
from app.config import Settings, get_settings
from app.llm.base import LLMProvider
from app.llm.factory import get_provider
from app.memory.context_selector import ContextSelector
from app.memory.extractor import MemoryExtractor
from app.memory.short_term import ShortTermStore
from app.storage.auth_store import AuthStore

logger = logging.getLogger(__name__)


def _build_primary_graph(settings: Settings) -> GraphRepository:
    if settings.graph_backend == "memory":
        return InMemoryGraphRepository()
    from app.brain.neo4j_repository import Neo4jGraphRepository
    return Neo4jGraphRepository(
        settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password
    )


def create_app(
    settings: Settings | None = None,
    primary_graph: GraphRepository | None = None,
    llm: LLMProvider | None = None,
) -> FastAPI:
    """Build the app. Tests inject primary_graph / llm; production builds both from settings."""
    settings = settings or get_settings()
    data_dir = settings.resolved_data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    primary = primary_graph or _build_primary_graph(settings)
    graph = ResilientGraphRepository(
        primary=primary,
        fallback=InMemoryGraphRepository(),
        primary_name="memory" if isinstance(primary, InMemoryGraphRepository) else "neo4j",
        retry_interval=settings.graph_retry_interval_seconds,
    )
    llm = llm or get_provider(settings)
    short_term = ShortTermStore(data_dir / "short_term.db")

    container = Container(
        settings=settings,
        graph=graph,
        short_term=short_term,
        auth=AuthService(
            AuthStore(data_dir / "auth.db"),
            settings.password_hash_iterations,
        ),
        chat=ChatService(
            short_term=short_term,
            selector=ContextSelector(top_n=settings.context_top_n),
            extractor=MemoryExtractor(),
            llm=llm,
            short_term_turns=settings.short_term_turns,
        ),
        llm=llm,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        graph.initialize()  # constraints + LifeArea seed; falls back if Neo4j is down
        logger.info("Graph backend: %s, LLM provider: %s", graph.backend_name, llm.name)
        yield
        if hasattr(primary, "close"):
            primary.close()

    app = FastAPI(title="PersonalizedAstroChat", version="1.0.0", lifespan=lifespan)
    app.state.container = container

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["*"],
            allow_headers=["Authorization", "Content-Type"],
        )

    routers = (routes_auth, routes_profile, routes_sessions, routes_chat, routes_health)
    for router in (module.router for module in routers):
        app.include_router(router)

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app