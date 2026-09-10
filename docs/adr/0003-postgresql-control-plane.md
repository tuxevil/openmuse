# ADR 0003: PostgreSQL as the Initial Control-Plane System of Record

- **Status:** Accepted
- **Date:** 2026-09-10

## Context

OpenMuse needs durable, transactional state for goals, tasks, executions, schedules, events, approvals, grants, model profiles, memory metadata, artifacts and audit records. The first deployment target is a single-user/local system, where operational simplicity matters.

Introducing a collection of databases, queues and vector services at the start would increase deployment and recovery complexity before the workload requires it.

## Decision

Use PostgreSQL as the initial control-plane system of record.

Where appropriate, use PostgreSQL capabilities for:

- relational domain state;
- transactions and optimistic concurrency;
- job/outbox coordination;
- full-text search;
- optional pgvector indexing;
- audit/event metadata.

Credential material remains logically and operationally separated from ordinary runtime-accessible state even if an early deployment uses the same PostgreSQL server with separate credentials/schema/database.

Large workspace/artifact bytes may live on filesystem/object storage, with metadata in PostgreSQL.

## Consequences

Positive:

- simpler local deployment;
- strong transactional semantics for task/recovery state;
- fewer moving parts;
- easy future replication/backup ecosystem;
- optional vector/full-text features without new infrastructure.

Costs:

- high-scale hosted deployment may eventually need a dedicated event bus/queue;
- large binary data should not be forced into normal rows;
- credential separation requires careful database roles/keys.

## Rejected alternative

**Start with PostgreSQL + Redis + NATS/Kafka + dedicated vector DB.** Rejected for the initial milestone because it adds operational complexity without proving a necessary workload requirement.

## Follow-up

Define an outbox/event interface so a future queue can be introduced without changing goal/task semantics. Treat embeddings as rebuildable indexes, not authoritative memory.
