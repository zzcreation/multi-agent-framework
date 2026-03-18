# 多 Agent 协作框架

基于 OpenClaw 的多 Agent 分布式任务执行框架。

## 架构

```
用户 → 主 Agent (本地) → 任务路由器 → 分发到合适的执行环境
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
               本地执行        远程 Assistant    远程 Sandbox
                                                  远程 Reviewer
```

## 角色定义

| Agent | 用途 | 触发条件 |
|-------|------|----------|
| Assistant | 资源紧张时协助处理拆分任务 | 本地负载 > 80%，任务队列堆积 |
| Reviewer | 代码审查、二次验证、优化建议 | 代码审查请求、安全审计 |
| Sandbox | 高风险操作隔离测试 | 危险命令、未知脚本 |

## 使用方法

### 检查系统健康

```bash
python main.py health
```

### 任务路由测试

```bash
python main.py route "检查这段代码有没有bug"
python main.py route "运行这个脚本"
```

### 执行任务

```bash
python main.py exec "帮我检查代码"
```

### 完整测试

```bash
python main.py test
```

## 文件结构

```
multi-agent-framework/
├── config/
│   └── remote-agent.json    # 远程 Agent 配置
├── scripts/
│   ├── task_router.py       # 任务路由器
│   └── remote_executor.py   # 远程执行器
├── main.py                 # 主控制器
└── README.md
```

## 配置

编辑 `config/remote-agent.json` 修改：
- 远程 Gateway 地址
- SSH 连接配置
- 风险关键词
- 触发条件