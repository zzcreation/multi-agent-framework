# OpenClaw Multi-Agent Framework 技术规范 v0.2

> 版本: 0.2
> 更新日期: 2026-03-21
> 状态: 已冻结

---

## 1. 系统架构

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          Clients                                │
│  (CLI, SDK, REST API, WebSocket)                               │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Control Plane                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Gateway   │  │  Scheduler   │  │  Registry    │          │
│  │   (API)      │──│  (Task Dist) │──│  (Workers)   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│         │                                    │                  │
│         ▼                                    ▼                  │
│  ┌──────────────┐                    ┌──────────────┐          │
│  │   Monitor   │                    │   Message    │          │
│  │  (Metrics)  │                    │     Bus      │          │
│  └──────────────┘                    └──────────────┘          │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Worker Runtime Pool                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Worker 1  │  │   Worker 2  │  │   Worker N   │          │
│  │  (Agent A)  │  │  (Agent B)  │  │  (Agent N)   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 组件职责

| 组件 | 职责 | 技术选型 |
|------|------|----------|
| Gateway | API 网关、认证、限流 | Flask + JWT |
| Scheduler | 任务调度、负载均衡 | 自研 |
| Registry | Worker 注册、心跳管理 | Redis |
| Message Bus | 消息传递、事件驱动 | Redis Stream |
| Worker Runtime | Agent 运行时、执行环境 | Python |

---

## 2. TaskEnvelope 协议

### 2.1 任务结构

```python
class TaskEnvelope:
    task_id: str              # 唯一标识 (UUID)
    task_type: str            # 任务类型 (execute/chat/action)
    priority: int            # 优先级 (1-10, 10 最高)
    payload: Dict           # 任务内容
    created_at: int         # 创建时间 (Unix timestamp)
    timeout: int            # 超时时间 (秒)
    retry_policy: RetryPolicy  # 重试策略
    metadata: Dict          # 元数据

class RetryPolicy:
    max_retries: int        # 最大重试次数
    backoff_base: int      # 退避基数 (秒)
    backoff_multiplier: int # 退避乘数
    max_backoff: int       # 最大退避时间 (秒)
```

### 2.2 任务状态

```
CREATED → PENDING → SCHEDULED → RUNNING → COMPLETED
                ↓                    ↓
              FAILED              CANCELLED
                ↓
              RETRYING ──────────→ PENDING
                ↓
              DEAD_LETTER
```

### 2.3 Worker 心跳

```python
class WorkerHeartbeat:
    worker_id: str          # Worker 唯一标识
    status: str             # 状态 (idle/busy/offline)
    capabilities: List[str] # 支持的任务类型
    current_load: int       # 当前负载 (0-100)
    started_at: int         # 启动时间
    last_heartbeat: int     # 最后心跳时间
```

---

## 3. 控制平面 API

### 3.1 任务管理

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/tasks | 提交任务 |
| GET | /api/v1/tasks/{id} | 获取任务状态 |
| DELETE | /api/v1/tasks/{id} | 取消任务 |
| GET | /api/v1/tasks | 列出任务 |

### 3.2 Worker 管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/workers | 列出 Workers |
| GET | /api/v1/workers/{id} | 获取 Worker 状态 |
| GET | /api/v1/workers/{id}/metrics | 获取 Worker 指标 |

### 3.3 系统

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/health | 健康检查 |
| GET | /api/v1/metrics | 系统指标 |

### 3.4 API 响应格式

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "request_id": "uuid",
    "timestamp": 1234567890
  }
}

