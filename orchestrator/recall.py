"""召回投影器（P1-4，≈ IGID memory_recall）。

每轮模型调用前，把编排状态投影为紧凑上下文：
进度 → 可执行步骤 → 已固化事实，硬预算 1200 token，
超限按优先级截断。投影只描述"当前该决定什么"，
不注入任何路线原始 JSON。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .plan import (
    OrchestrationSession,
    PlanStep,
    STATUS_SKIPPED,
    STEP_GEO,
    STEP_ROUTE,
)

TOKEN_BUDGET = 1200


def estimate_tokens(text: str) -> int:
    """粗估：CJK 字符 ≈1 token，其余按 4 字符 ≈1 token。"""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return cjk + (len(text) - cjk) // 4


def project(session: OrchestrationSession, budget: int = TOKEN_BUDGET) -> str:
    ready = session.ready_steps()
    progress = session.progress()

    lines: List[str] = [
        f"[计划进度] 共 {progress.get('total', 0)} 步，"
        f"完成 {progress.get('done', 0)}，失败 {progress.get('failed', 0)}，"
        f"跳过 {progress.get('skipped', 0)}。"
    ]

    # 跳过留痕（最高优先级之一：解释为什么少了某些步骤）
    for step in session.plan.values():
        if step.status == STATUS_SKIPPED and step.failure:
            lines.append(f"[已跳过] {step.step_id}：{step.failure.get('reason', '规则拦截')}")

    # 失败留痕
    for step in session.plan.values():
        if step.status == "failed" and step.failure:
            lines.append(f"[失败] {step.step_id}：{step.failure.get('reason', '未知')}")

    if ready:
        lines.append("[本次只需决定] 以下就绪步骤的执行：")
        for step in ready:
            lines.append(f"  - {step.step_id}（{step.kind}）参数槽位：{_params_brief(step)}")
    else:
        lines.append("[本次无需调用工具] 所有步骤已闭合。")

    lines.append("[已固化事实]")
    lines.append(_facts_brief(session))

    # 预算截断：保进度与就绪步骤，砍事实尾部
    text = "\n".join(lines)
    if estimate_tokens(text) <= budget:
        return text
    while lines and estimate_tokens("\n".join(lines)) > budget:
        # 从"已固化事实"段尾开始砍
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].startswith(("[已固化事实]", "  ·")):
                del lines[i]
                break
        else:
            del lines[-1]
        text = "\n".join(lines)
    return text


def _params_brief(step: PlanStep) -> str:
    if step.kind == STEP_ROUTE:
        return f"origin=<{step.params['geo_step']}坐标> destination=<{step.params['poi_key']}坐标>"
    return ", ".join(f"{k}={v}" for k, v in step.params.items())


def _facts_brief(session: OrchestrationSession, max_items: int = 12) -> str:
    facts: List[str] = []
    for step in session.steps_by_kind(STEP_GEO):
        if step.status == "done" and step.result:
            facts.append(
                f"  · {step.params['address']}({step.result['lng']},{step.result['lat']})"
            )
    search = next((s for s in session.plan.values() if s.kind == "search"), None)
    if search and search.status == "done" and search.result:
        names = [p["name"] for p in search.result[:max_items]]
        facts.append(f"  · 候选餐厅 {len(search.result)} 家：{'、'.join(names)}")
    return "\n".join(facts) if facts else "  · （暂无）"
