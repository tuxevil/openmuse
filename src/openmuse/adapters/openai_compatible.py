"""Dependency-light OpenAI-compatible adapter.

The adapter uses urllib so LiteLLM, Ollama, vLLM, OpenAI-compatible local
servers, and a test HTTP server all exercise the same OpenMuse contract.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

from ..domain import ContentPart, ModelCapabilities, ModelEvent, ModelMessage, ModelRequest, ModelResponse, ToolCall, Usage, text_part
from ..model import ModelAdapter


class ModelProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str = "provider_error", retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class OpenAICompatibleAdapter(ModelAdapter):
    def __init__(self, *, base_url: str, model: str, api_key: str | None = None, api_key_env: str | None = None, capabilities: ModelCapabilities | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.api_key_env = api_key_env
        self._capabilities = capabilities or ModelCapabilities(text=True, tool_calling=True, structured_output=True, parallel_tool_calls=True, context_tokens=131_072)

    @property
    def capabilities(self) -> ModelCapabilities:
        return self._capabilities

    def _headers(self) -> dict[str, str]:
        key = self.api_key or (os.environ.get(self.api_key_env, "") if self.api_key_env else "")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    @staticmethod
    def _message(message: ModelMessage) -> dict[str, Any]:
        content: Any
        if len(message.content) == 1 and message.content[0].type == "text":
            content = message.content[0].text or ""
        else:
            content = [{"type": part.type, "text": part.text, "source": part.source} for part in message.content]
        result: dict[str, Any] = {"role": message.role, "content": content}
        if message.name:
            result["name"] = message.name
        if message.tool_call_id:
            result["tool_call_id"] = message.tool_call_id
        return result

    def _payload(self, request: ModelRequest, stream: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.model, "messages": [self._message(m) for m in request.messages], "max_tokens": request.limits.max_output_tokens, "stream": stream}
        if request.tools:
            payload["tools"] = [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.input_schema}} for t in request.tools]
        if request.response_format:
            payload["response_format"] = request.response_format
        return payload

    def _request(self, request: ModelRequest, *, stream: bool = False):
        body = json.dumps(self._payload(request, stream)).encode("utf-8")
        http_request = urllib.request.Request(f"{self.base_url}/chat/completions", data=body, headers=self._headers(), method="POST")
        timeout = max(1, request.limits.deadline_ms / 1000)
        try:
            return urllib.request.urlopen(http_request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise ModelProviderError(f"provider HTTP {exc.code}: {detail}", code="provider_http_error", retryable=exc.code >= 500) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ModelProviderError(f"provider connection failed: {exc}", code="provider_unavailable", retryable=True) from exc

    @staticmethod
    def _response(data: dict[str, Any]) -> ModelResponse:
        try:
            choice = data["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelProviderError("provider response does not contain choices[0].message", code="invalid_provider_response") from exc
        content = message.get("content") or ""
        parts = (text_part(content),) if isinstance(content, str) else tuple(ContentPart(type=p.get("type", "text"), text=p.get("text"), source=p.get("source")) for p in content)
        calls = []
        for raw in message.get("tool_calls") or []:
            function = raw.get("function", {})
            try:
                arguments = json.loads(function.get("arguments", "{}"))
            except json.JSONDecodeError as exc:
                raise ModelProviderError("provider returned invalid tool arguments JSON", code="invalid_tool_arguments") from exc
            if not isinstance(arguments, dict):
                raise ModelProviderError("tool arguments must be an object", code="invalid_tool_arguments")
            calls.append(ToolCall(call_id=raw.get("id", "tool_call"), tool=function.get("name", ""), arguments=arguments))
        raw_usage = data.get("usage") or {}
        usage = Usage(input_tokens=int(raw_usage.get("prompt_tokens", 0) or 0), output_tokens=int(raw_usage.get("completion_tokens", 0) or 0), total_tokens=int(raw_usage.get("total_tokens", 0) or 0))
        return ModelResponse(message=ModelMessage(role="assistant", content=parts), tool_calls=tuple(calls), usage=usage, finish_reason=choice.get("finish_reason"), provider_request_id=data.get("id"), raw_metadata={"system_fingerprint": data.get("system_fingerprint")})

    def complete(self, request: ModelRequest) -> ModelResponse:
        with self._request(request) as response:
            try:
                data = json.loads(response.read().decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ModelProviderError("provider returned invalid JSON", code="invalid_provider_response") from exc
        return self._response(data)

    def stream(self, request: ModelRequest) -> Iterator[ModelEvent]:
        started = time.monotonic()
        calls: dict[str, dict[str, Any]] = {}
        call_indexes: dict[int, str] = {}
        yield ModelEvent(kind="response.started")
        with self._request(request, stream=True) as response:
            for raw_line in response:
                if time.monotonic() - started > request.limits.deadline_ms / 1000:
                    raise ModelProviderError("model stream deadline exceeded", code="deadline_exceeded", retryable=True)
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError as exc:
                    raise ModelProviderError("provider returned invalid streaming JSON", code="invalid_provider_response") from exc
                choice = (data.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                if delta.get("content"):
                    yield ModelEvent(kind="text.delta", text_delta=delta["content"])
                for call in delta.get("tool_calls") or []:
                    function = call.get("function") or {}
                    index = int(call.get("index", 0))
                    call_id = call.get("id") or call_indexes.get(index) or f"stream_call_{index}"
                    call_indexes[index] = call_id
                    state = calls.setdefault(call_id, {"name": "", "arguments": ""})
                    if function.get("name"):
                        state["name"] = function["name"]
                        yield ModelEvent(kind="tool_call.started", metadata={"call_id": call_id, "tool": state["name"]})
                    if function.get("arguments"):
                        state["arguments"] += function["arguments"]
                        yield ModelEvent(kind="tool_call.arguments.delta", tool_call_arguments_delta=function["arguments"], metadata={"call_id": call_id})
                raw_usage = data.get("usage")
                if raw_usage:
                    yield ModelEvent(kind="usage.updated", usage=Usage(input_tokens=int(raw_usage.get("prompt_tokens", 0) or 0), output_tokens=int(raw_usage.get("completion_tokens", 0) or 0), total_tokens=int(raw_usage.get("total_tokens", 0) or 0)))
        for call_id, state in calls.items():
            try:
                arguments = json.loads(state["arguments"] or "{}")
            except json.JSONDecodeError as exc:
                raise ModelProviderError("provider returned incomplete tool arguments", code="invalid_tool_arguments") from exc
            if not isinstance(arguments, dict):
                raise ModelProviderError("streamed tool arguments must be an object", code="invalid_tool_arguments")
            yield ModelEvent(kind="tool_call.completed", tool_call=ToolCall(call_id=call_id, tool=state["name"], arguments=arguments))
        yield ModelEvent(kind="response.completed")
