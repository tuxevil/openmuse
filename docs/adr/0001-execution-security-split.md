# ADR 0001: Separate Untrusted Execution from Security Authority

- **Status:** Accepted
- **Date:** 2026-09-10

## Context

OpenMuse gives an AI agent access to untrusted web/content, generated code, shell execution, private user context, and eventually external services. Prompt injection and model mistakes cannot be treated as exceptional events.

A single process that both interprets untrusted content and holds credentials/authorization would make the model's behavior part of the security boundary.

## Decision

OpenMuse will use two primary trust domains:

1. an **untrusted execution plane** for agent reasoning context, shell, generated code, skills, workspace and subagents;
2. a **trusted security plane** for Sentinel policy, credential brokerage, privileged connector workers, browser credential handling, network egress authority and security audit.

The execution plane cannot grant itself authority or directly mutate security-plane code/policy.

## Consequences

Positive:

- prompt injection does not automatically imply credential compromise;
- generated code can be powerful without ambient host authority;
- permissions become testable deterministic contracts;
- security code can remain small and separately hardened.

Costs:

- additional IPC/process boundaries;
- connector implementations need privileged-worker patterns;
- local deployment is more complex than one monolithic process;
- debugging requires correlation across components.

## Rejected alternative

**Single trusted agent process with secrets and prompt-based rules.** Rejected because behavior instructions are not reliable authorization boundaries for adversarial agent workloads.

## Follow-up

Any proposal that gives the runtime raw reusable credentials, direct unrestricted egress, host control sockets, or security-policy write access requires a new ADR and threat-model update.
