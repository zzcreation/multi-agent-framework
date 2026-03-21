#!/usr/bin/env python3
"""多 Agent 框架入口：默认以 Control Plane API 方式运行。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contracts.protocol import TaskPriority, TaskSpec
from services.control_plane_loader import build_controller


def run_api(host: str, port: int) -> int:
    app_path = ROOT / "services" / "control-plane" / "app.py"
    return subprocess.call([sys.executable, str(app_path), "--host", host, "--port", str(port)])


def cli_submit_task(task: str, priority: str = "medium") -> dict:
    controller = build_controller()
    spec = TaskSpec.new(
        title=task,
        payload={"task": task},
        priority=TaskPriority(priority),
    )
    result = controller.submit_task(spec)
    return result.to_dict()


def cli_health() -> dict:
    controller = build_controller()
    return {
        "ok": True,
        "workers": controller.registry.get_worker_snapshot(),
        "gateway": controller.router.get_remote_gateway(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="multi-agent framework")
    sub = parser.add_subparsers(dest="cmd")

    api = sub.add_parser("api", help="run control-plane http gateway")
    api.add_argument("--host", default="0.0.0.0")
    api.add_argument("--port", type=int, default=8080)

    health = sub.add_parser("health")

    exec_parser = sub.add_parser("exec")
    exec_parser.add_argument("task")
    exec_parser.add_argument("--priority", default="medium", choices=[p.value for p in TaskPriority])

    route = sub.add_parser("route")
    route.add_argument("task")

    args = parser.parse_args()

    if args.cmd == "api":
        return run_api(args.host, args.port)
    if args.cmd == "health":
        print(json.dumps(cli_health(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "exec":
        print(json.dumps(cli_submit_task(args.task, args.priority), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "route":
        controller = build_controller()
        result = controller.router.route(
            args.task,
            scheduling_input={"priority": "medium", "sla_seconds": 600, "retry_history": {"retry_count": 0}},
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
