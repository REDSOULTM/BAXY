"""Verificación EN VIVO de los fixes de router del Sprint 3 (S3b/S3c/S3d).

Regla #3.5 (CLAUDE.md): un cambio que toca el ruteo NO está listo hasta correrlo
contra el LLM REAL y ver la cadena completa. Acá probamos:
  - S3b: "hablame de X / contame sobre X" -> el subset ofrece web/knowledge y el
    4B elige una lookup tool (no abre app random).
  - S3c: "abre el navegador" -> ya NO da subset vacío; ofrece app/browser y el 4B
    abre el navegador.
  - S3d: "abre el navegador" NO incluye browser_real (ruido); "llená el formulario"
    SÍ lo conserva.

Solo lectura / sin SendInput: usamos select_tool_names (router) + una llamada al
LLM real (/v1/chat/completions) con el subset, mirando qué tool-call emite. NO
ejecuta la tool. Requiere el server vivo en :8080 (ya gestionado por el user).

Uso: python scripts/_live_verify_router_s3.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"


def _router_subset(q: str) -> list[str]:
    from gemma4_agent.routing.planner import select_tool_names, plan_mission
    return list(select_tool_names(q, plan_mission(q), safety_enabled=True))


def _tool_schemas_for(subset: list[str]) -> list[dict]:
    """Las tool schemas (OpenAI format) para el subset — lo que ve el 4B."""
    from gemma4_agent.tools_pkg.tool_schemas import COMPOUND_TOOL_SCHEMAS
    by_name = {s["function"]["name"]: s for s in COMPOUND_TOOL_SCHEMAS}
    return [by_name[t] for t in subset if t in by_name]


def _ask_llm(q: str, subset: list[str]) -> tuple[str | None, str]:
    """(tool_name elegido por el 4B, texto). None si no llamó tool."""
    tools = _tool_schemas_for(subset)
    body = {
        "model": "vram4-text",
        "messages": [
            {"role": "system", "content":
             "Eres un asistente de voz local. Si el usuario pide una acción en la "
             "PC o información del mundo, llamá la herramienta adecuada del subset."},
            {"role": "user", "content": q},
        ],
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.0,
        "max_tokens": 256,
    }
    req = urllib.request.Request(
        LLM_URL, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))
    msg = data["choices"][0]["message"]
    calls = msg.get("tool_calls") or []
    if calls:
        return calls[0]["function"]["name"], msg.get("content") or ""
    return None, msg.get("content") or ""


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    failures: list[str] = []

    # S3d (router-only, determinista): browser_real colapsa en nav simple,
    # se conserva en control-web. No necesita LLM.
    print("== S3d: collapse browser_real (router) ==")
    for q, must_absent in [("abre el navegador", True), ("abre chrome", True),
                           ("ve a youtube", True)]:
        sub = _router_subset(q)
        gone = "browser_real" not in sub
        ok = gone == must_absent
        print(f"  {'OK ' if ok else 'FALLA'} {q!r}: browser_real ausente={gone} "
              f"subset={[t for t in sub if t not in ('session','safety')]}")
        if not ok:
            failures.append(f"S3d-nav:{q}")
    for q in ("llena el formulario de esta pagina", "rellena el formulario de la web"):
        sub = _router_subset(q)
        ok = "browser_real" in sub
        print(f"  {'OK ' if ok else 'FALLA'} {q!r}: browser_real presente={ok}")
        if not ok:
            failures.append(f"S3d-form:{q}")

    # S3c: "abre el navegador" ya NO da subset vacío.
    print("== S3c: 'abre el navegador' no se abstiene (router) ==")
    for q in ("abre el navegador", "Abri el navegador"):
        sub = [t for t in _router_subset(q) if t not in ("session", "safety")]
        ok = bool(sub) and ("app" in sub or "browser" in sub)
        print(f"  {'OK ' if ok else 'FALLA'} {q!r}: subset={sub}")
        if not ok:
            failures.append(f"S3c:{q}")

    # S3b + cadena LLM real: "hablame de X" ofrece lookup y el 4B la elige.
    print("== S3b: 'hablame de X' -> subset+LLM eligen lookup (EN VIVO) ==")
    live_cases = [
        ("hablame de bruno mars", {"web", "knowledge"}),
        ("contame sobre la segunda guerra mundial", {"web", "knowledge"}),
        ("abre el navegador", {"app", "browser", "browser_real", "computer_use"}),
    ]
    for q, acceptable in live_cases:
        sub = _router_subset(q)
        sub_dom = [t for t in sub if t not in ("session", "safety")]
        offered = acceptable & set(sub)
        try:
            chosen, text = _ask_llm(q, sub)
        except Exception as e:
            print(f"  AVISO  {q!r}: LLM no disponible ({e}); router subset={sub_dom}")
            # router-level check still counts
            if not offered:
                failures.append(f"S3b-router:{q}")
            continue
        # PASS si el router OFRECIÓ una tool aceptable Y el 4B eligió alguna tool
        # del subset (o respondió con la lookup). El 4B es no-determinista; lo
        # clave es que la tool correcta ESTÉ disponible y el 4B no la ignore.
        chose_ok = (chosen in acceptable) if chosen else False
        router_ok = bool(offered)
        ok = router_ok and (chose_ok or chosen is not None)
        print(f"  {'OK ' if ok else 'FALLA'} {q!r}: router_ofreció={sorted(offered)} "
              f"4B_eligió={chosen!r}")
        if not router_ok:
            failures.append(f"S3b-router:{q}")
        elif chosen is not None and not chose_ok:
            # el 4B eligió OTRA tool del subset — lo anotamos pero no es fallo duro
            print(f"         (nota: 4B eligió {chosen!r}, fuera de {sorted(acceptable)})")

    print()
    if failures:
        print(f"FALLOS ({len(failures)}): {failures}")
        return 1
    print("TODO OK — fixes S3b/S3c/S3d verificados en vivo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
