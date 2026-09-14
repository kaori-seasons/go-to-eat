"""MiniCPM 客户端：模型窄接口。

模型只保留两个职责（P0）：
  1. 实体抽取兜底（规则抽取置信度低时，单步 JSON 槽位抽取）
  2. 最终推荐文案生成（把确定性结果表达为自然语言）
模型永远不做编排决策。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import httpx

DEFAULT_API_URL = "https://api.modelbest.cn/v1/chat/completions"
DEFAULT_MODEL = "MiniCPM-V-4.5"

ENTITY_SCHEMA_HINT = """从用户消息中抽取实体，只输出 JSON（不要输出其他内容）：
{"city": "城市名或null", "locations": ["出发地1", "出发地2"], "food": "菜系或null", "meeting_time": "HH:MM或null"}
约束：出发地最多 5 个；城市只能是 北京/上海/广州/深圳/厦门 之一。"""


class MiniCPMClient:
    def __init__(
        self,
        api_key: str,
        api_url: str = DEFAULT_API_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = 60.0,
    ):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.timeout = timeout

    async def chat(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.model, "messages": messages, "stream": False, "temperature": temperature}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.api_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]["content"] or ""

    # ---- 窄接口 1：实体抽取兜底 ----------------------------------------

    async def extract_entities(self, text: str) -> Optional[Dict[str, Any]]:
        raw = await self.chat([
            {"role": "system", "content": ENTITY_SCHEMA_HINT},
            {"role": "user", "content": text},
        ])
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    # ---- 窄接口 2：最终文案 --------------------------------------------

    async def summarize(self, result: Dict[str, Any]) -> str:
        facts = json.dumps(result, ensure_ascii=False)
        return await self.chat([
            {"role": "system", "content": "你是聚餐推荐助手。只根据提供的事实生成简洁推荐，不得编造数据。"},
            {"role": "user", "content": f"事实：{facts}\n请生成推荐语。"},
        ])
