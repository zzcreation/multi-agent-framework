# 部署指南

## 系统要求

### 本地环境
- Python 3.8+
- OpenClaw 2026.3.13+
- SSH 客户端

### 远程环境 (WSL2 Ubuntu)
- Ubuntu 20.04+ (WSL2)
- Node.js v22.22.1
- OpenClaw 2026.3.13
- 网络可达（端口 2222 SSH, 18789 Gateway）

## 部署步骤

### 1. 远程服务器设置

#### 1.1 安装 WSL2 Ubuntu

```powershell
wsl --install -d Ubuntu
```

#### 1.2 安装 Node.js

```bash
# 安装 nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# 安装 Node.js
nvm install 22.22.1
nvm use 22.22.1
```

#### 1.3 安装 OpenClaw

```bash
# 安装 OpenClaw
npm install -g openclaw

# 验证安装
openclaw --version
```

#### 1.4 配置 Gateway

```bash
# 启动 Gateway（lan 模式）
openclaw gateway start --mode lan --port 18789
```

#### 1.5 配置 SSH 端口转发

在 Windows 主机上配置端口转发：

```powershell
# 以管理员身份运行
netsh interface portproxy add v4tov4 listenport=2222 connectport=22 connectaddress=127.0.0.1
```

### 2. 本地环境配置

#### 2.1 克隆项目

```bash
git clone <repo-url>
cd multi-agent-framework
```

#### 2.2 安装依赖

```bash
pip install flask psutil
```

#### 2.3 配置

编辑 `config/remote-agent.json`：

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

**注意**：将 `host` 改为远程服务器的 IP 地址。

#### 2.4 测试连接

```bash
python scripts/remote_executor.py --check
python scripts/remote_executor.py --test-openclaw
```

### 3. 启动服务

#### 3.1 监控面板（可选）

```bash
cd scripts
python monitor_dashboard.py
# 访问 http://localhost:8877
```

#### 3.2 在 Python 中使用

```python
from scripts.remote_executor import RemoteExecutor

executor = RemoteExecutor()
result = executor.execute_task("你好", agent_type="assistant")
print(result)
```

## 验证部署

运行以下命令验证部署是否成功：

```bash
# 1. 检查 SSH 连接
python scripts/remote_executor.py --check

# 2. 测试 OpenClaw
python scripts/remote_executor.py --test-openclaw

# 3. 获取远程状态
python scripts/remote_executor.py --status
```

预期输出：
```
✅ 远程连接正常
远程 OpenClaw: ✅ 正常
{"connected": true, ...}
```

## 防火墙配置

### 远程服务器

```bash
# 开放必要端口
sudo ufw allow 22    # SSH
sudo ufw allow 18789  # Gateway
```

### Windows 主机

确保 Windows 防火墙允许：
- SSH (端口 2222)
- Gateway (端口 18789)

## 常见问题

### Q: SSH 连接失败

A: 检查：
1. 远程服务器 SSH 服务是否运行
2. 端口转发是否正确配置
3. 用户名和密码是否正确

### Q: Gateway 连接失败

A: 检查：
1. 远程 Gateway 是否启动：`openclaw gateway status`
2. 端口 18789 是否可达
3. 防火墙是否阻止

### Q: 任务执行超时

A: 检查：
1. 网络延迟
2. 远程服务器负载
3. 任务是否过于复杂

## 更新升级

```bash
# 更新本地代码
git pull

# 更新远程 OpenClaw
ssh -p 2222 zzc@192.168.130.33
npm update -g openclaw
```

## 卸载

```bash
# 停止 Gateway
openclaw gateway stop

# 移除 SSH 端口转发
netsh interface portproxy delete v4tov4 listenport=2222
```