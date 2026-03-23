# OpenClaw Worker SDK Examples

本目录包含 OpenClaw Worker SDK 的使用示例。

## 示例列表

| 示例 | 说明 |
|------|------|
| `basic_worker.py` | 基础 Worker 示例 |
| `custom_plugin.py` | 自定义插件示例 |
| `tool_decorator.py` | 工具装饰器示例 |
| `async_tasks.py` | 异步任务处理示例 |

## 快速开始

```python
from worker import create_worker, tool

# 定义工具
@tool(name="echo", description="Echo back the input")
def echo(payload):
    return {"echo": payload.get("message", "")}

# 创建 Worker
worker = create_worker(
    worker_id="my-worker",
    capabilities=["echo", "test"],
)

# 运行 Worker
async def main():
    await worker.start()

if __name__ == "__main__":
    asyncio.run(main())
```

## 更多信息

- [SDK 文档](../sdk/worker/README.md)
- [API 参考](../sdk/worker/api.md)
- [贡献指南](../CONTRIBUTING.md)