#!/usr/bin/env python3
"""Worker 注册中心：注册、心跳、租约过期摘除、能力标签管理。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional

from contracts.protocol import Heartbeat, Lease, WorkerRegistration


@dataclass
class WorkerState:
    registration: WorkerRegistration
    lease: Lease
    load: float = 0.0
    queue_depth: int = 0
    last_heartbeat: Optional[str] = None


class WorkerRegistry:
    def __init__(self, lease_ttl_seconds: int = 30):
        self.lease_ttl_seconds = lease_ttl_seconds
        self._workers: Dict[str, WorkerState] = {}
        self._lock = Lock()

    def register(self, worker: WorkerRegistration) -> Lease:
        lease = Lease.issue(worker.worker_id, ttl_seconds=self.lease_ttl_seconds)
        with self._lock:
            self._workers[worker.worker_id] = WorkerState(registration=worker, lease=lease)
        return lease

    def heartbeat(self, hb: Heartbeat) -> Optional[Lease]:
        with self._lock:
            self.evict_expired_locked()
            state = self._workers.get(hb.worker_id)
            if not state:
                return None
            state.load = hb.load
            state.queue_depth = hb.queue_depth
            state.last_heartbeat = hb.timestamp
            state.registration.capabilities = hb.capabilities
            state.lease = Lease.issue(hb.worker_id, ttl_seconds=self.lease_ttl_seconds)
            return state.lease

    def evict_expired_locked(self) -> None:
        expired = [wid for wid, s in self._workers.items() if s.lease.is_expired()]
        for wid in expired:
            self._workers.pop(wid, None)

    def evict_expired(self) -> None:
        with self._lock:
            self.evict_expired_locked()

    def list_workers(self) -> List[WorkerState]:
        with self._lock:
            self.evict_expired_locked()
            return list(self._workers.values())

    def get_worker_snapshot(self) -> List[dict]:
        return [
            {
                "worker_id": s.registration.worker_id,
                "endpoint": s.registration.endpoint,
                "capabilities": s.registration.capabilities,
                "load": s.load,
                "queue_depth": s.queue_depth,
                "last_heartbeat": s.last_heartbeat,
                "lease_expires_at": s.lease.expires_at,
                "now": datetime.now(timezone.utc).isoformat(),
            }
            for s in self.list_workers()
        ]
