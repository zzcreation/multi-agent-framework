"""
测试配置和 fixtures
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis = Mock()
    redis.ping.return_value = True
    redis.xadd.return_value = "test-msg-id"
    redis.xreadgroup.return_value = []
    redis.xack.return_value = 1
    redis.exists.return_value = False
    return redis


@pytest.fixture
def mock_registry():
    """Mock WorkerRegistry"""
    from services.control_plane.registry import WorkerRegistry, WorkerNode
    registry = WorkerRegistry()
    # Add mock workers
    registry.heartbeat(
        "test-worker-1",
        capabilities={"review": "true", "sandbox": "false", "toolset": "python"},
        cpu_usage=20,
        memory_usage=30,
        queue_depth=0,
        model_available=True,
    )
    registry.heartbeat(
        "test-worker-2", 
        capabilities={"review": "false", "sandbox": "true", "toolset": "bash"},
        cpu_usage=40,
        memory_usage=50,
        queue_depth=1,
        model_available=True,
    )
    return registry


@pytest.fixture
def sample_task_envelope():
    """Sample TaskEnvelope for testing"""
    from services.control_plane.task_protocol import TaskEnvelope
    return TaskEnvelope(
        task_id="test-task-001",
        task_type="review",
        priority=5,
        payload={"command": "echo hello", "required_review": "true"},
        deadline="2026-12-31T23:59:59",
    )


@pytest.fixture
def scheduler(mock_registry):
    """Scheduler with mock registry"""
    from services.control_plane.scheduler import Scheduler
    return Scheduler(mock_registry)


@pytest.fixture
def control_plane(mock_registry):
    """ControlPlane with mock registry"""
    from services.control_plane.control_plane import ControlPlane
    return ControlPlane(registry=mock_registry)