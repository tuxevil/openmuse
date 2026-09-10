# OpenMuse Threat Model

## Purpose

This threat model captures the initial security assumptions for OpenMuse and must evolve with the implementation. It is deliberately focused on the personal-agent architecture rather than generic web-application risks alone.

OpenMuse combines capabilities that create the classic high-risk agent pattern:

1. access to private user data;
2. exposure to untrusted content;
3. ability to communicate or act externally.

The project must therefore assume that prompt injection, model mistakes, malicious tool output, compromised dependencies, and hostile websites will occur.

## Assets to protect

### A1. Credentials

- OAuth access/refresh tokens;
- API keys;
- passwords;
- browser session cookies;
- SSH keys;
- payment credentials;
- recovery codes;
- one-time codes and magic links.

### A2. Private user data

- email;
- calendar;
- files;
- contacts;
- conversation history;
- memory;
- browsing state;
- home/IoT information;
- project/business data;
- location and travel information;
- personal artifacts.

### A3. Authority

- ability to send messages;
- ability to publish;
- ability to spend money;
- ability to delete/change remote data;
- ability to alter accounts/security settings;
- ability to control devices/services;
- ability to install software or modify systems.

### A4. Integrity

- memory correctness/provenance;
- goal/task state;
- permission/grant records;
- audit history;
- connector behavior;
- security configuration;
- artifacts.

### A5. Availability

- runtime;
- task scheduler;
- database;
- browser;
- connected services;
- local compute budget;
- token/cost budget.

## Trust boundaries

```text
[USER CLIENT]
     |
     | authenticated API + trusted approval path
     v
[CONTROL PLANE] ------------------> [MODEL PROVIDERS]
     |
     | task/context contract
     v
[UNTRUSTED RUNTIME]
     |
     | typed requests / proxy traffic
     v
[SECURITY PLANE: SENTINEL / AUTHD / CONNECTORS / BROWSERD]
     |
     | authorized concrete requests
     v
[EXTERNAL SERVICES / WEB]
```

Important: data crossing from external systems into the runtime is untrusted even when it comes from an authenticated account. An email in the user's inbox can contain malicious instructions.

## Threat actors

### T1. Malicious webpage/content author

Attempts to steer the agent through visible/hidden instructions, downloaded files, images, forms, or metadata.

### T2. Malicious sender/contact

Sends email/messages/calendar invites/documents designed to make the agent reveal data or take actions.

### T3. Compromised model behavior

The model may follow an attacker's instruction, hallucinate authority, misunderstand the user, or produce dangerous commands without malicious intent.

### T4. Malicious or compromised skill/package

Third-party or generated code attempts to access secrets, escape sandbox, exfiltrate data, or persist malicious behavior.

### T5. Compromised connector/service

External API returns malicious data or a connector implementation has a vulnerability.

### T6. Local attacker with non-root access

On a self-hosted machine, another local principal may try to read sockets/files or impersonate services.

### T7. Host administrator/root compromise

A host root attacker can generally defeat local process/container isolation. This is outside the protection claim of a normal local deployment and must be documented.

### T8. Malicious hosted operator

Relevant to future hosted OpenMuse. Without confidential-computing guarantees, an operator with sufficient infrastructure authority may access data. Hosted privacy claims must match actual deployment.

### T9. Supply-chain attacker

Compromises OpenMuse dependencies, container images, releases, package sources, or update infrastructure.

### T10. User mistake

The user may over-grant permissions, approve something without reading it, or accidentally provide credentials in normal chat.

## Threats and mitigations

### TM-01: Prompt injection causes data exfiltration

**Scenario:** A website tells the agent to read private memory/email and POST it to an attacker-controlled endpoint.

**Impact:** Confidentiality breach.

**Required mitigations:**

- runtime lacks raw reusable credentials;
- external content labeled untrusted;
- outbound traffic forced through Sentinel;
- private-data egress requires appropriate capability;
- destination/resource scope enforced;
- optional prompt-injection classifiers;
- data-aware egress/taint in later hardening.

**Acceptance test:** A red-team fixture containing explicit exfiltration instructions cannot transmit a protected fixture secret to an unapproved server.

