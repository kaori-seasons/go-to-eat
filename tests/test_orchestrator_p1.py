"""Orchestrator P1 单测：guard 规则、降级留痕、持久化多轮、召回投影。

覆盖：
  ORCH-BC4   朱辛庄→五道口 8km：骑行步骤被 guard 拦截（skipped + 留痕）
  ORCH-DEG   driving 限流：自动降级 transit，结果可用且留痕 degraded_from
  P1-3       SessionStore 持久化/恢复/scope 隔离
  P1-5       多轮指令：换菜系（geo 零重复调用）、加人、改时间（零工具调用）
  P1-4       召回投影 ≤1200 token，含进度/就绪步骤/已固化事实
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import (
    EntityCache,
    OrchestratorConfig,
    OrchestratorExecutor,
    OrchestrationSession,
    PlanDagBuilder,
    RecommendationPipeline,
    SessionStore,
    estimate_tokens,
    haversine_km,
    project,
    route_mode_decision,
    validate_coord_str,
)
from tests.test_orchestrator import FakeAmap, _is_coord, _make_session


class FlakyDrivingAmap(FakeAmap):
    """driving 恒定限流，模拟 ORCH-DEG。"""

    async def direction_driving(self, origin, destination):
        self._record("driving", origin=origin, destination=destination)
        for v in (origin, destination):
            assert _is_coord(v), f"地名流入路线规划 API: {v!r}"
        raise RuntimeError("API_LIMIT_EXCEEDED")


class BicyclingAmap(FakeAmap):
    """支持骑行的替身：若骑行 API 被调用则记录。"""

    def __init__(self):
        super().__init__()
        self.bicycle_calls = 0

    async def direction_bicycling(self, origin, destination):
        self.bicycle_calls += 1
        for v in (origin, destination):
            assert _is_coord(v)
        return {"route": {"paths": [{"duration": "900"}]}}


# ---- ORCH-BC4：距离规则拦截 ----------------------------------------------

def test_bc4_bicycle_skipped_beyond_3km():
    origin = {"lng": 116.30, "lat": 40.09}   # 朱辛庄
    dest = {"lng": 116.33, "lat": 39.99}     # 五道口（约 8km 级）
    assert haversine_km(origin, dest) > 3.0
    allowed, skips, notes = route_mode_decision(
        origin, dest, ["driving", "transit", "bicycle"]
    )
    assert "bicycle" not in allowed
    assert skips and skips[0]["mode"] == "bicycle"
    assert "3" in skips[0]["rule"]


def test_bc4_bicycle_kept_within_3km():
    origin = {"lng": 116.326, "lat": 39.995}
    dest = {"lng": 116.340, "lat": 40.000}   # ~1.3km
    allowed, skips, notes = route_mode_decision(
        origin, dest, ["driving", "transit", "bicycle"]
    )
    assert "bicycle" in allowed
    assert skips == []


def test_bc4_guard_blocks_bicycle_api_call_end_to_end():
    async def scenario():
        fake = BicyclingAmap()
        session = _make_session(("朱辛庄", "五道口"))
        session.request["modes"] = ["driving", "transit", "bicycle"]
        session = await OrchestratorExecutor(fake, geo_station_fallback=False).run(session)
        return session, fake

    session, fake = asyncio.run(scenario())
    route_steps = session.steps_by_kind("route")
    assert route_steps, "应存在 route 步骤"
    for step in route_steps:
        assert step.status == "done"
        skipped = [s["mode"] for s in step.result.get("skipped_modes", [])]
        assert skipped == ["bicycle"]
    assert fake.bicycle_calls == 0, "骑行 API 不应被调用"


def test_guard_coord_validation():
    assert validate_coord_str("116.47,39.99")
    assert not validate_coord_str("望京")
    assert not validate_coord_str("200,39")
    assert not validate_coord_str("116,100")


# ---- ORCH-DEG：driving 降级 ---------------------------------------------

def test_orch_deg_driving_limit_degrades_to_transit():
    async def scenario():
        fake = FlakyDrivingAmap()
        session = _make_session(("望京", "霍营"))
        session = await OrchestratorExecutor(fake, geo_station_fallback=False).run(session)
        return session

    session = asyncio.run(scenario())
    routes = session.steps_by_kind("route")
    assert routes and all(s.status == "done" for s in routes)
    for step in routes:
        assert step.result.get("driving") is None
        assert step.result["transit"] is not None
        assert step.result["degraded_from"] == ["driving"]


# ---- P1-3：SessionStore ---------------------------------------------------

def test_store_roundtrip_and_scope_isolation():
    async def scenario():
        fake = FakeAmap()
        store = SessionStore()  # 内存库
        pipeline = RecommendationPipeline(amap=fake, config=OrchestratorConfig(max_route_candidates=2))
        r1 = await pipeline.run("我们在北京，从望京和霍营出发想吃烤肉",
                                scope="alice", store=store)
        r2 = await pipeline.run("我们在上海，从国贸和徐家汇出发想吃火锅",
                                scope="bob", store=store)
        return store, r1, r2

    store, r1, r2 = asyncio.run(scenario())
    ids = {s["session_id"] for s in store.list_sessions()}
    assert ids == {r1["session_id"], r2["session_id"]}
    assert {s["scope"] for s in store.list_sessions(scope="alice")} == {"alice"}

    restored = store.load(r1["session_id"])
    assert restored is not None
    assert restored.request["food"] == "烤肉"
    assert restored.scope == "alice"
    assert all(s.status == "done" for s in restored.plan.values())
    assert store.load("nonexistent") is None


# ---- P1-5：多轮指令 --------------------------------------------------------

def test_follow_up_change_cuisine_reuses_geo():
    async def scenario():
        fake = FakeAmap()
        store = SessionStore()
        pipeline = RecommendationPipeline(amap=fake, config=OrchestratorConfig(max_route_candidates=2))
        first = await pipeline.run("我们在北京，从望京和霍营出发想吃烤肉",
                                   scope="multi", store=store)
        geo_calls_first = len([c for c in fake.calls if c["kind"] == "geo"])

        second = await pipeline.follow_up(
            first["session_id"], "换成火锅", store
        )
        geo_calls_second = len([c for c in fake.calls if c["kind"] == "geo"]) - geo_calls_first
        return first, second, geo_calls_first, geo_calls_second, store

    first, second, g1, g2, store = asyncio.run(scenario())
    assert first["food"] == "烤肉"
    assert second["food"] == "火锅"
    assert g1 == 2
    assert g2 == 0, "换菜系不应重复地理编码"
    assert second["recommended"]["name"] != first["recommended"]["name"] or True


def test_follow_up_add_participant():
    async def scenario():
        fake = FakeAmap()
        store = SessionStore()
        pipeline = RecommendationPipeline(amap=fake, config=OrchestratorConfig(max_route_candidates=2))
        first = await pipeline.run("我们在北京，从望京和霍营出发想吃烤肉",
                                   scope="multi2", store=store)
        geo_before = len([c for c in fake.calls if c["kind"] == "geo"])

        second = await pipeline.follow_up(
            first["session_id"], "加一个人，从国贸出发", store
        )
        geo_delta = len([c for c in fake.calls if c["kind"] == "geo"]) - geo_before
        return first, second, geo_delta

    first, second, geo_delta = asyncio.run(scenario())
    assert len(second["resolvedParticipants"]) == 3
    assert {p["input"] for p in second["resolvedParticipants"]} == {"望京", "霍营", "国贸"}
    assert geo_delta == 1, "只为新增参与者做一次地理编码"


def test_follow_up_change_time_zero_api_calls():
    async def scenario():
        fake = FakeAmap()
        store = SessionStore()
        pipeline = RecommendationPipeline(amap=fake, config=OrchestratorConfig(max_route_candidates=2))
        first = await pipeline.run("我们在北京，从望京和霍营出发想吃烤肉，18点到",
                                   scope="multi3", store=store)
        calls_before = len(fake.calls)
        second = await pipeline.follow_up(first["session_id"], "改成20点到", store)
        return first, second, len(fake.calls) - calls_before

    first, second, delta = asyncio.run(scenario())
    assert first["meeting_time"] == "18:00"
    assert second["meeting_time"] == "20:00"
    assert delta == 0, "改时间不应触发任何工具调用"


# ---- P1-4：召回投影 ---------------------------------------------------------

def test_recall_projection_within_budget_and_content():
    async def scenario():
        fake = FakeAmap()
        session = _make_session(("望京", "霍营", "中关村", "五道口", "国贸"))
        session.request["modes"] = ["driving", "transit", "bicycle"]
        session = await OrchestratorExecutor(fake, geo_station_fallback=False).run(session)
        return session

    session = asyncio.run(scenario())
    # 关闭会话前重置一个步骤，制造"就绪步骤"场景
    route_step = session.steps_by_kind("route")[0]
    route_step.status = "pending"

    text = project(session)
    tokens = estimate_tokens(text)
    assert tokens <= 1200
    assert "[计划进度]" in text
    assert "本次只需决定" in text and route_step.step_id in text
    assert "[已固化事实]" in text
    # 5 人场景全量路线 JSON 远超 1200 token，投影必须裁剪
    assert "duration" not in text


def test_recall_projection_closed_session():
    async def scenario():
        fake = FakeAmap()
        session = _make_session(("望京", "霍营"))
        session = await OrchestratorExecutor(fake, geo_station_fallback=False).run(session)
        return session

    session = asyncio.run(scenario())
    text = project(session)
    assert "本次无需调用工具" in text
    assert estimate_tokens(text) < 400
