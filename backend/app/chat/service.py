import logging
from dataclasses import dataclass, field
from app.brain.models import MemoryUpdate
from app.brain.resilient_repository import ScopedGraph
from app.chat.prompt import build_system_prompt
from app.llm.base import LLMProvider, LLMRequest
from app.memory.context_selector import ContextBundle, ContextSelector
from app.memory.extractor import MemoryExtractor
from app.memory.short_term import ShortTermStore
from app.profile.service import ProfileService

logger = logging.getLogger(__name__)


@dataclass
class ChatResult:
    response: str
    intent: str
    context_used: list[str]
    memory_updates: list[MemoryUpdate] = field(default_factory=list)
    degraded: bool = False


class ChatService:
    def __init__(
        self,
        short_term: ShortTermStore,
        selector: ContextSelector,
        extractor: MemoryExtractor,
        llm: LLMProvider,
        short_term_turns: int,
    ) -> None:
        self._short_term = short_term
        self._selector = selector
        self._extractor = extractor
        self._llm = llm
        self._turns = short_term_turns

    def handle_message(
        self, user_id: str, session_id: str, message: str, graph: ScopedGraph
    ) -> ChatResult:
        recent = self._short_term.recent(user_id, session_id, self._turns)
        bundle = self._selector.select(user_id, message, recent, graph)

        llm_failed = False
        try:
            reply = self._llm.generate(
                LLMRequest(
                    system_prompt=build_system_prompt(bundle),
                    history=recent,
                    message=message,
                    context=bundle,
                )
            )
        except Exception:
            logger.exception("LLM provider %s failed; using fallback reply", self._llm.name)
            reply = _fallback_reply(bundle)
            llm_failed = True

        self._short_term.append(user_id, session_id, "user", message)
        self._short_term.append(user_id, session_id, "assistant", reply)

        memory_updates = self._update_memory(user_id, message, graph)
        return ChatResult(
            response=reply,
            intent=bundle.category,
            context_used=bundle.context_used,
            memory_updates=memory_updates,
            degraded=graph.degraded or llm_failed,
        )

    def _update_memory(
        self, user_id: str, message: str, graph: ScopedGraph
    ) -> list[MemoryUpdate]:
        # Best effort: the user already has their answer, so a memory-write bug must not fail the request.
        try:
            extracted = self._extractor.extract(message)
            if extracted.is_empty():
                return []
            updates = ProfileService(graph).apply_chat_changes(user_id, extracted.profile)
            return updates + graph.upsert_facts(user_id, extracted.facts, extracted.corrections)
        except Exception:
            logger.exception("Memory update failed for user %s", user_id)
            return []


def _fallback_reply(bundle: ContextBundle) -> str:
    name = f" {bundle.profile.name}" if bundle.profile.name else ""
    return (
        f"Sorry{name}, I can't reach my guidance engine right now. I still have your details "
        "and our conversation saved, so please try again in a moment."
    )