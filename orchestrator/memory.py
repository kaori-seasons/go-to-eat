"""实体缓存（≈ IGID 人物印象）。

把工具结果固化为紧凑槽位：地名→坐标、POI→名称/坐标。
同一会话内零重复调用；scope 隔离保证并发会话零串线。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass
class CacheEntry:
    value: Any
    expires_at: float


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


class EntityCache:
    """会话级实体缓存。坐标默认 7 天 TTL，POI 默认 1 天。"""

    def __init__(self, geo_ttl: float = 7 * 86400, poi_ttl: float = 86400):
        self._store: Dict[Tuple[str, str], CacheEntry] = {}
        self._stats = CacheStats()
        self.geo_ttl = geo_ttl
        self.poi_ttl = poi_ttl

    def _scoped_key(self, scope: str, key: str) -> Tuple[str, str]:
        return (scope, key)

    def get(self, scope: str, key: str) -> Optional[Any]:
        entry = self._store.get(self._scoped_key(scope, key))
        if entry is None:
            self._stats.misses += 1
            return None
        if entry.expires_at < time.time():
            del self._store[self._scoped_key(scope, key)]
            self._stats.misses += 1
            return None
        self._stats.hits += 1
        return entry.value

    def put_geo(self, scope: str, city: str, name: str, point: Dict[str, Any]) -> str:
        key = f"geo:{city}:{name}"
        self._store[self._scoped_key(scope, key)] = CacheEntry(point, time.time() + self.geo_ttl)
        return key

    def get_geo(self, scope: str, city: str, name: str) -> Optional[Dict[str, Any]]:
        return self.get(scope, f"geo:{city}:{name}")

    def put_poi(self, scope: str, poi_id: str, poi: Dict[str, Any]) -> str:
        key = f"poi:{poi_id}"
        self._store[self._scoped_key(scope, key)] = CacheEntry(poi, time.time() + self.poi_ttl)
        return key

    def get_poi(self, scope: str, poi_id: str) -> Optional[Dict[str, Any]]:
        return self.get(scope, f"poi:{poi_id}")

    def clear(self, scope: Optional[str] = None) -> None:
        if scope is None:
            self._store.clear()
        else:
            self._store = {k: v for k, v in self._store.items() if k[0] != scope}

    @property
    def stats(self) -> CacheStats:
        return self._stats
