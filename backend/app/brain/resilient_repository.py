import logging
import threading
import time
from collections.abc import Callable, Sequence
from typing import Any
from app.brain.models import (
    CandidateCorrection,
    CandidateFact,
    Fact,
    FactType,
    MemoryUpdate,
    Profile,
)
from app.brain.repository import GraphRepository, GraphUnavailableError

logger = logging.getLogger(__name__)


class ResilientGraphRepository:
    """Routes every call to the primary graph, falling back to one shared in-memory graph.
    While the primary is down it is re-probed at most once per retry interval. The first
    successful call after an outage re-runs initialize() so constraints and LifeArea seed
    data exist even if the primary was unreachable at startup.
    """

    def __init__(
        self,
        primary: GraphRepository | None,
        fallback: GraphRepository,
        primary_name: str = "neo4j",
        retry_interval: float = 10.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._primary_name = primary_name
        self._retry_interval = retry_interval
        self._clock = clock
        self._lock = threading.Lock()
        self._primary_down = primary is None
        self._last_failure = float("-inf")

    @property
    def backend_name(self) -> str:
        return "in_memory" if self._primary_down else self._primary_name

    @property
    def is_degraded(self) -> bool:
        return self._primary_down

    def call(self, method: str, *args, **kwargs) -> tuple[Any, bool]:
        """Returns (result, served_by_fallback)."""
        if self._should_try_primary():
            try:
                result = getattr(self._primary, method)(*args, **kwargs)
            except GraphUnavailableError as exc:
                self._mark_down(method, exc)
            else:
                self._mark_up()
                return result, False
        return getattr(self._fallback, method)(*args, **kwargs), True

    def initialize(self) -> None:
        self._fallback.initialize()
        self.call("initialize")

    def scoped(self) -> "ScopedGraph":
        return ScopedGraph(self)

    def _should_try_primary(self) -> bool:
        if self._primary is None:
            return False
        with self._lock:
            return (
                not self._primary_down
                or self._clock() - self._last_failure >= self._retry_interval
            )

    def _mark_down(self, method: str, exc: Exception) -> None:
        with self._lock:
            was_down = self._primary_down
            self._primary_down = True
            self._last_failure = self._clock()
            if not was_down:
                logger.warning(
                    "Graph backend unavailable during %s (%s); using in-memory fallback",
                    method,
                    exc,
                )

    def _mark_up(self) -> None:
        with self._lock:
            recovered = self._primary_down
            self._primary_down = False
            if recovered:
                logger.info(
                    "Graph backend recovered; re-running schema/LifeArea initialization"
                )
                try:
                    self._primary.initialize()
                except GraphUnavailableError as exc:
                    self._mark_down("initialize", exc)


class ScopedGraph:
    """Per-request view of the resilient graph that records whether the fallback was used."""

    def __init__(self, resilient: ResilientGraphRepository) -> None:
        self._resilient = resilient
        self.degraded = False

    def _call(self, method: str, *args, **kwargs):
        result, used_fallback = self._resilient.call(method, *args, **kwargs)
        self.degraded = self.degraded or used_fallback
        return result

    def create_profile(self, profile: Profile) -> Profile:
        return self._call("create_profile", profile)

    def get_profile(self, user_id: str) -> Profile | None:
        return self._call("get_profile", user_id)

    def update_profile(self, user_id: str, fields: dict) -> Profile:
        return self._call("update_profile", user_id, fields)

    def query_facts(
        self,
        user_id: str,
        fact_types: Sequence[FactType],
        life_area: str | None = None,
        limit: int = 5,
    ) -> list[Fact]:
        return self._call("query_facts", user_id, fact_types, life_area, limit)

    def list_facts(self, user_id: str) -> list[Fact]:
        return self._call("list_facts", user_id)

    def upsert_facts(
        self,
        user_id: str,
        facts: Sequence[CandidateFact],
        corrections: Sequence[CandidateCorrection] = (),
    ) -> list[MemoryUpdate]:
        return self._call("upsert_facts", user_id, facts, corrections)

    def ping(self) -> bool:
        return self._call("ping")