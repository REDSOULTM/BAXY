"""Runtime configuration for the standalone Carter agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


PACKAGE_ROOT = Path(__file__).resolve().parent.parent  # reorg 2026-05-28: infra/ es subdir
PROJECT_ROOT = PACKAGE_ROOT.parent


@dataclass(frozen=True)
class AgentConfig:
    server_url: str = "http://127.0.0.1:8080"
    model: str = "gemma-4"
    llama_server_exe: Path = Path("C:/llamacpp-cuda/bin/llama-server.exe")
    # Default = E2B-Q4_K_M (perfil vram4, el ÚNICO activo desde 2026-05-26; ~3.36GB +visión @4K).
    # 2026-06-02: actualizado de E4B→E2B porque models/E4B (GGUF) se borró (no lo usaba prod;
    # el perfil vram4 ya sobreescribía con E2B vía profiles.py:196). El usuario puede sobreescribir
    # con GEMMA4_MODEL_PATH. Nota: el FT entrena E4B en formato HF aparte (otra ruta, no este GGUF).
    model_path: Path = PROJECT_ROOT / "models" / "E2B" / "gemma-4-E2B-it-Q4_K_M.gguf"
    mmproj_path: Path = PROJECT_ROOT / "models" / "E2B" / "mmproj-F16.gguf"
    temperature: float = 1.0
    top_p: float = 0.95
    top_k: int = 64
    min_p: Optional[float] = None
    repeat_penalty: float = 1.0
    seed: int = -1  # -1 = random per request
    max_tokens: int = 1280
    context_size: int = 16384
    request_timeout_s: float = 180.0
    max_agent_turns: int = 8
    parse_tool_calls: bool = True
    parallel_tool_calls: bool = False
    enable_thinking: bool = False
    reasoning_format: str = ""
    agent_mode: str = "auto"
    enable_tracing: bool = True
    # Safety gate de confirmación de lo IRREVERSIBLE: default ON (cumple el principio
    # #6 del producto y el README — "las operaciones destructivas piden confirmación
    # antes de proceder"). Estaba OFF por un default heredado SIN justificación
    # (commit 3f2664c) que contradecía el README y dejaba ejecutar "borra todo en C:/"
    # sin confirmar (cacería t1-4, juez LLM). Los EVALS lo desactivan explícito con
    # GEMMA4_AGENT_SAFETY=0 para medir routing sin fricción. Apagable por env.
    enable_safety: bool = True
    memory_path: Path = PACKAGE_ROOT / "data" / "memory.json"
    captures_dir: Path = PACKAGE_ROOT / "captures"
    trace_path: Path = PACKAGE_ROOT / "data" / "traces.jsonl"
    state_path: Path = PACKAGE_ROOT / "data" / "state.json"

    @property
    def chat_url(self) -> str:
        return f"{self.server_url.rstrip('/')}/v1/chat/completions"

    @property
    def health_url(self) -> str:
        return f"{self.server_url.rstrip('/')}/health"

    @classmethod
    def from_env(cls) -> "AgentConfig":
        # Fase V: si existe ~/.gemma4/active_profile.txt y los env vars
        # individuales no han sido seteados todavia en esta sesion, aplicar
        # el perfil persistido a os.environ antes de leerlo. Esto cubre el
        # caso "primer arranque tras reboot, GUI no clickeo nada todavia".
        # NO sobreescribe env vars ya presentes (respeta seteos manuales).
        try:
            _apply_persisted_profile_if_unset()
        except Exception:
            # Falla silenciosa: si profiles.py rompe algo, AgentConfig debe
            # seguir construyendose con los defaults/env existentes.
            pass

        memory_raw = os.environ.get("GEMMA4_AGENT_MEMORY")
        captures_raw = os.environ.get("GEMMA4_AGENT_CAPTURES")
        llama_raw = os.environ.get("GEMMA4_LLAMA_SERVER_EXE")
        model_raw = os.environ.get("GEMMA4_MODEL_PATH")
        mmproj_raw = os.environ.get("GEMMA4_MMPROJ_PATH")
        min_p_raw = os.environ.get("GEMMA4_AGENT_MIN_P")
        trace_raw = os.environ.get("GEMMA4_AGENT_TRACE_PATH") or os.environ.get("GEMMA4_AGENT_TRACE")
        state_raw = os.environ.get("GEMMA4_AGENT_STATE")
        return cls(
            server_url=os.environ.get("GEMMA4_AGENT_SERVER", cls.server_url),
            model=os.environ.get("GEMMA4_AGENT_MODEL", cls.model),
            llama_server_exe=Path(llama_raw) if llama_raw else cls.llama_server_exe,
            model_path=Path(model_raw) if model_raw else cls.model_path,
            mmproj_path=Path(mmproj_raw) if mmproj_raw else cls.mmproj_path,
            temperature=float(os.environ.get("GEMMA4_AGENT_TEMPERATURE", cls.temperature)),
            top_p=float(os.environ.get("GEMMA4_AGENT_TOP_P", cls.top_p)),
            top_k=int(os.environ.get("GEMMA4_AGENT_TOP_K", cls.top_k)),
            min_p=(float(min_p_raw) if min_p_raw else cls.min_p),
            repeat_penalty=float(os.environ.get("GEMMA4_AGENT_REPEAT_PENALTY", cls.repeat_penalty)),
            seed=int(os.environ.get("GEMMA4_AGENT_SEED", cls.seed)),
            max_tokens=int(os.environ.get("GEMMA4_AGENT_MAX_TOKENS", cls.max_tokens)),
            context_size=int(os.environ.get("GEMMA4_AGENT_CONTEXT", cls.context_size)),
            request_timeout_s=float(os.environ.get("GEMMA4_AGENT_TIMEOUT", cls.request_timeout_s)),
            max_agent_turns=int(os.environ.get("GEMMA4_AGENT_MAX_TURNS", cls.max_agent_turns)),
            parse_tool_calls=_env_bool("GEMMA4_AGENT_PARSE_TOOL_CALLS", cls.parse_tool_calls),
            parallel_tool_calls=_env_bool("GEMMA4_AGENT_PARALLEL_TOOL_CALLS", cls.parallel_tool_calls),
            enable_thinking=_env_bool("GEMMA4_AGENT_ENABLE_THINKING", cls.enable_thinking),
            reasoning_format=os.environ.get("GEMMA4_AGENT_REASONING_FORMAT", cls.reasoning_format),
            agent_mode=os.environ.get("GEMMA4_AGENT_MODE", cls.agent_mode),
            enable_tracing=_env_bool("GEMMA4_AGENT_TRACING", cls.enable_tracing),
            enable_safety=_env_bool("GEMMA4_AGENT_SAFETY", cls.enable_safety),
            memory_path=Path(memory_raw) if memory_raw else cls.memory_path,
            captures_dir=Path(captures_raw) if captures_raw else cls.captures_dir,
            trace_path=Path(trace_raw) if trace_raw else cls.trace_path,
            state_path=Path(state_raw) if state_raw else cls.state_path,
        )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on", "si"}


# Fase V: env vars escritos por apply_profile_to_env. Si NINGUNO esta seteado
# en os.environ pero hay un active_profile.txt persistido, aplicamos el perfil.
_PROFILE_OWNED_ENV = (
    "GEMMA4_AGENT_CONTEXT",
    "GEMMA4_KNOWLEDGE_RERANK",
    "GEMMA4_AGENT_PARALLEL_TOOLS",
    "GEMMA4_AGENT_FACT_EXTRACTION",
    "GEMMA4_ACTIVE_PROFILE",
)


def _apply_persisted_profile_if_unset() -> None:
    """Aplica el perfil persistido si los env vars del perfil no estan seteados.

    No sobreescribe nada que ya este en os.environ; respeta seteos manuales
    del usuario via shell o de Settings.apply_to_env.
    """
    # Si CUALQUIERA de los env vars del perfil ya esta seteado, asumimos que
    # alguien (Settings, profile_watcher, shell) ya tomo el control.
    for key in _PROFILE_OWNED_ENV:
        if key in os.environ:
            return
    # Lazy import para evitar ciclo (profiles importa state, state no importa
    # config, pero por las dudas hacemos late binding).
    from .profiles import apply_profile_to_env, get_active_profile

    profile = get_active_profile()
    apply_profile_to_env(profile)
