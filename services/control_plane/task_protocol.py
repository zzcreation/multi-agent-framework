from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import uuid4


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: int = 3
    exponential_backoff: bool = True


@dataclass
class TaskEnvelope:
    """统一任务协议，贯穿控制平面与数据平面。"""

    task_type: str
    payload: Dict[str, Any]
    task_id: str = field(default_factory=lambda: str(uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = "default"
    priority: int = 5
    deadline: str = field(default_factory=lambda: (datetime.utcnow() + timedelta(minutes=30)).isoformat())
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    idempotency_key: str = field(default_factory=lambda: str(uuid4()))

    @classmethod
    def from_task(cls, task: str, tenant_id: str = "default", task_type: str = "generic") -> "TaskEnvelope":
        return cls(task_type=task_type, payload={"task": task}, tenant_id=tenant_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "trace_id": self.trace_id,
            "tenant_id": self.tenant_id,
            "priority": self.priority,
            "deadline": self.deadline,
            "retry_policy": {
                "max_attempts": self.retry_policy.max_attempts,
                "backoff_seconds": self.retry_policy.backoff_seconds,
                "exponential_backoff": self.retry_policy.exponential_backoff,
            },
            "idempotency_key": self.idempotency_key,
            "task_type": self.task_type,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskEnvelope":
        retry = data.get("retry_policy", {})
        return cls(
            task_id=data.get("task_id", str(uuid4())),
            trace_id=data.get("trace_id", str(uuid4())),
            tenant_id=data.get("tenant_id", "default"),
            priority=data.get("priority", 5),
            deadline=data.get("deadline", datetime.utcnow().isoformat()),
            retry_policy=RetryPolicy(
                max_attempts=retry.get("max_attempts", 3),
                backoff_seconds=retry.get("backoff_seconds", 3),
                exponential_backoff=retry.get("exponential_backoff", True),
            ),
            idempotency_key=data.get("idempotency_key", str(uuid4())),
            task_type=data.get("task_type", "generic"),
            payload=data.get("payload", {}),
        )
