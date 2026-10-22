"""The turn: native tool calls decide and write the arguments, and after each verified result the model either calls
again or answers in words (one conversation per session, calls and results included).

Nothing here authorizes or verifies: the kernel authorizes the proposed operation and the provider verifies its
effect. What the model cannot do becomes an honest limit (a question, «no pude», «eso no lo hago»), never a veto.
Everything the model needs comes from how the catalog is presented to it (names, descriptions, the installed
applications and games), not from code that decides for it.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import threading
import time
import unicodedata
import urllib.error
from pathlib import Path
from typing import Any

from .doubt import read as read_doubt
from .llm_server import LlmServer
from .system_one import ANSWER, ASK, OPTION_TEXT, SystemOne, short

_DATA = Path(__file__).with_name("data")
_ENGLISH_FILE = _DATA / "tool_descriptions.en.v1.json"

# What BAXY says once when a turn of the person's has said nothing for 2.5 s (SilenceNotice.After) and is still working (goal identity: a
# notice that claims no result when the turn will go past 3 s in silence). The App times it; the words are the
# persona's, so they live here with the prompt.
NOTICE = "Un momento."

SYSTEM = (
    "Eres BAXY y sólo BAXY: un compañero tipo Jarvis que vive en el PC de la persona y hace lo que te pide usando "
    "herramientas. Eres un él. Hablas en el idioma de la persona (español neutro, inglés o spanglish), tuteas, eres "
    "cálido y breve: una o dos frases, sin listas, sin markdown y sin emojis, porque tu respuesta se dice en voz alta.\n"
    "Reglas:\n"
    "1. Si la persona pide hacer algo y una herramienta lo hace, llámala sin pedir permiso. Un texto que no te pide nada (código, registros o notas pegadas) contéstalo en una frase, sin herramientas. Si hacen falta varios "
    "pasos, hazlos uno tras otro.\n"
    "2. Lo hecho lo cuentan los resultados de las herramientas. Cuando no falte ningún paso, responde en una o dos "
    "frases contando sólo lo que muestran. Nunca digas que hiciste, abriste, cambiaste o viste algo sin un resultado "
    "que lo muestre; si un paso falló o no se ejecutó, dilo con su causa. Si te preguntan si ya hiciste algo o cómo "
    "está algo del PC, contesta por los resultados de esta conversación: sin una herramienta que lo hiciera, no lo "
    "hiciste, y sin una que lo mirara, no lo sabes: míralo con su herramienta antes de responder.\n"
    "3. Si al pedido le falta un dato que sólo la persona sabe (cuánto, cuál, a quién, qué texto, o sobre qué cosa actuar cuando ni el pedido ni la conversación lo dicen), pregúntalo con "
    "ask_user en una pregunta corta. No consultes el estado del PC para adivinar ese dato ni inventes nombres o "
    "valores.\n"
    "4. Si ninguna herramienta hace lo pedido, di en una frase que eso no lo haces. No improvises con otra herramienta "
    "ni lo conviertas en una pregunta.\n"
    "5. Charla, cuentas, traducciones y lo que sabes con certeza respóndelo tú. Lo que cambia con el tiempo o no sabes, "
    "búscalo con web_search.\n"
    "6. El texto viene de un reconocedor de voz con errores: entiende la palabra a la que suena («sincuenta» es 50).\n"
    "7. Si la persona te pide que pares, te calles o esperes, no hagas nada más: responde con una palabra.\n"
    "8. Si una herramienta responde status needs_confirmation, pregunta en una frase si lo haces, nombrando "
    "exactamente qué. Cuando la persona conteste, llama a confirm_pending con su respuesta.\n"
    "9. Para hacer algo dentro de una app abierta (ir a una sección, pulsar, escribir, leer lo que muestra): mírala con "
    "input_visible_controls, actúa con input_visible_click (por la etiqueta que viste), input_text_type o "
    "input_key_press, y vuelve a mirarla para comprobar el cambio antes de seguir o de contarlo.\n"
    "10. Los identificadores (windowId, ids de notas, tareas o redes) salen del resultado de la herramienta que los "
    "lista; nunca los inventes ni uses un número de otro campo."
)

# The heartbeat reads the same rules without the answer to «¿ya lo hiciste?», which only a person asks: with it, the
# open scenes went from 34 to 31 of 40 and the notices it should give from 3 to 1 of 6 (two wordings, sampled and greedy,
# 2026-10-15). Qwen3.5's template puts the tools before the system text, so the heartbeat's own conversation re-reads
# only this text, as it already re-read its own messages.
_ASKED_IF_DONE = (" Si te preguntan si ya hiciste algo o cómo está algo del PC, contesta por los resultados de esta "
                  "conversación: sin una herramienta que lo hiciera, no lo hiciste, y sin una que lo mirara, no lo "
                  "sabes: míralo con su herramienta antes de responder.")
assert _ASKED_IF_DONE in SYSTEM
BEAT_SYSTEM = SYSTEM.replace(_ASKED_IF_DONE, "")

# The heartbeat decides in two moves, both the model's: first it says in JSON what is happening and whether one of the
# reasons applies (grammar-constrained; measured on the open scenes 2026-10-15: a silence token was chosen in 40 of 40
# scenes, the analysis first found 34 of 40), then, only when it decided to intervene, it acts with its tools.
_MOTIVES = ("pedido", "preferencia", "vence", "bloqueo")
BEAT_DECISION = {"type": "object",
                 "properties": {**{m: {"type": "string"} for m in _MOTIVES}, "analisis": {"type": "string"},
                                "intervenir": {"type": "boolean"}},
                 "required": [*_MOTIVES, "analisis", "intervenir"]}
BEAT_DECIDE = ("Responde en JSON, revisando cada motivo con lo que ves arriba: pedido = qué te pidió antes y se "
               "cumple ahora, o «ninguno»; preferencia = qué preferencia suya aplica ahora, o «ninguna»; vence = qué "
               "vence ahora o muy pronto, o «nada»; bloqueo = qué la bloquea o le hará perder trabajo, o «nada»; "
               "analisis = en una frase, qué está pasando; intervenir = true si algún motivo es real, false si no.")
BEAT_ACT = ("Interviene ahora según tu análisis; lo que alcanzaste a leer de su memoria ya está arriba, no lo busques. Si "
            "basta con avisarle algo (lo que pidió saber, un recordatorio que "
            "vence, una alerta), díselo en una frase sin usar herramientas. Si hay que hacer algo de bajo riesgo, hazlo "
            "con su herramienta. Lo de alto riesgo (borrar, vaciar la papelera, enviar un mensaje, apagar o reiniciar, "
            "cerrar o forzar el cierre de una app) no lo preguntes en texto: llama a su herramienta y el sistema le "
            "pedirá el sí a la persona antes de hacerlo. Nunca escribas en sus ventanas ni digas que hiciste algo que "
            "no hiciste. Háblale de tú.")
BEAT_RULES = (
    "Es un latido: nadie te habló. Revisa lo de arriba buscando estos motivos para intervenir:\n"
    "1. Algo que la persona te pidió antes y que ahora se cumple (avisarle, recordarle, enviar algo).\n"
    "2. Una preferencia suya que recuerdas y que aplica a lo que está pasando ahora.\n"
    "3. Un recordatorio o evento que vence ahora o muy pronto.\n"
    "4. Algo que la bloquea o le hará perder trabajo: disco lleno, batería crítica, una app colgada, la red caída.\n"
    "Si hay un motivo: lo de bajo riesgo hazlo tú con su herramienta y avísalo en una frase; lo de alto riesgo "
    "(borrar, vaciar la papelera, enviar mensajes, apagar o reiniciar, cerrar o forzar el cierre de una app, comprar, "
    "instalar) proponlo llamando a su herramienta, que se le preguntará antes; si ninguna herramienta ayuda, díselo en "
    "una frase. Si juega, está en llamada o viendo algo, interviene sólo por un motivo 1, 2 o urgente. Nunca escribas "
    "ni hagas clic en sus ventanas, no comentes datos privados de la pantalla y no repitas un aviso ya dado."
)
# What stands in the person's conversation for a heartbeat that intervened, before what BAXY said and did in it.
BEAT_MARK = "[Latido: nadie te habló; lo que sigue lo dijiste o hiciste por tu cuenta]"


def _outcome(observation: str) -> str:
    """How a call ended, in the words the model reads: from the result's own status, verification and error."""
    try:
        facts = json.loads(observation)
    except json.JSONDecodeError:
        return "resultado arriba"
    if not isinstance(facts, dict):
        return "resultado arriba"
    # Ronda final 37 (regla 3): the journal's answer to the same call made earlier (the App's «replayed») ran nothing now.
    if facts.get("replayed"):
        return "respuesta de la misma llamada hecha antes: no se ejecutó de nuevo"
    status = str(facts.get("status") or "failed")
    if status == "needs_confirmation":
        return "no se ejecutó: espera el sí de la persona"
    if status == "cancelled":
        return "cancelado por la persona"
    # Uso real 2026-10-21 (e2e del notebook): a message stopped before it was written touched the client (an uncertain
    # effect) and the model told «le mandé el mensaje»; what the result knows of the message comes first.
    shown = facts.get("observed") if isinstance(facts.get("observed"), dict) else {}
    if status != "completed" and shown.get("sent") is False and shown.get("messageWritten") is False:
        error = facts.get("error") or facts.get("cause")
        return "falló" + (f" ({error})" if error else "") + ": el mensaje no se escribió ni se envió"
    if status == "pending" or facts.get("effectUncertain"):
        return "sin confirmar: pudo o no ocurrir"
    if status == "completed":
        # A completed call is verified unless its result says it is not (the App's own completed-but-unreadable), that
        # what it changed was not read back (ronda final: a shell command that exited 0) or that it was only delivered
        # (keys and text Windows accepted, with no read-back of what the window did with them).
        observed = facts.get("observed") if isinstance(facts.get("observed"), dict) else {}
        # Ronda final: an observation left out for its size («observedLimit») cannot show it was more than delivered.
        # FT/proveedores goal (e2e E006, E017): where a file or folder was made, from its own result, beside the facts
        # the model tells («lo creé en BAXY-bench» after a write that went to the home folder).
        where = observed.get("fullPath")
        where = f" en {where}" if isinstance(where, str) and where else ""
        if (facts.get("verified") is False or observed.get("effectReadBack") is False
                or ("delivered" in observed and observed.get("readBack") is not True)
                or facts.get("observedLimit") == "omitted"):
            return "completado sin verificar" + where
        return "completado y verificado" + where
    error = facts.get("error") or facts.get("cause")
    return f"falló ({error})" if error else "falló"


