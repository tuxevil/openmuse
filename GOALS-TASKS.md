# OpenMuse Goals and Tasks

## Purpose

OpenMuse should behave as a persistent agent, not as a sequence of isolated chat turns. Goals and tasks are the durable control-plane objects that make that possible.

A **goal** describes an outcome the user wants. A **task** describes a bounded unit of work performed in service of a goal or direct request. An **execution** is one attempt to perform a task.

```text
Goal
  -> Plan versions
  -> Tasks
      -> Executions
          -> Tool calls / observations / approvals / artifacts
```

## Goal model

Suggested initial schema:

```text
id
owner_id
title
description
success_criteria
constraints
status
priority
plan_version
notification_policy
budget
created_at
updated_at
started_at
completed_at
paused_at
```

### Goal status

```text
draft
active
paused
blocked
completed
cancelled
failed
```

`blocked` means OpenMuse knows it cannot progress without a dependency such as user input, approval, unavailable service, or external event.

## Goal success criteria

Goals should have explicit conditions when practical.

Bad:

```text
Find me a GPU.
```

Better:

```text
Find a Quadro RTX 4000 with estimated landed cost <= $180,
compatible with my stated constraints, from a seller/source I can inspect.
```

Success criteria help the agent decide whether new work matters and when to stop.

## Constraints

Constraints are durable task context, not necessarily security policy.

Examples:

- maximum price;
- date range;
- location;
- acceptable vendors;
- required output format;
- "do not contact sellers";
- "only use local models for this project".

Security-critical constraints should also be represented in deterministic policy where relevant.

## Plan

A plan is versioned rather than overwritten silently.

```text
plan v1
  research sources
  compare listings
  notify user

plan v2
  research sources
  verify shipping to Ecuador
  calculate landed cost
  notify user
```

Plan revisions store reason/provenance and do not erase completed history.

The plan is advisory orchestration state; it does not grant permissions.

## Task model

Suggested fields:

```text
id
goal_id
parent_task_id
type
title
input
expected_output
status
priority
dependency_ids
schedule_id
trigger_event_id
budget
retry_policy
checkpoint
created_at
started_at
finished_at
```

### Task status

```text
pending
ready
running
waiting_for_approval
waiting_for_user
waiting_for_event
waiting_for_dependency
retry_scheduled
succeeded
failed
cancelled
uncertain_external_state
```

`uncertain_external_state` is important for non-idempotent side effects after crashes.

## Execution model

Each attempt has:

```text
execution_id
task_id
attempt
runtime_id
model_profile
status
started_at
ended_at
checkpoint_before
checkpoint_after
usage
error
```

A task may have multiple executions due to retry, interruption, model switch, or recovery.

## Scheduling

OpenMuse supports durable schedules attached to tasks/goals.

Initial trigger types:

### One-time timer

```text
run_at: 2026-09-15T09:00:00-05:00
```

### Recurrence

Use a standard representation such as iCalendar RRULE where practical.

```text
FREQ=DAILY;BYHOUR=8
```

### Event trigger

Examples:

- incoming email matching filter;
- GitHub issue/PR event;
- webhook;
- price feed change;
- task completion;
- file change;
- calendar event approaching.

### Poll/watch

Some conditions have no push event and require periodic checks. A watch should define:

- interval/minimum cadence;
- condition;
- source;
- state from previous check;
- notification rule;
- resource/cost budget;
- stop condition.

## Scheduling semantics

The scheduler creates task executions through the same orchestration path as interactive work. A scheduled job gets no extra authority because it runs unattended.

If it needs an action not covered by a grant, it pauses for approval.

## Event provenance

Events are untrusted inputs unless produced by a trusted internal component.

Event record:

```text
id
type
source
authentication/provenance
received_at
payload_reference
deduplication_key
related_goal/task
```

Webhooks require authentication/replay protection.

## Concurrency

OpenMuse must support multiple independent tasks concurrently while protecting shared state.

Rules:

- each task has a stable ID and bounded context;
- writes to shared goal state use optimistic versioning or transactions;
- subagent outputs are observations/proposals until merged;
- plan updates must handle concurrent changes;
- conflicting tasks should be serialized when they share external side effects.

