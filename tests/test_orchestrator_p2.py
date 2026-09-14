"""Orchestrator P2 单测：tracing、disk cache、config 模式。

覆盖：
  P2-1   trace 每步耗时、降级留痕、step_count / api_calls 汇总
  P2-2   DiskEntityCache 写入磁盘 / 重启恢复 / 过期清理
  P2-4   orchestration_mode 配置 + model_assisted step_order_fn
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import (
    DiskEntityCache,
    OrchestratorConfig,
    OrchestratorExecutor,
    OrchestrationMode,
    OrchestrationSession,
    PlanDagBuilder,
    RecommendationPipeline,
    SessionTrace,
    SessionStore,
    validate_coord_str,
)
from orchestrator.tracing import StepTrace
from tests.test_orchestrator import FakeAmap, _make_session


# ---- P2-1：tracing -------------------------------------------------------

def test_tracing_step_duration_and_summary():
    async def scenario():
        fake = FakeAmap()
        trace = SessionTrace(session_id="t1", scope="default", mode="deterministic")
        session = _make_session(("望京", "霍营"))
        await OrchestratorExecutor(fake, geo_station_fallback=False).run(session, trace=trace)
        return trace

    trace = asyncio.run(scenario())
    d = trace.to_dict()
    assert d["session_id"] == "t1"
    assert d["mode"] == "deterministic"
    assert d["step_count"] >= 5
    assert d["total_api_calls"] >= 2
    assert all(s["duration_ms"] >= 0 for s in d["steps"])
    summary = trace.summary()
    assert summary["status_counts"].get("done", 0) >= 5
    assert summary["failed_steps"] == []
    assert summary["degraded_steps"] == []


def test_tracing_degraded_steps():
    async def scenario():
        from tests.test_orchestrator_p1 import FlakyDrivingAmap
        fake = FlakyDrivingAmap()
        trace = SessionTrace(session_id="deg", scope="default", mode="deterministic")
        session = _make_session(("望京", "霍营"))
        await OrchestratorExecutor(fake, geo_station_fallback=False).run(session, trace=trace)
        return trace

    trace = asyncio.run(scenario())
    summary = trace.summary()
    assert len(summary["degraded_steps"]) > 0


def test_tracing_api_call_count():
    async def scenario():
        fake = FakeAmap()
        trace = SessionTrace(session_id="api", scope="default", mode="deterministic")
        session = _make_session(("望京", "霍营"))
        await OrchestratorExecutor(fake, geo_station_fallback=False).run(session, trace=trace)
        return trace

    trace = asyncio.run(scenario())
    assert trace.total_api_calls > 0
    # trace 每步记录 api_calls，总和应等于各步 api_calls 之和
    sum_calls = sum(s.api_calls for s in trace.steps)
    assert trace.total_api_calls == sum_calls


# ---- P2-2：DiskEntityCache -------------------------------------------------

def test_disk_cache_persistence_and_recovery():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        cache1 = DiskEntityCache(db_path=db_path)
        cache1.put_geo("alice", "北京", "望京", {"lng": 116.47, "lat": 39.99, "label": "望京"})
        cache1.put_poi("alice", "poi1", {"id": "poi1", "name": "餐厅1", "lng": 116.40, "lat": 40.00})
        cache1.close()

        # 重启恢复
        cache2 = DiskEntityCache(db_path=db_path)
        assert cache2.get_geo("alice", "北京", "望京") is not None
        assert cache2.get("alice", "poi:poi1") is not None
        cache2.close()
    finally:
        os.unlink(db_path)


def test_disk_cache_scope_isolation():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        cache = DiskEntityCache(db_path=db_path)
        cache.put_geo("alice", "北京", "望京", {"lng": 116.47, "lat": 39.99})
        assert cache.get_geo("alice", "北京", "望京") is not None
        assert cache.get_geo("bob", "北京", "望京") is None
        cache.close()
    finally:
        os.unlink(db_path)


def test_disk_cache_cleanup_expired():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        cache = DiskEntityCache(db_path=db_path, geo_ttl=-1)  # 立即过期
        cache.put_geo("alice", "北京", "望京", {"lng": 116.47, "lat": 39.99})
        assert cache.get_geo("alice", "北京", "望京") is None  # 内存已过期
        deleted = cache.cleanup_expired()
        assert deleted == 1
        cache.close()
    finally:
        os.unlink(db_path)


# ---- P2-4：orchestration_mode 配置 -------------------------------------------

def test_config_from_dict():
    cfg = OrchestratorConfig.from_dict({
        "mode": "model_assisted",
        "max_route_candidates": 3,
        "recall_token_budget": 800,
        "enable_tracing": False,
    })
    assert cfg.mode == OrchestrationMode.MODEL_ASSISTED
    assert cfg.max_route_candidates == 3
    assert cfg.enable_tracing is False


def test_config_defaults():
    cfg = OrchestratorConfig()
    assert cfg.mode == OrchestrationMode.DETERMINISTIC
    assert cfg.enable_tracing is True
    assert cfg.max_route_candidates == 5


def test_model_assisted_step_order_fn():
    """验证 model_assisted 模式下 step_order_fn 被调用并能排序步骤。"""
    call_log = []

    def fake_order(steps):
        call_log.append(len(steps))
        return steps  # 原序返回

    async def scenario():
        fake = FakeAmap()
        session = _make_session(("望京", "霍营"))
        executor = OrchestratorExecutor(fake, geo_station_fallback=False, step_order_fn=fake_order)
        await executor.run(session)
        return call_log

    log = asyncio.run(scenario())
    assert len(log) > 0
    assert all(isinstance(n, int) for n in log)


def test_pipeline_returns_trace():
    async def scenario():
        fake = FakeAmap()
        pipeline = RecommendationPipeline(amap=fake)
        return await pipeline.run("我们在北京，从望京和霍营出发想吃烤肉", scope="trace_test")

    result = asyncio.run(scenario())
    assert "orchestration_trace" in result
    trace = result["orchestration_trace"]
    assert trace["step_count"] >= 5
    assert "trace_summary" in result
    assert result["trace_summary"]["status_counts"].get("done", 0) >= 5


def test_pipeline_tracing_disabled():
    async def scenario():
        fake = FakeAmap()
        cfg = OrchestratorConfig(enable_tracing=False)
        pipeline = RecommendationPipeline(amap=fake, config=cfg)
        return await pipeline.run("我们在北京，从望京和霍营出发想吃烤肉", scope="no_trace")

    result = asyncio.run(scenario())
    assert "orchestration_trace" not in result
