"""Small DB-API wrapper with PostgreSQL as the production backend.

SQLite is intentionally supported for deterministic unit/integration tests. It
is not the production control-plane backend.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "migrations"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL, extra TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS instances (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), name TEXT NOT NULL, status TEXT NOT NULL, config TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS instances_user_idx ON instances(user_id);
CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, instance_id TEXT NOT NULL REFERENCES instances(id), title TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS conversations_instance_idx ON conversations(instance_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id), role TEXT NOT NULL, content TEXT NOT NULL, sequence INTEGER NOT NULL, correlation_id TEXT, created_at TEXT NOT NULL, UNIQUE(conversation_id, sequence));
CREATE TABLE IF NOT EXISTS goals (id TEXT PRIMARY KEY, instance_id TEXT NOT NULL REFERENCES instances(id), title TEXT NOT NULL, description TEXT NOT NULL, success_criteria TEXT NOT NULL, constraints TEXT NOT NULL, status TEXT NOT NULL, priority INTEGER NOT NULL, plan_version INTEGER NOT NULL, notification_policy TEXT NOT NULL, budget TEXT NOT NULL, version INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, started_at TEXT, completed_at TEXT, paused_at TEXT);
CREATE INDEX IF NOT EXISTS goals_instance_status_idx ON goals(instance_id, status, priority DESC);
CREATE TABLE IF NOT EXISTS schedules (id TEXT PRIMARY KEY, instance_id TEXT NOT NULL REFERENCES instances(id), goal_id TEXT REFERENCES goals(id), task_id TEXT, trigger_type TEXT NOT NULL, run_at TEXT, recurrence TEXT, timezone TEXT NOT NULL, status TEXT NOT NULL, last_fired_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS schedules_due_idx ON schedules(status, run_at);
CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, goal_id TEXT REFERENCES goals(id), parent_task_id TEXT REFERENCES tasks(id), type TEXT NOT NULL, title TEXT NOT NULL, input TEXT NOT NULL, expected_output TEXT NOT NULL, status TEXT NOT NULL, priority INTEGER NOT NULL, dependency_ids TEXT NOT NULL, schedule_id TEXT REFERENCES schedules(id), trigger_event_id TEXT, budget TEXT NOT NULL, retry_policy TEXT NOT NULL, checkpoint TEXT NOT NULL, version INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, started_at TEXT, finished_at TEXT);
CREATE INDEX IF NOT EXISTS tasks_ready_idx ON tasks(status, priority DESC, created_at);
CREATE INDEX IF NOT EXISTS tasks_goal_idx ON tasks(goal_id, status);
CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, instance_id TEXT NOT NULL REFERENCES instances(id), event_type TEXT NOT NULL, source TEXT NOT NULL, provenance TEXT NOT NULL, payload TEXT NOT NULL, dedupe_key TEXT, goal_id TEXT REFERENCES goals(id), task_id TEXT REFERENCES tasks(id), created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS events_dedupe_idx ON events(instance_id, dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE TABLE IF NOT EXISTS executions (id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id), attempt INTEGER NOT NULL, runtime_id TEXT, model_profile TEXT NOT NULL, status TEXT NOT NULL, trigger_event_id TEXT REFERENCES events(id), trigger_key TEXT UNIQUE, started_at TEXT, ended_at TEXT, checkpoint_before TEXT NOT NULL, checkpoint_after TEXT NOT NULL, usage TEXT NOT NULL, error TEXT, correlation_id TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS executions_task_idx ON executions(task_id, attempt DESC);
CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, aggregate_type TEXT NOT NULL, aggregate_id TEXT NOT NULL, event_type TEXT NOT NULL, payload TEXT NOT NULL, dedupe_key TEXT UNIQUE, available_at TEXT NOT NULL, claimed_at TEXT, processed_at TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS outbox_pending_idx ON outbox(processed_at, available_at);
CREATE TABLE IF NOT EXISTS artifacts (id TEXT PRIMARY KEY, instance_id TEXT NOT NULL REFERENCES instances(id), goal_id TEXT REFERENCES goals(id), task_id TEXT REFERENCES tasks(id), name TEXT NOT NULL, media_type TEXT NOT NULL, storage_uri TEXT NOT NULL, content_hash TEXT, metadata TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_events (id TEXT PRIMARY KEY, instance_id TEXT NOT NULL REFERENCES instances(id), actor_type TEXT NOT NULL, actor_id TEXT, action TEXT NOT NULL, target_type TEXT NOT NULL, target_id TEXT, correlation_id TEXT, data TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS audit_instance_idx ON audit_events(instance_id, created_at);
CREATE TABLE IF NOT EXISTS model_profiles (id TEXT PRIMARY KEY, instance_id TEXT NOT NULL REFERENCES instances(id), name TEXT NOT NULL, role TEXT NOT NULL, adapter TEXT NOT NULL, config TEXT NOT NULL, capabilities TEXT NOT NULL, max_sensitivity TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(instance_id, name));
"""


class Database:
    def __init__(self, target: str = ":memory:") -> None:
        self.target = target
        self.backend = "postgres" if target.startswith(("postgres://", "postgresql://")) else "sqlite"
        self.connection: Any | None = None

    def connect(self) -> "Database":
        if self.connection is not None:
            return self
        if self.backend == "postgres":
            try:
                import psycopg
            except ImportError as exc:
                raise RuntimeError("PostgreSQL requires the optional dependency: pip install 'openmuse[postgres]'") from exc
            self.connection = psycopg.connect(self.target)
        else:
            self.connection = sqlite3.connect(self.target, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys = ON")
        return self

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def _placeholder_sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.backend == "postgres" else sql

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        if self.connection is None:
            self.connect()
        return self.connection.execute(self._placeholder_sql(sql), params)

    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        cursor = self.execute(sql, params)
        row = cursor.fetchone()
        if row is None:
            return None
        if isinstance(row, sqlite3.Row):
            return dict(row)
        return {desc[0]: value for desc, value in zip(cursor.description, row)}

    def query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        cursor = self.execute(sql, params)
        rows = cursor.fetchall()
        if isinstance(rows, list) and rows and isinstance(rows[0], sqlite3.Row):
            return [dict(row) for row in rows]
        return [{desc[0]: value for desc, value in zip(cursor.description, row)} for row in rows]

    @contextmanager
    def transaction(self) -> Iterator["Database"]:
        if self.connection is None:
            self.connect()
        try:
            yield self
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def migrate(self) -> None:
        self.connect()
        if self.backend == "sqlite":
            self.connection.executescript(SQLITE_SCHEMA)
            self.connection.commit()
            return
        for path in sorted(MIGRATIONS.glob("*.sql")):
            version = path.name
            if self.query_one("SELECT version FROM schema_migrations WHERE version = ?", (version,)):
                continue
            self.connection.execute(path.read_text(encoding="utf-8"))
            self.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)", (version, utc_now()))
            self.connection.commit()
