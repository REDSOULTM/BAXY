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
import unicodedata
from typing import Any, Callable

PRIMITIVES = (
    "focus_app", "open_chat", "open_voice", "open_url", "type", "send",
    "keypress", "click", "fill_field", "toggle", "wait_for", "scroll", "wait",
    "discord_control",
)

# Navegadores CONCRETOS que el usuario puede nombrar (nombres propios, no idioma).
# Si el app_hint de open_url matchea uno de estos, navegamos en ESA ventana por la
# barra de direcciones. Si NO (palabra genérica "navegador"/"browser", o vacío, o
# una app que no es navegador), usamos el navegador POR DEFECTO del SO
# (web_open_url / webbrowser.open) que SIEMPRE funciona — fix del caso "andá al
# navegador y comprá X" que fallaba porque "navegador" no es una app instalada.
_CONCRETE_BROWSER_TOKENS = (
    "chrome", "edge", "opera", "brave", "firefox", "vivaldi", "msedge", "operagx",
)

# Reintentos por paso CRÍTICO (hard-fail/verificado) antes de abortar la cadena.
# Acotado para no colgarse en un paso imposible: avanza lo más posible y, si tras
# los reintentos no puede, aborta honesto. Gate por env para tunear/medir.
import os as _os_cu
_STEP_RETRIES = int(_os_cu.environ.get("GEMMA4_CU_STEP_RETRIES", "2"))


def _is_concrete_browser(app_hint: str) -> bool:
    folded = re.sub(r"\s+", " ", (app_hint or "").casefold()).strip()
    if not folded:
        return False
    return any(tok in folded for tok in _CONCRETE_BROWSER_TOKENS)


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
    "- open_voice: entrar/unirse a un canal de voz en Discord. arg = nombre del canal.\n"
    "- open_url: navegar a una URL en el navegador. arg = la URL (con o sin https).\n"
    "- type: teclear texto en la app enfocada. arg = el texto.\n"
    "- send: enviar/confirmar (Enter). arg = \"\".\n"
    "- keypress: una tecla o combo. arg = la tecla (ej: enter, ctrl+s, escape).\n"
    "- fill_field: rellenar un campo por su etiqueta visible. arg = campo=valor.\n"
    "- toggle: activar/desactivar un switch o checkbox por nombre. arg = campo=on/off.\n"
    "- wait_for: esperar a que aparezca un texto/control. arg = texto visible.\n"
    "- discord_control: controlar voz en Discord. arg = mute, unmute, "
    "toggle_mute, deafen, undeafen, toggle_deafen, disconnect_voice.\n"
    "- scroll: desplazar la vista. arg = cantidad entera, negativo baja, positivo sube.\n"
    "- wait: esperar contenido dinamico. arg = segundos.\n"
    "- click: clickear un control/botón por su nombre visible. arg = el nombre.\n"
    "Reglas: usá el MÍNIMO de pasos. Empezá por focus_app si el objetivo nombra una "
    "app. Para 'mandar/escribir un mensaje a X': focus_app, open_chat(X), type(msg), "
    "send. Para 'abrir/operar una cuenta en la calculadora': focus_app, type(expr), "
    "keypress(enter). Para 'ir a una web': open_url(url), sin focus_app previo. "
    "IMPORTANTE: 'escribí/escribe/type/schreibe/scrivi <TEXTO> en <APP>' SIEMPRE son "
    "DOS pasos: focus_app(APP) Y type(TEXTO) — aunque el TEXTO sea una sola palabra y "
    "la APP sea genérica (el editor/Editor/bloc de notas/notepad). Nunca te quedes "
    "solo en focus_app cuando el usuario dio un texto a escribir.\n"
    "Discord: para un canal de texto usa focus_app(discord), open_chat(canal). "
    "Si tambien pide escribir/enviar, agrega type(mensaje), send. Para entrar a "
    "un canal de voz usa focus_app(discord), open_voice(canal). Para mutear o "
    "silenciar el microfono usa focus_app(discord), discord_control(mute); para "
    "desmutear usa unmute; para ensordecer/deafen usa deafen; para quitar "
    "ensordecido usa undeafen; para salir de llamada/canal de voz usa "
    "disconnect_voice.\n"
    "Navegador/apps genericas: nueva pestana = keypress(ctrl+t), open_url(url); "
    "cerrar pestana = keypress(ctrl+w); rellenar formulario = fill_field(campo=valor), "
    "activar/desactivar checkbox o switch = toggle(campo=on/off), "
    "no click+type salvo que fill_field falle; contenido dinamico = wait_for(texto) "
    "si sabes que texto/control debe aparecer, si no wait(segundos); desplazamiento = scroll(cantidad). "
    "Si el objetivo pide abrir un navegador y luego tocar algo dentro del navegador "
    "(favorito/bookmark/barra de favoritos, resultado, boton, link o elemento visible), "
    "planifica una cadena: focus_app(navegador), wait(1), click(nombre_del_elemento). "
    "IR A UNA WEB: para abrir una URL o un sitio (incluidas TIENDAS como Instant "
    "Gaming, Steam store, Epic), usa SOLO open_url(url) — NO pongas focus_app antes. "
    "open_url abre el navegador por defecto solo. focus_app(navegador) NO sirve "
    "('navegador' no es una app instalada). Si el usuario nombra un navegador "
    "CONCRETO ('en Opera', 'en Chrome'), recién ahí focus_app(ese nombre), open_url. "
    "Para BUSCAR algo en una tienda: open_url del sitio de la tienda, wait(2), y si "
    "hace falta type(lo que busca) + send. "
    "No uses gui.open: abrir apps es focus_app dentro de computer_use.\n"
    "Devolvé EXACTAMENTE el JSON, sin texto extra ni markdown.\n"
    "Ejemplos:\n"
    "'mandale hola a juan en discord' -> "
    '[{"op":"focus_app","arg":"discord"},{"op":"open_chat","arg":"juan"},'
    '{"op":"type","arg":"hola"},{"op":"send","arg":""}]\n'
    "'escribí hola en el editor' -> "
    '[{"op":"focus_app","arg":"editor"},{"op":"type","arg":"hola"}]\n'
    "'entra al canal de voz musica en discord' -> "
    '[{"op":"focus_app","arg":"discord"},{"op":"open_voice","arg":"musica"}]\n'
    "'mutea mi microfono en discord' -> "
    '[{"op":"focus_app","arg":"discord"},{"op":"discord_control","arg":"mute"}]\n'
    "'abre el navegador y clickea un favorito llamado noticias' -> "
    '[{"op":"focus_app","arg":"Opera GX"},{"op":"wait","arg":"1"},'
    '{"op":"click","arg":"noticias"}]\n'
    "'anda a instant gaming y busca resident evil requiem' -> "
    '[{"op":"open_url","arg":"instant-gaming.com"},{"op":"wait","arg":"2"},'
    '{"op":"type","arg":"resident evil requiem"},{"op":"send","arg":""}]\n'
    "'rellena el campo email con ana@example.com' -> "
    '[{"op":"fill_field","arg":"email=ana@example.com"}]\n'
    "'activa las notificaciones' -> "
    '[{"op":"toggle","arg":"notificaciones=on"}]\n'
    "'entra a youtube' -> "
    '[{"op":"open_url","arg":"youtube.com"}]'
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


