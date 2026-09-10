# ADR 0002: OpenMuse Owns a Provider-Neutral Model Contract

- **Status:** Accepted
- **Date:** 2026-09-10

## Context

OpenMuse must support local and hosted models from different providers. Many providers expose OpenAI-compatible APIs, and gateways such as LiteLLM make routing convenient, but tool calling, streaming, structured output, multimodal input, errors, usage accounting and reasoning controls vary.

If domain code persists or depends on one provider's request/response objects, model portability becomes superficial.

## Decision

OpenMuse will define and version its own internal model contract.

Provider adapters translate between that contract and provider APIs. OpenAI-compatible APIs are a first-class adapter target, not the semantic source of truth.

Core domain schemas for goals, tasks, permissions, memory and connectors must not depend on provider-specific classes or hidden conversation/session state.

## Consequences

Positive:

- models can be replaced without rewriting the control plane;
- model roles can be routed independently;
- local-only/privacy routing can be enforced;
- adapter conformance can be tested.

Costs:

- adapters require normalization work;
- lowest-common-denominator pressure must be actively avoided;
- provider-specific optimizations need optional extension fields/capability flags.

## Rejected alternative

**Make LiteLLM/OpenAI API objects the internal domain model.** Rejected because it would make an operational gateway an architectural dependency and leak compatibility quirks into durable OpenMuse state.

## Follow-up

Implement adapter conformance tests before adding many providers. Fallback must never broaden data exposure beyond routing policy.
