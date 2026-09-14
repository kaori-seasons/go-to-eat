"""管线门面：抽取 → 建图 → 确定性执行 → 排序 →（可选）模型文案。

用法：
    pipeline = RecommendationPipeline(amap=RealAmapClient(key))
    result = await pipeline.run("我们两个人分别从望京和霍营出发，想吃烤肉")

P2 支持：
    - orchestration_mode 灰度开关（deterministic | model_assisted）
    - 结构化 trace 留痕（每步耗时、降级、失败原因）
    - 磁盘缓存 TTL
"""

from __future__ import annotations

import re as _re
import uuid
from typing import Any, Dict, List, Optional

from .config import OrchestratorConfig, OrchestrationMode
from .executor import AmapLike, OrchestratorExecutor, StepOrderFn
from .extractor import CUISINES, ExtractedRequest, LLMEntityFallback, RuleExtractor
from .memory import EntityCache
from .plan import (
    OrchestrationSession,
    PlanDagBuilder,
    STEP_ROUTE,
    add_participant,
    reset_downstream,
    reset_routes_only,
)
from .plan import _slug
from .ranker import MODE_LABELS, rank_candidates
from .recall import project as recall_project
from .session_store import SessionStore
from .tracing import SessionTrace


def _match_cuisine(text: str) -> Optional[str]:
    for cuisine in CUISINES:
        if cuisine in text:
            return cuisine
    return None


def _match_meeting_time(text: str) -> Optional[str]:
    m = _re.search(r"(\d{1,2})[点时:：](\d{1,2})?分?", text)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2) or 0)
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}"
    return None


