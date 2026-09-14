"""Orchestrator P0 离线单测：全部使用 FakeAmap，不触网。

覆盖方案中的回归断言：
  ORCH-BC1  3 人场景 DAG ≥7 节点、geo 并行、search/route 全 done
  ORCH-BC2  route 入参必为坐标（不允许地名到达 API 层）
  ORCH-BC3  4 人 + 日料 完成率 100%，产出 1 推荐 + ≤2 备选
  ORCH-MULTI  会话内 geo 缓存复用（零重复 geo 调用）
  ORCH-SCOPE  并发会话零串线
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
    PlanDagBuilder,
    OrchestrationSession,
    RecommendationPipeline,
    RuleExtractor,
    rank_candidates,
    score_candidate,
)


class FakeAmap:
    """离线高德替身：记录全部入参，返回固定形状数据。"""

    def __init__(self):
        self.calls = []

    def _record(self, kind, **params):
        self.calls.append({"kind": kind, **params})

    async def geocode(self, address, city=""):
        self._record("geo", address=address, city=city)
        if address.endswith("地铁站") or address.endswith("公交站"):
            # 模拟：仅"地铁站"查询命中
            if address.endswith("地铁站"):
                return {"geocodes": [{"location": "116.47,39.99",
                                      "formatted_address": address,
                                      "adcode": "110105"}]}
            return {"geocodes": []}
        if address == "不存在的地点":
            return {"geocodes": []}
        return {"geocodes": [{"location": "116.40,40.00",
                              "formatted_address": f"{city}{address}",
                              "adcode": "110100"}]}

    async def text_search(self, keywords, city, types="餐饮"):
        self._record("search", keywords=keywords, city=city)
        return {"pois": [
            {"id": f"poi{i}", "name": f"餐厅{i}", "address": "某路1号",
             "location": f"116.4{i},39.9{i}"}
            for i in range(1, 7)
        ]}

    async def direction_driving(self, origin, destination):
        self._record("driving", origin=origin, destination=destination)
        for v in (origin, destination):
            assert _is_coord(v), f"地名流入路线规划 API: {v!r}"  # ORCH-BC2 断言
        return {"route": {"paths": [{"duration": "1800"}]}}

    async def direction_transit(self, origin, destination, city, cityd=""):
        self._record("transit", origin=origin, destination=destination, city=city)
        for v in (origin, destination):
            assert _is_coord(v), f"地名流入路线规划 API: {v!r}"
        return {"route": {"transits": [{"duration": "2400"}, {"duration": "3000"}]}}


def _is_coord(value) -> bool:
    try:
        lng, lat = value.split(",")
        return -180 <= float(lng) <= 180 and -90 <= float(lat) <= 90
    except Exception:
        return False


def _make_session(text_locations=("望京", "霍营"), city="北京", food="烤肉"):
    session = OrchestrationSession(
        request={"city": city, "locations": list(text_locations),
                 "food": food, "meeting_time": None},
    )
    PlanDagBuilder().build(session)
    return session


# ---- ORCH-BC1：DAG 物化 + 并行 + 全链完成 -------------------------------

def test_bc1_dag_materialized_and_completed():
    async def scenario():
        fake = FakeAmap()
        session = _make_session(("望京", "霍营", "朱辛庄"))
        session = await OrchestratorExecutor(fake, geo_station_fallback=False).run(session)
        geo_steps = session.steps_by_kind("geo")
        assert len(session.plan) >= 7          # 3 geo + 1 search + ≥3 route(裁剪前) + rank
        assert len(geo_steps) == 3
        assert all(s.status == "done" for s in session.plan.values())
        search = session.steps_by_kind("search")[0]
        assert len(search.result) == 6
        return session, fake

    session, fake = asyncio.run(scenario())
    routes = session.steps_by_kind("route")
    assert len(routes) == 3 * 5  # 3 人 × 5 候选（max_route_candidates 默认 5）


def test_bc1_geo_calls_issued_in_parallel_layer():
    """geo 层的调用数 == 参与者数（无冗余），一次 gather 完成。"""
    async def scenario():
        fake = FakeAmap()
        session = _make_session(("望京", "霍营"))
        await OrchestratorExecutor(fake, geo_station_fallback=False).run(session)
        geo_calls = [c for c in fake.calls if c["kind"] == "geo"]
        assert len(geo_calls) == 2
        return fake

    asyncio.run(scenario())


# ---- ORCH-BC2：坐标守门 --------------------------------------------------

def test_bc2_never_passes_place_names_to_routing():
    async def scenario():
        fake = FakeAmap()  # FakeAmap 内部对地名入参直接 assert 失败
        session = _make_session(("望京", "霍营"))
        await OrchestratorExecutor(fake, geo_station_fallback=False).run(session)

    asyncio.run(scenario())  # 未抛异常即通过


def test_bc2_station_fallback_chain():
    """geo 失败自动走 X地铁站 → X公交站 → 原名。"""
    async def scenario():
        fake = FakeAmap()
        session = _make_session(("西二旗", "霍营"))
        executor = OrchestratorExecutor(fake, geo_station_fallback=True)
        session = await executor.run(session)
        geo = session.plan["geo:西二旗"]
        assert geo.status == "done"
        assert geo.result["label"].endswith("地铁站")
        return fake

    fake = asyncio.run(scenario())
    addresses = [c["address"] for c in fake.calls if c["kind"] == "geo" and c["address"].startswith("西二旗")]
    assert addresses == ["西二旗地铁站"]


# ---- ORCH-BC3：端到端完成率 ---------------------------------------------

def test_bc3_full_pipeline_4_people():
    async def scenario():
        fake = FakeAmap()
        pipeline = RecommendationPipeline(amap=fake, config=OrchestratorConfig(max_route_candidates=3))
        return await pipeline.run(
            "我们在北京，四个人分别从望京、霍营、中关村和五道口出发，想吃日料，19点到",
            scope="bc3",
        )

    result = asyncio.run(scenario())
    assert result["food"] == "日料"
    assert result["city"] == "北京"
    assert result["meeting_time"] == "19:00"
    assert len(result["resolvedParticipants"]) == 4
    assert result["recommended"] is not None
    assert 1 <= len(result["alternatives"]) <= 2
    assert result["planProgress"]["total"] == result["planProgress"].get("done", 0)


# ---- ORCH-MULTI：缓存复用 ------------------------------------------------

def test_orch_multi_geo_cache_reuse():
    async def scenario():
        fake = FakeAmap()
        cache = EntityCache()
        executor = OrchestratorExecutor(fake, cache=cache, geo_station_fallback=False)
        session1 = _make_session(("望京", "霍营"))
        await executor.run(session1)
        geo_calls_first = len([c for c in fake.calls if c["kind"] == "geo"])

        session2 = _make_session(("望京", "霍营"), food="火锅")
        await executor.run(session2)
        geo_calls_second = len([c for c in fake.calls if c["kind"] == "geo"]) - geo_calls_first
        return geo_calls_first, geo_calls_second, cache

    first, second, cache = asyncio.run(scenario())
    assert first == 2
    assert second == 0  # 全部命中缓存
    assert cache.stats.hits >= 2


# ---- ORCH-SCOPE：会话隔离 ------------------------------------------------

def test_orch_scope_isolation():
    async def scenario():
        fake = FakeAmap()
        cache = EntityCache()
        executor = OrchestratorExecutor(fake, cache=cache, geo_station_fallback=False)
        s1 = _make_session(("望京", "霍营"))
        s2 = _make_session(("望京", "霍营"))
        s1.scope, s2.scope = "alice", "bob"
        await executor.run(s1)
        await executor.run(s2)
        return fake, cache

    fake, cache = asyncio.run(scenario())
    # 不同 scope 互不命中：两次会话各自真实发起 geo 调用（无跨会话缓存复用）
    geo_calls = [c for c in fake.calls if c["kind"] == "geo"]
    assert len(geo_calls) == 4


# ---- 失败路径 ------------------------------------------------------------

def test_geo_failure_marks_step_failed():
    async def scenario():
        fake = FakeAmap()
        session = _make_session(("不存在的地点", "霍营"))
        session = await OrchestratorExecutor(fake, geo_station_fallback=False).run(session)
        return session

    session = asyncio.run(scenario())
    assert session.plan["geo:不存在的地点"].status == "failed"
    assert session.plan["geo:不存在的地点"].failure["reason"] == "geocode_failed"
    # 依赖失败节点的 route 不应存在或不应为 done
    for step in session.steps_by_kind("route"):
        if "不存在的地点" in step.step_id:
            assert step.status != "done"


# ---- 抽取器 ---------------------------------------------------------------

def test_extractor_basic():
    ext = RuleExtractor()
    req = ext.extract("我们两个人分别从望京和霍营出发，想吃烤肉，帮我推荐一家餐厅，在北京")
    assert req.city == "北京"
    assert req.locations == ["望京", "霍营"]
    assert req.food == "烤肉"
    assert req.confidence == 1.0
    assert not req.needs_llm_fallback


def test_extractor_meeting_time():
    req = RuleExtractor().extract("从国贸、中关村和五道口出发，想吃日料，19点到，在上海")
    assert req.meeting_time == "19:00"
    assert req.city == "上海"
    assert len(req.locations) == 3


def test_extractor_low_confidence_flags_fallback():
    req = RuleExtractor().extract("帮我找家好吃的店")
    assert req.needs_llm_fallback


# ---- Ranker ----------------------------------------------------------------

def test_ranker_strategy_max_prefers_smallest_slowest():
    routes_a = [{"driving": 30, "transit": 40}, {"driving": 20, "transit": 40}]
    routes_b = [{"driving": 25, "transit": 35}, {"driving": 24, "transit": 35}]
    pois = [{"key": "a"}, {"key": "b"}]
    result = rank_candidates({}, {"a": routes_a, "b": routes_b}, pois, ["driving", "transit"], "max")
    assert result["recommended"]["poi"]["key"] == "b"
    assert result["recommended"]["score"]["mode"] == "driving"
    assert result["recommended"]["score"]["max"] == 25.0


def test_ranker_skips_incomplete_modes():
    routes = [{"driving": 30, "transit": None}, {"driving": 20, "transit": 40}]
    score = score_candidate(routes, ["driving", "transit"], "max")
    assert score["mode"] == "driving"


def test_ranker_strategy_spread():
    routes_a = [{"driving": 40, "transit": 40}, {"driving": 10, "transit": 40}]   # spread 30
    routes_b = [{"driving": 26, "transit": 40}, {"driving": 25, "transit": 40}]   # spread 1
    pois = [{"key": "a"}, {"key": "b"}]
    result = rank_candidates({}, {"a": routes_a, "b": routes_b}, pois, ["driving"], "spread")
    assert result["recommended"]["poi"]["key"] == "b"
