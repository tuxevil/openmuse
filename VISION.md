# OpenMuse Vision

## Mission

OpenMuse exists to make a capable personal AI agent something a user can **own, inspect, move, modify, and run on infrastructure and models of their choice**.

The project is not trying to recreate Meta Muse pixel-for-pixel. It is trying to reproduce the deeper product idea that makes Muse compelling: a personal agent that has durable context, its own constrained computer environment, long-running goals, background work, tools, a browser, proactive behavior, and the ability to act across services — while moving the trust boundary away from the model itself.

The target experience is simple:

> Tell OpenMuse what outcome you want. It can keep working toward that outcome, even when you are not actively chatting with it, while you retain control over data, models, credentials, permissions, infrastructure, and irreversible actions.

## Product thesis

Most current assistants are still organized around a turn:

```text
prompt -> inference -> answer
```

A personal agent needs a different primitive:

```text
intent -> durable goal -> plan -> work -> observations -> state updates
                         -> approvals -> actions -> follow-up -> completion
```

Conversation remains important, but it is an interface to durable state rather than the sole place where state exists.

OpenMuse therefore treats the following as first-class objects:

- user identity and explicit preferences;
- conversations and side conversations;
- goals and success criteria;
- tasks and executions;
- schedules and event subscriptions;
- plans and plan revisions;
- artifacts;
- memories and their provenance;
- skills and connectors;
- permissions and capabilities;
- approvals;
- credentials references;
- agent/runtime instances;
- model profiles;
- activity and audit events.

## The user promise

OpenMuse should eventually be able to make the following promises in a way that can be verified technically rather than trusted conversationally.

### Your models

The user can choose a local model, a hosted commercial model, several models routed by role, or an OpenAI-compatible gateway. Replacing a model must not require changing the control plane, memory format, task database, connector implementation, or security system.

### Your computer

OpenMuse can run on a personal workstation, a home server, a cloud VM, or a managed deployment. The logical runtime and security boundaries should remain consistent across deployment modes.

### Your data

Durable personal state should be inspectable and exportable. Human-readable memory should be preferred where practical, with structured database records used for indexing, provenance, concurrency, and policy.

### Your rules

The model does not get final authority over sensitive actions. Permissions, secrets, network access, and protected connectors are enforced by services outside the agent runtime.

## Who OpenMuse is for

The earliest users are expected to be technical users who are comfortable self-hosting and who want a persistent personal agent without surrendering model choice or infrastructure choice. The architecture should, however, avoid assuming that all future users are developers.

A successful project should be able to evolve from:

```text
power user installs OpenMuse on one machine
```

into:

```text
ordinary user chooses a trusted hosted OpenMuse provider
```

without changing the core contracts that define identity, memory, permissions, goals, and runtime behavior.

## Example experiences

OpenMuse should eventually support tasks such as:

- "Watch several marketplaces for this GPU and tell me when total landed cost is below my threshold."
- "Keep track of everything that is blocking my active projects and ask me only when you need a decision."
- "Read my calendar and mail for scheduling conflicts, but never send a message without approval."
- "Figure out how to query my solar inverter. If no integration exists, build a skill, test it in the sandbox, and ask me before installing it."
- "Organize a trip, keep monitoring prices and availability, and prepare bookings for approval."
- "Maintain this home server, install routine security updates automatically, but request approval for restarts or destructive changes."
- "Research this question over several days and update the report only when new evidence materially changes the conclusion."

These examples require persistence, scheduling, tools, browser use, memory, model reasoning, and security policy working together.

## Principles

### 1. Agent behavior is not a security boundary

System prompts are useful behavioral instructions, not authorization mechanisms. Any rule that protects credentials, money, data disclosure, destructive operations, identity, or external side effects must ultimately be enforceable outside the main model.

### 2. The runtime may be compromised

The architecture assumes the model can be manipulated by prompt injection and that generated code, downloaded content, third-party tools, or dependencies can be malicious. The goal is to bound consequences, not to pretend compromise is impossible.

### 3. Local-first does not mean single-process

Self-hosting must not collapse the security architecture into one process running as the user. Even a single-user local deployment should preserve separation between untrusted agent execution and privileged security services.

### 4. Model agnosticism is a contract problem

