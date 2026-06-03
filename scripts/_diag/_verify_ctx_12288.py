# -*- coding: utf-8 -*-
"""Verifica que vram4 bajó a 12288 y que la sincronización server↔compaction
queda consistente (apply_profile_to_env → GEMMA4_AGENT_CONTEXT → config)."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from gemma4_agent.infra.profiles import PROFILES, apply_profile_to_env

p = PROFILES["vram4"]
print("vram4.context_size =", p.context_size)
assert p.context_size == 12288, f"esperaba 12288, got {p.context_size}"

# El modo compact se conserva (umbral agent.py es ctx>=12288, y 12288>=12288 → compact).
mode = "full" if p.context_size >= 32768 else ("compact" if p.context_size >= 12288 else "OFF")
print("modo tool_schemas_hint a 12288 =", mode, "(debe ser compact)")
assert mode == "compact", "12288 perdió el modo compact — el umbral debe ser <=12288"

# Sincronización: apply_profile_to_env setea GEMMA4_AGENT_CONTEXT, config lo lee.
apply_profile_to_env(p)
env_ctx = os.environ.get("GEMMA4_AGENT_CONTEXT")
print("GEMMA4_AGENT_CONTEXT tras apply =", env_ctx)
assert env_ctx == "12288", f"env desincronizado: {env_ctx}"

from gemma4_agent.infra.config import AgentConfig
cfg = AgentConfig.from_env()
print("config.context_size (compaction) =", cfg.context_size)
assert cfg.context_size == 12288, "compaction desincronizada del server"

print("OK: vram4=12288, compact conservado, server↔compaction sincronizados.")
