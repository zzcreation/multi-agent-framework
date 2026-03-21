from __future__ import annotations

from typing import Dict

from scripts.remote_executor import RemoteExecutor
from services.control_plane.task_protocol import TaskEnvelope


class WorkerRuntime:
    """Data Plane: worker 执行面。"""

    def __init__(self):
        self.executor = RemoteExecutor()

    def execute(self, worker_id: str, envelope: TaskEnvelope, agent_type: str) -> Dict:
        task = envelope.payload.get("task", "")
        result = self.executor.execute_task(task, agent_type=agent_type, prefer_api=True)
        return {
            "worker_id": worker_id,
            "task_id": envelope.task_id,
            "trace_id": envelope.trace_id,
            "result": result,
        }
