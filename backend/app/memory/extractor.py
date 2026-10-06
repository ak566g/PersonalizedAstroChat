"""Rule-based extraction of long-term memory from a user message.
Each clause goes through, in order:
 1. profile-field cues (name, DOB, birth time/place, language) -> in-place profile update
 2. negations ("I don't want to X anymore") -> retract/supersede a fact
 3. structured facts (goal / preference / interest / memory) -> new or reinforced fact
Questions and anything matching no rule (small talk, requests) produce nothing.
"""
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from app.brain.models import CandidateCorrection, CandidateFact, FactType
from app.memory.life_area_classifier import classify_life_area
from app.profile.service import ProfileChanges

_MONTHS = {
    name: i
    for i, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for name in names
}
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))

_LANGUAGES = {
    "hindi",
    "english",
    "tamil",
    "telugu",
    "bengali",
    "bangla",
    "marathi",
    "gujarati",
    "kannada",
    "malayalam",
    "punjabi",
    "urdu",
    "odia",
    "assamese",
    "sanskrit",
    "spanish",
    "french",
    "german",
}

_NUMBER_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
}
_NUM = r"(\d+|a|an|one|two|three|four|five|six)"

_CLAUSE_SPLIT = re.compile(r"(?<=[.!?;])\s+|\s+[—–]\s+|\s+-\s+|\n+")

_QUESTION_START = re.compile(
    r"^(?:what|why|how|when|where|who|which|whose|should|could|would|can|do|does|did|is|are|"
    r"will|am|was|were|tell me|explain|any)\b",
    re.I,
)

_CORRECTION_CUE = re.compile(
    r"^(?:actually|sorry|correction|wait|oh|no|i meant(?: to say)?)\b[,:]?\s*",
    re.I,
)
_EXPLICIT_NOT = re.compile(r"[,;]?\s*\b(?:not|rather than|instead of)\s+(.+)$", re.I)

# profile cues
_NAME = re.compile(
    r"\b(?:my name is|my name's|i am called|i'm called|call me)\s+([a-z][a-z'\-]*(?:\s+[a-z][a-z'\-]*){0,2})",
    re.I,
)
_NAME_STOP = {"and", "i", "im", "but", "from", "born", "by", "the"}

_DATE_DMY = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_RE})\.?,?\s+(\d{{4}})\b",
    re.I,
)
_DATE_MDY = re.compile(
    rf"\b({_MONTH_RE})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b",
    re.I,
)
_DATE_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_DATE_NUMERIC = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b")  # DD/MM/YYYY

_BORN_YEAR = re.compile(
    r"\bborn\s+(?:in|on)\s+(?:the\s+year\s+)?((?:19|20)\d{2})\b", re.I
)
_TIME = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)|\b(\d{1,2}):(\d{2})\b",
    re.I,
)
_PLACE = re.compile(
    r"\b(?:in|at)\s+(?=([a-z][a-z.'\-]*(?:\s+[a-z][a-z.'\-]*){0,3}))", re.I
)
_PLACE_STOP = {
    "and", "on", "at", "in", "i", "but", "so", "to", "the",
    "morning", "evening", "night", "afternoon", "a", "an", "year",
}

_LANGUAGE_CUES = [
    re.compile(
        r"\b(?:talk|speak|reply|respond|answer|write|chat|communicate)\s+(?:to me\s+|with me\s+)?in\s+([a-z]+)",
        re.I,
    ),
    re.compile(r"\bprefer\s+(?:to\s+(?:talk|speak|chat)\s+in\s+)?([a-z]+)\b", re.I),
    re.compile(r"\b(?:preferred\s+)?language\s+is\s+([a-z]+)", re.I),
]

# negations
_NEGATIONS = [
    re.compile(
        r"\bi\s+(?:do not|don't|dont|no longer|won't|will not)\s+(want|plan|intend|wish|need|hope|like|love|enjoy|prefer)\s+(?:to\s+)?(.+)$",
        re.I,
    ),
    re.compile(
        r"\bi(?:'m| am)\s+(?:no longer|not)\s+(?:really\s+)?(planning|going|interested|into|preparing|hoping|aiming)\s+(?:to\s+|in\s+|for\s+|on\s+)?(.+)$",
        re.I,
    ),
    re.compile(
        r"\bi(?:'ve| have)\s+(given up on|dropped|abandoned|cancelled|canceled|stopped)\s+(?:the idea of\s+|my plans?\s+(?:to|of)\s+|plans?\s+to\s+)?(.+)$",
        re.I,
    ),
]

