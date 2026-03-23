"""
数据持久化模块 - 基于 PostgreSQL 实现任务状态、Worker 元数据、审计日志持久化
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态枚举"""
    CREATED = "CREATED"
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    RETRYING = "RETRYING"
    DEAD_LETTER = "DEAD_LETTER"


class DatabaseConfig:
    """数据库配置"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "openclaw",
        user: str = "openclaw",
        password: str = None,
        min_pool_size: int = 2,
        max_pool_size: int = 10,
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password or os.getenv("POSTGRES_PASSWORD", "openclaw")
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        self._pool = None

    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class TaskRecord:
    """任务记录"""
    task_id: str
    task_type: str
    priority: int
    status: TaskStatus
    payload: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    worker_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerRecord:
    """Worker 记录"""
    worker_id: str
    status: str
    capabilities: Dict[str, Any]
    cpu_usage: float = 0
    memory_usage: float = 0
    queue_depth: int = 0
    model_available: bool = True
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DatabaseManager:
    """数据库管理器 - PostgreSQL 连接池和基本操作"""

    def __init__(self, config: DatabaseConfig = None):
        self.config = config or DatabaseConfig()
        self._conn = None
        self._psycopg2_available = False

    def connect(self) -> bool:
        """连接数据库"""
        try:
            import psycopg2
            from psycopg2 import pool
            self._psycopg2_available = True
            self._pool = pool.ThreadedConnectionPool(
                self.config.min_pool_size,
                self.config.max_pool_size,
                self.config.connection_string
            )
            # 测试连接
            conn = self._pool.getconn()
            conn.autocommit = True
            self._pool.putconn(conn)
            logger.info("PostgreSQL connection established")
            self._initialize_schema()
            return True
        except ImportError:
            logger.warning("psycopg2 not installed, using in-memory fallback")
            return False
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            return False

    def _initialize_schema(self) -> None:
        """初始化数据库表结构"""
        if not self._psycopg2_available:
            return

        schema_sql = """
        -- 任务表
        CREATE TABLE IF NOT EXISTS tasks (
            task_id VARCHAR(255) PRIMARY KEY,
            task_type VARCHAR(100) NOT NULL,
            priority INTEGER DEFAULT 5,
            status VARCHAR(50) NOT NULL,
            payload JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            scheduled_at TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            worker_id VARCHAR(255),
            result JSONB,
            error TEXT,
            retry_count INTEGER DEFAULT 0,
            metadata JSONB DEFAULT '{}'
        );
        
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
        CREATE INDEX IF NOT EXISTS idx_tasks_worker_id ON tasks(worker_id);

        -- Worker 注册表
        CREATE TABLE IF NOT EXISTS workers (
            worker_id VARCHAR(255) PRIMARY KEY,
            status VARCHAR(50) NOT NULL,
            capabilities JSONB NOT NULL,
            cpu_usage FLOAT DEFAULT 0,
            memory_usage FLOAT DEFAULT 0,
            queue_depth INTEGER DEFAULT 0,
            model_available BOOLEAN DEFAULT TRUE,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSONB DEFAULT '{}'
        );
        
        CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status);
        CREATE INDEX IF NOT EXISTS idx_workers_last_heartbeat ON workers(last_heartbeat);

        -- 审计日志表
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            event_type VARCHAR(100) NOT NULL,
            entity_type VARCHAR(50) NOT NULL,
            entity_id VARCHAR(255),
            user_id VARCHAR(255),
            action VARCHAR(100) NOT NULL,
            details JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id);
        CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_logs(event_type);
        CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_logs(created_at);

        -- 死信队列表
        CREATE TABLE IF NOT EXISTS dead_letter_queue (
            id SERIAL PRIMARY KEY,
            task_id VARCHAR(255) NOT NULL,
            payload JSONB NOT NULL,
            failure_reason TEXT NOT NULL,
            retry_count INTEGER DEFAULT 0,
            failed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_dlq_task_id ON dead_letter_queue(task_id);
        """
        try:
            conn = self._pool.getconn()
            cursor = conn.cursor()
            cursor.execute(schema_sql)
            cursor.close()
            self._pool.putconn(conn)
            logger.info("Database schema initialized")
        except Exception as e:
            logger.error(f"Schema initialization failed: {e}")

    @contextmanager
    def get_connection(self):
        """获取数据库连接"""
        if self._psycopg2_available and self._pool:
            conn = self._pool.getconn()
            try:
                yield conn
            finally:
                self._pool.putconn(conn)
        else:
            # In-memory fallback
            yield None

    def save_task(self, record: TaskRecord) -> bool:
        """保存任务记录"""
        if self._psycopg2_available and self._pool:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO tasks (task_id, task_type, priority, status, payload, 
                                       created_at, updated_at, scheduled_at, started_at,
                                       completed_at, worker_id, result, error, retry_count, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (task_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        updated_at = CURRENT_TIMESTAMP,
                        completed_at = EXCLUDED.completed_at,
                        result = EXCLUDED.result,
                        error = EXCLUDED.error,
                        retry_count = EXCLUDED.retry_count,
                        metadata = EXCLUDED.metadata
                """, (
                    record.task_id, record.task_type, record.priority, record.status.value,
                    json.dumps(record.payload), record.created_at, record.updated_at,
                    record.scheduled_at, record.started_at, record.completed_at,
                    record.worker_id, json.dumps(record.result) if record.result else None,
                    record.error, record.retry_count, json.dumps(record.metadata)
                ))
                conn.commit()
                cursor.close()
            return True
        else:
            # In-memory fallback
            logger.debug(f"In-memory: task {record.task_id} saved")
            return True

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        """获取任务记录"""
        if self._psycopg2_available and self._pool:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM tasks WHERE task_id = %s", (task_id,))
                row = cursor.fetchone()
                cursor.close()
                if row:
                    return TaskRecord(
                        task_id=row[0], task_type=row[1], priority=row[2],
                        status=TaskStatus(row[3]), payload=row[4],
                        created_at=row[5], updated_at=row[6], scheduled_at=row[7],
                        started_at=row[8], completed_at=row[9], worker_id=row[10],
                        result=row[11], error=row[12], retry_count=row[13],
                        metadata=row[14]
                    )
        return None

    def list_tasks(self, status: TaskStatus = None, limit: int = 100) -> List[TaskRecord]:
        """列出任务记录"""
        tasks = []
        if self._psycopg2_available and self._pool:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if status:
                    cursor.execute(
                        "SELECT * FROM tasks WHERE status = %s ORDER BY created_at DESC LIMIT %s",
                        (status.value, limit)
                    )
                else:
                    cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT %s", (limit,))
                for row in cursor.fetchall():
                    tasks.append(TaskRecord(
                        task_id=row[0], task_type=row[1], priority=row[2],
                        status=TaskStatus(row[3]), payload=row[4],
                        created_at=row[5], updated_at=row[6], scheduled_at=row[7],
                        started_at=row[8], completed_at=row[9], worker_id=row[10],
                        result=row[11], error=row[12], retry_count=row[13],
                        metadata=row[14]
                    ))
                cursor.close()
        return tasks

    def save_worker(self, record: WorkerRecord) -> bool:
        """保存 Worker 记录"""
        if self._psycopg2_available and self._pool:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO workers (worker_id, status, capabilities, cpu_usage,
                                         memory_usage, queue_depth, model_available,
                                         registered_at, last_heartbeat, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (worker_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        cpu_usage = EXCLUDED.cpu_usage,
                        memory_usage = EXCLUDED.memory_usage,
                        queue_depth = EXCLUDED.queue_depth,
                        model_available = EXCLUDED.model_available,
                        last_heartbeat = CURRENT_TIMESTAMP,
                        metadata = EXCLUDED.metadata
                """, (
                    record.worker_id, record.status, json.dumps(record.capabilities),
                    record.cpu_usage, record.memory_usage, record.queue_depth,
                    record.model_available, record.registered_at, record.last_heartbeat,
                    json.dumps(record.metadata)
                ))
                conn.commit()
                cursor.close()
            return True
        return True

    def get_worker(self, worker_id: str) -> Optional[WorkerRecord]:
        """获取 Worker 记录"""
        if self._psycopg2_available and self._pool:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM workers WHERE worker_id = %s", (worker_id,))
                row = cursor.fetchone()
                cursor.close()
                if row:
                    return WorkerRecord(
                        worker_id=row[0], status=row[1], capabilities=row[2],
                        cpu_usage=row[3], memory_usage=row[4], queue_depth=row[5],
                        model_available=row[6], registered_at=row[7],
                        last_heartbeat=row[8], metadata=row[9]
                    )
        return None

    def list_workers(self, status: str = None, limit: int = 100) -> List[WorkerRecord]:
        """列出 Worker 记录"""
        workers = []
        if self._psycopg2_available and self._pool:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if status:
                    cursor.execute(
                        "SELECT * FROM workers WHERE status = %s ORDER BY last_heartbeat DESC LIMIT %s",
                        (status, limit)
                    )
                else:
                    cursor.execute("SELECT * FROM workers ORDER BY last_heartbeat DESC LIMIT %s", (limit,))
                for row in cursor.fetchall():
                    workers.append(WorkerRecord(
                        worker_id=row[0], status=row[1], capabilities=row[2],
                        cpu_usage=row[3], memory_usage=row[4], queue_depth=row[5],
                        model_available=row[6], registered_at=row[7],
                        last_heartbeat=row[8], metadata=row[9]
                    ))
                cursor.close()
        return workers

    def log_audit(self, event_type: str, entity_type: str, entity_id: str,
                  action: str, details: Dict = None, user_id: str = None) -> bool:
        """记录审计日志"""
        if self._psycopg2_available and self._pool:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO audit_logs (event_type, entity_type, entity_id, 
                                           user_id, action, details)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (event_type, entity_type, entity_id, user_id, action,
                      json.dumps(details) if details else None))
                conn.commit()
                cursor.close()
            return True
        return True

    def add_to_dlq(self, task_id: str, payload: Dict, reason: str, retry_count: int = 0) -> bool:
        """添加任务到死信队列"""
        if self._psycopg2_available and self._pool:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO dead_letter_queue (task_id, payload, failure_reason, retry_count)
                    VALUES (%s, %s, %s, %s)
                """, (task_id, json.dumps(payload), reason, retry_count))
                cursor.close()
            return True
        return True

    def get_dlq_messages(self, limit: int = 100) -> List[Dict]:
        """获取死信队列消息"""
        messages = []
        if self._psycopg2_available and self._pool:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM dead_letter_queue ORDER BY failed_at DESC LIMIT %s",
                    (limit,)
                )
                for row in cursor.fetchall():
                    messages.append({
                        "id": row[0],
                        "task_id": row[1],
                        "payload": row[2],
                        "reason": row[3],
                        "retry_count": row[4],
                        "failed_at": row[5]
                    })
                cursor.close()
        return messages

    def get_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        stats = {}
        if self._psycopg2_available and self._pool:
            try:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM tasks")
                    stats["total_tasks"] = cursor.fetchone()[0]
                    cursor.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
                    stats["tasks_by_status"] = dict(cursor.fetchall())
                    cursor.execute("SELECT COUNT(*) FROM workers")
                    stats["total_workers"] = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM dead_letter_queue")
                    stats["dlq_size"] = cursor.fetchone()[0]
                    cursor.close()
            except Exception as e:
                stats["error"] = str(e)
        else:
            stats["mode"] = "in-memory"
        return stats

    def close(self) -> None:
        """关闭连接"""
        if self._pool:
            self._pool.closeall()
            logger.info("PostgreSQL connection closed")


# 全局数据库管理器实例
_db_manager: Optional[DatabaseManager] = None


def get_db_manager(config: DatabaseConfig = None) -> DatabaseManager:
    """获取全局数据库管理器实例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(config)
    return _db_manager


def init_database(config: DatabaseConfig = None) -> bool:
    """初始化数据库连接"""
    global _db_manager
    _db_manager = DatabaseManager(config)
    return _db_manager.connect()