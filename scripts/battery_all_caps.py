"""BATERÍA INTEGRAL — 2+ variantes de CADA capacidad de la app, contra el agente
REAL (modelo en :8080), AGENTE FRESCO por caso (sin context-pollution), con TODO
lo físico STUBEADO (0 SendInput — Claude vive en VS Code, el input sintético lo
cierra: ver memory feedback_never_run_synthetic_input_lives_in_vscode).

Qué verifica por caso: la TOOL que el 4B eligió/ejecutó + el reply. NO ejerce
ninguna acción real del SO. Reporta por categoría y lista los que no rutean.

Pensado para correr desde Claude de forma segura (CLAUDE.md #3.5: probar en vivo
con el LLM/agente real, no delegar al user). El user hace la verificación FÍSICA.

Run: python scripts/battery_all_caps.py [--only cat1,cat2] [--runs 1]
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_AGENT_CONTEXT", "16384")
# modo normal por defecto (no mezclar guardas a11y salvo la categoría a11y)
os.environ.setdefault("GEMMA4_ACCESSIBILITY_MODE", "normal")

# (categoría, comando, expects_tool)  — expects_tool=False => pregunta/charla que
# el LLM responde de su conocimiento (tool opcional; [] + prosa = válido).
CASES: list[tuple[str, str, bool]] = [
    # apps (abrir/cerrar) — 2 variantes c/u
    ("apps", "abre la calculadora", True),
    ("apps", "abrí el bloc de notas", True),
    ("apps", "cierra el bloc de notas", True),
    ("apps", "open the file explorer", True),
    # ventanas
    ("ventanas", "minimiza todas las ventanas", True),
    ("ventanas", "maximiza la ventana actual", True),
    ("ventanas", "cierra esta ventana", True),
    # audio
    ("audio", "pon el volumen al 30", True),
    ("audio", "sube el volumen", True),
    ("audio", "mutea el sonido", True),
    ("audio", "turn up the volume", True),
    # media
    ("media", "pon música en spotify", True),
    ("media", "pausa la música", True),
    ("media", "pon un video de lofi en youtube", True),
    ("media", "prende algo en netflix", True),
    # sistema / visión
    ("sistema", "sacá un screenshot", True),
    ("sistema", "cuánta RAM estoy usando", True),
    ("sistema", "lista los procesos que más consumen", True),
    ("vision", "qué hay en mi pantalla", True),
    ("vision", "leéme lo que dice la pantalla", True),
    # navegar / buscar web
    ("navegar", "andá a youtube", True),
    ("navegar", "entrá a la página de wikipedia", True),
    ("buscar", "buscá teclados mecánicos en google", True),
    ("buscar", "busca el clima en internet", True),
    # preguntas de conocimiento (LLM responde directo; tool opcional)
    ("preguntas", "quién es Lionel Messi", False),
    ("preguntas", "qué es una GPU", False),
    ("preguntas", "cuánto es 25 por 4", False),
    # clima
    ("clima", "qué clima hace hoy", True),
    ("clima", "va a llover mañana", True),
    # email
    ("email", "mandale un correo a ana@gmail.com diciendo que llego tarde", True),
    ("email", "escribile un mail a juan@hotmail.com", True),
    # whatsapp enviar / responder / leer
    ("wa_send", "mandale un whatsapp a mamá diciendo que ya voy", True),
    ("wa_send", "escribile por whatsapp a Pedro", True),
    ("wa_reply", "respondele a mamá que sí", True),
    ("wa_reply", "contestale que llego en 10", True),
    ("wa_read", "leéme el último mensaje de Pedro", True),
    ("wa_read", "qué me escribió mamá", True),
    # contactos
    ("contactos", "agendá a Carlos con el número 1133445566", True),
    ("contactos", "guardá el contacto de Lucía 1199887766", True),
    # recordatorio / alarma / timer
    ("recordatorio", "recordame comprar pan a las 6 de la tarde", True),
    ("recordatorio", "avisame en 20 minutos que saque la comida", True),
    ("alarma", "poné una alarma a las 7 de la mañana", True),
    ("alarma", "despertame a las 8 y media", True),
    ("timer", "poné un timer de 5 minutos", True),
    ("timer", "contá 10 minutos", True),
    # agenda
    ("agenda", "qué tengo agendado para hoy", True),
    ("agenda", "agendá una reunión el viernes a las 3", True),
    # notas
    ("notas", "tomá nota: comprar leche", True),
    ("notas", "anotá que tengo que llamar al dentista", True),
    # wifi / bluetooth
    ("wifi", "apagá el wifi", True),
    ("wifi", "conectate al wifi de casa", True),
    ("bluetooth", "prendé el bluetooth", True),
    ("bluetooth", "desactivá el bluetooth", True),
    # archivos / portapapeles
    ("archivos", "buscá el archivo presupuesto.xlsx", True),
    ("archivos", "abrí mi carpeta de descargas", True),
    ("portapapeles", "copiá esto al portapapeles: hola mundo", True),
    ("portapapeles", "qué hay en el portapapeles", True),
    # charla / identidad / meta  (NO debe sacar screenshot ni inventar acción)
    ("charla", "hola", False),
    ("charla", "gracias", False),
    ("charla", "quién eres", False),
    ("charla", "qué podés hacer", False),
]


def _stub_physical(ag):
    """Neutraliza TODA acción real del SO. Devuelve resultados plausibles para
    que el agente continúe su flujo, pero sin SendInput, sin lanzar apps, sin
    abrir URLs, sin enviar mensajes, sin tocar wifi/bt/brillo."""
    t = ag.tools
    ok = lambda *a, **k: {"ok": True, "stubbed": True}
    # --- GUI físico (SendInput / pantalla) ---
    t.gui_keypress = lambda a: {"ok": True, "stubbed": True}
    t.gui_type = lambda a: {"ok": True, "typed": a.get("text", ""), "stubbed": True}
    t.gui_type_into = lambda a: {"ok": True, "stubbed": True}
    t.gui_click = lambda a: {"ok": True, "stubbed": True}
    t.gui_click_button = lambda a: {"ok": True, "clicked": True, "stubbed": True}
    t.gui_scroll = lambda a: {"ok": True, "stubbed": True}
    t.gui_screenshot = lambda a: {"ok": True, "image_path": str(ROOT / "x.png"), "stubbed": True}
    if hasattr(t, "_send_text_via_sendinput"):
        t._send_text_via_sendinput = lambda text: {"ok": True, "stubbed": True}
    # visión: no cargar mmproj ni describir de verdad
    t._describe_image_directly = lambda *a, **k: "(descripción de pantalla simulada)"
    # --- lanzar apps / abrir URLs ---
    if hasattr(t, "app_open"):
        t.app_open = lambda *a, **k: {"ok": True, "opened": True, "stubbed": True}
    if hasattr(t, "web_open_url"):
        t.web_open_url = lambda *a, **k: {"ok": True, "opened": True, "stubbed": True}
    if hasattr(t, "_open_url_in_browser"):
        t._open_url_in_browser = lambda *a, **k: {"ok": True, "opened": True, "stubbed": True}
    # app_resolver.open (lanza el proceso)
    try:
        if getattr(t, "apps", None) is not None:
            t.apps.open = lambda *a, **k: {"ok": True, "opened": True, "stubbed": True}
    except Exception:
        pass
    # --- mensajería / agenda real ---
    for name in ("whatsapp_tool", "_schedule_notification", "_send_whatsapp",
                 "system_brightness_set", "system_brightness_get"):
        if hasattr(t, name):
            setattr(t, name, ok)
    # web_search: devolvé algo sin red (rápido y determinista)
    t.web_search = lambda *a, **k: [
        {"title": "Resultado 1", "url": "https://example.com/1"},
        {"title": "Resultado 2", "url": "https://example.com/2"},
    ]


def _build_agent():
    from gemma4_agent.agent_core.agent import Gemma4Agent
    from gemma4_agent.infra.config import AgentConfig
    ag = Gemma4Agent(AgentConfig.from_env())
    _stub_physical(ag)
    return ag


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=str, default="")
    ap.add_argument("--runs", type=int, default=1)
    args = ap.parse_args()

    # boot del server compartido (detecta externo en :8080)
    from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
    from gemma4_agent.infra.llama_server import get_shared_manager
    prof = get_active_profile(); apply_profile_to_env(prof)
    print("[boot]", get_shared_manager().start(prof, wait_health=True, timeout_s=120), flush=True)

    only = {c.strip() for c in args.only.split(",") if c.strip()}
    cases = [c for c in CASES if not only or c[0] in only]

    by_cat: dict[str, list[bool]] = defaultdict(list)
    fails: list[tuple[str, str, str]] = []

    for cat, cmd, expects in cases:
        for _ in range(args.runs):
            ag = _build_agent()
            executed: list[str] = []
            orig = ag.trace.event

            def _ev(tid, kind, _ex=executed, _o=orig, **f):
                if kind == "tool_call":
                    n = f.get("name") or f.get("tool")
                    if n:
                        _ex.append(str(n))
                return _o(tid, kind, **f)

            ag.trace.event = _ev
            t0 = time.time()
            try:
                r = ag.run_content(cmd)
                reply = (getattr(r, "content", None) or "")[:75]
                err = getattr(r, "error", None)
                dom = [e.name for e in (r.tool_events or [])
                       if e.name not in {"session", "safety", "state", "verify"}]
            except Exception as exc:
                reply, err, dom = "", f"EXC {type(exc).__name__}: {exc}", []
            dt = time.time() - t0

            if err:
                ok = False
                fails.append((cat, cmd, f"ERROR: {err}"))
            elif expects:
                ok = bool(dom)
                if not ok:
                    fails.append((cat, cmd, f"sin tool de dominio; reply={reply!r}"))
            else:
                # charla/preguntas: NO debe sacar screenshot ni inventar acción
                # física; un [] + prosa, o web/knowledge, es válido. FALLA si
                # ejecutó gui/computer_use (la clase de bug que arreglamos).
                bad = any(d in {"gui", "computer_use", "uia"} for d in dom)
                ok = not bad
                if not ok:
                    fails.append((cat, cmd, f"acción física en charla: {dom} reply={reply!r}"))
            by_cat[cat].append(ok)
            print(f"  [{cat:12s}] {'OK ' if ok else 'XX '} {cmd[:40]:42s} "
                  f"dom={dom} {dt:4.1f}s | {reply!r}", flush=True)

    print("\n==== BATERÍA INTEGRAL (agente fresco, físico stubeado) ====", flush=True)
    tot_ok = tot = 0
    for cat in dict.fromkeys(c for c, _, _ in cases):
        oks = by_cat[cat]
        tot_ok += sum(oks); tot += len(oks)
        flag = "" if sum(oks) == len(oks) else "  <-- revisar"
        print(f"  {cat:13s} {sum(oks)}/{len(oks)}{flag}", flush=True)
    print(f"\n  OVERALL: {tot_ok}/{tot} = {tot_ok/max(1,tot):.2f}", flush=True)
    if fails:
        print(f"\n  === {len(fails)} a revisar ===", flush=True)
        for cat, cmd, why in fails:
            print(f"    [{cat}] {cmd!r}: {why}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
