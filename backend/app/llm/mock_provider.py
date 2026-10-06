from app.brain.models import Fact, FactType
from app.llm.base import LLMRequest
from app.memory.context_selector import ContextBundle

_AFFIRMATIONS = {
    "career": "Your professional path is illuminated by strong planetary momentum.",
    "relationship": "Venus and the lunar nodes highlight matters of harmony, connection, and honest dialogue.",
    "health": "Vitality flows best when daily rhythms and rest are honored.",
    "finance": "Prudence and long-term vision align well with your fiscal transits.",
    "general": "The celestial patterns reflect a season of steady growth and self-discovery.",
}


class MockProvider:
    name = "mock"

    def generate(self, request: LLMRequest) -> str:
        bundle: ContextBundle | None = request.context
        if bundle is None:
            return (
                "The stars encourage patience and steady contemplation as you move forward."
            )

        name_part = f"{bundle.profile.name}, " if bundle.profile.name else ""
        sign_part = (
            f"As a {bundle.profile.zodiac_sign}, " if bundle.profile.zodiac_sign else ""
        )
        affirmation = _AFFIRMATIONS.get(bundle.category, _AFFIRMATIONS["general"])

        paragraphs = [f"{sign_part}{name_part}{affirmation}".strip()]

        if bundle.facts:
            key_facts = [
                _format_fact(f)
                for f in bundle.facts[:2]
            ]
            paragraphs.append(
                f"Keeping your focus on {' and '.join(key_facts)} will serve you well during this phase."
            )

        if bundle.preferences or bundle.interests:
            personal = [f.label for f in (bundle.preferences + bundle.interests)[:2]]
            paragraphs.append(
                f"Your natural leaning toward {', '.join(personal)} provides steady ground."
            )

        return "\n\n".join(paragraphs)


def _format_fact(fact: Fact) -> str:
    if fact.fact_type == FactType.GOAL:
        suffix = f" by {fact.target_year}" if fact.target_year else ""
        return f"your goal to {fact.label}{suffix}"
    return fact.label