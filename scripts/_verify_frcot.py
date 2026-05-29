"""STUB verify de la implementacion FR-CoT (CPU puro, sin modelo/GPU).

Lo que SE puede verificar con stub (funciones puras):
  - el flag GEMMA4_FRCOT gatea la inyeccion de la plantilla en el system prompt
  - la guarda estructural borra un bloque INTENT:/TOOL:/ARGS:/GO filtrado al reply
  - NO toca prosa normal (sin falso positivo)

Lo que NO se puede verificar con stub (NECESITA modelo real, validacion en vivo):
  - si el Gemma de verdad razona breve en el formato
  - si el formato se queda en <think> o se filtra (el bug que rompio media)
Eso queda para la validacion en vivo cuando el usuario no este jugando.
"""
import os
import sys
from pathlib import Path

# El flag debe estar seteado ANTES de importar reasoning (lee _FRCOT_ON al cargar).
os.environ["GEMMA4_FRCOT"] = "1"
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

fails = []


def check(name, cond):
    print(f"  [{'OK ' if cond else 'FAIL'}] {name}", flush=True)
    if not cond:
        fails.append(name)


print("=== gating de la plantilla (agent_prompt) ===", flush=True)
from gemma4_agent.agent_core import agent_prompt as ap
check("_frcot_enabled() True con flag on", ap._frcot_enabled() is True)
core_on = ap._core_for_profile()
check("core incluye FRCOT_DIRECTIVE con flag on", "INTENT:" in core_on and "BRIEF REASONING" in core_on)
os.environ.pop("GEMMA4_FRCOT")
check("_frcot_enabled() False sin flag", ap._frcot_enabled() is False)
core_off = ap._core_for_profile()
check("core NO incluye FRCOT_DIRECTIVE sin flag", "BRIEF REASONING" not in core_off)
os.environ["GEMMA4_FRCOT"] = "1"  # restaurar para el strip (modulo ya cargado)

print("=== guarda estructural anti-filtrado (reasoning.sanitize_text) ===", flush=True)
from gemma4_agent.support import reasoning as rz
check("reasoning._FRCOT_ON True (leido al import con flag on)", rz._FRCOT_ON is True)
leaked = 'Claro. INTENT: open_app\nTOOL: app\nARGS: name=spotify\nGO\nListo, abrí Spotify.'
cleaned = rz.sanitize_text(leaked)
check("strip borra el bloque INTENT:", "INTENT:" not in cleaned)
check("strip borra TOOL:/ARGS:", "TOOL:" not in cleaned and "ARGS:" not in cleaned)
check("strip preserva el reply natural", "Listo, abrí Spotify." in cleaned)
normal = "La capital de Francia es París. Es la ciudad más grande."
check("strip NO toca prosa normal", rz.sanitize_text(normal) == normal)
casual = "Mi intención es ayudarte con lo que necesites."
check("strip NO toca 'intención' casual (sin formato)", rz.sanitize_text(casual) == casual)
# bloque sin GO (truncado) tambien se borra
leaked2 = 'INTENT: search\nTOOL: web\nARGS: query=clima'
check("strip borra bloque sin GO (truncado)", "INTENT:" not in rz.sanitize_text(leaked2))

print(f"\n=== RESULT: {'ALL OK' if not fails else 'FAILURES: ' + ','.join(fails)} ===", flush=True)
sys.exit(1 if fails else 0)
