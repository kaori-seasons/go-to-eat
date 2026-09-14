"""规则抽取器：自然语言 → 结构化请求（两级分解中的第一级）。

覆盖 90% 常规表述；低置信度时由上层调用 LLM 兜底窄接口
（输出受 JSON schema 约束的单步抽取，不做自由编排）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

SUPPORTED_CITIES = ("北京", "上海", "广州", "深圳", "厦门")

CUISINES = (
    "日料", "火锅", "烤肉", "烧烤", "川菜", "粤菜", "湘菜", "东北菜",
    "韩餐", "西餐", "素食", "海鲜", "饺子", "面馆", "快餐", "咖啡",
)

_CITY_PATTERN = "|".join(SUPPORTED_CITIES)
_FOOD_PATTERN = "|".join(CUISINES)

# 参与者出发地：支持 "从A和B出发" / "分别从A、B和C出发" / "A和B、C"
_LOCATIONS_RE = re.compile(
    r"(?:分别)?从(.+?)出发"
)
_MEETING_TIME_RE = re.compile(r"(\d{1,2})[点时:：](\d{1,2})?分?(?:钟)?(?:之?前)?到")


@dataclass
class ExtractedRequest:
    city: Optional[str] = None
    locations: List[str] = field(default_factory=list)
    food: str = "餐厅"
    meeting_time: Optional[str] = None
    confidence: float = 0.0
    issues: List[str] = field(default_factory=list)

    @property
    def needs_llm_fallback(self) -> bool:
        return self.confidence < 0.6

    def to_request(self) -> Dict[str, Any]:
        return {
            "city": self.city,
            "locations": self.locations,
            "food": self.food,
            "meeting_time": self.meeting_time,
        }


class LLMEntityFallback(Protocol):
    """模型兜底窄接口：只允许输出实体槽位，不允许输出编排决策。"""

    async def extract_entities(self, text: str) -> Optional[Dict[str, Any]]:
        ...


_PRONOUN_RE = re.compile(r"^(?:我们?|大家|朋友[们]?|同事[们]?|伙伴[们]?)+")

# 连接词切分：按"和/与/及"切分存在误伤含"和"地名（如"和平里"）的小概率风险，
# 当前支撑城市内无此类高频出发地，P0 采取激进切分；误伤由低置信度兜底接口接管。
_LOC_SEP_RE = re.compile(r"[、，,和与及\s]+")


def _split_locations(raw: str) -> List[str]:
    raw = _PRONOUN_RE.sub("", raw.strip())
    parts = _LOC_SEP_RE.split(raw)
    return [p for p in (part.strip() for part in parts) if p]


class RuleExtractor:
    """确定性实体抽取。"""

    def extract(self, text: str) -> ExtractedRequest:
        req = ExtractedRequest()

        city_match = re.search(_CITY_PATTERN, text)
        if city_match:
            req.city = city_match.group(0)

        food_match = re.search(_FOOD_PATTERN, text)
        if food_match:
            req.food = food_match.group(0)

        loc_match = _LOCATIONS_RE.search(text)
        if loc_match:
            req.locations = _split_locations(loc_match.group(1))
        req.locations = req.locations[:5]  # 产品约束：2-5 人

        time_match = _MEETING_TIME_RE.search(text)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                req.meeting_time = f"{hour:02d}:{minute:02d}"

        # 置信度打分
        if not req.city:
            req.issues.append("missing_city")
        if len(req.locations) < 2:
            req.issues.append("insufficient_locations")
        req.confidence = 1.0 - 0.4 * len(req.issues)
        return req
