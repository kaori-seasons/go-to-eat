"""StepGuard：业务规则前置层（P1-1）。

条件分支不下放给模型——距离/格式类规则在此硬编码拦截，
被跳过的步骤以 skipped 留痕，保证可解释性。
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

BICYCLE_MAX_KM = 3.0        # 超过 3km 不推荐骑行
DRIVING_SUGGEST_KM = 25.0   # 超过 25km 提示以公共交通为主


def haversine_km(origin: Dict[str, float], dest: Dict[str, float]) -> float:
    """球面距离（km）。入参为 {'lng': float, 'lat': float}。"""
    radians = math.pi / 180
    lat1, lat2 = origin["lat"] * radians, dest["lat"] * radians
    d_lat = (dest["lat"] - origin["lat"]) * radians
    d_lng = (dest["lng"] - origin["lng"]) * radians
    a = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
    return 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))


def validate_coord_str(value: str) -> bool:
    """校验 "lng,lat" 格式与范围。"""
    try:
        lng, lat = (float(v) for v in value.split(","))
    except (ValueError, AttributeError):
        return False
    return -180 <= lng <= 180 and -90 <= lat <= 90


def route_mode_decision(
    origin: Dict[str, float],
    dest: Dict[str, float],
    modes: List[str],
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """根据直线距离决定每个 route 步骤实际执行哪些出行方式。

    返回 (允许执行的模式列表, 跳过留痕列表)。
    直线距离通常为实际路程的 0.7-0.85 倍，规则阈值已考虑该偏差。
    """
    distance = haversine_km(origin, dest)
    allowed: List[str] = []
    skips: List[Dict[str, Any]] = []
    for mode in modes:
        if mode == "bicycle" and distance > BICYCLE_MAX_KM:
            skips.append({
                "mode": mode,
                "rule": f"distance {distance:.1f}km > {BICYCLE_MAX_KM}km",
            })
            continue
        allowed.append(mode)
    notes = []
    if distance > DRIVING_SUGGEST_KM and "driving" in allowed:
        notes.append(f"distance {distance:.1f}km > {DRIVING_SUGGEST_KM}km，建议以公共交通为主")
    return allowed, skips, notes
