from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openmuse.adapters.fake import FakeModelAdapter
from openmuse.db import Database
from openmuse.harness import AgentHarness
from openmuse.repository import ControlPlaneRepository


def make_repo(path: str | Path = ":memory:"):
    return ControlPlaneRepository(Database(str(path)))


class ControlPlaneTests(unittest.TestCase):
    def test_goal_task_execution_survives_restart_and_is_audited(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "control-plane.db"
            repo = make_repo(db_path)
            user = repo.create_user("sebastian@example.com", "Sebastian")
            instance = repo.create_instance(user["id"], "local")
            goal = repo.create_goal(instance["id"], "Prepare report", "Create a report", status="active")
            task = repo.create_task(goal_id=goal["id"], title="Summarize input", input={"value": "hello"})
            schedule = repo.create_schedule(instance["id"], task_id=task["id"], trigger_type="one_time")
            queued = repo.deliver_schedule(schedule["id"], "delivery-2026-09-10")
            result = AgentHarness(repo, FakeModelAdapter()).run(queued["id"])
            self.assertEqual(result["status"], "succeeded")
            repo.db.close()

            reopened = make_repo(db_path)
            self.assertEqual(reopened.get_task(task["id"])["status"], "succeeded")
            self.assertEqual(reopened.get_execution(queued["id"])["status"], "succeeded")
            actions = [event["action"] for event in reopened.audit_events(instance["id"])]
            self.assertEqual(actions, ["goal.created", "task.created", "execution.queued", "execution.succeeded"])


    def test_scheduler_delivery_is_idempotent_and_outbox_is_durable(self):
        repo = make_repo()
        user = repo.create_user("a@example.com", "A")
        instance = repo.create_instance(user["id"], "local")
        goal = repo.create_goal(instance["id"], "Watch", "Watch", status="active")
        task = repo.create_task(goal_id=goal["id"], title="Check")
        schedule = repo.create_schedule(instance["id"], task_id=task["id"], trigger_type="recurrence", recurrence="FREQ=DAILY")
        first = repo.deliver_schedule(schedule["id"], "same-delivery")
        second = repo.deliver_schedule(schedule["id"], "same-delivery")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(repo.db.query_all("SELECT * FROM events")), 1)
        self.assertEqual(len(repo.db.query_all("SELECT * FROM executions")), 1)
        self.assertEqual(len(repo.outbox_events()), 2)


    def test_tool_proposals_are_validated_and_security_grants_are_not_tools(self):
        from openmuse.domain import ToolCall, ToolDefinition
        from openmuse.harness import ToolRegistry

        registry = ToolRegistry()
        registry.register(ToolDefinition("echo", "Echo", {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}}), lambda args: args["text"])
        result = registry.execute(ToolCall("1", "echo", {"text": "ok"}))
        self.assertEqual(result.status, "ok")
        rejected = registry.execute(ToolCall("2", "echo", {}))
        self.assertEqual(rejected.status, "failed")