### TM-02: Prompt injection causes privileged connector write

**Scenario:** Malicious email tells OpenMuse to forward other messages or send a payment instruction.

**Impact:** Identity misuse, disclosure, financial harm.

**Mitigations:**

- connector write requires typed action;
- Sentinel is sole authority;
- no conversational grant;
- user approval for configured sensitive classes;
- precise grant matching;
- email connector filters authentication/recovery material.

### TM-03: Agent steals its own credentials

**Scenario:** Model runs `env`, reads config files, dumps process memory, or asks connector CLI for tokens.

**Impact:** Credential theft.

**Mitigations:**

- no raw credentials in runtime env/files;
- auth broker outside runtime;
- credential references/surrogates;
- connector workers authenticated and credential-allowlisted;
- no ptrace/cross-domain process access;
- logs redact secrets.

### TM-04: Skill modifies connector code to widen access

**Scenario:** A generated skill edits a Gmail tool to send data elsewhere using existing credentials.

**Impact:** Privilege escalation/exfiltration.

**Mitigations:**

- credential-capable connector implementation outside runtime;
- runtime CLI is non-secret thin client;
- security-plane code read-only/unmounted;
- generated skills have manifests and no implicit credentials;
- Sentinel validates concrete action.

### TM-05: Runtime escapes container

**Scenario:** Generated code exploits kernel/container vulnerability.

**Impact:** Full host compromise, security-plane compromise.

**Mitigations:**

- rootless/user namespaces;
- minimal capabilities;
- seccomp;
- no privileged containers;
- patched host/runtime;
- no host Docker socket;
- consider microVM backend for higher-assurance deployments;
- resource limits.

**Residual risk:** Kernel/container vulnerabilities remain possible.

### TM-06: Direct network bypass

**Scenario:** Agent ignores proxy and opens raw TCP/UDP socket or tunnel.

**Impact:** Bypass policy/exfiltration.

**Mitigations:**

- isolated network namespace;
- firewall only permits proxy/broker path;
- no `CAP_NET_ADMIN`/raw-socket capabilities;
- DNS path controlled;
- tests verify no direct egress.

### TM-07: DNS rebinding / SSRF

**Scenario:** Public hostname resolves to localhost/private metadata target.

**Impact:** Access to trusted services/credentials.

**Mitigations:**

- validate final resolved IP;
- block private/link-local/loopback by default;
- revalidate redirects;
- explicit internal-destination policy;
- protect cloud metadata endpoints.

### TM-08: Browser steals password

**Scenario:** Agent inspects DOM/accessibility tree after secure password fill.

**Impact:** Credential disclosure.

**Mitigations:**

- credential entry routed directly to trusted storage;
- secure fill via broker;
- agent paused during fill/user takeover;
- page representation excludes protected fields;
- no unrestricted CDP/script execution.

### TM-09: Browser performs unintended purchase

**Scenario:** Agent reaches checkout because of misunderstanding or malicious page.

**Impact:** Financial harm.

**Mitigations:**

- checkout detection;
- purchase-specific approval every time by default;
- exact merchant/amount/item summary;
- constrained payment token if supported;
- transaction audit.

### TM-10: Approval confusion / UI spoofing

**Scenario:** Agent chat says "click approve" or renders content resembling approval UI.

**Impact:** User grants unintended action.

**Mitigations:**

- approvals rendered only by trusted client component;
- visually/systemically distinct from chat/artifacts/web content;
- exact action/destination/amount displayed;
- direct client-to-Sentinel response path;
- chat text cannot satisfy approval API.

### TM-11: Overbroad persistent permission

**Scenario:** User grants "always" to something broader than intended.

**Impact:** Long-term authority abuse.

**Mitigations:**

- narrow grant templates;
- clear scope UI;
- expiration defaults for risky actions;
- permission dashboard and revocation;
- periodic review of high-risk persistent grants;
- grant usage audit.

### TM-12: Memory poisoning

**Scenario:** Untrusted content becomes durable memory: "user always wants purchases auto-approved."

**Impact:** Future behavior corruption.

**Mitigations:**

