# OpenMuse Security

## Security goal

OpenMuse is designed for a difficult security environment: an AI agent receives untrusted natural-language content, runs generated code, browses arbitrary websites, reads private user data, and may be authorized to act on external services.

The project therefore assumes that the main agent can be manipulated or simply make mistakes.

The primary objective is not to prove that the agent will always behave correctly. It is to **bound the damage possible when it does not**.

## Core security invariant

> The untrusted agent runtime must not be able to grant itself credentials, permissions, network access, or privileged connector actions.

All enforcement for those capabilities belongs outside the runtime.

## Trust model

OpenMuse starts with four trust classes.

### Trusted security plane

Contains the smallest practical set of components that enforce:

- policy;
- approvals;
- credential storage/use;
- connector privilege separation;
- browser credential insertion;
- network egress;
- audit integrity.

The security plane is the trusted computing base (TCB).

### Trusted control plane

Coordinates tasks and stores durable state, but should not casually possess raw secrets. It is trusted to schedule work and present policy state, not to bypass Sentinel.

### Untrusted execution plane

Includes:

- main agent loop execution context;
- model-generated commands;
- shell;
- downloaded files;
- generated code;
- third-party skill code;
- tool outputs;
- external webpage content;
- subagents.

Assume compromise is possible.

### External systems

Websites, APIs, model providers, plugins, package repositories, webhook senders, and connected services are outside OpenMuse's trust boundary.

## Security principles

### 1. Deny by construction where practical

The runtime should have no route to an external network except through a controlled egress mechanism. A policy engine that can be bypassed by opening another socket is not an authority.

### 2. Credentials are capabilities, not strings

Do not expose long-lived credentials to the model or general runtime environment. Prefer opaque references and just-in-time use by trusted components.

### 3. Conversation is not authorization

A chat message can express intent, but sensitive authorization must be represented by a structured approval/grant issued through trusted UI/API paths.

### 4. Least privilege at every layer

Scopes must be narrowed by:

- connector;
- account/connection;
- operation;
- resource;
- destination;
- task/goal;
- time;
- amount/quantity where relevant;
- read vs write;
- network destination;
- calling process/service.

### 5. Defense in depth

Model-level prompt-injection resistance is useful but insufficient. OpenMuse should combine:

- model instructions;
- untrusted-content labeling;
- classifier/detector layers where useful;
- runtime isolation;
- credential isolation;
- deterministic connector schemas;
- egress policy;
- human approval;
- audit and anomaly detection.

### 6. Secure defaults

Initial deployment should start cautious:

- read-only connectors before write access;
- public browsing before authenticated actions;
- no host network in runtime;
- no host credential mounts;
- approval for irreversible/high-impact actions;
- generated skills installed without credentials;
- network destinations constrained.

Users can relax policy explicitly.

## Credential architecture

### Requirements

Raw reusable secrets should not be available through:

- environment variables visible to the runtime;
- workspace files;
- shell history;
- model context;
- tool output;
- browser page snapshots;
- normal application logs.

### Credential references

The execution plane uses references:

```text
cred://gmail/primary
cred://github/personal
cred://browser/github.com/default
```

These references are not secrets.

### Surrogate flow

For integrations that require authorization headers or tokens:

```text
runtime
  -> surrogate request
credential broker
  -> opaque surrogate
runtime/connector request
  -> Sentinel validates concrete destination/action
Sentinel or connector worker
  -> obtains/injects real credential just in time
external service
```

Surrogates should be:

- short-lived;
- audience-bound;
- operation/scope-bound when possible;
- unusable outside the trusted boundary;
- revocable;
- logged by identifier, never secret value.

### Browser secrets

Passwords and sensitive form values should be captured by a secure client flow and inserted through `browserd` without becoming visible in the accessibility snapshot or runtime logs.

## Network egress

The runtime must not receive unrestricted outbound networking.

### MVP

Use a mandatory explicit proxy plus Linux network isolation. Only the proxy may reach the external network. Policy should evaluate at least:

- hostname;
- resolved IP;
- port;
- protocol;
- HTTP method where available;
- path where available;
- task identity;
- process/runtime identity;
- data sensitivity label where available.

Prevent bypass paths such as:

- direct host networking;
- alternate interfaces;
- Docker socket access;
- raw sockets;
- arbitrary VPN/tunnel creation;
- DNS rebinding to private addresses;
- localhost/metadata-service access.

### SSRF

After DNS resolution, Sentinel/proxy must reject prohibited address ranges even when the original hostname looked public.

At minimum protect:

- loopback;
- link-local;
- RFC1918/private ranges unless explicitly approved;
- cloud metadata endpoints;
- internal service networks;
- host gateway addresses.

### Data-aware egress

A hardened future design should track whether a process has accessed private user data and raise the authorization bar for outbound requests from that process.

The first version can approximate this with task/tool labels. A later version may use kernel-level attribution/taint propagation.

## Connector security

Built-in connectors that require private credentials should run outside the runtime.

The runtime gets thin typed CLIs or RPC stubs. Example:

```text
openmuse-gmail search --query 'from:example.com'
```

The CLI should not contain credentials. It submits a typed request to the privileged connector service.

