"""
工具注册系统 - 注册和管理 Worker 可用工具
"""

from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._handlers: Dict[str, Callable] = {}
        self._metadata: Dict[str, Dict] = {}

    def register(self, name: str, func: Callable, description: str = "", metadata: Dict = None):
        """注册工具"""
        self._tools[name] = func
        self._metadata[name] = {
            "description": description,
            "metadata": metadata or {},
            "signature": str(inspect.signature(func)),
        }
        logger.debug(f"Registered tool: {name}")

    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self._handlers[task_type] = handler
        logger.debug(f"Registered handler for task type: {task_type}")

    def get_tool(self, name: str) -> Optional[Callable]:
        """获取工具"""
        return self._tools.get(name)

    def get_handler(self, task_type: str) -> Optional[Callable]:
        """获取任务处理器"""
        return self._handlers.get(task_type)

    def list_tools(self) -> List[str]:
        """列出所有工具"""
        return list(self._tools.keys())

    def list_handlers(self) -> List[str]:
        """列出所有任务处理器"""
        return list(self._handlers.keys())

    def get_metadata(self, name: str) -> Optional[Dict]:
        """获取工具元数据"""
        return self._metadata.get(name)

    def get_all_metadata(self) -> Dict[str, Dict]:
        """获取所有工具元数据"""
        return self._metadata.copy()

    def unregister(self, name: str):
        """注销工具"""
        self._tools.pop(name, None)
        self._metadata.pop(name, None)

    def clear(self):
        """清空注册表"""
        self._tools.clear()
        self._handlers.clear()
        self._metadata.clear()


def tool(name: str = None, description: str = "", **metadata):
    """装饰器：注册工具函数"""

    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # 注册到全局注册表
        # 注意：需要在运行时通过 WorkerRuntime 使用
        wrapper._tool_name = tool_name
        wrapper._tool_description = description
        wrapper._tool_metadata = metadata

        return wrapper

    return decorator


# 全局注册表实例
_global_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """获取全局注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def register_tool(name: str, func: Callable, description: str = "", **metadata):
    """全局注册工具的便捷函数"""
    registry = get_registry()
    registry.register(name, func, description, metadata)


def register_handler(task_type: str, handler: Callable):
    """全局注册任务处理器的便捷函数"""
    registry = get_registry()
    registry.register_handler(task_type, handler)