class RecommendationPipeline:
    def __init__(
        self,
        amap: AmapLike,
        llm: Optional[LLMEntityFallback] = None,
        cache: Optional[EntityCache] = None,
        config: Optional[OrchestratorConfig] = None,
        step_order_fn: Optional[StepOrderFn] = None,
    ):
        self.config = config or OrchestratorConfig()
        self.extractor = RuleExtractor()
        self.llm = llm
        self.cache = cache or EntityCache()
        self.step_order_fn = step_order_fn
        self.executor = OrchestratorExecutor(
            amap,
            cache=self.cache,
            max_route_candidates=self.config.max_route_candidates,
            step_order_fn=step_order_fn,
        )

    async def _extract(self, text: str) -> ExtractedRequest:
        req = self.extractor.extract(text)
        if req.needs_llm_fallback and self.llm is not None:
            entities = await self.llm.extract_entities(text)
            if entities:
                if not req.city and entities.get("city"):
                    req.city = entities["city"]
                if len(req.locations) < 2 and entities.get("locations"):
                    req.locations = entities["locations"][:5]
                if entities.get("food"):
                    req.food = entities["food"]
                if not req.meeting_time and entities.get("meeting_time"):
                    req.meeting_time = entities["meeting_time"]
        if not req.city:
            raise ValueError("无法确定城市，请明确指定（北京/上海/广州/深圳/厦门）")
        if len(req.locations) < 2:
            raise ValueError("至少需要 2 位参与者的出发地")
        return req

    async def run(
        self,
        text: str,
        session_id: Optional[str] = None,
        scope: str = "default",
        strategy: str = "max",
        modes: Optional[List[str]] = None,
        summarize: bool = False,
        store: Optional[SessionStore] = None,
    ) -> Dict[str, Any]:
        req = await self._extract(text)
        request = req.to_request()
        request["strategy"] = strategy
        request["modes"] = modes or ["driving", "transit"]

        session = OrchestrationSession(
            request=request,
            session_id=session_id or uuid.uuid4().hex[:12],
            scope=scope,
        )
        trace = SessionTrace(
            session_id=session.session_id,
            scope=scope,
            mode=self.config.mode.value,
        )
        PlanDagBuilder(max_route_candidates=self.executor.max_route_candidates).build(session)
        session = await self.executor.run(session, trace=trace)
        if store is not None:
            store.save(session)

        ranking = self._collect_and_rank(session, request["modes"], strategy)
        return await self._format(session, req, ranking, summarize, trace)

    # ---- 多轮续跑（P1-3/P1-5）--------------------------------------------

    async def follow_up(
        self,
        session_id: str,
        text: str,
        store: SessionStore,
        strategy: str = "max",
        summarize: bool = False,
    ) -> Dict[str, Any]:
        """增量修改已闭合会话：换菜系 / 加人 / 改时间。geo 结果零重复调用。"""
        session = store.load(session_id)
        if session is None:
            raise KeyError(f"session not found: {session_id}")

        food = _match_cuisine(text)
        if food:
            session.request["food"] = food
            reset_downstream(session, new_keywords=food)
        if ("加" in text or "增加" in text or "多" in text) and "从" in text:
            location = text.split("从", 1)[1].split("出发")[0].strip("、，,和与 ")
            if location and f"geo:{_slug(location)}" not in session.plan:
                add_participant(session, location)
                session.request["locations"].append(location)
                reset_routes_only(session)
        meeting = _match_meeting_time(text)
        if meeting:
            session.request["meeting_time"] = meeting
            # 改时间不触发任何工具调用：排序结果与时间无关
            if store is not None:
                store.save(session)
            ranking = self._collect_and_rank(session, session.request["modes"], strategy)
            if ranking["recommended"] is None:
                raise RuntimeError("会话中没有可用的路线结果")
            return await self._format(session, self._req_from(session), ranking, summarize)

        trace = SessionTrace(
            session_id=session.session_id,
            scope=session.scope,
            mode=self.config.mode.value,
        )
        session = await self.executor.run(session, trace=trace)
        if store is not None:
            store.save(session)
        ranking = self._collect_and_rank(session, session.request["modes"], strategy)
        if not ranking["recommended"]:
            raise RuntimeError("没有任何候选餐厅能被所有参与者到达，请调整出发地或出行方式")
        return await self._format(session, self._req_from(session), ranking, summarize, trace)

    def _req_from(self, session: OrchestrationSession) -> ExtractedRequest:
        return ExtractedRequest(
            city=session.request.get("city"),
            locations=list(session.request.get("locations", [])),
            food=session.request.get("food", "餐厅"),
            meeting_time=session.request.get("meeting_time"),
            confidence=1.0,
        )

    # ---- 聚合与排序 -------------------------------------------------------

    def _collect_and_rank(
        self,
        session: OrchestrationSession,
        modes: List[str],
        strategy: str,
    ) -> Dict[str, Any]:
        routes_by_poi: Dict[str, List[Dict[str, Any]]] = {}
        for step in session.steps_by_kind(STEP_ROUTE):
            if step.status != "done" or step.result is None:
                continue
            routes_by_poi.setdefault(step.result["poi_key"], []).append({
                m: step.result.get(m) for m in modes
            })
        pois = []
        for key in routes_by_poi:
            poi = self.cache.get(session.scope, key)
            if poi:
                pois.append({**poi, "key": key})
        ranking = rank_candidates(session.plan, routes_by_poi, pois, modes=modes, strategy=strategy)
        if not ranking["recommended"]:
            raise RuntimeError("没有任何候选餐厅能被所有参与者到达，请调整出发地或出行方式")
        return ranking

    # ---- 输出格式化 ------------------------------------------------------

    async def _format(
        self,
        session: OrchestrationSession,
        req: ExtractedRequest,
        ranking: Dict[str, Any],
        summarize: bool,
        trace: Optional[SessionTrace] = None,
    ) -> Dict[str, Any]:
        def candidate_view(item: Dict[str, Any], selected: bool) -> Dict[str, Any]:
            poi, score = item["poi"], item["score"]
            return {
                "name": poi.get("name", ""),
                "address": poi.get("address", ""),
                "location": f"{poi['lng']},{poi['lat']}",
                "recommendedMode": MODE_LABELS[score["mode"]],
                "maxMin": round(score["max"], 1),
                "spreadMin": round(score["spread"], 1),
                "avgMin": round(score["avg"], 1),
                "selected": selected,
                "routes": [
                    {
                        "mode": MODE_LABELS[score["mode"]],
                        "minutes": round(route[score["mode"]], 1),
                    }
                    for route in item["routes"]
                ],
            }

        result: Dict[str, Any] = {
            "session_id": session.session_id,
            "city": req.city,
            "food": req.food,
            "meeting_time": req.meeting_time,
            "strategy": ranking["strategy"],
            "resolvedParticipants": [
                {
                    "input": step.params["address"],
                    "resolved": (step.result or {}).get("label", ""),
                    "location": (
                        f"{step.result['lng']},{step.result['lat']}"
                        if step.result else None
                    ),
                }
                for step in session.plan.values() if step.kind == "geo"
            ],
            "recommended": candidate_view(ranking["recommended"], True),
            "alternatives": [candidate_view(item, False) for item in ranking["alternatives"]],
            "planProgress": session.progress(),
        }
        if trace is not None and self.config.enable_tracing:
            result["orchestration_trace"] = trace.to_dict()
            result["trace_summary"] = trace.summary()
        if summarize and self.llm is not None:
            if hasattr(self.llm, "summarize"):
                result["summary_text"] = await self.llm.summarize(result)
        return result
