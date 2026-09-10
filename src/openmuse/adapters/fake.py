from __future__ import annotations

from collections.abc import Callable

from ..domain import ModelCapabilities, ModelEvent, ModelMessage, ModelRequest, ModelResponse, Usage, text_part
from ..model import ModelAdapter


class FakeModelAdapter(ModelAdapter):
    """Deterministic backend used by tests and local smoke runs."""

    def __init__(self, responder: Callable[[ModelRequest], ModelResponse] | None = None) -> None:
        self.responder = responder

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(text=True, tool_calling=True, structured_output=True, parallel_tool_calls=True, context_tokens=1_000_000)

    def complete(self, request: ModelRequest) -> ModelResponse:
        if self.responder:
            return self.responder(request)
        user_text = ""
        for message in reversed(request.messages):
            if message.role == "user":
                user_text = " ".join(part.text or "" for part in message.content if part.type == "text")
                break
        return ModelResponse(
            message=ModelMessage(role="assistant", content=(text_part(f"FAKE_OK: {user_text}"),)),
            usage=Usage(input_tokens=sum(len(part.text or "") for m in request.messages for part in m.content), output_tokens=1, total_tokens=1),
            finish_reason="stop",
            provider_request_id="fake",
        )

    def stream(self, request: ModelRequest):
        response = self.complete(request)
        yield ModelEvent(kind="response.started")
        text = response.message.content[0].text or ""
        for chunk in (text[index:index + 8] for index in range(0, len(text), 8)):
            yield ModelEvent(kind="text.delta", text_delta=chunk)
        yield ModelEvent(kind="usage.updated", usage=response.usage)
        yield ModelEvent(kind="response.completed", metadata={"finish_reason": "stop"})
