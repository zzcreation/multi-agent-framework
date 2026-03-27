# 消息队列评估报告

## 概述

本文档评估了适合 OpenClaw 多代理框架的消息队列解决方案。

## 评估对象

- **NATS** - 轻量级、高性能消息系统
- **Apache Kafka** - 大规模分布式流平台

## 评估维度

| 维度 | NATS | Kafka |
|------|------|-------|
| 架构 | 简化发布/订阅 | 分区日志存储 |
| 延迟 | < 1ms | 2-5ms |
| 吞吐量 | 百万级/秒 | 百万级/秒 |
| 持久化 | 可选 | 必须 |
| 运维复杂度 | 低 | 高 |
| 多租户 | JetStream 支持 | 多租户插件 |
| 客户端支持 | 40+ 语言 | 很多语言 |

## OpenClaw 需求分析

### 当前场景

1. **任务队列** - Worker 从 Control Plane 拉取任务
2. **事件总线** - 各组件间的事件通知
3. **多租户隔离** - 需要租户级别的消息隔离

### 需求优先级

| 需求 | 优先级 | 说明 |
|------|--------|------|
| 低延迟 | 高 | 任务分发需要快速响应 |
| 简单运维 | 中 | 降低运维复杂度 |
| 多租户 | 高 | 支持多个租户隔离 |
| 持久化 | 低 | 任务队列可接受内存队列 |

## 详细对比

### NATS

**优点：**
- 极低的延迟（< 1ms）
- 部署简单，资源占用少
- 客户端库轻量
- 支持 JetStream（持久化、流式）

**缺点：**
- 持久化功能相对较新
- 生态系统小于 Kafka
- 企业级功能需要 NATS JetStream

**适用场景：**
- 低延迟任务分发
- 简单的发布/订阅
- 资源受限环境

### Apache Kafka

**优点：**
- 成熟的生态系统
- 强大的持久化和回溯能力
- 优秀的多租户支持
- 高吞吐量场景

**缺点：**
- 资源消耗大
- 运维复杂
- 延迟相对较高

**适用场景：**
- 大规模数据流处理
- 事件溯源
- 日志聚合

## 架构建议

### 推荐方案：NATS with JetStream

```
┌─────────────────────────────────────────────────────────┐
│                    OpenClaw Architecture                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   ┌─────────────┐      ┌─────────────┐                │
│   │  Control    │      │   Worker    │                │
│   │   Plane     │◄────►│   Nodes     │                │
│   └─────────────┘      └─────────────┘                │
│         │                    │                          │
│         ▼                    ▼                          │
│   ┌─────────────────────────────────────────────┐       │
│   │              NATS JetStream                  │       │
│   │  ┌─────────────┐  ┌─────────────────────┐  │       │
│   │  │ Task Queue  │  │   Event Bus         │  │       │
│   │  │ (durable)   │  │   (pub/sub)         │  │       │
│   │  └─────────────┘  └─────────────────────┘  │       │
│   └─────────────────────────────────────────────┘       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 实现方式

#### 1. 任务队列（Task Queue）

```python
# NATS JetStream 任务队列
js = jetstream.JetStream()
task_stream = js.stream("tasks")
consumer = task_stream.consumer("workers")
```

#### 2. 事件总线（Event Bus）

```python
# NATS 发布/订阅
nc = NATS()
await nc.subscribe("events.worker.*", callback=handler)
await nc.publish("events.task.completed", data)
```

### 多租户隔离

使用 NATS 账户隔离：

```
accounts: {
  tenant_A: {
    jetstream: true
    imports: [{ stream: "shared.tasks" }]
  }
  tenant_B: { ... }
}
```

## 实施计划

### 阶段 1: NATS 集成（2周）

1. 部署 NATS JetStream 集群
2. 实现任务队列生产者/消费者
3. 实现事件总线
4. 单元测试

### 阶段 2: 多租户支持（1周）

1. 配置 NATS 账户隔离
2. 实现租户级资源配额
3. 监控和告警

### 阶段 3: 监控和优化（1周）

1. 集成 Prometheus + Grafana
2. 性能基准测试
3. 文档编写

## 结论

**推荐选择：NATS with JetStream**

理由：
1. 满足低延迟需求（< 1ms）
2. 运维复杂度低
3. 支持多租户
4. 资源占用少
5. 足够支持当前和未来 1-2 年的规模

**备选方案：**
- 如果后续需要处理大规模数据流（> 10万/秒），可以考虑迁移到 Kafka
- 当前规模 NATS 完全足够

---

## 附录：配置示例

### NATS 配置文件（nats.conf）

```yaml
listen: 0.0.0.0:4222
jetstream: {
  store_dir: /data/jetstream
  max_memory_store: 1GB
  max_file_store: 10GB
}

accounts: {
  $G: {
    users: [{ user: "admin", password: "password" }]
  }
}
```

### Python 客户端使用示例

```python
import asyncio
import nats

async def main():
    nc = await nats.connect("nats://localhost:4222")
    js = nc.jetstream()
    
    # 发布任务
    await js.publish("tasks", b'{"task_id": "123", "payload": {...}}')
    
    # 订阅任务
    sub = await js.consume("tasks")
    async for msg in sub:
        await msg.ack()
        print(msg.data)

asyncio.run(main())
```

---

**评估人**: OpenClaw Agent  
**评估日期**: 2026-03-26  
**版本**: 1.0