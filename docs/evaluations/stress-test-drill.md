# OpenClaw 压测与故障演练

## 概述

本文档描述 OpenClaw 的压力测试和故障演练方案。

## 压力测试

### 测试目标

1. 验证系统在高负载下的稳定性
2. 确定系统瓶颈和容量上限
3. 验证自动扩容机制
4. 测试故障恢复能力

### 测试场景

#### 场景 1: 基础负载测试

```python
import asyncio
import aiohttp
import time
from datetime import datetime

async def basic_load_test(base_url: str, duration: int = 60):
    """基础负载测试"""
    print(f"[{datetime.now()}] 开始基础负载测试...")
    
    results = {
        "total_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0,
        "latencies": []
    }
    
    start_time = time.time()
    tasks = []
    
    async with aiohttp.ClientSession() as session:
        while time.time() - start_time < duration:
            # 持续发送请求
            task = asyncio.create_task(send_request(session, base_url, results))
            tasks.append(task)
            
            # 控制发送速率
            await asyncio.sleep(0.01)  # 100 req/s
    
    await asyncio.gather(*tasks)
    
    # 输出结果
    elapsed = time.time() - start_time
    print(f"总请求数: {results['total_requests']}")
    print(f"成功: {results['successful_requests']}")
    print(f"失败: {results['failed_requests']}")
    print(f"QPS: {results['total_requests']/elapsed:.2f}")
    
    return results

async def send_request(session, base_url, results):
    """发送单个请求"""
    results["total_requests"] += 1
    try:
        async with session.post(
            f"{base_url}/api/tasks",
            json={"task": "load_test", "priority": 1}
        ) as resp:
            if resp.status == 200:
                results["successful_requests"] += 1
            else:
                results["failed_requests"] += 1
    except Exception as e:
        results["failed_requests"] += 1
```

#### 场景 2: 峰值负载测试

```python
async def peak_load_test(base_url: str, peak_concurrency: int = 1000):
    """峰值负载测试 - 模拟突发流量"""
    print(f"[{datetime.now()}] 开始峰值负载测试 (并发: {peak_concurrency})...")
    
    # 预热
    await warm_up(base_url, 100)
    
    # 峰值
    start = time.time()
    tasks = []
    async with aiohttp.ClientSession() as session:
        for i in range(peak_concurrency):
            task = asyncio.create_task(send_request(session, base_url, {}))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    elapsed = time.time() - start
    
    print(f"峰值测试完成:")
    print(f"  并发数: {peak_concurrency}")
    print(f"  耗时: {elapsed:.2f}s")
    print(f"  QPS: {peak_concurrency/elapsed:.2f}")
```

#### 场景 3: 持续负载测试

```python
async def sustained_load_test(base_url: str, duration: int = 3600):
    """持续负载测试 - 1小时"""
    print(f"[{datetime.now()}] 开始持续负载测试 ({duration}s)...")
    
    # 每分钟采样
    samples = []
    start_time = time.time()
    
    for minute in range(duration // 60):
        minute_start = time.time()
        
        # 1分钟内持续发送
        tasks = []
        async with aiohttp.ClientSession() as session:
            for _ in range(6000):  # ~100 req/s
                task = asyncio.create_task(send_request(session, base_url, {}))
                tasks.append(task)
                await asyncio.sleep(0.01)
            
            await asyncio.gather(*tasks, return_exceptions=True)
        
        minute_elapsed = time.time() - minute_start
        samples.append(6000 / minute_elapsed)
        
        print(f"  第 {minute+1} 分钟: QPS = {samples[-1]:.2f}")
    
    print(f"平均 QPS: {sum(samples)/len(samples):.2f}")
    print(f"最小 QPS: {min(samples):.2f}")
    print(f"最大 QPS: {max(samples):.2f}")
```

## 故障演练

### 故障类型

1. **Worker 故障**: Worker 节点宕机
2. **网络故障**: 网络分区、延迟增加
3. **资源耗尽**: CPU/内存耗尽
4. **依赖故障**: 数据库、消息队列不可用

### 故障注入

#### 1. Worker 故障注入

