from __future__ import annotations

import argparse
import json
import sys

from .adapters.fake import FakeModelAdapter
from .api import serve
from .db import Database
from .harness import AgentHarness
from .repository import ControlPlaneRepository


def _repo(db_target: str) -> ControlPlaneRepository:
    return ControlPlaneRepository(Database(db_target))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="openmuse")
    parser.add_argument("--db", default="openmuse.db", help="SQLite path or PostgreSQL DSN")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate")
    api = sub.add_parser("serve")
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, default=8787)
    user = sub.add_parser("user-create")
    user.add_argument("email")
    user.add_argument("--name", default=None)
    instance = sub.add_parser("instance-create")
    instance.add_argument("user_id")
    instance.add_argument("--name", default="default")
    goal = sub.add_parser("goal-create")
    goal.add_argument("instance_id")
    goal.add_argument("title")
    goal.add_argument("--description", default="")
    demo = sub.add_parser("demo")
    demo.add_argument("instance_id")
    demo.add_argument("title")
    args = parser.parse_args(argv)
    repo = _repo(args.db)
    if args.command == "migrate":
        print(json.dumps({"ok": True, "backend": repo.db.backend, "db": args.db}))
    elif args.command == "serve":
        serve(repo, args.host, args.port)
    elif args.command == "user-create":
        print(json.dumps(repo.create_user(args.email, args.name or args.email), ensure_ascii=False))
    elif args.command == "instance-create":
        print(json.dumps(repo.create_instance(args.user_id, args.name), ensure_ascii=False))
    elif args.command == "goal-create":
        print(json.dumps(repo.create_goal(args.instance_id, args.title, args.description), ensure_ascii=False))
    elif args.command == "demo":
        goal = repo.create_goal(args.instance_id, args.title, args.title, status="active")
        task = repo.create_task(goal_id=goal["id"], title=args.title, input={"request": args.title})
        schedule = repo.create_schedule(args.instance_id, task_id=task["id"], trigger_type="one_time")
        queued = repo.deliver_schedule(schedule["id"], "cli-demo-1")
        result = AgentHarness(repo, FakeModelAdapter()).run(queued["id"])
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
