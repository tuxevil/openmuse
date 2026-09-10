-- PostgreSQL control-plane schema. IDs are application-generated opaque strings
-- so exports remain portable across installations.
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    extra JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS instances (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS instances_user_idx ON instances(user_id);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    instance_id TEXT NOT NULL REFERENCES instances(id),
    title TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'primary',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS conversations_instance_idx ON conversations(instance_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,
    content JSONB NOT NULL,
    sequence BIGINT NOT NULL,
    correlation_id TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE(conversation_id, sequence)
);

CREATE TABLE IF NOT EXISTS goals (
    id TEXT PRIMARY KEY,
    instance_id TEXT NOT NULL REFERENCES instances(id),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    success_criteria JSONB NOT NULL DEFAULT '{}'::jsonb,
    constraints JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'draft',
    priority INTEGER NOT NULL DEFAULT 0,
    plan_version INTEGER NOT NULL DEFAULT 0,
    notification_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    budget JSONB NOT NULL DEFAULT '{}'::jsonb,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    paused_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS goals_instance_status_idx ON goals(instance_id, status, priority DESC);

CREATE TABLE IF NOT EXISTS schedules (
    id TEXT PRIMARY KEY,
    instance_id TEXT NOT NULL REFERENCES instances(id),
    goal_id TEXT REFERENCES goals(id),
    task_id TEXT,
    trigger_type TEXT NOT NULL,
    run_at TIMESTAMPTZ,
    recurrence TEXT,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    status TEXT NOT NULL DEFAULT 'active',
    last_fired_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS schedules_due_idx ON schedules(status, run_at);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    goal_id TEXT REFERENCES goals(id),
    parent_task_id TEXT REFERENCES tasks(id),
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    input JSONB NOT NULL DEFAULT '{}'::jsonb,
    expected_output JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 0,
    dependency_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    schedule_id TEXT REFERENCES schedules(id),
    trigger_event_id TEXT,
    budget JSONB NOT NULL DEFAULT '{}'::jsonb,
    retry_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
    checkpoint JSONB NOT NULL DEFAULT '{}'::jsonb,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS tasks_ready_idx ON tasks(status, priority DESC, created_at);
CREATE INDEX IF NOT EXISTS tasks_goal_idx ON tasks(goal_id, status);

ALTER TABLE schedules ADD CONSTRAINT schedules_task_fk FOREIGN KEY (task_id) REFERENCES tasks(id);

CREATE TABLE IF NOT EXISTS executions (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    attempt INTEGER NOT NULL,
    runtime_id TEXT,
    model_profile TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    trigger_event_id TEXT,
    trigger_key TEXT UNIQUE,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    checkpoint_before JSONB NOT NULL DEFAULT '{}'::jsonb,
    checkpoint_after JSONB NOT NULL DEFAULT '{}'::jsonb,
    usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    error JSONB,
    correlation_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS executions_task_idx ON executions(task_id, attempt DESC);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    instance_id TEXT NOT NULL REFERENCES instances(id),
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    dedupe_key TEXT,
    goal_id TEXT REFERENCES goals(id),
    task_id TEXT REFERENCES tasks(id),
    created_at TIMESTAMPTZ NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS events_dedupe_idx ON events(instance_id, dedupe_key) WHERE dedupe_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS outbox (
    id TEXT PRIMARY KEY,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    dedupe_key TEXT UNIQUE,
    available_at TIMESTAMPTZ NOT NULL,
    claimed_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS outbox_pending_idx ON outbox(processed_at, available_at);

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    instance_id TEXT NOT NULL REFERENCES instances(id),
    goal_id TEXT REFERENCES goals(id),
    task_id TEXT REFERENCES tasks(id),
    name TEXT NOT NULL,
    media_type TEXT NOT NULL,
    storage_uri TEXT NOT NULL,
    content_hash TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    instance_id TEXT NOT NULL REFERENCES instances(id),
    actor_type TEXT NOT NULL,
    actor_id TEXT,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT,
    correlation_id TEXT,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_instance_idx ON audit_events(instance_id, created_at);

CREATE TABLE IF NOT EXISTS model_profiles (
    id TEXT PRIMARY KEY,
    instance_id TEXT NOT NULL REFERENCES instances(id),
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    adapter TEXT NOT NULL,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    capabilities JSONB NOT NULL DEFAULT '{}'::jsonb,
    max_sensitivity TEXT NOT NULL DEFAULT 'private',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    UNIQUE(instance_id, name)
);
