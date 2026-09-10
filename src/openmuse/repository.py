"""Transactional repositories for Phase 1 control-plane state."""

from __future__ import annotations

import json
from typing import Any

from .db import Database, utc_now
from .domain import new_id, json_text


class ConflictError(RuntimeError):
    """Optimistic-concurrency or deduplication conflict."""


class NotFoundError(KeyError):
    pass


class ControlPlaneRepository:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.db.migrate()

    @staticmethod
    def _payload(value: Any) -> str:
        return json_text(value if value is not None else {})

    def create_user(self, email: str, display_name: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        now = utc_now()
        row = {"id": new_id("usr"), "email": email, "display_name": display_name, "extra": extra or {}, "created_at": now, "updated_at": now}
        with self.db.transaction():
            self.db.execute("INSERT INTO users(id,email,display_name,extra,created_at,updated_at) VALUES (?,?,?,?,?,?)", (row["id"], email, display_name, self._payload(row["extra"]), now, now))
        return row

    def create_instance(self, user_id: str, name: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
        self.require("users", user_id)
        now = utc_now()
        row = {"id": new_id("ins"), "user_id": user_id, "name": name, "status": "active", "config": config or {}, "created_at": now, "updated_at": now}
        with self.db.transaction():
            self.db.execute("INSERT INTO instances(id,user_id,name,status,config,created_at,updated_at) VALUES (?,?,?,?,?,?,?)", (row["id"], user_id, name, row["status"], self._payload(row["config"]), now, now))
        return row

    def create_conversation(self, instance_id: str, title: str = "Main", kind: str = "primary") -> dict[str, Any]:
        self.require("instances", instance_id)
        now = utc_now()
        row = {"id": new_id("cnv"), "instance_id": instance_id, "title": title, "kind": kind, "status": "active", "created_at": now, "updated_at": now}
        with self.db.transaction():
            self.db.execute("INSERT INTO conversations(id,instance_id,title,kind,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)", (row["id"], instance_id, title, kind, row["status"], now, now))
        return row

    def append_message(self, conversation_id: str, role: str, content: Any, correlation_id: str | None = None) -> dict[str, Any]:
        self.require("conversations", conversation_id)
        now = utc_now()
        with self.db.transaction():
            seq_row = self.db.query_one("SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence FROM messages WHERE conversation_id = ?", (conversation_id,))
            sequence = int(seq_row["next_sequence"])
            row = {"id": new_id("msg"), "conversation_id": conversation_id, "role": role, "content": content, "sequence": sequence, "correlation_id": correlation_id, "created_at": now}
            self.db.execute("INSERT INTO messages(id,conversation_id,role,content,sequence,correlation_id,created_at) VALUES (?,?,?,?,?,?,?)", (row["id"], conversation_id, role, self._payload(content), sequence, correlation_id, now))
            self.db.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
        return row

    def list_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        rows = self.db.query_all("SELECT * FROM messages WHERE conversation_id = ? ORDER BY sequence", (conversation_id,))
        for row in rows:
            row["content"] = json.loads(row["content"])
        return rows

    def create_goal(self, instance_id: str, title: str, description: str, *, status: str = "draft", success_criteria: dict[str, Any] | None = None, constraints: dict[str, Any] | None = None, priority: int = 0, budget: dict[str, Any] | None = None) -> dict[str, Any]:
        self.require("instances", instance_id)
        now = utc_now()
        row = {"id": new_id("goal"), "instance_id": instance_id, "title": title, "description": description, "success_criteria": success_criteria or {}, "constraints": constraints or {}, "status": status, "priority": priority, "plan_version": 0, "notification_policy": {}, "budget": budget or {}, "version": 1, "created_at": now, "updated_at": now, "started_at": None, "completed_at": None, "paused_at": None}
        with self.db.transaction():
            self.db.execute("INSERT INTO goals(id,instance_id,title,description,success_criteria,constraints,status,priority,plan_version,notification_policy,budget,version,created_at,updated_at,started_at,completed_at,paused_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (row["id"], instance_id, title, description, self._payload(row["success_criteria"]), self._payload(row["constraints"]), status, priority, 0, self._payload({}), self._payload(row["budget"]), 1, now, now, None, None, None))
            self._audit_in_tx(instance_id, "system", "control-plane", "goal.created", "goal", row["id"], row["id"], {})
            self._outbox_in_tx("goal", row["id"], "goal.created", {"goal_id": row["id"]}, f"goal.created:{row['id']}")
        return row

    def update_goal_status(self, goal_id: str, status: str) -> dict[str, Any]:
        old = self.require("goals", goal_id)
        now = utc_now()
        started = old["started_at"] or (now if status == "active" else None)
        completed = now if status in {"completed", "cancelled", "failed"} else old["completed_at"]
        with self.db.transaction():
            result = self.db.execute("UPDATE goals SET status = ?, started_at = ?, completed_at = ?, updated_at = ?, version = version + 1 WHERE id = ? AND version = ?", (status, started, completed, now, goal_id, old["version"]))
            if result.rowcount != 1:
                raise ConflictError(f"goal changed concurrently: {goal_id}")
            self._audit_in_tx(old["instance_id"], "system", "control-plane", "goal.status_changed", "goal", goal_id, goal_id, {"from": old["status"], "to": status})
        return self.require("goals", goal_id)

    def create_task(self, *, title: str, task_type: str = "agent", goal_id: str | None = None, parent_task_id: str | None = None, input: dict[str, Any] | None = None, expected_output: dict[str, Any] | None = None, status: str = "ready", priority: int = 0, dependency_ids: list[str] | None = None, budget: dict[str, Any] | None = None, retry_policy: dict[str, Any] | None = None) -> dict[str, Any]:
        instance_id = None
        if goal_id:
            goal = self.require("goals", goal_id)
            instance_id = goal["instance_id"]
        elif parent_task_id:
            parent = self.require("tasks", parent_task_id)
            if parent["goal_id"]:
                instance_id = self.require("goals", parent["goal_id"])["instance_id"]
        if instance_id is None:
            raise ValueError("a task must belong to a goal or parent task in Phase 1")
        now = utc_now()
        row = {"id": new_id("task"), "goal_id": goal_id, "parent_task_id": parent_task_id, "type": task_type, "title": title, "input": input or {}, "expected_output": expected_output or {}, "status": status, "priority": priority, "dependency_ids": dependency_ids or [], "schedule_id": None, "trigger_event_id": None, "budget": budget or {}, "retry_policy": retry_policy or {}, "checkpoint": {}, "version": 1, "created_at": now, "updated_at": now, "started_at": None, "finished_at": None}
        with self.db.transaction():
            self.db.execute("INSERT INTO tasks(id,goal_id,parent_task_id,type,title,input,expected_output,status,priority,dependency_ids,schedule_id,trigger_event_id,budget,retry_policy,checkpoint,version,created_at,updated_at,started_at,finished_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (row["id"], goal_id, parent_task_id, task_type, title, self._payload(row["input"]), self._payload(row["expected_output"]), status, priority, self._payload(row["dependency_ids"]), None, None, self._payload(row["budget"]), self._payload(row["retry_policy"]), self._payload({}), 1, now, now, None, None))
            self._audit_in_tx(instance_id, "system", "control-plane", "task.created", "task", row["id"], row["id"], {"goal_id": goal_id})
            self._outbox_in_tx("task", row["id"], "task.created", {"task_id": row["id"], "goal_id": goal_id}, f"task.created:{row['id']}")
        return row

    def create_schedule(self, instance_id: str, *, task_id: str, trigger_type: str, run_at: str | None = None, recurrence: str | None = None, timezone: str = "UTC") -> dict[str, Any]:
        self.require("instances", instance_id)
        task = self.require("tasks", task_id)
        if task["goal_id"] and self.require("goals", task["goal_id"])["instance_id"] != instance_id:
            raise ValueError("task and schedule must belong to the same instance")
        now = utc_now()
        row = {"id": new_id("sch"), "instance_id": instance_id, "goal_id": task["goal_id"], "task_id": task_id, "trigger_type": trigger_type, "run_at": run_at, "recurrence": recurrence, "timezone": timezone, "status": "active", "last_fired_at": None, "created_at": now, "updated_at": now}
        with self.db.transaction():
            self.db.execute("INSERT INTO schedules(id,instance_id,goal_id,task_id,trigger_type,run_at,recurrence,timezone,status,last_fired_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (row["id"], instance_id, row["goal_id"], task_id, trigger_type, run_at, recurrence, timezone, "active", None, now, now))
            self.db.execute("UPDATE tasks SET schedule_id = ?, updated_at = ? WHERE id = ?", (row["id"], now, task_id))
        return row

    def deliver_schedule(self, schedule_id: str, delivery_key: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Atomically deduplicate a scheduler delivery and enqueue one execution."""
        schedule = self.require("schedules", schedule_id)
        if schedule["status"] != "active":
            raise ConflictError(f"schedule is not active: {schedule_id}")
        task = self.require("tasks", schedule["task_id"])
        now = utc_now()
        execution_trigger_key = f"{schedule['instance_id']}:{delivery_key}"
        with self.db.transaction():
            event_id = new_id("evt")
            try:
                self.db.execute("INSERT INTO events(id,instance_id,event_type,source,provenance,payload,dedupe_key,goal_id,task_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (event_id, schedule["instance_id"], "schedule.fired", "scheduler", self._payload({"delivery_key": delivery_key}), self._payload(payload or {}), delivery_key, schedule["goal_id"], task["id"], now))
                event_created = True
            except Exception as exc:
                if "unique" not in str(exc).lower() and "constraint" not in str(exc).lower():
                    raise
                event = self.db.query_one("SELECT * FROM events WHERE instance_id = ? AND dedupe_key = ?", (schedule["instance_id"], delivery_key))
                if event is None:
                    raise
                event_id = event["id"]
                event_created = False
            if not event_created:
                existing = self.db.query_one("SELECT * FROM executions WHERE trigger_key = ?", (execution_trigger_key,))
                if existing:
                    return self.get_execution(existing["id"])
            attempt_row = self.db.query_one("SELECT COALESCE(MAX(attempt),0)+1 AS next_attempt FROM executions WHERE task_id = ?", (task["id"],))
            execution_id = new_id("exec")
            correlation_id = new_id("corr")
            self.db.execute("INSERT INTO executions(id,task_id,attempt,runtime_id,model_profile,status,trigger_event_id,trigger_key,checkpoint_before,checkpoint_after,usage,error,correlation_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (execution_id, task["id"], int(attempt_row["next_attempt"]), None, "default", "queued", event_id, execution_trigger_key, task["checkpoint"] if isinstance(task["checkpoint"], str) else self._payload(task["checkpoint"]), self._payload({}), self._payload({}), None, correlation_id, now))
            self.db.execute("UPDATE schedules SET last_fired_at = ?, updated_at = ? WHERE id = ?", (now, now, schedule_id))
            self._audit_in_tx(schedule["instance_id"], "scheduler", "scheduler", "execution.queued", "execution", execution_id, correlation_id, {"task_id": task["id"], "schedule_id": schedule_id, "delivery_key": delivery_key})
        return self.get_execution(execution_id)

    def claim_execution(self, execution_id: str) -> dict[str, Any]:
        execution = self.require("executions", execution_id)
        now = utc_now()
        with self.db.transaction():
            result = self.db.execute("UPDATE executions SET status = ?, started_at = ? WHERE id = ? AND status = ?", ("running", now, execution_id, "queued"))
            if result.rowcount != 1:
                raise ConflictError(f"execution is already claimed or finished: {execution_id}")
            task = self.require("tasks", execution["task_id"])
            self.db.execute("UPDATE tasks SET status = ?, started_at = COALESCE(started_at, ?), updated_at = ?, version = version + 1 WHERE id = ?", ("running", now, now, task["id"]))
        return self.get_execution(execution_id)

    def finish_execution(self, execution_id: str, *, status: str, checkpoint: dict[str, Any] | None = None, usage: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> dict[str, Any]:
        execution = self.require("executions", execution_id)
        if status not in {"succeeded", "failed", "cancelled"}:
            raise ValueError(f"invalid terminal execution status: {status}")
        now = utc_now()
        with self.db.transaction():
            result = self.db.execute("UPDATE executions SET status = ?, ended_at = ?, checkpoint_after = ?, usage = ?, error = ? WHERE id = ? AND status = ?", (status, now, self._payload(checkpoint or {}), self._payload(usage or {}), self._payload(error) if error else None, execution_id, "running"))
            if result.rowcount != 1:
                raise ConflictError(f"execution is not running: {execution_id}")
            task_status = "succeeded" if status == "succeeded" else ("cancelled" if status == "cancelled" else "failed")
            self.db.execute("UPDATE tasks SET status = ?, checkpoint = ?, finished_at = ?, updated_at = ?, version = version + 1 WHERE id = ?", (task_status, self._payload(checkpoint or {}), now, now, execution["task_id"]))
            task = self.require("tasks", execution["task_id"])
            instance_id = self.require("goals", task["goal_id"])["instance_id"] if task["goal_id"] else None
            if instance_id:
                self._audit_in_tx(instance_id, "orchestrator", "agent", f"execution.{status}", "execution", execution_id, execution["correlation_id"], {"task_id": execution["task_id"]})
        return self.get_execution(execution_id)

    def checkpoint_execution(self, execution_id: str, checkpoint: dict[str, Any]) -> None:
        """Persist an intermediate harness checkpoint for restart recovery."""
        execution = self.require("executions", execution_id)
        now = utc_now()
        with self.db.transaction():
            result = self.db.execute("UPDATE executions SET checkpoint_after = ? WHERE id = ? AND status = ?", (self._payload(checkpoint), execution_id, "running"))
            if result.rowcount != 1:
                raise ConflictError(f"execution is not running: {execution_id}")
            self.db.execute("UPDATE tasks SET checkpoint = ?, updated_at = ?, version = version + 1 WHERE id = ?", (self._payload(checkpoint), now, execution["task_id"]))

    def add_artifact(self, instance_id: str, name: str, media_type: str, storage_uri: str, *, goal_id: str | None = None, task_id: str | None = None, content_hash: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.require("instances", instance_id)
        now = utc_now()
        row = {"id": new_id("art"), "instance_id": instance_id, "goal_id": goal_id, "task_id": task_id, "name": name, "media_type": media_type, "storage_uri": storage_uri, "content_hash": content_hash, "metadata": metadata or {}, "created_at": now}
        with self.db.transaction():
            self.db.execute("INSERT INTO artifacts(id,instance_id,goal_id,task_id,name,media_type,storage_uri,content_hash,metadata,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (row["id"], instance_id, goal_id, task_id, name, media_type, storage_uri, content_hash, self._payload(row["metadata"]), now))
        return row

    def create_model_profile(self, instance_id: str, name: str, role: str, adapter: str, config: dict[str, Any], capabilities: dict[str, Any], max_sensitivity: str = "private") -> dict[str, Any]:
        self.require("instances", instance_id)
        now = utc_now()
        row = {"id": new_id("mdl"), "instance_id": instance_id, "name": name, "role": role, "adapter": adapter, "config": config, "capabilities": capabilities, "max_sensitivity": max_sensitivity, "status": "active", "created_at": now, "updated_at": now}
        with self.db.transaction():
            self.db.execute("INSERT INTO model_profiles(id,instance_id,name,role,adapter,config,capabilities,max_sensitivity,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (row["id"], instance_id, name, role, adapter, self._payload(config), self._payload(capabilities), max_sensitivity, "active", now, now))
        return row

    def get_model_profile(self, instance_id: str, name: str) -> dict[str, Any]:
        row = self.db.query_one("SELECT * FROM model_profiles WHERE instance_id = ? AND name = ? AND status = 'active'", (instance_id, name))
        if not row:
            raise NotFoundError(f"model profile: {instance_id}/{name}")
        for key in ("config", "capabilities"):
            row[key] = json.loads(row[key])
        return row

    def list_model_profiles(self, instance_id: str) -> list[dict[str, Any]]:
        rows = self.db.query_all("SELECT * FROM model_profiles WHERE instance_id = ? ORDER BY name", (instance_id,))
        for row in rows:
            row["config"] = json.loads(row["config"])
            row["capabilities"] = json.loads(row["capabilities"])
        return rows

    def get_execution(self, execution_id: str) -> dict[str, Any]:
        row = self.require("executions", execution_id)
        for key in ("checkpoint_before", "checkpoint_after", "usage", "error"):
            if isinstance(row[key], str):
                row[key] = json.loads(row[key])
        return row

    def get_task(self, task_id: str) -> dict[str, Any]:
        row = self.require("tasks", task_id)
        for key in ("input", "expected_output", "dependency_ids", "budget", "retry_policy", "checkpoint"):
            row[key] = json.loads(row[key]) if isinstance(row[key], str) else row[key]
        return row

    def build_task_context_rows(self, task_id: str) -> dict[str, Any]:
        task = self.get_task(task_id)
        goal = self.require("goals", task["goal_id"]) if task["goal_id"] else None
        if goal:
            for key in ("success_criteria", "constraints", "notification_policy", "budget"):
                goal[key] = json.loads(goal[key]) if isinstance(goal[key], str) else goal[key]
        executions = self.db.query_all("SELECT id,attempt,status,checkpoint_before,checkpoint_after,usage,error,created_at,ended_at FROM executions WHERE task_id = ? ORDER BY attempt", (task_id,))
        for row in executions:
            for key in ("checkpoint_before", "checkpoint_after", "usage", "error"):
                if isinstance(row[key], str):
                    row[key] = json.loads(row[key])
        return {"task": task, "goal": goal, "executions": executions}

    def audit_events(self, instance_id: str) -> list[dict[str, Any]]:
        rows = self.db.query_all("SELECT * FROM audit_events WHERE instance_id = ? ORDER BY created_at, id", (instance_id,))
        for row in rows:
            row["data"] = json.loads(row["data"])
        return rows

    def outbox_events(self) -> list[dict[str, Any]]:
        rows = self.db.query_all("SELECT * FROM outbox ORDER BY created_at, id")
        for row in rows:
            row["payload"] = json.loads(row["payload"])
        return rows

    def require(self, table: str, row_id: str) -> dict[str, Any]:
        if table not in {"users", "instances", "conversations", "goals", "tasks", "schedules", "executions"}:
            raise ValueError(f"unsupported table: {table}")
        row = self.db.query_one(f"SELECT * FROM {table} WHERE id = ?", (row_id,))
        if not row:
            raise NotFoundError(f"{table}: {row_id}")
        return row

    def _audit_in_tx(self, instance_id: str, actor_type: str, actor_id: str, action: str, target_type: str, target_id: str, correlation_id: str | None, data: dict[str, Any]) -> None:
        self.db.execute("INSERT INTO audit_events(id,instance_id,actor_type,actor_id,action,target_type,target_id,correlation_id,data,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (new_id("audit"), instance_id, actor_type, actor_id, action, target_type, target_id, correlation_id, self._payload(data), utc_now()))

    def _outbox_in_tx(self, aggregate_type: str, aggregate_id: str, event_type: str, payload: dict[str, Any], dedupe_key: str) -> None:
        self.db.execute("INSERT INTO outbox(id,aggregate_type,aggregate_id,event_type,payload,dedupe_key,available_at,claimed_at,processed_at,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (new_id("out"), aggregate_type, aggregate_id, event_type, self._payload(payload), dedupe_key, utc_now(), None, None, utc_now()))

    @staticmethod
    def _execution_row(row: dict[str, Any]) -> dict[str, Any]:
        return row
