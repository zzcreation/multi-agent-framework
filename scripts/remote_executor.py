#!/usr/bin/env python3
"""
远程 Agent 执行器
负责与远程 OpenClaw Gateway 通信，执行任务并获取结果
"""

import json
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config" / "remote-agent.json"

# 远程 OpenClaw 路径配置
REMOTE_NODE_PATH = "/home/zzc/.nvm/versions/node/v22.22.1/bin/node"
REMOTE_OPENCLAW_PATH = "/home/zzc/.nvm/versions/node/v22.22.1/bin/openclaw"
REMOTE_NVM_DIR = "/home/zzc/.nvm"

class RemoteExecutor:
    def __init__(self, config_path: str = None):
        self.config_path = config_path or CONFIG_PATH
        self.config = self._load_config()
        
    def _load_config(self) -> dict:
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_openclaw_cmd_prefix(self) -> str:
        """获取远程 OpenClaw 调用前缀"""
        return f'NVM_DIR={REMOTE_NVM_DIR} {REMOTE_NODE_PATH} {REMOTE_OPENCLAW_PATH}'
    
    def get_ssh_command(self) -> list:
        """获取 SSH 命令"""
        ssh = self.config.get('ssh_config', {})
        host = ssh.get('host', '192.168.130.33')
        user = ssh.get('user', 'zzc')
        port = ssh.get('port', 2222)
        return [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'ConnectTimeout=60',
            '-o', 'ServerAliveInterval=10',
            '-p', str(port),
            f'{user}@{host}'
        ]
    
    def check_remote_connection(self) -> bool:
        """检查远程连接"""
        try:
            result = subprocess.run(
                self.get_ssh_command() + ['echo', 'ok'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0 and 'ok' in result.stdout
        except Exception as e:
            print(f"连接检查失败: {e}", file=sys.stderr)
            return False
    
    def get_remote_status(self) -> dict:
        """获取远程 OpenClaw 状态"""
        ssh_cmd = self.get_ssh_command()
        
        # 获取远程 openclaw status
        cmd = ssh_cmd + [
            'NVM_DIR=/home/zzc/.nvm',
            REMOTE_NODE_PATH,
            REMOTE_OPENCLAW_PATH,
            'status'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                'connected': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr
            }
        except Exception as e:
            return {'connected': False, 'error': str(e)}
    
    def execute_on_remote(self, command: str) -> dict:
        """在远程主机执行命令"""
        ssh_cmd = self.get_ssh_command()
        
        # 使用远程 WSL2 的 OpenClaw 执行任务
        openclaw_cmd = self.get_openclaw_cmd_prefix()
        remote_cmd = f'''
export PATH=/home/zzc/.nvm/versions/node/v22.22.1/bin:$PATH
{command}
'''
        
        cmd = ssh_cmd + ['bash', '-c', remote_cmd]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': '执行超时'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_remote_openclaw(self) -> bool:
        """测试远程 OpenClaw 是否正常工作"""
        ssh_cmd = self.get_ssh_command()
        
        # 直接调用，不使用 bash -c
        cmd = ssh_cmd + [
            'NVM_DIR=/home/zzc/.nvm',
            REMOTE_NODE_PATH,
            REMOTE_OPENCLAW_PATH,
            '--version'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            output = result.stdout.strip()
            if result.returncode == 0 and output:
                print(f"远程 OpenClaw 版本: {output}")
                return True
            else:
                print(f"测试失败: returncode={result.returncode}, stdout={repr(result.stdout)}, stderr={repr(result.stderr)}", file=sys.stderr)
        except Exception as e:
            print(f"测试失败: {e}", file=sys.stderr)
        return False
    
    def execute_via_gateway_api(self, prompt: str, agent_type: str = "assistant") -> dict:
        """
        通过 OpenClaw Gateway HTTP API 调用远程 Agent
        
        Args:
            prompt: 任务提示词
            agent_type: Agent 类型 (assistant/reviewer/sandbox)
            
        Returns:
            执行结果字典
        """
        gateway = self.config.get('remote_gateway', '')
        
        # 将 ws:// 转换为 http://
        if gateway.startswith('ws://'):
            http_gateway = gateway.replace('ws://', 'http://')
        else:
            http_gateway = gateway
        
        # 构建请求
        url = f"{http_gateway}/api/agent/turn"
        
        payload = {
            "message": prompt,
            "agent": agent_type,
            "stream": False
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                result = response.read().decode('utf-8')
                return {
                    'success': True,
                    'result': json.loads(result),
                    'agent_type': agent_type
                }
        except urllib.error.URLError as e:
            return {
                'success': False,
                'error': f"Gateway API 调用失败: {str(e)}",
                'agent_type': agent_type
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'agent_type': agent_type
            }
    
    def execute_via_ssh_shell(self, command: str) -> dict:
        """
        通过 SSH Shell 执行命令（传统方式）
        """
        ssh_cmd = self.get_ssh_command()
        
        remote_cmd = f'''
export PATH=/home/zzc/.nvm/versions/node/v22.22.1/bin:$PATH
{command}
'''
        
        cmd = ssh_cmd + ['bash', '-c', remote_cmd]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode,
                'method': 'ssh_shell'
            }
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': '执行超时', 'method': 'ssh_shell'}
        except Exception as e:
            return {'success': False, 'error': str(e), 'method': 'ssh_shell'}
    
    def execute_task(self, task: str, agent_type: str = "assistant", prefer_api: bool = True) -> dict:
        """
        执行任务，自动选择执行方式
        
        Args:
            task: 任务描述
            agent_type: Agent 类型
            prefer_api: 是否优先使用 Gateway API
        """
        if prefer_api:
            # 优先尝试使用 Gateway API
            result = self.execute_via_gateway_api(task, agent_type)
            if result['success']:
                return result
        
        # Fallback 到 SSH Shell 方式
        openclaw_cmd = f'echo "{task.replace("\"", "\\\"").replace("\n", "\\n")}" | openclaw agent --model bailian/MiniMax-M2.5'
        return self.execute_via_ssh_shell(openclaw_cmd)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='远程 Agent 执行器')
    parser.add_argument('--check', action='store_true', help='检查远程连接')
    parser.add_argument('--status', action='store_true', help='获取远程状态')
    parser.add_argument('--test-openclaw', action='store_true', help='测试远程 OpenClaw')
    parser.add_argument('--exec', type=str, help='执行远程命令')
    
    args = parser.parse_args()
    executor = RemoteExecutor()
    
    if args.check:
        result = executor.check_remote_connection()
        print(f"远程连接: {'✅ 正常' if result else '❌ 失败'}")
        
    if args.status:
        result = executor.get_remote_status()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    if args.test_openclaw:
        result = executor.test_remote_openclaw()
        print(f"远程 OpenClaw: {'✅ 正常' if result else '❌ 失败'}")
        
    if args.exec:
        result = executor.execute_on_remote(args.exec)
        print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()