_NEGATION_TYPES = {
    "want": FactType.GOAL,
    "plan": FactType.GOAL,
    "planning": FactType.GOAL,
    "intend": FactType.GOAL,
    "wish": FactType.GOAL,
    "need": FactType.GOAL,
    "hope": FactType.GOAL,
    "hoping": FactType.GOAL,
    "going": FactType.GOAL,
    "preparing": FactType.GOAL,
    "aiming": FactType.GOAL,
    "like": FactType.INTEREST,
    "love": FactType.INTEREST,
    "enjoy": FactType.INTEREST,
    "interested": FactType.INTEREST,
    "into": FactType.INTEREST,
    "prefer": FactType.PREFERENCE,
}

# structured facts
_GOAL_PATTERNS = [
    re.compile(
        r"\bi(?:'m| am| was)?\s+(?:really\s+|also\s+|still\s+|now\s+|currently\s+|seriously\s+)?"
        r"(?:planning|plan|preparing|prepare|hoping|hope|aiming|aim|trying|try|intending|intend|"
        r"wanting|want|wish|would like|'d like|looking|thinking)\s+(?:to|for|on|of|about)\s+(.+)$",
        re.I,
    ),
    re.compile(
        r"\bi(?:'m| am)\s+going\s+to\s+(?!the\b|a\b|an\b|my\b|bed\b|sleep\b)(.+)$",
        re.I,
    ),
    re.compile(
        r"\bmy\s+(?:goal|plan|dream|aim|ambition|target)\s+is\s+(?:to\s+)?(.+)$",
        re.I,
    ),
    re.compile(
        r"\bi(?:'ve| have)\s+(?:got\s+)?(?:a|an|my)\s+(.+?\b(?:interview|exam|exams|test|wedding|deadline|launch|presentation)\b.*)$",
        re.I,
    ),
    re.compile(
        r"\bi\s+(?:really\s+)?(?:want|need|would like|'d like)\s+(?!to\b)(?:a|an|my)\s+(.+)$",
        re.I,
    ),
]

_PREFERENCE_PATTERNS = [
    re.compile(r"\bi\s+(?:prefer|would rather|'d rather)\s+(.+)$", re.I),
    re.compile(r"\bi\s+like\s+(?:it\s+)?when\s+(.+)$", re.I),
]

_INTEREST_PATTERNS = [
    re.compile(
        r"\bi(?:'m| am)\s+(?:really\s+|very\s+|deeply\s+|quite\s+)?(?:interested in|into|passionate about|fascinated by|curious about)\s+(.+)$",
        re.I,
    ),
    re.compile(r"\bi\s+(?:really\s+)?(?:love|enjoy|like)\s+(.+)$", re.I),
]

_MEMORY_PATTERNS = [
    re.compile(
        r"\bi\s+(?:currently\s+|recently\s+|just\s+)?(?:live|work|study|studied|moved|relocated)\b.+",
        re.I,
    ),
    re.compile(
        r"\bi(?:'m| am)\s+(?:married|single|divorced|engaged|pregnant|expecting|retired|unemployed|self-employed|studying|working)\b.*",
        re.I,
    ),
    re.compile(
        r"\bi(?:'m| am)\s+(?:a|an)\s+(?!bit\b|little\b|lot\b)\w+.*",
        re.I,
    ),
    re.compile(
        r"\bi\s+(?:have|'ve got|have got)\s+(?:a|an|one|two|three|four|\d+)\s+(?:kids?|children|child|sons?|daughters?|brothers?|sisters?|siblings?|dogs?|cats?|pets?)\b.*",
        re.I,
    ),
    re.compile(
        r"\bmy\s+(?:wife|husband|partner|mother|mom|father|dad|son|daughter|brother|sister|boss|girlfriend|boyfriend|fiance|fiancee)\s+(?:is|has|was|just)\b.*",
        re.I,
    ),
    re.compile(
        r"\bi\s+(?:just\s+)?got\s+(?:married|engaged|promoted|divorced|a new job|laid off|fired)\b.*",
        re.I,
    ),
]

_NON_GOAL_STARTS = re.compile(
    r"^(?:know|ask|understand|see|hear|check|find out|talk|chat|discuss|tell|help|advice|guidance|reading|prediction|horoscope)\b",
    re.I,
)
_NON_OBJECT = {"you", "it", "that", "this", "them", "him", "her", "me"}
_FILLER = re.compile(
    r"\b(?:instead|anymore|any more|eventually|someday|one day|too|as well|though|please|hopefully|i think)\b",
    re.I,
)

