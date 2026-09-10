# AGENTS.md

## Purpose

This file is the primary working contract for coding agents contributing to OpenMuse. Read it before making changes.

OpenMuse is an open-source, model-agnostic personal AI agent inspired by the publicly described product/security architecture of Meta Muse, but implemented independently and designed for self-hosting, portability, and multiple model providers.

The current phase is **architecture-first pre-alpha**. Do not optimize for feature count. Preserve trust boundaries and durable state semantics.

## Product invariant

OpenMuse is not a chat wrapper. It is a persistent personal-agent system with durable goals/tasks, memory, tools, browser access, background work, and deterministic security enforcement outside the main agent runtime.

## Security invariant

> Treat the agent execution environment as untrusted.

The runtime may process prompt injection, malicious files, generated code, compromised dependencies, or simply incorrect model output.

Therefore the runtime must not be able to grant itself:

- raw credentials;
- protected connector authority;
- unrestricted network egress;
- browser secret access;
- writes to security-plane code/policy;
- permission grants.

If a change weakens one of these boundaries, stop and update `THREAT-MODEL.md` and an ADR before implementation.

## Read these documents first

For architecture/security work, read:

1. `VISION.md`
2. `ARCHITECTURE.md`
3. `SECURITY.md`
4. `THREAT-MODEL.md`
5. `SENTINEL.md`
6. `MODEL-CONTRACT.md`
7. `GOALS-TASKS.md`
8. `MEMORY.md`
9. `SKILLS-CONNECTORS.md`
10. `ROADMAP.md`
11. `docs/meta-muse-research.md` when reasoning about Meta Muse behavior

Do not treat product claims about Meta Muse as implementation requirements unless an OpenMuse design document explicitly adopts them.

## Development priorities

Unless an issue/ADR says otherwise, work in this order:

1. durable domain/control-plane state;
2. provider-neutral model contract;
3. isolated execution runtime;
4. controlled public browser/egress;
5. Sentinel approvals/policy;
6. credential broker and privileged connector workers;
7. memory;
8. long-running goals/subagents/proactivity;
9. generated skills;
10. broader connectors/UI/hardening.

Do not add powerful credentialed actions before Sentinel exists in the execution path.

## Architecture boundaries

### Control plane

Owns:

- users/instances;
- conversations;
- goals;
- tasks;
- executions;
- schedules/events;
- orchestration;
- model profiles;
- memory metadata;
- artifacts metadata;
- audit coordination.

### Execution plane

Untrusted. Owns/uses:

- workspace;
- shell;
- generated code;
- runtime skills;
- projected memory;
- subagent execution;
- temporary files.

It must not own credentials or permission records.

### Security plane

Trusted computing base. Owns:

- Sentinel policy/decisions;
- grants/approvals;
- credential broker;
- privileged connector workers;
- browser credential path;
- network egress authority;
- security audit events.

Keep this code small, typed, testable, and difficult for the runtime to mutate.

## Model independence

Core domain code must not import provider-specific request/response classes.

Do not persist provider-specific objects as authoritative task state.

Implement providers behind `ModelAdapter`-style contracts described in `MODEL-CONTRACT.md`.

OpenAI-compatible APIs and LiteLLM are supported paths, not the semantic definition of OpenMuse.

When adding a model feature:

- declare capability explicitly;
- define normalized behavior;
- add adapter conformance tests;
- specify fallback behavior;
- preserve sensitivity/routing policy.

Do not silently fall back from local/private execution to a cloud provider when policy forbids it.

## State and durability

Never make the current model transcript the sole source of durable state.

Persist explicitly:

- goal status;
- task status;
- plan/checkpoint;
- approvals;
- schedules;
- execution attempts;
- artifacts;
- memory/provenance;
- audit events.

Long-running work must be restart-safe.

For external writes, handle the crash window where the side effect may have happened but local success was not persisted. Prefer idempotency keys and verification before retry.

## Tool and connector rules

A model tool call is an untrusted proposal until:

1. schema validated;
2. policy evaluated;
3. required authorization exists;
4. trusted worker executes the concrete action.

Do not place reusable connector tokens in runtime environment variables or workspace files.

Built-in credentialed connectors should execute outside the runtime. Runtime CLIs/RPC clients should be thin, typed, and non-secret.

Generated skills receive no credentials automatically.

## Browser rules

Do not give the main runtime unrestricted CDP access by default.

Browser access should go through `browserd`/broker abstractions.

Prefer constrained browser actions and accessibility snapshots.

