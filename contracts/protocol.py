#!/usr/bin/env python3
"""统一协议定义：所有 agent 执行都使用结构化契约。"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import uuid


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TaskSpec:
    task_id: str
    title: str
    payload: Dict[str, Any]
    priority: TaskPriority = TaskPriority.MEDIUM
    sla_seconds: int = 600
    target_capability: Optional[str] = None
    retry_count: int = 0
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @staticmethod
    def new(title: str, payload: Dict[str, Any], **kwargs: Any) -> "TaskSpec":
        return TaskSpec(task_id=str(uuid.uuid4()), title=title, payload=payload, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["priority"] = self.priority.value
        return data


@dataclass
class TaskResult:
    task_id: str
    success: bool
    output: Dict[str, Any]
    error: Optional[str] = None
    worker_id: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Heartbeat:
    worker_id: str
    load: float
    queue_depth: int
    capabilities: List[str]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Lease:
    worker_id: str
    lease_id: str
    expires_at: str

    @staticmethod
    def issue(worker_id: str, ttl_seconds: int = 30) -> "Lease":
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        return Lease(worker_id=worker_id, lease_id=str(uuid.uuid4()), expires_at=expires.isoformat())

    def is_expired(self) -> bool:
        return datetime.fromisoformat(self.expires_at) <= datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorkerRegistration:
    worker_id: str
    endpoint: str
    capabilities: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def encode_message(message: Dict[str, Any]) -> str:
    return json.dumps(message, ensure_ascii=False)


def decode_message(raw: str) -> Dict[str, Any]:
    return json.loads(raw)
