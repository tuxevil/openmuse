# OpenMuse Roadmap

## Strategy

OpenMuse should be built as a sequence of **vertical security-preserving slices**, not as a checklist of disconnected agent features.

The first useful proof is not "the model can call tools." It is:

> A durable goal can execute useful background work in an isolated runtime, survive restart, use a replaceable model, and request a sensitive action through a deterministic approval path that the runtime cannot bypass.

Each milestone below has explicit exit criteria.

## Phase 0 — Foundation and contracts

**Goal:** make the project implementable without architecture ambiguity.

Deliverables:

- repository structure;
- architecture and trust boundaries;
- threat model;
- Sentinel protocol draft;
- model adapter contract;
- goal/task/execution schemas;
- memory schema/provenance model;
- skill/connector manifest drafts;
- coding-agent contribution instructions;
- ADR process;
- initial test strategy.

Exit criteria:

- trust domains are explicit;
- raw credentials are forbidden from runtime by design;
- runtime networking is defined as brokered/controlled;
- model provider is not encoded into domain schemas;
- first MVP vertical slice is agreed.

## Phase 1 — Durable single-user control plane

**Status:** implemented in the initial modular-monolith slice. PostgreSQL
migrations, SQLite contract tests, durable lifecycle objects, transactional
schedule deduplication, restart checkpoints, outbox records, and audit links
are available under `src/openmuse/`.

**Goal:** create persistent domain objects before autonomy.

Implement:

- PostgreSQL schema/migrations;
- user/instance identity;
- conversations/messages;
- goals;
- tasks;
- executions;
- events/outbox;
- schedules;
- artifacts metadata;
- audit events;
- basic API/CLI.

Prefer a modular monolith initially. Process boundaries should reflect trust boundaries, not arbitrary service decomposition.

Exit criteria:

- goal/task state survives process restart;
- scheduler can create a task execution without active client;
- duplicate schedule delivery is deduplicated;
- audit trail links goal -> task -> execution.

## Phase 2 — Model-neutral agent loop

**Status:** implemented in the initial modular-monolith slice. The OpenMuse
adapter contract, deterministic fake backend, OpenAI-compatible backend,
normalized streaming/tool calls, structured-output validation, usage tracking,
role profiles, and local-only routing hooks are available under
`src/openmuse/`.

**Goal:** prove provider independence early.

Implement:

- `ModelAdapter` interface;
- OpenAI-compatible adapter;
- second materially different adapter or backend;
- streaming normalization;
- tool-call normalization;
- structured-output validation;
- context builder;
- cancellation/timeouts;
- usage/cost reporting;
- role-based model profiles;
- sensitivity-aware routing hooks.

LiteLLM can be supported immediately as an OpenAI-compatible target, but tests must also run without LiteLLM so it does not become an accidental hard dependency.

Exit criteria:

- same deterministic test task passes with two backends;
- provider-specific response objects do not leak into domain tables;
- restart can rebuild context from durable state;
- local-only routing policy refuses cloud fallback.

## Phase 3 — Isolated execution runtime

**Goal:** give the agent a computer without giving it the host.

Implement:

- `RuntimeDriver` interface;
- rootless container backend;
- per-user/per-instance workspace;
- shell execution with resource/time limits;
- readonly base image;
- explicit writable mounts;
- no host network;
- no host PID namespace;
- no Docker socket;
- dropped Linux capabilities/seccomp;
- task/process identity;
- runtime lifecycle/recovery.

Exit criteria:

- runtime cannot read host fixture secrets;
- runtime cannot access external network directly;
- runtime can execute code and persist authorized workspace files;
- runtime restart does not destroy durable user workspace;
- runaway process limits work.

## Phase 4 — Public-web browser slice

**Goal:** support useful research/monitoring with no private connector credentials yet.

Implement:

- `browserd` broker;
- Chromium + Playwright;
- constrained browser actions;
- accessibility snapshot;
- screenshot support;
- navigation policy;
- download handling into controlled workspace;
- public egress proxy;
- SSRF/private-IP blocking;
- browser-agent role.

