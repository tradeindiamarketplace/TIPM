"""Shared gate exception and retry helper."""
from __future__ import annotations

import time
from typing import Any, Callable

from .channels import AdapterError


class GateBlocked(Exception):
    def __init__(self, action: str, reasons: list[str]):
        super().__init__(f"{action} blocked: " + "; ".join(reasons))
        self.reasons = reasons


def call_with_retry(fn: Callable[[], Any], attempts: int = 4, base_delay: float = 0.5,
                    sleep: Callable[[float], None] = time.sleep) -> Any:
    """Exponential backoff for transient AdapterErrors only; anything else surfaces at once."""
    for n in range(attempts):
        try:
            return fn()
        except AdapterError:
            if n == attempts - 1:
                raise
            sleep(base_delay * 2 ** n)
