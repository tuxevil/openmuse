# OpenMuse Architecture

## Scope

This document defines the initial system architecture for OpenMuse. It is intentionally implementation-oriented enough to guide development while keeping replaceable infrastructure behind stable contracts.

The architecture is based on five planes:

1. **Experience plane** — chat, goals, activity, approvals, memory, artifacts.
2. **Control plane** — durable application state, scheduling, orchestration, model routing, task lifecycle.
3. **Execution plane** — the untrusted agent runtime, generated code, shell, skills, subagents.
4. **Security plane** — Sentinel, credential broker, connector workers, browser broker, egress controls, audit.
5. **External plane** — model providers, websites, APIs, connected accounts, channels.

The most important invariant is:

> The execution plane must not be able to grant itself authority from the security plane.

## System context

```text
                   +-----------------------------+
                   |          User               |
                   +-----------------------------+
                      |      |        |       |
                      v      v        v       v
                    Web     CLI   WhatsApp   Mobile
                      \      |       /        /
                       +-----+------+---------+
                              |
                              v
                    +-------------------+
                    | OpenMuse Gateway  |
                    +-------------------+
                              |
          +-------------------+--------------------+
          |                   |                    |
          v                   v                    v
 +----------------+   +----------------+   +----------------+
 | Conversations  |   | Goals / Tasks  |   | Event Router   |
 +----------------+   +----------------+   +----------------+
          \                   |                    /
           +------------------+-------------------+
                              |
                              v
                  +------------------------+
                  | Agent Orchestrator     |
                  +------------------------+
                    |        |          |
                    v        v          v
                models    runtime    subagents
                    |        |          |
                    |        v          |
                    |  +-------------+  |
                    |  | Agent Cell  |<-+
                    |  +-------------+
                    |      |     |
                    |      |     +--------> Browser Broker
                    |      |
                    |      +--------------> Sentinel
                    |                         |
                    |                 +-------+-------+
                    |                 |               |
                    |                 v               v
                    |            Auth Broker     Connectors
                    |                 |               |
                    +-----------------+---------------+
                                      |
                                      v
                               Outside world
```

## Deployment profiles

OpenMuse must support at least two profiles without changing its logical contracts.

### Personal / local

A single user runs the control plane and security services on one Linux host. The execution plane runs in an isolated container or VM. The model may run on the same machine or remotely.

This is the first implementation target.

### Hosted / multi-user

A control service provisions isolated per-user or per-tenant execution/security environments. Tenant isolation becomes an additional boundary beyond the runtime/security split.

This is not an MVP requirement, but early schemas and IDs must not assume a globally single user.

## Components

### 1. Gateway

Responsibilities:

- authenticate clients;
- normalize inbound messages and events;
- expose chat/task/activity streams;
- route approval prompts from Sentinel directly to trusted clients;
- publish agent output and notifications;
- provide APIs for memory, goals, models, skills, connections, and settings.

The Gateway is not allowed to silently convert normal chat text into privileged approval grants.

Suggested first implementation: a small typed HTTP/WebSocket service. The language is less important than preserving contracts.

### 2. Conversation service

Conversations store human interaction, but they are not the sole state machine.

Data model should support:

- one primary long-lived conversation;
- side chats with isolated conversational context;
- messages arriving while executions are running;
- references from messages to goals/tasks/artifacts/approvals;
- asynchronous agent output;
- cancellation/interruption semantics.

### 3. Goal service

A goal is a durable desired outcome with:

- owner;
- title and description;
- success criteria;
- constraints;
- status;
- plan snapshot/version;
- related tasks;
- schedule/event subscriptions;
- notification policy;
- linked memories/artifacts/connections;
- lifecycle timestamps.

See `GOALS-TASKS.md`.

### 4. Scheduler / event router

Background work can originate from:

- explicit schedules;
- timers;
- recurring cron-like schedules;
- webhook/provider events;
- changes in external state;
- completion/failure of dependent tasks;
- agent-created future checks approved within a goal.

The scheduler creates task executions; it does not call models directly.

### 5. Agent orchestrator

The orchestrator turns durable work into model/runtime executions.

Responsibilities:

- load bounded task context;
- select a model profile by role/policy;
- start/resume/cancel executions;
- expose tools to the model through the runtime contract;
- manage subagent fan-out;
- persist execution checkpoints;
- enforce budget/time/step limits;
- emit structured events;
- recover from process restart.

The orchestrator may ask Sentinel for capabilities; it cannot issue grants itself.

### 6. Model router

OpenMuse owns an internal provider-neutral model contract. Adapters translate it to:

- OpenAI-compatible APIs;
- Anthropic-style APIs;
- Gemini-style APIs;
- local engines;
- LiteLLM or other gateways;
- future providers.

LiteLLM is a useful initial deployment option but is not a core architectural dependency.

See `MODEL-CONTRACT.md`.

### 7. Agent runtime cell

The runtime cell is the agent's computer and must be treated as untrusted.

It contains, at minimum:

