import uuid
from collections.abc import Sequence
from contextlib import AbstractContextManager, nullcontext
from typing import Protocol
from app.brain.matching import best_match
from app.brain.models import (
    DOMAIN_SCOPED_TYPES,
    CandidateCorrection,
    CandidateFact,
    Fact,
    FactType,
    MemoryUpdate,
    Profile,
    utc_now,
)

INITIAL_CONFIDENCE = 0.6
REINFORCE_STEP = 0.15


class GraphUnavailableError(Exception):
    """The graph backend could not be reached (as opposed to a query finding nothing)."""


class GraphRepository(Protocol):
    def initialize(self) -> None: ...
    def ping(self) -> bool: ...
    def create_profile(self, profile: Profile) -> Profile: ...
    def get_profile(self, user_id: str) -> Profile | None: ...
    def update_profile(self, user_id: str, fields: dict) -> Profile: ...
    def query_facts(
        self,
        user_id: str,
        fact_types: Sequence[FactType],
        life_area: str | None = None,
        limit: int = 5,
    ) -> list[Fact]: ...
    def list_facts(self, user_id: str) -> list[Fact]: ...
    def upsert_facts(
        self,
        user_id: str,
        facts: Sequence[CandidateFact],
        corrections: Sequence[CandidateCorrection] = (),
    ) -> list[MemoryUpdate]: ...


class FactWriteMixin:
    """Memory-update policy shared by every backend; backends only supply storage primitives."""

    def _transaction(self) -> AbstractContextManager:
        return nullcontext()

    def _active_facts(self, user_id: str, fact_types: Sequence[FactType]) -> list[Fact]:
        raise NotImplementedError

    def _create_fact(self, user_id: str, fact: Fact) -> None:
        raise NotImplementedError

    def _reinforce_fact(
        self,
        fact: Fact,
        confidence: float,
        timeframe: str | None,
        target_year: int | None,
        now: str,
    ) -> None:
        raise NotImplementedError

    def _supersede_fact(self, user_id: str, old: Fact, new: Fact) -> None:
        raise NotImplementedError

    def _retract_fact(self, fact: Fact, now: str) -> None:
        raise NotImplementedError

    def upsert_facts(
        self,
        user_id: str,
        facts: Sequence[CandidateFact],
        corrections: Sequence[CandidateCorrection] = (),
    ) -> list[MemoryUpdate]:
        updates: list[MemoryUpdate] = []
        pending = list(facts)

        with self._transaction():
            for correction in corrections:
                types = [correction.fact_type] if correction.fact_type else list(FactType)
                target = best_match(self._active_facts(user_id, types), correction.target_hint)
                if target is None:
                    # Nothing to retract; a stated replacement is still a valid new fact.
                    if correction.replacement:
                        pending.append(correction.replacement)
                    continue

                now = utc_now()
                if correction.replacement:
                    new = _build_fact(correction.replacement, now, fallback_area=target.life_area)
                    new.supersedes_id = target.id
                    self._supersede_fact(user_id, target, new)
                    updates.append(
                        MemoryUpdate(
                            "superseded",
                            new.fact_type.value,
                            new.label,
                            new.life_area,
                            {"replaced": target.label},
                        )
                    )
                else:
                    self._retract_fact(target, now)
                    updates.append(
                        MemoryUpdate(
                            "retracted",
                            target.fact_type.value,
                            target.label,
                            target.life_area,
                        )
                    )

            for candidate in pending:
                existing = best_match(
                    self._active_facts(user_id, [candidate.fact_type]), candidate.label
                )
                now = utc_now()
                if existing:
                    confidence = min(round(existing.confidence + REINFORCE_STEP, 2), 1.0)
                    self._reinforce_fact(
                        existing,
                        confidence,
                        candidate.timeframe or existing.timeframe,
                        candidate.target_year or existing.target_year,
                        now,
                    )
                    updates.append(
                        MemoryUpdate(
                            "reinforced",
                            existing.fact_type.value,
                            existing.label,
                            existing.life_area,
                            {"confidence": confidence},
                        )
                    )
                else:
                    new = _build_fact(candidate, now)
                    self._create_fact(user_id, new)
                    updates.append(
                        MemoryUpdate("created", new.fact_type.value, new.label, new.life_area)
                    )

        return updates


def _build_fact(
    candidate: CandidateFact, now: str, fallback_area: str | None = None
) -> Fact:
    life_area = None
    if candidate.fact_type in DOMAIN_SCOPED_TYPES:
        life_area = candidate.life_area or fallback_area
    return Fact(
        id=str(uuid.uuid4()),
        fact_type=candidate.fact_type,
        label=candidate.label,
        confidence=INITIAL_CONFIDENCE,
        status="active",
        created_at=now,
        updated_at=now,
        life_area=life_area,
        timeframe=candidate.timeframe,
        target_year=candidate.target_year,
    )