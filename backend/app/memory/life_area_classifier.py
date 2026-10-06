import re
from app.brain.models import LIFE_AREAS

# Used for both incoming messages (what is the user asking about?) and for tagging new
# facts at write time (classified on the whole clause, not just the extracted label, so
# "switch jobs" is tagged career via "jobs"). One vocabulary keeps the two paths in
# agreement.
_KEYWORDS: dict[str, set[str]] = {
    "career": {
        "career", "careers", "job", "jobs", "work", "working", "office", "boss",
        "promotion", "interview", "interviews", "company", "companies", "business",
        "startup", "startups", "entrepreneur", "entrepreneurship", "profession",
        "professional", "colleague", "colleagues", "resign", "resignation", "hire",
        "hired", "hiring", "employer", "employment", "workplace", "internship",
        "freelance", "freelancing", "manager", "management", "appraisal",
    },
    "relationship": {
        "relationship", "relationships", "love", "partner", "marriage", "married",
        "marry", "wife", "husband", "girlfriend", "boyfriend", "dating", "breakup",
        "divorce", "engaged", "engagement", "spouse", "romance", "romantic",
        "soulmate", "compatibility", "wedding", "fiance", "fiancee",
    },
    "health": {
        "health", "healthy", "sick", "illness", "fitness", "exercise", "gym", "diet",
        "stress", "stressed", "sleep", "anxiety", "anxious", "depression", "doctor",
        "hospital", "weight", "disease", "mental", "wellbeing", "wellness", "injury",
        "pain", "medicine", "yoga",
    },
    "finance": {
        "money", "finance", "finances", "financial", "invest", "investing",
        "investment", "investments", "savings", "salary", "loan", "loans", "debt",
        "debts", "wealth", "income", "budget", "stock", "stocks", "property",
        "mortgage", "tax", "taxes", "expenses", "spending", "crypto",
    },
}


def classify_life_area(text: str) -> str | None:
    words = re.findall(r"[a-z]+", text.lower())
    counts = {area: sum(w in _KEYWORDS[area] for w in words) for area in LIFE_AREAS}
    best = max(LIFE_AREAS, key=lambda area: counts[area])  # ties resolve in LIFE_AREAS order
    return best if counts[best] else None