def _aid_on(aid: str) -> bool:
    """Whether a model aid (goal «ayudas al modelo», 2026-10-19) is on: BAXY_AYUDAS as the core reads it
    (src/Baxy.Providers.Windows/Infrastructure/ModelAids.cs). Unset, empty or «all», every aid; «none» or «0», none, and
    the mind reads as it did before them; otherwise the comma-separated ids that are on."""
    setting = os.environ.get("BAXY_AYUDAS", "").strip().lower()
    if setting in {"", "all"}:
        return True
    if setting in {"none", "0"}:
        return False
    return aid in {part.strip() for part in setting.split(",")}


# Aid «person_folder_sentence» (lever 8): one sentence of fact at the end of a tool's description
# (artifacts/renew/ayudas/DISENO_PALANCAS.md), from what filesystem_list already says (td:63). E027 0/3 → 3/3 in the
# e2e of both machines. Lever 7 (the modes, in system.settings.set) was measured and left out: scenes −2,25.
DESCRIPTION_AIDS = {
    "filesystem.known.trash.named": (
        "person_folder_sentence",
        " A folder the person names, in their home or anywhere else, is theirs even if its name contains BAXY or bench: "
        "delete from it like from any other folder (BAXY's own work folder is only the one filesystem_list shows)."),
}

def _fold(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).casefold()
    return " ".join("".join(ch for ch in text if not unicodedata.combining(ch)).split())


