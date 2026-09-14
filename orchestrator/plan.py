"""Plan DAG：把一次聚餐请求物化为步骤节点与依赖边（≈ IGID memory_graph）。

节点在请求到达时即建图（geo/search/rank），route 节点在 search 结果
确定后由执行器动态展开——依赖关系永远显式存在于数据结构中，
不再依赖模型在上下文里"心算"计划。
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

STATUS_PENDING = "pending"
STATUS_READY = "ready"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

STEP_GEO = "geo"
STEP_SEARCH = "search"
STEP_ROUTE = "route"
STEP_RANK = "rank"


def _slug(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", name) or "x"


@dataclass
class PlanStep:
    step_id: str
    kind: str
    params: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)
    status: str = STATUS_PENDING
    result_ref: Optional[str] = None
    result: Any = None
    failure: Optional[Dict[str, Any]] = None

    def mark(self, status: str, result: Any = None, failure: Dict[str, Any] | None = None) -> None:
        self.status = status
        if result is not None:
            self.result = result
        if failure is not None:
            self.failure = failure


@dataclass
class OrchestrationSession:
    """一次聚餐请求的编排状态。scope 用于会话隔离（≈ group_isolation）。"""

    request: Dict[str, Any]          # {city, locations, food, meeting_time}
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    scope: str = "default"
    turn: int = 0
    created_at: float = field(default_factory=time.time)
    plan: Dict[str, PlanStep] = field(default_factory=dict)

    def add_step(self, step: PlanStep) -> PlanStep:
        if step.step_id in self.plan:
            raise ValueError(f"duplicate step_id: {step.step_id}")
        self.plan[step.step_id] = step
        return step

    def steps_by_kind(self, kind: str) -> List[PlanStep]:
        return [s for s in self.plan.values() if s.kind == kind]

    def ready_steps(self) -> List[PlanStep]:
        """依赖全部 done、自身未执行的步骤。"""
        ready = []
        for step in self.plan.values():
            if step.status not in (STATUS_PENDING, STATUS_READY):
                continue
            deps = [self.plan[dep] for dep in step.depends_on if dep in self.plan]
            if all(dep.status == STATUS_DONE for dep in deps):
                ready.append(step)
        return ready

    def progress(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for step in self.plan.values():
            counts[step.status] = counts.get(step.status, 0) + 1
        counts["total"] = len(self.plan)
        return counts

    def is_closed(self) -> bool:
        return all(
            s.status in (STATUS_DONE, STATUS_FAILED, STATUS_SKIPPED)
            for s in self.plan.values()
        )


class PlanDagBuilder:
    """由结构化请求构建阶段一 DAG：geo* N → search → rank。"""

    def __init__(self, max_route_candidates: int = 5):
        self.max_route_candidates = max_route_candidates

    def build(self, session: OrchestrationSession) -> OrchestrationSession:
        req = session.request
        city = req["city"]
        geo_ids: Dict[str, str] = {}
        for location in req["locations"]:
            slug = _slug(location)
            geo_ids[location] = session.add_step(PlanStep(
                step_id=f"geo:{slug}",
                kind=STEP_GEO,
                params={"address": location, "city": city},
            )).step_id
        search_id = session.add_step(PlanStep(
            step_id="search:food",
            kind=STEP_SEARCH,
            params={"keywords": req.get("food") or "餐厅", "city": city},
            depends_on=[],
        )).step_id
        session.add_step(PlanStep(
            step_id="rank:final",
            kind=STEP_RANK,
            params={"strategy": req.get("strategy", "max")},
            depends_on=[search_id],
        ))
        return session


def reset_downstream(session: OrchestrationSession, new_keywords: Optional[str] = None) -> None:
    """多轮指令"换菜系"：删除全部 route 节点，search 重置为 pending。

    geo 结果保留（done），不重复地理编码。
    """
    for step in session.steps_by_kind(STEP_ROUTE):
        del session.plan[step.step_id]
    search = next(s for s in session.plan.values() if s.kind == STEP_SEARCH)
    if new_keywords:
        search.params["keywords"] = new_keywords
    search.status = STATUS_PENDING
    search.result = None
    search.failure = None
    rank = session.plan["rank:final"]
    rank.depends_on = [search.step_id]
    rank.status = STATUS_PENDING
    rank.result = None


def add_participant(session: OrchestrationSession, location: str) -> PlanStep:
    """多轮指令"加一个人"：新增 geo 节点；route 层由 expand_route_steps 补齐。"""
    return session.add_step(PlanStep(
        step_id=f"geo:{_slug(location)}",
        kind=STEP_GEO,
        params={"address": location, "city": session.request["city"]},
    ))


def reset_routes_only(session: OrchestrationSession) -> None:
    """加人后：删除旧 route 节点（新参与者需要全量重算），保留 search/geo 结果。"""
    for step in session.steps_by_kind(STEP_ROUTE):
        del session.plan[step.step_id]
    rank = session.plan["rank:final"]
    rank.depends_on = [s.step_id for s in session.plan.values() if s.kind == STEP_SEARCH]
    rank.status = STATUS_PENDING
    rank.result = None


def expand_route_steps(
    session: OrchestrationSession,
    poi_keys: List[str],
    max_candidates: int,
) -> List[PlanStep]:
    """search 完成后展开 route 节点：每个候选餐厅 × 每个参与者。"""
    created = []
    search = next(s for s in session.plan.values() if s.kind == STEP_SEARCH)
    for poi_key in poi_keys[:max_candidates]:
        for step in session.steps_by_kind(STEP_GEO):
            step_id = f"route:{poi_key}:{step.step_id.split(':', 1)[1]}"
            if step_id in session.plan:
                continue
            created.append(session.add_step(PlanStep(
                step_id=step_id,
                kind=STEP_ROUTE,
                params={
                    "poi_key": poi_key,
                    "geo_step": step.step_id,
                    "city": session.request["city"],
                },
                depends_on=[step.step_id, search.step_id],
            )))
        # rank 依赖所有 route
    rank = session.plan["rank:final"]
    rank.depends_on.extend(step.step_id for step in created
                           if step.step_id not in rank.depends_on)
    return created
