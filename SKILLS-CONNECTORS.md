# OpenMuse Skills and Connectors

## Purpose

OpenMuse needs to learn how to do new things without coupling every capability to the core agent loop. Skills and connectors provide two different extension mechanisms and must remain conceptually separate.

> **A skill teaches behavior. A connector grants structured access to an external service.**

A skill may run entirely in the untrusted runtime. A connector that uses protected credentials belongs in the security plane.

## Skill

A skill is a versioned package containing instructions and optionally code/resources that help the agent perform a class of tasks.

Illustrative layout:

```text
skills/
  home-assistant/
    SKILL.md
    manifest.yaml
    bin/
      ha
    scripts/
    tests/
    examples/
```

### Skill manifest

Example:

```yaml
name: home-assistant
version: 0.1.0
description: Work with a Home Assistant instance through the OpenMuse HA connector.
author: user
entrypoints:
  - bin/ha
requires:
  tools:
    - connector.home_assistant
  network: []
capabilities:
  requested:
    - home_assistant.read
    - home_assistant.service_call
```

`requested` capabilities are declarations, not grants.

## SKILL.md

`SKILL.md` is human- and agent-readable operational guidance:

- when to use the skill;
- commands/tools available;
- examples;
- expected outputs;
- known limitations;
- safety notes;
- common workflows.

Skills should be concise enough for on-demand context loading. The runtime should discover metadata without injecting every installed skill into every model call.

## Skill lifecycle

```text
discovered
  -> staged
  -> validated
  -> installed
  -> enabled
  -> disabled
  -> updated
  -> removed
```

### Generated skills

OpenMuse may generate a skill when no suitable capability exists.

Required process:

1. create in a build/staging workspace;
2. generate manifest and provenance;
3. run tests in sandbox;
4. inspect declared capabilities and filesystem/network needs;
5. produce content hash/version;
6. request installation approval according to policy;
7. install into versioned skill store;
8. grant no credentials automatically.

Generated skill code must not modify security-plane code or policy.

## Skill provenance

Track:

```text
source = bundled | registry | git | user | agent_generated
source_uri
source_revision
content_hash
created_by
created_for_goal/task
review_state
installed_at
```

This allows auditing and safe update decisions.

## Connector

A connector exposes typed operations against an external service or protected local system.

Examples:

```text
gmail.list_messages
gmail.get_message
gmail.create_draft
gmail.send_message
calendar.list_events
calendar.create_event
github.list_issues
github.create_issue
home_assistant.get_state
home_assistant.call_service
```

### Connector manifest

```yaml
name: gmail
version: 1
worker: openmuse-connector-gmail
credentials:
  - id: google_oauth
methods:
  list_messages:
    risk: low
    auth: read
  create_draft:
    risk: moderate
    auth: write
  send_message:
    risk: high
    auth: write
```

Connector manifests are security-relevant and should be reviewed/versioned.

## Connector worker architecture

Preferred built-in pattern:

```text
Agent runtime
    |
    | thin CLI / typed RPC
    v
Connector facade
    |
    v
Sentinel -----> grant/approval
    |
    v
Privileged connector worker
    |
    +-----> credential broker
    |
    v
External API
```

The runtime-facing CLI contains no reusable credential.

## Why not put connector credentials in skill CLIs?

If the agent can modify the same code that can read a credential, a prompt injection can potentially rewrite that code to exfiltrate the secret.

Separating privileged connector workers means agent-generated runtime code can request actions but cannot simply dump the underlying token.

## Connector SDK

The connector SDK should make secure behavior easier than insecure behavior.

It should provide:

- typed method schemas;
- credential binding by reference;
- authenticated worker identity;
- Sentinel request construction;
- audit hooks;
- redaction utilities;
- idempotency helpers;
- pagination helpers;
- error normalization;
- test harness with fake credentials/providers.

## Connector method schema

Example:

```json
{
  "name": "gmail.send_message",
  "input_schema": {
    "type": "object",
    "required": ["to", "subject", "body"],
    "properties": {
      "to": {"type": "array", "items": {"type": "string"}},
      "subject": {"type": "string"},
      "body": {"type": "string"}
    }
  },
  "risk": "high",
  "side_effect": "external_write",
  "idempotency": "provider_or_application_key"
}
```

The agent cannot invent undocumented arguments that widen credential scope.

## MCP

OpenMuse should support MCP where useful, but MCP availability does not automatically make an MCP server trusted.