```python
import subprocess
import signal
import time

class WorkerFailureInjector:
    """Worker 故障注入器"""
    
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.original_pid = None
    
    def kill_worker(self):
        """模拟 Worker 崩溃"""
        print(f"注入故障: 杀死 Worker {self.worker_id}")
        
        # 找到 Worker 进程并杀死
        result = subprocess.run(
            ["pgrep", "-f", f"worker.{self.worker_id}"],
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            pid = int(result.stdout.strip().split()[0])
            os.kill(pid, signal.SIGKILL)
            print(f"Worker {self.worker_id} (PID: {pid}) 已终止")
    
    def network_partition(self, duration: int = 30):
        """模拟网络分区"""
        print(f"注入故障: 网络分区 {duration}s")
        
        # 使用 iptables 模拟网络隔离
        subprocess.run([
            "iptables", "-A", "INPUT", "-p", "tcp",
            "--dport", "8080", "-j", "DROP"
        ])
        
        time.sleep(duration)
        
        # 恢复
        subprocess.run(["iptables", "-F"])
        print("网络已恢复")
    
    def resource_exhaustion(self, resource_type: str = "cpu"):
        """模拟资源耗尽"""
        print(f"注入故障: {resource_type} 耗尽")
        
        if resource_type == "cpu":
            # 启动 CPU 密集型进程
            subprocess.Popen(["stress", "--cpu", "4", "-t", "60s"])
        elif resource_type == "memory":
            # 消耗内存
            subprocess.Popen(["stress", "--vm", "2", "--vm-bytes", "2G", "-t", "60s"])
```

#### 2. 数据库故障注入

```python
class DatabaseFailureInjector:
    """数据库故障注入"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def corrupt_database(self):
        """模拟数据库损坏"""
        print("注入故障: 数据库损坏")
        
        # 随机修改数据库文件
        with open(self.db_path, "r+b") as f:
            f.seek(0)
            f.write(b"CORRUPTED")
    
    def lock_database(self):
        """模拟数据库锁定"""
        print("注入故障: 数据库锁定")
        
        # 创建长时间锁
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("BEGIN EXCLUSIVE")
        
        # 保持锁定 30 秒
        time.sleep(30)
        conn.close()
    
    def network_delay(self, delay_ms: int = 5000):
        """模拟数据库延迟"""
        print(f"注入故障: 数据库延迟 {delay_ms}ms")
        
        # 使用 tc 模拟延迟
        subprocess.run([
            "tc", "qdisc", "add", "dev", "eth0", "root",
            "netem", "delay", f"{delay_ms}ms"
        ])
```

### 故障恢复测试

```python
async def test_failover_recovery():
    """测试故障转移恢复"""
    print("[测试] 故障转移恢复...")
    
    # 1. 提交任务
    task_id = await submit_task("important_task")
    print(f"  任务已提交: {task_id}")
    
    # 2. 注入 Worker 故障
    injector = WorkerFailureInjector("worker-1")
    injector.kill_worker()
    
    # 3. 等待故障检测 (应该 < 2s)
    await asyncio.sleep(3)
    
    # 4. 验证任务被重新调度
    status = await get_task_status(task_id)
    
    if status == "SUCCEEDED":
        print("  ✅ 故障恢复成功 - 任务自动重试并完成")
    else:
        print(f"  ❌ 故障恢复失败 - 任务状态: {status}")
    
    # 5. 验证恢复时间 < 10s
    recovery_time = await measure_recovery_time()
    print(f"  恢复时间: {recovery_time:.2f}s")
    
    assert recovery_time < 10, "恢复时间超过 10s"
```

## 测试报告

### 压力测试结果记录

```markdown
## 测试结果

### 基础负载测试
| 指标 | 结果 | 状态 |
|------|------|------|
| QPS | 150 | ✅ |
| P99 延迟 | 15ms | ✅ |
| 成功率 | 99.9% | ✅ |

### 峰值负载测试
| 并发数 | QPS | 成功率 |
|--------|-----|--------|
| 100 | 145 | 99.9% |
| 500 | 138 | 99.5% |
| 1000 | 120 | 98.0% |

### 故障恢复测试
| 场景 | 恢复时间 | 状态 |
|------|----------|------|
| Worker 故障 | 3.5s | ✅ |
| 网络分区 | 5.2s | ✅ |
| 数据库锁定 | 8.1s | ✅ |
```

---

**维护者**: OpenClaw Team
**版本**: 1.0