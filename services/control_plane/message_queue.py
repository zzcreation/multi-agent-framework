"""
消息队列模块 - 基于 Redis Stream 实现异步任务队列
支持：任务持久化、消费者组、DLQ 死信队列、消息可靠传递
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import heapq


# 默认配置
DEFAULT_STREAM_KEY = "openclaw:tasks"
DEFAULT_DLQ_KEY = "openclaw:tasks:dlq"
DEFAULT_CONSUMER_GROUP = "openclaw-workers"
DEFAULT_CONSUMER_PREFIX = "consumer-"

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # 秒


@dataclass
class QueueMessage:
    """队列消息"""
    id: str  # Redis Stream message ID
    envelope: Dict[str, Any]  # TaskEnvelope 序列化
    retry_count: int = 0
    enqueued_at: float = field(default_factory=time.time)


class MessageQueue:
    """基于 Redis Stream 的消息队列，支持消费者组、DLQ、消息可靠传递"""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        stream_key: str = DEFAULT_STREAM_KEY,
        dlq_key: str = DEFAULT_DLQ_KEY,
        consumer_group: str = DEFAULT_CONSUMER_GROUP,
    ):
        self.redis_url = redis_url
        self.stream_key = stream_key
        self.dlq_key = dlq_key
        self.consumer_group = consumer_group
        self._redis = None
        self._consumer_id = f"{DEFAULT_CONSUMER_PREFIX}{int(time.time() * 1000)}"
        self._local_queue: List[QueueMessage] = []  # 本地缓冲队列

    def connect(self) -> bool:
        """连接 Redis"""
        try:
            import redis
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
            self._redis.ping()
            self._ensure_consumer_group()
            return True
        except ImportError:
            print("redis-py not installed, using in-memory fallback")
            return False
        except Exception as e:
            print(f"Redis connection failed: {e}, using in-memory fallback")
            return False

    def _ensure_consumer_group(self) -> None:
        """确保消费者组存在"""
        try:
            # 检查流是否存在
            if not self._redis.exists(self.stream_key):
                self._redis.xgroup_create(self.stream_key, self.consumer_group, id="0", mkstream=True)
        except Exception as e:
            print(f"Consumer group creation: {e}")

    def enqueue(self, envelope: Dict[str, Any], delay_seconds: int = 0) -> str:
        """入队任务"""
        if not self._redis:
            raise RuntimeError("Redis not available, cannot enqueue")

        message = {
            "envelope": json.dumps(envelope),
            "retry_count": "0",
            "enqueued_at": str(time.time()),
        }

        if delay_seconds > 0:
            # 延迟队列：使用 sorted set 实现延迟
            delay_key = f"{self.stream_key}:delayed"
            self._redis.zadd(delay_key, {json.dumps(message): time.time() + delay_seconds})
            return f"delayed:{delay_seconds}"

        # 直接写入 Stream
        msg_id = self._redis.xadd(self.stream_key, message)
        return msg_id

    def process_delayed_tasks(self) -> int:
        """处理延迟队列中到期任务"""
        if not self._redis:
            return 0
        delay_key = f"{self.stream_key}:delayed"
        now = time.time()
        # 获取所有到期任务
        ready = self._redis.zrangebyscore(delay_key, 0, now)
        if ready:
            for msg_json in ready:
                msg = json.loads(msg_json)
                self._redis.xadd(self.stream_key, msg)
            self._redis.zremrangebyscore(delay_key, 0, now)
        return len(ready)

    def consume(self, count: int = 10, block_ms: int = 5000) -> List[QueueMessage]:
        """消费消息（使用消费者组）"""
        messages = []

        # 先处理本地队列
        while self._local_queue and count > 0:
            msg = heapq.heappop(self._local_queue)
            messages.append(msg)
            count -= 1

        if count <= 0:
            return messages

        # 从 Redis 消费
        if self._redis:
            try:
                # 使用消费者组读取
                results = self._redis.xreadgroup(
                    self.consumer_group,
                    self._consumer_id,
                    {self.stream_key: ">"},
                    count=count,
                    block=block_ms,
                )

                for stream, msgs in results or []:
                    for msg_id, msg in msgs:
                        envelope = json.loads(msg["envelope"])
                        retry_count = int(msg.get("retry_count", "0"))
                        enqueued_at = float(msg.get("enqueued_at", time.time()))

                        queue_msg = QueueMessage(
                            id=msg_id,
                            envelope=envelope,
                            retry_count=retry_count,
                            enqueued_at=enqueued_at,
                        )
                        messages.append(queue_msg)

            except Exception as e:
                print(f"Redis consume error: {e}")

        return messages

    def ack(self, message_id: str) -> bool:
        """确认消息处理成功"""
        if self._redis:
            try:
                self._redis.xack(self.stream_key, self.consumer_group, message_id)
                return True
            except Exception as e:
                print(f"ACK error: {e}")
        return True  # In-memory 模式总是成功

    def nack(self, message_id: str, retry_count: int, envelope: Dict[str, Any]) -> bool:
        """消息处理失败，放入重试队列或 DLQ"""
        if retry_count >= MAX_RETRIES:
            # 超过重试次数，进入 DLQ
            return self._send_to_dlq(envelope, f"max_retries_exceeded:{MAX_RETRIES}")

        # 重试：带延迟重新入队
        delay = RETRY_DELAY_BASE ** retry_count
        retry_envelope = envelope.copy()
        retry_envelope["_retry_count"] = retry_count + 1
        retry_envelope["_last_retry"] = time.time()

        message = {
            "envelope": json.dumps(retry_envelope),
            "retry_count": str(retry_count + 1),
            "enqueued_at": str(time.time()),
        }

        delay_key = f"{self.stream_key}:retry"
        self._redis.zadd(delay_key, {json.dumps(message): time.time() + delay})
        return True

    def process_retry_queue(self) -> int:
        """处理重试队列"""
        retry_key = f"{self.stream_key}:retry"
        now = time.time()
        ready = self._redis.zrangebyscore(retry_key, 0, now)

        count = 0
        for msg_json in ready:
            msg = json.loads(msg_json)
            self._redis.xadd(self.stream_key, msg)
            count += 1

        if ready:
            self._redis.zremrangebyscore(retry_key, 0, now)
        return count

    def _send_to_dlq(self, envelope: Dict[str, Any], reason: str) -> bool:
        """发送消息到死信队列"""
        dlq_message = {
            "envelope": json.dumps(envelope),
            "reason": reason,
            "failed_at": str(time.time()),
        }
        self._redis.xadd(self.dlq_key, dlq_message)
        return True

    def get_dlq_messages(self, count: int = 10) -> List[Dict]:
        """获取死信队列消息"""
        messages = self._redis.xrange(self.dlq_key, "-", "+", count)
        return [
            {
                "id": msg_id,
                "envelope": json.loads(msg["envelope"]),
                "reason": msg.get("reason", "unknown"),
                "failed_at": msg.get("failed_at", "unknown"),
            }
            for msg_id, msg in messages
        ]

    def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        if not self._redis:
            return {
                "stream_length": len(self._local_queue),
                "delayed_count": 0,
                "retry_count": 0,
                "dlq_length": 0,
            }

        try:
            stream_len = self._redis.xlen(self.stream_key)
            delay_key = f"{self.stream_key}:delayed"
            retry_key = f"{self.stream_key}:retry"
            dlq_len = self._redis.xlen(self.dlq_key)

            return {
                "stream_length": stream_len,
                "delayed_count": self._redis.zcard(delay_key),
                "retry_count": self._redis.zcard(retry_key),
                "dlq_length": dlq_len,
            }
        except Exception as e:
            return {"error": str(e)}

    def close(self) -> None:
        """关闭连接"""
        if self._redis:
            self._redis.close()


class MessageQueueManager:
    """消息队列管理器 - 统一管理多个队列"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.main_queue: Optional[MessageQueue] = None

    def initialize(self) -> bool:
        """初始化主队列"""
        self.main_queue = MessageQueue(self.redis_url)
        return self.main_queue.connect()

    def get_queue(self, name: str = "default") -> MessageQueue:
        """获取指定队列"""
        if name == "default":
            return self.main_queue
        return MessageQueue(self.redis_url, stream_key=f"openclaw:tasks:{name}")

    def get_stats(self) -> Dict[str, Any]:
        """获取所有队列统计"""
        return {
            "main": self.main_queue.get_queue_stats() if self.main_queue else {}
        }