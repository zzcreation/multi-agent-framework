"""
Automatic Failover Module

This module provides:
1. Worker health monitoring
2. Failure detection
3. Task rebalancing on worker failure
"""

from __future__ import annotations

import time
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from services.control_plane.task_protocol import TaskEnvelope

logger = logging.getLogger(__name__)


class WorkerStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class WorkerHealth:
    """Worker health information"""
    worker_id: str
    status: WorkerStatus = WorkerStatus.UNKNOWN
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_heartbeat: float = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    health_score: float = 1.0  # 0.0 to 1.0


class HealthMonitor:
    """
    Monitors worker health and detects failures.
    
    Uses multiple signals:
    - Heartbeat staleness
    - Consecutive failure count
    - CPU/Memory thresholds
    - Queue depth
    """
    
    def __init__(
        self,
        heartbeat_timeout: float = 60.0,           # Seconds without heartbeat = stale
        failure_threshold: int = 3,                  # Consecutive failures = degraded
        critical_failure_threshold: int = 5,        # Critical failures = failed
        recovery_threshold: int = 3,                # Consecutive successes to recover
        cpu_threshold: float = 95.0,                # CPU usage threshold
        memory_threshold: float = 95.0,            # Memory usage threshold
    ):
        self.heartbeat_timeout = heartbeat_timeout
        self.failure_threshold = failure_threshold
        self.critical_failure_threshold = critical_failure_threshold
        self.recovery_threshold = recovery_threshold
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        
        self._health: Dict[str, WorkerHealth] = {}
        self._lock = threading.RLock()
        
        # Callbacks
        self._on_worker_failed: Optional[Callable[[str, List[TaskEnvelope]], None]] = None
        self._on_worker_recovered: Optional[Callable[[str], None]] = None
        self._on_worker_degraded: Optional[Callable[[str, WorkerHealth], None]] = None
    
    def register_callbacks(
        self,
        on_worker_failed: Optional[Callable[[str, List[TaskEnvelope]], None]] = None,
        on_worker_recovered: Optional[Callable[[str], None]] = None,
        on_worker_degraded: Optional[Callable[[str, WorkerHealth], None]] = None,
    ) -> None:
        """Register callbacks for health state changes"""
        self._on_worker_failed = on_worker_failed
        self._on_worker_recovered = on_worker_recovered
        self._on_worker_degraded = on_worker_degraded
    
    def update_heartbeat(
        self,
        worker_id: str,
        cpu_usage: float = 0,
        memory_usage: float = 0,
        queue_depth: int = 0,
        model_available: bool = True,
    ) -> WorkerHealth:
        """Update worker heartbeat and return health status"""
        with self._lock:
            if worker_id not in self._health:
                self._health[worker_id] = WorkerHealth(worker_id=worker_id)
            
            health = self._health[worker_id]
            health.last_heartbeat = time.time()
            
            # Check for issues
            issues = []
            
            # CPU/Memory check
            if cpu_usage > self.cpu_threshold:
                issues.append(f"high_cpu={cpu_usage}")
            if memory_usage > self.memory_threshold:
                issues.append(f"high_memory={memory_usage}")
            
            # Update status based on issues
            if issues:
                if health.status != WorkerStatus.DEGRADED:
                    logger.warning(f"Worker {worker_id} degraded: {', '.join(issues)}")
                    if self._on_worker_degraded:
                        self._on_worker_degraded(worker_id, health)
                health.status = WorkerStatus.DEGRADED
            else:
                if health.status == WorkerStatus.DEGRADED:
                    health.consecutive_successes += 1
                    if health.consecutive_successes >= self.recovery_threshold:
                        health.status = WorkerStatus.HEALTHY
                        logger.info(f"Worker {worker_id} recovered")
                        if self._on_worker_recovered:
                            self._on_worker_recovered(worker_id)
            return health
    
    def record_success(self, worker_id: str) -> None:
        """Record successful execution"""
        with self._lock:
            if worker_id not in self._health:
                self._health[worker_id] = WorkerHealth(worker_id=worker_id)
            
            health = self._health[worker_id]
            health.consecutive_failures = 0
            health.consecutive_successes += 1
            health.last_success_time = time.time()
            
            # Update health score
            health.health_score = min(1.0, health.health_score + 0.05)
            
            if health.status == WorkerStatus.FAILED:
                if health.consecutive_successes >= self.recovery_threshold:
                    health.status = WorkerStatus.HEALTHY
                    logger.info(f"Worker {worker_id} recovered from failed state")
                    if self._on_worker_recovered:
                        self._on_worker_recovered(worker_id)
            elif health.status == WorkerStatus.DEGRADED:
                if health.consecutive_successes >= self.recovery_threshold:
                    health.status = WorkerStatus.HEALTHY
                    logger.info(f"Worker {worker_id} fully recovered")
                    if self._on_worker_recovered:
                        self._on_worker_recovered(worker_id)
    
    def record_failure(self, worker_id: str) -> None:
        """Record failed execution"""
        with self._lock:
            if worker_id not in self._health:
                self._health[worker_id] = WorkerHealth(worker_id=worker_id)
            
            health = self._health[worker_id]
            health.consecutive_failures += 1
            health.consecutive_successes = 0
            health.last_failure_time = time.time()
            
            # Update health score
            health.health_score = max(0.0, health.health_score - 0.2)
            
            # Determine status
            old_status = health.status
            
            if health.consecutive_failures >= self.critical_failure_threshold:
                health.status = WorkerStatus.FAILED
                logger.error(f"Worker {worker_id} marked as FAILED after {health.consecutive_failures} failures")
                if old_status != WorkerStatus.FAILED and self._on_worker_failed:
                    self._on_worker_failed(worker_id, [])
            elif health.consecutive_failures >= self.failure_threshold:
                health.status = WorkerStatus.DEGRADED
                logger.warning(f"Worker {worker_id} marked as DEGRADED after {health.consecutive_failures} failures")
                if old_status != WorkerStatus.DEGRADED and self._on_worker_degraded:
                    self._on_worker_degraded(worker_id, health)
    
    def check_stale_workers(self, active_worker_ids: List[str]) -> List[str]:
        """Check for stale workers (no heartbeat recently)"""
        stale = []
        now = time.time()
        
        with self._lock:
            for worker_id in active_worker_ids:
                health = self._health.get(worker_id)
                if health:
                    if now - health.last_heartbeat > self.heartbeat_timeout:
                        stale.append(worker_id)
                else:
                    # No heartbeat record = unknown, not stale
                    pass
        
        return stale
    
    def get_failed_workers(self) -> List[str]:
        """Get list of failed worker IDs"""
        with self._lock:
            return [
                worker_id
                for worker_id, health in self._health.items()
                if health.status == WorkerStatus.FAILED
            ]
    
    def get_degraded_workers(self) -> List[str]:
        """Get list of degraded worker IDs"""
        with self._lock:
            return [
                worker_id
                for worker_id, health in self._health.items()
                if health.status == WorkerStatus.DEGRADED
            ]
    
    def get_healthy_workers(self, active_worker_ids: List[str]) -> List[str]:
        """Get list of healthy worker IDs from active workers"""
        with self._lock:
            return [
                worker_id
                for worker_id in active_worker_ids
                if worker_id in self._health
                and self._health[worker_id].status == WorkerStatus.HEALTHY
            ]
    
    def get_all_health(self) -> Dict[str, Dict]:
        """Get health status for all workers"""
        with self._lock:
            return {
                worker_id: {
                    "status": health.status.value,
                    "health_score": health.health_score,
                    "consecutive_failures": health.consecutive_failures,
                    "consecutive_successes": health.consecutive_successes,
                    "last_heartbeat": health.last_heartbeat,
                    "last_failure_time": health.last_failure_time,
                }
                for worker_id, health in self._health.items()
            }


