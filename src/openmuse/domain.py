from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4


class Sensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    PRIVATE = "private"
    RESTRICTED = "restricted"


class GoalStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class TaskStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    WAITING_FOR_USER = "waiting_for_user"
    WAITING_FOR_EVENT = "waiting_for_event"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNCERTAIN_EXTERNAL_STATE = "uncertain_external_state"


class ExecutionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def from_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


@dataclass(frozen=True)
class ContentPart:
    type: str
    text: str | None = None
    source: dict[str, Any] | None = None


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    risk: str = "low"
    authority: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    tool: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    status: str
    content: tuple[ContentPart, ...] = ()
    system: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float | None = None
    currency: str = "USD"


@dataclass(frozen=True)
class ModelCapabilities:
    text: bool = True
    vision: bool = False
    audio_input: bool = False
    tool_calling: bool = False
    parallel_tool_calls: bool = False
    structured_output: bool = False
    context_tokens: int = 8192
    reasoning_control: bool = False


@dataclass(frozen=True)
class ModelMessage:
    role: str
    content: tuple[ContentPart, ...]
    name: str | None = None
    tool_call_id: str | None = None


@dataclass(frozen=True)
class ModelLimits:
    max_output_tokens: int = 4096
    deadline_ms: int = 120_000


@dataclass(frozen=True)
class ModelRequest:
    execution_id: str
    role: str
    messages: tuple[ModelMessage, ...]
    tools: tuple[ToolDefinition, ...] = ()
    response_format: dict[str, Any] | None = None
    limits: ModelLimits = field(default_factory=ModelLimits)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelResponse:
    message: ModelMessage
    tool_calls: tuple[ToolCall, ...] = ()
    usage: Usage = field(default_factory=Usage)
    finish_reason: str | None = None
    provider_request_id: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelEvent:
    """Provider-neutral streaming event."""

    kind: str
    text_delta: str | None = None
    tool_call: ToolCall | None = None
    tool_call_arguments_delta: str | None = None
    usage: Usage | None = None
    error: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def text_part(text: str) -> ContentPart:
    return ContentPart(type="text", text=text)


def dataclass_json(value: Any) -> str:
    return json_text(asdict(value))
