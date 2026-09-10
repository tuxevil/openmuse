# OpenMuse Sentinel

## Role

Sentinel is the independent authority that decides whether the OpenMuse runtime may perform an external or privileged action.

The main agent can **propose** actions. Sentinel decides whether they are:

```text
ALLOW
DENY
ASK_USER
```

The main agent cannot override Sentinel, mint grants, read its secret policy state, or modify its code.

## Why Sentinel exists

LLMs are probabilistic and consume adversarial data. A system prompt such as "ask before sending email" is useful behavior guidance, but it is not a reliable access-control mechanism.

Sentinel converts human consent and administrator policy into structured, enforceable capabilities.

## Authority boundary

Sentinel should be the sole decision point for:

- connector actions;
- network egress from the untrusted runtime;
- protected browser actions;
- use of credential references;
- installation of privileged capabilities;
- any other action class explicitly assigned to it.

A deployment is insecure if the runtime has an alternate route that can produce the same side effect without Sentinel.

## Action request

Every privileged operation is represented as a typed request.

Illustrative schema:

```json
{
  "request_id": "req_01J...",
  "subject": {
    "runtime_id": "runtime_user_1",
    "execution_id": "exec_123",
    "task_id": "task_77",
    "goal_id": "goal_42"
  },
  "action": {
    "namespace": "gmail",
    "operation": "send_message",
    "risk": "high"
  },
  "resource": {
    "connection_id": "conn_gmail_primary"
  },
  "scope": {
    "recipient": "alice@example.com",
    "message_hash": "sha256:..."
  },
  "purpose": {
    "class": "user_requested_communication",
    "summary": "Send the finalized project update to Alice"
  },
  "provenance": {
    "trigger": "conversation",
    "user_message_id": "msg_123"
  }
}
```

Sentinel should derive or verify risk metadata itself; the runtime cannot lower the risk simply by claiming `risk: low`.

## Decision

```json
{
  "decision": "allow",
  "request_id": "req_01J...",
  "grant_id": "grant_01J...",
  "constraints": {},
  "audit_id": "audit_01J..."
}
```

or:

```json
{
  "decision": "deny",
  "reason_code": "destination_not_allowed",
  "user_visible_reason": "This permission does not cover that recipient."
}
```

or:

```json
{
  "decision": "ask_user",
  "approval_id": "approval_01J...",
  "display": {
    "title": "Send email?",
    "summary": "Send this message to alice@example.com",
    "details": {}
  },
  "grant_options": ["once", "this_task"]
}
```

## Grants

A grant is an authoritative capability record, not a line of natural language.

Minimum fields:

```text
id
issuer
subject/action/resource constraints
goal/task constraints
destination constraints
purpose class
created_at
not_before
expires_at
max_uses
uses
revoked_at
parent approval/policy
```

### Scope types

OpenMuse should eventually support:

- `once` — one matching invocation;
- `session` — while a trusted user session remains active;
- `task` — only one task;
- `goal` — tasks belonging to one goal;
- `time_bounded` — until a specific time;
- `persistent` — until revoked.

Not every action should offer every scope. For example, purchases may remain approval-every-time even when browsing is permanently allowed.

## Policy sources

Sentinel combines policy from several sources with explicit precedence:

```text
hard safety invariant
    > administrator/deployment policy
        > user deny/revocation
            > user grant
                > goal/task requested scope
                    > agent proposal
```

The exact precedence needs tests. A lower-precedence layer can never broaden a higher-level deny.

## Risk registry

Maintain a versioned registry of action classes.

Example:

```yaml
gmail.read_message:
  default_risk: low
  default_policy: ask_on_first_use

gmail.create_draft:
  default_risk: moderate
  default_policy: ask_on_first_use

gmail.send_message:
  default_risk: high
  default_policy: ask
  allowed_grants: [once, task, time_bounded]

payments.purchase:
  default_risk: critical
  default_policy: always_ask
  allowed_grants: [once]
```

Risk is determined by policy code and action schema, not model prose.

## User approval path

The approval request should go:

```text
Sentinel -> trusted Gateway/client -> explicit approval UI -> Sentinel
```

It should not go:

```text
Sentinel -> model -> chat bubble -> model parses "yes" -> allowed
```

The UI must distinguish trusted approval controls from content produced by the agent, websites, or artifacts.

## Purpose binding

Permissions should be bound not only to connector/action but also to a meaningful use case when possible.

Example:

```text
ALLOW calendar.create_event
for task=plan-trip-quito
```

should not automatically allow:

```text
calendar.create_event
for unrelated task=marketing-spam
```

Purpose binding reduces reuse of broad privileges after prompt injection.

## Request canonicalization

Sentinel must authorize the same concrete object that is executed.

For an email send:

- recipients;
- subject;
- body hash/content class;
- attachments;
- sending account;

should not be mutable after approval without re-evaluation.

