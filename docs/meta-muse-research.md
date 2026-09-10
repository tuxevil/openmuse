# Research Notes: Meta Muse Personal Agent

**Research date:** 2026-09-10  
**Scope:** Meta's personal AI agent named **Muse**, not the Muse model family or media-generation products.

## Purpose

This document records publicly available information that informed OpenMuse. It intentionally separates:

- **META-DOCUMENTED** — directly stated in a public Meta source;
- **EXTERNAL REPORTING** — reported by a third-party publication;
- **OPENMUSE INTERPRETATION** — our architectural conclusion or design choice.

This is a research record, not a claim that OpenMuse reproduces Meta's private source code or exact internal implementation.

## Primary public sources

### P1 — Meta product page

https://ai.meta.com/muse/

Public product description covering Secure VM, browser, approvals, credential store, goals, ideas/background work, connectors, generated tools, and FAQs.

### P2 — Meta Newsroom launch announcement

https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/

Published September 8, 2026. Covers product behavior, long-running goals, background work, Secure VM, Sentinel, credentials, user permissions, purchasing, memory, and upcoming Confidential VM.

### P3 — Meta AI Research security architecture

https://research.meta.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse

Title: *How We Built Safety Into Muse*. Published September 8, 2026. This is the most technically important public source. It describes the VM/runtime trust split, Hatch, systemd-nspawn, authd, privsep, Sentinel, network egress, credential surrogation, tainted egress, browser brokerage, prompt-injection defenses, Postgres durable state, and related details.

### P4 — Meta product design essay

https://introducing.muse.ai/

Title: *How We Designed Muse*. September 2026. Covers the product semantics of long-running work, filesystem/terminal, browser, background/event-driven execution, main chat and side chats, proactivity, activity log, Goals, deterministic approvals, editable memory, Artifacts, and Ideas.

## Useful external reporting

These are secondary sources and should not override Meta's own technical descriptions.

### E1 — Reuters, September 8, 2026

https://www.reuters.com/business/meta-launches-ai-agent-that-can-access-other-apps-send-emails-make-payments-2026-09-08/

Reports launch context, app/service access, security concerns and pre-launch testing history.

### E2 — The Verge, September 2026

Public reporting on Muse's launch and positioning, including comparisons to open personal-agent projects and discussion of the Secure VM/Sentinel approach.

### E3 — WIRED, September 2026

Public reporting focused on trust/privacy/security around Muse, including Secure VM, Sentinel and planned confidential-computing direction.

Third-party reporting may contain details not independently verified here. OpenMuse architecture should prefer P1–P4 for factual claims about Meta's implementation.

---

# Product behavior

## Personal agent rather than turn-by-turn chatbot

**META-DOCUMENTED (P2/P4):** Muse can take tasks and projects, create action plans for long-term goals, continue after the application is closed, and return when something changes or user input/approval is required.

P4 explicitly says Muse is not designed as a strictly turn-by-turn experience. Users can interrupt it or send multiple tasks without waiting for the previous response.

**OPENMUSE INTERPRETATION:** Conversation should not be the system state. Goals, tasks, schedules, plans, approvals, artifacts, and execution checkpoints need independent durable objects.

## Long-running goals

**META-DOCUMENTED (P2/P4):** After receiving a goal, Muse can develop a personalized plan, coordinate time/resources, advance work on its own, and expose goal progress through a Goals view.

**OPENMUSE INTERPRETATION:** `Goal`, `Task`, `Execution`, and versioned `Plan` should be first-class domain objects. See `GOALS-TASKS.md`.

## Background and event-driven work

**META-DOCUMENTED (P4):** Once a goal/task exists, Muse can continue working on a schedule and in response to relevant events. After background work completes, it evaluates whether the result is worth surfacing and only notifies when something meaningfully new exists or input is needed.

**OPENMUSE INTERPRETATION:** OpenMuse needs both a scheduler and an event router. Notifications should have a novelty/urgency decision instead of treating every completed background execution as a message.

## Proactivity

**META-DOCUMENTED (P4):** Muse can send messages without being prompted. Meta describes intentionally setting a high bar for proactive interruptions and allowing users to tune proactivity.

**OPENMUSE INTERPRETATION:** Proactivity should be a policy/evaluation layer with outcomes such as notify-now, digest, silent update, discard.

