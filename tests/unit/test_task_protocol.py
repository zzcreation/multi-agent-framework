"""
TaskEnvelope 协议单元测试
"""

import pytest
import json
from datetime import datetime
from services.control_plane.task_protocol import TaskEnvelope, TaskStatus


class TestTaskEnvelope:
    """TaskEnvelope 测试用例"""

    def test_create_envelope(self):
        """测试创建任务信封"""
        envelope = TaskEnvelope(
            task_id="test-001",
            task_type="review",
            priority=5,
            payload={"command": "echo hello"},
            deadline="2026-12-31T23:59:59",
        )
        assert envelope.task_id == "test-001"
        assert envelope.task_type == "review"
        assert envelope.priority == 5

    def test_serialization(self, sample_task_envelope):
        """测试序列化"""
        data = sample_task_envelope.to_dict()
        assert isinstance(data, dict)
        assert "task_id" in data
        
        # 测试 JSON 序列化
        json_str = json.dumps(data, default=str)
        assert isinstance(json_str, str)

    def test_deserialization(self, sample_task_envelope):
        """测试反序列化"""
        data = sample_task_envelope.to_dict()
        restored = TaskEnvelope.from_dict(data)
        
        assert restored.task_id == sample_task_envelope.task_id
        assert restored.task_type == sample_task_envelope.task_type
        assert restored.priority == sample_task_envelope.priority

    def test_default_values(self):
        """测试默认值"""
        envelope = TaskEnvelope(
            task_id="test-default",
            task_type="test",
            priority=5,
            payload={},
            deadline="2026-12-31T23:59:59",
        )
        assert envelope.status == TaskStatus.NEW
        assert envelope.created_at is not None

    def test_deadline_validation(self):
        """测试截止时间验证"""
        with pytest.raises(ValueError):
            TaskEnvelope(
                task_id="invalid-deadline",
                task_type="test",
                priority=5,
                payload={},
                deadline="invalid-date"
            )