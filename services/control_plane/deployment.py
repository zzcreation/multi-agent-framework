"""
部署管理模块 - 支持渐进发布、自动回滚
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DeploymentStrategy(str, Enum):
    """部署策略"""
    ROLLING = "rolling"
    BLUE_GREEN = "blue-green"
    CANARY = "canary"
    RECREATE = "recreate"


class DeploymentStatus(str, Enum):
    """部署状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    ROLLING_BACK = "rolling_back"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class DeploymentRecord:
    """部署记录"""
    deployment_id: str
    version: str
    strategy: DeploymentStrategy
    status: DeploymentStatus
    replicas: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DeploymentManager:
    """部署管理器 - 支持渐进发布和自动回滚"""

    def __init__(
        self,
        namespace: str = "openclaw-system",
        kubeconfig: str = None,
    ):
        self.namespace = namespace
        self.kubeconfig = kubeconfig
        self._deployments: Dict[str, DeploymentRecord] = {}

    def _run_kubectl(self, args: List[str], capture_output: bool = True, input_data: str = None) -> tuple:
        """执行 kubectl 命令"""
        cmd = ["kubectl"]
        if self.kubeconfig:
            cmd.extend(["--kubeconfig", self.kubeconfig])
        cmd.extend(args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                timeout=300,
                input=input_data,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", "Command timeout"
        except FileNotFoundError:
            return 1, "", "kubectl not found"
        except Exception as e:
            return 1, "", str(e)

    def create_deployment(
        self,
        name: str,
        image: str,
        replicas: int = 1,
        strategy: DeploymentStrategy = DeploymentStrategy.ROLLING,
    ) -> Optional[str]:
        """创建部署"""
        deployment_id = f"{name}-{int(time.time())}"

        record = DeploymentRecord(
            deployment_id=deployment_id,
            version=image,
            strategy=strategy,
            status=DeploymentStatus.PENDING,
            replicas=replicas,
        )

        # 构建部署 YAML
        manifest = self._build_deployment_manifest(name, image, replicas, strategy)

        # 应用部署 - 通过 stdin 传递 manifest
        returncode, stdout, stderr = self._run_kubectl([
            "apply", "-f", "-",
            "--namespace", self.namespace,
        ], input_data=manifest, capture_output=False)

        if returncode != 0:
            record.status = DeploymentStatus.FAILED
            record.error = stderr
            logger.error(f"Deployment failed: {stderr}")
        else:
            record.status = DeploymentStatus.IN_PROGRESS
            logger.info(f"Deployment {deployment_id} created")

        self._deployments[deployment_id] = record
        return deployment_id if record.status != DeploymentStatus.FAILED else None

    def _build_deployment_manifest(
        self,
        name: str,
        image: str,
        replicas: int,
        strategy: DeploymentStrategy,
    ) -> str:
        """构建部署 manifest"""
        # 简化版 manifest
        return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
  namespace: {self.namespace}
spec:
  replicas: {replicas}
  strategy:
    type: {strategy.value.capitalize()}
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      containers:
      - name: {name}
        image: {image}
        ports:
        - containerPort: 8080
"""

    def get_deployment_status(self, deployment_id: str) -> Optional[DeploymentRecord]:
        """获取部署状态"""
        return self._deployments.get(deployment_id)

    def check_rollout_status(self, name: str) -> str:
        """检查 rollout 状态"""
        returncode, stdout, stderr = self._run_kubectl([
            "rollout", "status", f"deployment/{name}",
            "--namespace", self.namespace,
            "--timeout=300s",
        ])
        return "success" if returncode == 0 else "failed"

    def rollback(self, name: str, revision: int = None) -> bool:
        """回滚到上一版本或指定版本"""
        args = ["rollout", "undo", f"deployment/{name}"]
        if revision:
            args.extend(["--to-revision", str(revision)])

        args.extend(["--namespace", self.namespace])

        returncode, stdout, stderr = self._run_kubectl(args)

        if returncode == 0:
            # 更新部署记录状态
            for dep in self._deployments.values():
                if name in dep.deployment_id:
                    dep.status = DeploymentStatus.ROLLING_BACK
            logger.info(f"Rollback initiated for {name}")
            return True

        logger.error(f"Rollback failed: {stderr}")
        return False

    def auto_rollback_on_failure(
        self,
        deployment_id: str,
        name: str,
        error_threshold: float = 0.1,
        check_interval: int = 30,
    ) -> bool:
        """自动回滚（当错误率超过阈值时）"""
        record = self._deployments.get(deployment_id)
        if not record:
            return False

        max_checks = 10  # 最多检查 10 次 (5分钟)

        for i in range(max_checks):
            # 获取 Pod 状态
            returncode, stdout, stderr = self._run_kubectl([
                "get", "pods",
                "-l", f"app={name}",
                "--namespace", self.namespace,
                "-o", "json",
            ])

            if returncode != 0:
                time.sleep(check_interval)
                continue

            try:
                pods = json.loads(stdout)
                total = len(pods.get("items", []))
                if total == 0:
                    continue

                # 计算失败率
                failed = sum(
                    1 for pod in pods.get("items", [])
                    if pod.get("status", {}).get("phase") in ["Failed", "Error"]
                )
                failure_rate = failed / total

                logger.info(f"Check {i+1}: failure_rate={failure_rate:.2%}")

                if failure_rate > error_threshold:
                    logger.warning(f"Failure rate {failure_rate:.2%} exceeds threshold, initiating rollback")
                    return self.rollback(name)

            except (json.JSONDecodeError, KeyError):
                pass

            time.sleep(check_interval)

        logger.warning(f"Auto-rollback check completed, no rollback triggered")
        return False

    def get_revisions(self, name: str) -> List[Dict]:
        """获取部署历史版本"""
        returncode, stdout, stderr = self._run_kubectl([
            "rollout", "history", f"deployment/{name}",
            "--namespace", self.namespace,
        ])

        # 解析输出 (简化版)
        revisions = []
        if returncode == 0:
            # 解析 revision 信息
            pass

        return revisions

    def scale(self, name: str, replicas: int) -> bool:
        """扩缩容"""
        returncode, stdout, stderr = self._run_kubectl([
            "scale", f"deployment/{name}",
            "--replicas", str(replicas),
            "--namespace", self.namespace,
        ])
        return returncode == 0

    def get_metrics(self, name: str) -> Dict[str, Any]:
        """获取部署指标"""
        returncode, stdout, stderr = self._run_kubectl([
            "get", "deployment", name,
            "--namespace", self.namespace,
            "-o", "json",
        ])

        if returncode != 0:
            return {}

        try:
            dep = json.loads(stdout)
            status = dep.get("status", {})

            return {
                "replicas": status.get("replicas", 0),
                "ready_replicas": status.get("readyReplicas", 0),
                "updated_replicas": status.get("updatedReplicas", 0),
                "available_replicas": status.get("availableReplicas", 0),
            }
        except json.JSONDecodeError:
            return {}


# 全局部署管理器实例
_deployment_manager: Optional[DeploymentManager] = None


def get_deployment_manager(
    namespace: str = "openclaw-system",
    kubeconfig: str = None,
) -> DeploymentManager:
    """获取全局部署管理器实例"""
    global _deployment_manager
    if _deployment_manager is None:
        _deployment_manager = DeploymentManager(namespace, kubeconfig)
    return _deployment_manager