_TIME_EXPRESSIONS: list[tuple[re.Pattern, Callable[[re.Match, int], int | None]]] = [
    (re.compile(r"\bnext year\b", re.I), lambda m, y: y + 1),
    (re.compile(r"\bthis year\b", re.I), lambda m, y: y),
    (
        re.compile(rf"\b(?:in|within)\s+{_NUM}\s+years?\b", re.I),
        lambda m, y: y + _to_int(m.group(1)),
    ),
    (
        re.compile(r"\b(?:by|in|before|during|around)\s+((?:19|20)\d{2})\b", re.I),
        lambda m, y: int(m.group(1)),
    ),
    (
        re.compile(
            r"\b(?:next|this)\s+(?:week|month|quarter|summer|winter|spring|fall|autumn)\b",
            re.I,
        ),
        lambda m, y: None,
    ),
    (
        re.compile(rf"\b(?:in|within)\s+{_NUM}\s+(?:days?|weeks?|months?)\b", re.I),
        lambda m, y: None,
    ),
    (re.compile(r"\b(?:soon|shortly)\b", re.I), lambda m, y: None),
]


@dataclass
class ExtractionResult:
    profile: ProfileChanges = field(default_factory=ProfileChanges)
    facts: list[CandidateFact] = field(default_factory=list)
    corrections: list[CandidateCorrection] = field(default_factory=list)

    def is_empty(self) -> bool:
        return self.profile.is_empty() and not self.facts and not self.corrections


class MemoryExtractor:
    def __init__(self, today: Callable[[], date] = date.today) -> None:
        self._today = today

    def extract(self, message: str) -> ExtractionResult:
        result = ExtractionResult()
        for clause in _statement_clauses(message):
            if self._extract_profile(clause, result.profile):
                continue
            if correction := self._extract_negation(clause):
                result.corrections.append(correction)
                continue
            text, replaced_hint = _split_explicit_correction(clause)
            fact = self._extract_fact(text)
            if fact and replaced_hint:
                result.corrections.append(
                    CandidateCorrection(replaced_hint, fact.fact_type, fact)
                )
            elif fact:
                result.facts.append(fact)
        _pair_replacements(result)
        return result

    def _extract_profile(self, text: str, changes: ProfileChanges) -> bool:
        matched = False
        if m := _NAME.search(text):
            if name := _clean_name(m.group(1)):
                changes.fields["name"] = name
                matched = True
        lower = text.lower()
        if any(
            cue in lower for cue in ("born", "birthday", "date of birth", "dob", "birth time")
        ):
            if dob := _parse_date(text):
                changes.fields["dob"] = dob.isoformat()
                matched = True
            elif m := _BORN_YEAR.search(text):
                changes.dob_year = int(m.group(1))
                matched = True
            if (birth_time := _parse_time(text)) and ("born" in lower or "birth time" in lower):
                changes.fields["time_of_birth"] = birth_time
                matched = True
        if "born" in lower and (place := _parse_birth_place(text)):
            changes.fields["birth_place"] = place
            matched = True
        for pattern in _LANGUAGE_CUES:
            if (m := pattern.search(text)) and m.group(1).lower() in _LANGUAGES:
                changes.fields["preferred_language"] = m.group(1).capitalize()
                matched = True
                break
        return matched

    def _extract_negation(self, text: str) -> CandidateCorrection | None:
        for pattern in _NEGATIONS:
            if m := pattern.search(text):
                verb = m.group(1).lower()
                hint, _, _ = self._split_time(m.group(2))
                hint = _clean_object(hint)
                if not hint:
                    return None
                return CandidateCorrection(hint, _NEGATION_TYPES.get(verb))
        return None

    def _extract_fact(self, text: str) -> CandidateFact | None:
        for pattern in _GOAL_PATTERNS:
            if m := pattern.search(text):
                raw = m.group(1)
                if _NON_GOAL_STARTS.match(raw.strip()):
                    return None
                remainder, timeframe, target_year = self._split_time(raw)
                label = _clean_object(remainder)
                if label:
                    return CandidateFact(
                        FactType.GOAL, label, classify_life_area(text), timeframe, target_year
                    )
        for fact_type, patterns in (
            (FactType.PREFERENCE, _PREFERENCE_PATTERNS),
            (FactType.INTEREST, _INTEREST_PATTERNS),
        ):
            for pattern in patterns:
                if m := pattern.search(text):
                    label = _clean_object(m.group(1))
                    if label and label.lower() not in _NON_OBJECT:
                        return CandidateFact(fact_type, label)
        for pattern in _MEMORY_PATTERNS:
            if m := pattern.search(text):
                label = _sentence_case(m.group(0).strip(",.;"))[:200]
                return CandidateFact(FactType.MEMORY, label, classify_life_area(text))
        return None

    def _split_time(self, text: str) -> tuple[str, str | None, int | None]:
        year = self._today().year
        for pattern, resolve in _TIME_EXPRESSIONS:
            if m := pattern.search(text):
                remainder = (text[: m.start()] + " " + text[m.end() :]).strip()
                return remainder, m.group(0).lower(), resolve(m, year)
        return text, None, None


