#!/usr/bin/env python3
"""
多 Agent 协作框架 - 主控制器
Control Plane 负责接入/路由/策略，Data Plane 负责 worker 执行。
"""

import json
import sys
from pathlib import Path

# 添加项目目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from services.control_plane.control_plane import ControlPlane
from services.control_plane.task_protocol import TaskEnvelope


class MultiAgentController:
    def __init__(self):
        self.control_plane = ControlPlane()
        # 启动时注册两个默认 worker
        self.control_plane.worker_heartbeat(
            "worker-reviewer-1",
            capabilities={"review": "true", "sandbox": "false", "toolset": "python", "model": "bailian/MiniMax-M2.5"},
            cpu_usage=20,
            memory_usage=35,
            queue_depth=1,
            model_available=True,
        )
        self.control_plane.worker_heartbeat(
            "worker-sandbox-1",
            capabilities={"review": "false", "sandbox": "true", "toolset": "bash", "model": "bailian/MiniMax-M2.5"},
            cpu_usage=45,
            memory_usage=50,
            queue_depth=2,
            model_available=True,
        )

    def check_system_health(self) -> dict:
        """检查系统健康状态"""
        workers = self.control_plane.registry.list_alive()
        return {
            "control_plane": True,
            "worker_runtime": True,
            "alive_workers": len(workers),
            "workers": [w.worker_id for w in workers],
            "all_healthy": len(workers) > 0,
        }

    def execute_task(self, task: str, force_remote: str = None) -> dict:
        """通过统一 TaskEnvelope 入队并执行一次调度。"""
        payload = {"task": task}
        if force_remote == "reviewer":
            payload["required_review"] = True
        elif force_remote == "sandbox":
            payload["required_sandbox"] = True

        envelope = TaskEnvelope(task_type="generic", payload=payload)
        accepted = self.control_plane.submit_task(envelope)
        dispatch_result = self.control_plane.dispatch_once()
        return {
            "accepted": accepted,
            "dispatch": dispatch_result,
        }

    def test_full_pipeline(self) -> dict:
        """测试完整流程（路由 + 调度 + saga）"""
        tasks = [
            "检查这段代码有没有bug",
            "运行这个脚本",
            "git commit -m 'test'",
        ]
        results = []
        for task in tasks:
            result = self.execute_task(task)
            results.append({"task": task, "result": result})

        return {
            "health_check": self.check_system_health(),
            "pipeline_test": results,
            "saga_logs": self.control_plane.transition_logs(),
        }


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
                envelope = TaskEnvelope.from_task(task)
                controller.control_plane.submit_task(envelope)
                result = controller.control_plane.scheduler.route(envelope)
                print(json.dumps({
                    "task": task,
                    "worker": result.worker_id if result else None,
                    "matched_capabilities": result.capabilities if result else None,
                }, indent=2, ensure_ascii=False))
            else:
                print("Usage: python main.py route <task>")
        else:
            print(f"Unknown command: {cmd}")
            print("Available: health, test, exec, route")
    else:
        result = controller.check_system_health()
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
