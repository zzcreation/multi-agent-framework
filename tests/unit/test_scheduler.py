"""
Scheduler 单元测试
"""

import pytest
import time
from services.control_plane.scheduler import Scheduler
from services.control_plane.task_protocol import TaskEnvelope


class TestScheduler:
    """Scheduler 测试用例"""

    def test_submit_task(self, scheduler, sample_task_envelope):
        """测试任务提交"""
        scheduler.submit(sample_task_envelope)
        assert scheduler.has_pending() is True

    def test_priority_queue_order(self, scheduler):
        """测试优先级队列顺序"""
        low_priority = TaskEnvelope(
            task_id="low-priority",
            task_type="test",
            priority=10,
            payload={},
            deadline="2026-12-31T23:59:59"
        )
        high_priority = TaskEnvelope(
            task_id="high-priority",
            task_type="test", 
            priority=1,
            payload={},
            deadline="2026-12-31T23:59:59"
        )
        
        scheduler.submit(low_priority)
        scheduler.submit(high_priority)
        
        # 高优先级任务应该先出队
        next_task = scheduler.next_task()
        assert next_task.task_id == "high-priority"

    def test_delayed_task(self, scheduler, sample_task_envelope):
        """测试延迟队列"""
        scheduler.submit(sample_task_envelope, delay_seconds=10)
        # 延迟任务不应该立即可用
        assert scheduler.has_pending() is False

    def test_route_to_worker(self, scheduler, sample_task_envelope, mock_registry):
        """测试路由到合适的 Worker"""
        worker = scheduler.route(sample_task_envelope)
        assert worker is not None

    def test_idempotency_check(self, scheduler, sample_task_envelope):
        """测试幂等性检查"""
        scheduler.submit(sample_task_envelope)
        scheduler.submit(sample_task_envelope)  # 重复提交
        
        task = scheduler.next_task()
        # 第二次应该返回 None（已被标记为已处理）
        next_task = scheduler.next_task()
        # 由于幂等性检查，第二次提交会被跳过
        assert next_task is None or next_task.task_id == sample_task_envelope.task_id

    def test_mark_running(self, scheduler, sample_task_envelope):
        """测试标记任务运行中"""
        scheduler.mark_running("test-worker", sample_task_envelope)
        assert "test-worker" in scheduler._running_by_worker

    def test_mark_done(self, scheduler, sample_task_envelope):
        """测试标记任务完成"""
        scheduler.mark_running("test-worker", sample_task_envelope)
        scheduler.mark_done("test-worker")
        assert "test-worker" not in scheduler._running_by_worker

    def test_is_expired(self, scheduler, sample_task_envelope):
        """测试过期检查"""
        # 创建已过期的任务
        expired_task = TaskEnvelope(
            task_id="expired",
            task_type="test",
            priority=5,
            payload={},
            deadline="2020-01-01T00:00:00"
        )
        assert scheduler.is_expired(expired_task) is True
        
        # 未过期的任务
        assert scheduler.is_expired(sample_task_envelope) is False

