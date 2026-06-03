"""Standalone Gemma 4 local agent package.

Reorg 2026-05-28: los modulos productivos viven en sub-paquetes
(agent_core, computer_use_pkg, routing, infra, safety_pkg, memory_pkg,
tools_pkg, mission, support). Para mantener back-compat con codigo y tests
que hacen `from gemma4_agent.X import Y` o `mock.patch("gemma4_agent.X.Y")`,
re-aliasamos sys.modules en el import del paquete. Esto reemplaza los
~86 shim .py de raiz por una sola tabla en este __init__.

Nota: los tests dinamicos con `__import__('gemma4_agent.X', ...)` y los
patches con `unittest.mock.patch('gemma4_agent.X.Y')` siguen funcionando
porque ambos resuelven via sys.modules — y ahora sys.modules['gemma4_agent.X']
apunta al modulo REAL en el subpkg.
"""
from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"


# --- Back-compat sys.modules aliasing (reorg 2026-05-28) ---
def _alias_subpkg_modules() -> None:
    """Crear aliases sys.modules['gemma4_agent.X'] -> 'gemma4_agent.<subpkg>.X'
    para cada stem movido. Best-effort: si algun subpkg falla, los demas siguen.
    """
    import importlib
    import sys as _sys

    # Mapa stem -> subpkg. Hardcoded para evitar IO de descubrir en cada
    # import del paquete (esto corre 1 vez al cargar gemma4_agent).
    aliases = {
        # agent_core
        "agent": "agent_core",
        "agent_compaction": "agent_core",
        "agent_dispatch": "agent_core",
        "agent_guards": "agent_core",
        "agent_prompt": "agent_core",
        "agent_runner": "agent_core",
        "turn_types": "agent_core",
        # computer_use_pkg
        "computer_use": "computer_use_pkg",
        "computer_use_b": "computer_use_pkg",
        "gui_safety": "computer_use_pkg",
        "gui_verify": "computer_use_pkg",
        "gui_vision_gate": "computer_use_pkg",
        "win_focus": "computer_use_pkg",
        # NOTA: accessibility tiene 2 ubicaciones (computer_use_pkg y
        # domain_tools). El alias top-level apunta a computer_use_pkg —
        # callers que querian domain_tools deben usar la ruta completa.
        "accessibility": "computer_use_pkg",
        "accessibility_voice": "computer_use_pkg",
        # routing
        # NOTA: router tiene 2 ubicaciones (routing y computer_use_caps).
        # Alias top-level apunta a routing.
        "router": "routing",
        "semantic_router": "routing",
        "intent_router": "routing",
        "context_router": "routing",
        "exemplar_router": "routing",
        "reranker": "routing",
        "planner": "routing",
        "command_splitter": "routing",
        # infra
        # NOTA reorg 2026-05-28: NO incluir runnables aqui (launcher, server,
        # voice_runner, watcher_runner, task_runner, routine_runner). Tienen
        # `if __name__ == "__main__"` y se invocan con `python -m`. Si los
        # aliasamos, runpy emite RuntimeWarning porque el modulo ya esta en
        # sys.modules antes de ejecutarse. Los entry points migraron a path
        # nuevo: `python -m gemma4_agent.infra.<nombre>`.
        "config": "infra",
        "tracing": "infra",
        "telemetry": "infra",
        "llama_server": "infra",
        "llm_client": "infra",
        "log_recorder": "infra",
        "model_info": "infra",
        "profiles": "infra",
        "profile_watcher": "infra",
        "prewarm": "infra",
        "events_bus": "infra",
        "boot_progress": "infra",
        # safety_pkg
        "safety": "safety_pkg",
        "safety_hook": "safety_pkg",
        "ssrf_guard": "safety_pkg",
        "verify_core": "safety_pkg",
        "verify_policy": "safety_pkg",
        "verifiers": "safety_pkg",
        "reply_validator": "safety_pkg",
        "grounding_gate": "safety_pkg",
        "loop_detection": "safety_pkg",
        "intent_validator": "safety_pkg",
        "abstain_head": "safety_pkg",
        # memory_pkg (microagents excluido: tiene __main__ runnable)
        "memory": "memory_pkg",
        "memory_retrieval": "memory_pkg",
        "experience": "memory_pkg",
        "pattern_miner": "memory_pkg",
        "behavior_log": "memory_pkg",
        "knowledge": "memory_pkg",
        "project_context": "memory_pkg",
        "suggestion_queue": "memory_pkg",
        "sessions": "memory_pkg",
        "state": "memory_pkg",
        # tools_pkg (mcp_server, skills_registry excluidos: __main__ runnable)
        "tools": "tools_pkg",
        "tool_schemas": "tools_pkg",
        "tool_result": "tools_pkg",
        "tool_head": "tools_pkg",
        "ops_tools": "tools_pkg",
        "app_resolver": "tools_pkg",
        "multimodal": "tools_pkg",
        "subagent": "tools_pkg",
        # mission
        "mission_checkpoint": "mission",
        "mission_goal": "mission",
        "mission_outcome": "mission",
        "explicit_plan": "mission",
        # support (chat, eval_smoke, import_triggercmd excluidos: __main__ runnable)
        "datetime_parse": "support",
        "modes": "support",
        "personas": "support",
        "reasoning": "support",
        "evaluator": "support",
        "vram_watchdog": "support",
    }

    # Importar el paquete a si mismo para poder setattr
    pkg = _sys.modules.get("gemma4_agent")

    for stem, subpkg in aliases.items():
        full = f"gemma4_agent.{subpkg}.{stem}"
        shim_name = f"gemma4_agent.{stem}"
        try:
            mod = importlib.import_module(full)
        except ImportError:
            # Si algun submodulo no importa, no romper el package import.
            continue
        if shim_name not in _sys.modules:
            _sys.modules[shim_name] = mod
        # mock.patch("gemma4_agent.X.Y") usa getattr en el paquete, no
        # sys.modules directo — exponer el alias como atributo tambien.
        if pkg is not None and not hasattr(pkg, stem):
            setattr(pkg, stem, mod)


_alias_subpkg_modules()


def _alias_domain_tools_shims() -> None:
    """Sprint R2 (2026-05-28) creo shims `gemma4_agent.domain_tools_X` que
    aliased a `gemma4_agent.domain_tools.X`. Los movemos del filesystem al
    init para limpiar la raiz, manteniendo la API publica.
    """
    import importlib
    import sys as _sys

    domain_areas = (
        "accessibility", "backup_sync", "bluetooth", "calendar", "contacts",
        "container", "creative_local", "data_analysis", "database",
        "dependency", "desktop_layout", "developer", "device_settings",
        "document", "fact_check", "file_process", "form_filler", "game_launcher",
        "habit_tracker", "helpers", "job_manager", "local_search",
        "maintenance", "media_edit", "network", "notes", "notifications",
        "office", "peripheral", "photo_library", "printer_scanner",
        "routine", "source_manager", "study", "watcher", "whatsapp",
        "wifi",
    )
    pkg = _sys.modules.get("gemma4_agent")

    for area in domain_areas:
        full = f"gemma4_agent.domain_tools.{area}"
        shim_name = f"gemma4_agent.domain_tools_{area}"
        try:
            mod = importlib.import_module(full)
        except ImportError:
            continue
        if shim_name not in _sys.modules:
            _sys.modules[shim_name] = mod
        attr_name = f"domain_tools_{area}"
        if pkg is not None and not hasattr(pkg, attr_name):
            setattr(pkg, attr_name, mod)


_alias_domain_tools_shims()
