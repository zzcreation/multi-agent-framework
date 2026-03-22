"""
Worker 运行时 - 插件化 Worker 核心
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .plugin import Plugin, PluginLoader
from .tools import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class WorkerConfig:
    """Worker 配置"""
    worker_id: str = None
    capabilities: Dict[str, str] = field(default_factory=dict)
    max_concurrent_tasks: int = 3
    task_timeout_seconds: int = 300
    heartbeat_interval_seconds: int = 30
    control_plane_url: str = os.getenv("CONTROL_PLANE_URL", "http://localhost:8080")


class WorkerRuntime:
    """Worker 运行时 - 管理任务执行和插件"""

    def __init__(self, config: WorkerConfig = None):
        self.config = config or WorkerConfig()
        self._plugins: Dict[str, Plugin] = {}
        self._plugin_loader = PluginLoader()
        self._tool_registry = ToolRegistry()
        self._running = False
        self._current_tasks: Dict[str, Any] = {}

    def register_plugin(self, plugin: Plugin):
        """注册插件"""
        self._plugins[plugin.name] = plugin
        plugin.register_tools(self._tool_registry)
        logger.info(f"Registered plugin: {plugin.name}")

    def load_plugins_from_directory(self, directory: str):
        """从目录加载插件"""
        plugins = self._plugin_loader.load_from_directory(directory)
        for plugin in plugins:
            self.register_plugin(plugin)
        logger.info(f"Loaded {len(plugins)} plugins from {directory}")

    def get_tool(self, name: str) -> Optional[Callable]:
        """获取工具"""
        return self._tool_registry.get_tool(name)

    def list_tools(self) -> List[str]:
        """列出所有可用工具"""
        return self._tool_registry.list_tools()

    async def execute_task(self, task_envelope: Dict) -> Dict:
        """执行任务"""
        task_id = task_envelope.get("task_id")
        task_type = task_envelope.get("task_type")
        payload = task_envelope.get("payload", {})

        logger.info(f"Executing task {task_id} of type {task_type}")

        # 查找对应的处理器
        handler = self._tool_registry.get_handler(task_type)

        if not handler:
            return {
                "task_id": task_id,
                "status": "failed",
                "error": f"No handler for task type: {task_type}",
            }

        try:
            self._current_tasks[task_id] = asyncio.current_task()
            result = await asyncio.wait_for(
                handler(payload),
                timeout=self.config.task_timeout_seconds,
            )
            return {
                "task_id": task_id,
                "status": "succeeded",
                "result": result,
            }
        except asyncio.TimeoutError:
            return {
                "task_id": task_id,
                "status": "failed",
                "error": "Task timeout",
            }
        except Exception as e:
            logger.exception(f"Task {task_id} failed")
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
            }
        finally:
            self._current_tasks.pop(task_id, None)

    async def start_heartbeat(self):
        """启动心跳"""
        while self._running:
            try:
                await self._send_heartbeat()
            except Exception as e:
                logger.warning(f"Heartbeat failed: {e}")
            await asyncio.sleep(self.config.heartbeat_interval_seconds)

    async def _send_heartbeat(self):
        """发送心跳"""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{self.config.control_plane_url}/api/workers/heartbeat",
                json={
                    "worker_id": self.config.worker_id,
                    "capabilities": self.config.capabilities,
                    "status": "alive",
                    "queue_depth": len(self._current_tasks),
                },
            )

    async def start(self):
        """启动 Worker"""
        self._running = True
        logger.info(f"Worker {self.config.worker_id} started")

        # 启动心跳
        asyncio.create_task(self.start_heartbeat())

        # 等待任务
        await self._poll_tasks()

    async def _poll_tasks(self):
        """轮询任务"""
        import aiohttp
        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.config.control_plane_url}/api/workers/{self.config.worker_id}/next-task"
                    ) as resp:
                        if resp.status == 200:
                            task = await resp.json()
                            if task:
                                await self.execute_task(task)
                        elif resp.status == 204:
                            await asyncio.sleep(1)
                        else:
                            await asyncio.sleep(5)
            except Exception as e:
                logger.warning(f"Task polling failed: {e}")
                await asyncio.sleep(5)

    def stop(self):
        """停止 Worker"""
        self._running = False
        logger.info(f"Worker {self.config.worker_id} stopped")

    def get_status(self) -> Dict:
        """获取状态"""
        return {
            "worker_id": self.config.worker_id,
            "capabilities": self.config.capabilities,
            "running": self._running,
            "plugins": list(self._plugins.keys()),
            "tools": self.list_tools(),
            "current_tasks": len(self._current_tasks),
        }


# 全局运行时实例
_runtime: Optional[WorkerRuntime] = None


def get_runtime(config: WorkerConfig = None) -> WorkerRuntime:
    """获取全局运行时实例"""
    global _runtime
    if _runtime is None:
        _runtime = WorkerRuntime(config)
    return _runtime


def create_worker(
    worker_id: str,
    capabilities: List[str] = None,
    plugin_dirs: List[str] = None,
) -> WorkerRuntime:
    """创建 Worker 的便捷函数"""
    config = WorkerConfig(
        worker_id=worker_id,
        capabilities={cap: "true" for cap in (capabilities or [])},
    )
    runtime = get_runtime(config)

    # 加载插件
    if plugin_dirs:
        for directory in plugin_dirs:
            runtime.load_plugins_from_directory(directory)

    return runtime