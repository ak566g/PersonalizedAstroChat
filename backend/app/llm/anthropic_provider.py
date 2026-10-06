from app.llm.base import LLMError, LLMRequest, Turn

MAX_TOKENS = 16000


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str | None, model: str, effort: str, timeout: float) -> None:
        import anthropic  # lazy: only required when this provider is selected
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2)
        self._model = model
        self._effort = effort

    def generate(self, request: LLMRequest) -> str:
        try:
            response = self._client.beta.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=request.system_prompt,
                messages=_to_messages(request.history, request.message),
                output_config={"effort": self._effort},
                # On a safety-classifier decline the API retries on a fallback model itself.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except self._anthropic.APIError as exc:
            raise LLMError(f"Anthropic API error: {exc}") from exc

        if response.stop_reason == "refusal":
            raise LLMError("Model declined the request")

        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if not text:
            raise LLMError(f"Empty response (stop_reason={response.stop_reason})")
        return text


def _to_messages(history: list[Turn], message: str) -> list[dict]:
    messages: list[dict] = []
    for turn in [*history, Turn("user", message)]:
        if not messages and turn.role != "user":
            continue  # the conversation sent to the API must start with a user turn
        if messages and messages[-1]["role"] == turn.role:
            messages[-1]["content"] += "\n\n" + turn.content
        else:
            messages.append({"role": turn.role, "content": turn.content})
    return messages