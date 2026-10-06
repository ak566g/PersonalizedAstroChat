from app.brain.models import Fact, FactType
from app.memory.context_selector import ContextBundle

_INSTRUCTIONS = """You are MyNaksh's astrology guide. Give warm, practical, personalized guidance.
Personalize using only the user context below; never invent facts about the user.
If a detail you need (e.g. date of birth) is missing, answer generally and invite them to share it.
Astrology is for reflection, not certainty: avoid definitive medical, legal or financial claims.
Keep answers concise: a short paragraph or a few bullet points."""


def describe_fact(fact: Fact) -> str:
    if fact.fact_type == FactType.GOAL:
        text = f"Goal: {fact.label}"
        if fact.target_year:
            text += f" (target year {fact.target_year})"
        elif fact.timeframe:
            text += f" ({fact.timeframe})"
    elif fact.fact_type == FactType.PREFERENCE:
        text = f"Prefers: {fact.label}"
    elif fact.fact_type == FactType.INTEREST:
        text = f"Interested in: {fact.label}"
    else:
        text = fact.label
    return f"[{fact.life_area}] {text}" if fact.life_area else text


def build_system_prompt(bundle: ContextBundle) -> str:
    p = bundle.profile
    sections = [_INSTRUCTIONS]

    profile_lines = [
        f"- {label}: {value}"
        for label, value in (
            ("Name", p.name),
            ("Date of birth", p.dob),
            ("Time of birth", p.time_of_birth),
            ("Birth place", p.birth_place),
            ("Sun sign", p.zodiac_sign),
            ("Preferred language", p.preferred_language),
        )
        if value
    ]
    sections.append(
        "## User profile\n"
        + ("\n".join(profile_lines) or "(no profile details yet)")
    )

    if bundle.facts:
        sections.append(
            "## Relevant long-term memory\n"
            + "\n".join(f"- {describe_fact(f)}" for f in bundle.facts)
        )

    personal = bundle.preferences + bundle.interests
    if personal:
        sections.append(
            "## Preferences and interests\n"
            + "\n".join(f"- {describe_fact(f)}" for f in personal)
        )

    if p.preferred_language:
        sections.append(f"Respond in {p.preferred_language}.")

    return "\n\n".join(sections)