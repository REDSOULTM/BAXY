"""Computer-use UNIVERSAL — ejecutor de planes (NO un macro por intención).

Diseño (decidido por medición 2026-05-25, gates en CLAUDE.md):
  - El 4B NO encadena acciones solo (medido 2/10: hace focus_app y para).
  - El 4B SÍ emite un PLAN de primitivas (medido 10/10 parseable, 7/10 correcto).
  -> El LLM da el OBJETIVO crudo (cualquier idioma/fraseo). Un PLANIFICADOR (el
     mismo 4B con un prompt de plan) lo descompone en un PLAN de primitivas
     ATÓMICAS. UNA función ejecuta esas primitivas verificando por estado del SO.
     NO hay un macro/regex por verbo: agregar una intención nueva = el 4B la
     planifica con las primitivas que ya hay; agregar una CAPACIDAD nueva = una
     primitiva nueva (raro), no una función por fraseo.

Primitivas (vocabulario CERRADO, reutilizan tools/helpers ya existentes):
  focus_app(app)   -> _focus_window_chen (restaura si está minimizada + ALT-trick)
  open_chat(name)  -> quick-switcher (Ctrl+K/Ctrl+T) + verify por título
  open_url(url)    -> barra de direcciones (Ctrl+L) + type + Enter, o web_open_url
  type(text)       -> gui type (SendInput in-process)
  send()           -> keypress ENTER
  keypress(keys)   -> gui keypress (combos in-process)
  click(label)     -> gui click_button (UIA Name + InvokePattern + verify)

VERIFY por estado del SO entre pasos (título de ventana, no frame-diff frágil).
Universal: sin listas de apps ni idiomas; usa los títulos REALES del SO.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

PRIMITIVES = ("focus_app", "open_chat", "open_url", "type", "send", "keypress", "click")


def _foreground_title() -> str:
    """Título de la ventana en FOREGROUND ahora. Para verificar por estado del SO
    cuál ventana fue la afectada (cuando hay varias del mismo app). '' si no se puede."""
    try:
        import win32gui
        return win32gui.GetWindowText(win32gui.GetForegroundWindow()) or ""
    except Exception:
        return ""

# Prompt del PLANIFICADOR. El 4B sólo LISTA pasos (su fuerte: 10/10 parseable).
# No ejecuta: devuelve datos. Vocabulario cerrado -> el ejecutor mapea 1:1.
PLANNER_SYSTEM = (
    "Sos un planificador de acciones de computer-use en Windows. Te doy un objetivo "
    "del usuario (en cualquier idioma) y devolvés SOLO un JSON: una lista de pasos. "
    "Cada paso es un objeto {\"op\": <primitiva>, \"arg\": <string>}.\n"
    "Primitivas válidas:\n"
    "- focus_app: traer al frente / abrir la app. arg = nombre de la app.\n"
    "- open_chat: abrir el chat/conversación/canal de un contacto en una app de "
    "chat (Discord/Slack/Teams/WhatsApp). arg = nombre del contacto o canal.\n"
    "- open_url: navegar a una URL en el navegador. arg = la URL (con o sin https).\n"
    "- type: teclear texto en la app enfocada. arg = el texto.\n"
    "- send: enviar/confirmar (Enter). arg = \"\".\n"
    "- keypress: una tecla o combo. arg = la tecla (ej: enter, ctrl+s, escape).\n"
    "- click: clickear un control/botón por su nombre visible. arg = el nombre.\n"
    "Reglas: usá el MÍNIMO de pasos. Empezá por focus_app si el objetivo nombra una "
    "app. Para 'mandar/escribir un mensaje a X': focus_app, open_chat(X), type(msg), "
    "send. Para 'abrir/operar una cuenta en la calculadora': focus_app, type(expr), "
    "keypress(enter). Para 'ir a una web': focus_app(navegador), open_url(url). "
    "IMPORTANTE: 'escribí/escribe/type/schreibe/scrivi <TEXTO> en <APP>' SIEMPRE son "
    "DOS pasos: focus_app(APP) Y type(TEXTO) — aunque el TEXTO sea una sola palabra y "
    "la APP sea genérica (el editor/Editor/bloc de notas/notepad). Nunca te quedes "
    "solo en focus_app cuando el usuario dio un texto a escribir.\n"
    "Devolvé EXACTAMENTE el JSON, sin texto extra ni markdown.\n"
    "Ejemplos:\n"
    "'mandale hola a juan en discord' -> "
    '[{"op":"focus_app","arg":"discord"},{"op":"open_chat","arg":"juan"},'
    '{"op":"type","arg":"hola"},{"op":"send","arg":""}]\n'
    "'escribí hola en el editor' -> "
    '[{"op":"focus_app","arg":"editor"},{"op":"type","arg":"hola"}]'
)


def request_plan(chat_fn: Callable[[list[dict]], dict], goal: str) -> list[dict] | None:
    """Pide al 4B un plan de primitivas para `goal`. chat_fn(messages)->resp dict
    (OpenAI-style). Devuelve la lista de pasos parseada y validada, o None."""
    try:
        resp = chat_fn([
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": goal},
        ])
        text = (((resp or {}).get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    except Exception:
        return None
    return parse_plan(text)


def plan_for(agent: Any, goal: str) -> list[dict] | None:
    """Conveniencia: pide el plan usando el cliente del agente, resolviendo el
    MODELO de texto activo server-driven (en router mode el client default 'gemma-4'
    NO existe en el server — hay que pasar el preset '<profile>-text'). greedy para
    una decisión discreta y estable."""
    model = None
    try:
        from .llama_server import resolve_turn_model
        model = resolve_turn_model(has_image=False)  # '<profile>-text' o None
    except Exception:
        model = None

    def _chat(msgs):
        return agent.client.chat(msgs, tools=None, enable_thinking=False,
                                 max_tokens=256, timeout_s=60.0, greedy=True,
                                 model=model)
    return request_plan(_chat, goal)


def parse_plan(text: str) -> list[dict] | None:
    """Parsea el JSON del plan, tolerante a fences markdown y texto alrededor.
    Devuelve [{op,arg}] válido (ops en PRIMITIVES) o None."""
    if not text:
        return None
    t = text.strip()
    if "```" in t:
        parts = t.split("```")
        if len(parts) >= 2:
            t = parts[1]
            if t.lstrip().lower().startswith("json"):
                t = t.lstrip()[4:]
    i, j = t.find("["), t.rfind("]")
    if i < 0 or j < 0 or j <= i:
        return None
    try:
        plan = json.loads(t[i:j + 1])
    except Exception:
        return None
    if not isinstance(plan, list) or not plan:
        return None
    out = []
    for step in plan:
        if not isinstance(step, dict):
            return None
        op = str(step.get("op") or "").strip()
        if op not in PRIMITIVES:
            return None  # vocabulario cerrado: un op desconocido invalida el plan
        out.append({"op": op, "arg": str(step.get("arg") or "")})
    return out or None


def summarize_result(goal: str, plan: list[dict], result: dict) -> str:
    """Resumen humano y HONESTO del resultado de ejecutar un plan. Reporta lo que el
    estado del SO confirma — sin afirmar lo que no se verificó (CLAUDE.md §3)."""
    steps = result.get("steps") or []
    app = result.get("focused_app") or ""
    if not result.get("ok"):
        failed = result.get("failed_at")
        bad = next((s for s in steps if s.get("op") == failed and not s.get("ok")), None)
        what = (bad or {}).get("arg") or failed or "la acción"
        if failed == "focus_app":
            return f"No pude enfocar/abrir «{what}»."
        if failed == "open_chat":
            return (f"No encontré «{what}» en {app}. ¿Está escrito igual que en la app?")
        if failed == "open_url":
            return f"No pude abrir «{what}» en el navegador."
        return f"No pude completar «{goal}» (falló {failed})."
    # éxito: describir según las primitivas que corrieron.
    ops = [s["op"] for s in steps]
    sent = "send" in ops
    typed = next((s["arg"] for s in steps if s["op"] == "type"), "")
    chat = next((s["arg"] for s in steps if s["op"] == "open_chat"), "")
    url = next((s["arg"] for s in steps if s["op"] == "open_url"), "")
    if sent and chat:
        return f"Listo, le escribí «{typed}» a {chat}."
    if chat:
        return f"Abrí el chat de «{chat}»" + (f" en {app}." if app else ".")
    if url:
        return f"Listo, entré a {url}" + (f" en {app}." if app else ".")
    if typed:
        return f"Listo, escribí «{typed}»" + (f" en {app}." if app else ".")
    return f"Listo." if app else "Hecho."


class PlanExecutor:
    """Ejecuta un plan de primitivas reusando los helpers del agente/tools. UNA
    clase, un dispatch por primitiva — sin código por intención. Verifica por
    estado del SO. `agent` provee: tools, _focus_window_chen (vía tools),
    _quick_switcher_nav, _app_window_title, _title_now_matches."""

    def __init__(self, agent: Any):
        self.ag = agent
        self.tools = agent.tools

    # -- primitivas atómicas (cada una reusa lo que YA existe) -----------------
    def _focus_app(self, app: str) -> dict:
        # enfocar si está abierta (restaura minimizada); si no, abrirla.
        win = self.ag._window_title_in_text(app) or app
        ok = False
        try:
            ok = self.tools._focus_window_chen(win)
        except Exception:
            ok = False
        if not ok:
            # no estaba al frente / no abierta -> intentar abrir por app.open.
            try:
                r = self.tools.execute("app", {"action": "open", "name": app})
                ok = bool(r.get("ok"))
                time.sleep(1.5)
                self.tools._focus_window_chen(app)
            except Exception:
                pass
        return {"ok": True, "focused": win, "launched_if_needed": not ok}

    def _open_chat(self, name: str, app_hint: str) -> dict:
        # quick-switcher (Ctrl+K) + verify por título; reusa _quick_switcher_nav.
        win = app_hint or (self.ag._window_title_in_text(name) or "")
        before = self.ag._app_window_title(win) if win else ""
        try:
            self.ag._quick_switcher_nav(win, name, "cu")
        except Exception:
            pass
        matched = self.ag._title_now_matches(win, name, before) if win else False
        return {"ok": matched, "verified": matched, "target": name}

    def _open_url(self, url: str, app_hint: str) -> dict:
        u = url.strip()
        if not re.match(r"^https?://", u, re.IGNORECASE):
            u = "https://" + u
        # si hay un navegador al frente/abierto, usar su barra (Ctrl+L) — respeta el
        # navegador del usuario; si no, web_open_url (default del SO).
        win = app_hint or ""
        before = self.ag._app_window_title(win) if win else ""
        try:
            from . import gui_safety
            gui_safety.reset_action_budget()
            if win:
                self.tools._focus_window_chen(win)
                time.sleep(0.5)
                self.tools.execute("gui", {"action": "keypress", "keys": "ctrl+l"})
                time.sleep(0.3)
                self.tools.execute("gui", {"action": "type", "text": u})
                time.sleep(0.3)
                self.tools.execute("gui", {"action": "keypress", "keys": "enter"})
                time.sleep(1.5)
            else:
                self.tools.web_open_url({"url": u})
                time.sleep(1.5)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        # VERIFY contra la ventana en FOREGROUND (la que acabamos de enfocar+navegar),
        # NO "cualquier ventana de la app": puede haber VARIAS ventanas del mismo
        # navegador y _app_window_title devuelve una arbitraria (bug medido: 5
        # ventanas Opera -> leía la equivocada). El host de la URL debe aparecer en
        # el título de la ventana activa.
        after = _foreground_title()
        host = re.sub(r"^https?://(www\.)?", "", u).split("/")[0]
        token = host.split(".")[0]
        # VERIFY robusto: comparar SIN espacios ni puntuación en AMBOS lados. El
        # título suele "espaciar" el dominio ("stackoverflow" -> "Stack Overflow",
        # "duckduckgo" -> "DuckDuckGo") -> el match contiguo daba falso-negativo
        # (bug medido en la maratón). Normalizamos a solo-alfanumérico.
        def _norm(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())
        ok = bool(token) and _norm(token) in _norm(after)
        return {"ok": ok, "verified": ok, "url": u, "title": after}

    def _type(self, text: str, win: str) -> dict:
        try:
            if win:
                self.tools._focus_window_chen(win)
                time.sleep(0.5)  # dejar que la app quede LISTA para recibir teclas
                                  # (notepad recién enfocado se comía los 1ros chars)
            r = self.tools.execute("gui", {"action": "type", "text": text})
            return {"ok": bool(r.get("ok")), "text": text}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _send(self, win: str) -> dict:
        return self._keypress("enter", win)

    def _keypress(self, keys: str, win: str) -> dict:
        try:
            r = self.tools.execute("gui", {"action": "keypress", "keys": keys})
            return {"ok": bool(r.get("ok")), "keys": keys}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _click(self, label: str, win: str) -> dict:
        try:
            r = self.tools.execute("gui", {"action": "click_button", "label": label, "window": win})
            inner = r.get("result", r) if isinstance(r, dict) else {}
            return {"ok": bool(inner.get("ok")), "label": label,
                    "grounding": inner.get("grounding")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def _app_token(s: str) -> str:
        """Token ESTABLE de la app desde un nombre o título. Para apps con título
        dinámico (navegador, Discord) el nombre de la app es el ÚLTIMO segmento tras
        ' - ' ("Welcome to Python.org - Opera" -> "Opera"); si no hay ' - ', el token
        más largo. Se usa como contexto de foco persistente entre pasos (NO el título
        completo, que cambia al navegar y deja stale la verificación)."""
        s = (s or "").strip()
        if " - " in s:
            return s.split(" - ")[-1].strip()
        toks = sorted((t for t in re.findall(r"\w+", s) if len(t) >= 4), key=len, reverse=True)
        return toks[0] if toks else s

    # -- ejecutor ---------------------------------------------------------------
    def execute(self, plan: list[dict], turn_id: str = "cu") -> dict:
        """Ejecuta el plan paso a paso. Mantiene `app_token` (nombre ESTABLE de la
        app, p.ej. 'Opera'/'Discord'/'Calculadora') como contexto de foco — NO el
        título completo (que cambia al navegar). type/click/keypress/open_* operan
        sobre esa app. Para en el 1er fallo DURO de navegación (focus/open_chat/
        open_url); type/keypress/send son best-effort. Verifica por estado del SO."""
        app_token = ""
        steps_out = []
        try:
            from . import gui_safety
            gui_safety.reset_action_budget()
        except Exception:
            pass
        for step in plan:
            op, arg = step["op"], step["arg"]
            if op == "focus_app":
                res = self._focus_app(arg)
                # token estable: del título real si lo hay, si no del arg.
                full = self.ag._window_title_in_text(arg) or arg
                app_token = self._app_token(full)
            elif op == "open_chat":
                res = self._open_chat(arg, app_token)
            elif op == "open_url":
                res = self._open_url(arg, app_token)
            elif op == "type":
                res = self._type(arg, app_token)
            elif op == "send":
                res = self._send(app_token)
            elif op == "keypress":
                res = self._keypress(arg, app_token)
            elif op == "click":
                res = self._click(arg, app_token)
            else:
                res = {"ok": False, "error": f"primitiva desconocida: {op}"}
            steps_out.append({"op": op, "arg": arg, **res})
            try:
                self.ag.trace.event(turn_id, "cu_step", op=op, arg=str(arg)[:40],
                                    ok=res.get("ok"), app=app_token[:30])
            except Exception:
                pass
            if op in ("focus_app", "open_chat", "open_url") and not res.get("ok"):
                return {"ok": False, "steps": steps_out, "focused_app": app_token,
                        "failed_at": op}
            time.sleep(0.2)
        return {"ok": True, "steps": steps_out, "focused_app": app_token}
