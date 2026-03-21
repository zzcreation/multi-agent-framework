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
        worker = registry.register(
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
        registry.register(
            "worker-1",
            capabilities={"review": "true"},
            cpu_usage=20,
            memory_usage=30,
            queue_depth=0,
            model_available=True,
        )
        
        # 模拟心跳更新
        worker = registry.worker_heartbeat(
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

    def test_worker_expiry(self):
        """测试 Worker 过期"""
        registry = WorkerRegistry()
        registry.register(
            "worker-1",
            capabilities={"review": "true"},
            cpu_usage=20,
            memory_usage=30,
            queue_depth=0,
            model_available=True,
            ttl_seconds=1,  # 1秒 TTL
        )
        
        # 立即检查应该存活
        workers = registry.list_alive()
        assert len(workers) == 1
        
        # 等待过期
        time.sleep(1.5)
        
        # 再次检查应该不存活
        workers = registry.list_alive()
        assert len(workers) == 0

    def test_unregister_worker(self):
        """测试注销 Worker"""
        registry = WorkerRegistry()
        registry.register(
            "worker-1",
            capabilities={"review": "true"},
            cpu_usage=20,
            memory_usage=30,
            queue_depth=0,
            model_available=True,
        )
        
        registry.unregister("worker-1")
        assert registry.get("worker-1") is None

    def test_filter_by_capability(self):
        """测试按能力过滤"""
        registry = WorkerRegistry()
        registry.register(
            "worker-review",
            capabilities={"review": "true", "sandbox": "false"},
            cpu_usage=20,
            memory_usage=30,
            queue_depth=0,
            model_available=True,
        )
        registry.register(
            "worker-sandbox",
            capabilities={"review": "false", "sandbox": "true"},
            cpu_usage=20,
            memory_usage=30,
            queue_depth=0,
            model_available=True,
        )
        
        # 过滤有 review 能力的 worker
        reviewers = registry.list_alive(capabilities={"review": "true"})
        assert len(reviewers) == 1
        assert reviewers[0].worker_id == "worker-review"