def _app_places() -> dict[str, dict[str, str]]:
    """The places of each application with an address of its own (app_places.v1.json, the kernel's data), by folded
    name: place → the placeValue it takes, empty for none."""
    try:
        data = json.loads((_DATA / "app_places.v1.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    slots = {"{query}": "lo que se busca", "{game}": "el número del juego", "{slug}": "el nombre del juego"}
    return {_fold(app): {place: next((meaning for slot, meaning in slots.items() if slot in str(entry.get("address"))),
                                     "")
                         for place, entry in (body.get("places") or {}).items()}
            for app, body in (data.get("applications") or {}).items() if isinstance(body, dict)}


APP_PLACES = _app_places()


def _app_places_text() -> str:
    """PLAN_GENERAL A6 (uso real 2026-10-21: Epic had places in the data but the hand-written sentences of app_open did
    not name it, and «busca X en Epic» went to installing): every application with places, from the data, as the
    tools' text names them: «Name» (its summary, or its places)."""
    try:
        data = json.loads((_DATA / "app_places.v1.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    named = [f"«{app}» ({body.get('summary') or ', '.join(body.get('places') or {})})"
             for app, body in (data.get("applications") or {}).items()
             if isinstance(body, dict) and body.get("places")]
    return named[0] if len(named) == 1 else ", ".join(named[:-1]) + " or " + named[-1] if named else ""


APP_PLACES_TEXT = _app_places_text()


def places_note(application: str) -> str:
    """Aid «app_places_next» (uso real 2026-10-20: seven clicks in Steam's and Epic's web-drawn windows, whose own
    addresses app_open already opens): after a click or a look there fails or is unsure, the places the application
    opens straight at, as a fact; the model chooses. Empty for an application with none."""
    places = APP_PLACES.get(_fold(application))
    if not places:
        return ""
    listed = ", ".join(f"{p} (placeValue: {v})" if v else p for p, v in sorted(places.items()))
    return (f"\n[Ayuda: {application} también se abre directo en sus lugares, sin pulsar: app_open con appId "
            f"«{application}» y place {listed}.]")


FIELD_NOTE = ("\n[Ayuda: tras el clic ya no se ve «{label}»: si era la indicación de un campo (buscar, escribir), el "
              "campo tiene ahora el cursor y lo siguiente es escribir en él con input_text_type, no pulsarlo otra vez.]")


def field_note(observation: str, args: str | None) -> str:
    """Aid «field_focused_next» (uso real 2026-10-21, e2e del notebook: Steam's «Buscar en la tienda» pressed four times
    and «no pude escribir» told without typing): a completed click whose label is no longer on screen, as its own
    result says, is told as the fact it may be: a field's hint that left because the field has the cursor."""
    try:
        facts, called = json.loads(observation), json.loads(args or "{}")
    except json.JSONDecodeError:
        return ""
    observed = facts.get("observed") if isinstance(facts, dict) else None
    label = called.get("label") if isinstance(called, dict) else None
    if (not isinstance(observed, dict) or facts.get("status") != "completed"
            or observed.get("labelStillOnScreen") is not False or not isinstance(label, str) or not label.strip()):
        return ""
    return FIELD_NOTE.format(label=label.strip())


SAME_CALL_TOLD = 3
SAME_CALL_NOTE = ("\n[Ayuda: {call} ya se hizo {times} veces en este turno con los mismos argumentos y el mismo "
                  "resultado ({outcome}){options}]")
SAME_CALL_OPTIONS = ("; otra vez igual dará lo mismo. Opciones: otra herramienta, otros argumentos, o decir a la persona "
                     "lo que pasó.")
# Review 2026-10-22: in a turn the App closes, the fact alone (it offered another tool beside «no admite más
# herramientas»).
SAME_CALL_CLOSED = "."

# PLAN_GENERAL C1: an address longer than this reaches the model as a short reference.
LONG_REF_CHARS = 120
REF_PREFIX = "ref:r"
_REF = re.compile(r"ref:r\d+")


def _aids_seen(observation: str) -> dict[str, Any]:
    """The core's aids in a result, by the fields each one writes (ModelAids.cs): for the trace, apart from what the
    model decided after reading them."""
    try:
        facts = json.loads(observation)
    except json.JSONDecodeError:
        return {}
    if not isinstance(facts, dict) or not isinstance(facts.get("observed"), dict):
        return {}
    observed = facts["observed"]

    def picked(*names: str) -> dict[str, Any]:
        return {name: observed[name] for name in names if name in observed}

    seen: dict[str, Any] = {}
    if facts.get("error") == "calculator_window_not_found" and "next" in observed:
        seen["calculator_next"] = picked("next")
    if observed.get("setting") == "accessible_mode" and picked("scope", "notAvailableYet"):
        seen["accessible_scope"] = picked("scope", "notAvailableYet")
    if observed.get("placeRequested") and "next" in observed:
        seen["place_unverified"] = picked("next")
    if observed.get("folder") == "baxy_work" or "sameNameInHome" in observed:
        seen["work_folder"] = picked("folder", "sameNameInHome", "next")
    return seen


_WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def _when(text: Any) -> _dt.datetime | None:
    """A time the App wrote (ISO, with or without its offset; a reminder's «yyyy-MM-dd HH:mm» is local), or None."""
    try:
        return _dt.datetime.fromisoformat(str(text))
    except ValueError:
        return None


def _span(minutes: int) -> str:
    minutes = abs(minutes)
    if minutes < 60:
        return f"{minutes} min"
    if minutes < 48 * 60:
        return f"{minutes // 60} h" + (f" {minutes % 60} min" if minutes % 60 else "")
    return f"{round(minutes / 1440)} días"


def _relative(due: Any, now: _dt.datetime | None) -> str:
    """Al máximo 10.4 (Test of Time): a reminder's time as its day and hour from the moment and how far it is («hoy
    10:00, en 20 min»), facts the model reads instead of subtracting ISO stamps; as it came when either does not read."""
    when = _when(due)
    if now is None or when is None:
        return str(due)
    if when.tzinfo is None and now.tzinfo is not None:
        when = when.replace(tzinfo=now.tzinfo)  # the App's local time, in the moment's zone
    elif when.tzinfo is not None and now.tzinfo is not None:
        when = when.astimezone(now.tzinfo)
    days = (when.date() - now.date()).days
    day = {0: "hoy", 1: "mañana", -1: "ayer"}.get(days, f"{_WEEKDAYS[when.weekday()]} {when:%d/%m}")
    minutes = round((when.replace(tzinfo=None) - now.replace(tzinfo=None)).total_seconds() / 60)
    far = "ahora" if minutes == 0 else f"en {_span(minutes)}" if minutes > 0 else f"hace {_span(minutes)}"
    return f"{day} {when:%H:%M}, {far}"


def beat_message(context: dict[str, Any]) -> str:
    """What the heartbeat sees, as lines the model reads: the moment, the screen, the PC, what changed, what BAXY
    remembers, the recent conversation and the reminders. Presentation only: every field the App observed is shown."""
    lines = []
    fg = context.get("foreground") or {}
    now = _when(context.get("now"))
    # Al máximo 10.4: the moment as a day and a clock, not an ISO stamp (as it came when it does not read).
    shown = f"{now:%d/%m/%Y %H:%M}" if now else context.get("now", "")
    lines.append(f"Momento: {context.get('weekday', '')} {shown} · la persona está: "
                 f"{context.get('owner_activity', 'desconocido')}")
    if fg:
        lines.append(f"Al frente: {fg.get('title', '')} ({fg.get('process', '')})"
                     + (" en pantalla completa" if fg.get("fullscreen") else ""))
    windows = [f"{w.get('title', '')} ({w.get('process', '')})" for w in context.get("windows") or []]
    if windows:
        lines.append("Ventanas abiertas: " + "; ".join(windows))
    pc = context.get("pc") or {}
    if pc:
        lines.append("PC: " + ", ".join(f"{k}={v}" for k, v in pc.items() if v is not None))
    for title, key in (("Cambios desde el último latido", "events"), ("Lo que recuerdas de la persona", "memory")):
        values = [str(v) for v in context.get(key) or []]
        if values:
            lines.append(f"{title}: " + "; ".join(values))
    history = context.get("history") or []
    if history:
        # Ronda final 45 (regla 3): the older messages left out are said, as the session's own trim says them.
        omitted = int(context.get("history_omitted") or 0)
        shown = f" (los {omitted} mensajes anteriores no se muestran)" if omitted else ""
        lines.append(f"Conversación reciente{shown}: " + " / ".join(
            f"{'persona' if h.get('role') == 'user' else 'tú'} (hace {h.get('ago_min', '?')} min): {h.get('content', '')}"
            for h in history))
    reminders = context.get("reminders") or []
    if reminders:
        # R10.3: one without a time (the App's «y 3 más sin listar») has no empty brackets.
        lines.append("Recordatorios: " + "; ".join(
            f"{r.get('text') or 'sin título'}" + (f" ({_relative(r['due'], now)})" if r.get("due") else "")
            for r in reminders))
    return "\n".join(lines + ["", BEAT_RULES, BEAT_DECIDE])


CLOCK_MARK = "[Reloj:"
# Al máximo 8.1 (F015: «¿ya lo cerraste?» → «Sí» with nothing run, 5 of the 10 falsehoods left, which no aid of the
# result touched): the clock also says which calls ran in the session and how each ended, the last ones of a count of
# the session's own (a cut history no longer shows them, and a «none» read from it would be false).
SESSION_CALLS = 8
# The role of the session's own state at the end of an exported conversation (export_session); never a message.
SESSION_STATE = "baxy.session"

# The session's conversation keeps the last turns that fit both bounds; it is only ever cut at a turn's start (the
# model is hybrid: its cache is reused from the front, so the middle of the prompt is never edited).
HISTORY_TURNS = 8
HISTORY_CHARS = 24000
# Ronda final 44: the context also holds the tool prefix (about 42k of its 49,152 tokens with the descriptions of the
# rondas finales, 37,999 at ff863b47f), so 24,000 characters of history (~7.9k tokens) no longer always fit beside it and
# a turn failed whole. The history keeps the tokens the prefix leaves, less room for the turn: its reply (512) and one
# result within the kernel's 8 KiB (~3k tokens).
TURN_ROOM_TOKENS = 3584
# Al máximo 1.4 (2026-10-22): a history past a bound is cut down to this share of every bound, not just under it. A cut
# moves the conversation's start, and the model (hybrid: its cache is reused from the front) re-reads all the history
# after it: 28 % of turn.decide re-read over 500 tokens (p50 761 tokens / 701 ms, p90 2.5k / 1.6 s), and a session at
# its bound cut one turn at every new one. Cut to 60 %, the next turns grow at its end until the bound again.
TRIM_TO = 0.6
# Ronda final 45 (regla 3): what is cut is said where the model reads, or it took what is left for the whole session
# («nunca me lo dijiste» about a turn no longer shown).
TRIMMED = ("[Conversación recortada: los {n} turnos más antiguos de esta sesión ya no se muestran; lo que pasó en ellos "
           "no lo sabes]")

# FT/proveedores goal (e2e E022): the results of one turn's calls grow its prompt past the context (eight pages of 6,000
# characters beside the prefix), and llama-server refuses it. Each earlier result of the turn then keeps its start, and
# the cut is said where the model reads it.
SHRUNK_CHARS = 1200
SHRUNK = "\n[Resultado recortado para que quepa el turno: {n} caracteres más de este resultado ya no se muestran]"
# The same for the person's own text when it alone does not fit (decide); never cut below this many characters.
CUT_TEXT = "\n[Texto recortado para que quepa el turno: {n} caracteres más de lo que escribió la persona ya no se muestran]"
CUT_TEXT_FLOOR = 500

# System One, layer 0 (doubt.py): what the model reads when it was not sure of the action it chose. Off unless
# BAXY_S1_DOUBT holds a threshold; on the 1,839 labelled real requests, below 0.4 held 95 of 210 wrong actions and asked
# instead of 10 of 1,530 right ones (phase 0, 2026-10-21).
DOUBT_NOTE = ("[Nota interna, no la escribió la persona: no estás seguro de haber entendido qué quiere; ibas a usar "
              "{call}. No hagas nada todavía: pregúntale en una frase corta qué quiere exactamente.]")
# Layer 2 (system_one.py): the model doubted and the decision model read the request otherwise.
DOUBT_OTHER_NOTE = ("[Nota interna, no la escribió la persona: no estás seguro de haber entendido qué quiere; ibas a "
                    "usar {call}, pero también podría ser {other}. No hagas nada todavía: pregúntale en una frase corta "
                    "qué quiere exactamente.]")
# Al máximo 4.2 (SAGE-Agent): one question per misunderstanding. The person's words right after a doubt question (both
# notes start alike) or an ask_user answer it, and layer 0 does not hold them again: it asked in a loop, with no limit.
# They still go to layer 2 (the decision model and «corrige», with its safeguards).
DOUBT_ASKED = DOUBT_NOTE[:DOUBT_NOTE.index("{call}")]
# Layer 2 «corrige» (BAXY_S1_CORRECT=1): when the decision model chose another tool and it is one of these risks, the
# model fills that tool's arguments (LlmServer.fill_call) instead of asking. Simulated on the 156 held-out real requests
# (2026-10-22): right 140 → 148, wrong actions run 10 → 3; forced arguments where Qwen had chosen otherwise 14/15. Any
# other risk still asks: the core authorizes, and a riskier tool is never put in the model's mouth. Al máximo 5.1: nor
# one with an effect of the catalog (keys, clicks or commands to a window that may be the person's; what the model wrote
# sent out of the PC; a radio, a network, a pairing, airplane or display mode changed), whatever its risk: a call the
# model did not choose never lands there. A catalog without the field (the measurement catalogs saved before it)
# corrects by risk alone, as before.
CORRECTABLE_RISKS = ("read_only", "low_reversible")


def _threshold(name: str) -> float:
    """A System One threshold from the environment (BAXY_S1_DOUBT, BAXY_S1_VETO); 0 when unset: that layer is off."""
    try:
        return max(0.0, min(1.0, float(os.environ.get(name, "") or 0)))
    except ValueError:
        return 0.0


NOT_RUN = json.dumps({"status": "not_run", "reason": "the turn ended before this call ran"})
# Review 2026-10-22: a call queued behind one that did not complete was chosen on what that one would have done (app_open
# failed and input_text_type then typed into the person's own window): it is not run, and the model decides again.
NOT_RUN_AFTER = json.dumps({"status": "not_run", "reason": "the call before it in this turn did not complete"})
# A call the App was already running when its turn ended: it may have run, and nothing says what it did (audit
# 2026-10-15: the model read «not run» for a call the core had executed).
NO_RESULT = json.dumps({"status": "unknown", "reason": "no result came back for this call: it may have run or not"})
NO_RESULT_RAN = "sin resultado: pudo o no ocurrir"  # the same, among the session's calls (8.1)
# A question of the model's the person saw and did not answer before the turn ended.
ASKED = json.dumps({"status": "asked", "reason": "the person saw the question; their answer, if it comes, is their "
                                                 "next message"})

# The operation the App reads as «the person answered the pending confirmation» (the kernel's challenge): the App sends
# the exact invocation the kernel challenged again with its token, or drops it.
CONFIRM_OPERATION = "confirmation.answer"
# Renew al máximo (F005 of the notebook's falsehood bench, 2026-10-22): «¿ya lo subiste?» was answered with
# confirm_pending approve:true and nothing waiting for a «sí»; with a confirmation pending it would have approved what
# nobody approved. Without one, the call never reaches the App: its result says so and the model answers in words.
NOTHING_PENDING = json.dumps({"status": "failed", "error": "nothing_pending",
                              "reason": "no action is waiting for the person's confirmation"})
CONFIRM = {
    "type": "function",
    "function": {
        "name": "confirm_pending",
        "description": (
            "Give the person's answer to the confirmation you asked them for (an action that needed their «sí»). "
            "Use when: you asked «¿Lo borro?» and they said «sí, dale» (approve true) or «no, déjalo» (approve false). "
            "Do not use when: nothing is waiting for confirmation, or they asked for something new instead."
        ),
        "parameters": {"type": "object", "properties": {"approve": {"type": "boolean"}}, "required": ["approve"]},
    },
}

ASK_USER = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": (
            "Ask the person ONE short question, in their language, when a value an action needs is missing or the "
            "request could mean two different actions. Use when: «pon una alarma» (no time), «mándale un mensaje» "
            "(no recipient or text). Do not use when: the request is complete, to chat, or when no tool can do what is "
            "asked (ordering food or a taxi, calls, payments, bookings): then say in one sentence that you don't do "
            "that; asking for an address or a number will not make it possible."
        ),
        "parameters": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
    },
}


# What the model sees of an argument schema: meaning only. Validation-only keywords stay with the kernel, which
# validates the exact schema anyway; contract constants (a const or a one-value enum) are not the model's to write and
# are added back when its call is handed to the App (measured 2026-10-15: −4k tokens of prefix; memory.save wrote 114
# output tokens, its constants among them).
_MEANING_KEYS = {"type", "properties", "required", "items", "enum", "description", "minimum", "maximum", "anyOf",
                 "oneOf", "default", "format"}


