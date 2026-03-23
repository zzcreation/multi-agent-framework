from __future__ import annotations

from typing import Dict

from scripts.task_router import TaskRouter
from services.control_plane.registry import WorkerRegistry
from services.control_plane.saga import SagaManager
from services.control_plane.scheduler import Scheduler
from services.control_plane.task_protocol import TaskEnvelope
from services.worker_runtime.runtime import WorkerRuntime


class ControlPlane:
    """Control Plane: 任务接入、路由、调度、策略。"""

    def __init__(self):
        self.router = TaskRouter()
        self.registry = WorkerRegistry()
        self.scheduler = Scheduler(self.registry)
        self.saga = SagaManager()
        self.runtime = WorkerRuntime()
        self._register_default_compensation()

    def _register_default_compensation(self) -> None:
        self.saga.register_compensation("generic", lambda envelope: {
            "compensated": True,
            "action": "log_and_drop",
            "task_id": envelope.task_id,
        })

    def worker_heartbeat(self, worker_id: str, capabilities: Dict[str, str], cpu_usage: float = 0,
                         memory_usage: float = 0, queue_depth: int = 0, model_available: bool = True) -> Dict:
        worker = self.registry.heartbeat(
            worker_id=worker_id,
            capabilities=capabilities,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            queue_depth=queue_depth,
            model_available=model_available,
        )
        return {"worker_id": worker.worker_id, "status": "alive", "capabilities": worker.capabilities}

    def submit_task(self, envelope: TaskEnvelope, delay_seconds: int = 0) -> Dict:
        self.saga.transition(envelope, "NEW", "QUEUED")
        self.scheduler.submit(envelope, delay_seconds=delay_seconds)
        return {"accepted": True, "task": envelope.to_dict(), "delay_seconds": delay_seconds}

    def dispatch_once(self) -> Dict:
        task = self.scheduler.next_task()
        if not task:
            return {"dispatched": False, "reason": "queue_empty"}
        if self.scheduler.is_expired(task):
            self.saga.transition(task, "QUEUED", "EXPIRED")
            return {"dispatched": False, "reason": "expired", "task_id": task.task_id}

        worker = self.scheduler.route(task)
        if not worker:
            self.scheduler.submit(task, delay_seconds=2)
            return {"dispatched": False, "reason": "no_worker_matched", "task_id": task.task_id}

        self.saga.transition(task, "QUEUED", "DISPATCHED", detail=f"worker={worker.worker_id}")
        self.scheduler.mark_running(worker.worker_id, task)

        route_result = self.router.route(task.payload.get("task", ""))
        agent_type = route_result.get("target", "assistant")
        preempted = self.scheduler.maybe_preempt(worker.worker_id, task)

        try:
            execution = self.runtime.execute(worker.worker_id, task, agent_type)
            success = execution.get("result", {}).get("success", False)
            if success:
                self.saga.transition(task, "DISPATCHED", "SUCCEEDED")
            else:
                self.saga.transition(task, "DISPATCHED", "FAILED", detail=str(execution.get("result")))
                compensation = self.saga.compensate(task)
                execution["compensation"] = compensation
            execution["preempted"] = preempted
            return execution
        finally:
            self.scheduler.mark_done(worker.worker_id)

    def transition_logs(self):
        return self.saga.get_transition_log()