## Subagents

A task can fan out bounded child tasks/subagents.

Example:

```text
research GPU
  |- marketplace A worker
  |- marketplace B worker
  |- shipping-cost worker
  `- synthesis worker
```

The parent defines:

- maximum fan-out;
- maximum depth;
- role/model profile;
- per-child budget;
- deadline;
- expected output schema.

Subagents inherit no new security authority automatically. They operate under task-scoped capability rules.

## Checkpointing

Long-running work must be resumable from explicit state.

A checkpoint can contain:

```json
{
  "phase": "verify_shipping",
  "completed_items": ["listing_1", "listing_2"],
  "pending_items": ["listing_3"],
  "artifact_ids": ["artifact_8"],
  "observation_ids": ["obs_12", "obs_13"]
}
```

Do not rely solely on a model's hidden session state to resume.

## User interruption

If the user sends a new message while work is running, the control plane determines whether it is:

- additional information for the running task;
- cancellation;
- changed constraints;
- a separate task;
- an unrelated side-chat message.

The agent may need to cancel/replan, but durable task state prevents losing work.

## Waiting for approval

Sensitive action flow:

```text
running
  -> Sentinel ASK_USER
  -> waiting_for_approval
  -> grant/deny event
  -> ready/resume OR blocked/cancelled
```

The task checkpoint must be committed before waiting so a restart does not lose the pending action context.

## Waiting for user input

Not every question is a security approval. A task may need a preference/decision.

Use a separate structured `input_request` object so ordinary questions do not become permission grants.

## Notifications and proactivity

Completing background work does not always mean sending a message.

A `NotificationDecision` should consider:

- novelty;
- urgency;
- user action required;
- impact on success criteria;
- user-selected verbosity;
- duplicate/recent notification;
- time/day policy;
- confidence.

Possible result:

```text
notify_now
include_in_digest
update_goal_silently
discard_as_not_material
```

The evaluator may use an LLM, but deterministic rules should enforce quiet hours/critical alerts/preferences where configured.

## Ideas

Ideas are proposals generated from goals, memory, patterns, and observations.

An idea is **not** an active task and has no authority to act.

```text
idea -> user accepts -> goal/task
```

Some deployments may allow explicitly configured low-risk auto-promotion, but the default should be conservative.

## Budgeting

Budgets can exist at:

- user/day/month;
- goal;
- task;
- execution;
- model role.

Budget dimensions:

- tokens;
- estimated USD;
- wall-clock time;
- tool calls;
- browser minutes;
- subagent count.

Budget exhaustion creates a durable blocked/failed state rather than relying on the model to notice cost.

## Retry policy

Tasks need explicit retry semantics:

- max attempts;
- backoff;
- retryable errors;
- deadline;
- idempotency requirements.

Never automatically retry a high-impact operation when external completion is uncertain.

## Cancellation

Cancellation propagates from goal -> tasks -> active executions where appropriate.

The system records whether an external action had already happened before cancellation.

## Goal archive

When a goal completes:

- final result/artifacts retained;
- plan and task history archived;
- relevant lessons may become memory candidates;
- schedules/watches stop unless explicitly detached;
- temporary grants associated only with the goal expire/revoke according to policy.

## MVP vertical slice

The first end-to-end goal should be a marketplace monitor:

```text
User: Watch for product X below landed-cost threshold Y.
```

It exercises:

1. goal creation;
2. plan creation;
3. scheduled recurring research;
4. browser/public web access;
5. state across runs;
6. result comparison/novelty;
7. notification;
8. pause/cancel;
9. service restart/recovery.

Then extend the same architecture with one approval-gated action such as preparing and sending an email.

## Acceptance criteria

- multiple goals can coexist;
- background task resumes after application restart;
- scheduled task does not depend on open chat connection;
- user can inspect current plan/status;
- task can wait for approval and resume correctly;
- subagent fan-out is bounded;
- changing model does not change task schema;
- duplicate scheduler delivery does not duplicate task side effects;
- completed/cancelled goal stops its watches;
- proactive notification can be suppressed when result is not materially new.
