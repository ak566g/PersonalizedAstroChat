from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

@dataclass(frozen=True)
class Turn:
    role: Literal["user", "assistant"]
    content: str

@dataclass
class LLMRequest:
    system_prompt: str
    history: list[Turn]
    message: str
    # Structured view of the selected context (a ContextBundle). Real providers only need
    # system_prompt; the mock provider templates its reply from this.
    context: Any = field(default=None)

class LLMError(Exception):
    """The provider failed to produce a usable response."""

class LLMProvider(Protocol):
    name: str

    def generate(self, request: LLMRequest) -> str: ...