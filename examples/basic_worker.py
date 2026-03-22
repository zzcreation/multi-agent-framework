"""
基础 Worker 示例
"""

import asyncio
from worker import WorkerRuntime, WorkerConfig


async def main():
    """运行基础 Worker"""

    # 创建配置
    config = WorkerConfig(
        worker_id="basic-worker-001",
        capabilities={
            "echo": "true",
            "math": "true",
            "text": "true",
        },
        max_concurrent_tasks=3,
        task_timeout_seconds=300,
    )

    # 创建运行时
    runtime = WorkerRuntime(config)

    # 注册简单的工具
    @runtime._tool_registry.register(name="echo", description="Echo back input")
    def echo(payload):
        return {"echo": payload.get("message", "")}

    @runtime._tool_registry.register(name="add", description="Add two numbers")
    def add(payload):
        a = payload.get("a", 0)
        b = payload.get("b", 0)
        return {"result": a + b}

    @runtime._tool_registry.register(name="uppercase", description="Convert to uppercase")
    def uppercase(payload):
        text = payload.get("text", "")
        return {"result": text.upper()}

    # 注册任务处理器
    @runtime._tool_registry.register_handler(task_type="echo")
    async def handle_echo(payload):
        return await asyncio.to_thread(echo, payload)

    @runtime._tool_registry.register_handler(task_type="math")
    async def handle_math(payload):
        operation = payload.get("operation", "add")
        if operation == "add":
            return await asyncio.to_thread(add, payload)
        return {"error": f"Unknown operation: {operation}"}

    # 打印状态
    print(f"Worker started: {config.worker_id}")
    print(f"Tools: {runtime.list_tools()}")

    # 模拟任务执行
    task = {
        "task_id": "test-001",
        "task_type": "echo",
        "payload": {"message": "Hello, World!"},
    }

    result = await runtime.execute_task(task)
    print(f"Task result: {result}")

    # 停止 Worker
    runtime.stop()
    print("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())