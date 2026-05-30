"""LIVE verificación del fix de la 2da cabeza: tool-call-as-text capitalizado.

INCIDENTE 2026-05-30: el 4B emitió `Web(action="search", query="mejor lego
batman")` como TEXTO (nombre de tool capitalizado). El detector exigía `[a-z]`
inicial → no rescató → el texto crudo llegó literal al usuario.

Este harness corre el agente REAL contra el llama-server vivo (sin SendInput) y:

  (A) Prueba el camino de rescate END-TO-END inyectando el string exacto que
      falló (`Web(action="search"...)`) por `detect_leaked_tool_call` con el
      allowlist REAL del registry → debe sintetizar una call `web` válida.

  (B) Corre fraseos reales que piden búsqueda web EN CONTEXTO GUI heredado
      (reproduce la secuencia: abrir app -> preguntar algo que necesita web),
      y verifica que NINGÚN reply final contenga un tool-call-as-text crudo
      (regex `^\s*[A-Za-z]\w*\(`). El 4B es no-determinista; si en alguna
      corrida emite el call como texto, el rescate debe atraparlo (o ejecutar
      la tool), nunca devolver el texto crudo.

Uso:  python scripts/_verify_leaked_call_fix_live.py
Requiere: llama-server sano en :8080 (perfil vram4).
Seguro: run_content NO usa SendInput.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

# Un reply final que EMPIEZA como `Tool(args)` = leak crudo no rescatado.
_LEAK_SHAPE = re.compile(r"^\s*[A-Za-z][A-Za-z0-9_]{1,40}\s*\(", re.DOTALL)


def part_a_unit_through_registry() -> bool:
    from gemma4_agent.support.reasoning import detect_leaked_tool_call
    from gemma4_agent.tools_pkg.tools import COMPOUND_TOOL_SCHEMAS as CTS
    known = {s["function"]["name"] for s in CTS
             if isinstance(s, dict) and isinstance(s.get("function"), dict)}
    print(f"[A] allowlist real = {len(known)} tools ; 'web' presente = {'web' in known}")
    leaked = 'Web(action="search", query="mejor lego batman")'
    out = detect_leaked_tool_call(leaked, known_tool_names=known)
    ok = bool(out) and out["function"]["name"] == "web"
    print(f"[A] '{leaked}' -> rescatado={'sí' if out else 'no'}"
          + (f" name={out['function']['name']!r} args={out['function']['arguments']}" if out else ""))
    # negativo: capitalizado pero no-tool no debe colarse
    neg = detect_leaked_tool_call('Banana(action="peel")', known_tool_names=known)
    ok = ok and (neg is None)
    print(f"[A] 'Banana(action=\"peel\")' -> rescatado={'sí' if neg else 'no'} (esperado: no)")
    return ok


def part_b_live(ag) -> bool:
    # Reproduce el contexto GUI heredado: abrir una app y LUEGO preguntar algo
    # que el 4B suele rutear a web/search (donde antes capitalizaba `Web`).
    seq = [
        "abrí la calculadora",                # deja contexto GUI [app]
        "buscá cuál es el mejor lego batman", # continuación que necesita web
        "qué tiempo hace en Madrid",          # otra que tira a web
        "buscame el precio del iphone 15",    # otra a web
    ]
    all_clean = True
    for i, txt in enumerate(seq, 1):
        try:
            r = ag.run_content(txt)
            reply = (getattr(r, "content", None) or str(r)) or ""
        except Exception as e:  # noqa: BLE001
            print(f"[B] {i}. {txt!r} -> EXCEPTION {type(e).__name__}: {e}")
            all_clean = False
            continue
        leaked = bool(_LEAK_SHAPE.match(reply.strip()))
        flag = "  <-- LEAK CRUDO!" if leaked else ""
        print(f"[B] {i}. {txt!r}\n       reply: {reply[:140]!r}{flag}")
        if leaked:
            all_clean = False
    return all_clean


def main() -> int:
    print("[A] === camino de rescate por el registry real ===")
    a_ok = part_a_unit_through_registry()

    print("\n[B] === vivo contra el agente + LLM real ===")
    from gemma4_agent.agent_core.agent import Gemma4Agent
    from gemma4_agent.infra.config import AgentConfig
    ag = Gemma4Agent(AgentConfig.from_env())
    b_ok = part_b_live(ag)

    print("\n========== RESULTADO ==========")
    print(f"  [A] rescate capitalizado por registry : {'PASS' if a_ok else 'FAIL'}")
    print(f"  [B] sin leak crudo en replies en vivo : {'PASS' if b_ok else 'FAIL'}")
    ok = a_ok and b_ok
    print("\n  VERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
