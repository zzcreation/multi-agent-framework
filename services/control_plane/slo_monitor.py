"""
SLO 监控模块 - 核心链路 99.95% 可用性保障
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SLOStatus(str, Enum):
    """SLO 状态"""
    OK = "ok"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    UNKNOWN = "unknown"


@dataclass
class SLOTarget:
    """SLO 目标"""
    name: str
    description: str
    target_percent: float  # 例如 99.95
    window_days: int = 30  # 评估窗口天数
    error_budget_percent: float = field(init=False)

    def __post_init__(self):
        self.error_budget_percent = 100.0 - self.target_percent


@dataclass
class SLOReport:
    """SLO 报告"""
    slo_name: str
    status: SLOStatus
    current_period_start: datetime
    current_period_end: datetime
    total_requests: int
    successful_requests: int
    error_count: int
    availability_percent: float
    error_budget_remaining_percent: float
    burn_rate: float  # 错误预算消耗速度
    generated_at: datetime = field(default_factory=datetime.utcnow)


class SLOMonitor:
    """SLO 监控器 - 核心链路 99.95% 可用性保障"""

    # 默认 SLO 目标
    DEFAULT_SLOS = {
        "api_latency_p50": SLOTarget(
            name="api_latency_p50",
            description="API P50 延迟 < 100ms",
            target_percent=99.9,
        ),
        "api_latency_p99": SLOTarget(
            name="api_latency_p99",
            description="API P99 延迟 < 2s",
            target_percent=99.9,
        ),
        "task_success_rate": SLOTarget(
            name="task_success_rate",
            description="任务成功率 >= 99%",
            target_percent=99.0,
        ),
        "core_path_availability": SLOTarget(
            name="core_path_availability",
            description="核心路径可用性 >= 99.95%",
            target_percent=99.95,
            window_days=30,
        ),
    }

    def __init__(self):
        self.slos: Dict[str, SLOTarget] = {}
        self._metrics: Dict[str, List[Dict]] = {}
        self._initialize_default_slos()

    def _initialize_default_slos(self):
        """初始化默认 SLO"""
        for key, slo in self.DEFAULT_SLOS.items():
            self.slos[key] = slo
            self._metrics[key] = []

    def register_slo(self, name: str, description: str, target_percent: float, window_days: int = 30):
        """注册新的 SLO"""
        self.slos[name] = SLOTarget(
            name=name,
            description=description,
            target_percent=target_percent,
            window_days=window_days,
        )
        self._metrics[name] = []

    def record_request(
        self,
        slo_name: str,
        success: bool,
        latency_ms: float = None,
        timestamp: datetime = None,
    ):
        """记录请求"""
        if slo_name not in self._metrics:
            logger.warning(f"SLO {slo_name} not registered")
            return

        if timestamp is None:
            timestamp = datetime.utcnow()

        self._metrics[slo_name].append({
            "timestamp": timestamp,
            "success": success,
            "latency_ms": latency_ms,
        })

    def _get_window_data(self, slo_name: str, window_days: int) -> List[Dict]:
        """获取窗口期内的数据"""
        cutoff = datetime.utcnow() - timedelta(days=window_days)
        return [
            m for m in self._metrics[slo_name]
            if m["timestamp"] >= cutoff
        ]

    def calculate_availability(self, slo_name: str) -> SLOReport:
        """计算 SLO 可用性"""
        if slo_name not in self.slos:
            return None

        slo = self.slos[slo_name]
        window_data = self._get_window_data(slo_name, slo.window_days)

        if not window_data:
            return SLOReport(
                slo_name=slo_name,
                status=SLOStatus.UNKNOWN,
                current_period_start=datetime.utcnow() - timedelta(days=slo.window_days),
                current_period_end=datetime.utcnow(),
                total_requests=0,
                successful_requests=0,
                error_count=0,
                availability_percent=0.0,
                error_budget_remaining_percent=100.0,
                burn_rate=0.0,
            )

        total = len(window_data)
        successful = sum(1 for m in window_data if m.get("success", False))
        errors = total - successful
        availability = (successful / total * 100) if total > 0 else 0

        error_budget_remaining = 100.0 - (100.0 - availability) / (100.0 - slo.target_percent) * 100 if slo.target_percent < 100 else 100.0

        # 计算燃烧率 (简单版本)
        days_elapsed = min(slo.window_days, (datetime.utcnow() - window_data[0]["timestamp"]).total_seconds() / 86400)
        burn_rate = (errors / total) / (error_budget_remaining / 100 / slo.window_days) if days_elapsed > 0 and error_budget_remaining > 0 else 0

        # 判断状态
        if availability >= slo.target_percent:
            status = SLOStatus.OK
        elif availability >= slo.target_percent - 1.0:
            status = SLOStatus.AT_RISK
        else:
            status = SLOStatus.BREACHED

        return SLOReport(
            slo_name=slo_name,
            status=status,
            current_period_start=window_data[0]["timestamp"],
            current_period_end=datetime.utcnow(),
            total_requests=total,
            successful_requests=successful,
            error_count=errors,
            availability_percent=availability,
            error_budget_remaining_percent=error_budget_remaining,
            burn_rate=burn_rate,
        )

    def check_all_slos(self) -> Dict[str, SLOReport]:
        """检查所有 SLO 状态"""
        reports = {}
        for slo_name in self.slos:
            reports[slo_name] = self.calculate_availability(slo_name)
        return reports

    def is_healthy(self) -> bool:
        """检查整体健康状态"""
        reports = self.check_all_slos()
        return all(r.status in [SLOStatus.OK, SLOStatus.UNKNOWN] for r in reports.values())

    def get_alerts(self) -> List[Dict]:
        """获取告警列表"""
        reports = self.check_all_slos()
        alerts = []

        for slo_name, report in reports.items():
            if report.status == SLOStatus.BREACHED:
                alerts.append({
                    "severity": "critical",
                    "slo": slo_name,
                    "message": f"SLO {slo_name} breached: {report.availability_percent:.2f}% < {self.slos[slo_name].target_percent}%",
                    "current_budget": report.error_budget_remaining_percent,
                })
            elif report.status == SLOStatus.AT_RISK:
                alerts.append({
                    "severity": "warning",
                    "slo": slo_name,
                    "message": f"SLO {slo_name} at risk: {report.availability_percent:.2f}% (budget: {report.error_budget_remaining_percent:.1f}%)",
                    "burn_rate": report.burn_rate,
                })

        return alerts

    def get_dashboard_metrics(self) -> Dict:
        """获取 Dashboard 指标"""
        reports = self.check_all_slos()

        return {
            "overall_status": "healthy" if self.is_healthy() else "unhealthy",
            "slos": {
                name: {
                    "status": report.status.value,
                    "availability": f"{report.availability_percent:.2f}%",
                    "target": f"{self.slos[name].target_percent}%",
                    "error_budget": f"{report.error_budget_remaining_percent:.1f}%",
                }
                for name, report in reports.items()
            },
            "alerts": self.get_alerts(),
        }

    def cleanup_old_metrics(self, days: int = 31):
        """清理旧指标数据"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        for slo_name in self._metrics:
            self._metrics[slo_name] = [
                m for m in self._metrics[slo_name]
                if m["timestamp"] >= cutoff
            ]


# 全局 SLO 监控器实例
_slo_monitor: Optional[SLOMonitor] = None


def get_slo_monitor() -> SLOMonitor:
    """获取全局 SLO 监控器实例"""
    global _slo_monitor
    if _slo_monitor is None:
        _slo_monitor = SLOMonitor()
    return _slo_monitor


# 便捷函数
def record_api_request(success: bool, latency_ms: float = None):
    """记录 API 请求"""
    monitor = get_slo_monitor()
    monitor.record_request("api_latency_p50", success, latency_ms)
    monitor.record_request("api_latency_p99", success, latency_ms)
    monitor.record_request("core_path_availability", success, latency_ms)


def record_task_execution(success: bool):
    """记录任务执行"""
    monitor = get_slo_monitor()
    monitor.record_request("task_success_rate", success)


def get_slo_status() -> Dict:
    """获取 SLO 状态"""
    return get_slo_monitor().get_dashboard_metrics()