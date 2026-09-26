"""A hash-bound LoRA for the contextual decider only (Fase 3.5b D13–D16), off for every other model role.

The server loads it without applying it (global scale 0); ``semantic.decider`` requests turn it on per request on
the decider's reserved slot, so the cached decider prefix is always computed with it and no other role sees it.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .cpu_prose_adapter import read_bound_adapter, verify_neutral_adapter

ENVIRONMENT_VARIABLE = "BAXY_MIND_DECIDER_ADAPTER"
SCHEMA = "baxy-decider-adapter-v1"


@dataclass(frozen=True)
class DeciderAdapter:
    gguf: Path
    sha256: str
    base_sha256: str

    @classmethod
    def from_environment(cls, base_gguf: str | None) -> DeciderAdapter | None:
        bound = read_bound_adapter(ENVIRONMENT_VARIABLE, SCHEMA, base_gguf, "decider_adapter")
        return None if bound is None else cls(*bound)

    def server_arguments(self) -> list[str]:
        return ["--lora", str(self.gguf), "--lora-init-without-apply"]

    def initialize(self, endpoint: str, timeout: float) -> None:
        verify_neutral_adapter(endpoint, self.gguf, timeout, "decider_adapter")

    @staticmethod
    def request_fields() -> dict:
        return {"lora": [{"id": 0, "scale": 1.0}]}
