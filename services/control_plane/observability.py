"""
可观测性模块 - OpenTelemetry 埋点
支持：指标收集、链路追踪、日志关联
"""

from __future__ import annotations

import logging
import time
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from functools import wraps

logger = logging.getLogger(__name__)

# OpenTelemetry 可用性
OTEL_AVAILABLE = False

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry import metrics
    from opentelemetry.trace import Status, StatusCode
    OTEL_AVAILABLE = True
except ImportError:
    logger.warning("OpenTelemetry not installed, using mock tracing")
    trace = None


@dataclass
class SpanContext:
    """追踪上下文"""
    trace_id: str = ""
    span_id: str = ""
    parent_span_id: str = ""


class ObservabilityManager:
    """可观测性管理器"""

    def __init__(self, service_name: str = "openclaw"):
        self.service_name = service_name
        self._tracer = None
        self._meter = None
        self._initialized = False

    def initialize(
        self,
        otlp_endpoint: str = None,
        sampling_rate: float = 0.1,
        enable_console: bool = True,
    ) -> bool:
        """初始化 OpenTelemetry"""
        if not OTEL_AVAILABLE:
            logger.info("Using mock observability (no OpenTelemetry)")
            self._initialized = True
            return True

        try:
            # 创建资源
            resource = Resource.create({
                "service.name": self.service_name,
                "service.version": "0.2.0",
                "deployment.environment": os.getenv("ENV", "development"),
            })

            # 初始化追踪
            provider = TracerProvider(resource=resource, sampler=sampling_rate)

            # 添加 Console 导出器（开发环境）
            if enable_console:
                provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

            # 添加 OTLP 导出器（如果配置了）
            if otlp_endpoint:
                provider.add_span_processor(
                    BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
                )

            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer(__name__)

            # 初始化指标 - 只有配置了 OTLP endpoint 才启用
            if otlp_endpoint:
                try:
                    from opentelemetry.sdk.metrics.export import ConsoleMetricExporter
                    metric_reader = PeriodicExportingMetricReader(
                        ConsoleMetricExporter()
                    )
                    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
                    metrics.set_meter_provider(meter_provider)
                except ImportError:
                    logger.warning("Metric exporter not available, skipping metrics")
            else:
                # 无 OTLP endpoint 时使用空的 MeterProvider
                meter_provider = MeterProvider(resource=resource)
                metrics.set_meter_provider(meter_provider)

            self._meter = metrics.get_meter(__name__)

            self._initialized = True
            logger.info("OpenTelemetry initialized")
            return True

        except Exception as e:
            logger.error(f"OpenTelemetry initialization failed: {e}")
            return False

    @contextmanager
    def start_span(
        self,
        name: str,
        attributes: Dict[str, Any] = None,
        kind: str = "internal",
    ):
        """开始一个追踪 span"""
        if not self._initialized or not self._tracer:
            # Mock implementation
            yield SpanContext()
            return

        span_kind = {
            "internal": trace.SpanKind.INTERNAL,
            "server": trace.SpanKind.SERVER,
            "client": trace.SpanKind.CLIENT,
            "producer": trace.SpanKind.PRODUCER,
            "consumer": trace.SpanKind.CONSUMER,
        }.get(kind, trace.SpanKind.INTERNAL)

        with self._tracer.start_as_current_span(
            name,
            kind=span_kind,
            attributes=attributes or {},
        ) as span:
            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "",
        attributes: Dict[str, Any] = None,
    ) -> None:
        """记录指标"""
        if not self._initialized or not self._meter:
            return

        try:
            counter = self._meter.create_counter(
                name,
                unit=unit,
                description=f"Metric {name}",
            )
            counter.add(value, attributes or {})
        except Exception as e:
            logger.debug(f"Metric recording failed: {e}")

    def record_task_submitted(self, task_id: str, task_type: str) -> None:
        """记录任务提交"""
        self.record_metric(
            "openclaw.tasks.submitted.total",
            1,
            attributes={"task_id": task_id, "task_type": task_type}
        )

    def record_task_completed(self, task_id: str, duration_ms: float, success: bool) -> None:
        """记录任务完成"""
        self.record_metric(
            "openclaw.tasks.completed.total",
            1,
            attributes={"task_id": task_id, "success": str(success)}
        )
        self.record_metric(
            "openclaw.tasks.duration.ms",
            duration_ms,
            "ms",
            attributes={"task_id": task_id}
        )

    def record_task_failed(self, task_id: str, error: str) -> None:
        """记录任务失败"""
        self.record_metric(
            "openclaw.tasks.failed.total",
            1,
            attributes={"task_id": task_id, "error": error}
        )

    def record_worker_heartbeat(self, worker_id: str, cpu: float, memory: float) -> None:
        """记录 Worker 心跳"""
        self.record_metric(
            "openclaw.worker.cpu_usage",
            cpu,
            "%",
            attributes={"worker_id": worker_id}
        )
        self.record_metric(
            "openclaw.worker.memory_usage",
            memory,
            "%",
            attributes={"worker_id": worker_id}
        )

    def get_trace_id(self) -> str:
        """获取当前追踪 ID"""
        if trace and trace.get_current_span():
            return format(trace.get_current_span().get_span_context().trace_id, "032x")
        return ""


# 便捷装饰器
def traced(span_name: str = None, attributes: Dict[str, Any] = None):
    """追踪装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = span_name or func.__name__
            with _observability.start_span(name, attributes=attributes):
                start = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration_ms = (time.time() - start) * 1000
                    _observability.record_task_completed(
                        task_id=name,
                        duration_ms=duration_ms,
                        success=True
                    )
                    return result
                except Exception as e:
                    duration_ms = (time.time() - start) * 1000
                    _observability.record_task_failed(task_id=name, error=str(e))
                    raise
        return wrapper
    return decorator


# 全局可观测性管理器
_observability: ObservabilityManager = ObservabilityManager()


def get_observability() -> ObservabilityManager:
    """获取全局可观测性管理器"""
    return _observability


def init_observability(
    service_name: str = "openclaw",
    otlp_endpoint: str = None,
    sampling_rate: float = 0.1,
) -> bool:
    """初始化可观测性"""
    global _observability
    _observability = ObservabilityManager(service_name)
    return _observability.initialize(otlp_endpoint, sampling_rate)


# 预定义的追踪上下文管理器
@contextmanager
def track_task(task_id: str, task_type: str):
    """追踪任务执行"""
    with _observability.start_span(
        f"task.{task_type}",
        attributes={"task_id": task_id, "task_type": task_type},
        kind="client",
    ):
        yield