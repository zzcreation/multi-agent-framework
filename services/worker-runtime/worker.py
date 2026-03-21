#!/usr/bin/env python3
"""Worker Runtime：从消息队列 pull 任务并 push 结果。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.remote_executor import MessageQueueTransportAdapter


class WorkerRuntime:
    def __init__(self, worker_id: str, capabilities: list[str]):
        self.worker_id = worker_id
        self.capabilities = capabilities
        self.mq = MessageQueueTransportAdapter()

    def run_forever(self, poll_interval: float = 1.0):
        print(f"worker-runtime [{self.worker_id}] started, capabilities={self.capabilities}")
        while True:
            task_msg = self.mq.consume(timeout=1)
            if not task_msg:
                time.sleep(poll_interval)
                continue

            task_payload = task_msg.get("task", {})
            result = {
                "success": True,
                "worker_id": self.worker_id,
                "output": {
                    "echo": task_payload,
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                },
                "method": "mq_worker_push",
            }
            self.mq.push_result(result)


if __name__ == "__main__":
    worker = WorkerRuntime(worker_id="worker-local-1", capabilities=["review", "security", "sandbox"])
    worker.run_forever()
