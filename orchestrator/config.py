"""编排配置（P2-4）：orchestration_mode 灰度开关 + 全局配置。

deterministic（默认）：编排全确定性，模型只做实体兜底与文案生成。
model_assisted：模型参与就绪步骤排序决策（需传入 LLM 客户端）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class OrchestrationMode(str, Enum):
    DETERMINISTIC = "deterministic"
    MODEL_ASSISTED = "model_assisted"


@dataclass
class OrchestratorConfig:
    mode: OrchestrationMode = OrchestrationMode.DETERMINISTIC
    max_route_candidates: int = 5
    recall_token_budget: int = 1200
    db_path: Optional[str] = None  # None = 内存缓存；字符串 = 磁盘路径
    enable_disk_cache: bool = False
    enable_tracing: bool = True

    @classmethod
    def from_dict(cls, d: dict) -> "OrchestratorConfig":
        mode = d.get("mode", "deterministic")
        return cls(
            mode=OrchestrationMode(mode),
            max_route_candidates=d.get("max_route_candidates", 5),
            recall_token_budget=d.get("recall_token_budget", 1200),
            db_path=d.get("db_path"),
            enable_disk_cache=d.get("enable_disk_cache", False),
            enable_tracing=d.get("enable_tracing", True),
        )
