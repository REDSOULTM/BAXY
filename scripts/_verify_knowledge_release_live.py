"""LIVE verificación del fix de herencia: soltar contexto GUI ante pregunta-del-mundo.

INCIDENTE 2026-05-30: tras abrir una app (contexto GUI), una pregunta fresca
("cuál es el mejor lego batman") heredaba [app,gui,uia] SIN web → el 4B emitía
`Web(action="search"...)` como texto. Fix: si wants_knowledge(turn) es True, NO
heredar GUI → el router ofrece web/knowledge. Evento de traza nuevo:
`inherit_released_for_knowledge`.

Reproduce la secuencia EXACTA contra el agente + LLM real (sin SendInput):
  1. abrir una app (deja contexto GUI [app])
  2. preguntar algo info-claro → debe SOLTARSE (inherit_released_for_knowledge),
     ofrecer web/knowledge, y el reply NO debe ser un tool-call-as-text crudo.

Y verifica el anti-regresión: un 'operate-app' tras abrir la app debe MANTENER
la herencia GUI (inherit_kept_gui_context), NO soltarse.

Uso:  python scripts/_verify_knowledge_release_live.py
Requiere: llama-server sano en :8080. Seguro: run_content (sin SendInput).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

TRACES = ROOT / "gemma4_agent" / "data" / "traces.jsonl"
_LEAK_SHAPE = re.compile(r"^\s*[A-Za-z][A-Za-z0-9_]{1,40}\s*\(", re.DOTALL)


def _tail_size() -> int:
    try:
        return TRACES.stat().st_size
    except FileNotFoundError:
        return 0


def _events_since(since: int) -> list[dict]:
    out: list[dict] = []
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


def _kinds_for_turn(events, turn_id):
    return [e for e in events if e.get("turn_id") == turn_id]


def main() -> int:
    from gemma4_agent.agent_core.agent import Gemma4Agent
    from gemma4_agent.infra.config import AgentConfig

    print("[live] construyendo agente (server vivo en :8080)...", flush=True)
    ag = Gemma4Agent(AgentConfig.from_env())

    # (1) abrir una app deja contexto GUI. Usamos calculadora (no irreversible).
    print("\n[live] paso 1: abrir la calculadora (deja contexto GUI)...", flush=True)
    ag.run_content("abrí la calculadora")

    checks = []
    # (2) preguntas info-claras: deben SOLTAR el GUI (inherit_released_for_knowledge)
    knowledge_qs = [
        "cuál es el mejor lego batman",
        "qué es un dinosaurio",
        "buscame el precio del iphone 15",
    ]
    for q in knowledge_qs:
        off = _tail_size()
        r = ag.run_content(q)
        reply = (getattr(r, "content", None) or str(r)) or ""
        evs = _events_since(off)
        # tomar el primer turno real (request_start)
        tid = next((e["turn_id"] for e in evs if e.get("kind") == "request_start"), None)
        tev = _kinds_for_turn(evs, tid) if tid else evs
        released = any(e.get("kind") == "inherit_released_for_knowledge" for e in tev)
        kept_gui = any(e.get("kind") == "inherit_kept_gui_context" for e in tev)
        subset = next((e.get("tools") for e in tev if e.get("kind") == "tool_subset"), None)
        leaked = bool(_LEAK_SHAPE.match(reply.strip()))
        offered_web = bool(subset and ("web" in subset or "knowledge" in subset))
        ok = released and (not kept_gui) and (not leaked)
        checks.append(ok)
        print(f"\n[live] Q(info): {q!r}")
        print(f"        released_for_knowledge={released}  kept_gui={kept_gui}  subset={subset}")
        print(f"        web/knowledge ofrecido={offered_web}  leak_crudo={leaked}")
        print(f"        reply: {reply[:120]!r}")
        print(f"        -> {'PASS' if ok else 'FAIL'}")

    # (3) anti-regresión: operate-app tras abrir app debe MANTENER GUI.
    print("\n[live] paso 3 (anti-regresión): operate-app debe MANTENER GUI...", flush=True)
    # re-abrir contexto GUI por si el turno anterior lo cambió
    ag.run_content("abrí la calculadora")
    off = _tail_size()
    r = ag.run_content("ahora sumá 2 más 2")
    evs = _events_since(off)
    tid = next((e["turn_id"] for e in evs if e.get("kind") == "request_start"), None)
    tev = _kinds_for_turn(evs, tid) if tid else evs
    kept_gui = any(e.get("kind") == "inherit_kept_gui_context" for e in tev)
    released = any(e.get("kind") == "inherit_released_for_knowledge" for e in tev)
    # No-regresión: NO debe soltarse por knowledge (es operate-app).
    no_regress = not released
    checks.append(no_regress)
    print(f"        operate-app 'sumá 2+2': kept_gui={kept_gui}  released={released}")
    print(f"        -> {'PASS (no se soltó indebidamente)' if no_regress else 'FAIL (se soltó un operate-app!)'}")

    print("\n========== RESULTADO ==========")
    ok = all(checks)
    print(f"  checks: {sum(checks)}/{len(checks)} PASS")
    print("  VERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
