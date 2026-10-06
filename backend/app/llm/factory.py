from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.mock_provider import MockProvider


def get_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            effort=settings.anthropic_effort,
            timeout=settings.llm_timeout_seconds,
        )
    return MockProvider()