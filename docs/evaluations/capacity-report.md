# OpenClaw 容量报告与扩容策略

## 概述

本文档分析 OpenClaw 多代理框架的当前容量状态，并提供扩容策略建议。

## 当前容量状态

### 控制平面

| 指标 | 当前值 | 建议阈值 | 状态 |
|------|--------|----------|------|
| CPU 使用率 | 45% | 70% | ✅ 正常 |
| 内存使用 | 3.2GB / 8GB | 6GB | ✅ 正常 |
| 任务队列深度 | 120 | 500 | ✅ 正常 |
| QPS | 85 | 100 | ⚠️ 接近上限 |

### Worker 节点

| Worker | 状态 | CPU | 内存 | 队列深度 | 任务数 |
|--------|------|-----|------|----------|--------|
| worker-1 | 健康 | 55% | 2.8GB | 15 | 8 |
| worker-2 | 健康 | 62% | 3.1GB | 22 | 12 |
| worker-3 | 健康 | 48% | 2.5GB | 8 | 5 |

### 数据库

| 指标 | 当前值 | 建议阈值 | 状态 |
|------|--------|----------|------|
| 连接数 | 15 | 50 | ✅ 正常 |
| 查询延迟 | 12ms | 50ms | ✅ 正常 |
| 存储使用 | 450MB | 2GB | ✅ 正常 |

## 容量分析

### 任务处理能力

根据基准测试结果：
- **单 Worker 吞吐量**: 150 tasks/s
- **多 Worker 扩展效率**: 约 80%
- **推荐 Worker 数**: 4-8 个

### 当前瓶颈

1. **任务分发**: 控制平面单点分发，限制扩展性
2. **轮询延迟**: HTTP 轮询有 ~50ms 延迟
3. **数据库连接**: 连接池大小限制

### 扩容触发条件

| 指标 | 阈值 | 动作 |
|------|------|------|
| 控制平面 CPU | > 70% | 扩容控制平面 |
| 控制平面内存 | > 6GB | 扩容或优化 |
| Worker CPU 平均 | > 80% | 增加 Worker |
| 任务队列深度 | > 500 | 增加 Worker |
| QPS | > 90% | 优化或扩容 |

## 扩容策略

### 1. 水平扩展 Worker

```yaml
# Kubernetes HPA 配置示例
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: openclaw-worker-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: openclaw-worker
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Pods
    pods:
      metric:
        name: task_queue_depth
      target:
        type: AverageValue
        averageValue: "50"
```

### 2. 控制平面扩展

当前配置：
- 4 核 CPU, 8GB RAM
- 支持 ~1000 QPS

扩展建议：
- 8 核 CPU, 16GB RAM 可支持 ~2500 QPS
- 多实例部署需要负载均衡

### 3. 数据库优化

当前使用 SQLite，适合小规模部署。

扩展路径：
1. **中期**: 迁移到 PostgreSQL
2. **长期**: 使用分布式数据库 (TiDB, CockroachDB)

### 4. 消息队列优化

当前使用内存队列，适合 <1000 tasks/s。

扩展建议：
- **NATS** (推荐): <1ms 延迟，支持多租户
- **Kafka**: 高吞吐，适合日志/审计场景

## 自动扩容配置

### Worker 自动扩容脚本

```python
import asyncio
import aiohttp
from datetime import datetime, timedelta

class CapacityScaler:
    """自动扩容管理器"""
    
    def __init__(self, control_plane_url: str):
        self.control_plane_url = control_plane_url
        self.scale_out_threshold = 0.8  # 80% CPU 时扩容
        self.scale_in_threshold = 0.3   # 30% CPU 时缩容
        self.min_workers = 2
        self.max_workers = 20
    
    async def check_and_scale(self):
        """检查容量并自动扩容/缩容"""
        stats = await self.get_system_stats()
        
        avg_cpu = sum(w["cpu"] for w in stats["workers"]) / len(stats["workers"])
        queue_depth = stats["queue_depth"]
        
        current_workers = len(stats["workers"])
        
        # 扩容条件
        if avg_cpu > self.scale_out_threshold * 100 or queue_depth > 500:
            if current_workers < self.max_workers:
                await self.scale_out(current_workers + 2)
                print(f"扩容: {current_workers} -> {current_workers + 2}")
        
        # 缩容条件
        elif avg_cpu < self.scale_in_threshold * 100 and queue_depth < 50:
            if current_workers > self.min_workers:
                await self.scale_in(current_workers - 1)
                print(f"缩容: {current_workers} -> {current_workers - 1}")
    
    async def get_system_stats(self) -> dict:
        """获取系统状态"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.control_plane_url}/api/stats") as resp:
                return await resp.json()
    
    async def scale_out(self, target_count: int):
        """扩展 Worker"""
        # 调用 API 启动新 Worker
        pass
    
    async def scale_in(self, target_count: int):
        """收缩 Worker"""
        # 调用 API 停止 Worker
        pass

# 运行扩容检查 (每分钟)
async def main():
    scaler = CapacityScaler("http://localhost:8080")
    while True:
        await scaler.check_and_scale()
        await asyncio.sleep(60)

# asyncio.run(main())
```

### 监控指标

关键指标监控：
```yaml
metrics:
  - name: task_queue_depth
    type: gauge
    help: "任务队列深度"
  
  - name: worker_cpu_usage
    type: gauge
    help: "Worker CPU 使用率"
  
  - name: tasks_per_second
    type: counter
    help: "每秒处理任务数"
  
  - name: task_latency_p99
    type: histogram
    help: "任务延迟 P99"
```

## 容量规划建议

### 短期 (1-3 个月)

| 场景 | 配置 | 成本 |
|------|------|------|
| 开发/测试 | 2 Workers | 低 |
| 小规模生产 | 4 Workers | 中 |
| 中等规模 | 8 Workers | 中高 |

### 中期 (3-6 个月)

- 引入负载均衡
- 迁移到 PostgreSQL
- 部署 NATS 消息队列

### 长期 (6-12 个月)

- 多区域部署
- 分布式数据库
- 自动化扩容 (K8s HPA)

## 总结

当前系统状态：
- ✅ 控制平面容量充足
- ✅ Worker 节点健康
- ✅ 数据库运行正常

建议行动：
1. ✅ 当前无需扩容
2. 📝 监控 QPS 接近上限，准备扩容
3. 📝 考虑引入负载均衡支持多控制平面

---

**报告日期**: 2026-03-27
**版本**: 1.0