```text
/workspace
/memory-view        # projected/authorized memory content
/skills
/artifacts
/tmp
```

It may execute:

- shell commands;
- generated scripts;
- installed user-space packages within policy;
- CLI tools;
- agent-created code;
- subagent workers;
- file transformations.

It must not contain:

- raw OAuth tokens;
- host SSH keys;
- cloud provider root credentials;
- Sentinel policy signing keys;
- auth-broker storage;
- unrestricted Docker/host sockets;
- direct browser CDP credentials;
- the database password for security-plane stores unless narrowly scoped and unavoidable.

#### MVP isolation

For v0.x, use rootless Podman/Docker or another namespace-capable Linux container profile with:

- separate user namespace;
- dropped capabilities;
- read-only base image;
- explicit writable mounts;
- seccomp profile;
- no host PID namespace;
- no host network;
- no Docker socket;
- controlled egress proxy;
- resource limits.

#### Hardened target

Later versions may use systemd-nspawn, microVMs, gVisor, Firecracker, Kata, or another backend. The `RuntimeDriver` contract must allow replacement.

### 8. Sentinel

Sentinel is the sole authority for sensitive actions and runtime network egress.

It receives typed requests such as:

```json
{
  "subject": "runtime:task-exec-123",
  "action": "gmail.send_message",
  "resource": "connection:gmail:primary",
  "destination": "alice@example.com",
  "purpose": "Send the draft explicitly requested by the user",
  "task_id": "task-42",
  "context_hash": "..."
}
```

It returns:

```text
ALLOW(grant_id, scope)
DENY(reason)
ASK_USER(approval_id, proposed_grants)
```

See `SENTINEL.md`.

### 9. Credential broker (`authd` concept)

Credentials are stored outside the runtime. The runtime receives stable references or surrogate tokens, never reusable secrets when avoidable.

Example:

```text
cred://gmail/primary
cred://github/personal
cred://browser/example.com/user-1
```

The broker validates the identity of the calling security-plane worker before releasing or using credential material.

For HTTP connectors, the preferred pattern is just-in-time credential insertion at a trusted network/connector boundary.

### 10. Connector workers

A connector is privileged integration code that can act on a service.

Built-in connectors should run outside the untrusted runtime when they require protected credentials. Runtime-facing CLIs are thin clients that submit typed requests to connector workers.

Example:

```text
runtime CLI
   -> typed Unix socket / RPC
      -> Sentinel authorization
         -> connector worker
            -> credential broker
               -> external service
```

A calendar worker must not be able to request a GitHub credential merely by changing a parameter.

### 11. Browser broker

The browser is privileged because it may hold authenticated sessions, passwords, payment state, and arbitrary untrusted content.

The runtime/browser agent should receive a constrained interface such as:

- navigate;
- snapshot accessibility tree;
- screenshot;
- click element;
- type non-secret text;
- scroll;
- wait;
- upload an explicitly authorized file;
- request secure credential fill;
- request checkout approval.

The main runtime should not receive unrestricted Chrome DevTools Protocol access by default.

When the user is manually entering a secret or taking control, agent browser actions must pause.

### 12. Memory service

Memory has two representations:

1. human-readable durable files or records the user can inspect/edit;
2. structured/indexed records containing provenance, confidence, timestamps, sensitivity labels, and retrieval metadata.

Vector search is an index, not the source of truth.

See `MEMORY.md`.

### 13. Artifact service

Artifacts are durable outputs that may be richer than chat messages:

- documents;
- reports;
- spreadsheets/data files;
- code projects;
- HTML dashboards;
- images;
- structured plans;
- exports.

Artifacts have ownership, provenance, content hash, MIME type, versions, and references to the task(s) that produced them.

### 14. Audit ledger

Every sensitive transition should emit an immutable-ish append-only audit event. At minimum:

- task started/resumed/stopped;
- model selected;
- tool invoked;
- connector requested;
- network request approved/blocked;
- approval requested/responded;
- credential reference used;
- memory added/changed/deleted;
- skill installed/changed;
- goal/schedule changed;
- artifact created;
- policy changed.

Audit records should distinguish model-proposed text from system-observed facts.

## Trust domains

### Trusted client domain

A client may collect passwords or approvals only through explicit secure UI paths. Chat content is untrusted input even when authored by the user because it is not a cryptographically scoped capability grant.

### Control plane

Trusted to coordinate work and store state, but should avoid direct access to plaintext credentials.

### Execution plane

Untrusted by design. Assume malicious instructions, malicious dependency, compromised generated code, or compromised model behavior.

### Security plane

Trusted computing base for authorization, secrets, egress, browser credential insertion, connector privilege separation, and audit policy.

The TCB should be kept small and difficult for the runtime to mutate.

## Data stores

### PostgreSQL

Initial source of truth for:

- users/tenants;
- conversations/messages metadata;
- goals/tasks/executions;
- schedules/events;
- model profiles;
- memory metadata/provenance;
- permissions/grants/approvals;
- connections metadata;
- skills metadata;
- audit events;
- artifact metadata.