## Main chat and side chats

**META-DOCUMENTED (P4):** Product design centers on one long-running main conversation, while side chats were added for topics/projects where users wanted separate context.

**OPENMUSE INTERPRETATION:** Conversation scopes should be explicit and can reference the same underlying durable goals/memory without requiring one infinite transcript.

## Ideas

**META-DOCUMENTED (P4):** Early testers sometimes did not know what to ask because the system could do many things. Muse therefore generates Ideas based on goals, patterns, learned information, and conversation.

**OPENMUSE INTERPRETATION:** `Idea` should be a proposal object with zero authority. An idea becomes an active goal/task only through explicit policy/user acceptance.

## Artifacts

**META-DOCUMENTED (P4):** Muse can create rich outputs such as documents, PDFs, webpages, trackers and dashboards. Meta calls these Artifacts and treats them as outputs that can exist beyond a chat text response.

**OPENMUSE INTERPRETATION:** Artifacts deserve durable IDs, versions, MIME types, provenance, task links, and independent storage.

---

# The agent's computer

## Dedicated persistent cloud computer

**META-DOCUMENTED (P1/P2/P3):** Each Muse/user has a dedicated cloud VM. Meta describes it as an isolated Linux box with browser, storage, CPU and memory sufficient for real work.

P3 says this environment can compile code written by the agent, develop custom skills, run concurrent subagents, and run crons.

**OPENMUSE INTERPRETATION:** A serious personal agent needs a persistent execution environment, not merely stateless remote function calls. OpenMuse will make the deployment location replaceable: local machine, home server, VM, or hosted provider.

## Filesystem and terminal

**META-DOCUMENTED (P4):** Muse has its own computer with filesystem and terminal, which it can use to write code and build tools needed by a task.

**OPENMUSE INTERPRETATION:** OpenMuse runtime should expose a real constrained filesystem and shell, but that runtime is explicitly untrusted.

## Builds its own tools/connectors

**META-DOCUMENTED (P1/P3/P4):** Meta states that if a task requires a tool that does not exist, Muse can build one. P3 says Muse can write custom connectors for services that expose APIs or CLIs.

**OPENMUSE INTERPRETATION:** Self-extension is a core feature, but generated code must be staged/tested/versioned and must not inherit secrets or the ability to modify the security plane. See `SKILLS-CONNECTORS.md`.

## Subagents

**META-DOCUMENTED (P3):** Meta describes Muse as launching "swarms of subagents" and says the VM is sized for concurrent subagents.

**OPENMUSE INTERPRETATION:** Subagents are bounded child tasks with explicit fan-out/depth/budget. They do not get independent ambient authority.

---

# Secure VM architecture

## Two security domains, not an agent with root

**META-DOCUMENTED (P3):** Meta explicitly says the right mental model is two isolated security domains on one box, not an LLM agent with root.

**OPENMUSE INTERPRETATION:** This is one of the strongest ideas to preserve. OpenMuse defines an untrusted execution plane and a separate trusted security plane.

## Hatch

**META-DOCUMENTED (P3):** `Hatch` is Meta's internal name for Muse in the codebase. P3 describes the Hatch daemon as the core agentic harness.

Do not confuse this with a public OpenMuse component name; OpenMuse should use its own terminology.

## systemd-nspawn runtime cell

**META-DOCUMENTED (P3):** Hatch, workspace/files, binaries and tools run in a `systemd-nspawn` runtime container. Root in the runtime cell is mapped to an unprivileged host user.

P3 additionally states that the cell has:

- its own root filesystem with a full Debian image;
- a virtual network interface;
- filtered syscalls (Meta gives `io_uring` as an example);
- limited kernel capabilities (examples include no `CAP_SYS_PTRACE` and no `CAP_NET_ADMIN`).

**OPENMUSE INTERPRETATION:** OpenMuse can begin with a rootless container driver but should define `RuntimeDriver` so stronger backends can replace it. The security property matters more than copying `systemd-nspawn` immediately.

## Sensitive services outside the runtime cell

**META-DOCUMENTED (P3):** Meta lists security-sensitive host-side services including:

