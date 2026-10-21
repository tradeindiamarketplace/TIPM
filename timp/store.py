"""In-memory repository with the uniqueness rules of db/schema.sql.

Production swaps this for PostgreSQL behind the same interface; the constraints
named here exist as UNIQUE indexes there, so behaviour is the same.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable


class UniqueViolation(Exception):
    pass


class NotFound(Exception):
    pass


class Clock:
    def __init__(self, start: datetime | None = None):
        self._now = start or datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self._now

    def advance(self, **kw) -> None:
        self._now += timedelta(**kw)


class Store:
    def __init__(self):
        self._tables: dict[str, dict[str, Any]] = defaultdict(dict)
        self._unique: dict[str, dict[tuple, str]] = defaultdict(dict)
        self._seq: dict[str, int] = defaultdict(int)
        self.idempotency: dict[str, str] = {}

    def new_id(self, prefix: str) -> str:
        self._seq[prefix] += 1
        return f"{prefix}_{self._seq[prefix]:05d}"

    def add(self, table: str, obj: Any, unique: dict[str, tuple] | None = None) -> Any:
        for name, key in (unique or {}).items():
            if key in self._unique[name]:
                raise UniqueViolation(f"{name}={key} already used by {self._unique[name][key]}")
        for name, key in (unique or {}).items():
            self._unique[name][key] = obj.id
        self._tables[table][obj.id] = obj
        return obj

    def lookup(self, constraint: str, key: tuple) -> str | None:
        return self._unique[constraint].get(key)

    def release(self, constraint: str, key: tuple) -> None:
        self._unique[constraint].pop(key, None)

    def get(self, table: str, id_: str) -> Any:
        try:
            return self._tables[table][id_]
        except KeyError:
            raise NotFound(f"{table}/{id_}") from None

    def all(self, table: str) -> list[Any]:
        return list(self._tables[table].values())

    def where(self, table: str, pred: Callable[[Any], bool]) -> list[Any]:
        return [o for o in self._tables[table].values() if pred(o)]

    def tables(self) -> Iterable[str]:
        return self._tables.keys()
