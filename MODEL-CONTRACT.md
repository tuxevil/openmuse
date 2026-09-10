# OpenMuse Model Contract

## Goal

OpenMuse must be able to change models and model providers without changing the semantics of goals, tasks, permissions, memory, connectors, or the runtime security model.

This requires an OpenMuse-owned model contract. OpenAI-compatible APIs are an important transport target, and LiteLLM is a useful router, but neither should define the internal semantics of the system.

## Design rules

1. Models propose; deterministic services authorize.
2. Provider-specific fields stay inside adapters.
3. Tool schemas are generated from OpenMuse tool manifests, not handwritten per provider.
4. Streaming is normalized into OpenMuse events.
5. Model capability differences are explicit and queryable.
6. Fallback is policy-aware, not automatic at any cost.
7. Hidden provider state must not be required for durable task recovery.
8. The same task should be replayable against another model with an equivalent bounded context package.

## Model profile

A model profile is a durable configuration object such as:

```yaml
id: primary
adapter: openai-compatible
endpoint: http://litellm:4000/v1
model: openmuse-primary
capabilities:
  text: true
  vision: true
  tool_calling: true
  structured_output: true
  reasoning: optional
  computer_use: false
privacy:
  allowed_sensitivity: confidential
limits:
  context_tokens: 131072
  output_tokens: 8192
  timeout_seconds: 180
routing:
  fallbacks:
    - local-primary
```

Provider authentication belongs in the control/security configuration, not in the task context.

## Roles

OpenMuse should route by logical role rather than assuming one universal model.

Initial roles:

- `orchestrator` — general planning and task execution;
- `research` — retrieval-heavy work;
- `browser` — browser-specific reasoning;
- `coding` — generated tools/code;
- `memory` — extraction, reconciliation, summarization;
- `notification` — novelty/urgency evaluation;
- `safety_classifier` — optional independent classifier, never sole authorization authority.

A deployment may map all roles to one model or use different providers.

## Normalized request

Illustrative internal schema:

```json
{
  "execution_id": "exec_123",
  "role": "orchestrator",
  "messages": [
    {"role": "system", "content": [...]},
    {"role": "user", "content": [...]}
  ],
  "tools": [],
  "response_format": null,
  "limits": {
    "max_output_tokens": 4096,
    "deadline_ms": 120000
  },
  "metadata": {
    "goal_id": "goal_42",
    "task_id": "task_77",
    "sensitivity": "private"
  }
}
```

The request must not contain raw connector credentials.

## Content parts

Messages should support typed parts rather than only strings:

```text
Text
ImageReference
FileReference
ArtifactReference
ToolObservation
MemoryReference
UntrustedContent
```

`UntrustedContent` must preserve provenance and must not be flattened into trusted system instructions by an adapter.

Example:

```json
{
  "type": "untrusted_content",
  "source": {
    "kind": "web",
    "url": "https://example.com"
  },
  "content": "..."
}
```

## Tool contract

A tool exposed to a model has:

```text
name
version
description
JSON-schema input
JSON-schema output or result envelope
risk class
authority requirements
execution target
```

Example logical manifest:

```yaml
name: calendar.list_events
version: 1
input_schema: ...
execution_target: connector:calendar
risk: low
authority:
  connector: calendar
  action: read
```

The provider adapter converts this into the provider's function/tool syntax.

## Tool calls

Normalized tool proposal:

```json
{
  "call_id": "call_abc",
  "tool": "calendar.create_event",
  "arguments": {
    "title": "Dentist",
    "start": "2026-10-03T14:00:00-05:00"
  }
}
```

Tool arguments are untrusted model output until validated against schema and policy.

The model never receives a tool named `grant_permission` that can manufacture security authority.

## Tool results

Tool results must distinguish system metadata from untrusted external content:

```json
{
  "call_id": "call_abc",
  "status": "ok",
  "system": {
    "duration_ms": 211,
    "connector": "calendar",
    "request_id": "provider_req_123"
  },
  "content": [
    {
      "type": "untrusted_content",
      "source": {"kind": "connector", "id": "calendar"},
      "content": "..."
    }
  ]
}
```

A provider adapter must not silently convert tool content into developer/system messages.

## Normalized stream events

Adapters should emit a common event stream:

```text
response.started
text.delta
reasoning.summary.delta       # only if provider exposes suitable content
structured.delta
tool_call.started
tool_call.arguments.delta
tool_call.completed
usage.updated
response.completed
response.failed
```