- `hatch-safety` — independent safety models/classifiers around model inference;
- `privsep` connector workers;
- `hatch-authd` credential storage/surrogation;
- Sentinel — connector and network permission authority;
- Postgres durable application state outside the runtime cell;
- constrained inference/telemetry proxies.

**OPENMUSE INTERPRETATION:** Preserve the security-domain split, but do not blindly reproduce every daemon boundary in the MVP. Components that hold credentials or enforce authority should be outside the runtime.

## IPC

**META-DOCUMENTED (P3):** Communication between runtime and other services uses Unix domain sockets with `SO_PEERCRED` and peer ACLs.

**OPENMUSE INTERPRETATION:** Local IPC should use kernel-authenticated peer identity where possible. A generic unauthenticated localhost HTTP port is a weaker default for privileged service calls.

---

# Sentinel

## Independent permission authority

**META-DOCUMENTED (P2/P3):** Sentinel is separate from the main Muse agent and is the sole permission authority for connector actions and runtime network egress. Muse proposes an action; Sentinel can allow, deny, or ask the user.

**OPENMUSE INTERPRETATION:** This becomes a foundational invariant. OpenMuse's main model must never possess a `grant_permission` primitive that bypasses Sentinel.

## Human approval

**META-DOCUMENTED (P3/P4):** When user approval is required, execution stops and a pending approval is presented through deterministic UI. P3 states that the approval path is direct between Sentinel and the client rather than mediated by the conversation.

P3 describes one-time, session-scoped, task-scoped, time-bounded and perpetual permission options.

**OPENMUSE INTERPRETATION:** Approval is a structured capability grant. A natural-language "yes" in chat is not authoritative permission.

## Connector authorization

**META-DOCUMENTED (P3):** Connector requests describe connector/method/action/scope/context. Sentinel evaluates policy set by the user.

**OPENMUSE INTERPRETATION:** Build typed action schemas and a versioned risk registry. Grants must match the concrete action executed.

---

# Network egress

## Every concrete request governed at egress

**META-DOCUMENTED (P3):** Runtime traffic reaches Sentinel through a forward proxy using Linux networking controls. Meta says Sentinel can inspect/evaluate:

- hostname;
- resolved/final destination IP;
- port;
- protocol;
- HTTP method;
- path;
- decoded request.

P3 also describes SSRF restrictions that prevent apparently public hostnames from resolving to private infrastructure.

**OPENMUSE INTERPRETATION:** Runtime must have no alternate direct network route. Initial OpenMuse can implement mandatory proxy + network namespace/firewall before advanced eBPF work.

## Tainted egress

**META-DOCUMENTED (P3):** Meta describes kernel-level data-flow tracking called "tainted egress." Tool execution starts clean and becomes tainted after reading user data. Tainted/unverifiable processes lose narrow auto-allow behavior and return to normal approval flow.

P3 says implementation uses:

- eBPF cgroup programs for network interception/process attribution;
- eBPF programs on Linux Security Module hooks for taint propagation.

**OPENMUSE INTERPRETATION:** This is an advanced hardening target, not a v0 dependency. OpenMuse should first propagate coarse data-sensitivity labels at task/process level so later kernel attribution has a compatible policy concept.

---

# Credentials and privileged connectors

## Main agent does not see real credentials

**META-DOCUMENTED (P1/P2/P3):** Muse does not have visibility into user passwords/payment methods. Credentials are kept in secure storage. P3 says `hatch-authd` handles OAuth credentials and credential surrogation.

## Just-in-time credential insertion

**META-DOCUMENTED (P3):** Runtime code/worker can use a surrogate token. After Sentinel authorizes the concrete network request, the surrogate is replaced with the real credential obtained from authd at the network boundary.

Meta's explicit security argument is that a prompt injection cannot coerce the agent to reveal a real token that the agent never possesses.

**OPENMUSE INTERPRETATION:** Implement opaque credential references/surrogates and privileged redemption/insertion. Never make `.env` secrets inside the agent runtime the normal architecture.

## Privsep connector workers

**META-DOCUMENTED (P3):** Built-in credential-capable connector business logic runs outside the runtime cell. Runtime CLIs parse arguments/open already-authorized files and pass typed data/file descriptors over a Unix socket. Workers are identified by cgroup and get explicit credential allowlists.

Meta gives the example that a calendar worker cannot obtain an email credential merely by changing a parameter.

