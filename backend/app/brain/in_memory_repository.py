import threading
from collections.abc import Sequence
from dataclasses import replace
from app.brain.models import LIFE_AREAS, Fact, FactType, Profile, utc_now
from app.brain.repository import FactWriteMixin

class InMemoryGraphRepository(FactWriteMixin):
    """Process-local graph used for tests and as the fallback when Neo4j is unreachable."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._profiles: dict[str, Profile] = {}
        self._facts: dict[str, list[Fact]] = {}
        self._life_areas: set[str] = set()

    def initialize(self) -> None:
        with self._lock:
            self._life_areas.update(LIFE_AREAS)

    def ping(self) -> bool:
        return True

    def create_profile(self, profile: Profile) -> Profile:
        with self._lock:
            now = utc_now()
            stored = replace(profile, created_at=profile.created_at or now, updated_at=now)
            self._profiles[profile.user_id] = stored
            return replace(stored)

    def get_profile(self, user_id: str) -> Profile | None:
        with self._lock:
            profile = self._profiles.get(user_id)
            return replace(profile) if profile else None

    def update_profile(self, user_id: str, fields: dict) -> Profile:
        with self._lock:
            now = utc_now()
            current = self._profiles.get(user_id) or Profile(user_id=user_id, created_at=now)
            updated = replace(current, **fields, updated_at=now)
            self._profiles[user_id] = updated
            return replace(updated)

    def query_facts(
        self,
        user_id: str,
        fact_types: Sequence[FactType],
        life_area: str | None = None,
        limit: int = 5,
    ) -> list[Fact]:
        with self._lock:
            matches = [
                f
                for f in self._facts.get(user_id, [])
                if f.status == "active"
                and f.fact_type in fact_types
                and (life_area is None or f.life_area == life_area)
            ]
            matches.sort(key=lambda f: (f.confidence, f.updated_at), reverse=True)
            return [replace(f) for f in matches[:limit]]

    def list_facts(self, user_id: str) -> list[Fact]:
        with self._lock:
            return [
                replace(f)
                for f in sorted(self._facts.get(user_id, []), key=lambda f: f.created_at)
            ]

    def _transaction(self):
        return self._lock

    def _active_facts(self, user_id: str, fact_types: Sequence[FactType]) -> list[Fact]:
        return [
            replace(f)
            for f in self._facts.get(user_id, [])
            if f.status == "active" and f.fact_type in fact_types
        ]

    def _find(self, fact_id: str) -> Fact:
        for facts in self._facts.values():
            for fact in facts:
                if fact.id == fact_id:
                    return fact
        raise KeyError(fact_id)

    def _create_fact(self, user_id: str, fact: Fact) -> None:
        self._profiles.setdefault(user_id, Profile(user_id=user_id, created_at=fact.created_at))
        if fact.life_area:
            self._life_areas.add(fact.life_area)
        self._facts.setdefault(user_id, []).append(replace(fact))

    def _reinforce_fact(self, fact, confidence, timeframe, target_year, now) -> None:
        fact = self._find(fact.id)
        fact.confidence, fact.timeframe, fact.target_year, fact.updated_at = (
            confidence,
            timeframe,
            target_year,
            now,
        )

    def _supersede_fact(self, user_id: str, old: Fact, new: Fact) -> None:
        stored_old = self._find(old.id)
        stored_old.status, stored_old.updated_at = "superseded", new.created_at
        self._create_fact(user_id, new)

    def _retract_fact(self, fact: Fact, now: str) -> None:
        fact = self._find(fact.id)
        fact.status, fact.updated_at = "retracted", now