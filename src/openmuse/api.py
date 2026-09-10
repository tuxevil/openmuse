"""Minimal stdlib HTTP API for the Phase 1 control plane."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .repository import ControlPlaneRepository, NotFoundError


class ControlPlaneHandler(BaseHTTPRequestHandler):
    repository: ControlPlaneRepository

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        value = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(value, dict):
            raise ValueError("request body must be a JSON object")
        return value

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            self._send(200, {"ok": True, "service": "openmuse-control-plane"})
            return
        if path.startswith("/executions/"):
            try:
                self._send(200, self.repository.get_execution(path.rsplit("/", 1)[-1]))
            except NotFoundError:
                self._send(404, {"error": "not_found"})
            return
        self._send(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            body = self._json()
            if path == "/users":
                result = self.repository.create_user(body["email"], body.get("display_name", body["email"]), body.get("extra"))
            elif path == "/instances":
                result = self.repository.create_instance(body["user_id"], body.get("name", "default"), body.get("config"))
            elif path == "/goals":
                result = self.repository.create_goal(body["instance_id"], body["title"], body.get("description", ""), status=body.get("status", "draft"), success_criteria=body.get("success_criteria"), constraints=body.get("constraints"), priority=int(body.get("priority", 0)), budget=body.get("budget"))
            elif path == "/tasks":
                result = self.repository.create_task(title=body["title"], task_type=body.get("type", "agent"), goal_id=body.get("goal_id"), parent_task_id=body.get("parent_task_id"), input=body.get("input"), expected_output=body.get("expected_output"), status=body.get("status", "ready"), priority=int(body.get("priority", 0)), dependency_ids=body.get("dependency_ids"), budget=body.get("budget"), retry_policy=body.get("retry_policy"))
            elif path == "/schedules":
                result = self.repository.create_schedule(body["instance_id"], task_id=body["task_id"], trigger_type=body.get("trigger_type", "one_time"), run_at=body.get("run_at"), recurrence=body.get("recurrence"), timezone=body.get("timezone", "UTC"))
            elif path.startswith("/schedules/") and path.endswith("/deliver"):
                schedule_id = path.split("/")[2]
                result = self.repository.deliver_schedule(schedule_id, body["delivery_key"], body.get("payload"))
            else:
                self._send(404, {"error": "not_found"})
                return
            self._send(201, result)
        except (KeyError, ValueError, NotFoundError) as exc:
            self._send(400, {"error": "invalid_request", "message": str(exc)})
        except Exception as exc:
            self._send(500, {"error": "internal_error", "message": str(exc)})

    def log_message(self, *_args: Any) -> None:
        return


def serve(repository: ControlPlaneRepository, host: str = "127.0.0.1", port: int = 8787) -> None:
    handler = type("OpenMuseHandler", (ControlPlaneHandler,), {"repository": repository})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"OpenMuse control plane listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
