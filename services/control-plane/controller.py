#!/usr/bin/env python3
"""Control Plane 编排核心。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from contracts.protocol import Heartbeat, TaskResult, TaskSpec, WorkerRegistration
from scripts.remote_executor import RemoteExecutor
from scripts.task_router import TaskRouter
from registry import WorkerRegistry


class ControlPlaneController:
    def __init__(self):
        self.router = TaskRouter()
        self.executor = RemoteExecutor()
        self.registry = WorkerRegistry(lease_ttl_seconds=30)

    def submit_task(self, spec: TaskSpec, force_target: Optional[str] = None) -> TaskResult:
        workers = self.registry.get_worker_snapshot()
        route = self.router.route(
            spec.title,
            scheduling_input={
                "worker_loads": workers,
                "priority": spec.priority.value,
                "sla_seconds": spec.sla_seconds,
                "retry_history": {"retry_count": spec.retry_count},
            },
        )
        target = force_target or route["target"]

        execution = self.executor.execute_task_contract(
            spec=spec,
            agent_type=target if target != "local" else "assistant",
            prefer_transport="auto",
        )
        return TaskResult(
            task_id=spec.task_id,
            success=execution.get("success", False),
            output=execution,
            error=execution.get("error"),
            worker_id=target,
        )

    def register_worker(self, payload: Dict[str, Any]) -> dict:
        registration = WorkerRegistration(
            worker_id=payload["worker_id"],
            endpoint=payload.get("endpoint", ""),
            capabilities=payload.get("capabilities", []),
        )
        lease = self.registry.register(registration)
        return {"success": True, "lease": lease.to_dict()}

    def receive_heartbeat(self, payload: Dict[str, Any]) -> dict:
        heartbeat = Heartbeat(
            worker_id=payload["worker_id"],
            load=float(payload.get("load", 0.0)),
            queue_depth=int(payload.get("queue_depth", 0)),
            capabilities=payload.get("capabilities", []),
        )
        lease = self.registry.heartbeat(heartbeat)
        if not lease:
            return {"success": False, "error": "worker not registered"}
        return {"success": True, "lease": lease.to_dict()}
