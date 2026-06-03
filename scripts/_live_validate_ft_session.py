# -*- coding: utf-8 -*-
"""Validación EN VIVO (regla #3.5) del estado de la sesión 2026-06-02.

Corre contra el agente + LLM REALES (modelo FT desplegado, perfil vram4),
inyectando mensajes por agent.run_content (= la UI, seguro: NO usa SendInput
físico). Verifica la cadena completa de tools + el reply para:

  1. ROUTER corregido: preguntas-conocimiento NO disparan acción espuria
     (el bug whatsapp en 'que es pytest' que arreglé esta sesión).
  2. smart_home ELIMINADO: pedir control de casa inteligente NO crashea ni
     ofrece la tool muerta — el LLM responde honestamente.
  3. Comandos reales SIGUEN funcionando (no rompí routing al limpiar).
  4. 3 perfiles a11y (modos movilidad/no_vidente) responden coherente.

NO ejecuta nada físico irreversible. run_content/CDP/vision son seguros
(memoria feedback_never_run_synthetic_input_lives_in_vscode).
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

# Confirmar server vivo antes de nada.
import urllib.request
try:
    urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=5)
except Exception as e:
    print(f"[ABORT] server no responde en :8080 ({type(e).__name__}). Arrancalo con _boot_server_for_eval.py")
    sys.exit(2)

from gemma4_agent.agent_core.agent import Gemma4Agent  # noqa: E402

agent = Gemma4Agent()


def run(msg: str) -> dict:
    """Inyecta un mensaje por el path de la UI y devuelve el resultado crudo."""
    t0 = time.time()
    try:
        res = agent.run_content(msg)
    except Exception as e:
        return {"msg": msg, "error": f"{type(e).__name__}: {e}", "dt": time.time() - t0}
    reply = ""
    tools = []
    if isinstance(res, dict):
        reply = res.get("reply") or res.get("text") or ""
        tools = res.get("tools_used") or res.get("tool_calls") or []
    else:
        reply = str(res)
    return {"msg": msg, "reply": reply, "tools": tools, "dt": time.time() - t0}


# --- Casos de validación ---
CASES = [
    # (categoria, mensaje, criterio_humano)
    ("router/pregunta", "que es pytest", "responde definición; NO abre app ni whatsapp"),
    ("router/pregunta", "qué significa API", "responde definición; NO acción espuria"),
    ("router/comando", "mutea", "ejecuta audio mute"),
    ("router/comando", "subí el volumen al 30%", "audio set_volume 30"),
    ("smart_home/muerta", "prendé las luces de la sala", "NO crashea; responde honesto (no tengo esa capacidad)"),
    ("smart_home/muerta", "bajá la temperatura del termostato", "NO crashea; honesto"),
    ("a11y/movilidad", "abrí la calculadora", "ejecuta sin pedir acción manual"),
    ("a11y/general", "qué hay en mi pantalla", "describe (vision) o pide screenshot, no inventa"),
]

print("=" * 70)
print("VALIDACIÓN EN VIVO — modelo FT, perfil vram4 (regla #3.5)")
print("=" * 70)
results = []
for cat, msg, crit in CASES:
    r = run(msg)
    results.append((cat, msg, crit, r))
    err = r.get("error")
    if err:
        print(f"\n[{cat}] {msg!r}\n  ❌ ERROR: {err}")
        continue
    reply = (r["reply"] or "").replace("\n", " ").strip()
    print(f"\n[{cat}] {msg!r}  ({r['dt']:.1f}s)")
    print(f"  tools: {r['tools']}")
    print(f"  reply: {reply[:160]}")
    print(f"  esperado: {crit}")

print("\n" + "=" * 70)
errs = [r for *_, r in results if r.get("error")]
print(f"RESUMEN: {len(results)} casos corridos, {len(errs)} con excepción.")
if errs:
    print("CASOS CON EXCEPCIÓN (revisar):")
    for *_, r in results:
        if r.get("error"):
            print(f"  - {r['msg']!r}: {r['error']}")
print("Revisar manualmente reply/tools arriba: las preguntas NO deben tener")
print("tools de acción; smart_home NO debe crashear; comandos SÍ ejecutan.")