**OPENMUSE INTERPRETATION:** Built-in credentialed connectors should use thin runtime facades and privileged workers. Generated skills cannot simply edit a credential-bearing CLI.

## Email authentication material filtering

**META-DOCUMENTED (P3):** Muse's email connector filters one-time codes, password reset links and login magic links using deterministic filters and a classifier.

**OPENMUSE INTERPRETATION:** Email is not just "read access"; it often contains authority over other accounts. OpenMuse email connectors should protect authentication/recovery material by default.

---

# Browser

## Real Chromium-based browser

**META-DOCUMENTED (P1/P3/P4):** Muse has a browser capable of search/navigation/forms/transactions. P3 calls it an up-to-date Chromium-based browser behind a virtualization layer.

## Specialized browser subagent

**META-DOCUMENTED (P3):** Muse uses a special browser subagent for each browser task.

**OPENMUSE INTERPRETATION:** Browser reasoning can be routed to a specialized model/role without making that model part of the browser security boundary.

## Brokered CDP and accessibility tree

**META-DOCUMENTED (P3):** The browser is managed by a separate broker that owns the Chrome DevTools Protocol connection. The browser subagent sees an accessibility-tree snapshot rather than raw DOM. Meta says it cannot run JavaScript in page context, has no script verbs or exec in the browser process, and Chrome devtools are disabled.

**OPENMUSE INTERPRETATION:** OpenMuse `browserd` should expose narrow actions and avoid giving unrestricted CDP to the main runtime.

## User takeover / credential fill pauses agent

**META-DOCUMENTED (P3):** When the user takes control or protected credential storage is filling a form, the agent is paused.

**OPENMUSE INTERPRETATION:** Secure browser takeover/fill should be explicit task state, not a race between automation and the human.

## Browser classifiers

**META-DOCUMENTED (P3):** Meta describes additional classifiers for personal-data egress, prompt injection in DOM/media/downloads, and high-risk forms.

**OPENMUSE INTERPRETATION:** These are useful defense-in-depth layers but do not replace broker restrictions/Sentinel.

---

# Purchases

## Approval at checkout

**META-DOCUMENTED (P2/P3):** Muse asks for human approval for purchase actions. P3 says checkout using stored payment state is detected and approved with exact purchase details.

## Payment-token minimization

**META-DOCUMENTED (P2/P3):** At launch, Meta partnered with Stripe Link and describes a single-use card mechanism rather than exposing the user's regular card number to the agent/merchant path. P3 says payment credential is bounded by merchant, amount and time.

**OPENMUSE INTERPRETATION:** OpenMuse should treat payment as a later high-risk connector/browser capability. The generalizable idea is transaction-bound credential minimization, not a dependency on Stripe.

---

# Memory and user data

## Memory is inspectable/editable

**META-DOCUMENTED (P3/P4):** Meta states that users can inspect/edit/download files including Muse's memory. P4 explicitly describes Memory files that users can read and edit directly.

**OPENMUSE INTERPRETATION:** Human-readable memory should remain a first-class representation. Vector stores are indexes, not the only source of truth.

## VM as system of record

**META-DOCUMENTED (P3):** Meta says the dedicated VM is the system of record for what the user puts in Muse, with limited data sent out for inference/telemetry as described in its policy.

**OPENMUSE INTERPRETATION:** OpenMuse should make deployment/data placement explicit and portable. A local installation can keep control-plane state local while model-routing policy determines what context may go to external providers.

## Training/ads/privacy claims

**META-DOCUMENTED (P2/P3):** Meta says Muse VM/conversation data is not shared with Meta ad systems; interactions may still indirectly influence advertising via ordinary activity on external/Meta services. Meta describes training use of sanitized trajectories by default with an opt-out.

These are Meta service policies, not OpenMuse architecture requirements.

---

# Safety around model inference

## Model training is one layer, not the boundary

**META-DOCUMENTED (P3):** Meta says Muse Spark was trained for zero-shot tool calling with CLIs/skills, long context, long-trajectory instruction following with prompt-injection awareness, and multi-agent coordination.

Meta nevertheless explicitly assumes the model can make mistakes or be attacked and places deterministic boundaries beneath it.

