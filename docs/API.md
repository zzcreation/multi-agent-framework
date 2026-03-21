# API 文档

## RemoteExecutor 类

主执行器类，负责与远程 OpenClaw Gateway 通信。

### 构造函数

```python
from remote_executor import RemoteExecutor

executor = RemoteExecutor(config_path: str = None)
```

**参数：**
- `config_path`: 配置文件路径，默认 `config/remote-agent.json`

### 核心方法

#### `check_remote_connection(max_retries: int = 3) -> bool`

检查远程连接是否正常（带重试机制）。

```python
result = executor.check_remote_connection()
# 返回: True/False
```

#### `execute_task(task: str, agent_type: str = "assistant", prefer_api: bool = True) -> dict`

执行远程任务。

```python
result = executor.execute_task(
    task="帮我写一个 Python 脚本",
    agent_type="assistant"
)
# 返回: {
#   'success': True,
#   'result': {...},
#   'method': 'ssh_openclaw_agent',
#   'agent_type': 'assistant'
# }
```

#### `execute_via_gateway_api(prompt: str, agent_type: str = "assistant") -> dict`

通过 Gateway HTTP API 调用远程 Agent。

```python
result = executor.execute_via_gateway_api(
    prompt="任务描述",
    agent_type="reviewer"
)
```

#### `get_remote_status() -> dict`

获取远程 OpenClaw 状态。

```python
status = executor.get_remote_status()
# 返回: {'connected': True, 'output': '...', 'error': None}
```

#### `test_remote_openclaw() -> bool`

测试远程 OpenClaw 是否正常工作。

```python
result = executor.test_remote_openclaw()
# 返回: True/False
```

### 性能优化方法

#### `execute_tasks_parallel(tasks: List[dict], max_workers: int = 3) -> List[dict]`

并发执行多个任务。

```python
tasks = [
    {'task': '任务1', 'agent_type': 'assistant'},
    {'task': '任务2', 'agent_type': 'reviewer'},
    {'task': '任务3', 'agent_type': 'assistant'}
]
results = executor.execute_tasks_parallel(tasks, max_workers=3)
```

#### `get_cached_remote_status(use_cache: bool = True) -> dict`

获取远程状态（带缓存，30秒）。

```python
status = executor.get_cached_remote_status()
```

#### `get_remote_skills() -> List[str]`

获取远程 Agent 可用技能列表（带缓存，60秒）。

```python
skills = executor.get_remote_skills()
# 返回: ['skill1', 'skill2', ...]
```

### 辅助方法

#### `get_ssh_command() -> list`

获取 SSH 命令列表。

```python
ssh_cmd = executor.get_ssh_command()
# 返回: ['ssh', '-o', 'StrictHostKeyChecking=no', ...]
```

#### `get_openclaw_cmd_prefix() -> str`

获取远程 OpenClaw 调用前缀。

---

## SSHConnectionPool 类

SSH 连接池，维护持久连接以提升性能。

```python
from remote_executor import SSHConnectionPool

pool = SSHConnectionPool()
connection = pool.get_connection(ssh_cmd)
pool.close()
```

---

## 装饰器

### `@with_retry(max_retries=3, retry_delay=2, retry_on=None)`

重试装饰器。

```python
@with_retry(max_retries=3, retry_delay=2)
def my_function():
    ...
```

### `@cached(ttl=300)`

带 TTL 的缓存装饰器。

```python
@cached(ttl=60)
def my_function():
    ...
```

---

## 配置项

配置文件 `config/remote-agent.json` 包含：

```json
{
  "ssh_config": {
    "host": "192.168.130.33",
    "port": 2222,
    "user": "zzc"
  },
  "remote_gateway": "ws://192.168.130.33:18789",
  "agents": {
    "assistant": {"agent_id": "assistant"},
    "reviewer": {"agent_id": "reviewer"},
    "sandbox": {"agent_id": "sandbox"}
  }
}
```