The credential store should use a separately protected schema/database/service and keys unavailable to the runtime.

### Filesystem/object store

Used for:

- workspace files;
- human-readable memory files;
- artifacts;
- skill packages;
- execution logs too large for normal DB rows;
- export bundles.

### Queue/event bus

Do not introduce a distributed queue for the first milestone unless required. PostgreSQL-backed jobs/outbox semantics are sufficient for the single-user MVP. The event interface should allow NATS/Redis/Kafka/etc. later.

## Core internal contracts

OpenMuse should stabilize interfaces before optimizing implementation.

### `ModelAdapter`

```text
capabilities()
start(request) -> stream
cancel(execution)
```

### `RuntimeDriver`

```text
create(identity, policy)
start(runtime_id)
exec(runtime_id, command, limits)
mount(runtime_id, projection)
stop(runtime_id)
destroy(runtime_id)
health(runtime_id)
```

### `PolicyAuthority`

```text
evaluate(ActionRequest) -> Decision
respond(approval_id, UserDecision)
validate(grant_id, ActionRequest)
```

### `CredentialBroker`

```text
bind(connection, secret_material)
issue_surrogate(caller, credential, scope)
redeem_or_inject(trusted_caller, surrogate, destination)
revoke(connection)
```

### `Connector`

```text
manifest()
methods()
invoke(typed_request, grant_context)
```

### `BrowserBroker`

```text
create_session(task_context)
snapshot(session)
act(session, browser_action)
secure_fill(session, credential_reference)
close(session)
```

## Typical flow: read-only research

```text
1. Scheduler creates task execution.
2. Orchestrator loads goal + bounded memory + task state.
3. Model decides to research a public site.
4. Runtime requests browser navigation.
5. Browser broker/Sentinel permits low-risk public browsing.
6. Browser agent receives constrained page representation.
7. Findings return as untrusted observations.
8. Model produces structured result.
9. Result is persisted.
10. Notification policy decides whether to interrupt user.
```

## Typical flow: sensitive connector write

```text
1. Model proposes sending an email.
2. Runtime invokes thin gmail CLI with typed arguments.
3. Connector request reaches Sentinel.
4. Existing grants are checked exactly against action/scope/purpose.
5. If no suitable grant exists, Sentinel creates approval.
6. Trusted client shows deterministic approval UI.
7. User grants once/task/time/permanent scope or denies.
8. Sentinel records authoritative grant.
9. Privileged connector worker executes with credential broker.
10. Result and audit trail return to the task.
```

## Typical flow: generated skill

```text
1. Agent determines no suitable skill exists.
2. It creates code only in a build workspace.
3. Tests run in an isolated runtime without protected credentials.
4. Static policy checks inspect manifest and declared capabilities.
5. A skill artifact is created with content hash and provenance.
6. Installation policy decides whether user approval is required.
7. Installed skill gets no credentials automatically.
8. Any future privileged action still passes through Sentinel/connectors.
```

## Failure and recovery

Long-running work must tolerate crashes. Each execution should have explicit checkpoints and idempotency metadata.

After restart, the orchestrator must distinguish:

- safe to retry;
- already completed;
- awaiting approval;
- external side effect uncertain;
- cancelled;
- terminal failure.

Sensitive writes should use provider idempotency keys where available. If external state is uncertain after a crash, OpenMuse should verify before retrying rather than risk duplicate side effects.

## Observability

Observability has two audiences.

### User-visible

- what OpenMuse is doing now;
- what goal/task caused it;
- which external service is involved;
- what is waiting for approval;
- what changed;
- why the user was notified.

### Operator/developer

- execution traces;
- model latency/token/cost metrics;
- tool/runtime timings;
- policy decisions;
- sandbox resource use;
- connector failures;
- scheduler lag;
- prompt-injection classifier outcomes when present.

Sensitive values must be redacted before telemetry.

## Initial technology direction

This is a starting point, not a permanent commitment:

- **Control/harness:** Python or TypeScript; choose based on fastest path to a robust typed agent loop.
- **Security daemons:** Rust or Go are strong candidates for small privileged services.
- **Database:** PostgreSQL.
- **Runtime MVP:** rootless Podman/Docker on Linux.
- **Browser:** Chromium + Playwright behind `browserd`.
- **Model gateway:** native adapters plus optional LiteLLM/OpenAI-compatible endpoint.
- **IPC:** Unix domain sockets locally; authenticated RPC when components become remote.
- **Frontend:** React/Next.js or another conventional web client.

The project should resist premature microservices. Trust boundaries should create process boundaries; organizational fashion should not.

## Architecture decision rule

When evaluating a new component, ask in this order:

1. Does it change a trust boundary?
2. Does it grant new authority or credentials?
3. Does it create durable state?
4. Does it affect model-provider neutrality?
5. Does it need to survive restart?
6. Can it be replaced behind an existing contract?

Security-boundary decisions deserve ADRs and threat-model updates before implementation.
