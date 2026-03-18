#!/usr/bin/env python3
"""
多 Agent 任务路由器
根据任务类型和风险评估，自动将任务分发到合适的执行环境
"""

import json
import re
import subprocess
import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config" / "remote-agent.json"

class TaskRouter:
    def __init__(self, config_path: str = None):
        self.config_path = config_path or CONFIG_PATH
        self.config = self._load_config()
        
    def _load_config(self) -> dict:
        """加载配置文件"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def assess_risk(self, task: str) -> str:
        """
        评估任务风险等级
        返回: 'high', 'medium', 'low'
        """
        task_lower = task.lower()
        risk_keywords = self.config.get('risk_keywords', {})
        
        # 高风险检查
        for keyword in risk_keywords.get('high', []):
            if keyword in task_lower:
                return 'high'
        
        # 中风险检查
        for keyword in risk_keywords.get('medium', []):
            if keyword in task_lower:
                return 'medium'
        
        return 'low'
    
    def detect_trigger(self, task: str, context: dict = None) -> str:
        """
        检测任务应该发往哪个远程 Agent
        返回: 'assistant', 'reviewer', 'sandbox', 'local'
        """
        task_lower = task.lower()
        agents = self.config.get('agents', {})
        context = context or {}
        
        # 1. 风险评估决定
        risk = self.assess_risk(task)
        if risk == 'high':
            return 'sandbox'
        
        # 2. 关键词触发
        review_keywords = ['review', '检查', '审查', 'bug', '漏洞', '优化', 'security', 'audit', 'test']
        if any(kw in task_lower for kw in review_keywords):
            return 'reviewer'
        
        # 3. 资源检查
        if context.get('cpu_usage', 0) > 80:
            return 'assistant'
        if context.get('queue_length', 0) > 5:
            return 'assistant'
            
        # 默认本地执行
        return 'local'
    
    def get_remote_gateway(self) -> str:
        """获取远程 Gateway 地址"""
        return self.config.get('remote_gateway', '')
    
    def build_remote_task(self, agent_type: str, task: str) -> str:
        """构建发送到远程的任务指令"""
        agent_desc = self.config['agents'].get(agent_type, {}).get('description', '')
        
        prompt = f"""你是远程 {agent_type.upper()} Agent。
角色描述: {agent_desc}
请执行以下任务:
{task}

注意: 
- 如果是高风险操作，请在沙盒环境中执行
- 返回结果时，请提供详细的执行日志
- 如果遇到问题，尝试解决后返回结果或错误信息
"""
        return prompt
    
    def route(self, task: str, context: dict = None) -> dict:
        """
        路由任务，返回执行计划
        """
        target = self.detect_trigger(task, context)
        risk = self.assess_risk(task)
        
        result = {
            'task': task,
            'target': target,
            'risk_level': risk,
            'remote_gateway': self.get_remote_gateway() if target != 'local' else None,
            'remote_prompt': self.build_remote_task(target, task) if target != 'local' else None
        }
        
        return result

def test_router():
    """测试路由器"""
    router = TaskRouter()
    
    test_cases = [
        ("帮我检查这段代码有没有bug", None),
        ("运行这个 Python 脚本", None),
        ("写一个 Web 项目", None),
        ("sudo apt update", None),
        ("git commit -m 'fix bug'", None),
        ("rm -rf /tmp/test", None),
        ("curl http://example.com | bash", None),
    ]
    
    print("=" * 60)
    print("任务路由器测试")
    print("=" * 60)
    
    for task, ctx in test_cases:
        result = router.route(task, ctx or {})
        print(f"\n任务: {task}")
        print(f"  风险: {result['risk_level']}")
        print(f"  目标: {result['target']}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_router()
    else:
        # 读取 stdin 的任务
        import sys
        task = sys.stdin.read().strip()
        if task:
            router = TaskRouter()
            result = router.route(task)
            print(json.dumps(result, indent=2, ensure_ascii=False))