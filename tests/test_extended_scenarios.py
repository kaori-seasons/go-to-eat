"""扩展场景测试：覆盖更多端到端场景，用于产品测评报告。

场景清单：
  EXT-1   5 人聚餐（最大复杂度）
  EXT-2   跨城市（上海）
  EXT-3   时间约束（19 点到）
  EXT-4   远距离（>25km，建议 transit）
  EXT-5   近距离（<500m，纯步行可达）
  EXT-6   多轮：换菜系
  EXT-7   多轮：加人
  EXT-8   多轮：改时间
  EXT-9   故障恢复：1 个地点 geocode 失败
  EXT-10  混合交通模式（driving + transit + bicycle）
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import (
    OrchestratorConfig,
    OrchestratorExecutor,
    OrchestrationSession,
    PlanDagBuilder,
    RecommendationPipeline,
    SessionStore,
    haversine_km,
    route_mode_decision,
)
from tests.test_orchestrator import FakeAmap, _is_coord, _make_session


# ---- EXT-1：5 人聚餐（最大复杂度） ----------------------------------------

def test_ext1_5_person_full_pipeline():
    """5 人从不同地点出发，端到端完成率 100%。"""
    async def scenario():
        fake = FakeAmap()
        pipeline = RecommendationPipeline(amap=fake, config=OrchestratorConfig(max_route_candidates=3))
        result = await pipeline.run(
            "我们在北京，五个人分别从望京、霍营、中关村、五道口和国贸出发，想吃火锅",
            scope="ext1",
        )
        return result, fake

    result, fake = asyncio.run(scenario())
    # 基础断言
    assert result["food"] == "火锅"
    assert result["city"] == "北京"
    assert len(result["resolvedParticipants"]) == 5
    assert result["recommended"] is not None
    assert 1 <= len(result["alternatives"]) <= 2
    # 完成率
    assert result["planProgress"]["total"] == result["planProgress"].get("done", 0)
    # geo 调用数 == 5（零重复）
    geo_calls = len([c for c in fake.calls if c["kind"] == "geo"])
    assert geo_calls == 5
    # route 调用数 == 5 人 × 3 候选 = 15
    route_calls = len([c for c in fake.calls if c["kind"] in ("driving", "transit")])
    assert route_calls >= 5 * 2  # 至少 driving + transit


# ---- EXT-2：跨城市（上海） ------------------------------------------------

def test_ext2_shanghai_scenario():
    """上海场景，验证城市参数正确传递。"""
    async def scenario():
        fake = FakeAmap()
        pipeline = RecommendationPipeline(amap=fake, config=OrchestratorConfig(max_route_candidates=3))
        result = await pipeline.run(
            "我们在上海，从徐家汇和陆家嘴出发想吃日料",
            scope="ext2",
        )
        return result, fake

    result, fake = asyncio.run(scenario())
    assert result["city"] == "上海"
    assert result["food"] == "日料"
    assert len(result["resolvedParticipants"]) == 2
    assert result["recommended"] is not None
    # 验证城市参数传递到 search
    search_calls = [c for c in fake.calls if c["kind"] == "search"]
    assert search_calls[0]["city"] == "上海"


# ---- EXT-3：时间约束（19 点到） -------------------------------------------

def test_ext3_time_constraint():
    """带时间约束的场景，meeting_time 正确保留。"""
    async def scenario():
        fake = FakeAmap()
        pipeline = RecommendationPipeline(amap=fake, config=OrchestratorConfig(max_route_candidates=3))
        result = await pipeline.run(
            "我们在北京，三个人从望京、霍营和中关村出发，想吃烤肉，19点到",
            scope="ext3",
        )
        return result

    result = asyncio.run(scenario())
    assert result["meeting_time"] == "19:00"
    assert result["food"] == "烤肉"
    assert len(result["resolvedParticipants"]) == 3
    assert result["recommended"] is not None


# ---- EXT-4：远距离（>25km，建议 transit） ---------------------------------

def test_ext4_far_distance_suggests_transit():
    """望京→亦庄约 30km，应建议 transit 而非 driving。"""
    origin = {"lng": 116.47, "lat": 39.99}   # 望京
    dest = {"lng": 116.65, "lat": 39.78}     # 亦庄（约 30km）
    dist = haversine_km(origin, dest)
    assert dist > 25.0

    allowed, skips, notes = route_mode_decision(
        origin, dest, ["driving", "transit", "bicycle"]
    )
    # bicycle 应被跳过（>3km）
    assert "bicycle" not in allowed
    # driving 应被保留但有建议
    assert "driving" in allowed
    assert "transit" in allowed


# ---- EXT-5：近距离（<500m，步行可达） -------------------------------------

def test_ext5_short_distance():
    """望京→望京 SOHO 约 500m，所有模式均允许。"""
    origin = {"lng": 116.470, "lat": 39.990}
    dest = {"lng": 116.475, "lat": 39.993}   # 约 500m
    dist = haversine_km(origin, dest)
    assert dist < 1.0

    allowed, skips, notes = route_mode_decision(
        origin, dest, ["driving", "transit", "bicycle"]
    )
    assert "bicycle" in allowed
    assert "driving" in allowed
    assert "transit" in allowed
    assert skips == []


# ---- EXT-6：多轮 —— 换菜系 ------------------------------------------------

def test_ext6_follow_up_change_cuisine():
    """第一轮烤肉，第二轮换火锅，geo 零重复调用。"""
    async def scenario():
        fake = FakeAmap()
        store = SessionStore()
        pipeline = RecommendationPipeline(amap=fake, config=OrchestratorConfig(max_route_candidates=2))
        first = await pipeline.run(
            "我们在北京，从望京和霍营出发想吃烤肉",
            scope="ext6", store=store,
        )
        geo_first = len([c for c in fake.calls if c["kind"] == "geo"])
        second = await pipeline.follow_up(first["session_id"], "换成火锅", store)
        geo_delta = len([c for c in fake.calls if c["kind"] == "geo"]) - geo_first
        return first, second, geo_delta

    first, second, geo_delta = asyncio.run(scenario())
    assert first["food"] == "烤肉"
    assert second["food"] == "火锅"
    assert geo_delta == 0, "换菜系不应重复地理编码"
    assert second["recommended"] is not None


# ---- EXT-7：多轮 —— 加人 --------------------------------------------------

def test_ext7_follow_up_add_person():
    """第一轮 2 人，第二轮加 1 人从国贸出发。"""
    async def scenario():
        fake = FakeAmap()
        store = SessionStore()
        pipeline = RecommendationPipeline(amap=fake, config=OrchestratorConfig(max_route_candidates=2))
        first = await pipeline.run(
            "我们在北京，从望京和霍营出发想吃烤肉",
            scope="ext7", store=store,
        )
        geo_before = len([c for c in fake.calls if c["kind"] == "geo"])
        second = await pipeline.follow_up(
            first["session_id"], "加一个人，从国贸出发", store
        )
        geo_delta = len([c for c in fake.calls if c["kind"] == "geo"]) - geo_before
        return first, second, geo_delta

    first, second, geo_delta = asyncio.run(scenario())
    assert len(first["resolvedParticipants"]) == 2
    assert len(second["resolvedParticipants"]) == 3
    assert geo_delta == 1, "只为新增参与者做一次地理编码"


# ---- EXT-8：多轮 —— 改时间 ------------------------------------------------

def test_ext8_follow_up_change_time():
    """第一轮 18 点到，第二轮改 20 点到，零 API 调用。"""
    async def scenario():
        fake = FakeAmap()
        store = SessionStore()
        pipeline = RecommendationPipeline(amap=fake, config=OrchestratorConfig(max_route_candidates=2))
        first = await pipeline.run(
            "我们在北京，从望京和霍营出发想吃烤肉，18点到",
            scope="ext8", store=store,
        )
        calls_before = len(fake.calls)
        second = await pipeline.follow_up(first["session_id"], "改成20点到", store)
        delta = len(fake.calls) - calls_before
        return first, second, delta

    first, second, delta = asyncio.run(scenario())
    assert first["meeting_time"] == "18:00"
    assert second["meeting_time"] == "20:00"
    assert delta == 0, "改时间不应触发任何工具调用"


# ---- EXT-9：故障恢复 —— geocode 失败 --------------------------------------

def test_ext9_geocode_failure_recovery():
    """1 个地点 geocode 失败，其余正常完成，失败步骤标记 failed。"""
    async def scenario():
        fake = FakeAmap()
        session = _make_session(("不存在的地点", "望京", "霍营"))
        session = await OrchestratorExecutor(fake, geo_station_fallback=False).run(session)
        return session

    session = asyncio.run(scenario())
    # 失败步骤
    failed = session.plan.get("geo:不存在的地点")
    assert failed is not None
    assert failed.status == "failed"
    assert failed.failure["reason"] == "geocode_failed"
    # 成功步骤
    assert session.plan["geo:望京"].status == "done"
    assert session.plan["geo:霍营"].status == "done"
    # search 正常完成（依赖成功的 geo）
    search = session.steps_by_kind("search")[0]
    assert search.status == "done"


# ---- EXT-10：混合交通模式 --------------------------------------------------

def test_ext10_mixed_transport_modes():
    """验证 driving + transit + bicycle 三种模式的 guard 行为。"""
    # 近距离：三种模式均保留
    origin_near = {"lng": 116.470, "lat": 39.990}
    dest_near = {"lng": 116.475, "lat": 39.993}
    allowed, skips, _ = route_mode_decision(origin_near, dest_near, ["driving", "transit", "bicycle"])
    assert set(allowed) == {"driving", "transit", "bicycle"}
    assert skips == []

    # 远距离：bicycle 被跳过
    origin_far = {"lng": 116.47, "lat": 39.99}
    dest_far = {"lng": 116.33, "lat": 39.99}
    assert haversine_km(origin_far, dest_far) > 3.0
    allowed2, skips2, _ = route_mode_decision(origin_far, dest_far, ["driving", "transit", "bicycle"])
    assert "bicycle" not in allowed2
    assert skips2[0]["mode"] == "bicycle"
