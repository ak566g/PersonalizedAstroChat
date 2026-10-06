from datetime import date

# Tropical sun-sign start dates (month, day). Stub astrology: sun sign from date of birth
# only.
_SIGN_STARTS = [
    ((1, 20), "Aquarius"),
    ((2, 19), "Pisces"),
    ((3, 21), "Aries"),
    ((4, 20), "Taurus"),
    ((5, 21), "Gemini"),
    ((6, 21), "Cancer"),
    ((7, 23), "Leo"),
    ((8, 23), "Virgo"),
    ((9, 23), "Libra"),
    ((10, 23), "Scorpio"),
    ((11, 22), "Sagittarius"),
    ((12, 22), "Capricorn"),
]

SIGN_TRAITS = {
    "Aries": "bold initiative and a drive to start new things",
    "Taurus": "patience, steadiness and a builder's persistence",
    "Gemini": "curiosity, adaptability and a gift for communication",
    "Cancer": "intuition, loyalty and strong emotional intelligence",
    "Leo": "confidence, creativity and natural leadership",
    "Virgo": "precision, practicality and careful planning",
    "Libra": "diplomacy, balance and a talent for partnerships",
    "Scorpio": "focus, resilience and strategic depth",
    "Sagittarius": "optimism, vision and a love of growth",
    "Capricorn": "discipline, ambition and long-term thinking",
    "Aquarius": "originality, independence and forward thinking",
    "Pisces": "empathy, imagination and creative intuition",
}


def sun_sign(dob: date) -> str:
    sign = "Capricorn"  # Jan 1 - Jan 19
    for start, name in _SIGN_STARTS:
        if (dob.month, dob.day) >= start:
            sign = name
    return sign


def sun_sign_from_iso(dob: str | None) -> str | None:
    if not dob:
        return None
    try:
        return sun_sign(date.fromisoformat(dob))
    except ValueError:
        return None