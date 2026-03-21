# 使用说明

## 快速开始

### 1. 环境要求

- Python 3.8+
- SSH 客户端
- 远程服务器已安装 OpenClaw

### 2. 基本用法

```python
from scripts.remote_executor import RemoteExecutor

# 创建执行器实例
executor = RemoteExecutor()

# 检查远程连接
if executor.check_remote_connection():
    print("✅ 远程连接正常")

# 执行任务
result = executor.execute_task(
    task="你好，请介绍一下自己",
    agent_type="assistant"
)

if result['success']:
    print(result['result'])
```

### 3. 命令行用法

```bash
# 检查远程连接
python scripts/remote_executor.py --check

# 获取远程状态
python scripts/remote_executor.py --status

# 测试远程 OpenClaw
python scripts/remote_executor.py --test-openclaw

# 执行远程命令
python scripts/remote_executor.py --exec "echo hello"
```

### 4. 启动监控面板

```bash
cd scripts
python monitor_dashboard.py
# 访问 http://localhost:8877
```

## 任务执行

### 选择 Agent 类型

| Agent | 用途 | 适用场景 |
|-------|------|----------|
| `assistant` | 通用任务 | 大多数任务 |
| `reviewer` | 代码审查 | 代码审查请求 |
| `sandbox` | 隔离测试 | 高风险操作 |

```python
# 代码审查
result = executor.execute_task(
    task="请审查这段代码: def foo(): pass",
    agent_type="reviewer"
)
```

### 并发任务

```python
tasks = [
    {'task': '任务1', 'agent_type': 'assistant'},
    {'task': '任务2', 'agent_type': 'assistant'},
    {'task': '任务3', 'agent_type': 'reviewer'}
]
results = executor.execute_tasks_parallel(tasks, max_workers=3)
```

### 使用缓存

```python
# 获取缓存的远程状态（30秒有效）
status = executor.get_cached_remote_status()

# 获取缓存的技能列表（60秒有效）
skills = executor.get_remote_skills()
```

## 错误处理

执行器内置了完善的错误处理：

```python
result = executor.execute_task("任务")

if not result['success']:
    print(f"❌ 失败: {result.get('error')}")
else:
    print(f"✅ 成功: {result['result']}")
```

常见错误：
- `SSH connection timeout`: SSH 连接超时
- `Execution timeout`: 任务执行超时（5分钟）
- `JSON decode error`: 结果解析失败

## 日志

日志文件位置：`/tmp/remote_executor.log`

```bash
# 实时查看日志
tail -f /tmp/remote_executor.log
```

## 性能优化

框架已内置以下优化：

1. **SSH 连接复用**: 减少连接建立开销
2. **结果缓存**: 避免重复请求
3. **并发执行**: 多任务并行处理
4. **重试机制**: 自动重试失败操作

这些功能默认启用，无需额外配置。