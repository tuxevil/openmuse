from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import unittest

from openmuse.adapters.fake import FakeModelAdapter
from openmuse.adapters.openai_compatible import OpenAICompatibleAdapter
from openmuse.db import Database
from openmuse.domain import ModelMessage, ModelRequest, text_part
from openmuse.harness import AgentHarness
from openmuse.model import ModelRouter, parse_structured_text
from openmuse.repository import ControlPlaneRepository


class CompletionHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers["Content-Length"])
        request = json.loads(self.rfile.read(length))
        self.server.seen_model = request["model"]
        if request.get("stream"):
            chunks = [
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call-1", "function": {"name": "echo", "arguments": '{"text":'}}]}}]},
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": '"streamed"}'}}]}}]},
            ]
            body = b"".join(f"data: {json.dumps(chunk)}\n\n".encode() for chunk in chunks) + b"data: [DONE]\n\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        body = json.dumps({"id": "http-1", "choices": [{"message": {"role": "assistant", "content": "FAKE_OK: Execute the task"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return


class ModelContractTests(unittest.TestCase):
    def test_same_task_runs_through_fake_and_openai_compatible_backends(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), CompletionHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def run(adapter):
                repo = ControlPlaneRepository(Database())
                user = repo.create_user("x@example.com", "X")
                instance = repo.create_instance(user["id"], "local")
                goal = repo.create_goal(instance["id"], "Same", "Same", status="active")
                task = repo.create_task(goal_id=goal["id"], title="Execute")
                schedule = repo.create_schedule(instance["id"], task_id=task["id"], trigger_type="one_time")
                execution = repo.deliver_schedule(schedule["id"], "one")
                return AgentHarness(repo, adapter).run(execution["id"])

            fake = run(FakeModelAdapter())
            remote = run(OpenAICompatibleAdapter(base_url=f"http://127.0.0.1:{server.server_port}/v1", model="test-model"))
            self.assertEqual(fake["status"], remote["status"])
            self.assertEqual(fake["status"], "succeeded")
            self.assertGreater(fake["usage"]["total_tokens"], 0)
            self.assertEqual(remote["usage"]["total_tokens"], 7)
            self.assertEqual(server.seen_model, "test-model")
        finally:
            server.shutdown()
            server.server_close()


    def test_streaming_is_normalized_into_openmuse_events(self):
        adapter = FakeModelAdapter()
        request = ModelRequest("exec", "orchestrator", (ModelMessage("user", (text_part("hello"),)),))
        events = list(adapter.stream(request))
        self.assertEqual(events[0].kind, "response.started")
        self.assertTrue("".join(event.text_delta or "" for event in events if event.kind == "text.delta").startswith("FAKE_OK"))
        self.assertEqual(events[-1].kind, "response.completed")

    def test_openai_stream_accumulates_fragmented_tool_arguments(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), CompletionHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            adapter = OpenAICompatibleAdapter(base_url=f"http://127.0.0.1:{server.server_port}/v1", model="stream-model")
            request = ModelRequest("exec", "orchestrator", (ModelMessage("user", (text_part("hello"),)),))
            events = list(adapter.stream(request))
            completed = [event.tool_call for event in events if event.kind == "tool_call.completed"]
            self.assertEqual(len(completed), 1)
            self.assertEqual(completed[0].arguments, {"text": "streamed"})
        finally:
            server.shutdown()
            server.server_close()


    def test_structured_output_is_validated(self):
        schema = {"type": "object", "required": ["answer"], "properties": {"answer": {"type": "string"}}}
        self.assertEqual(parse_structured_text('{"answer":"yes"}', schema), {"answer": "yes"})
        with self.assertRaises(ValueError):
            parse_structured_text('{"other":true}', schema)


    def test_local_only_routing_does_not_fallback_to_remote(self):
        repo = ControlPlaneRepository(Database())
        user = repo.create_user("route@example.com", "Route")
        instance = repo.create_instance(user["id"], "local")
        repo.create_model_profile(instance["id"], "cloud", "orchestrator", "remote", {}, {"text": True}, max_sensitivity="private")
        router = ModelRouter(repo, {"remote": FakeModelAdapter()})
        with self.assertRaisesRegex(Exception, "no allowed model profile"):
            router.resolve(instance["id"], "orchestrator", "private", local_only=True)

    def test_harness_can_resolve_role_profile_from_durable_router(self):
        repo = ControlPlaneRepository(Database())
        user = repo.create_user("profile@example.com", "Profile")
        instance = repo.create_instance(user["id"], "local")
        repo.create_model_profile(instance["id"], "local", "orchestrator", "fake", {"local": True}, {"text": True}, max_sensitivity="private")
        goal = repo.create_goal(instance["id"], "Profile task", "Profile task", status="active")
        task = repo.create_task(goal_id=goal["id"], title="Run")
        schedule = repo.create_schedule(instance["id"], task_id=task["id"], trigger_type="one_time")
        execution = repo.deliver_schedule(schedule["id"], "profile-run")
        result = AgentHarness(repo, router=ModelRouter(repo, {"fake": FakeModelAdapter()})).run(execution["id"], local_only=True)
        self.assertEqual(result["status"], "succeeded")
