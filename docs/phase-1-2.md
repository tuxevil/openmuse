# Phase 1 + Phase 2 implementation

This slice is deliberately a modular monolith. It proves durable orchestration
state and model replacement before OpenMuse receives a host-facing runtime or
credentialed tools.

## Run the smoke demo

```bash
PYTHONPATH=src python -m openmuse.cli --db /tmp/openmuse.db migrate
PYTHONPATH=src python -m openmuse.cli --db /tmp/openmuse.db user-create sebastian@example.com --name Sebastian
PYTHONPATH=src python -m unittest discover -s tests -v
```

The `demo` command accepts an instance ID, creates a goal/task/schedule,
delivers the schedule once, and runs it through the deterministic fake model.

## Production database

Use a PostgreSQL DSN with the optional dependency:

```bash
pip install 'openmuse[postgres]'
PYTHONPATH=src python -m openmuse.cli --db 'postgresql://user:password@localhost/openmuse' migrate
```

The application generates opaque IDs and stores provider-neutral domain state.
PostgreSQL migrations are in `migrations/`; SQLite exists only to make the
contract and recovery tests runnable without an external service.

## Contracts and boundaries

- `ControlPlaneRepository` owns durable lifecycle state and writes audit/outbox
  records in the same transactions as domain changes.
- `ContextBuilder` reconstructs a bounded `ModelRequest` from task and execution
  state; a hidden provider conversation is never required for recovery.
- `ModelAdapter` is the harness boundary. `FakeModelAdapter` is deterministic;
  `OpenAICompatibleAdapter` uses only the standard library and does not expose
  provider response objects to the control plane.
- `ToolRegistry` validates model proposals before dispatch. It explicitly
  refuses a `grant_permission` tool; Sentinel is not implemented in this phase.
- `ModelRouter.resolve(..., local_only=True)` filters profiles before adapter
  selection and therefore cannot silently broaden a local-only task to a cloud
  profile.

## Deliberate non-goals

This phase does not claim to provide runtime isolation, network egress control,
credential brokering, browser mediation, or trusted approvals. Those belong to
Phases 3–6 and must not be simulated by system prompts or the current minimal
HTTP API.