Classify MCP servers by execution/authority:

### Runtime MCP

Runs inside the untrusted runtime with no protected credentials and under egress policy.

### Brokered MCP

A trusted adapter exposes selected MCP operations through Sentinel and credential controls.

### External MCP

Remote server is an external service. Data sent to it is egress and subject to policy.

Never equate "MCP connected" with "permission granted."

## CLI tools

CLI is a useful agent interface because models can discover and compose commands naturally.

OpenMuse should prefer predictable machine-readable modes:

```bash
openmuse-gmail list --query 'newer_than:7d' --json
```

over parsing pretty terminal output.

Every CLI should have:

- `--help`;
- stable exit codes;
- structured JSON output option;
- clear error messages;
- no secret output;
- no hidden interactive prompts during unattended execution.

## Skill discovery

The orchestrator should build a compact catalog from manifests:

```text
name
description
capability tags
entrypoints
```

The model can request full `SKILL.md` only when relevant. This keeps prompt size bounded as the skill library grows.

## Installing third-party skills

Third-party skills are untrusted code.

Installation should record:

- source and version/commit;
- content hash;
- requested capabilities;
- executable files;
- dependency manifest;
- test/static scan outcome;
- user/admin approval if required.

The skill still runs under runtime isolation and Sentinel egress rules.

## Dependencies

Avoid letting skills mutate the base runtime globally in uncontrolled ways.

Prefer one of:

- skill-specific Python venv;
- isolated package environment;
- immutable image layer built from approved manifest;
- containerized worker for complex dependencies.

This improves reproducibility and rollback.

## Tool building

OpenMuse's tool-builder workflow should differentiate:

### Pure local tool

Example: parse a proprietary file format. It can be generated, tested, and installed entirely in the runtime.

### Public API tool

Generated skill can call public endpoints through Sentinel-controlled egress.

### Credentialed API tool

Do not allow generated code to receive raw credential by default. Options:

1. build a user-reviewed privileged connector;
2. use a generic trusted authenticated HTTP broker with tightly constrained destination/method/credential scope;
3. require explicit unsafe/developer mode for direct secrets, with prominent warnings.

The secure path should be the normal path.

## Generic authenticated HTTP broker

To avoid writing a privileged connector for every API, OpenMuse may later provide a generic broker where the user binds:

```text
credential -> exact origin + allowed methods/paths
```

For example:

```yaml
connection: custom-inverter-api
origin: https://api.vendor.example
credential: cred://custom-inverter/main
allowed:
  - method: GET
    path_prefix: /v1/status
```

The generated skill sees only the broker reference. This provides flexibility without raw secrets.

## Browser vs connector

Use connector when:

- stable API exists;
- structured data/action is possible;
- narrow authorization can be expressed.

Use browser when:

- no suitable API exists;
- user workflow inherently requires website UI;
- visual state matters.

Browser automation should not become a shortcut for avoiding connector permission policy.

## Skills registry

A future registry should distribute metadata and packages, not trust.

Useful registry features:

- signed publisher identity;
- content hashes;
- reproducible releases;
- declared capabilities;
- compatibility version;
- security advisories;
- popularity/reputation signals;
- source code link.

The user/runtime still installs under local policy.

## Version compatibility

Manifests should declare:

```yaml
openmuse:
  min_version: 0.2.0
skill_api: 1
connector_api: 1
```

OpenMuse should version contracts independently from package versions.

## Revocation

Disabling/removing a skill must stop future execution but should not delete historical audit records.

Disconnecting a connector must:

- revoke credential binding;
- invalidate surrogates;
- invalidate or suspend related grants;
- cause future scheduled tasks to enter a clear blocked state.

## Initial connector priorities

For a useful personal-agent MVP, prioritize a small representative set rather than dozens:

1. filesystem/runtime (local, no external credential);
2. browser/public web;
3. email (read + approval-gated send);
4. calendar (read + approval-gated create/update);
5. GitHub or another developer service as a test of typed credentialed integration.

The architecture matters more than connector count.

## Acceptance criteria

- agent can discover a skill on demand;
- agent can create/test a generated local skill;
- generated skill cannot read connector credential;
- connector write is blocked without Sentinel grant;
- connector worker can only access its allowlisted credential;
- disconnect revokes future access;
- runtime MCP cannot bypass egress;
- skill package is versioned and attributable;
- same connector can be invoked by different model providers with identical typed semantics.
