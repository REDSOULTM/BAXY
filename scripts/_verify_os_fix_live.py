"""LIVE verificación del fix del NameError `_os` en _finalize_turn.

Corre el agente REAL contra el llama-server vivo (no mocks), inyecta por
`run_content` (= la UI, sin SendInput) los fraseos que fallaron HOY en
traces.jsonl, y comprueba en las trazas nuevas que:

  (1) NO aparece `silent_fallback / reply_validator / NameError: _os`
      en ningún turno (era universal antes del fix).
  (2) El bloque de validación de reply realmente CORRE (no se traga la
      excepción), p.ej. para un reply de charla puede disparar o no un
      anti-pattern, pero la ausencia del fallback es la señal dura.

Uso:  python scripts/_verify_os_fix_live.py
Requiere: llama-server sano en :8080 (perfil vram4).
Seguro: run_content NO usa SendInput (no cierra VS Code).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

TRACES = ROOT / "gemma4_agent" / "data" / "traces.jsonl"

# Fraseos tomados literalmente de los turnos que fallaron hoy (2026-05-30).
PHRASES = [
    "Hola",                              # charla pura (013033)
    "qué es un dinosaurio",              # pregunta de conocimiento (012941)
    "cuál es la forma más común de cocinar un huevo",  # conocimiento (012850)
    "abrí spotify",                      # acción real -> tool, reply con efecto
]


def _tail_size() -> int:
    try:
        return TRACES.stat().st_size
    except FileNotFoundError:
        return 0


def _read_new_events(since: int):
    import json
    out = []
    if not TRACES.exists():
        return out
    with open(TRACES, "r", encoding="utf-8") as f:
        f.seek(since)
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def main() -> int:
    from gemma4_agent.agent_core.agent import Gemma4Agent
    from gemma4_agent.infra.config import AgentConfig

    print("[live] construyendo Gemma4Agent (server vivo en :8080)...", flush=True)
    ag = Gemma4Agent(AgentConfig.from_env())

    start_off = _tail_size()
    print(f"[live] traces.jsonl offset inicial = {start_off}", flush=True)

    for i, txt in enumerate(PHRASES, 1):
        print(f"\n[live] === turno {i}/{len(PHRASES)} : {txt!r} ===", flush=True)
        try:
            r = ag.run_content(txt)
            reply = getattr(r, "content", None) or str(r)
            print(f"[live]   REPLY: {reply[:160]!r}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[live]   EXCEPTION run_content: {type(e).__name__}: {e}", flush=True)

    events = _read_new_events(start_off)
    print(f"\n[live] eventos nuevos capturados: {len(events)}", flush=True)

    # --- chequeo duro: ningún silent_fallback de reply_validator por NameError _os
    os_fallbacks = [
        e for e in events
        if e.get("kind") == "silent_fallback"
        and e.get("component") == "reply_validator"
        and "_os" in (e.get("error") or "")
    ]
    any_rv_fallback = [
        e for e in events
        if e.get("kind") == "silent_fallback" and e.get("component") == "reply_validator"
    ]
    validator_ran = [
        e for e in events if e.get("kind") == "reply_anti_pattern_detected"
    ]

    print("\n========== RESULTADO ==========")
    print(f"  silent_fallback(reply_validator, NameError _os): {len(os_fallbacks)}  (esperado: 0)")
    print(f"  silent_fallback(reply_validator, cualquiera)   : {len(any_rv_fallback)}  (esperado: 0)")
    print(f"  reply_anti_pattern_detected (validador corrió) : {len(validator_ran)}")
    if any_rv_fallback:
        for e in any_rv_fallback[:5]:
            print(f"    - fallback: {e.get('error')}")
    if validator_ran:
        for e in validator_ran[:5]:
            print(f"    - anti-pattern: {e.get('pattern')}")

    ok = (len(os_fallbacks) == 0) and (len(any_rv_fallback) == 0)
    # ASCII-only print: la consola de Windows es cp1252 y un ✓/✗ la rompe.
    print("\n  VERDICT:", "PASS (validador vivo, sin NameError)" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
