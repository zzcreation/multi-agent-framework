from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional


@dataclass
class WorkerNode:
    worker_id: str
    capabilities: Dict[str, str]
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    queue_depth: int = 0
    model_available: bool = True
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)

    def is_alive(self, ttl_seconds: int = 30) -> bool:
        return datetime.utcnow() - self.last_heartbeat <= timedelta(seconds=ttl_seconds)


class WorkerRegistry:
    def __init__(self):
        self._workers: Dict[str, WorkerNode] = {}

    def heartbeat(self, worker_id: str, capabilities: Dict[str, str], cpu_usage: float, memory_usage: float,
                  queue_depth: int, model_available: bool) -> WorkerNode:
        node = self._workers.get(worker_id)
        if node is None:
            node = WorkerNode(worker_id=worker_id, capabilities=capabilities)
            self._workers[worker_id] = node

        node.capabilities = capabilities
        node.cpu_usage = cpu_usage
        node.memory_usage = memory_usage
        node.queue_depth = queue_depth
        node.model_available = model_available
        node.last_heartbeat = datetime.utcnow()
        return node

    def list_alive(self) -> List[WorkerNode]:
        return [w for w in self._workers.values() if w.is_alive()]

    def get(self, worker_id: str) -> Optional[WorkerNode]:
        worker = self._workers.get(worker_id)
        if worker and worker.is_alive():
            return worker
        return None
