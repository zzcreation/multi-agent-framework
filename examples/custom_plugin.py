"""
自定义插件示例
"""

import asyncio
from worker import WorkerRuntime, WorkerConfig, Plugin


class TextProcessingPlugin(Plugin):
    """文本处理插件"""

    name = "text_processing"
    version = "0.1.0"
    description = "文本处理工具集"

    def register_tools(self, registry):
        """注册文本处理工具"""

        @registry.register(name="reverse", description="反转文本")
        def reverse(payload):
            text = payload.get("text", "")
            return {"result": text[::-1]}

        @registry.register(name="length", description="计算文本长度")
        def length(payload):
            text = payload.get("text", "")
            return {"result": len(text)}

        @registry.register(name="word_count", description="统计词数")
        def word_count(payload):
            text = payload.get("text", "")
            words = text.split()
            return {"result": len(words), "words": len(words)}

        # 注册任务处理器
        registry.register_handler("reverse", lambda p: reverse(p))
        registry.register_handler("length", lambda p: length(p))
        registry.register_handler("word_count", lambda p: word_count(p))


class MathPlugin(Plugin):
    """数学计算插件"""

    name = "math"
    version = "0.1.0"
    description = "数学计算工具集"

    def register_tools(self, registry):
        """注册数学工具"""

        @registry.register(name="calculate", description="通用计算器")
        def calculate(payload):
            expression = payload.get("expression", "0")
            try:
                # 安全计算 (仅支持基本运算)
                allowed_chars = set("0123456789+-*/.() ")
                if all(c in allowed_chars for c in expression):
                    result = eval(expression)  # 注意：生产环境请使用安全解析
                else:
                    return {"error": "Invalid expression"}
                return {"result": result}
            except Exception as e:
                return {"error": str(e)}

        @registry.register(name="factorial", description="阶乘计算")
        def factorial(payload):
            n = payload.get("n", 0)
            if n < 0:
                return {"error": "Negative number"}
            if n > 100:
                return {"error": "Number too large"}
            result = 1
            for i in range(1, n + 1):
                result *= i
            return {"result": result}

        # 注册任务处理器
        registry.register_handler("calculate", lambda p: calculate(p))
        registry.register_handler("factorial", lambda p: factorial(p))


async def main():
    """运行带插件的 Worker"""

    # 创建配置
    config = WorkerConfig(
        worker_id="plugin-worker-001",
        capabilities=["text", "math"],
    )

    # 创建运行时
    runtime = WorkerRuntime(config)

    # 注册插件
    runtime.register_plugin(TextProcessingPlugin())
    runtime.register_plugin(MathPlugin())

    # 打印状态
    print(f"Worker started: {config.worker_id}")
    print(f"Plugins: {list(runtime._plugins.keys())}")
    print(f"Tools: {runtime.list_tools()}")

    # 测试文本处理
    task1 = {
        "task_id": "test-001",
        "task_type": "reverse",
        "payload": {"text": "Hello World"},
    }
    result1 = await runtime.execute_task(task1)
    print(f"Reverse task: {result1}")

    # 测试数学计算
    task2 = {
        "task_id": "test-002",
        "task_type": "factorial",
        "payload": {"n": 5},
    }
    result2 = await runtime.execute_task(task2)
    print(f"Factorial task: {result2}")

    # 停止 Worker
    runtime.stop()
    print("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())