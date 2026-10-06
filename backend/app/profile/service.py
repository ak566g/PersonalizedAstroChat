from dataclasses import dataclass, field
from datetime import date
from app.brain.models import MemoryUpdate, Profile
from app.brain.repository import GraphRepository
from app.profile.zodiac import sun_sign_from_iso


@dataclass
class ProfileChanges:
    """Profile facts detected in a chat message."""

    fields: dict = field(default_factory=dict)
    # A bare year ("I was born in 1996") only corrects the year of an already-known DOB.
    dob_year: int | None = None

    def is_empty(self) -> bool:
        return not self.fields and self.dob_year is None


class ProfileService:
    def __init__(self, graph: GraphRepository) -> None:
        self._graph = graph

    def create(self, user_id: str, fields: dict) -> Profile:
        profile = Profile(user_id=user_id, **fields)
        profile.zodiac_sign = sun_sign_from_iso(profile.dob)
        return self._graph.create_profile(profile)

    def get(self, user_id: str) -> Profile:
        return self._graph.get_profile(user_id) or Profile(user_id=user_id)

    def update(self, user_id: str, fields: dict) -> Profile:
        fields = dict(fields)
        if "dob" in fields:
            fields["zodiac_sign"] = sun_sign_from_iso(fields["dob"])
        return self._graph.update_profile(user_id, fields)

    def apply_chat_changes(
        self, user_id: str, changes: ProfileChanges
    ) -> list[MemoryUpdate]:
        if changes.is_empty():
            return []
        current = self.get(user_id)
        fields = dict(changes.fields)
        if changes.dob_year and "dob" not in fields and current.dob:
            fields["dob"] = _with_year(
                date.fromisoformat(current.dob), changes.dob_year
            ).isoformat()
        changed = {k: v for k, v in fields.items() if getattr(current, k) != v}
        if not changed:
            return []
        self.update(user_id, changed)
        return [
            MemoryUpdate("profile_updated", "profile", name, details={"value": value})
            for name, value in changed.items()
        ]


def _with_year(d: date, year: int) -> date:
    try:
        return d.replace(year=year)
    except ValueError:  # Feb 29 into a non-leap year
        return d.replace(year=year, day=28)