Pause automation while a user is manually entering protected credentials or taking control.

Protected browser actions must be eligible for Sentinel authorization.

## Memory rules

Memory:

- needs provenance;
- can be edited/deleted by the user;
- may have sensitivity and scope;
- cannot grant permission;
- cannot be trusted solely because it is old/persistent;
- should distinguish direct user statements from inference/external observations.

Vector embeddings are derived indexes, not authoritative memory.

## Approval rules

Do not interpret chat replies as authoritative security grants.

Approvals use structured trusted UI/API paths and produce scoped capability grants.

A grant must match the concrete action at execution time.

High-risk actions should fail closed if Sentinel is unavailable.

## Networking rules

The target runtime has no direct egress route. Network access goes through controlled brokers/proxies.

Any temporary development exception must be clearly marked unsafe and must not become the default production path.

Block SSRF to private/link-local/loopback/metadata destinations by default.

## Code quality

When implementation begins:

- prefer small modules with explicit interfaces;
- type public/internal contracts;
- validate all model/tool/connector inputs;
- use structured errors with stable codes;
- preserve correlation IDs across goal/task/execution/tool/audit events;
- avoid global mutable singleton state;
- make retries and idempotency explicit;
- redact secrets in logs;
- write migrations for schema changes;
- document security-relevant configuration.

## Tests

Tests are part of the architecture.

For every feature, add the narrowest useful tests at the same time.

### Minimum test families

- domain/unit tests;
- database/migration tests;
- model adapter conformance tests;
- runtime isolation integration tests;
- Sentinel policy/grant tests;
- connector authorization tests;
- browser broker tests;
- restart/recovery tests;
- security/red-team regression fixtures.

Do not weaken or rewrite tests simply to make a change pass. If a documented invariant and a test disagree, stop and reconcile the design explicitly.

## Security regression principle

Every meaningful security bug should become a regression test.

Examples:

- direct egress bypass;
- credential appearing in runtime output;
- grant scope bypass;
- approval replay;
- SSRF;
- connector using wrong credential;
- prompt-injection fixture causing external side effect;
- memory poisoning creating authority;
- duplicate write after crash.

## Dependency policy

Before adding a dependency, consider:

- maintenance/activity;
- license compatibility;
- security history;
- transitive size;
- whether it runs in the TCB;
- whether a smaller standard-library implementation is safer for privileged code.

Security-plane services should minimize dependencies.

## Repository structure

Do not create large empty scaffolds. Add directories when a milestone needs them.

The expected eventual shape is described in `ROADMAP.md`.

When introducing a new top-level component, update `ARCHITECTURE.md` if its responsibility/trust boundary is not already clear.

## ADRs

Use `docs/adr/` for decisions that are difficult to reverse or materially affect:

- trust boundaries;
- runtime backend;
- language/runtime for core services;
- database architecture;
- model contract changes;
- credential paths;
- browser privilege;
- egress enforcement;
- multi-tenant deployment.

An ADR should record context, decision, alternatives, consequences, and status.

## Documentation discipline

When implementation changes reality, update the documentation in the same PR.

Use precise language:

- **implemented** — exists and is tested;
- **planned** — accepted design, not yet implemented;
- **experimental** — present but unstable;
- **inferred** — reasoned from evidence, not confirmed;
- **Meta-documented** — directly supported by a public Meta source.

Do not claim security properties that tests/deployment do not yet enforce.

## Working with Meta Muse references

OpenMuse uses only public information as inspiration.

Do not:

- scrape/private-reverse-engineer authenticated Meta Muse internals;
- present inferred Meta behavior as confirmed;
- copy proprietary source code;
- couple OpenMuse to private Meta endpoints.

Do:

- cite public sources in research docs;
- separate observed facts from OpenMuse design choices;
- independently implement the architecture.

## Naming

`OpenMuse` is currently a development codename. Avoid building package/protocol assumptions that make a future rename unnecessarily difficult.

## Before committing

For code changes, verify as applicable:

```text
format
lint
typecheck
unit tests
integration tests
security tests
migration tests
```

Report the exact commands run and any test that could not run.

## Definition of done

A contribution is not done merely when the happy path works. It is done when:

- behavior is covered by appropriate tests;
- restart/failure semantics are understood;
- security boundary is preserved;
- logs do not expose secrets;
- documentation is current;
- model-provider assumptions are explicit;
- user-visible/audit state is coherent.

When in doubt, choose the design that gives the untrusted runtime less ambient authority.
