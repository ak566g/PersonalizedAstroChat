"""Deterministic, context-aware stand-in for a real LLM so the whole pipeline runs offline."""

from app.brain.models import FactType
from app.chat.prompt import describe_fact
from app.llm.base import LLMRequest
from app.memory.context_selector import FOLLOW_UP, MEMORY_RECALL
from app.profile.zodiac import SIGN_TRAITS

_AREA_ADVICE = {
    "career": "focus on sharpening the skills your next role will reward, and make your move "
              "when you have a clear plan rather than out of restlessness",
    "relationship": "lead with honest, patient communication and give important conversations time",
    "health": "build small, consistent routines around sleep, movement and stress",
    "finance": "favour steady saving and well-researched decisions over quick wins",
}


class MockProvider:
    name = "mock"

    def generate(self, request: LLMRequest) -> str:
        reply = self._reply(request)
        return reply[:1].upper() + reply[1:]

    def _reply(self, request: LLMRequest) -> str:
        bundle = request.context
        if bundle is None:
            return "I'm here to help with astrology-based guidance. What's on your mind?"
        profile = bundle.profile
        greeting = f"{profile.name}, " if profile.name else ""
        sign_note = (
            f" As a {profile.zodiac_sign}, you bring {SIGN_TRAITS[profile.zodiac_sign]}."
            if profile.zodiac_sign in SIGN_TRAITS
            else ""
        )

        if bundle.category == FOLLOW_UP:
            last = next((t.content for t in reversed(request.history) if t.role == "assistant"), None)
            if not last:
                return "Could you tell me a bit more about what you'd like me to explain?"
            return (
                f"{greeting}I said that because of what we just discussed: \"{_first_sentence(last)}\" "
                f"It follows from the goals and details you've shared with me.{sign_note}"
            )

        if bundle.category == MEMORY_RECALL:
            items = bundle.facts + bundle.preferences + bundle.interests
            if not items:
                return (f"{greeting}I don't have anything saved about that yet. Tell me about your "
                        "goals or plans and I'll remember them.")
            lines = "\n".join(f"- {describe_fact(f)}" for f in items)
            return f"{greeting}here's what I remember about you:\n{lines}"

        advice = _AREA_ADVICE.get(bundle.category)
        if advice:
            goals = [f for f in bundle.facts if f.fact_type == FactType.GOAL]
            goal_note = ""
            if goals:
                goal = goals[0]
                when = f" (target {goal.target_year})" if goal.target_year else (f" ({goal.timeframe})" if goal.timeframe else "")
                goal_note = f" Your goal \"{goal.label}\"{when} should anchor that plan."
            return f"{greeting}for your {bundle.category}, {advice}.{goal_note}{sign_note}"

        return (f"{greeting}I can offer guidance on career, relationships, health or finances."
                f"{sign_note} What would you like to explore?")


def _first_sentence(text: str) -> str:
    sentence = text.split(". ")[0].strip()
    return sentence if sentence.endswith((".", "!", "?")) else sentence + "."