OpenMuse does not require access to private chain-of-thought. Reasoning-capable models may expose summaries or opaque reasoning metadata according to provider policy.

## Capability negotiation

Before assigning work, the router must know relevant capabilities:

```yaml
text: true
vision: true
audio_input: false
tool_calling: true
parallel_tool_calls: true
structured_output: true
context_tokens: 131072
computer_use_native: false
reasoning_control:
  supported: true
  modes: [off, low, medium, high]
```

If a task requires vision and the chosen profile lacks vision, the router must deliberately choose another profile or fail. It should not silently drop the image.

## Context package

Durable task state is projected into a bounded model context for each execution.

Potential sections:

```text
system behavior
security/runtime constraints
current user request/event
goal summary
current task state
plan/checkpoint
relevant memory
available tools
recent observations
artifact references
budget/deadline
```

This projection is reconstructable from durable state. A provider's hidden conversation/session ID may be cached as an optimization but cannot be the only source of state.

## Memory interaction

Models do not write authoritative memory tables directly.

They can propose memory operations:

```json
{
  "op": "remember",
  "candidate": {
    "statement": "User prefers window seats",
    "source_message_id": "msg_123",
    "confidence": 0.96
  }
}
```

The memory service validates provenance, deduplicates/reconciles, applies policy, and persists.

Likewise, memory cannot grant permissions.

## Model routing policy

Routing should consider:

- role;
- required modalities/tools;
- sensitivity;
- local-only requirement;
- cost budget;
- latency target;
- quality profile;
- context size;
- provider health;
- user preference.

Example:

```yaml
routing:
  orchestrator:
    prefer: frontier
    fallback: local-large
  memory:
    prefer: local-small
  notification:
    prefer: local-small
  confidential:
    allowed_providers: [local]
```

## Fallback semantics

Fallback must never broaden data exposure.

If a task is marked `local_only`, outage of the local model results in `blocked/model_unavailable`, not an automatic call to a cloud provider.

Fallback also must not change security permissions. Connector authority exists independently of which model is active.

## Cost and budget

The model layer should return normalized usage:

```json
{
  "input_tokens": 1200,
  "output_tokens": 300,
  "cached_input_tokens": 800,
  "estimated_cost_usd": 0.0021,
  "provider_reported_cost_usd": null
}
```

Executions and goals may have budgets. Budget exhaustion is a control-plane state transition, not a prompt instruction.

## Cancellation

The orchestrator must be able to cancel active generation when:

- user interrupts/cancels;
- task superseded;
- deadline exceeded;
- policy violation detected;
- budget exceeded;
- provider stream stalls.

Adapters must make a best effort to abort network work and report cancellation state consistently.

## Structured output

Where a workflow requires a state transition, use schemas rather than parsing prose.

Examples:

- plan update;
- memory candidate;
- notification decision;
- tool arguments;
- task result;
- subagent delegation.

If a provider lacks native JSON schema enforcement, the adapter may use prompt/schema validation/retry, but the rest of OpenMuse sees the same validated object.

## Provider adapter boundary

Provider-specific concepts such as:

- Anthropic content blocks;
- OpenAI response IDs;
- Gemini function call fields;
- local engine sampler controls;
- LiteLLM metadata;
- prompt caching APIs;

must remain within adapter code or optional opaque metadata.

Core domain objects must not depend on them.

## OpenAI-compatible support

An OpenAI-compatible adapter is a first-class target because it unlocks:

- LiteLLM;
- vLLM;
- llama.cpp-compatible servers;
- many commercial providers;
- user-operated gateways.

However, OpenMuse should maintain conformance tests because "OpenAI-compatible" implementations often differ in tool calling, streaming, JSON schema, usage reporting, and error behavior.

## Adapter conformance tests

Every adapter should pass tests for:

- plain text completion;
- streaming text;
- one tool call;
- multiple tool calls where supported;
- invalid tool arguments;
- structured output;
- cancellation;
- timeout;
- provider error normalization;
- usage normalization;
- image input if declared;
- context-limit error;
- untrusted-content preservation;
- no credential material in logged request fixtures.

## MVP acceptance criterion

The first milestone must demonstrate the same durable task executed successfully using two meaningfully different model backends with no changes to goal/task/permission schemas or connector code.