First reference goal:

```text
Watch for product X below threshold Y and notify me when a new matching result appears.
```

Exit criteria:

- scheduled monitor works with app closed;
- state is compared across runs;
- no notification is sent for unchanged result;
- runtime cannot obtain unrestricted CDP;
- private/metadata destinations are blocked;
- browser session can be inspected in activity log.

## Phase 5 — Sentinel v1 and trusted approval path

**Goal:** make deterministic authorization real before adding powerful writes.

Implement:

- Sentinel service;
- typed `ActionRequest`/`Decision`;
- grants;
- pending approvals;
- secure client approval endpoint/UI;
- once/task/time-bounded scopes;
- revocation;
- risk registry;
- fail-closed behavior;
- audit events;
- canonicalization/replay protection.

Exit criteria:

- chat text cannot create a grant;
- one-time grant cannot be reused;
- task grant cannot cross task boundary;
- modified post-approval request fails;
- Sentinel outage blocks protected actions.

## Phase 6 — Credential broker + first privileged connector

**Goal:** perform authenticated work while keeping raw credentials out of runtime.

Implement:

- credential broker;
- encrypted credential store;
- connector worker identity/ACLs;
- surrogate/opaque credential references;
- email connector read path;
- email create-draft/send path;
- sensitive email redaction rules;
- Sentinel connector policy.

Reference flow:

```text
Read recent mail -> summarize actionable items -> prepare reply -> ask user -> send.
```

Exit criteria:

- `env`, filesystem, logs, and tool output in runtime contain no raw OAuth token;
- wrong worker cannot redeem credential;
- read can be allowed while send is denied/ask;
- send after approval succeeds exactly once;
- injected email cannot exfiltrate protected fixture data.

## Phase 7 — Memory v1

**Goal:** create useful long-term context without hidden opaque memory.

Implement:

- structured memory records;
- provenance;
- readable memory projection/files;
- retrieval interface;
- conflict/supersession;
- edit/delete APIs;
- sensitivity labels;
- model routing integration;
- optional pgvector/hybrid index.

Exit criteria:

- memory survives restart and can be exported;
- user can inspect/edit/delete without model mediation;
- memory source is visible;
- poisoned external content cannot create permission;
- restricted memory stays out of forbidden providers.

## Phase 8 — Goals, subagents, and proactive work

**Goal:** move from scheduled scripts to a convincing persistent agent.

Implement:

- plan versions;
- task dependencies;
- bounded subagent fan-out;
- execution budgets;
- event-driven triggers;
- waiting-for-user state;
- notification evaluator;
- digest vs immediate notification;
- Ideas proposals;
- goal progress UI.

Exit criteria:

- two goals run concurrently;
- child tasks are bounded by depth/fan-out/budget;
- task waits/resumes across user approval/input;
- background result is surfaced only when materially new;
- goal can be paused/cancelled and its watches stop.

## Phase 9 — Skills and self-extension

**Goal:** let OpenMuse build reusable capabilities safely.

Implement:

- skill manifests and discovery;
- staged generated-skill workspace;
- skill tests;
- install/enable/disable/version lifecycle;
- provenance/content hashes;
- skill-specific dependencies;
- MCP runtime adapter;
- generic authenticated HTTP broker design/prototype.

Reference flow:

```text
User asks for unsupported local/API integration
-> agent researches interface
-> creates skill
-> tests it
-> asks to install if policy requires
-> later reuses it
```

Exit criteria:

- generated skill becomes reusable;
- generated skill cannot edit security plane;
- install does not grant credentials;
- declared capabilities are visible before install;
- skill can be rolled back/disabled.

## Phase 10 — Broader connectors and rich artifacts

**Goal:** make OpenMuse useful across common personal workflows.

Potential connectors:

- calendar;
- GitHub;
- files/storage;
- Home Assistant;
- task/project systems;
- messaging;
- custom HTTP connections.

Artifact work:

- versioned documents;
- HTML dashboards;
- reports;
- structured data exports;
- live artifacts linked to goals.

Exit criteria:

