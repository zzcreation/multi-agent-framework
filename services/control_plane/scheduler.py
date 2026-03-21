from __future__ import annotations

import heapq
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from services.control_plane.registry import WorkerNode, WorkerRegistry
from services.control_plane.task_protocol import TaskEnvelope


@dataclass(order=True)
class QueueItem:
    priority: int
    created_at: float
    task: TaskEnvelope = field(compare=False)


class Scheduler:
    """支持优先级队列、延迟队列、抢占和负载感知路由。"""

    def __init__(self, registry: WorkerRegistry):
        self.registry = registry
        self._priority_queue: List[QueueItem] = []
        self._delayed_queue: List[Tuple[float, TaskEnvelope]] = []
        self._running_by_worker: Dict[str, TaskEnvelope] = {}

    def submit(self, envelope: TaskEnvelope, delay_seconds: int = 0) -> None:
        if delay_seconds > 0:
            heapq.heappush(self._delayed_queue, (time.time() + delay_seconds, envelope))
            return
        heapq.heappush(self._priority_queue, QueueItem(priority=envelope.priority, created_at=time.time(), task=envelope))

    def promote_delayed(self) -> None:
        now = time.time()
        while self._delayed_queue and self._delayed_queue[0][0] <= now:
            _, task = heapq.heappop(self._delayed_queue)
            heapq.heappush(self._priority_queue, QueueItem(priority=task.priority, created_at=time.time(), task=task))

    def has_pending(self) -> bool:
        self.promote_delayed()
        return bool(self._priority_queue)

    def next_task(self) -> Optional[TaskEnvelope]:
        self.promote_delayed()
        if not self._priority_queue:
            return None
        return heapq.heappop(self._priority_queue).task

    def route(self, envelope: TaskEnvelope) -> Optional[WorkerNode]:
        candidates = self.registry.list_alive()
        if not candidates:
            return None

        review_capability = envelope.payload.get("required_review")
        sandbox_capability = envelope.payload.get("required_sandbox")
        toolset = envelope.payload.get("required_toolset")

        def capable(worker: WorkerNode) -> bool:
            if review_capability and worker.capabilities.get("review") != "true":
                return False
            if sandbox_capability and worker.capabilities.get("sandbox") != "true":
                return False
            if toolset and worker.capabilities.get("toolset") != toolset:
                return False
            if not worker.model_available:
                return False
            return True

        filtered = [w for w in candidates if capable(w)]
        if not filtered:
            return None

        # 负载感知: CPU + 内存 + 队列深度（越低越好）
        return min(filtered, key=lambda w: (w.cpu_usage * 0.4 + w.memory_usage * 0.3 + w.queue_depth * 10 * 0.3))

    def maybe_preempt(self, worker_id: str, incoming: TaskEnvelope) -> bool:
        """抢占策略：高优先级(数值更小)可抢占当前低优任务。"""
        running = self._running_by_worker.get(worker_id)
        if running and incoming.priority < running.priority:
            self.submit(running, delay_seconds=1)
            self._running_by_worker[worker_id] = incoming
            return True
        return False

    def mark_running(self, worker_id: str, envelope: TaskEnvelope) -> None:
        self._running_by_worker[worker_id] = envelope

    def mark_done(self, worker_id: str) -> None:
        self._running_by_worker.pop(worker_id, None)

    @staticmethod
    def is_expired(envelope: TaskEnvelope) -> bool:
        return datetime.fromisoformat(envelope.deadline) < datetime.utcnow()