For HTTP egress:

- hostname;
- resolved IP;
- method;
- path;
- relevant body sensitivity;
- credential reference;

must be evaluated close to the network boundary.

This prevents time-of-check/time-of-use gaps where the runtime gets one request approved and sends another.

## Egress policy

Sentinel should own a network-policy interface independent of connector policy.

Example request:

```json
{
  "process": "runtime:exec_123:pid_999",
  "destination": {
    "hostname": "api.example.com",
    "resolved_ip": "203.0.113.10",
    "port": 443,
    "protocol": "https"
  },
  "http": {
    "method": "POST",
    "path": "/v1/items"
  },
  "data_labels": ["private:user"]
}
```

### Default egress behavior

- public read-only web browsing may be auto-allowed under a narrow browsing policy;
- private/internal IPs denied unless explicitly configured;
- authenticated requests require credential/use policy;
- outbound requests carrying private data to new destinations require approval or explicit policy;
- unknown protocols denied initially.

## Taint/data labels

MVP can propagate coarse labels through execution context:

```text
PUBLIC
USER_PRIVATE
CONNECTOR_PRIVATE
SECRET_REFERENCE
HIGHLY_SENSITIVE
```

A process/task that reads private projections becomes data-sensitive for policy decisions.

This is not a complete information-flow-control system, but it creates the contract required for future kernel-level taint tracking.

## Credential surrogation

Sentinel and credential broker cooperate so the runtime can invoke authenticated operations without seeing reusable credentials.

Example:

```text
runtime sends Authorization: Bearer surrogate_xyz
          |
          v
Sentinel validates destination + action
          |
          v
trusted boundary exchanges surrogate for real token
          |
          v
request sent
```

Properties:

- surrogate must not be useful at another destination;
- redemption must authenticate trusted caller;
- surrogates expire;
- original credential never appears in runtime logs;
- revoke connection invalidates future use.

## Connector policy

For built-in connectors, Sentinel receives typed operations rather than trying to infer semantics from arbitrary HTTP.

Example:

```text
calendar.list_events
calendar.create_event
calendar.update_event
calendar.delete_event
```

Fine-grained methods permit useful policies such as read-always/write-ask.

## Browser policy

Browser broker submits high-risk events to Sentinel:

```text
browser.navigate
browser.upload_file
browser.secure_fill
browser.submit_form
browser.send_message
browser.checkout
browser.account_setting_change
```

Normal click/navigation can remain low-friction. A classifier may help identify checkout/forms, but final policy should use deterministic signals whenever possible.

## Pending approvals

When decision is `ASK_USER`:

1. operation stops before side effect;
2. approval row is persisted;
3. task moves to `waiting_for_approval`;
4. user receives trusted approval UI;
5. response creates grant or denial;
6. task resumes from checkpoint;
7. original request is revalidated against grant;
8. operation executes or fails safely.

Approvals need expiration to avoid stale actions executing unexpectedly days later.

## Replay protection

Approval responses and one-time grants require unique nonces/IDs. Replaying an old client response must not create a second grant or repeat an action.

## Audit

Sentinel emits authoritative audit events for:

- request received;
- policy inputs used;
- decision;
- approval created;
- user response;
- grant created/used/revoked/expired;
- credential surrogate redeemed;
- egress allowed/denied;
- connector action allowed/denied.

Logs must store identifiers/hashes instead of secrets.

## Failure mode

Sentinel should fail closed for protected actions.

If Sentinel is unavailable:

- already-running purely local computation may continue according to runtime policy;
- new network egress and protected connector actions fail/queue;
- the system must not bypass policy "to keep working."

## Sentinel implementation phases

### Phase 0 — policy interface

Build the typed `ActionRequest -> Decision` service with deterministic rules and PostgreSQL grants/approvals. No LLM required.

### Phase 1 — connector authority

All protected connector writes pass through Sentinel and trusted workers.

### Phase 2 — network authority

Runtime has no direct egress; proxy submits concrete requests to Sentinel.

### Phase 3 — data labels

Task/process sensitivity propagates to egress decisions.

### Phase 4 — independent classifiers

Add prompt-injection/data-exfiltration classifiers outside runtime as a defense-in-depth signal.

### Phase 5 — hardened attribution

Explore cgroups/eBPF/LSM or a dedicated sandbox backend for process-level egress and taint attribution.

## Tests that must exist before broad autonomy

- runtime cannot access network when Sentinel/proxy is stopped;
- `DENY` cannot be bypassed through another connector path;
- one-time grant cannot be reused;
- task-scoped grant cannot be used by another task;
- expired grant fails;
- revoked grant fails;
- modified action after approval fails;
- forged chat "approval" has no effect;
- wrong connector worker cannot redeem a credential;
- SSRF to loopback/private/metadata destination fails;
- runtime cannot read auth store;
- Sentinel failure is fail-closed for external side effects.
