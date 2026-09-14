"""确定性执行器：拓扑分层调度 + 层内并行（asyncio.gather）。

默认 deterministic 模式：就绪步骤同层并行发出，不依赖模型。
model_assisted 模式：可注入 step_order_fn 对就绪步骤排序。

P2 集成：每步执行时生成结构化 trace（StepTrace），
所有降级/失败/跳过均留痕，供排障与 CI 回归分析。
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional, Protocol

from .guard import route_mode_decision
from .memory import EntityCache
from .plan import (
    STATUS_DONE,
    STATUS_FAILED,
    OrchestrationSession,
    PlanStep,
    STEP_GEO,
    STEP_RANK,
    STEP_ROUTE,
    STEP_SEARCH,
    expand_route_steps,
)
from .tracing import SessionTrace

MAX_ROUTE_CANDIDATES = 5


class AmapLike(Protocol):
    """duck-typed：兼容 tests/real_amap_client.RealAmapClient。

    direction_bicycling 为可选能力（骑行模式开启时才需要）。
    """

    async def geocode(self, address: str, city: str = "") -> Dict[str, Any]: ...
    async def text_search(self, keywords: str, city: str, types: str = "餐饮") -> Dict[str, Any]: ...
    async def direction_driving(self, origin: str, destination: str) -> Dict[str, Any]: ...
    async def direction_transit(self, origin: str, destination: str, city: str, cityd: str = "") -> Dict[str, Any]: ...


def _parse_lng_lat(location: str) -> Optional[Dict[str, float]]:
    try:
        lng, lat = (float(v) for v in location.split(","))
    except (ValueError, AttributeError):
        return None
    if not (-180 <= lng <= 180 and -90 <= lat <= 90):
        return None
    return {"lng": lng, "lat": lat}


def _drive_minutes(resp: Dict[str, Any]) -> Optional[float]:
    try:
        seconds = float(resp["route"]["paths"][0]["duration"])
        return seconds / 60 if seconds > 0 else None
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _transit_minutes(resp: Dict[str, Any]) -> Optional[float]:
    try:
        transits = resp["route"]["transits"]
        durations = [float(t["duration"]) for t in transits if t.get("duration")]
        return min(durations) / 60 if durations else None
    except (KeyError, TypeError, ValueError):
        return None


StepOrderFn = Callable[[List[PlanStep]], List[PlanStep]]


class OrchestratorExecutor:
    def __init__(
        self,
        amap: AmapLike,
        cache: Optional[EntityCache] = None,
        max_route_candidates: int = MAX_ROUTE_CANDIDATES,
        geo_station_fallback: bool = True,
        step_order_fn: Optional[StepOrderFn] = None,
    ):
        self.amap = amap
        self.cache = cache or EntityCache()
        self.max_route_candidates = max_route_candidates
        self.geo_station_fallback = geo_station_fallback
        self.step_order_fn = step_order_fn

    # ---- 单步执行 -------------------------------------------------------

    async def _execute_geo(self, session: OrchestrationSession, step: PlanStep) -> Dict[str, Any]:
        address, city = step.params["address"], step.params["city"]
        cached = self.cache.get_geo(session.scope, city, address)
        if cached:
            return cached

        point = await self._geocode_with_station_chain(address, city)
        if point is None:
            step.mark(STATUS_FAILED, failure={"reason": "geocode_failed", "address": address})
            raise LookupError(f"无法定位「{address}」")
        self.cache.put_geo(session.scope, city, address, point)
        return point

    async def _geocode_with_station_chain(self, address: str, city: str) -> Optional[Dict[str, float]]:
        """复用 Web 端语义：X地铁站 → X公交站 → 原始地名。"""
        candidates = [address]
        if self.geo_station_fallback:
            candidates = [f"{address}地铁站", f"{address}公交站", address]
        for query in candidates:
            try:
                resp = await self.amap.geocode(address=query, city=city)
            except Exception as exc:  # 网络层错误：记录后继续降级
                last_error = str(exc)
                continue
            geocodes = resp.get("geocodes") or []
            if geocodes and geocodes[0].get("location"):
                point = _parse_lng_lat(geocodes[0]["location"])
                if point:
                    point["label"] = geocodes[0].get("formatted_address") or query
                    point["adcode"] = geocodes[0].get("adcode", "")
                    return point
        return None

    async def _execute_search(self, session: OrchestrationSession, step: PlanStep) -> List[Dict[str, Any]]:
        resp = await self.amap.text_search(
            keywords=step.params["keywords"], city=step.params["city"]
        )
        pois = [
            poi for poi in (resp.get("pois") or [])
            if poi.get("id") and poi.get("location") and _parse_lng_lat(poi["location"])
        ]
        if not pois:
            step.mark(STATUS_FAILED, failure={"reason": "no_restaurants"})
            raise LookupError("未搜索到候选餐厅")
        results = []
        for poi in pois:
            lnglat = _parse_lng_lat(poi["location"])
            enriched = {
                "id": poi["id"],
                "name": poi.get("name", ""),
                "address": poi.get("address", ""),
                "lng": lnglat["lng"],
                "lat": lnglat["lat"],
            }
            key = self.cache.put_poi(session.scope, poi["id"], enriched)
            results.append(enriched | {"key": key})
        return results

    async def _execute_route(self, session: OrchestrationSession, step: PlanStep) -> Dict[str, Any]:
        poi = self.cache.get(session.scope, step.params["poi_key"])
        geo_step = session.plan[step.params["geo_step"]]
        origin = geo_step.result
        city = step.params["city"]
        origin_str = f"{origin['lng']},{origin['lat']}"
        dest_str = f"{poi['lng']},{poi['lat']}"

        # StepGuard：距离规则在调用前拦截（如 >3km 不骑行）
        requested = session.request.get("modes") or ["driving", "transit"]
        allowed, skips, notes = route_mode_decision(origin, poi, requested)

        result: Dict[str, Any] = {"poi_key": step.params["poi_key"]}
        degraded: List[str] = []
        if skips:
            result["skipped_modes"] = skips
        if notes:
            result["notes"] = notes

        if "driving" in allowed:
            try:
                result["driving"] = _drive_minutes(
                    await self.amap.direction_driving(origin_str, dest_str)
                )
            except Exception:
                degraded.append("driving")  # P1-2：失败留痕，transit 兜底
        if "transit" in allowed:
            try:
                result["transit"] = _transit_minutes(
                    await self.amap.direction_transit(origin_str, dest_str, city)
                )
            except Exception:
                pass
        if "bicycle" in allowed:
            bicycle_fn = getattr(self.amap, "direction_bicycling", None)
            if bicycle_fn is not None:
                try:
                    result["bicycle"] = _drive_minutes(await bicycle_fn(origin_str, dest_str))
                except Exception:
                    pass

        minutes = [result.get(m) for m in ("driving", "transit", "bicycle")]
        if all(v is None for v in minutes):
            step.mark(STATUS_FAILED, failure={
                "reason": "all_modes_failed",
                "degraded": degraded,
            })
            raise LookupError("所有出行方式均规划失败")
        if degraded:
            result["degraded_from"] = degraded
        return result

    async def _execute_step(
        self, session: OrchestrationSession, step: PlanStep, trace: Optional[SessionTrace]
    ) -> None:
        step_trace = trace.start_step(step.step_id, step.kind, step.params) if trace else None
        try:
            if step.kind == STEP_GEO:
                result = await self._execute_geo(session, step)
                step.mark(STATUS_DONE, result=result)
            elif step.kind == STEP_SEARCH:
                result = await self._execute_search(session, step)
                step.mark(STATUS_DONE, result=result)
            elif step.kind == STEP_ROUTE:
                result = await self._execute_route(session, step)
                step.mark(STATUS_DONE, result=result)
            elif step.kind == STEP_RANK:
                step.mark(STATUS_DONE)
                result = None
            else:
                result = None

            if step_trace:
                degraded = None
                skipped = None
                if step.kind == STEP_ROUTE and step.result:
                    degraded = step.result.get("degraded_from")
                    skipped = step.result.get("skipped_modes")
                trace.finish_step(
                    step_trace, step.status,
                    degraded_from=degraded,
                    skipped_modes=skipped,
                    api_calls=1 if step.kind != STEP_RANK else 0,
                )
            return

        except LookupError as exc:
            if step_trace:
                trace.finish_step(step_trace, STATUS_FAILED, failure=step.failure, api_calls=1)
            raise
        except Exception as exc:
            step.mark(STATUS_FAILED, failure={"reason": repr(exc)})
            if step_trace:
                trace.finish_step(step_trace, STATUS_FAILED, failure=step.failure, api_calls=1)
            raise

    # ---- 主循环 ---------------------------------------------------------

    async def run(
        self,
        session: OrchestrationSession,
        trace: Optional[SessionTrace] = None,
    ) -> OrchestrationSession:
        session.turn += 1
        route_expanded = False
        while not session.is_closed():
            ready = session.ready_steps()
            if not ready:
                break
            # model_assisted 模式：注入就绪步骤排序
            if self.step_order_fn:
                ready = self.step_order_fn(ready)
            # 同层并行
            results = await asyncio.gather(
                *(self._execute_step(session, step, trace) for step in ready),
                return_exceptions=True,
            )
            for step, result in zip(ready, results):
                if isinstance(result, BaseException) and step.status == STATUS_FAILED:
                    continue
                if isinstance(result, BaseException):
                    step.mark(STATUS_FAILED, failure={"reason": repr(result)})
                    if trace:
                        step_trace = trace.start_step(step.step_id, step.kind, step.params)
                        trace.finish_step(step_trace, STATUS_FAILED, failure=step.failure)

            # search 完成后一次性展开 route 节点
            if not route_expanded:
                search_steps = session.steps_by_kind(STEP_SEARCH)
                if search_steps and search_steps[0].status == STATUS_DONE:
                    pois = search_steps[0].result or []
                    expand_route_steps(session, [p["key"] for p in pois], self.max_route_candidates)
                    route_expanded = True
        return session
