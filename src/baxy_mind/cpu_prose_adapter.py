"""A hash-bound adapter for CPU observations, isolated from other model roles."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request

ENVIRONMENT_VARIABLE = "BAXY_MIND_CPU_PROSE_ADAPTER"
SCHEMA = "baxy-cpu-prose-adapter-v1"
PROPERTIES = {"schema", "gguf", "gguf_sha256", "base_gguf_sha256"}


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@dataclass(frozen=True)
class CpuProseAdapter:
    gguf: Path
    sha256: str
    base_sha256: str

    @classmethod
    def from_environment(cls, base_gguf: str | None) -> CpuProseAdapter | None:
        raw = os.environ.get(ENVIRONMENT_VARIABLE)
        if raw is None or not raw.strip():
            return None
        value = json.loads(raw)
        if not isinstance(value, dict) or set(value) != PROPERTIES or value["schema"] != SCHEMA:
            raise ValueError("cpu_prose_adapter_schema_invalid")
        if not all(isinstance(value[key], str) for key in PROPERTIES):
            raise ValueError("cpu_prose_adapter_fields_invalid")
        adapter = Path(value["gguf"])
        if not adapter.is_absolute() or not adapter.is_file() or adapter.suffix.lower() != ".gguf":
            raise ValueError("cpu_prose_adapter_file_invalid")
        if not base_gguf or not Path(base_gguf).is_file():
            raise ValueError("cpu_prose_adapter_base_missing")
        if file_sha256(adapter) != value["gguf_sha256"]:
            raise ValueError("cpu_prose_adapter_hash_mismatch")
        if file_sha256(Path(base_gguf)) != value["base_gguf_sha256"]:
            raise ValueError("cpu_prose_adapter_base_mismatch")
        return cls(adapter.resolve(), value["gguf_sha256"], value["base_gguf_sha256"])

    def server_arguments(self) -> list[str]:
        return ["--lora", str(self.gguf), "--lora-init-without-apply"]

    def initialize(self, endpoint: str, timeout: float) -> None:
        """Verify the loaded asset and neutral default before model readiness."""
        deadline = time.monotonic() + timeout

        def exchange(body: object | None = None) -> object:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("cpu_prose_adapter_initialization_timeout")
            request = urllib.request.Request(
                endpoint + "/lora-adapters",
                data=None if body is None else json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=min(5.0, remaining)) as response:
                return json.load(response)

        def correct_asset(value: object) -> bool:
            return (
                isinstance(value, list) and len(value) == 1
                and isinstance(value[0], dict) and value[0].get("id") == 0
                and isinstance(value[0].get("path"), str)
                and Path(value[0]["path"]).resolve() == self.gguf
            )

        if not correct_asset(exchange()):
            raise ValueError("cpu_prose_adapter_server_mismatch")
        exchange([{"id": 0, "scale": 0.0}])
        verified = exchange()
        if not correct_asset(verified) or verified[0].get("scale") != 0.0:
            raise ValueError("cpu_prose_adapter_default_not_zero")

    @staticmethod
    def sampling() -> dict:
        # CPU-only qualification586/588/589; never a global model profile.
        return {
            "temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0,
            "presence_penalty": 0.0, "repeat_penalty": 1.0, "seed": 0,
            "lora": [{"id": 0, "scale": 1.0}],
        }


def applies_to_cpu_prose(situation: dict, observed: dict) -> bool:
    return (
        isinstance(observed.get("cpu"), dict) and bool(observed["cpu"])
        and set(observed).issubset({"scope", "cpu", "failures"})
        and not observed.get("failures")
        and situation.get("kind") in {"operation", "status"}
        and situation.get("polarity") != "failure"
        and situation.get("cause") != "acting"
        and situation.get("kind") != "confirmation"
    )
