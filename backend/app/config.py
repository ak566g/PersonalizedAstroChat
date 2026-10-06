from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    graph_backend: Literal["neo4j", "memory"] = "neo4j"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "astrochat-dev-pw"

    # While Neo4j is down, re-probe it at most this often instead of on every call.
    graph_retry_interval_seconds: float = 10.0

    llm_provider: Literal["mock", "anthropic"] = "mock"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5"
    anthropic_effort: Literal["low", "medium", "high"] = "medium"
    llm_timeout_seconds: float = 30.0

    data_dir: Path = Path("./data")
    context_top_n: int = 5
    short_term_turns: int = 10
    password_hash_iterations: int = 310_000

    # Only needed when the UI is served from a different origin; the Vite dev server proxies instead.
    cors_origins: list[str] = []

    @property
    def resolved_data_dir(self) -> Path:
        return self.data_dir.expanduser().resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()