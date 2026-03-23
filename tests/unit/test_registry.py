"""
WorkerRegistry 单元测试
"""

import pytest
import time
from services.control_plane.registry import WorkerRegistry, WorkerNode


class TestWorkerRegistry:
    """WorkerRegistry 测试用例"""

    def test_register_worker(self):
        """测试注册 Worker"""
        registry = WorkerRegistry()
        worker = registry.heartbeat(
            "worker-1",
            capabilities={"review": "true"},
            cpu_usage=20,
            memory_usage=30,
            queue_depth=0,
            model_available=True,
        )
        assert worker.worker_id == "worker-1"
        assert worker.capabilities["review"] == "true"

    def test_heartbeat_update(self):
        """测试心跳更新"""
        registry = WorkerRegistry()
        registry.heartbeat(
            "worker-1",
            capabilities={"review": "true"},
            cpu_usage=20,
            memory_usage=30,
            queue_depth=0,
            model_available=True,
        )
        
        # 模拟心跳更新
        worker = registry.heartbeat(
            "worker-1",
            capabilities={"review": "true"},
            cpu_usage=25,
            memory_usage=35,
            queue_depth=1,
            model_available=True,
        )
        
        assert worker.cpu_usage == 25
        assert worker.memory_usage == 35

    def test_list_alive_workers(self, mock_registry):
        """测试列出存活 Worker"""
        workers = mock_registry.list_alive()
        assert len(workers) >= 1

        """测试注销 Worker"""
        registry = WorkerRegistry()
        registry.heartbeat(
            "worker-1",
            capabilities={"review": "true"},
            cpu_usage=20,
            memory_usage=30,
            queue_depth=0,
            model_available=True,
        )
        
        registry.unregister("worker-1")
        assert registry.get("worker-1") is None

