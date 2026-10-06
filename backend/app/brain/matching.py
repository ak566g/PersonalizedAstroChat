import re
from collections.abc import Iterable
from app.brain.models import Fact

_STOPWORDS = {
    "a", "an", "the", "my", "to", "of", "for", "in", "on",
    "be", "is", "am", "are", "it", "that", "this", "with",
    "at", "and", "or", "i", "me", "about", "some", "any", "more",
    "anymore", "longer", "instead", "really", "actually", "just", "now", "again", "also",
    "still", "very", "so", "get", "go", "do",
}

MATCH_THRESHOLD = 0.5


def _stem(word: str) -> str:
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokens(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS}


def similarity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def best_match(candidates: Iterable[Fact], text: str) -> Fact | None:
    """Most similar fact above the threshold; ties go to higher confidence, then recency."""
    scored = [
        (score, fact.confidence, fact.updated_at, fact)
        for fact in candidates
        if (score := similarity(fact.label, text)) >= MATCH_THRESHOLD
    ]
    if not scored:
        return None
    return max(scored, key=lambda s: s[:3])[3]