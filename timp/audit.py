"""Append-only, hash-chained audit log (Agent M). Any edit to a past event breaks verify()."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from .domain import AuditEvent

GENESIS = "0" * 64


def _digest(prev: str, at: datetime, actor: str, action: str, subject: str, details: dict) -> str:
    body = json.dumps([prev, at.isoformat(), actor, action, subject, details], sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()


class AuditLog:
    def __init__(self, clock):
        self._clock = clock
        self._events: list[AuditEvent] = []

    def record(self, actor_id: str, action: str, subject: str, **details: Any) -> AuditEvent:
        prev = self._events[-1].hash if self._events else GENESIS
        at = self._clock.now()
        ev = AuditEvent(len(self._events) + 1, at, actor_id, action, subject, details, prev,
                        _digest(prev, at, actor_id, action, subject, details))
        self._events.append(ev)
        return ev

    def events(self, action: str | None = None, subject: str | None = None) -> list[AuditEvent]:
        return [e for e in self._events
                if (action is None or e.action == action) and (subject is None or e.subject == subject)]

    def verify(self) -> bool:
        prev = GENESIS
        for e in self._events:
            if e.prev_hash != prev or e.hash != _digest(prev, e.at, e.actor_id, e.action, e.subject, e.details):
                return False
            prev = e.hash
        return True
