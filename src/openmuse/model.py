"""OpenMuse-owned model adapter contract and routing policy."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from .domain import ModelCapabilities, ModelEvent, ModelRequest, ModelResponse, Sensitivity
from .repository import ControlPlaneRepository


class ModelAdapter(ABC):
    """The only model interface the orchestrator depends on."""

    @property
    @abstractmethod
    def capabilities(self) -> ModelCapabilities:
        raise NotImplementedError

    @abstractmethod
    def complete(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError

    def stream(self, request: ModelRequest) -> Iterator[ModelEvent]:
        response = self.complete(request)
        yield ModelEvent(kind="response.started")
        text = next((part.text for part in response.message.content if part.type == "text" and part.text), "")
        if text:
            yield ModelEvent(kind="text.delta", text_delta=text)
        for call in response.tool_calls:
            yield ModelEvent(kind="tool_call.completed", tool_call=call)
        if response.usage:
            yield ModelEvent(kind="usage.updated", usage=response.usage)
        yield ModelEvent(kind="response.completed", metadata={"finish_reason": response.finish_reason})


class ModelRoutingError(RuntimeError):
    pass


_SENSITIVITY_RANK = {
    Sensitivity.PUBLIC.value: 0,
    Sensitivity.INTERNAL.value: 1,
    Sensitivity.CONFIDENTIAL.value: 2,
    Sensitivity.PRIVATE.value: 3,
    Sensitivity.RESTRICTED.value: 4,
}


class ModelRouter:
    """Selects a durable role profile without widening sensitivity exposure."""

    def __init__(self, repository: ControlPlaneRepository, adapters: dict[str, ModelAdapter]) -> None:
        self.repository = repository
        self.adapters = adapters

    def resolve(self, instance_id: str, role: str, sensitivity: str, *, local_only: bool = False) -> tuple[ModelAdapter, dict[str, Any]]:
        requested = _SENSITIVITY_RANK.get(sensitivity, 99)
        candidates = [p for p in self.repository.list_model_profiles(instance_id) if p["role"] in {role, "orchestrator"} and p["status"] == "active"]
        candidates.sort(key=lambda p: (p["role"] != role, _SENSITIVITY_RANK.get(p["max_sensitivity"], -1)))
        for profile in candidates:
            if _SENSITIVITY_RANK.get(profile["max_sensitivity"], -1) < requested:
                continue
            if local_only and not bool(profile["config"].get("local", False)):
                continue
            adapter = self.adapters.get(profile["adapter"])
            if adapter is not None:
                return adapter, profile
        raise ModelRoutingError(f"no allowed model profile for role={role!r}, sensitivity={sensitivity!r}")


def validate_json_schema(value: Any, schema: dict[str, Any], path: str = "$", *, _root: dict[str, Any] | None = None) -> None:
    """Small deterministic validator for the subset needed by agent outputs."""
    root = _root or schema
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref.startswith("#/$defs/"):
            validate_json_schema(value, root["$defs"][ref.split("/")[-1]], path, _root=root)
            return
        raise ValueError(f"unsupported schema reference at {path}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: value is not in enum")
    kind = schema.get("type")
    valid = {"object": isinstance(value, dict), "array": isinstance(value, list), "string": isinstance(value, str), "integer": isinstance(value, int) and not isinstance(value, bool), "number": isinstance(value, (int, float)) and not isinstance(value, bool), "boolean": isinstance(value, bool), "null": value is None}
    if kind in valid and not valid[kind]:
        raise ValueError(f"{path}: expected {kind}")
    if isinstance(value, dict):
        for required in schema.get("required", []):
            if required not in value:
                raise ValueError(f"{path}: missing required property {required!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            if extra:
                raise ValueError(f"{path}: unexpected properties {sorted(extra)}")
        for key, child in properties.items():
            if key in value:
                validate_json_schema(value[key], child, f"{path}.{key}", _root=root)
    if isinstance(value, list) and "items" in schema:
        for index, child in enumerate(value):
            validate_json_schema(child, schema["items"], f"{path}[{index}]", _root=root)


def parse_structured_text(text: str, schema: dict[str, Any]) -> Any:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"model returned invalid JSON: {exc.msg}") from exc
    validate_json_schema(value, schema)
    return value