Connector worker identity must be strongly authenticated. Each worker gets explicit credential allowlists. A Gmail worker must not be allowed to fetch arbitrary credentials simply because `authd` is reachable.

### Read/write separation

Where the upstream provider permits it, OAuth scopes should separate read and write.

OpenMuse policy then narrows them further. Possessing Gmail read OAuth scope does not imply the agent may read account security messages or extract login codes.

### Sensitive email filtering

Email connectors should treat the following as protected classes:

- one-time passcodes;
- password-reset links;
- magic login links;
- security-recovery material;
- raw authentication tokens.

The default agent view should redact or omit them unless a specific trusted workflow requires otherwise.

## Browser security

The browser encounters adversarial content by default.

### Broker requirement

Chromium/Playwright should be controlled by a broker outside the main runtime. The browser agent receives a constrained action API, not unrestricted CDP.

### Page representation

Prefer accessibility-tree snapshots and screenshots over arbitrary DOM/script access. The browser agent should not be able to execute JavaScript in page context merely to bypass broker restrictions.

### User takeover

When the user takes over the browser or enters protected credentials, automated browser actions pause.

### High-risk browser actions

Examples that should require additional policy/approval include:

- checkout/payment;
- account deletion;
- changing security settings;
- posting public content;
- sending messages;
- accepting contracts/terms on behalf of the user;
- uploading private files;
- entering personal identifiers into a new domain;
- downloading/executing unknown binaries.

## Prompt injection

Prompt injection is not considered solved.

OpenMuse should label external data as untrusted and maintain a clear distinction between:

- user/developer instructions;
- tool observations;
- website content;
- connector data;
- files;
- generated/retrieved memory.

Defenses may include classifier ensembles and explicit context labels, but these cannot replace deterministic boundaries.

The architecture must remain safe enough if a model believes the malicious instruction.

## Approval system

Approvals are structured capabilities.

A grant should include fields such as:

```text
grant_id
subject
connector/action
resource/destination
purpose class
goal/task scope
issued_at
expires_at
max uses
constraints
issuer
revocation state
```

Supported lifetimes should eventually include:

- one use;
- current session;
- current task;
- current goal;
- bounded time window;
- persistent until revoked.

A later invocation is allowed only if its structured request is inside the grant scope.

## Sensitive-action taxonomy

OpenMuse should maintain a versioned action-risk registry.

Illustrative classes:

### Low risk

- read public webpage;
- list local workspace files;
- read a connector explicitly granted read access;
- create a draft artifact.

### Moderate risk

- upload a non-sensitive file to an approved destination;
- edit a reversible calendar event;
- create a draft email in a connected account;
- install a new non-privileged skill.

### High risk

- send a message/email;
- publish content;
- purchase or transfer money;
- delete remote data;
- change account/security settings;
- reveal private information to a new destination;
- execute a contract/accept binding terms;
- grant another principal access.

Risk classification informs policy; it does not itself grant permission.

## Generated code and skills

The agent may create code in the execution plane. It may not modify the trusted security plane.

Generated skills require:

- manifest;
- provenance;
- declared capabilities;
- content hash/version;
- test result;
- install state;
- author (`agent`, `user`, external package);
- optional review/approval.

A generated skill receives no connector credentials automatically.

## Update integrity

Security-plane binaries/configuration must not be writable by the runtime.

Eventually, releases should support:

- signed release artifacts;
- reproducible or attestable builds where practical;
- explicit migration steps;
- rollback;
- separate policy/config change audit.

## Logging and telemetry

Never log raw secrets.

Logs should redact:

- credentials;
- authorization headers;
- cookies/session tokens;
- OTPs;
- password reset URLs/tokens;
- payment information;
- sensitive form values.

Model trajectories may contain personal information and should be treated as private user data. Hosted deployments should make remote telemetry explicit and configurable.

## Backup and export

Backups of memory/workspace/state may contain highly sensitive data. Backups must be encrypted at rest in hosted deployments.

Credential export is a separate decision from normal OpenMuse export. Default exports should contain re-bindable credential references and connector metadata, not plaintext secrets.

## Local deployment caveat

A local-first install cannot protect the user from a fully compromised host kernel/root administrator. OpenMuse isolation protects components from each other under the assumed host trust model; it is not a replacement for host security.

This limitation must be stated plainly.

## Security review gates

The following changes require a threat-model update before merge:

- new credential path;
- new network bypass or protocol;
- new privileged connector;
- broader runtime capabilities;
- browser CDP exposure;
- host filesystem mounts;
- new approval/grant type;
- remote multi-tenant architecture;
- automatic installation/execution of agent-generated privileged code;
- changes that move a component into or out of the TCB.

## Security milestone for MVP

The first meaningful security milestone is not "prompt injection resistant." It is:

1. runtime has no raw connector credentials;
2. runtime has no unrestricted network route;
3. sensitive connector action is impossible without Sentinel authorization;
4. user approval travels through a trusted structured path;
5. runtime cannot modify Sentinel/authd/connector-worker code or policy;
6. every sensitive attempt has an audit event;
7. a simulated prompt injection that tells the agent to exfiltrate a secret fails because the secret is unavailable and the egress/action is denied.

If the MVP cannot demonstrate those properties, additional agent autonomy should wait.
