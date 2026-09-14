"""编排留痕：结构化 trace 事件（P2-1）。

每个步骤执行时记录：step_id、kind、params、耗时、状态、失败/降级原因。
聚合为会话级 trace，供 Web UI、排障、CI 回归分析使用。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StepTrace:
    """单步执行留痕。"""

    step_id: str
    kind: str
    params: Dict[str, Any]
    status: str  # pending|done|failed|skipped
    started_at: float = 0.0
    finished_at: float = 0.0
    duration_ms: float = 0.0
    failure: Optional[Dict[str, Any]] = None
    degraded_from: Optional[List[str]] = None
    skipped_modes: Optional[List[Dict[str, Any]]] = None
    api_calls: int = 0  # 该步骤触发的 API 调用次数

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "step_id": self.step_id,
            "kind": self.kind,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 1),
            "api_calls": self.api_calls,
        }
        if self.failure:
            d["failure"] = self.failure
        if self.degraded_from:
            d["degraded_from"] = self.degraded_from
        if self.skipped_modes:
            d["skipped_modes"] = self.skipped_modes
        return d


@dataclass
class SessionTrace:
    """会话级 trace 容器。"""

    session_id: str
    scope: str
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0
    total_duration_ms: float = 0.0
    steps: List[StepTrace] = field(default_factory=list)
    total_api_calls: int = 0
    mode: str = "deterministic"  # deterministic | model_assisted

    def start_step(self, step_id: str, kind: str, params: Dict[str, Any]) -> StepTrace:
        trace = StepTrace(
            step_id=step_id,
            kind=kind,
            params=params,
            status="pending",
            started_at=time.time(),
        )
        self.steps.append(trace)
        return trace

    def finish_step(
        self,
        trace: StepTrace,
        status: str,
        failure: Optional[Dict[str, Any]] = None,
        degraded_from: Optional[List[str]] = None,
        skipped_modes: Optional[List[Dict[str, Any]]] = None,
        api_calls: int = 0,
    ) -> None:
        trace.finished_at = time.time()
        trace.duration_ms = (trace.finished_at - trace.started_at) * 1000
        trace.status = status
        trace.failure = failure
        trace.degraded_from = degraded_from
        trace.skipped_modes = skipped_modes
        trace.api_calls = api_calls
        self.total_api_calls += api_calls

    def close(self) -> None:
        self.finished_at = time.time()
        self.total_duration_ms = (self.finished_at - self.started_at) * 1000

    def to_dict(self) -> Dict[str, Any]:
        self.close()
        return {
            "session_id": self.session_id,
            "scope": self.scope,
            "mode": self.mode,
            "total_duration_ms": round(self.total_duration_ms, 1),
            "total_api_calls": self.total_api_calls,
            "step_count": len(self.steps),
            "steps": [s.to_dict() for s in self.steps],
        }

    def summary(self) -> Dict[str, Any]:
        """精简摘要，适合注入日志或 CI 输出。"""
        self.close()
        status_counts: Dict[str, int] = {}
        for step in self.steps:
            status_counts[step.status] = status_counts.get(step.status, 0) + 1
        return {
            "session_id": self.session_id,
            "total_duration_ms": round(self.total_duration_ms, 1),
            "total_api_calls": self.total_api_calls,
            "status_counts": status_counts,
            "degraded_steps": [s.step_id for s in self.steps if s.degraded_from],
            "failed_steps": [s.step_id for s in self.steps if s.status == "failed"],
        }
