"""
插件系统 - 动态加载和扩展 Worker 功能
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, List, Type

logger = logging.getLogger(__name__)


class Plugin(ABC):
    """插件基类"""

    name: str = "base_plugin"
    version: str = "0.1.0"
    description: str = ""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._handlers: Dict[str, Callable] = {}

    @abstractmethod
    def register_tools(self, registry) -> None:
        """注册工具到注册表"""
        pass

    def get_tool(self, name: str) -> Callable:
        """获取工具"""
        return self._tools.get(name)

    def get_handler(self, task_type: str) -> Callable:
        """获取任务处理器"""
        return self._handlers.get(task_type)

    def on_load(self) -> None:
        """插件加载时回调"""
        logger.info(f"Plugin {self.name} loaded")

    def on_unload(self) -> None:
        """插件卸载时回调"""
        logger.info(f"Plugin {self.name} unloaded")


class PluginLoader:
    """插件加载器"""

    def __init__(self):
        self._loaded_plugins: Dict[str, Type[Plugin]] = {}

    def load_plugin_from_file(self, file_path: str) -> Plugin:
        """从文件加载插件"""
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Plugin file not found: {file_path}")

        # 动态导入模块
        spec = importlib.util.spec_from_file_location(path.stem, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = module
        spec.loader.exec_module(module)

        # 查找 Plugin 类
        plugin_class = None
        for item in dir(module):
            obj = getattr(module, item)
            if isinstance(obj, type) and issubclass(obj, Plugin) and obj is not Plugin:
                plugin_class = obj
                break

        if not plugin_class:
            raise ValueError(f"No Plugin class found in {file_path}")

        plugin = plugin_class()
        self._loaded_plugins[plugin.name] = plugin_class
        logger.info(f"Loaded plugin: {plugin.name} from {file_path}")
        return plugin

    def load_from_directory(self, directory: str) -> List[Plugin]:
        """从目录加载所有插件"""
        plugins = []
        path = Path(directory)

        if not path.exists():
            logger.warning(f"Plugin directory not found: {directory}")
            return plugins

        for file_path in path.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
            try:
                plugin = self.load_plugin_from_file(str(file_path))
                plugins.append(plugin)
            except Exception as e:
                logger.error(f"Failed to load plugin from {file_path}: {e}")

        return plugins

    def get_loaded_plugins(self) -> Dict[str, Type[Plugin]]:
        """获取已加载的插件"""
        return self._loaded_plugins.copy()


class PluginManager:
    """插件管理器"""

    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}
        self._loader = PluginLoader()

    def load_plugin(self, plugin: Plugin):
        """加载插件"""
        self._plugins[plugin.name] = plugin
        plugin.on_load()

    def unload_plugin(self, name: str):
        """卸载插件"""
        if name in self._plugins:
            self._plugins[name].on_unload()
            del self._plugins[name]

    def get_plugin(self, name: str) -> Plugin:
        """获取插件"""
        return self._plugins.get(name)

    def list_plugins(self) -> List[str]:
        """列出所有插件"""
        return list(self._plugins.keys())

    def reload_plugin(self, name: str, file_path: str = None):
        """重载插件"""
        self.unload_plugin(name)
        if file_path:
            plugin = self._loader.load_plugin_from_file(file_path)
            self.load_plugin(plugin)