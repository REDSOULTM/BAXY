"""Shared base for internal computer-use capabilities."""
from __future__ import annotations

from typing import Any


class Capability:
    """Small internal executor for one domain of computer-use primitives."""

    ops: frozenset[str] = frozenset()

    def __init__(self, executor: Any):
        self.executor = executor

    @property
    def ag(self) -> Any:
        return self.executor.ag

    @property
    def tools(self) -> Any:
        return self.executor.tools

    def run(self, op: str, arg: str, app_token: str) -> tuple[dict, str]:
        raise NotImplementedError