class FailoverManager:
    """
    Manages task rebalancing when workers fail.
    
    Features:
    - Automatic task recovery from failed workers
    - Load balancing across healthy workers
    - Configurable recovery policies
    """
    
    def __init__(
        self,
        health_monitor: Optional[HealthMonitor] = None,
        max_retry_count: int = 3,
        retry_delay_seconds: float = 2.0,
    ):
        self.health_monitor = health_monitor or HealthMonitor()
        self.max_retry_count = max_retry_count
        self.retry_delay_seconds = retry_delay_seconds
        
        # Task tracking for recovery
        self._task_retries: Dict[str, int] = {}  # task_id -> retry_count
        self._failed_tasks: Dict[str, TaskEnvelope] = {}  # task_id -> task
        self._lock = threading.RLock()
    
    def mark_task_failed(
        self,
        task_id: str,
        task: TaskEnvelope,
        failed_worker_id: Optional[str] = None,
    ) -> bool:
        """
        Mark a task as failed and track for potential retry.
        
        Returns True if task should be retried on another worker.
        """
        with self._lock:
            current_retries = self._task_retries.get(task_id, 0)
            
            if current_retries >= self.max_retry_count:
                logger.error(f"Task {task_id} exceeded max retry count ({self.max_retry_count})")
                return False
            
            self._task_retries[task_id] = current_retries + 1
            self._failed_tasks[task_id] = task
            
            # Record failure for the worker
            if failed_worker_id:
                self.health_monitor.record_failure(failed_worker_id)
            
            logger.info(
                f"Task {task_id} marked for retry "
                f"(attempt {current_retries + 1}/{self.max_retry_count})"
            )
            return True
    
    def mark_task_success(self, task_id: str, worker_id: Optional[str] = None) -> None:
        """Mark task as successfully completed"""
        with self._lock:
            self._task_retries.pop(task_id, None)
            self._failed_tasks.pop(task_id, None)
            
            if worker_id:
                self.health_monitor.record_success(worker_id)
    
    def get_retryable_tasks(self) -> List[TaskEnvelope]:
        """Get tasks that can be retried"""
        with self._lock:
            return list(self._failed_tasks.values())
    
    def remove_task(self, task_id: str) -> None:
        """Remove task from tracking (e.g., after manual handling)"""
        with self._lock:
            self._task_retries.pop(task_id, None)
            self._failed_tasks.pop(task_id, None)
    
    def get_stats(self) -> Dict:
        """Get failover statistics"""
        with self._lock:
            return {
                "tracking_tasks": len(self._failed_tasks),
                "total_retries": sum(self._task_retries.values()),
                "health_status": self.health_monitor.get_all_health(),
            }