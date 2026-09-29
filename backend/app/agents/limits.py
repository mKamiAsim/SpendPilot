"""Caps for one deep review, until evaluation says otherwise."""

from __future__ import annotations

from datetime import timedelta

MAX_MODEL_CALLS = 40
MAX_DELEGATION_DEPTH = 2
MAX_PARALLEL_SPECIALISTS = 2
REVIEW_DEADLINE = timedelta(minutes=10)


class ReviewLimit(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class Budget:
    def __init__(self) -> None:
        self.calls = 0

    def charge(self, count: int = 1) -> None:
        if count < 1:
            raise ReviewLimit("budget", "A model call count must be positive.")
        if self.calls + count > MAX_MODEL_CALLS:
            raise ReviewLimit("budget", "This review reached the 40 model-call limit.")
        self.calls += count
