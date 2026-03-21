#!/usr/bin/env python3
"""
多 Agent 协作框架 - 主控制器
负责协调本地和远程 Agent 的任务执行
"""

import json
import subprocess
import sys
from pathlib import Path

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from scripts.task_router import TaskRouter
from scripts.remote_executor import RemoteExecutor

class MultiAgentController:
    def __init__(self):
        self.router = TaskRouter()
        self.executor = RemoteExecutor()
        
    def check_system_health(self) -> dict:
        """检查系统健康状态"""
        health = {
            'local_connection': True,  # 本地始终可达
            'remote_ssh': self.executor.check_remote_connection(),
            'remote_openclaw': self.executor.test_remote_openclaw() if self.executor.check_remote_connection() else False
        }
        health['all_healthy'] = all(health.values())
        return health
    
    def execute_task(self, task: str, force_remote: str = None) -> dict:
        """
        执行任务，自动选择执行环境
        
        Args:
            task: 任务描述
            force_remote: 强制使用远程 Agent (assistant/reviewer/sandbox)
        """
        # 1. 路由决策
        if force_remote:
            target = force_remote
        else:
            route_result = self.router.route(task)
            target = route_result['target']
        
        # 2. 执行任务
        if target == 'local':
            return {
                'executed_by': 'local',
                'result': '本地执行（功能未实现）',
                'task': task
            }
        else:
            # 远程执行 - 使用 Gateway API 调用远程 Agent
            # 优先使用 API 方式，失败则 fallback 到 SSH
            result = self.executor.execute_task(task, agent_type=target, prefer_api=True)
            
            # 检查是否需要回退到 SSH
            if not result.get('success', False) and 'Gateway API' in result.get('error', ''):
                # API 失败，使用 SSH Shell 方式
                remote_cmd = self._build_openclaw_command(task, target)
                result = self.executor.execute_on_remote(remote_cmd)
                result['method'] = 'ssh_shell_fallback'
            
            return {
                'executed_by': f'remote_{target}',
                'result': result,
                'task': task,
                'gateway': self.router.get_remote_gateway(),
                'method': result.get('method', 'gateway_api')
            }
    
    def _build_openclaw_command(self, task: str, agent_type: str) -> str:
        """构建远程 OpenClaw 命令"""
        prompt = self.router.build_remote_task(agent_type, task)
        
        # 使用 openclaw agent 命令执行任务
        # 这里需要根据实际的 OpenClaw API 来调整
        escaped_prompt = prompt.replace('"', '\\"').replace('\n', '\\n')
        
        cmd = f'echo "{escaped_prompt}" | openclaw agent --model bailian/MiniMax-M2.5'
        
        return cmd
    
    def test_full_pipeline(self) -> dict:
        """测试完整流程"""
        results = {
            'health_check': self.check_system_health(),
            'router_test': None,
            'remote_execution_test': None
        }
        
        # 测试路由器
        test_tasks = [
            "检查这段代码有没有bug",
            "运行这个脚本",
            "git commit -m 'test'"
        ]
        
        router_results = []
        for task in test_tasks:
            route = self.router.route(task)
            router_results.append({
                'task': task,
                'target': route['target'],
                'risk': route['risk_level']
            })
        
        results['router_test'] = router_results
        
        # 测试远程执行
        if results['health_check']['remote_openclaw']:
            test_result = self.executor.execute_on_remote('echo "Remote test OK"')
            results['remote_execution_test'] = test_result
        
        return results

def main():
    controller = MultiAgentController()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == 'health':
            result = controller.check_system_health()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
        elif cmd == 'test':
            result = controller.test_full_pipeline()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
        elif cmd == 'exec':
            task = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else ''
            if task:
                result = controller.execute_task(task)
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print("Usage: python main.py exec <task>")
        
        elif cmd == 'route':
            task = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else ''
            if task:
                result = controller.router.route(task)
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print("Usage: python main.py route <task>")
        else:
            print(f"Unknown command: {cmd}")
            print("Available: health, test, exec, route")
    else:
        # 默认显示健康状态
        result = controller.check_system_health()
        print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()