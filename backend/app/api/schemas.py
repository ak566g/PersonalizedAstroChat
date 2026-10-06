from datetime import date
from pydantic import BaseModel, Field, field_validator

_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
_TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class ProfileFields(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    dob: date | None = None
    time_of_birth: str | None = Field(
        None, pattern=_TIME_PATTERN, description="24h HH:MM"
    )
    birth_place: str | None = Field(None, min_length=1, max_length=100)
    preferred_language: str | None = Field(None, min_length=1, max_length=40)

    @field_validator("dob")
    @classmethod
    def dob_not_in_future(cls, value: date | None) -> date | None:
        if value and value > date.today():
            raise ValueError("date of birth cannot be in the future")
        return value

    def profile_values(self, only_set: bool = False) -> dict:
        data = self.model_dump(
            include=set(ProfileFields.model_fields), exclude_unset=only_set
        )
        if data.get("dob") is not None:
            data["dob"] = data["dob"].isoformat()
        return data


class SignupRequest(ProfileFields):
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class SignupResponse(BaseModel):
    session_token: str
    user_id: str
    degraded: bool


class LoginResponse(BaseModel):
    session_token: str


class ProfileResponse(BaseModel):
    user_id: str
    name: str | None
    dob: str | None
    time_of_birth: str | None
    birth_place: str | None
    preferred_language: str | None
    zodiac_sign: str | None
    degraded: bool


class ChatRequest(BaseModel):
    session_id: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:\-]+$"
    )
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be blank")
        return value


class MemoryUpdateOut(BaseModel):
    action: str
    type: str
    label: str
    life_area: str | None
    details: dict


class ChatResponse(BaseModel):
    response: str
    user_id: str
    session_id: str
    context_used: list[str]
    intent: str
    memory_updates: list[MemoryUpdateOut]
    degraded: bool


class FactOut(BaseModel):
    id: str
    type: str
    label: str
    status: str
    confidence: float
    life_area: str | None
    timeframe: str | None
    target_year: int | None
    supersedes_id: str | None
    created_at: str
    updated_at: str


class BrainResponse(BaseModel):
    user_id: str
    facts: list[FactOut]
    degraded: bool


class HealthResponse(BaseModel):
    status: str
    graph_backend: str
    llm_provider: str


class SessionOut(BaseModel):
    session_id: str
    title: str
    message_count: int
    last_message_at: str


class SessionsResponse(BaseModel):
    sessions: list[SessionOut]


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: str


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: list[MessageOut]