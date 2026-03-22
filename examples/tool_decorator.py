"""
工具装饰器示例 - 使用 @tool 装饰器注册工具
"""

import asyncio
from worker import WorkerRuntime, WorkerConfig, tool


# 使用 @tool 装饰器定义工具
@tool(name="greet", description="生成问候语")
def greet(payload):
    name = payload.get("name", "World")
    style = payload.get("style", "friendly")
    
    greetings = {
        "friendly": f"Hi, {name}! 👋",
        "formal": f"Hello, {name}.",
        "casual": f"Hey {name}!",
    }
    
    return {
        "greeting": greetings.get(style, greetings["friendly"]),
        "name": name,
    }


@tool(name="format_date", description="格式化日期")
def format_date(payload):
    from datetime import datetime
    
    date_str = payload.get("date")
    format_str = payload.get("format", "%Y-%m-%d")
    
    try:
        if date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            dt = datetime.now()
        
        return {"formatted": dt.strftime(format_str)}
    except Exception as e:
        return {"error": str(e)}


@tool(name="hash", description="生成哈希值")
def hash_string(payload):
    import hashlib
    import json
    
    text = payload.get("text", "")
    algorithm = payload.get("algorithm", "sha256")
    
    try:
        hash_func = getattr(hashlib, algorithm)()
        hash_func.update(text.encode())
        return {
            "hash": hash_func.hexdigest(),
            "algorithm": algorithm,
            "length": len(hash_func.hexdigest()),
        }
    except AttributeError:
        return {"error": f"Unsupported algorithm: {algorithm}"}


async def main():
    """运行使用装饰器的 Worker"""

    # 创建配置
    config = WorkerConfig(
        worker_id="decorator-worker-001",
        capabilities=["greet", "format", "hash"],
    )

    # 创建运行时
    runtime = WorkerRuntime(config)

    # 获取内部注册表并注册工具
    # 注意：在实际使用中，应通过插件或直接调用 register
    registry = runtime._tool_registry
    
    # 注册工具（使用装饰器函数）
    for func in [greet, format_date, hash_string]:
        tool_name = getattr(func, "_tool_name", func.__name__)
        tool_desc = getattr(func, "_tool_description", "")
        registry.register(tool_name, func, tool_desc)

    # 注册任务处理器
    registry.register_handler("greet", lambda p: greet(p))
    registry.register_handler("format_date", lambda p: format_date(p))
    registry.register_handler("hash", lambda p: hash_string(p))

    # 打印状态
    print(f"Worker started: {config.worker_id}")
    print(f"Tools: {runtime.list_tools()}")
    print(f"Metadata: {runtime._tool_registry.get_all_metadata()}")

    # 测试问候
    task1 = {
        "task_id": "test-001",
        "task_type": "greet",
        "payload": {"name": "Alice", "style": "friendly"},
    }
    result1 = await runtime.execute_task(task1)
    print(f"Greet task: {result1}")

    # 测试哈希
    task2 = {
        "task_id": "test-002",
        "task_type": "hash",
        "payload": {"text": "Hello World", "algorithm": "md5"},
    }
    result2 = await runtime.execute_task(task2)
    print(f"Hash task: {result2}")

    # 停止 Worker
    runtime.stop()


if __name__ == "__main__":
    asyncio.run(main())