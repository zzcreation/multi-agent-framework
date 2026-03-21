# 多 Agent 协作框架 - 长期计划

> 创建时间：2026-03-18
> 最后更新：2026-03-20 09:02 (cron检查 - 长期计划)
> 计划ID: LONGTERM_2026_01

## 目标

建立以本地 OpenClaw 为主 Agent，远程 WSL2 Ubuntu 为从 Agent 的多 Agent 协作系统。

---

## 计划阶段

### 阶段 1：基础设施搭建 ✅ 已完成
- [x] 远程主机安装 WSL2 Ubuntu
- [x] 安装 Node.js v22.22.1
- [x] 安装 OpenClaw 2026.3.13
- [x] 配置 Gateway (lan 模式，端口 18789)
- [x] 端口转发 (2222 SSH, 18789 Gateway)

### 阶段 2：主从架构设计 ✅ 已完成
- [x] 设计通信协议
- [x] 定义任务分发策略
- [x] 设计状态同步机制

### 阶段 3：框架实现 ✅ 已完成 (2026-03-19)
- [x] 任务分发脚本
- [x] 风险评估逻辑
- [x] 远程执行器
- [x] **真正通过 OpenClaw API 调用远程 Agent** (使用 `openclaw agent --message` 命令)
- [x] **实现结果回传机制** (通过 JSON 输出返回结构化结果)
- [x] **测试完整流程** (远程 Agent 响应验证通过 ✅)

> 验证测试 (2026-03-19 06:01):
> - 远程连接: ✅ SSH 正常
> - 远程 OpenClaw: ✅ 2026.3.13
> - 远程执行: ✅ 成功调用 reviewer agent
> - 结果回传: ✅ JSON 结构化输出

### 阶段 4：优化与生产 🔄 进行中 (开始时间: 2026-03-19)

#### 4.1 错误处理增强 ✅ 已完成 (2026-03-20)
> 执行任务：
> 1. ✅ 读取 `scripts/remote_executor.py` 检查现有错误处理
> 2. ✅ 在 SSH 连接部分添加 try-except 和重试逻辑（with_retry 装饰器）
> 3. ✅ 添加命令执行超时检测（timeout 参数）
> 4. ✅ 添加 JSON 解析失败的异常处理（_parse_agent_result + _try_extract_json）
> 5. ✅ 添加日志记录（logging 模块，日志写入 /tmp/remote_executor.log）

- [x] SSH 连接异常处理
- [x] 命令执行超时处理
- [x] 结果解析失败处理
- [x] 日志记录完善

> 实现细节：
> - 添加 `with_retry` 装饰器，支持自定义重试条件
> - `check_remote_connection()` 增加重试逻辑（默认3次）
> - `_parse_agent_result()` 增强 JSON 解析，支持部分提取
> - 全方法添加 logging 日志记录
> - 日志文件：`/tmp/remote_executor.log`

#### 4.2 监控面板 ✅ 已完成 (2026-03-21)
> 执行任务：
> 1. ✅ 检查 scripts/monitor_dashboard.py 是否存在
> 2. ✅ 验证监控面板依赖（flask, psutil）
> 3. ✅ 测试系统健康状态获取（CPU、内存、磁盘、Gateway）
> 4. ✅ 测试远程 Agent 状态监控（SSH 连接检测）
> 5. ✅ 测试任务执行统计（日志文件读取）

- [x] 系统健康状态展示（CPU、内存、磁盘、Gateway 状态）
- [x] 远程 Agent 状态监控（SSH 连接、OpenClaw 版本）
- [x] 任务执行统计（日志分析）

> 实现细节：
> - Flask 网页面板，访问地址 http://localhost:8877
> - API 接口 /api/status 返回 JSON 状态
> - 实时显示系统资源使用情况
> - 远程 Agent SSH 连接状态检测
> - 从 /tmp/remote_executor.log 读取任务执行统计

