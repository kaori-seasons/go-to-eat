"""磁盘实体缓存（P2-2）：SQLite 后端 + TTL 过期。

继承 EntityCache 接口，启动时从磁盘恢复条目，
写入时同步落盘。坐标 7 天、POI 1 天。
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Dict, Optional

from .memory import EntityCache

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entity_cache (
    scope      TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    expires_at REAL NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (scope, key)
);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON entity_cache(expires_at);
"""


class DiskEntityCache(EntityCache):
    """SQLite 持久化实体缓存。

    启动时从磁盘恢复未过期条目；写入时同步落盘。
    适合自托管后端；Cloudflare Functions 环境请用内存版。
    """

    def __init__(self, db_path: str = "orchestrator_cache.db", **kwargs):
        super().__init__(**kwargs)
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(_SCHEMA)
        self._recover_from_disk()

    def _recover_from_disk(self) -> None:
        """启动时恢复未过期条目到内存。"""
        now = time.time()
        rows = self._conn.execute(
            "SELECT scope, key, value, expires_at FROM entity_cache WHERE expires_at > ?",
            (now,),
        ).fetchall()
        for scope, key, value_json, expires_at in rows:
            sk = (scope, key)
            from .memory import CacheEntry
            self._store[sk] = CacheEntry(json.loads(value_json), expires_at)

    def put_geo(self, scope: str, city: str, name: str, point: Dict[str, Any]) -> str:
        key = super().put_geo(scope, city, name, point)
        self._persist(scope, key, point, self.geo_ttl)
        return key

    def put_poi(self, scope: str, poi_id: str, poi: Dict[str, Any]) -> str:
        key = super().put_poi(scope, poi_id, poi)
        self._persist(scope, key, poi, self.poi_ttl)
        return key

    def _persist(self, scope: str, key: str, value: Any, ttl: float) -> None:
        now = time.time()
        self._conn.execute(
            "INSERT OR REPLACE INTO entity_cache (scope, key, value, expires_at, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (scope, key, json.dumps(value, ensure_ascii=False), now + ttl, now),
        )
        self._conn.commit()

    def cleanup_expired(self) -> int:
        """删除已过期的磁盘条目，返回删除数量。"""
        cursor = self._conn.execute(
            "DELETE FROM entity_cache WHERE expires_at < ?", (time.time(),)
        )
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._conn.close()
