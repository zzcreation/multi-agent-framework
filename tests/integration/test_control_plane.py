"""
集成测试 - Control Plane 完整流程测试
"""

import pytest
from services.control_plane.control_plane import ControlPlane
from services.control_plane.scheduler import Scheduler
from services.control_plane.registry import WorkerRegistry
from services.control_plane.task_protocol import TaskEnvelope


class TestControlPlaneIntegration:
    """ControlPlane 集成测试"""

    def test_full_task_flow(self):
        """测试完整任务流程"""
        # 1. 初始化 - ControlPlane creates registry/scheduler internally
        control_plane = ControlPlane()
        registry = control_plane.registry
        scheduler = control_plane.scheduler
        
        # 2. 注册 Worker
        control_plane.worker_heartbeat(
            "worker-1",
            capabilities={"review": "true", "sandbox": "false", "toolset": "python"},
            cpu_usage=20,
            memory_usage=30,
            queue_depth=0,
            model_available=True,
        )
        
        # 3. 提交任务
        envelope = TaskEnvelope(
            task_type="review",
            priority=5,
            payload={"command": "test command"},
            deadline="2026-12-31T23:59:59",
        )
        result = control_plane.submit_task(envelope)
        task_id = result.get("task", {}).get("task_id")
        assert task_id is not None
        
        # 4. 检查任务状态
        status = control_plane.get_task_status(task_id)
        assert status is not None
        
    def test_task_routing(self):
        """测试任务路由"""
        control_plane = ControlPlane()
        registry = control_plane.registry
        scheduler = control_plane.scheduler
        
        # 注册不同能力的 Worker
        control_plane.worker_heartbeat(
            "worker-review",
            capabilities={"review": "true"},
            cpu_usage=20,
            memory_usage=30,
            queue_depth=0,
            model_available=True,
        )
        control_plane.worker_heartbeat(
            "worker-sandbox",
            capabilities={"sandbox": "true"},
            cpu_usage=20,
            memory_usage=30,
            queue_depth=0,
            model_available=True,
        )
        
        # 提交需要 review 的任务
        envelope = TaskEnvelope(
            task_type="review",
            priority=5,
            payload={"required_review": "true"},
            deadline="2026-12-31T23:59:59",
        )
        result = control_plane.submit_task(envelope)
        task_id = result.get("task", {}).get("task_id")
        
        # 调度任务
        result = control_plane.dispatch_next_task()
        assert result is not None
        
    def test_worker_health_check(self):
        """测试 Worker 健康检查"""
        control_plane = ControlPlane()
        registry = control_plane.registry
        scheduler = control_plane.scheduler
        
        # 注册 Worker
        control_plane.worker_heartbeat(
            "worker-1",
            capabilities={"review": "true"},
            cpu_usage=80,  # 高负载
            memory_usage=90,
            queue_depth=10,
            model_available=True,
        )
        
        # 检查系统健康
        health = control_plane.check_system_health()
        assert "worker_health" in health or "workers" in health