def _statement_clauses(message: str) -> list[str]:
    """Split into clauses and drop questions, keeping statements attached to a trailing
    question ("I'm planning to switch jobs next year, what do you think?")."""
    clauses: list[str] = []
    text = message.replace("—", " ").replace("–", " ")
    for clause in _CLAUSE_SPLIT.split(text):
        clause = clause.strip()
        if not clause:
            continue
        segments = re.split(r",\s*", clause) if clause.endswith("?") else [clause]
        if len(segments) > 1:
            kept = [
                s for s in segments
                if not _QUESTION_START.match(s.strip()) and not s.strip().endswith("?")
            ]
            clause = ", ".join(kept)
        elif _QUESTION_START.match(clause) or clause.endswith("?"):
            continue
        clause = clause.strip(".!;,")
        if clause:
            clauses.append(clause)
    return clauses


def _split_explicit_correction(clause: str) -> tuple[str, str | None]:
    """'Actually, I want to start a company, not switch jobs' -> (statement, 'switch jobs')."""
    if not _CORRECTION_CUE.match(clause):
        return clause, None
    text = clause
    while (m := _CORRECTION_CUE.match(text)) and m.end() > 0:
        text = text[m.end() :]
    if m := _EXPLICIT_NOT.search(text):
        hint = _clean_object(m.group(1))
        return text[: m.start()].strip(), hint or None
    return text, None


def _pair_replacements(result: ExtractionResult) -> None:
    """'I don't want to switch jobs anymore. I want to start a company.' -> one supersede."""
    for correction in result.corrections:
        if correction.replacement:
            continue
        for i, fact in enumerate(result.facts):
            if correction.fact_type in (None, fact.fact_type):
                correction.replacement = result.facts.pop(i)
                correction.fact_type = fact.fact_type
                break


def _clean_object(text: str) -> str:
    text = _FILLER.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(",. :-!")
    text = re.sub(r"^(?:a|an|the|some)\s+", "", text, flags=re.I)
    return text[:80].strip()


def _clean_name(raw: str) -> str | None:
    words = []
    for word in raw.split():
        if word.lower() in _NAME_STOP:
            break
        words.append(word[:1].upper() + word[1:])
    return " ".join(words) or None


def _parse_date(text: str) -> date | None:
    candidates = []
    if m := _DATE_DMY.search(text):
        candidates.append((int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1))))
    if m := _DATE_MDY.search(text):
        candidates.append((int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2))))
    if m := _DATE_ISO.search(text):
        candidates.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    if m := _DATE_NUMERIC.search(text):
        candidates.append((int(m.group(3)), int(m.group(2)), int(m.group(1))))
    for year, month, day in candidates:
        try:
            return date(year, month, day)
        except ValueError:
            continue
    return None


def _parse_time(text: str) -> str | None:
    if not (m := _TIME.search(text)):
        return None
    if m.group(4):
        hour, minute = int(m.group(4)), int(m.group(5))
    else:
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
    meridiem = m.group(3).lower().replace(".", "") if m.group(3) else ""
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _parse_birth_place(text: str) -> str | None:
    stripped = text
    for pattern in (_DATE_DMY, _DATE_MDY, _DATE_ISO, _DATE_NUMERIC, _TIME):
        stripped = pattern.sub(" ", stripped)
    stripped = re.sub(r"\b\d+\b", " ", stripped)
    for m in _PLACE.finditer(stripped):
        words = []
        for word in m.group(1).split():
            if word.lower() in _PLACE_STOP or word.lower() in _MONTHS:
                break
            words.append(word[:1].upper() + word[1:])
        if words:
            return " ".join(words)
    return None


def _sentence_case(text: str) -> str:
    return text[:1].upper() + text[1:]


def _to_int(token: str) -> int:
    return int(token) if token.isdigit() else _NUMBER_WORDS[token.lower()]