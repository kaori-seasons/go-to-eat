"""公平性排序：从 functions/lib/recommendation.js 的 scoreCandidate 移植。

三种策略（与 Web 端语义一致，作为单一事实源的 Python 镜像）：
  max     → 最慢的人更快：max -> spread -> avg
  spread  → 时间差最小：  spread -> max -> avg
  average → 平均耗时最低：avg -> max -> spread
纯代码计算，不涉及模型。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

STRATEGY_MAX = "max"
STRATEGY_SPREAD = "spread"
STRATEGY_AVERAGE = "average"

MODE_LABELS = {"driving": "驾车", "transit": "公共交通"}


def score_candidate(
    routes: List[Dict[str, Optional[float]]],
    modes: List[str],
    strategy: str = STRATEGY_MAX,
) -> Optional[Dict[str, Any]]:
    """routes: 每位参与者一项 {driving: minutes|None, transit: minutes|None}。

    返回该候选餐厅的最佳出行方式评分；任一模式下有人缺数据则跳过该模式。
    """
    participant_count = len(routes)
    scores = []
    for mode in modes:
        values = [route.get(mode) for route in routes]
        if len(values) != participant_count or any(v is None for v in values):
            continue
        avg = sum(values) / len(values)
        variance = sum((v - avg) ** 2 for v in values) / len(values)
        vmax = max(values)
        spread = vmax - min(values)
        metrics = {"mode": mode, "max": vmax, "avg": avg, "variance": variance, "spread": spread}
        if strategy == STRATEGY_MAX:
            metrics.update(primary=vmax, secondary=spread, tertiary=avg)
        elif strategy == STRATEGY_AVERAGE:
            metrics.update(primary=avg, secondary=spread, tertiary=vmax)
        else:
            metrics.update(primary=spread, secondary=vmax, tertiary=avg)
        scores.append(metrics)
    if not scores:
        return None
    return min(scores, key=lambda s: (s["primary"], s["secondary"], s["tertiary"]))


def rank_candidates(
    session_plan: Dict[str, Any],
    routes_by_poi: Dict[str, List[Dict[str, Optional[float]]]],
    pois: List[Dict[str, Any]],
    modes: List[str],
    strategy: str = STRATEGY_MAX,
) -> Dict[str, Any]:
    """对全部候选评分、排序，产出 1 推荐 + ≤2 备选。"""
    viable = []
    for poi in pois:
        routes = routes_by_poi.get(poi["key"])
        if not routes:
            continue
        score = score_candidate(routes, modes, strategy)
        if score is None:
            continue
        viable.append({"poi": poi, "score": score, "routes": routes})
    viable.sort(key=lambda item: (item["score"]["primary"],
                                  item["score"]["secondary"],
                                  item["score"]["tertiary"]))
    finalists = viable[:3]
    if not finalists:
        return {"recommended": None, "alternatives": [], "strategy": strategy}
    return {
        "recommended": finalists[0],
        "alternatives": finalists[1:3],
        "strategy": strategy,
    }
