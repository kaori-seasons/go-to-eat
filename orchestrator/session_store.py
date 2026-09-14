"""会话持久化（P1-3）：SQLite 后端 + scope 隔离（≈ IGID save_manager + group_isolation）。

只存紧凑编排状态（plan 槽位 + 请求字段），不存工具原始大响应——
大结果仍由 EntityCache 承载；store 负责"关机后计划不失忆"。
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional

from .plan import OrchestrationSession, PlanStep

_SCHEMA = """
CREATE TABLE IF NOT EXISTS orchestration_sessions (
    session_id TEXT PRIMARY KEY,
    scope      TEXT NOT NULL,
    turn       INTEGER NOT NULL,
    request    TEXT NOT NULL,
    plan       TEXT NOT NULL,
    updated_at REAL NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_scope ON orchestration_sessions(scope);
"""


class SessionStore:
    def __init__(self, path: str = ":memory:"):
        self._conn = sqlite3.connect(path)
        self._conn.executescript(_SCHEMA)

    def save(self, session: OrchestrationSession) -> None:
        plan = {
            sid: {
                "step_id": s.step_id,
                "kind": s.kind,
                "params": s.params,
                "depends_on": s.depends_on,
                "status": s.status,
                "result_ref": s.result_ref,
                "result": s.result,
                "failure": s.failure,
            }
            for sid, s in session.plan.items()
        }
        self._conn.execute(
            "INSERT OR REPLACE INTO orchestration_sessions"
            " (session_id, scope, turn, request, plan, updated_at, created_at)"
            " VALUES (?, ?, ?, ?, ?, strftime('%s','now'), ?)",
            (
                session.session_id,
                session.scope,
                session.turn,
                json.dumps(session.request, ensure_ascii=False),
                json.dumps(plan, ensure_ascii=False),
                session.created_at,
            ),
        )
        self._conn.commit()

    def load(self, session_id: str) -> Optional[OrchestrationSession]:
        row = self._conn.execute(
            "SELECT session_id, scope, turn, request, plan, created_at"
            " FROM orchestration_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        sid, scope, turn, request, plan, created_at = row
        session = OrchestrationSession(
            request=json.loads(request),
            session_id=sid,
            scope=scope,
            turn=turn,
            created_at=created_at,
        )
        for data in json.loads(plan).values():
            session.add_step(PlanStep(
                step_id=data["step_id"],
                kind=data["kind"],
                params=data["params"],
                depends_on=data["depends_on"],
                status=data["status"],
                result_ref=data["result_ref"],
                result=data["result"],
                failure=data["failure"],
            ))
        return session

    def list_sessions(self, scope: Optional[str] = None) -> List[Dict[str, Any]]:
        if scope is None:
            rows = self._conn.execute(
                "SELECT session_id, scope, turn FROM orchestration_sessions"
                " ORDER BY updated_at DESC"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT session_id, scope, turn FROM orchestration_sessions"
                " WHERE scope = ? ORDER BY updated_at DESC",
                (scope,),
            ).fetchall()
        return [{"session_id": r[0], "scope": r[1], "turn": r[2]} for r in rows]

    def close(self) -> None:
        self._conn.close()