def _fold_label(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _contains_folded(haystack: str, needles: tuple[str, ...]) -> bool:
    h = _fold_label(haystack)
    return any(_fold_label(n) in h for n in needles if n)


def _canonical_discord_control(action: str) -> str:
    a = _fold_label(str(action or "").replace("_", " ")).replace(" ", "_")
    if not a:
        return ""
    canonical = {
        "mute", "unmute", "toggle_mute",
        "deafen", "undeafen", "toggle_deafen",
        "disconnect_voice",
    }
    compact = {
        "togglemute": "toggle_mute",
        "toggledeafen": "toggle_deafen",
        "disconnectvoice": "disconnect_voice",
    }
    return a if a in canonical else compact.get(a.replace("_", ""), a)


def _discord_control_human(action: str) -> str:
    return {
        "mute": "silencie el microfono",
        "unmute": "reactive el microfono",
        "toggle_mute": "cambie el mute del microfono",
        "deafen": "active el ensordecido",
        "undeafen": "quite el ensordecido",
        "toggle_deafen": "cambie el ensordecido",
        "disconnect_voice": "sali del canal de voz",
    }.get(action, f"ejecute {action}")


def summarize_result(goal: str, plan: list[dict], result: dict) -> str:
    """Resumen humano y HONESTO del resultado de ejecutar un plan. Reporta lo que el
    estado del SO confirma — sin afirmar lo que no se verificó (CLAUDE.md §3)."""
    steps = result.get("steps") or []
    app = result.get("focused_app") or ""
    if not result.get("ok"):
        failed = result.get("failed_at")
        bad = next((s for s in steps if s.get("op") == failed and not s.get("ok")), None)
        failed_step = next((s for s in steps if s.get("op") == failed), None)
        completion = str((failed_step or {}).get("completion_status") or "")
        if completion == "needs_capability":
            return (
                f"No pude completar '{goal}': la app no expone una capa usable "
                "de API/UIA/OCR/vision para verificar la accion."
            )
        if completion in {"needs_secret_handoff", "secret_handoff"}:
            return (
                f"No pude completar '{goal}': el campo parece sensible y requiere "
                "ingreso/confirmacion directa del usuario."
            )
        if failed_step and failed_step.get("verified") is False:
            return f"Intente completar '{goal}', pero no pude verificar: {failed}."
        what = (bad or {}).get("arg") or failed or "la acción"
        if failed == "focus_app":
            return f"No pude enfocar/abrir «{what}»."
        if failed == "open_chat":
            return (f"No encontré «{what}» en {app}. ¿Está escrito igual que en la app?")
        if failed == "open_voice":
            return f"No pude entrar al canal de voz '{what}' en {app}."
        if failed == "discord_control":
            return f"No pude controlar Discord para '{what}'."
        if failed == "open_url":
            return f"No pude abrir {what} en el navegador."
        if failed == "fill_field":
            return f"No pude rellenar el campo pedido ({what})."
        if failed == "toggle":
            return f"No pude cambiar el control pedido ({what})."
        if failed == "wait_for":
            return f"No aparecio {what} antes del timeout."
        return f"No pude completar «{goal}» (falló {failed})."
    # éxito: describir según las primitivas que corrieron.
    if result.get("verified") is False:
        unverified = [
            str(s.get("op") or "")
            for s in steps
            if s.get("verified") is not True
        ]
        detail = ", ".join(op for op in unverified if op) or "pasos criticos"
        return f"Intente completar '{goal}', pero no pude verificar: {detail}."
    ops = [s["op"] for s in steps]
    sent = "send" in ops
    typed = next((s["arg"] for s in steps if s["op"] == "type"), "")
    # nombre REAL del chat abierto (la app pudo fuzzy-matchear un typo: "shotercock"
    # -> "ShooterCOCK"); reportamos lo que la app realmente abrió, no lo que se tipeó.
    _chat_step = next((s for s in steps if s["op"] == "open_chat"), None)
    chat = (_chat_step.get("opened") or _chat_step.get("arg")) if _chat_step else ""
    _voice_step = next((s for s in steps if s["op"] == "open_voice"), None)
    voice = (_voice_step.get("opened") or _voice_step.get("arg")) if _voice_step else ""
    _discord_step = next((s for s in reversed(steps) if s["op"] == "discord_control"), None)
    _click_step = next((s for s in reversed(steps) if s["op"] == "click"), None)
    _fill_step = next((s for s in reversed(steps) if s["op"] == "fill_field"), None)
    _toggle_step = next((s for s in reversed(steps) if s["op"] == "toggle"), None)
    _wait_step = next((s for s in reversed(steps) if s["op"] == "wait_for"), None)
    url = next((s["arg"] for s in steps if s["op"] == "open_url"), "")
    if _discord_step:
        act = _canonical_discord_control(_discord_step.get("action") or _discord_step.get("arg") or "")
        phrase = _discord_control_human(act)
        if _discord_step.get("already"):
            return f"Discord ya estaba en ese estado ({phrase})."
        if _discord_step.get("verified"):
            return f"Listo, {phrase} en Discord."
        return f"Ejecute {phrase} en Discord, pero no pude verificar el estado."
    if sent and chat:
        return f"Listo, le escribí «{typed}» a {chat}."
    if voice:
        return f"Listo, entre al canal de voz '{voice}'" + (f" en {app}." if app else ".")
    if chat:
        return f"Abrí el chat de «{chat}»" + (f" en {app}." if app else ".")
    if url:
        return f"Listo, entré a {url}" + (f" en {app}." if app else ".")
    if _fill_step:
        field = _fill_step.get("field") or (_fill_step.get("arg") or "").split("=", 1)[0]
        return f"Listo, rellene el campo {field}." + (f" en {app}." if app else ".")
    if _toggle_step:
        label = _toggle_step.get("label") or (_toggle_step.get("arg") or "").split("=", 1)[0]
        return f"Listo, cambie {label}." + (f" en {app}." if app else ".")
    if _wait_step:
        target = _wait_step.get("target") or _wait_step.get("arg") or "el contenido"
        return f"Listo, aparecio {target}." + (f" en {app}." if app else ".")
    if _click_step:
        label = _click_step.get("arg") or _click_step.get("label") or "el objetivo"
        return f"Listo, hice click en «{label}»" + (f" en {app}." if app else ".")
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
        from .computer_use_caps import CapabilityDetector, CapabilityRouter, choose_policy, family_for_snapshot
        self.detector = CapabilityDetector(self.tools)
        self.capabilities = CapabilityRouter(self)
        self.choose_policy = choose_policy
        self.capability_family = family_for_snapshot

    # -- primitivas atómicas (cada una reusa lo que YA existe) -----------------
    def _focus_app(self, app: str) -> dict:
        # Structural verify: focusing an app is only successful if a window ends
        # up in the foreground. A launch request alone is not enough to mark the
        # plan verified.
        win = self.ag._window_title_in_text(app) or app
        focused_title = ""

        def _try_focus(hint: str) -> bool:
            nonlocal focused_title
            if not hint:
                return False
            try:
                if not self.tools._focus_window_chen(hint):
                    return False
                time.sleep(0.2)
                focused_title = _foreground_title() or hint
                return True
            except Exception:
                return False

        ok = _try_focus(win)
        launched = False
        if not ok:
            try:
                r = self.tools.execute("app", {"action": "open", "name": app})
                launched = bool(r.get("ok"))
                time.sleep(1.5)
                for hint in (win, app, self.ag._window_title_in_text(app) or ""):
                    if _try_focus(hint):
                        ok = True
                        break
                    time.sleep(0.25)
            except Exception:
                ok = False
                launched = False
        return {
            "ok": bool(ok),
            "verified": bool(ok),
            "focused": focused_title or win,
            "requested_app": app,
            "launched_if_needed": launched,
        }

    def _open_chat(self, name: str, app_hint: str) -> dict:
        # quick-switcher (Ctrl+K) + verify por título; reusa _quick_switcher_nav.
        win = app_hint or (self.ag._window_title_in_text(name) or "")
        before = self.ag._app_window_title(win) if win else ""
        try:
            self.ag._quick_switcher_nav(win, name, "cu")
        except Exception:
            pass
        after = self.ag._app_window_title(win) if win else ""
        exact = self.ag._title_now_matches(win, name, before) if win else False
        # ÉXITO TOLERANTE A TYPOS: el quick-switcher de las apps de chat hace FUZZY
        # match — "shotercock" (typo) abre "ShooterCOCK". El verify exacto por
        # substring fallaba aunque el chat SÍ se abrió (bug medido 2026-05-25: el
        # usuario veía "No encontré" de un éxito real). Si el título CAMBIÓ a un chat
        # nuevo (navegó), lo contamos como éxito y reportamos el chat REAL abierto
        # (honesto: "abrí X" con el nombre que muestra la app, no el que tipeó mal).
        navigated = bool(after) and after != before
        ok = exact or navigated
        # nombre real del chat = primer segmento del título (sin la app), si navegó.
        actual = name
        if navigated and " - " in after:
            head = after.split(" - ")[0].strip().lstrip("@").strip()
            if head:
                actual = head
        return {"ok": ok, "verified": exact, "target": name,
                "opened": actual, "exact": exact, "fuzzy": navigated and not exact}

    def _open_voice(self, name: str, app_hint: str) -> dict:
        win = app_hint or "Discord"
        before_title = self.ag._app_window_title(win) if win else ""
        before_voice = self._discord_voice_status(win)
        try:
            self.ag._quick_switcher_nav(win, name, "cu_voice")
        except Exception:
            pass
        time.sleep(0.8)
        after_title = self.ag._app_window_title(win) if win else ""
        after_voice = self._discord_voice_status(win)
        exact = self.ag._title_now_matches(win, name, before_title) if win else False
        navigated = bool(after_title) and after_title != before_title
        connected = bool(after_voice.get("voice_connected"))
        became_connected = connected and not bool(before_voice.get("voice_connected"))
        target_tokens = tuple(t for t in _fold_label(name).split() if len(t) >= 3)
        target_visible = bool(target_tokens) and any(
            _contains_folded(str(label), target_tokens)
            for label in (after_voice.get("names") or [])
        )
        # UIA for Electron can be unavailable on already-running Discord
        # instances. A title change is still real OS state, so let the action
        # proceed, but only mark it verified when we can tie it to the target or
        # to a voice-connected state.
        ok = became_connected or target_visible or exact or navigated
        actual = name
        if navigated and " - " in after_title:
            head = after_title.split(" - ")[0].strip().lstrip("@").strip()
            if head:
                actual = head
        return {
            "ok": ok,
            "verified": became_connected or target_visible or exact,
            "target": name,
            "opened": actual,
            "exact": exact,
            "fuzzy": navigated and not exact,
            "voice_connected": connected,
            "target_visible": target_visible,
        }

    def _open_url(self, url: str, app_hint: str) -> dict:
        u = url.strip()
        if not re.match(r"^https?://", u, re.IGNORECASE):
            u = "https://" + u
        # ¿El app_hint nombra un navegador CONCRETO (Chrome/Opera/...)? Solo en ese
        # caso usamos la barra de direcciones (Ctrl+L) de ESA ventana. Si es la
        # palabra GENÉRICA "navegador"/"browser", o está vacío, o es otra app, NO
        # tipeamos a ciegas en una ventana que quizás no existe: usamos el
        # navegador POR DEFECTO del SO (web_open_url), que SIEMPRE abre la URL.
        # (Fix 2026-05-26: "andá al navegador y comprá X" fallaba porque
        # focus_app("navegador") no resuelve ninguna app y luego se tipeaba en la
        # ventana equivocada -> verify fallaba -> needs_verification.)
        win = app_hint if _is_concrete_browser(app_hint) else ""
        dispatched = False  # ¿el SO ACEPTÓ abrir la URL? (web_open_url opened=True)
        try:
            from . import gui_safety
            gui_safety.reset_action_budget()
            if win:
                # NAVEGADOR CONCRETO: tecleamos en SU barra de direcciones -> ESA
                # ventana debe mostrar el sitio. La verificación por título es
                # FUERTE y exigible (no marcamos dispatched-leniente: si el título
                # no matchea, es un fallo real — tecleamos en una ventana concreta).
                self.tools._focus_window_chen(win)
                time.sleep(0.5)
                self.tools.execute("gui", {"action": "keypress", "keys": "ctrl+l"})
                time.sleep(0.3)
                self.tools.execute("gui", {"action": "type", "text": u})
                time.sleep(0.3)
                self.tools.execute("gui", {"action": "keypress", "keys": "enter"})
                time.sleep(1.5)
            else:
                # NAVEGADOR POR DEFECTO: el SO abre la URL pero NO controlamos qué
                # ventana queda al frente -> dispatched-leniente (opened=True es
                # evidencia de que se abrió, aunque el foreground sea otra app).
                _wr = self.tools.web_open_url({"url": u})
                dispatched = bool(isinstance(_wr, dict) and (_wr.get("ok") or _wr.get("opened")))
                time.sleep(1.8)
        except Exception as exc:
            return {"ok": False, "verified": False, "error": str(exc)}
        # VERIFY por TÍTULO de la ventana en foreground (confirmación FUERTE: el
        # host aparece en el título de la ventana activa). Normalizamos a solo
        # alfanumérico (el título "espacia" el dominio: stackoverflow->Stack Overflow).
        after = _foreground_title()
        host = re.sub(r"^https?://(www\.)?", "", u).split("/")[0]
        token = host.split(".")[0]
        def _norm(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())
        title_match = bool(token) and _norm(token) in _norm(after)
        # SEMÁNTICA HONESTA (fix 2026-05-27, cadenas largas): abrir una URL es una
        # acción DISPATCH-async. El SO acepta el open (web_open_url opened=True) pero
        # la pestaña/ventana puede NO estar al frente al instante (otra app enfocada
        # -> el título no matchea) -> ANTES eso daba ok=False y ABORTABA la cadena
        # entera por un falso-negativo. Ahora:
        #   - título matchea -> verificado FUERTE (ok=True, verified=True).
        #   - despachado pero sin confirmar foreground -> ok=True (la URL se abrió),
        #     verified=None (no pude CONFIRMAR el foreground, pero NO es un fallo).
        #   - ni despachado ni título -> fallo real (ok=False).
        if title_match:
            return {"ok": True, "verified": True, "url": u, "title": after}
        if dispatched:
            return {"ok": True, "verified": None, "url": u, "title": after,
                    "completion_status": "opened_url_unconfirmed_foreground"}
        return {"ok": False, "verified": False, "url": u, "title": after}

    def _type(self, text: str, win: str) -> dict:
        try:
            if win:
                self.tools._focus_window_chen(win)
                time.sleep(0.5)  # dejar que la app quede LISTA para recibir teclas
                                  # (notepad recién enfocado se comía los 1ros chars)
            args = {"action": "type_into", "text": text, "window": win}
            # Discord/Electron text inputs are more reliable through SendKeys and
            # this avoids touching the user's clipboard during in-app messaging.
            if _fold_label(win) == "discord":
                args["method"] = "sendkeys"
            r = self.tools.execute("gui", args)
            return {"ok": bool(r.get("ok")), "verified": r.get("verified") is True, "text": text}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _send(self, win: str) -> dict:
        return self._keypress("enter", win)

    def _keypress(self, keys: str, win: str) -> dict:
        try:
            if win:
                self.tools._focus_window_chen(win)
                time.sleep(0.2)
            r = self.tools.execute("gui", {"action": "keypress", "keys": keys, "window": win})
            return {"ok": bool(r.get("ok")), "verified": r.get("verified") is True, "keys": keys}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _click(self, label: str, win: str) -> dict:
        try:
            r = self.tools.execute("gui", {"action": "click_button", "label": label, "window": win})
            inner = r.get("result", r) if isinstance(r, dict) else {}
            verified = inner.get("verified")
            if verified is None and inner.get("state_changed") is not None:
                verified = bool(inner.get("state_changed"))
            if verified is None:
                verified = False
            return {"ok": bool(inner.get("ok")), "verified": bool(verified),
                    "label": label, "grounding": inner.get("grounding"),
                    "state_changed": inner.get("state_changed"),
                    "completion_status": inner.get("completion_status")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def _split_field_value(spec: str) -> tuple[str, str] | None:
        raw = (spec or "").strip()
        if not raw:
            return None
        for sep in ("=>", "->", "::", "=", "|", ":"):
            if sep in raw:
                left, right = raw.split(sep, 1)
                field, value = left.strip(), right.strip()
                if field and value:
                    return field, value
        return None

    def _fill_field(self, spec: str, win: str) -> dict:
        parsed = self._split_field_value(spec)
        if parsed is None:
            return {
                "ok": False,
                "verified": False,
                "error": "fill_field requires arg formatted as field=value",
                "arg": spec,
            }
        field, value = parsed

        # 1) UIA ValuePattern first: structured, no coordinates, works across
        # native/WinUI/Office-style controls when the field exposes a value.
        try:
            r = self.tools.execute("uia", {
                "action": "set_value",
                "query": field,
                "value": value,
                "window": win,
            })
            if isinstance(r, dict) and r.get("ok"):
                return {
                    "ok": True,
                    "verified": r.get("verified") is True,
                    "field": field,
                    "value_chars": len(value),
                    "method": r.get("method") or "uia_set_value",
                    "element": r.get("element"),
                }
            if isinstance(r, dict) and (
                r.get("completion_status") == "needs_secret_handoff"
                or r.get("status") == "needs_secret_handoff"
            ):
                return {
                    "ok": False,
                    "verified": False,
                    "field": field,
                    "value_chars": len(value),
                    "completion_status": "needs_secret_handoff",
                    "error": r.get("error") or "secret_field_requires_user_handoff",
                    "method": r.get("method") or "uia_set_value",
                }
        except Exception:
            pass

        # 2) Generic fallback: click/focus field label, then type_into with OS/UIA
        # verification. This covers custom controls and webviews better than raw
        # key injection, while still avoiding blind coordinates when possible.
        clicked = self._click(field, win)
        if not clicked.get("ok") or clicked.get("verified") is not True:
            return {
                "ok": False,
                "verified": False,
                "field": field,
                "error": clicked.get("error") or "field_not_verified",
                "click": clicked,
            }
        try:
            typed = self.tools.execute("gui", {
                "action": "type_into",
                "text": value,
                "window": win,
            })
        except Exception as exc:
            typed = {"ok": False, "error": str(exc)}
        return {
            "ok": bool(typed.get("ok")),
            "verified": typed.get("verified") is True,
            "field": field,
            "value_chars": len(value),
            "method": "click_then_type_into",
            "click": clicked,
            "type": typed,
        }

    @staticmethod
    def _parse_toggle_spec(spec: str) -> tuple[str, bool | None]:
        parsed = PlanExecutor._split_field_value(spec)
        if parsed is None:
            return (spec or "").strip(), None
        label, raw = parsed
        val = raw.strip().casefold()
        if val in {"on", "true", "1", "yes", "checked"}:
            return label, True
        if val in {"off", "false", "0", "no", "unchecked"}:
            return label, False
        return label, None

    @staticmethod
    def _toggle_state_to_bool(state: object) -> bool | None:
        s = str(state or "").strip().casefold()
        if s == "on":
            return True
        if s == "off":
            return False
        return None

    def _toggle(self, spec: str, win: str) -> dict:
        label, desired = self._parse_toggle_spec(spec)
        if not label:
            return {"ok": False, "verified": False, "error": "toggle requires label or label=on/off"}

        def _read() -> dict:
            try:
                r = self.tools.execute("uia", {
                    "action": "find",
                    "query": label,
                    "window": win,
                    "limit": 8,
                    "timeout_sec": 8,
                })
                if not isinstance(r, dict) or not r.get("ok"):
                    return {"ok": False, "source": r}
                matches = r.get("matches") or []
                for el in matches:
                    if not isinstance(el, dict):
                        continue
                    patterns = {str(p) for p in (el.get("patterns") or [])}
                    if "Toggle" in patterns:
                        return {"ok": True, "element": el,
                                "state": self._toggle_state_to_bool(el.get("toggle_state"))}
                first = matches[0] if matches else None
                return {"ok": bool(first), "element": first, "state": None}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        before = _read()
        if not before.get("ok"):
            return {"ok": False, "verified": False, "label": label,
                    "error": "toggle_control_not_found", "status_before": before}
        if desired is not None and before.get("state") is desired:
            return {"ok": True, "verified": True, "already": True,
                    "label": label, "desired": desired, "status_before": before}
        clicked = self._click(label, win)
        if not clicked.get("ok"):
            return {"ok": False, "verified": False, "label": label,
                    "desired": desired, "click": clicked}
        time.sleep(0.4)
        after = _read()
        verified = False
        if desired is not None:
            verified = after.get("state") is desired
        elif before.get("state") is not None and after.get("state") is not None:
            verified = after.get("state") is not before.get("state")
        else:
            verified = clicked.get("verified") is True
        return {
            "ok": bool(verified),
            "verified": bool(verified),
            "label": label,
            "desired": desired,
            "method": "uia_toggle_then_verify",
            "status_before": before,
            "status_after": after,
            "click": clicked,
        }

    def _wait_for(self, target: str, win: str) -> dict:
        label = (target or "").strip()
        if not label:
            return {"ok": False, "verified": False, "error": "wait_for requires target text"}
        deadline = time.monotonic() + 12.0
        last: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            try:
                r = self.tools.execute("uia", {
                    "action": "find",
                    "query": label,
                    "window": win,
                    "limit": 5,
                    "timeout_sec": 6,
                })
                last = r if isinstance(r, dict) else {"ok": False}
                if isinstance(r, dict) and r.get("ok") and int(r.get("count") or 0) > 0:
                    return {
                        "ok": True,
                        "verified": True,
                        "target": label,
                        "method": "uia_find",
                        "matches": r.get("matches"),
                    }
            except Exception:
                pass
            try:
                ocr = self.tools.execute("gui", {
                    "action": "locate_text",
                    "target": label,
                    "min_conf": 35,
                })
                last = ocr if isinstance(ocr, dict) else last
                if isinstance(ocr, dict) and ocr.get("found"):
                    return {
                        "ok": True,
                        "verified": True,
                        "target": label,
                        "method": "ocr_locate_text",
                        "matches": ocr.get("matches"),
                    }
            except Exception:
                pass
            time.sleep(0.5)
        return {
            "ok": False,
            "verified": False,
            "target": label,
            "error": "target_not_found_before_timeout",
            "last": last,
        }

    def _scroll(self, amount: str, win: str) -> dict:
        try:
            if win:
                self.tools._focus_window_chen(win)
                time.sleep(0.2)
            try:
                n = int(float(str(amount or "-5").strip()))
            except Exception:
                n = -5
            r = self.tools.execute("gui", {"action": "scroll", "amount": n, "window": win})
            return {"ok": bool(r.get("ok")), "verified": r.get("verified") is True, "amount": n}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _wait(self, seconds: str) -> dict:
        try:
            s = float(str(seconds or "1").strip())
        except Exception:
            s = 1.0
        s = max(0.1, min(10.0, s))
        time.sleep(s)
        return {"ok": True, "seconds": s, "verified": True}

    @staticmethod
    def _bounds(el: dict) -> dict:
        b = el.get("bounds") if isinstance(el, dict) else {}
        return b if isinstance(b, dict) else {}

    @classmethod
    def _center(cls, el: dict) -> tuple[int, int] | None:
        point = el.get("clickable_point") if isinstance(el, dict) else None
        if isinstance(point, dict) and point.get("x") is not None and point.get("y") is not None:
            try:
                return int(point["x"]), int(point["y"])
            except Exception:
                return None
        b = cls._bounds(el)
        try:
            x = int(float(b.get("x", 0)) + float(b.get("width", 0)) / 2)
            y = int(float(b.get("y", 0)) + float(b.get("height", 0)) / 2)
        except Exception:
            return None
        return (x, y) if x and y else None

    @classmethod
    def _discord_voice_candidates(cls, elements: list[dict], root: dict) -> list[dict]:
        """Seleccion estructural, no linguistica: controles clickeables/toggle en
        el panel inferior izquierdo de Discord. Se basa en rol/patron/bounds UIA,
        no en Name/localizacion de texto."""
        rb = cls._bounds(root)
        try:
            rx = float(rb.get("x", 0)); ry = float(rb.get("y", 0))
            rw = max(1.0, float(rb.get("width", 0))); rh = max(1.0, float(rb.get("height", 0)))
        except Exception:
            rx = ry = 0.0; rw = rh = 1.0
        out: list[dict] = []
        clickable_types = {"Button", "CheckBox", "MenuItem"}
        for el in elements:
            if not isinstance(el, dict):
                continue
            if not bool(el.get("enabled", True)) or bool(el.get("offscreen", False)):
                continue
            b = cls._bounds(el)
            try:
                x = float(b.get("x", 0)); y = float(b.get("y", 0))
                w = float(b.get("width", 0)); h = float(b.get("height", 0))
            except Exception:
                continue
            if w < 8 or h < 8:
                continue
            cx = x + w / 2; cy = y + h / 2
            in_bottom = cy >= ry + rh * 0.55
            in_left_panel = rx + rw * 0.04 <= cx <= rx + rw * 0.42
            compact_control = w <= max(96.0, rw * 0.12) and h <= max(96.0, rh * 0.12)
            patterns = {str(p) for p in (el.get("patterns") or [])}
            ctype = str(el.get("control_type") or "")
            if in_bottom and in_left_panel and compact_control and (ctype in clickable_types or patterns):
                out.append(el)
        out.sort(key=lambda e: (
            float(cls._bounds(e).get("y", 0)),
            float(cls._bounds(e).get("x", 0)),
        ))
        return out

    @staticmethod
    def _toggle_state(el: dict | None) -> bool | None:
        if not isinstance(el, dict):
            return None
        if "Toggle" not in {str(p) for p in (el.get("patterns") or [])}:
            return None
        state = str(el.get("toggle_state") or "").strip().casefold()
        if state == "on":
            return True
        if state == "off":
            return False
        return None

    def _click_element(self, el: dict | None, win: str) -> dict:
        point = self._center(el or {})
        if point is None:
            return {"ok": False, "error": "element_has_no_clickable_point"}
        try:
            if win:
                self.tools._focus_window_chen(win)
                time.sleep(0.2)
            r = self.tools.execute("gui", {"action": "click", "x": point[0], "y": point[1], "window": win})
            return {"ok": bool(r.get("ok")), "point": {"x": point[0], "y": point[1]}}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _discord_uia_tree(self, win: str) -> dict:
        """Read Discord's UIA tree with retries for Chromium/Electron's lazy AX
        tree. If Discord was already running without accessibility enabled, this
        may still only expose the legacy chrome wrapper; callers must treat that
        as degraded grounding, not as success."""
        last: dict[str, Any] = {}
        for attempt in range(4):
            try:
                r = self.tools.execute("uia", {
                    "action": "tree",
                    "window": win or "Discord",
                    "limit": 200,
                    "timeout_sec": 8,
                })
            except Exception as exc:
                last = {"ok": False, "error": str(exc)}
                r = last
            if isinstance(r, dict) and r.get("ok"):
                elements = r.get("elements") or []
                root = r.get("root") if isinstance(r.get("root"), dict) else {}
                candidates = self._discord_voice_candidates(elements, root)
                if candidates or len(elements) > 2:
                    return r
                last = r
            elif isinstance(r, dict):
                last = r
            if attempt < 3:
                time.sleep(0.35 + attempt * 0.2)
        return last

    def _discord_voice_status(self, win: str) -> dict:
        r = self._discord_uia_tree(win)
        if not isinstance(r, dict) or not r.get("ok"):
            return {"ok": False, "error": (r or {}).get("error") if isinstance(r, dict) else "uia_failed"}
        elements = r.get("elements") or []
        root = r.get("root") if isinstance(r.get("root"), dict) else {}
        candidates = self._discord_voice_candidates(elements, root)
        uia_degraded = not candidates and len(elements) <= 2

        def _cx(el: dict) -> float:
            b = self._bounds(el)
            return float(b.get("x", 0)) + float(b.get("width", 0)) / 2.0

        def _cy(el: dict) -> float:
            b = self._bounds(el)
            return float(b.get("y", 0)) + float(b.get("height", 0)) / 2.0

        rb = self._bounds(root)
        try:
            row_tol = max(18.0, float(rb.get("height", 0)) * 0.025)
        except Exception:
            row_tol = 24.0

        toggles = [el for el in candidates if "Toggle" in {str(p) for p in (el.get("patterns") or [])}]
        bottom_toggle_y = max((_cy(el) for el in toggles), default=None)
        user_row_toggles: list[dict] = []
        if bottom_toggle_y is not None:
            user_row_toggles = [el for el in toggles if abs(_cy(el) - bottom_toggle_y) <= row_tol]
            if len(user_row_toggles) < 2:
                user_row_toggles = sorted(toggles, key=lambda el: (_cy(el), _cx(el)))[-2:]
            user_row_toggles.sort(key=_cx)

        mic_control = user_row_toggles[0] if len(user_row_toggles) >= 1 else None
        deafen_control = user_row_toggles[1] if len(user_row_toggles) >= 2 else None
        disconnect_control = None
        if bottom_toggle_y is not None:
            upper_controls = []
            for el in candidates:
                patterns = {str(p) for p in (el.get("patterns") or [])}
                if el in user_row_toggles or "Toggle" in patterns:
                    continue
                # Avoid treating the user-settings button beside mic/deafen as a
                # voice disconnect button. A disconnect control must live in the
                # voice panel above the bottom user-controls row.
                if _cy(el) >= bottom_toggle_y - row_tol:
                    continue
                if "Invoke" not in patterns and str(el.get("control_type") or "") not in {"Button", "MenuItem"}:
                    continue
                upper_controls.append(el)
            if upper_controls:
                closest_row_y = max(_cy(el) for el in upper_controls)
                closest_row = [el for el in upper_controls if abs(_cy(el) - closest_row_y) <= row_tol]
                disconnect_control = max(closest_row, key=_cx)
        status: dict[str, Any] = {
            "ok": True,
            "mic_muted": self._toggle_state(mic_control),
            "mic_control": mic_control,
            "deafened": self._toggle_state(deafen_control),
            "deafen_control": deafen_control,
            "disconnect_control": disconnect_control,
            "voice_connected": bool(disconnect_control),
            "uia_degraded": uia_degraded,
            "element_count": len(elements),
            "names": [str(el.get("name") or "") for el in elements[:80] if isinstance(el, dict)],
        }
        return status

    def _discord_shortcut_attempt(self, keys: str, win: str, before: dict,
                                  action: str, desired_key: str | None = None,
                                  desired_value: bool | None = None) -> dict:
        detail = self._keypress(keys, win)
        time.sleep(0.8)
        after = self._discord_voice_status(win)
        verified = (
            desired_key is not None
            and desired_value is not None
            and after.get(desired_key) is desired_value
        )
        return {
            "ok": verified or bool(detail.get("ok")),
            "verified": verified,
            "action": action,
            "method": "shortcut",
            "detail": detail,
            "status_before": before,
            "status_after": after,
            "degraded": not verified,
            "error": None if verified else "state_unknown_or_unverified_after_shortcut",
        }

    def _discord_control(self, action: str, win: str) -> dict:
        act = _canonical_discord_control(action)
        if act not in {
            "mute", "unmute", "toggle_mute", "deafen", "undeafen",
            "toggle_deafen", "disconnect_voice",
        }:
            return {"ok": False, "action": action, "error": "unknown_discord_control"}
        win = win or "Discord"
        try:
            self.tools._focus_window_chen(win)
            time.sleep(0.4)
        except Exception:
            pass
        before = self._discord_voice_status(win)
        if act in {"mute", "unmute"}:
            desired = act == "mute"
            current = before.get("mic_muted")
            if current is desired:
                return {"ok": True, "verified": True, "already": True,
                        "action": act, "status_before": before}
            if current is None:
                return self._discord_shortcut_attempt(
                    "ctrl+shift+m", win, before, act, "mic_muted", desired)
            detail = self._keypress("ctrl+shift+m", win)
            time.sleep(0.8)
            after = self._discord_voice_status(win)
            verified = after.get("mic_muted") is desired
            return {"ok": verified, "verified": verified, "action": act,
                    "method": "shortcut", "detail": detail,
                    "status_before": before, "status_after": after}
        if act == "toggle_mute":
            current = before.get("mic_muted")
            if current is None:
                return self._discord_shortcut_attempt("ctrl+shift+m", win, before, act)
            pressed = self._keypress("ctrl+shift+m", win)
            time.sleep(0.8)
            after = self._discord_voice_status(win)
            verified = after.get("mic_muted") is not current
            return {"ok": verified, "verified": verified,
                    "action": act, "method": "shortcut", "detail": pressed,
                    "status_before": before, "status_after": after}
        if act in {"deafen", "undeafen"}:
            desired = act == "deafen"
            current = before.get("deafened")
            if current is desired:
                return {"ok": True, "verified": True, "already": True,
                        "action": act, "status_before": before}
            if current is None:
                return self._discord_shortcut_attempt(
                    "ctrl+shift+d", win, before, act, "deafened", desired)
            detail = self._keypress("ctrl+shift+d", win)
            time.sleep(0.8)
            after = self._discord_voice_status(win)
            verified = after.get("deafened") is desired
            return {"ok": verified, "verified": verified, "action": act,
                    "method": "shortcut", "detail": detail,
                    "status_before": before, "status_after": after}
        if act == "toggle_deafen":
            current = before.get("deafened")
            if current is None:
                return self._discord_shortcut_attempt("ctrl+shift+d", win, before, act)
            pressed = self._keypress("ctrl+shift+d", win)
            time.sleep(0.8)
            after = self._discord_voice_status(win)
            verified = after.get("deafened") is not current
            return {"ok": verified, "verified": verified,
                    "action": act, "method": "shortcut", "detail": pressed,
                    "status_before": before, "status_after": after}
        control = before.get("disconnect_control")
        if not control:
            return {"ok": False, "verified": False, "action": act,
                    "status_before": before, "error": "disconnect_control_not_found"}
        clicked = self._click_element(control, win)
        time.sleep(0.8)
        after = self._discord_voice_status(win)
        verified = not bool(after.get("voice_connected"))
        return {"ok": verified, "verified": verified,
                "action": act, "method": "uia_point", "detail": clicked,
                "status_before": before, "status_after": after}

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
            include_uia = op in {"click", "fill_field", "toggle", "wait_for", "discord_control"}
            before_caps = self.detector.snapshot(app_token, include_uia=include_uia)
            layer_policy = self.choose_policy(before_caps, op).to_dict()
            capability_family = self.capability_family(before_caps)
            if layer_policy.get("primary") == "honest_fail":
                res = {
                    "ok": False,
                    "verified": False,
                    "error": "no_available_structural_or_visual_layer",
                    "completion_status": "needs_capability",
                    "method": "capability_policy",
                }
                steps_out.append({
                    "op": op,
                    "arg": arg,
                    "capabilities_before": before_caps,
                    "capabilities_after": before_caps,
                    "capability_policy": layer_policy,
                    "capability_family": capability_family,
                    **res,
                })
                return {"ok": False, "steps": steps_out, "focused_app": app_token,
                        "failed_at": op}
            # REINTENTO ACOTADO POR PASO (universal, 2026-05-27). Antes un solo
            # fallo TRANSITORIO de un paso hard-fail (ventana sin foco aún, página
            # cargando) abortaba la cadena ENTERA. La literatura (Plan-and-Act) y
            # la medición lo confirman: la fragilidad por-paso es el techo de las
            # cadenas largas. Reintentamos un paso hard-fail/verificado hasta
            # _STEP_RETRIES veces, re-tomando el snapshot y re-enfocando entre
            # intentos, ANTES de rendirnos. Universal: no sabe de "tiendas" ni de
            # casos de uso — reintenta CUALQUIER primitiva frágil. Pasos best-
            # effort (type/send/keypress/scroll/wait) NO se reintentan (no son
            # hard-fail; su fallo no corta la cadena).
            _is_critical = (self.capabilities.is_hard_fail(op)
                            or self.capabilities.is_verified_step(op))
            res, app_token = self.capabilities.run(
                op, arg, app_token, snapshot=before_caps, policy=layer_policy,
            )
            _attempts = 1
            while (_is_critical and _attempts <= _STEP_RETRIES
                   and (not res.get("ok") or res.get("verified") is False)):
                try:
                    self.ag.trace.event(turn_id, "cu_step_retry", op=op,
                                        attempt=_attempts, prev_ok=res.get("ok"))
                except Exception:
                    pass
                time.sleep(0.4 + 0.3 * _attempts)  # backoff: dar tiempo a la UI
                # re-enfocar la app del contexto (un paso suele fallar porque la
                # ventana perdió foco entre pasos) y re-tomar el snapshot.
                if app_token:
                    try:
                        self.tools._focus_window_chen(app_token)
                        time.sleep(0.2)
                    except Exception:
                        pass
                before_caps = self.detector.snapshot(app_token, include_uia=include_uia)
                layer_policy = self.choose_policy(before_caps, op).to_dict()
                res, app_token = self.capabilities.run(
                    op, arg, app_token, snapshot=before_caps, policy=layer_policy,
                )
                _attempts += 1
            if _attempts > 1:
                res = {**res, "retries": _attempts - 1}
            # routed through internal capability router
            # app_token is updated by the owning capability
            after_caps = self.detector.snapshot(app_token, include_uia=False)
            steps_out.append({
                "op": op,
                "arg": arg,
                "capabilities_before": before_caps,
                "capabilities_after": after_caps,
                "capability_policy": layer_policy,
                "capability_family": capability_family,
                **res,
            })
            try:
                self.ag.trace.event(turn_id, "cu_step", op=op, arg=str(arg)[:40],
                                    ok=res.get("ok"), app=app_token[:30],
                                    app_kind=after_caps.get("app_kind"),
                                    method=res.get("method"),
                                    policy=layer_policy.get("primary"),
                                    family=capability_family,
                                    risk=layer_policy.get("risk"))
            except Exception:
                pass
            hard_failed = self.capabilities.is_hard_fail(op) and not res.get("ok")
            unverified_hard_step = (
                self.capabilities.is_hard_fail(op)
                and self.capabilities.is_verified_step(op)
                and res.get("verified") is False
            )
            if hard_failed or unverified_hard_step:
                return {"ok": False, "steps": steps_out, "focused_app": app_token,
                        "failed_at": op}
            time.sleep(0.2)
        verified_steps = [
            s for s in steps_out
            if self.capabilities.is_verified_step(str(s.get("op") or ""))
        ]
        verified = bool(verified_steps) and all(s.get("verified") is True for s in verified_steps)
        return {"ok": True, "verified": verified, "steps": steps_out, "focused_app": app_token}