- provenance on memory;
- distinguish direct user statements from inferred/external claims;
- forbid memory from creating authorization grants;
- sensitivity/authority labels;
- conflict handling;
- user inspect/edit/delete.

### TM-13: Task state injection

**Scenario:** Tool output is interpreted as a system task transition or success signal.

**Impact:** Incorrect actions/state.

**Mitigations:**

- typed tool responses;
- orchestrator owns task transitions;
- content cannot write control records directly;
- schema validation.

### TM-14: Duplicate side effect after crash

**Scenario:** Process crashes after external write but before local success checkpoint; retry sends twice.

**Impact:** Duplicate messages/orders/events.

**Mitigations:**

- idempotency keys where available;
- write-ahead execution record;
- uncertain-state status;
- verify external state before retry;
- never blindly retry high-impact non-idempotent operations.

### TM-15: Infinite loop / resource exhaustion

**Scenario:** Agent recursively spawns subagents or repeatedly retries a task.

**Impact:** Cost/availability denial.

**Mitigations:**

- execution budgets;
- max fan-out/depth;
- wall-clock limits;
- token/cost quotas;
- retry limits/backoff;
- circuit breakers;
- user-visible runaway detection.

### TM-16: Model-provider data leak

**Scenario:** Sensitive context is sent to a provider the user did not intend to trust.

**Impact:** Privacy breach.

**Mitigations:**

- model profiles declare data policy;
- task/context sensitivity labels;
- routing constraints;
- local-only profile option;
- audit provider selection;
- explicit failure rather than silent fallback when policy forbids another provider.

### TM-17: Fallback model gains broader authority

**Scenario:** Primary model unavailable, router switches to another provider/model with different safety behavior.

**Impact:** Unexpected data exposure/behavior.

**Mitigations:**

- authority remains outside model;
- model fallback policy separate from connector grants;
- provider sensitivity constraints;
- capability negotiation;
- no hidden fallback for protected tasks.

### TM-18: Malicious webhook/event

**Scenario:** Attacker sends forged event causing scheduled work/actions.

**Impact:** Trigger abuse.

**Mitigations:**

- authenticate webhooks;
- replay protection;
- event provenance;
- event merely creates bounded task context, not automatic privilege;
- Sentinel still authorizes side effects.

### TM-19: Audit tampering

**Scenario:** Runtime edits logs to hide action.

**Impact:** Loss of accountability/recovery.

**Mitigations:**

- runtime cannot write authoritative audit store;
- append-only API;
- actor identity/correlation IDs;
- optional hash chaining/signing later.

### TM-20: Backup leakage

**Scenario:** unencrypted backup exposes memory/files/credentials.

**Impact:** Broad confidentiality breach.

**Mitigations:**

- encrypt backups;
- separate credential backup policy;
- least-privilege storage access;
- restore tests;
- avoid plaintext export of secrets.

## Threats intentionally not solved by MVP

The MVP will not claim to fully defend against:

- malicious host root/kernel;
- hardware/firmware compromise;
- side channels between co-resident workloads in all environments;
- all prompt-injection techniques;
- all supply-chain compromise;
- a user deliberately approving a clearly described malicious action;
- malicious behavior by an external service after OpenMuse legitimately sends authorized data.

These are residual risks, not reasons to weaken the enforceable boundaries we can build.

## Security test suite categories

The repository should eventually include deterministic tests for:

- direct network bypass;
- private-IP/metadata SSRF;
- credential absence in runtime;
- wrong-worker credential requests;
- approval scope mismatch;
- expired/revoked grant;
- duplicate replay of approval;
- prompt-injection exfiltration fixture;
- memory poisoning fixture;
- untrusted tool-output schema escape;
- user browser takeover pause;
- generated skill attempting security-plane write;
- crash/retry around non-idempotent action;
- runaway subagent/resource limits;
- model-routing sensitivity policy.

## Review cadence

Update this document whenever:

- a new privileged component is added;
- a new type of user data enters the system;
- the runtime receives a new Linux capability/mount/network path;
- a connector gains write authority;
- approval semantics change;
- a model provider receives additional sensitive context;
- a browser capability expands;
- deployment becomes multi-user/hosted;
- a security incident or red-team finding reveals a new attack path.
