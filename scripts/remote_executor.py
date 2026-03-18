#!/usr/bin/env python3
"""
远程 Agent 执行器
负责与远程 OpenClaw Gateway 通信，执行任务并获取结果
"""

import json
import subprocess
import sys
import time
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config" / "remote-agent.json"

class RemoteExecutor:
    def __init__(self, config_path: str = None):
        self.config_path = config_path or CONFIG_PATH
        self.config = self._load_config()
        
    def _load_config(self) -> dict:
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_ssh_command(self) -> list:
        """获取 SSH 命令"""
        ssh = self.config.get('ssh_config', {})
        return [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'ConnectTimeout=60',
            '-o', 'ServerAliveInterval=10',
            ssh.get('user', 'zzc'),
            '-p', str(ssh.get('port', 2222)),
            ssh.get('host', '192.168.130.33')
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
            'bash', '-c',
            'export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && openclaw status'
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
        remote_cmd = f'''
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
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
        
        cmd = ssh_cmd + [
            'bash', '-c',
            'export NVM_DIR="$HOME/.nvm" && [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" && openclaw --version'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                print(f"远程 OpenClaw 版本: {result.stdout.strip()}")
                return True
        except Exception as e:
            print(f"测试失败: {e}", file=sys.stderr)
        return False

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