**OPENMUSE INTERPRETATION:** OpenMuse must not require Muse Spark or any specially trained model to preserve its core security properties. Better models improve success rate; they do not create permission authority.

## Independent safety classifiers

**META-DOCUMENTED (P3):** `hatch-safety` and other classifier ensembles run outside the runtime cell so attackers cannot disable them from inside the agent environment.

**OPENMUSE INTERPRETATION:** If OpenMuse adds prompt-injection/safety classifiers, they belong outside the runtime and act as defense-in-depth signals. Sentinel remains deterministic permission authority.

---

# Postgres and durable state

**META-DOCUMENTED (P3):** Meta says durable application state is stored in a Postgres database separate from the runtime cell and credential store.

**OPENMUSE INTERPRETATION:** PostgreSQL is a strong default for OpenMuse control-plane state. It can also support outbox jobs, full-text search and optional pgvector, reducing infrastructure complexity in early versions.

---

# Self-modification

**META-DOCUMENTED (P3):** The security article says Muse builds its own tools and "edits itself."

The public material does not, in the sources reviewed here, establish that the untrusted agent can rewrite Sentinel/authd/security-plane services.

**OPENMUSE INTERPRETATION:** OpenMuse will intentionally narrow self-modification:

Allowed by design:

```text
workspace
scripts
generated skills
artifacts
user-space task code
memory proposals/files under memory policy
```

Not agent-writable:

```text
Sentinel
authd
security policy engine
trusted connector workers
runtime supervisor
trusted browser broker
release/update trust roots
```

This yields the principle:

> mutable agent plane, protected security plane.

---

# Confidential VM

**META-DOCUMENTED (P2/P3):** Meta announced a future Muse Confidential VM intended to cryptographically prevent Meta from accessing VM data, with a user-held key and external auditing.

At the September 8 launch, this was described as upcoming rather than the default launch architecture.

**OPENMUSE INTERPRETATION:** OpenMuse does not need confidential computing to establish its first local/self-hosted security boundary. A future hosted deployment can explore SEV-SNP/TDX/confidential-VM designs, but should not claim protection from the host operator until it is verifiable.

---

# What OpenMuse should copy conceptually

These are OpenMuse decisions inspired by the public design, not claims of source compatibility:

1. persistent computer/runtime per user/instance;
2. durable goals/tasks/background work;
3. independent security authority;
4. raw credentials outside agent runtime;
5. controlled network egress;
6. privileged connector workers;
7. constrained browser broker;
8. inspectable/editable memory;
9. explicit activity/audit visibility;
10. generated tools/skills with lifecycle controls;
11. deterministic approvals for consequential actions;
12. high bar for proactive interruption.

# What OpenMuse deliberately changes

1. **Provider neutrality:** no dependency on Muse Spark or Meta inference.
2. **Infrastructure neutrality:** local-first plus arbitrary cloud/hosted deployments.
3. **Open implementation:** public contracts and code.
4. **Portable state:** documented export/restore is a product requirement.
5. **Replaceable runtime:** security properties defined independently of one container technology.
6. **Explicit separation of skills vs authority:** generated skills never imply credentials/grants.
7. **No core self-edit authority:** agent cannot modify its security plane.
8. **Routing by role:** different models may handle orchestration, browser, coding, memory, and notification.

# Unknowns / do not assume

The reviewed public sources do **not** provide enough detail to treat the following as established facts:

- exact internal database schema;
- exact system prompt beyond the line quoted publicly in P4;
- exact planner/state-machine implementation;
- exact subagent orchestration protocol;
- exact memory extraction/consolidation algorithm;
- exact embedding/vector architecture;
- exact model-router logic;
- all connector protocol schemas;
- all details of Meta's deployment/provisioning infrastructure;
- production implementation details of the announced Confidential VM beyond public descriptions.

When OpenMuse makes a choice in these areas, label it an OpenMuse design decision rather than "how Muse works."

# Research conclusion

The strongest reusable insight from Meta Muse is not a particular model or UI. It is the combination of:

```text
persistent agent computer
+ durable goals/background work
+ model capable of tools/subagents
+ inspectable personal state
+ security enforcement outside the model
+ credentials outside the runtime
+ controlled browser/network/connector authority
```

OpenMuse should preserve those system properties while making the model, infrastructure, data location, and extension ecosystem open and replaceable.
