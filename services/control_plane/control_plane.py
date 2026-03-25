from __future__ import annotations

from typing import Dict, Optional

from scripts.task_router import TaskRouter
from services.control_plane.registry import WorkerRegistry
from services.control_plane.saga import SagaManager
from services.control_plane.scheduler import Scheduler
from services.control_plane.task_protocol import TaskEnvelope
from services.control_plane.rate_limiter import (
    get_rate_limiter_registry,
    RateLimiterRegistry,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
)
from services.worker_runtime.runtime import WorkerRuntime


class ControlPlane:
    """Control Plane: 任务接入、路由、调度、策略。"""

    # Default rate limits
    DEFAULT_RATE = 100.0  # requests per second
    DEFAULT_BURST = 200   # burst capacity
    
    def __init__(self, rate_limit: Optional[float] = None, burst_limit: Optional[int] = None):
        self.router = TaskRouter()
        self.registry = WorkerRegistry()
        self.scheduler = Scheduler(self.registry)
        self.saga = SagaManager()
        self.runtime = WorkerRuntime()
        
        # Initialize rate limiter registry
        self.rate_limiters = get_rate_limiter_registry()
        self.default_rate = rate_limit or self.DEFAULT_RATE
        self.default_burst = burst_limit or self.DEFAULT_BURST
        
        # Initialize circuit breaker for runtime
        self.runtime_breaker = self.rate_limiters.get_or_create_breaker(
            "runtime",
            CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=3,
                timeout_seconds=30.0,
            )
        )
        
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
        # Apply rate limiting (per tenant or global)
        tenant_id = envelope.payload.get("tenant_id", "default")
        limiter_key = f"submit:{tenant_id}"
        
        if not self.rate_limiters.check_rate_limit(
            limiter_key, 
            self.default_rate, 
            self.default_burst
        ):
            return {
                "accepted": False, 
                "reason": "rate_limit_exceeded",
                "tenant_id": tenant_id,
                "retry_after": 1.0,
            }
        
        self.saga.transition(envelope, "NEW", "QUEUED")
        self.scheduler.submit(envelope, delay_seconds=delay_seconds)
        return {"accepted": True, "task": envelope.to_dict(), "delay_seconds": delay_seconds}

    def dispatch_once(self) -> Dict:
        # Check circuit breaker before dispatching
        if not self.runtime_breaker.can_execute():
            return {
                "dispatched": False,
                "reason": "circuit_breaker_open",
                "breaker_state": self.runtime_breaker.state.value,
                "retry_after": 30.0,
            }
        
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
                self.runtime_breaker.record_success()
            else:
                self.saga.transition(task, "DISPATCHED", "FAILED", detail=str(execution.get("result")))
                self.runtime_breaker.record_failure()
                compensation = self.saga.compensate(task)
                execution["compensation"] = compensation
            execution["preempted"] = preempted
            return execution
        except Exception as e:
            self.runtime_breaker.record_failure()
            raise
        finally:
            self.scheduler.mark_done(worker.worker_id)

    def get_rate_limit_stats(self) -> Dict:
        """Get rate limiter and circuit breaker statistics"""
        return self.rate_limiters.get_all_stats()

    def transition_logs(self):
        return self.saga.get_transition_log()
