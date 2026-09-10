"""Persistent, provider-neutral agent loop for Phase 2."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from typing import Any

from .context import ContextBuilder
from .domain import ModelMessage, ModelRequest, ToolCall, ToolDefinition, ToolResult, Usage, text_part
from .model import ModelAdapter, ModelRouter, parse_structured_text
from .repository import ControlPlaneRepository


class ToolRegistry:
    """Validates proposals before dispatching safe, explicitly registered tools."""

    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        self._executors: dict[str, Callable[[dict[str, Any]], Any]] = {}

    def register(self, definition: ToolDefinition, executor: Callable[[dict[str, Any]], Any]) -> None:
        if definition.name == "grant_permission":
            raise ValueError("security authority cannot be exposed as a model tool")
        self._definitions[definition.name] = definition
        self._executors[definition.name] = executor

    def definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(self._definitions.values())

    def execute(self, call: ToolCall) -> ToolResult:
        definition = self._definitions.get(call.tool)
        if definition is None:
            return ToolResult(call_id=call.call_id, status="rejected", content=(text_part(f"Unknown tool: {call.tool}"),), system={"code": "unknown_tool"})
        try:
            _validate_arguments(call.arguments, definition.input_schema)
            result = self._executors[call.tool](call.arguments)
        except Exception as exc:
            return ToolResult(call_id=call.call_id, status="failed", content=(text_part(str(exc)),), system={"code": "tool_execution_failed"})
        content = result if isinstance(result, tuple) else (text_part(json.dumps(result, ensure_ascii=False, sort_keys=True)) if not isinstance(result, str) else text_part(result),)
        return ToolResult(call_id=call.call_id, status="ok", content=content if isinstance(content, tuple) else (content,), system={"tool": call.tool})


def _validate_arguments(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{path}: tool arguments must be an object")
    for name in schema.get("required", []):
        if name not in value:
            raise ValueError(f"{path}: missing required argument {name!r}")
    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False and set(value) - set(properties):
        raise ValueError(f"{path}: unexpected arguments")
    for name, spec in properties.items():
        if name not in value:
            continue
        expected = spec.get("type")
        actual = value[name]
        valid = {"string": isinstance(actual, str), "integer": isinstance(actual, int) and not isinstance(actual, bool), "number": isinstance(actual, (int, float)) and not isinstance(actual, bool), "boolean": isinstance(actual, bool), "object": isinstance(actual, dict), "array": isinstance(actual, list)}
        if expected in valid and not valid[expected]:
            raise ValueError(f"{path}.{name}: expected {expected}")


class AgentRunError(RuntimeError):
    def __init__(self, message: str, *, code: str = "agent_error") -> None:
        super().__init__(message)
        self.code = code


class AgentHarness:
    def __init__(self, repository: ControlPlaneRepository, adapter: ModelAdapter | None = None, *, router: ModelRouter | None = None, context_builder: ContextBuilder | None = None, tools: ToolRegistry | None = None, max_turns: int = 8) -> None:
        if adapter is None and router is None:
            raise ValueError("AgentHarness requires an adapter or a ModelRouter")
        self.repository = repository
        self.adapter = adapter
        self.router = router
        self.context_builder = context_builder or ContextBuilder(repository)
        self.tools = tools or ToolRegistry()
        self.max_turns = max_turns

    def run(self, execution_id: str, *, role: str = "orchestrator", sensitivity: str = "private", local_only: bool = False, cancel_event: threading.Event | None = None, response_format: dict[str, Any] | None = None) -> dict[str, Any]:
        self.repository.claim_execution(execution_id)
        total = Usage()
        transcript: list[dict[str, Any]] = []
        try:
            execution = self.repository.get_execution(execution_id)
            task = self.repository.get_task(execution["task_id"])
            goal = self.repository.require("goals", task["goal_id"]) if task["goal_id"] else None
            adapter = self.adapter
            if adapter is None:
                assert self.router is not None
                adapter, _profile = self.router.resolve(goal["instance_id"], role, sensitivity, local_only=local_only)
            if response_format and not adapter.capabilities.structured_output:
                raise AgentRunError("selected model does not support structured output", code="capability_mismatch")
            for turn in range(self.max_turns):
                if cancel_event and cancel_event.is_set():
                    raise AgentRunError("execution cancelled", code="cancelled")
                request = self.context_builder.build(execution_id, role=role, tools=self.tools.definitions(), response_format=response_format)
                if transcript:
                    request = ModelRequest(execution_id=request.execution_id, role=request.role, messages=request.messages + tuple(ModelMessage(role=x["role"], content=(text_part(x["content"]),), tool_call_id=x.get("tool_call_id")) for x in transcript), tools=request.tools, response_format=request.response_format, limits=request.limits, metadata=request.metadata)
                response = adapter.complete(request)
                total = _sum_usage(total, response.usage)
                text = " ".join(part.text or "" for part in response.message.content if part.type == "text")
                transcript.append({"role": "assistant", "content": text, "tool_calls": [{"call_id": c.call_id, "tool": c.tool, "arguments": c.arguments} for c in response.tool_calls]})
                checkpoint = {"turn": turn + 1, "last_text": text, "tool_calls": transcript[-1]["tool_calls"], "transcript": transcript[-4:]}
                self.repository.checkpoint_execution(execution_id, checkpoint)
                if response_format and text:
                    parsed = parse_structured_text(text, response_format.get("json_schema", {}).get("schema", response_format.get("schema", response_format)))
                    checkpoint["structured_output"] = parsed
                    self.repository.checkpoint_execution(execution_id, checkpoint)
                if not response.tool_calls:
                    return self.repository.finish_execution(execution_id, status="succeeded", checkpoint=checkpoint, usage=_usage_dict(total))
                for call in response.tool_calls:
                    result = self.tools.execute(call)
                    result_text = " ".join(part.text or "" for part in result.content)
                    transcript.append({"role": "tool", "content": result_text, "tool_call_id": call.call_id})
            raise AgentRunError("maximum model turns exceeded", code="turn_limit")
        except AgentRunError as exc:
            status = "cancelled" if exc.code == "cancelled" else "failed"
            return self.repository.finish_execution(execution_id, status=status, checkpoint={"transcript": transcript}, usage=_usage_dict(total), error={"code": exc.code, "message": str(exc)})
        except Exception as exc:
            return self.repository.finish_execution(execution_id, status="failed", checkpoint={"transcript": transcript}, usage=_usage_dict(total), error={"code": getattr(exc, "code", "agent_error"), "message": str(exc)})


def _sum_usage(left: Usage, right: Usage) -> Usage:
    return Usage(input_tokens=left.input_tokens + right.input_tokens, output_tokens=left.output_tokens + right.output_tokens, total_tokens=left.total_tokens + right.total_tokens, estimated_cost=(left.estimated_cost or 0) + (right.estimated_cost or 0))


def _usage_dict(usage: Usage) -> dict[str, Any]:
    return {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens, "total_tokens": usage.total_tokens, "estimated_cost": usage.estimated_cost, "currency": usage.currency}
