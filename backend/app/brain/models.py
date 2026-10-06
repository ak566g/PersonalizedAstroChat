from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class FactType(str, Enum):
    GOAL = "goal"
    PREFERENCE = "preference"
    INTEREST = "interest"
    MEMORY = "memory"


# Fact types whose nodes are linked to a LifeArea and retrieved by domain category.
DOMAIN_SCOPED_TYPES = (FactType.GOAL, FactType.MEMORY)
LIFE_AREAS = ("career", "relationship", "health", "finance")
PROFILE_FIELDS = ("name", "dob", "time_of_birth", "birth_place", "preferred_language")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Profile:
    user_id: str
    name: str | None = None
    dob: str | None = None  # ISO date, e.g. "1995-08-15"
    time_of_birth: str | None = None  # "HH:MM"
    birth_place: str | None = None
    preferred_language: str | None = None
    zodiac_sign: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def has_any_details(self) -> bool:
        return any(getattr(self, f) for f in PROFILE_FIELDS) or bool(self.zodiac_sign)


@dataclass
class CandidateFact:
    fact_type: FactType
    label: str
    life_area: str | None = None
    timeframe: str | None = None
    target_year: int | None = None


@dataclass
class CandidateCorrection:
    """Retracts an existing active fact; optionally replaces it with a new one.
    fact_type=None means 'search every structured fact type for the target'.
    """

    target_hint: str
    fact_type: FactType | None = None
    replacement: CandidateFact | None = None


@dataclass
class Fact:
    id: str
    fact_type: FactType
    label: str
    confidence: float
    status: str  # "active" | "superseded" | "retracted"
    created_at: str
    updated_at: str
    life_area: str | None = None
    timeframe: str | None = None
    target_year: int | None = None
    supersedes_id: str | None = None


@dataclass
class MemoryUpdate:
    action: str  # created | reinforced | superseded | retracted | profile_updated
    fact_type: str
    label: str
    life_area: str | None = None
    details: dict = field(default_factory=dict)