def _model_schema(schema: Any, constants: dict[str, Any] | None = None) -> Any:
    if not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key not in _MEANING_KEYS:
            continue
        if key == "type" and isinstance(value, list):
            kinds = [kind for kind in value if kind != "null"]
            value = kinds[0] if len(kinds) == 1 else kinds
        if key == "properties" and isinstance(value, dict):
            props = {}
            for name, prop in value.items():
                if constants is not None and isinstance(prop, dict) and (
                        "const" in prop or (isinstance(prop.get("enum"), list) and len(prop["enum"]) == 1)):
                    constants[name] = prop["const"] if "const" in prop else prop["enum"][0]
                    continue
                props[name] = _model_schema(prop)
            value = props
        elif key == "items":
            value = _model_schema(value)
        elif key in {"anyOf", "oneOf"} and isinstance(value, list):
            value = [_model_schema(item) for item in value]
        out[key] = value
    if constants and isinstance(out.get("required"), list):
        out["required"] = [name for name in out["required"] if name not in constants]
    return out


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


class Mind:
    def __init__(self, server: LlmServer, trace: Path, system_one: SystemOne | None = None) -> None:
        self.server = server
        self.trace = trace
        self.system_one = system_one  # layer 2: the decision model beside Qwen (None: off)
        self._judged: dict[str, Any] | None = None
        self.tools: list[dict[str, Any]] = []
        self.wire_to_op: dict[str, str] = {}
        self.risk: dict[str, str] = {}  # each tool's risk as the App sent it, by wire name (layer 2 «corrige»)
        self.effects: dict[str, list[str]] = {}  # each tool's effects as the App sent them (al máximo 5.1), by wire name
        self._turn: dict[str, Any] | None = None
        self._beat: dict[str, Any] | None = None
        self.conversation: list[dict[str, Any]] = []
        self.trimmed_turns = 0
        # The tools and the system prompt in tokens, as the server counted them at warm-up (0 before it).
        self.prefix_tokens = 0
        self._tokens: dict[str, int] = {}  # each turn's text in the conversation and its tokens (_turn_sizes)
        self.constants: dict[str, dict[str, Any]] = {}
        english = json.loads(_ENGLISH_FILE.read_text(encoding="utf-8")) if _ENGLISH_FILE.is_file() else {}
        self.english: dict[str, str] = english.get("tools") or {}
        self.arguments: dict[str, dict[str, str]] = english.get("arguments") or {}
        self.decide_temperature = _env_float("BAXY_RENEW_DECIDE_TEMPERATURE", 0.2)
        self.seed = int(_env_float("BAXY_RENEW_SEED", 0))
        # PLAN_GENERAL C1: the long addresses results carried, by the short reference the model saw, and back.
        self._refs: dict[str, str] = {}
        self._ref_of: dict[str, str] = {}
        # Review 2026-10-22: the ids the mind writes itself (a confirmation's call, a call the server gave none, a
        # correction) count up for the whole session: from the conversation's length they repeated once it was trimmed.
        self._ids = 0
        self._ran: list[str] = []  # the session's last calls as «tool → how it ended» (8.1), and how many ran in all
        self._ran_count = 0
        # Review 2026-10-22: the voice thread logs here too (voice.speak, __main__.py): one row at a time.
        self._log_lock = threading.Lock()

    # ---- short references (PLAN_GENERAL C1) ----------------------------------------------------------------
    def _shorten(self, observation: str) -> tuple[str, dict[str, str]]:
        """The result with every address longer than LONG_REF_CHARS replaced by its short reference, and the
        references made for it (a known address keeps its reference). Text that is not JSON goes as it came."""
        try:
            facts = json.loads(observation)
        except json.JSONDecodeError:
            return observation, {}
        made: dict[str, str] = {}

        def walk(value: Any) -> Any:
            if isinstance(value, dict):
                return {k: walk(v) for k, v in value.items()}
            if isinstance(value, list):
                return [walk(v) for v in value]
            if isinstance(value, str) and len(value) > LONG_REF_CHARS and value.startswith(("http://", "https://")):
                ref = self._ref_of.get(value)
                if ref is None:
                    ref = f"{REF_PREFIX}{len(self._refs) + 1}"
                    self._refs[ref], self._ref_of[value] = value, ref
                made[ref] = value
                return ref
            return value

        shortened = walk(facts)
        if not made:
            return observation, {}
        return json.dumps(shortened, ensure_ascii=False), made

    def _expand(self, value: Any) -> Any:
        """A call's arguments with every short reference the model wrote put back as the address it stands for."""
        if isinstance(value, dict):
            return {k: self._expand(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._expand(v) for v in value]
        if isinstance(value, str) and REF_PREFIX in value:
            return _REF.sub(lambda m: self._refs.get(m.group(0), m.group(0)), value)
        return value

    def _new_id(self, kind: str) -> str:
        # A hyphen, never an underscore: an id written before the counter (confirm_12, call_5_0) is never repeated.
        self._ids += 1
        return f"{kind}-{self._ids}"

    # ---- catalog -------------------------------------------------------------------------------------------
    def configure(self, message: dict[str, Any]) -> int:
        capabilities = list(message.get("capabilities") or [])
        try:  # the exact catalog the App sent, for offline measurement of the presentation
            (self.trace.parent / "catalog.configure.json").write_text(
                json.dumps(message, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        apps = [str(n) for n in ((message.get("applicationCatalog") or {}).get("names") or []) if str(n).strip()]
        games = sorted({f'{e.get("name")} (appId {e.get("appId")}, {e.get("provider")})'
                        for e in ((message.get("gameCatalog") or {}).get("entries") or [])
                        if isinstance(e, dict) and e.get("name")})
        tools, wire_to_op, risk, effects = [ASK_USER, CONFIRM], {}, {}, {}
        aids: dict[str, Any] = {}
        for cap in capabilities:
            name = str(cap.get("name") or "")
            description = (self.english.get(name) or str(cap.get("description") or "")).replace(
                "{app_places}", APP_PLACES_TEXT)
            if name == "app.open" and apps:
                description += " Installed applications (use one of these names as appId): " + "; ".join(apps) + "."
            if name == "game.launch" and games:
                description += " The person's installed games: " + "; ".join(games) + "."
            if name in DESCRIPTION_AIDS and _aid_on(DESCRIPTION_AIDS[name][0]):
                aid, sentence = DESCRIPTION_AIDS[name]
                description = description.rstrip() + sentence
                aids[aid] = sentence.strip()
            raw = cap.get("argumentsSchema")
            constants: dict[str, Any] = {}
            schema = _model_schema(raw if isinstance(raw, dict) else {}, constants)
            if constants:
                self.constants[name] = constants
            schema["type"] = "object"
            schema.setdefault("properties", {})
            # What one argument means, where the model fills it (a folder named by the person went missing from the
            # path when only the tool's text said it: own path set 3/8, with the meaning on the argument 6/8).
            for argument, meaning in (self.arguments.get(name) or {}).items():
                if isinstance(schema["properties"].get(argument), dict):
                    schema["properties"][argument]["description"] = meaning.replace("{app_places}", APP_PLACES_TEXT)
            wire = name.replace(".", "_")
            tool = {"type": "function", "function": {"name": wire, "description": description, "parameters": schema}}
            tools.append(tool)
            wire_to_op[wire] = name
            risk[wire] = str(cap.get("risk") or "")
            effects[wire] = [str(e) for e in cap.get("effects") or []]
        self.tools, self.wire_to_op, self.risk, self.effects = tools, wire_to_op, risk, effects
        if aids:
            # A session's aid in the tools themselves, once: its own trace row, as the aids of a turn.
            self._log("configure.aid", time.monotonic(), None, aids=aids)
        return len(capabilities)

    def warm(self) -> None:
        """Process the tools and the system prompt once, so every turn starts from a cached prefix."""
        self.call_tokens = self.server.tokenize("<tool_call>")
        if len(self.call_tokens) != 1:
            raise RuntimeError(f"<tool_call> is not one token of this model: {self.call_tokens}")
        reply = self.server.chat({"messages": [{"role": "system", "content": self._system()},
                                                   {"role": "user", "content": "hola"}],
                                  "tools": self.tools, "max_tokens": 1,
                                  "chat_template_kwargs": {"enable_thinking": False}}, timeout=600)
        self.prefix_tokens = int((reply.get("usage") or {}).get("prompt_tokens") or 0)

    def _system(self, beat: bool = False) -> str:
        # Constant, so the prefix (tools, system, earlier messages) never changes between turns and is never re-read.
        return BEAT_SYSTEM if beat else SYSTEM

    @staticmethod
    def _pending_note(pending: dict[str, Any] | None) -> str:
        """The call the kernel holds for the person's yes, when one is: after «sí» the model called that tool again
        instead of answering it (e2e practice E021, 3 of 3), and the kernel only asked again."""
        if not isinstance(pending, dict) or not pending.get("operation"):
            return ""
        wire = str(pending["operation"]).replace(".", "_")
        arguments = pending.get("arguments")
        shown = f" {json.dumps(arguments, ensure_ascii=False)}" if isinstance(arguments, dict) else ""
        return (f"\n[Espera el sí de la persona: {wire}{shown}. Si sus palabras contestan a tu pregunta, llama a "
                f"confirm_pending con approve true o false.]")

    def _clock(self) -> str:
        # The time is a message of its own just before the person's words (the end of the prompt, the only part that is
        # new anyway). Appended to their words it was copied into arguments: a clipboard text and a web query carried
        # «[Thursday 15/10/2026 04:21 hora local…]» (2026-10-15). It also says no tool has run yet in this turn: the
        # last «[En este turno: …]» the model saw was the previous turn's, and lines of turns without calls were false
        # 24 % of the time against 6 % (falsedades p5-p8); decision2 on the notebook gained by that mechanism (P041
        # stopped inventing, P049 stopped looking up the clock): 227/230 vs 226. Al máximo 8.1: and the session's calls.
        now = _dt.datetime.now().astimezone()
        offset = now.strftime("%z")
        ran = str(self._ran_count or "ninguna")
        if self._ran:
            last = "" if len(self._ran) == self._ran_count else f", las {len(self._ran)} últimas"
            ran += f"{last} ({' / '.join(self._ran)})"
        return (f"{CLOCK_MARK} {now.strftime('%A %d/%m/%Y %H:%M')} hora local, UTC{offset[:3]}:{offset[3:]}; "
                "los campos que terminan en Utc van en UTC; turno nuevo: aún no se ejecutó ninguna herramienta en este "
                f"turno; llamadas a herramientas en esta sesión: {ran}]")

    # ---- turn ----------------------------------------------------------------------------------------------
    # One conversation for the whole session (native loop): every tool call the model made, every verified result that
    # came back as a tool message and every answer stay in it, turn after turn. The model reads what was really run in
    # earlier turns, not a retelling of it: a history of bare «Listo, abrí Steam» replies without the calls behind them
    # taught it to answer «Listo» without calling (2026-10-15 01:52, diagnosed on the notebook against the journal).
    # Parallel calls run in order, one per round trip.
    def new_session(self, history: list[dict[str, Any]] | None = None) -> None:
        """Start a fresh conversation, optionally from earlier plain exchanges (a bench case's context)."""
        self._turn = self._beat = None
        self.trimmed_turns = 0
        self._refs, self._ref_of, self._ids = {}, {}, 0
        self._ran, self._ran_count = [], 0
        self.conversation = [{"role": m["role"], "content": m["content"]} for m in history or []
                             if m.get("role") in {"user", "assistant"} and str(m.get("content") or "").strip()]

    def export_session(self) -> list[dict[str, Any]]:
        """The session's conversation as it stands (calls and results included), for the App to keep with the session it
        shows (design v4, Sessions); it is asked for between turns. Its last element is the session's own state (review
        2026-10-22: the short references and the ids, or after a relaunch ref:r1 stood for another address; al máximo
        8.1: the session's calls); the App keeps the array as it is."""
        state = {"role": SESSION_STATE, "refs": self._refs, "ids": self._ids, "ran": self._ran,
                 "ran_count": self._ran_count}
        return json.loads(json.dumps([*self.conversation, state], ensure_ascii=False))

    def load_session(self, conversation: list[Any]) -> None:
        """Go back to a kept session: its conversation exactly as exported, so the model reads what really ran."""
        self.new_session()
        state = next((m for m in conversation if isinstance(m, dict) and m.get("role") == SESSION_STATE), {})
        if isinstance(state.get("refs"), dict):
            self._refs = {str(ref): str(value) for ref, value in state["refs"].items()}
            self._ref_of = {value: ref for ref, value in self._refs.items()}
        self._ids = state["ids"] if isinstance(state.get("ids"), int) and state["ids"] > 0 else 0
        self.conversation = [m for m in conversation if isinstance(m, dict)
                             and m.get("role") in {"user", "assistant", "tool"}]
        if isinstance(state.get("ran_count"), int) and isinstance(state.get("ran"), list):
            self._ran, self._ran_count = [str(entry) for entry in state["ran"]][-SESSION_CALLS:], state["ran_count"]
        else:
            # Kept before 8.1: how many calls its conversation shows (their results are in it), never «none».
            self._ran_count = sum(1 for m in self.conversation for c in m.get("tool_calls") or []
                                  if c.get("function", {}).get("name") != ASK_USER["function"]["name"])
        self._trim()

    def decide(self, request_id: Any, text: str, pending: dict[str, Any] | None = None) -> dict[str, Any]:
        # Review 2026-10-22: a decision that fails (the model server down, an error) takes back what it added, so the
        # next turn never reads an old request without its answer as one still to do.
        turn = self._turn
        if turn and turn.get("asked"):
            # The person's next words answer the model's own ask_user: they are that call's result, in the same loop, so
            # the steps already run stay in the conversation and are never run again. A new request instead of an
            # answer reaches the model the same way, and the model reads it as what it is.
            asked, after, said = turn.pop("asked"), turn.pop("after_asked", []), turn["text"]
            answer = {"role": "tool", "tool_call_id": asked, "content": text}
            turn["conv"].append(answer)
            for later in after:
                turn["conv"].append({"role": "tool", "tool_call_id": later, "content": NOT_RUN})
            turn["text"], turn["answering"] = text, True
            try:
                return self._next(request_id, "turn.decide", turn)
            except Exception:
                self._take_back(turn["conv"], answer)
                turn.update(asked=asked, after_asked=after, text=said)
                raise
        self._close_open_calls()
        answering = any(str(m.get("content") or "").startswith(DOUBT_ASKED) for m in self.conversation[-2:])
        clock = {"role": "user", "content": self._clock() + self._pending_note(pending)}
        self.conversation.append(clock)
        request = {"role": "user", "content": text}
        self.conversation.append(request)
        try:
            self._trim()
            # Review 2026-10-22: a text that alone does not fit beside the prefix (a pasted log) failed the turn whole
            # and wordless, as only earlier turns can be trimmed: it keeps its start, halved until it fits, and the cut
            # is said where the model reads it.
            keep = len(text)
            while keep > CUT_TEXT_FLOOR and not self._fits(self._turn_sizes()):
                keep //= 2
                request["content"] = text[:keep] + CUT_TEXT.format(n=len(text) - keep)
            self._turn = {"conv": self.conversation, "queue": [], "awaiting": None, "text": text,
                          "pending": bool(isinstance(pending, dict) and pending.get("operation")),
                          "answering": answering}
            return self._next(request_id, "turn.decide", self._turn)
        except Exception:
            self._take_back(self.conversation, clock)
            self._turn = None
            raise

    @staticmethod
    def _take_back(conv: list[dict[str, Any]], first: dict[str, Any]) -> None:
        """Remove `first` (that very message) and everything after it."""
        del conv[next(i for i, m in enumerate(conv) if m is first):]

    def beat(self, request_id: Any, context: dict[str, Any]) -> dict[str, Any]:
        """The heartbeat: nobody spoke; the model looks at the moment in a conversation of its own (OpenClaw's isolated
        heartbeat session), says what is happening and whether to intervene, and only then acts, proposes or says
        something. Same tools (the cached prefix: the template puts them first) and a system text without the «¿ya lo
        hiciste?» sentence; what it did joins the person's conversation only if it intervened."""
        started = time.monotonic()
        if self._beat is not None:
            # Review 2026-10-22: a heartbeat the App never ended is closed as end_beat closes it, never overwritten
            # with what BAXY said or did in it unsaid.
            self.end_beat()
        conv = [{"role": "user", "content": beat_message(context)}]
        # Review 2026-10-22: a heartbeat that read the person's memory keeps out of the trace what it deduced from it and
        # what it said, as a turn does from its memory call on (_result).
        private = bool(context.get("memory"))
        # The decision whether to intervene is greedy: on the open scenes 32 → 34 of 40 sampled against greedy.
        reply = self.server.chat({"messages": [{"role": "system", "content": self._system(beat=True)}, *conv],
                                  "tools": self.tools, "tool_choice": "none", "max_tokens": 400,
                                  "chat_template_kwargs": {"enable_thinking": False},
                                  "temperature": 0.0, "top_p": 0.8, "top_k": 20, "min_p": 0.0,
                                  "seed": 0,
                                  "response_format": {"type": "json_schema",
                                                      "json_schema": {"name": "latido", "schema": BEAT_DECISION}}})
        content = (reply["choices"][0]["message"].get("content") or "").strip()
        try:
            decision = json.loads(content)
        except json.JSONDecodeError:
            decision = None
        if not isinstance(decision, dict) or not isinstance(decision.get("intervenir"), bool):
            # Unreadable (cut by the token budget, or not the schema): said as what it is, never as a silence.
            self._log("turn.beat.decide", started, reply, text="[latido]", content=None if private else content,
                      failure="unreadable")
            return {"type": "turn.result", "id": request_id, "kind": "failure", "operation": None, "arguments": None,
                    "question": "", "reply": ""}
        intervene = decision["intervenir"]
        self._log("turn.beat.decide", started, reply, text="[latido]", content=None if private else content,
                  intervene=intervene)
        self._beat = {"conv": conv, "queue": [], "awaiting": None, "text": "[latido]", "beat": True,
                      "silent": not intervene, "private": private}
        if not intervene:
            return {"type": "turn.result", "id": request_id, "kind": "silence", "operation": None, "arguments": None,
                    "question": "", "reply": ""}
        # The analysis stays as the model's own words, not as JSON: with its JSON before it, the model answered the
        # second move in JSON again (practice scene P023). Al máximo 10.3: the motives it found go before it, as words
        # too: the move that acts read only the analysis (PALANCAS-nb 10.3, scenes P002 and P023).
        motives = "; ".join(f"{m}: {decision.get(m) or ''}" for m in _MOTIVES)
        conv.append({"role": "assistant", "content": f"{motives}. {decision.get('analisis') or ''}".rstrip()})
        conv.append({"role": "user", "content": BEAT_ACT})
        return self._next(request_id, "turn.beat", self._beat)

    def end_beat(self) -> None:
        """The App ended the heartbeat's turn: a beat that was not silent is part of the conversation from now on (the
        person may answer what BAXY said or proposed); a silent one leaves no trace."""
        beat, self._beat = self._beat, None
        if not beat or beat.get("silent"):
            return
        if beat.get("awaiting"):
            beat["conv"].append({"role": "tool", "tool_call_id": beat["awaiting"], "content": NO_RESULT})
            self._ran_add(beat.get("calling"), NO_RESULT_RAN)
        if beat.get("asked"):
            beat["conv"].append({"role": "tool", "tool_call_id": beat["asked"], "content": ASKED})
        pending = [c["id"] for c in beat.get("queue") or []]
        for call_id in [*beat.get("after_asked", []), *pending]:
            if call_id:
                beat["conv"].append({"role": "tool", "tool_call_id": call_id, "content": NOT_RUN})
        self._close_open_calls()
        # Review 2026-10-22 (R10.2 of the notebook): what the person may answer is what BAXY said and did, not what the
        # heartbeat read (its moment, its rules, its analysis and the order to act, the first three messages).
        acted = beat["conv"][3:]
        if acted:
            self.conversation.extend([{"role": "user", "content": BEAT_MARK}, *acted])
        self._trim()

    def _ran_add(self, calling: Any, outcome: str) -> None:
        """One call of the session and how it ended, for the clock (8.1)."""
        wire = CONFIRM["function"]["name"] if calling == CONFIRM_OPERATION else str(calling or "?").replace(".", "_")
        self._ran, self._ran_count = [*self._ran, f"{wire} → {outcome}"][-SESSION_CALLS:], self._ran_count + 1

    def _close_open_calls(self) -> None:
        """A call the App never answered (the turn ended first) gets its honest result, so the conversation stays a
        valid tool transcript and the model never reads an unanswered call as done."""
        turn = self._turn or {}
        if turn.get("awaiting"):
            self.conversation.append({"role": "tool", "tool_call_id": turn["awaiting"], "content": NO_RESULT})
            self._ran_add(turn.get("calling"), NO_RESULT_RAN)
        if turn.get("asked"):
            self.conversation.append({"role": "tool", "tool_call_id": turn["asked"], "content": ASKED})
        pending = [c["id"] for c in turn.get("queue") or []]
        for call_id in [*turn.get("after_asked", []), *pending]:
            if call_id:
                self.conversation.append({"role": "tool", "tool_call_id": call_id, "content": NOT_RUN})
        self._turn = None

    def _trim(self) -> None:
        """Keep the last turns that fit the budget; a turn starts at its clock, so no call loses its result. Past it, the
        oldest turns go until what is left fits TRIM_TO of every bound."""
        turns = self._turn_sizes()
        if len(turns) <= 1 or self._fits(turns):
            return
        dropped = 1
        while dropped < len(turns) - 1 and not self._fits(turns[dropped:], TRIM_TO):
            dropped += 1
        # Up to the first kept turn's clock: an earlier note of what was cut goes with the turns cut. In place: an open
        # turn's conversation is this same list (the notebook's review of 1.1/1.2, 2026-10-22).
        del self.conversation[:turns[dropped][0]]
        self.trimmed_turns += dropped
        self.conversation.insert(0, {"role": "user", "content": TRIMMED.format(n=self.trimmed_turns)})

    def _turn_sizes(self) -> list[tuple[int, int, int]]:
        """Each turn of the conversation as (its first message, characters, tokens); the first turn takes in what comes
        before its clock (the note of a cut, a bench's history). Al máximo 1.3/1.4 (2026-10-22): the whole history went
        to /tokenize at every check, and the cut checked again after each turn it took out; now each turn's text is
        counted once and kept (their sum differs from the whole text's by a token at most where two turns meet), so a
        check counts only the turns that changed (the open one, the one before once its answer came) and a cut counts
        nothing more. The last reply's
        usage.prompt_tokens was not used: it does not count what came after that reply (a result, the clock, the
        request), and the template's own tokens are not the history's."""
        if not self.conversation:
            return []
        bounds = [0, *self._turn_starts()[1:], len(self.conversation)]
        texts = ["".join(json.dumps(m, ensure_ascii=False) for m in self.conversation[a:b])
                 for a, b in zip(bounds, bounds[1:])]
        if self.prefix_tokens:
            self._tokens = {t: self._tokens[t] if t in self._tokens else len(self.server.tokenize(t)) for t in texts}
        return [(a, len(t), self._tokens.get(t, 0)) for a, t in zip(bounds, texts)]

    def _fits(self, turns: list[tuple[int, int, int]], share: float = 1.0) -> bool:
        """Whether these turns fit `share` of every bound: turns, characters and the tokens the prefix leaves."""
        room = self.server.context - self.prefix_tokens - TURN_ROOM_TOKENS
        return (len(turns) <= HISTORY_TURNS * share and sum(t[1] for t in turns) <= HISTORY_CHARS * share
                and (not self.prefix_tokens or sum(t[2] for t in turns) <= room * share))

    def _turn_starts(self) -> list[int]:
        return [i for i, m in enumerate(self.conversation)
                if m["role"] == "user" and str(m.get("content") or "").startswith(CLOCK_MARK)]

    def continue_turn(self, request_id: Any, observation: str, final: bool = False,
                      beat: bool = False) -> dict[str, Any]:
        """The verified result of the call the App ran goes back as that call's tool message. ``final``: the App closes
        the turn (steps spent, engine down, or a confirmation waiting), so the model answers now in text from what the
        results show. ``beat``: the heartbeat's turn."""
        turn = self._beat if beat else self._turn
        if not turn or not turn.get("awaiting"):
            raise RuntimeError("no open turn to continue")
        conv = turn["conv"]
        # Every call of the turn so far with how it ended, at the end of the newest result: where the model writes its
        # answer, the facts it may tell are together (it told «no pude abrir Steam» after Steam opened, «lo guardé»
        # after the typing failed, 2026-10-15 falsehood bench).
        done = turn.setdefault("done", [])
        calling = str(turn.get("calling", "?"))
        calling = CONFIRM["function"]["name"] if calling == CONFIRM_OPERATION else calling.replace(".", "_")
        outcome = _outcome(observation)
        entry, same = f"{calling} → {outcome}", turn.get("last_call")
        # Grouped only when the result is the same too: a click that worked and then failed are two facts (round 2).
        turn["last_call"] = (calling, turn.get("calling_args"), outcome)
        if done and same == turn["last_call"]:
            turn["repeats"] = turn.get("repeats", 1) + 1
            done[-1] = f"{calling} ×{turn['repeats']} con los mismos argumentos → {outcome}"
        else:
            turn["repeats"] = 1
            done.append(entry)
        self._ran_add(turn.get("calling"), outcome)
        aids = _aids_seen(observation)
        named = json.loads(turn.get("calling_args") or "{}") if calling in {"app_open", "input_visible_controls"} else {}
        # Uso real: a look at another window (the browser's) came between the opening and the failures; the application
        # kept is the last one named that has places of its own.
        application = named.get("appId") or named.get("application") if isinstance(named, dict) else None
        if isinstance(application, str) and _fold(application) in APP_PLACES:
            turn["app_named"] = application
        note = ""
        if (calling in {"input_visible_click", "input_visible_controls"} and not outcome.startswith("completado")
                and turn.get("app_named") and not turn.get("places_told") and _aid_on("app_places_next")):
            note = places_note(turn["app_named"])
            if note:
                turn["places_told"] = True
                aids["app_places_next"] = note.strip()
        if calling == "input_visible_click" and not turn.get("field_told") and _aid_on("field_focused_next"):
            field = field_note(observation, turn.get("calling_args"))
            if field:
                turn["field_told"] = True
                note += field
                aids["field_focused_next"] = field.strip()
        # Aid «same_call_next» (PLAN_GENERAL C2; uso real: the same click 5-7 times, a reload and a typing in turn): a
        # call made a third time in this turn with the same arguments and the same result, whatever came between, is
        # told as a fact with its options, once per turn (a loop of a look and a click repeats both).
        seen = turn.setdefault("calls_seen", {})
        key = json.dumps([calling, turn.get("calling_args"), outcome], ensure_ascii=False)
        seen[key] = seen.get(key, 0) + 1
        if seen[key] == SAME_CALL_TOLD and not turn.get("same_told") and _aid_on("same_call_next"):
            turn["same_told"] = True
            repeated = SAME_CALL_NOTE.format(call=calling, times=SAME_CALL_TOLD, outcome=outcome,
                                             options=SAME_CALL_CLOSED if final else SAME_CALL_OPTIONS)
            note += repeated
            aids["same_call_next"] = repeated.strip()
        # Aid «short_refs» (PLAN_GENERAL C1; uso real: news addresses of ~500 tokens copied wrong, 11 s each): a long
        # address in a result reaches the model as a short reference, and the mind puts the address back in its calls.
        shown, made = self._shorten(observation) if _aid_on("short_refs") else (observation, {})
        if made:
            aids["short_refs"] = sorted(made) if turn.get("private") else made
        conv.append({"role": "tool", "tool_call_id": turn["awaiting"],
                     "content": shown + "\n[En este turno: " + "; ".join(done) + "]" + note})
        turn["awaiting"] = None
        if aids:
            # What the aids told the model, a row of its own: the model's decision after it is the next row.
            self._log("turn.aid", time.monotonic(), None, operation=turn.get("calling"),
                      aids=sorted(aids) if turn.get("private") else aids)
        if final:
            # The App closes the turn (its step budget spent, the engine down, or a confirmation waiting for the
            # person): said where the model reads it, at the end of the last result, without a cause the mind does not
            # know.
            conv[-1]["content"] += ("\n[Este turno no admite más herramientas: responde ahora a la persona sólo "
                                    "con lo que muestran los resultados.]")
        completed = outcome.startswith("completado")
        if turn["queue"] and not final and completed:
            return self._result(request_id, turn, turn["queue"].pop(0), None, "turn.continue", time.monotonic(), "")
        for call in turn["queue"]:
            conv.append({"role": "tool", "tool_call_id": call["id"], "content": NOT_RUN if final else NOT_RUN_AFTER})
        turn["queue"] = []
        return self._next(request_id, "turn.continue", turn, final=final)

    def confirm(self, request_id: Any, approve: bool, label: str) -> dict[str, Any]:
        """The person pressed Sí or No on a pending confirmation: their answer (the button's label) and the
        confirm_pending call it stands for enter the conversation as they are, with no model call in between."""
        started = time.monotonic()
        self._close_open_calls()
        call_id = self._new_id("confirm")
        self.conversation.append({"role": "user", "content": label})
        self.conversation.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": call_id, "type": "function",
             "function": {"name": CONFIRM["function"]["name"], "arguments": json.dumps({"approve": approve})}}]})
        self._turn = {"conv": self.conversation, "queue": [], "awaiting": call_id, "text": label,
                      "calling": CONFIRM_OPERATION}
        self._log("turn.confirm", started, None, text=label, kind="action", operation=CONFIRM_OPERATION,
                  arguments={"approve": approve})
        return {"type": "turn.result", "id": request_id, "kind": "action", "operation": CONFIRM_OPERATION,
                "arguments": {"approve": approve}, "reply": "", "question": ""}

    def _shrink_turn(self, conv: list[dict[str, Any]]) -> bool:
        """Cut each result of the open turn but the newest to its start (SHRUNK_CHARS), saying so: whether any was."""
        starts = [i for i, m in enumerate(conv)
                  if m["role"] == "user" and str(m.get("content") or "").startswith(CLOCK_MARK)]
        results = [m for m in conv[(starts[-1] if starts else 0):] if m["role"] == "tool"]
        cut = False
        for message in results[:-1]:
            content = str(message.get("content") or "")
            if len(content) > SHRUNK_CHARS and SHRUNK.format(n="")[:20] not in content:
                message["content"] = content[:SHRUNK_CHARS] + SHRUNK.format(n=len(content) - SHRUNK_CHARS)
                cut = True
        return cut

    def _next(self, request_id: Any, stage: str, turn: dict[str, Any], final: bool = False,
              shrunk: bool = False) -> dict[str, Any]:
        started = time.monotonic()
        conv = turn["conv"]
        messages = [{"role": "system", "content": self._system(bool(turn.get("beat")))}, *conv]
        body = {"messages": messages, "tools": self.tools, "max_tokens": 512, "parallel_tool_calls": True,
                "chat_template_kwargs": {"enable_thinking": False},
                "temperature": self.decide_temperature, "top_p": 0.8, "top_k": 20, "min_p": 0.0,
                # A fixed seed: the same conversation gets the same decision, so two runs of a bench differ by the
                # change measured, not by sampling noise (±3 of 90 without it). Review 2026-10-22: BAXY_RENEW_SEED moves
                # it, to measure that noise (0 by default).
                "seed": self.seed}
        if self._doubted(stage, turn, final):
            # The decision's own token probabilities, for its doubt (doubt.py, System One) and the trace: same call, no
            # other pass. Al máximo 9.5 (2026-10-22): only where the doubt is read; elsewhere (turn.continue, the last
            # answer, the heartbeat) the server sorted the vocabulary at every token for a doubt only the trace kept,
            # which those rows no longer carry (−20 to −100 ms per call, expected).
            body.update(logprobs=True, top_logprobs=10)
        if final:
            # The last answer of an exhausted turn is words only. The tools stay, so the cached prefix (37k tokens)
            # is not evicted by a shorter prompt (llama.cpp PR #24176: a restore re-reads ~4k tokens; measured 2.3-3.6 s
            # on the next order). tool_choice none alone still let Qwen3.5 write a call as XML text that reached the
            # person (llama.cpp #20837; 2026-10-15 E017): the token that opens a call cannot be sampled.
            body["tool_choice"] = "none"
            body["logit_bias"] = [[token, False] for token in self.call_tokens]
        try:
            reply = self.server.chat(body)
        except urllib.error.HTTPError as error:
            # llama-server refuses a prompt past its context with HTTP 400: within a turn that is its own results, so
            # they are cut (said where the model reads) and the model answers in words from what is left, once.
            if error.code != 400 or shrunk or not self._shrink_turn(conv):
                raise
            self._log(stage, started, None, kind="context_shrunk", operation=None, arguments=None, content=None)
            return self._next(request_id, stage, turn, final=True, shrunk=True)
        message = reply["choices"][0]["message"]
        content = (message.get("content") or "").strip()
        calls = []
        for index, call in enumerate(message.get("tool_calls") or []):
            wire = call["function"]["name"]
            raw = call["function"].get("arguments") or "{}"
            try:
                arguments = json.loads(raw)
            except json.JSONDecodeError:
                arguments = None
            if not isinstance(arguments, dict):
                # Not an object: it travels as written, so the rejection says what the model gave.
                arguments = {"unparsedArguments": raw}
            calls.append({"id": call.get("id") or self._new_id("call"), "wire": wire, "arguments": arguments})
        note = self._held(stage, turn, final, calls[0], reply, body) if calls else None
        if isinstance(note, dict):
            # Layer 2 «corrige»: the decision model's tool, with the arguments the model itself wrote for it, replaces
            # the action the model doubted (and anything queued behind it, chosen on the same misreading). Review
            # 2026-10-22 (and B-MED-8): the words it wrote for the doubted call go with it, and the row says whose doubt
            # it carries (doubt_of) beside the operation that runs.
            turn["doubt_of"] = self.wire_to_op.get(calls[0]["wire"], calls[0]["wire"])
            calls, note, content = [note], None, ""
        if note:
            # System One: the model was not sure of this action (layer 0), or was unsure and the decision model chose
            # otherwise (layer 2). Nothing runs; it is told so where it reads and asks the person, in its own words, what
            # they want (the call it nearly made never enters the conversation).
            conv.append({"role": "user", "content": note})
            doubted = self.wire_to_op.get(calls[0]["wire"], calls[0]["wire"])
            if doubted.startswith("memory."):
                turn["private"] = True  # review 2026-10-22: the words meant for memory, as after a memory call
            self._log(stage, started, reply, text=None if turn.get("private") else turn["text"], kind="doubt_ask",
                      operation=doubted, arguments=None, content=None)
            return self._next(request_id, stage, turn, final=True, shrunk=shrunk)
        if calls:
            conv.append({"role": "assistant", "content": content, "tool_calls": [
                {"id": c["id"], "type": "function",
                 "function": {"name": c["wire"], "arguments": json.dumps(c["arguments"], ensure_ascii=False)}}
                for c in calls]})
            turn["queue"] = calls[1:]
            return self._result(request_id, turn, calls[0], reply, stage, started, content)
        if not final and ("<tool_call>" in content or "<function=" in content):
            # Review 2026-10-22: a call llama-server could not parse stays as text in content, and it reached the person
            # as BAXY's words. It is a failed call: the model answers in words, where a call cannot be written.
            self._log(stage, started, reply, text=None if turn.get("private") else turn["text"], kind="malformed_call",
                      operation=None, arguments=None, content=None)
            return self._next(request_id, stage, turn, final=True, shrunk=shrunk)
        if not content and not final and stage == "turn.continue" and not turn.get("beat"):
            # After a call the model wrote nothing and called nothing: an empty reply is a failed turn that never tells
            # what ran (round 2, as an empty ask_user), so it answers in words from the results.
            return self._next(request_id, stage, turn, final=True, shrunk=shrunk)
        if content:
            conv.append({"role": "assistant", "content": content})
        return self._result(request_id, turn, None, reply, stage, started, content)

    @staticmethod
    def _doubted(stage: str, turn: dict[str, Any], final: bool) -> bool:
        """Whether this call's decision is read for its doubt: a person's turn deciding, not its last answer, a
        continuation or a heartbeat."""
        return stage == "turn.decide" and not final and not turn.get("beat")

    def _held(self, stage: str, turn: dict[str, Any], final: bool, call: dict[str, Any], reply: dict | None,
              body: dict[str, Any]) -> str | dict[str, Any] | None:
        """The note that holds the turn's first action, the call that replaces it, or None. Layer 0 (BAXY_S1_DOUBT): the
        model's confidence is under the threshold, unless these words answer a question (DOUBT_ASKED) or the call is
        low_reversible. Layer 2
        (BAXY_S1_VETO, with a decision model): under that one, the decision model is asked which of the model's own
        candidates the person meant, and a different answer holds it — or, with BAXY_S1_CORRECT=1 and a tool of
        CORRECTABLE_RISKS, the model fills that tool and it runs instead; a low_reversible call it does not correct
        runs. Asking and confirming are never held: they
        already put the person in the loop."""
        if not self._doubted(stage, turn, final):
            return None
        if call["wire"] in (ASK_USER["function"]["name"], CONFIRM["function"]["name"]):
            return None
        doubt = read_doubt(reply)
        if doubt is None:
            return None
        # Al máximo, System One 2: layer 0 never holds a low_reversible call; its error is undone and the kernel verifies
        # it. On 26 runs of decision2 with System One (2026-10-22) it held 23, 22 of them right without System One (P040
        # ×7, P085 ×15) and none useful; read_only it holds still (24 useful against 5 harmful), and anything riskier.
        if doubt["confidence"] < _threshold("BAXY_S1_DOUBT") and not turn.get("answering") \
                and self.risk.get(call["wire"]) != "low_reversible":
            return DOUBT_NOTE.format(call=call["wire"])
        if self.system_one is None or doubt["confidence"] >= _threshold("BAXY_S1_VETO"):
            return None
        options = self._candidates(call["wire"], doubt, body)
        judged = self.system_one.choose(turn["text"], self._said(), options)
        self._judged = {"options": list(options), **judged} if judged else {"options": list(options), "choice": None}
        if not judged or judged["choice"] == call["wire"]:
            return None
        corrected = self._corrected(judged["choice"], body)
        if corrected is not None:
            self._judged["corrected"] = True
            return corrected
        if self.risk.get(call["wire"]) == "low_reversible":
            # Al máximo, System One 2: nor does layer 2 turn a low_reversible call into a question; it only corrects it.
            # On the same 26 runs it asked instead of 11, all right without System One (P112 ×4, P124 ×6, P113 ×1);
            # its corrections of them were 6 useful (P257) against 2 harmful.
            return None
        other = OPTION_TEXT.get(judged["choice"], judged["choice"])
        return DOUBT_OTHER_NOTE.format(call=call["wire"], other=other)

    def _said(self) -> list[dict[str, str]]:
        """What the person and BAXY said before the words being decided, for the decision model: their messages and
        BAXY's answers and questions (an ask_user's question lives in its call), never an internal note «[...]». Review
        2026-10-22: answering ask_user, the last two messages are not the clock and the request, and the question was
        left out."""
        source = self.conversation
        if source and source[-1].get("role") == "user":
            source = source[:-1]  # the request itself (an answer to ask_user is the tool message, left out by role)
        said = []
        for message in source:
            content = message.get("content")
            if message.get("role") in ("user", "assistant") and isinstance(content, str) and content.strip() \
                    and not content.startswith("["):
                said.append({"role": message["role"], "content": content})
            for call in message.get("tool_calls") or []:
                if call["function"]["name"] == ASK_USER["function"]["name"]:
                    try:
                        question = json.loads(call["function"]["arguments"]).get("question")
                    except (json.JSONDecodeError, AttributeError):
                        question = None
                    if isinstance(question, str) and question.strip():
                        said.append({"role": "assistant", "content": question})
        return said

    def _corrected(self, wire: str, body: dict[str, Any]) -> dict[str, Any] | None:
        """The decision model's tool as a call the model filled itself (piece A), or None — the turn then asks: correcting
        is off, the tool's risk is not in CORRECTABLE_RISKS, it has an effect of the catalog, or the model did not write
        that tool's call."""
        if os.environ.get("BAXY_S1_CORRECT", "").strip() != "1" or self.risk.get(wire) not in CORRECTABLE_RISKS \
                or self.effects.get(wire):
            return None
        try:
            filled = self.server.fill_call(body, wire)
        except Exception:  # noqa: BLE001 - a fill that failed falls back to asking
            return None
        if not filled or filled.get("name") != wire or not self._founded(wire, filled["arguments"], body["messages"]):
            return None
        return {"id": self._new_id("s1"), "wire": wire, "arguments": filled["arguments"]}

    def _founded(self, wire: str, arguments: dict[str, Any], messages: list[dict[str, Any]]) -> bool:
        """Whether a filled call holds every required argument of its tool and each text or number among them appears
        in what the conversation showed: the person's words or a tool's result (folded, as a whole word). B-MED-1 of the
        notebook (2026-10-22): Laya chose window_snap where Qwen chose window_resolve, and fill_call wrote windowId «1»,
        which no result had listed, and it ran; a web_download got a page of results as its url.
        Al máximo, System One 1: three kinds of value are the catalog's, not the person's words, and count as founded: a
        code of the argument's own enum («downloads» for «Descargas», «pause», «left»), an application or game the mind
        listed to the model in app_open and game_launch, or that game's appId («Worms W.M.D» for «el Worms»), and a file
        name whose name and extension were both said («contrato.pdf» for «el PDF contrato»: Qwen writes it so). Practice
        P203 (26 runs with System One, 2026-10-22): Laya chose file_read at 0.91 in 7 and «corrige» asked every time.
        Ids (windowId, reminderId…) and any other text still have to appear in the conversation or in a result."""
        tool = next((t["function"] for t in self.tools if t["function"]["name"] == wire), {})
        required = (tool.get("parameters") or {}).get("required") or []
        properties = (tool.get("parameters") or {}).get("properties") or {}
        seen = _fold(" ".join(str(m.get("content") or "") for m in messages
                              if m.get("role") == "tool" or (m.get("role") == "user"
                                                             and not str(m.get("content") or "").startswith("["))))

        def said(text: str) -> bool:
            return bool(text) and re.search(rf"(?<!\w){re.escape(text)}(?!\w)", seen) is not None

        for name in required:
            value = arguments.get(name)
            if value is None or value == "":
                return False
            if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                continue
            prop = properties.get(name)
            if isinstance(value, str) and ((isinstance(prop, dict) and value in (prop.get("enum") or []))
                                           or self._listed(value)):
                continue
            text = _fold(str(int(value) if isinstance(value, float) and value.is_integer() else value))
            stem, dot, extension = text.rpartition(".")
            if not said(text) and not (dot and re.fullmatch(r"[a-z0-9]{1,5}", extension) and said(stem)
                                       and said(extension)):
                return False
        return True

    def _listed(self, value: str) -> bool:
        """Whether a value is a whole entry of the lists configure put in the descriptions of app_open («Installed
        applications (use one of these names as appId): A; B.») and game_launch («The person's installed games: Name
        (appId N, provider); …»): an application's name, a game's name or a game's appId."""
        folded = re.escape(_fold(value))
        lists = {"app_open": ("installed applications (use one of these names as appid): ",
                              rf"(?:^|; ){folded}(?=;|\.(?: |$))"),
                 "game_launch": ("the person's installed games: ", rf"(?:^|; ){folded} \(appid |\(appid {folded}, ")}
        for tool in self.tools:
            marker, entry = lists.get(tool["function"]["name"], ("", ""))
            description = _fold(str(tool["function"].get("description") or ""))
            at = description.find(marker) if marker else -1
            if at >= 0 and re.search(entry, description[at + len(marker):]):
                return True
        return False

    def _candidates(self, chosen: str, doubt: dict[str, Any], body: dict[str, Any]) -> dict[str, str]:
        """The model's own candidates as the decision model's options (as in its training, build_kev_data.py): the tool it
        chose, the tools it nearly wrote at its weakest name token (the rest of each name written greedily on the same
        slot), asking, and answering in words."""
        described = {t["function"]["name"]: short(t["function"]["description"]) for t in self.tools}
        # B-MED-3 (2026-10-22): the rule of its training (qwen_signals.py, rollouts): the chosen tool and the next three
        # tokens of the weakest one, each of p ≥ 0.01 (served, the chosen token took a place and a rival needed 0.02).
        names = [chosen]
        for token, p in doubt.get("rivals") or []:
            if p < 0.01 or len(names) >= 4:
                continue
            written = doubt.get("written", "") + token
            try:
                written += self.server.complete_name(body, written) if ">" not in written[written.find("<function="):] else ""
            except Exception:  # noqa: BLE001 - a rival that cannot be read is left out
                continue
            at = written.find("<function=")
            names.append(written[at + len("<function="):].split(">")[0].strip() if at >= 0 else "")
        options = {n: described[n] for n in dict.fromkeys(names) if n in described and n != ASK}
        return {**options, ASK: OPTION_TEXT[ASK], ANSWER: OPTION_TEXT[ANSWER]}

    def _result(self, request_id: Any, turn: dict[str, Any], call: dict[str, Any] | None, reply: dict | None,
                stage: str, started: float, content: str) -> dict[str, Any]:
        result: dict[str, Any] = {"type": "turn.result", "id": request_id, "kind": "conversation", "operation": None,
                                  "arguments": None, "question": "", "reply": ""}
        if call is not None and call["wire"] == "ask_user":
            question = " ".join(str(call["arguments"].get("question") or "").split())
            later = [c["id"] for c in turn.get("queue") or []]
            turn["queue"], turn["awaiting"] = [], None
            if question:
                turn["asked"], turn["after_asked"] = call["id"], later
                result.update(kind="clarify", question=question)
            else:
                # An empty question asks nothing: it and the calls after it did not run, and what the model wrote
                # beside it is its answer.
                for call_id in [call["id"], *later]:
                    turn["conv"].append({"role": "tool", "tool_call_id": call_id, "content": NOT_RUN})
                if not content:
                    # Nothing to say beside it: the model answers in words from what ran (an empty reply after an
                    # action was a failed turn that never told what happened; round 2).
                    self._log(stage, started, reply, text=None if turn.get("private") else turn["text"],
                              kind="ask_user_empty", operation=None, arguments=None, content=None)
                    return self._next(request_id, stage, turn, final=True)
                result.update(reply=content)
        elif call is not None and call["wire"] == CONFIRM["function"]["name"] and not turn.get("pending"):
            for call_id in [call["id"], *(c["id"] for c in turn.get("queue") or [])]:
                turn["conv"].append({"role": "tool", "tool_call_id": call_id,
                                     "content": NOTHING_PENDING if call_id == call["id"] else NOT_RUN})
            turn["queue"], turn["awaiting"] = [], None
            self._log(stage, started, reply, text=None if turn.get("private") else turn["text"],
                      kind="nothing_pending", operation=None, arguments=None, content=None)
            return self._next(request_id, stage, turn, final=True)
        elif call is not None:
            name = (CONFIRM_OPERATION if call["wire"] == CONFIRM["function"]["name"]
                    else self.wire_to_op.get(call["wire"], call["wire"]))
            turn["awaiting"] = call["id"]
            turn["calling"] = name
            turn["calling_args"] = json.dumps(call["arguments"], sort_keys=True, ensure_ascii=False)
            arguments = self._expand({**call["arguments"], **self.constants.get(name, {})})
            result.update(kind="action", operation=name, arguments=arguments)
        elif content:
            result.update(reply=content)
        doubt_of = {"doubt_of": turn.pop("doubt_of")} if "doubt_of" in turn else {}
        if str(result["operation"] or "").startswith("memory.") or str(doubt_of.get("doubt_of")).startswith("memory."):
            turn["private"] = True
        private = bool(turn.get("private"))
        # What the person keeps in memory stays out of the trace, as in the App's (NativeTurnLoop): from the memory
        # call on, their words, the calls' arguments and the model's text.
        self._log(stage, started, reply, text=None if private else turn["text"], kind=result["kind"],
                  operation=result["operation"], arguments=call["arguments"] if call and not private else None,
                  content=None if private else content, **doubt_of)
        return result

    # ---- trace ---------------------------------------------------------------------------------------------
    def _log(self, stage: str, started: float, reply: dict[str, Any] | None, **fields: Any) -> None:
        timings = (reply or {}).get("timings") or {}
        row = {"t": _dt.datetime.now().isoformat(timespec="milliseconds"), "stage": stage,
               "ms": round((time.monotonic() - started) * 1000),
               "prompt_n": timings.get("prompt_n"), "prompt_ms": timings.get("prompt_ms"),
               "predicted_n": timings.get("predicted_n"), "predicted_ms": timings.get("predicted_ms"), **fields}
        doubt = read_doubt(reply)
        if doubt is not None:
            doubt.pop("written", None)  # the call's own text up to its weakest token: only for reading the rivals
            row["doubt"] = doubt
        if self._judged is not None and stage.startswith("turn."):
            # Only a turn's own row carries the decision model's answer: the voice thread logs here too (voice.speak).
            row["system_one"], self._judged = self._judged, None
        try:
            with self._log_lock, self.trace.open("a", encoding="utf-8") as out:
                out.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        except OSError:
            pass