{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Error description",
    "details": { ... }
  }
}
```

---

## 4. 消息协议

### 4.1 消息队列

| 队列名称 | 用途 | 消息类型 |
|----------|------|----------|
| tasks.pending | 等待执行的任务 | TaskEnvelope |
| tasks.scheduled | 已调度的任务 | TaskEnvelope |
| tasks.completed | 已完成的任务 | TaskResult |
| tasks.failed | 失败的任务 | TaskResult |
| workers.heartbeat | Worker 心跳 | WorkerHeartbeat |
| workers.register | Worker 注册 | WorkerInfo |

### 4.2 事件类型

| 事件名称 | 说明 |
|----------|------|
| task.created | 任务创建 |
| task.started | 任务开始执行 |
| task.completed | 任务完成 |
| task.failed | 任务失败 |
| worker.registered | Worker 注册 |
| worker.heartbeat | Worker 心跳 |
| worker.offline | Worker 离线 |

---

## 5. 安全机制

### 5.1 认证

- API Key 认证
- JWT Token (未来支持)
- Token 有效期: 24 小时

### 5.2 授权

- 基于角色的访问控制 (RBAC)
- 角色: admin, operator, viewer

### 5.3 限流

| 端点 | 限制 |
|------|------|
| POST /api/v1/tasks | 100/minute |
| GET /api/v1/* | 1000/minute |

---

## 6. 可观测性

### 6.1 指标 (Metrics)

| 指标名称 | 类型 | 描述 |
|----------|------|------|
| tasks_submitted_total | Counter | 提交任务总数 |
| tasks_completed_total | Counter | 完成任务总数 |
| tasks_failed_total | Counter | 失败任务总数 |
| task_duration_seconds | Histogram | 任务执行时间 |
| worker_load | Gauge | Worker 负载 |
| api_request_duration | Histogram | API 请求延迟 |

### 6.2 日志

- 结构化 JSON 日志
- 日志级别: DEBUG, INFO, WARNING, ERROR
- 日志保留: 30 天

### 6.3 追踪

- OpenTelemetry 集成
- 采样率: 10%
- 传播: W3C Trace Context

---

## 7. 部署配置

### 7.1 环境变量

| 变量名 | 必填 | 描述 | 默认值 |
|--------|------|------|--------|
| OPENCLAW_MODE | 是 | 运行模式 | development |
| CONTROL_PLANE_PORT | 是 | API 端口 | 8080 |
| REDIS_URL | 是 | Redis 连接 | redis://localhost:6379 |
| API_KEY | 是 | API 密钥 | - |
| LOG_LEVEL | 否 | 日志级别 | INFO |

### 7.2 资源需求

| 服务 | CPU | 内存 | 磁盘 |
|------|-----|------|------|
| Control Plane | 1 core | 512 MB | 1 GB |
| Worker | 0.5 core | 256 MB | 500 MB |

---

## 8. 客户端 SDK

### 8.1 Python SDK

```python
from openclaw import OpenClawClient

client = OpenClawClient(
    api_key="your-api-key",
    endpoint="http://localhost:8080"
)

# 提交任务
task = client.tasks.submit(
    task_type="execute",
    payload={"command": "echo hello"},
    priority=5
)

# 获取结果
result = client.tasks.get(task.task_id)
print(result.status, result.output)
```

### 8.2 CLI

```bash
# 提交任务
openclaw task submit --type execute --payload '{"command": "echo hello"}'

# 查看状态
openclaw task status <task-id>

# 列出任务
openclaw task list --status completed
```

---

## 9. 未来规划 (v1.0)

- [ ] PostgreSQL 持久化
- [ ] Kafka 消息队列
- [ ] 多租户支持
- [ ] OAuth 2.0 认证
- [ ] Grafana 集成看板

---

## 附录

### A. 错误码

| 错误码 | 描述 | HTTP 状态码 |
|--------|------|-------------|
| TASK_NOT_FOUND | 任务不存在 | 404 |
| TASK_EXPIRED | 任务已过期 | 410 |
| WORKER_UNAVAILABLE | Worker 不可用 | 503 |
| RATE_LIMIT_EXCEEDED | 超出限流 | 429 |
| AUTH_FAILED | 认证失败 | 401 |
| AUTH_FORBIDDEN | 权限不足 | 403 |

### B. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.1 | 2026-03-18 | 初始版本 |
| 0.2 | 2026-03-21 | TaskEnvelope 协议冻结 |

---

*本文档定义了 v0.2 版本的完整技术规范，是开发、测试和部署的参考依据。*