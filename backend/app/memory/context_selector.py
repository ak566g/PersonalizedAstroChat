import re
from dataclasses import dataclass
from app.brain.models import DOMAIN_SCOPED_TYPES, LIFE_AREAS, Fact, FactType, Profile
from app.brain.repository import GraphRepository
from app.llm.base import Turn
from app.memory.life_area_classifier import classify_life_area

MEMORY_RECALL = "memory_recall"
FOLLOW_UP = "follow_up"
GENERAL = "general_astrology"
ALWAYS_INCLUDE_LIMIT = 3

_RECALL = re.compile(
    r"\b(remember|recall|told you|i mentioned|said before|what do you know about (?:me|my))\b",
    re.I,
)
_FOLLOW_UP_START = re.compile(
    r"^(why|how come|how so|what do you mean|tell me more|explain|elaborate|go on|really|and|so|"
    r"can you explain|could you explain|say more|in what way|what else)\b",
    re.I,
)
_REFERENTIAL = re.compile(r"\b(that|this|it|those|these)\b", re.I)
_FOLLOW_UP_MAX_WORDS = 10


@dataclass
class ContextBundle:
    category: str
    profile: Profile
    preferences: list[Fact]
    interests: list[Fact]
    facts: list[Fact]
    recent_turns: list[Turn]
    context_used: list[str]


def classify_message(message: str, has_history: bool) -> str:
    """Exactly one category, by precedence: recall > life area > follow-up > general."""
    if _RECALL.search(message):
        return MEMORY_RECALL
    if area := classify_life_area(message):
        return area
    short = len(re.findall(r"\w+", message)) <= _FOLLOW_UP_MAX_WORDS
    if has_history and short and (_FOLLOW_UP_START.search(message.strip()) or _REFERENTIAL.search(message)):
        return FOLLOW_UP
    return GENERAL


class ContextSelector:
    def __init__(self, top_n: int = 5) -> None:
        self._top_n = top_n

    def select(
        self, user_id: str, message: str, recent_turns: list[Turn], graph: GraphRepository
    ) -> ContextBundle:
        profile = graph.get_profile(user_id) or Profile(user_id=user_id)
        preferences = graph.query_facts(
            user_id, [FactType.PREFERENCE], limit=ALWAYS_INCLUDE_LIMIT
        )
        interests = graph.query_facts(
            user_id, [FactType.INTEREST], limit=ALWAYS_INCLUDE_LIMIT
        )
        category = classify_message(message, has_history=bool(recent_turns))

        facts: list[Fact] = []
        if category in LIFE_AREAS:
            facts = graph.query_facts(
                user_id, DOMAIN_SCOPED_TYPES, life_area=category, limit=self._top_n
            )
        elif category == MEMORY_RECALL:
            facts = self._recall(user_id, message, graph)

        fact_ids = {f.id for f in facts}
        preferences = [p for p in preferences if p.id not in fact_ids]
        interests = [i for i in interests if i.id not in fact_ids]

        return ContextBundle(
            category=category,
            profile=profile,
            preferences=preferences,
            interests=interests,
            facts=facts,
            recent_turns=recent_turns,
            context_used=_context_keys(
                profile, preferences, interests, facts, recent_turns
            ),
        )

    def _recall(self, user_id: str, message: str, graph: GraphRepository) -> list[Fact]:
        # "What do you remember about my career goals?" ranks career facts first, then fills
        # the remaining slots with everything else that's active.
        focused: list[Fact] = []
        if area := classify_life_area(message):
            focused = graph.query_facts(
                user_id, DOMAIN_SCOPED_TYPES, life_area=area, limit=self._top_n
            )
        everything = graph.query_facts(user_id, list(FactType), limit=self._top_n)
        seen = {f.id for f in focused}
        return (focused + [f for f in everything if f.id not in seen])[: self._top_n]


def _context_keys(profile, preferences, interests, facts, recent_turns) -> list[str]:
    keys = [
        f"{f.life_area}_{f.fact_type.value}" if f.life_area else f.fact_type.value
        for f in facts
    ]
    if profile.has_any_details():
        keys.append("user_profile")
    if profile.zodiac_sign:
        keys.append("zodiac_sign")
    if preferences:
        keys.append("preference")
    if interests:
        keys.append("interest")
    if recent_turns:
        keys.append("recent_conversation")
    return list(dict.fromkeys(keys))