#!/usr/bin/env python3
"""Control Plane HTTP Gateway（可配合 gRPC service 使用）。"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contracts.protocol import TaskPriority, TaskSpec
from services.control_plane_loader import build_controller


controller = build_controller()


class ControlPlaneHandler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/healthz":
            self._json(200, {"ok": True, "workers": controller.registry.get_worker_snapshot()})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")

        if self.path == "/v1/tasks/submit":
            spec = TaskSpec.new(
                title=payload.get("title", "untitled"),
                payload=payload.get("payload", {}),
                priority=TaskPriority(payload.get("priority", "medium")),
                sla_seconds=int(payload.get("sla_seconds", 600)),
                target_capability=payload.get("target_capability"),
                retry_count=int(payload.get("retry_count", 0)),
                tags=payload.get("tags", []),
            )
            result = controller.submit_task(spec)
            self._json(200, result.to_dict())
            return

        if self.path == "/v1/workers/register":
            self._json(200, controller.register_worker(payload))
            return

        if self.path == "/v1/workers/heartbeat":
            self._json(200, controller.receive_heartbeat(payload))
            return

        self._json(404, {"error": "not found"})


def run(host: str = "0.0.0.0", port: int = 8080):
    server = HTTPServer((host, port), ControlPlaneHandler)
    print(f"control-plane gateway listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", default=8080, type=int)
    args = parser.parse_args()
    run(args.host, args.port)