- at least three credentialed integrations follow the same security contract;
- no connector gets special-case bypass around Sentinel/authd;
- artifacts survive and remain linked to provenance.

## Phase 11 — Hardened security

**Goal:** reduce the gap between architectural intent and stronger isolation.

Explore/implement:

- stronger runtime backend (systemd-nspawn/microVM/gVisor/etc.);
- kernel-level process attribution;
- cgroup/eBPF egress enforcement;
- taint/data-flow tracking;
- independent prompt-injection classifiers;
- signed updates;
- hash-chained audit ledger;
- hardened browser isolation;
- security fuzzing/red-team suite;
- third-party security review.

Exit criteria are security-review driven rather than feature-count driven.

## Phase 12 — Portable backup/export/restore

**Goal:** make ownership operationally real.

Implement versioned export of:

- memory;
- goals/tasks/history;
- artifacts;
- workspace;
- skills;
- model profiles excluding secrets;
- connection metadata;
- permissions/grants where safe/meaningful;
- audit history.

Credential material should require a separate encrypted migration path or re-binding.

Exit criteria:

- export from installation A;
- restore into clean installation B;
- reconnect credentials;
- resume a paused goal with preserved state.

## Phase 13 — Hosted/multi-user deployment

**Goal:** support a provider-operated OpenMuse without weakening single-user ownership contracts.

Requirements before claiming safe multi-user operation:

- tenant isolation architecture;
- per-tenant runtime/security boundary;
- provisioning lifecycle;
- encrypted backups;
- operator access model;
- rate/cost quotas;
- incident response;
- privacy policy matching actual implementation;
- threat-model expansion.

Confidential-computing deployment may be explored later, but should not be marketed before it is technically verifiable.

## Parallel workstreams

Several tracks can proceed alongside the vertical milestones without blocking them.

### UI/UX

Prototype Chat, Goals, Ideas, Activity, Memory, Connections, Skills, Models, Permissions, and Computer views.

### Evaluations

Create repeatable evals for:

- long-horizon instruction following;
- tool-call correctness;
- model portability;
- browser robustness;
- prompt-injection resistance;
- notification quality;
- memory extraction/retrieval;
- cost/latency.

### Model benchmarking

Test local and hosted models behind identical roles/contracts. Results inform routing; they must not change the architecture.

### OpenClaw/other project study

Continuously evaluate reusable open-source patterns/components. Reuse only where trust boundaries, licenses, and architecture fit.

## What not to build first

Do not prioritize before the secure vertical slice:

- dozens of connectors;
- mobile apps;
- polished avatar customization;
- complex multi-tenant Kubernetes deployment;
- custom foundation model training;
- marketplace/registry infrastructure;
- kernel-level taint before a simpler egress policy works;
- autonomous edits to core OpenMuse code.

## Suggested repository structure when coding begins

```text
openmuse/
  apps/
    gateway/
    web/
  services/
    orchestrator/
    sentinel/
    authd/
    browserd/
  packages/
    domain/
    model-contract/
    runtime-contract/
    connector-sdk/
    skill-sdk/
  connectors/
    gmail/
    calendar/
  skills/
  runtime/
    images/
    drivers/
  migrations/
  tests/
    integration/
    security/
    evals/
  docs/
    adr/
```

Do not create this entire tree as empty scaffolding. Add components as the milestone needs them.

## Immediate implementation backlog after architecture merge

1. Choose control-plane language between Python and TypeScript based on the team/agent development workflow.
2. Define domain schemas for Goal, Task, Execution, Event, AuditEvent.
3. Bring up PostgreSQL + migrations.
4. Implement model adapter interface + OpenAI-compatible adapter.
5. Implement deterministic fake model for integration tests.
6. Implement scheduler/outbox and restart recovery.
7. Implement `RuntimeDriver` with rootless container backend.
8. Prove direct runtime egress is blocked.
9. Implement public browser broker.
10. Run the first marketplace-monitor vertical slice.
11. Implement Sentinel v1 before any credentialed write connector.

This sequence should remain the default unless implementation discoveries justify an ADR changing it.