#### 4.3 性能调优 ✅ 已完成 (2026-03-21)
> 执行任务：
> 1. ✅ 添加 SSH 连接池 (SSHConnectionPool) 实现连接复用
> 2. ✅ 添加 @cached 装饰器支持 TTL 缓存
> 3. ✅ 添加并发执行方法 execute_tasks_parallel()
> 4. ✅ 添加缓存状态获取 get_cached_remote_status()
> 5. ✅ 添加技能列表缓存 get_remote_skills()

- [x] SSH 连接复用（SSHConnectionPool 持久连接）
- [x] 并发任务支持（ThreadPoolExecutor，最多 3 并发）
- [x] 缓存优化（@cached 装饰器，TTL 30-60 秒）

> 实现细节：
> - SSHConnectionPool: 复用 SSH 会话，连接保持 5 分钟
> - @cached(ttl=300): 带 TTL 的缓存装饰器
> - execute_tasks_parallel(): 并发执行多任务
> - get_cached_remote_status(): 缓存 30 秒的远程状态
> - get_remote_skills(): 缓存 60 秒的技能列表

#### 4.4 文档化 ✅ 已完成 (2026-03-21)
> 执行任务：
> 1. ✅ 创建 API 文档 (docs/API.md)
> 2. ✅ 创建使用说明 (docs/USAGE.md)
> 3. ✅ 创建部署指南 (docs/DEPLOY.md)

- [x] API 文档（RemoteExecutor 类、方法、配置）
- [x] 使用说明（快速开始、任务执行、错误处理）
- [x] 部署指南（系统要求、部署步骤、常见问题）

> 文档位置：
> - `docs/API.md` - API 参考文档
> - `docs/USAGE.md` - 使用说明
> - `docs/DEPLOY.md` - 部署指南

> **当前状态**：阶段4.4 文档化已完成，长期计划全部完成 🎉

---

## 角色定义

| Agent | 用途 | 触发条件 |
|-------|------|----------|
| main (本地) | 本地主 Agent，处理日常任务 | 默认 |
| xiaoqi-remote | 远程专属 Agent，小骐的远程化身 | 通过 SSH 调用 |
| Assistant | 资源紧张时协助处理拆分任务 | 本地负载 > 80%，任务队列堆积 |
| Reviewer | 代码审查、二次验证、优化建议 | 代码审查请求 |
| Sandbox | 高风险操作隔离测试 | 危险命令、未知脚本 |

---

## 风险评估规则

### 高风险 → sandbox
- `rm -rf`, `dd if=`, `:(){:|:&};:` ( Fork 炸弹)
- `curl | bash`, `wget | bash`
- `eval`, `exec`, `system()`, `shell_exec()`
- 管道执行: `| bash`, `| sh`

### 中风险 → 本地
- `sudo`, `apt install`, `pip install`
- `docker`, `kill`, `pkill`

### 低风险 → local/reviewer
- `git`, `cat`, `ls`, `cd`
- 代码检查、优化请求

---

## Git 提交记录

| 提交 | 说明 |
|------|------|
| e13ff4b | feat: 初始化多 Agent 协作框架 |
| 258f90b | fix: 调整 SSH 超时配置 |
| d60cbf2 | fix: 改进高风险命令检测 |
| 8ea050c | test: 添加测试脚本 |
| xxxxxxx | feat: 实现远程 OpenClaw agent 调用，结果 JSON 回传 |
| xxxxxxx | fix: 修正 agent_id 映射，测试通过 |

---

## 实现细节

### 远程执行方式
通过 SSH 在远程主机执行 `openclaw agent --message "<task>" --agent xiaoqi-remote --json` 命令，实现真正的远程 Agent 调用。

### 结果回传
- 结构化 JSON 输出
- 包含 payloads (文本回复), meta (执行元数据)
- 包含 durationMs, model, provider 等信息

---

## 下一步行动

1. ~~完善远程执行器，真正通过 OpenClaw API调用远程 Agent~~ ✅ 已完成 (2026-03-19)
2. ~~实现结果回传机制~~ ✅ 已完成 (2026-03-19)
3. ~~测试完整流程~~ ✅ 已完成 (2026-03-19)
4. 进入阶段4：优化与生产
   - 增强错误处理
   - 添加监控面板
   - 性能调优

---

*此文件由定时任务每 3 小时检查并更新进度*