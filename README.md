# 多 Agent 协作框架

基于 OpenClaw 的多 Agent 分布式任务执行框架。

## 架构（Control Plane / Worker Runtime 双进程）

```
用户/调用方 → Control Plane API(HTTP gateway, 可扩展 gRPC)
                        │
                        ▼
                  Task Router（调度输入）
                        │
                        ▼
          统一协议 TaskSpec/TaskResult/Heartbeat/Lease
                        │
        ┌───────────────┴────────────────┐
        ▼                                ▼
 Message Queue（pull/push）          SSH fallback
        ▼
 Worker Runtime（capabilities: review/security/sandbox）
```

## 角色定义

| Agent | 用途 | 触发条件 |
|-------|------|----------|
| Assistant | 资源紧张时协助处理拆分任务 | 本地负载 > 80%，任务队列堆积 |
| Reviewer | 代码审查、二次验证、优化建议 | 代码审查请求、安全审计 |
| Sandbox | 高风险操作隔离测试 | 危险命令、未知脚本 |

## 使用方法

### 启动 Control Plane API

```bash
python main.py api --host 0.0.0.0 --port 8080
```

### 任务路由测试

```bash
python main.py route "检查这段代码有没有bug"
python main.py route "运行这个脚本"
```

### 执行任务（统一协议）

```bash
python main.py exec "帮我检查代码" --priority high
```

### 完整测试

```bash
python main.py test
```

## 文件结构

```
multi-agent-framework/
├── contracts/
│   └── protocol.py         # TaskSpec/TaskResult/Heartbeat/Lease 协议
├── proto/
│   └── control_plane.proto # gRPC 协议草案
├── services/
│   ├── control-plane/      # 主 Agent API 服务
│   ├── worker-runtime/     # 从 Agent 执行服务
│   └── control_plane_loader.py
├── config/
│   └── remote-agent.json    # 远程 Agent 配置
├── scripts/
│   ├── task_router.py       # 任务路由器
│   └── remote_executor.py   # 远程执行器（Gateway/MQ/SSH 适配器）
├── main.py                 # 统一入口
└── README.md
```

## 配置

编辑 `config/remote-agent.json` 修改：
- 远程 Gateway 地址
- SSH 连接配置
- 风险关键词
- 触发条件
