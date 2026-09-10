# OpenMuse

> **Your personal AI. Your computer. Your models. Your rules.**

OpenMuse is an experimental, model-agnostic personal AI agent **intended to be released as open source**, designed to keep working on your behalf across long-running goals, tools, applications, files, and the web.

The project is inspired by product and security concepts publicly described for Meta Muse, while deliberately pursuing a different implementation goal: a portable, self-hostable agent runtime that is not tied to Meta infrastructure, Meta models, or any single model provider.

OpenMuse is **not** an unofficial client for Meta Muse and does not use or depend on private Meta APIs. `OpenMuse` is currently a development codename; naming and trademark review remain open project decisions.

## Status

**Pre-alpha / architecture phase.** The repository currently defines the product vision, architecture, security model, model contract, runtime boundaries, memory design, goals/tasks model, skills/connectors model, and implementation roadmap before substantial code is written.

## Core idea

A useful personal agent needs more than an LLM with function calling. OpenMuse treats the agent as a persistent software system with its own constrained computer environment:

- persistent workspace and memory;
- shell, files, browser, skills, and generated tools;
- long-running goals, scheduled work, and event-driven work;
- concurrent subagents and specialized workers;
- user-visible activity and audit history;
- model routing through replaceable providers;
- credentials that the main agent cannot read;
- deterministic permission enforcement outside the agent;
- network egress controlled by an independent security plane.

The central security assumption is deliberately pessimistic:

> **The agent runtime may be wrong, manipulated, or compromised. Security must not depend on the agent choosing to behave.**

## Architectural principles

OpenMuse is being designed around the following principles:

1. **Model agnostic by construction.** The runtime must not depend on the behavior, tool syntax, proprietary memory, or hidden state of one model provider.
2. **Local-first, cloud-capable.** The same logical runtime should be deployable on a personal machine, home server, VM, or managed cloud environment.
3. **Persistent, not turn-bound.** Conversations are an interface to durable goals, tasks, state, memory, artifacts, and automations.
4. **Security outside the model.** Authorization, credential access, network egress, and sensitive actions are enforced by deterministic services outside the untrusted agent runtime.
5. **Least privilege.** Agents and tools receive the minimum capabilities required for the current task.
6. **Inspectable state.** Users should be able to understand what the agent knows, what it is doing, what it plans to do, and why an action was permitted.
7. **Portable data.** Memory, goals, artifacts, skills, configuration, and audit data should be exportable rather than trapped in a hosted service.
8. **Open interfaces.** Prefer standard or broadly reusable interfaces such as OpenAI-compatible model APIs, MCP, Agent Skills-style packages, CLIs, HTTP, and explicit typed contracts.
9. **Replaceable subsystems.** Models, browser implementations, sandboxes, vector stores, schedulers, and connector backends should be replaceable behind stable contracts.
10. **Agent-extensible, security-protected.** The agent may create skills, scripts, artifacts, and workspace code, but it must not be able to rewrite the services that police it.

## Conceptual architecture

```text
Clients: Web / Mobile / WhatsApp / CLI / other channels
                         |
                         v
                  OpenMuse Gateway
                         |
          +--------------+---------------+
          |              |               |
          v              v               v
    Conversations      Goals         Event Router
                         |               Scheduler
                         +-------+-------+
                                 |
                                 v
                       Agent Orchestrator
                                 |
                      Model Router / Adapters
                                 |
               OpenAI-compatible and native APIs
                                 |
                         UNTRUSTED RUNTIME
             files / shell / skills / code / subagents
                         |                 |
                         |                 +--> Browser Broker
                         v
                    SENTINEL PLANE
        policy / approvals / egress / audit / data controls
             |                         |
             v                         v
       Credential Broker         Connector Workers
             |                         |
             +-----------+-------------+
                         |
                         v
                    Outside world
```

## Read the design

Start here:

- [VISION.md](VISION.md) — mission, product thesis, principles, non-goals, and v1 definition of success.
- [ARCHITECTURE.md](ARCHITECTURE.md) — components, trust domains, data stores, runtime and core contracts.
- [SECURITY.md](SECURITY.md) — security invariants, credential architecture, egress, browser and connector policy.
- [THREAT-MODEL.md](THREAT-MODEL.md) — assets, attackers, concrete threats, mitigations, residual risks, and test categories.
- [SENTINEL.md](SENTINEL.md) — deterministic action authorization, grants, approvals, network egress and credential surrogation.
- [MODEL-CONTRACT.md](MODEL-CONTRACT.md) — provider-neutral model adapters, capabilities, tools, routing and fallback semantics.
- [MEMORY.md](MEMORY.md) — inspectable memory, provenance, sensitivity, retrieval, conflict handling and export.
- [GOALS-TASKS.md](GOALS-TASKS.md) — durable goals, tasks, executions, scheduling, events, subagents and notifications.
- [SKILLS-CONNECTORS.md](SKILLS-CONNECTORS.md) — extension model, generated skills, privileged connectors, MCP and CLI conventions.
- [ROADMAP.md](ROADMAP.md) — vertical implementation sequence and milestone exit criteria.
- [AGENTS.md](AGENTS.md) — working contract for coding agents contributing to the repository.
- [docs/meta-muse-research.md](docs/meta-muse-research.md) — source-backed research separating Meta-documented behavior from OpenMuse interpretation.
- [docs/adr/](docs/adr/) — architecture decisions that should not be changed casually.

## What OpenMuse is not

OpenMuse is not intended to be:

- a wrapper around a single frontier model;
- a chat UI with a collection of tools;
- an unrestricted autonomous shell running with the user's credentials;
- a clone of Meta's private implementation;
- a replacement for deterministic security controls with prompt instructions;
- a system where installing a skill implicitly grants it every credential or network destination.

## Influences

OpenMuse studies public ideas from several agent systems and standards, including Meta Muse and its published Secure VM/Sentinel design, OpenClaw, MCP, CLI-oriented agent skills, browser automation systems, and conventional capability-based security architectures.

Public Meta sources that motivated the project include:

- https://ai.meta.com/muse/
- https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/
- https://research.meta.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse
- https://introducing.muse.ai/

These sources describe Meta's product. They are references for research and interoperability thinking, not a statement that OpenMuse is affiliated with or endorsed by Meta.

## Development philosophy

The first milestone is intentionally narrow: prove that one OpenMuse instance can accept a long-running goal, persist it, execute useful work in an isolated runtime, use a replaceable model, survive process restarts, request deterministic approval for a sensitive action, and resume after approval with a complete audit trail.

Everything else should build on that foundation.

## License

A project license has **not yet been selected**. Until a license is added, the repository should not be represented as legally open-source software despite that being the project's intent. License choice is an explicit project decision still to be made.