Supporting many model names is insufficient. OpenMuse must define its own stable request, response, tool, event, streaming, cancellation, and capability contracts so a provider adapter can map different APIs into them.

### 5. Persistent state is explicit

The agent should not depend on an ever-growing hidden chat transcript. Goals, task state, memory, plans, schedules, approvals, and artifacts must have explicit durable representations.

### 6. Proactivity must earn interruptions

Background activity is useful only if the agent does not become noisy. Proactive results should pass a relevance/novelty/urgency policy before becoming notifications.

### 7. Skills are code; connectors are authority

A skill can teach the model how to accomplish something. A connector may hold authority to access an external service. These must not be treated as the same trust object.

### 8. Generated capabilities require lifecycle controls

The agent may generate scripts or skills, but generated code should be attributable, reviewable, testable, versioned, and installable only into allowed locations. It must never gain the ability to mutate the security plane merely because it can edit its workspace.

### 9. Human control should be deterministic where consent matters

Approvals must be represented as structured capability grants with clear scope. "The user sounded okay with it in chat" is not an approval record.

### 10. Portability is a feature, not an export afterthought

OpenMuse should have a documented export format for memory, goals, artifacts, skill configuration, model configuration, and audit history. Credentials should be re-bindable rather than exported casually in plaintext.

## Non-goals

OpenMuse does not initially aim to:

- train a foundation model;
- compete on raw benchmark performance with model vendors;
- support billions of users in the first architecture;
- implement confidential-computing guarantees in the MVP;
- automate financial, legal, medical, or other high-impact decisions without explicit policy and user control;
- make every third-party integration available on day one;
- guarantee complete resistance to prompt injection;
- allow arbitrary runtime code to inherit host credentials;
- use autonomous self-modification of core/security code as a product feature.

## Product surfaces

The long-term product can expose several surfaces over the same control plane:

- **Chat** — the primary conversational relationship with the agent.
- **Goals** — durable desired outcomes, plans, progress, blockers, and success criteria.
- **Ideas** — agent-generated suggestions that have not yet become goals/actions.
- **Activity** — live and historical execution visibility.
- **Computer** — runtime health, browser activity, files, and sandbox state.
- **Artifacts** — documents, reports, code, dashboards, exports, and generated outputs.
- **Memory** — inspectable long-term facts/preferences with provenance and controls.
- **Connections** — services and accounts bound to credential references.
- **Skills** — installed, generated, enabled, and disabled capabilities.
- **Models** — model profiles and role routing.
- **Permissions** — capability policies, pending approvals, and grants.

These are views over durable state. None should require the chat transcript to reconstruct their meaning.

## Differentiation

OpenMuse should not position itself merely as another multi-provider chat assistant. Its differentiation should come from the combination of:

- personal-agent product semantics;
- persistent computer/runtime;
- strong trust-domain separation by default;
- model-provider neutrality;
- self-hostability and portability;
- explicit long-running goals and background work;
- inspectable memory and audit history;
- open skills/connectors ecosystem;
- agent-extensible workspace with a protected security plane.

## Relationship to Meta Muse

Meta Muse is a primary inspiration because Meta has publicly documented unusually concrete architectural details about its personal-agent security model, persistent VM, Sentinel authorization, protected credentials, background work, goals, memory, browser isolation, and generated tools.

OpenMuse will study those public concepts but implement its own code and interfaces. It is not affiliated with Meta, does not depend on private Meta services, and should avoid presenting inferred details as facts about Meta's implementation.

`OpenMuse` is a working project name. Before a broad public launch, the project should review naming and trademark risk and be prepared to rename without changing package/API identity assumptions.

## Definition of success for v1

A v1 should make a technically credible claim that a user can run a persistent personal agent that:

1. uses at least two interchangeable model providers;
2. has a durable workspace and inspectable memory;
3. accepts long-running goals and scheduled/event-driven tasks;
4. survives service restarts without losing task state;
5. uses a real browser through a constrained broker;
6. uses at least three useful connectors;
7. can generate and install a user-approved skill;
8. cannot directly read protected connector credentials;
9. cannot perform sensitive connector actions without an appropriate capability grant;
10. cannot bypass configured network egress policy from the runtime;
11. records a coherent activity/audit trail;
12. can be exported and restored to another OpenMuse installation.

That is the product OpenMuse is trying to build.
