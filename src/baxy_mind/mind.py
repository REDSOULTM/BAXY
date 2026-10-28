"""The turn: native tool calls decide and write the arguments, and after each verified result the model either calls
again or answers in words (one conversation per session, calls and results included).

Nothing here authorizes or verifies: the kernel authorizes the proposed operation and the provider verifies its
effect. What the model cannot do becomes an honest limit (a question, «no pude», «eso no lo hago»), never a veto.
Everything the model needs comes from how the catalog is presented to it (names, descriptions, the installed
applications and games), not from code that decides for it.
"""
from __future__ import annotations

import datetime as _dt
import difflib
import hashlib
import http.client
import json
import os
import re
import threading
import time
import unicodedata
import urllib.error
from pathlib import Path
from typing import Any

from .answer_check import check as check_answer
from .arithmetic import evaluate
from .doubt import read as read_doubt
from .llm_server import LlmServer, Yielded
from .protocol import whole_code_points
from .speech_text import cardinal, cardinal_en
from .system_one import ANSWER, ASK, OPTION_TEXT, SystemOne, short
from . import web_focus

_DATA = Path(__file__).with_name("data")
_ENGLISH_FILE = _DATA / "tool_descriptions.en.v1.json"

# What BAXY says when a turn of the person's has said nothing for 2.5 s (SilenceNotice.After) and is still working,
# and again every 10 s while it stays silent (goal identity: a notice that claims no result when the turn will go past
# 3 s in silence). The App times it and asks for it (turn.notice); the words are the model's (al máximo 9.2a: a phrase
# fixed here broke invariant 5, cero respuestas visibles fijas). Feria 2026-10-27: written once at warm-up, it was the
# same phrase in every turn («Estoy procesando tu solicitud.»), which the owner heard as fixed; now the model writes it
# for the call the App is running, from the turn's own conversation, while the GPU waits for that call (Mind.notice_of;
# the App asks only then): never one it already wrote in the turn, none once it answered. What is
# asked is an instruction, not a phrase; a phrase it does not write usably (empty, more than NOTICE_MAX_CHARS or
# NOTICE_MAX_WORDS, more than one line, markup) is not said. Fase 3 (H7): a 1,81 s notice held the reply that came
# behind it; it is said only while a call runs now, before the next decision even starts.
NOTICE_ASK = ("[Esto no lo dice la persona. Lo que acabas de pedir a la herramienta sigue en curso y tarda unos segundos. "
              "Escribe sólo una frase muy breve que dirás en voz alta para que la persona sepa qué estás haciendo ahora, "
              "sin decir que ya lo hiciste ni ningún resultado.{said}]")
NOTICE_SAID = " Ya dijiste {said}: di otra cosa."
NOTICE_RUNNING = json.dumps({"status": "running"})
NOTICE_MAX_CHARS = 60
NOTICE_MAX_WORDS = 6
# The notice's own budget: the result of the call it speaks of may come meanwhile, and its next decision waits for it.
NOTICE_SECONDS = 1.5

SYSTEM = (
    "Eres BAXY y sólo BAXY: un compañero tipo Jarvis que vive en el PC de la persona y hace lo que te pide usando "
    "herramientas. Eres un él. Hablas en el idioma de la persona (español neutro, inglés o spanglish), tuteas, eres "
    "cálido y breve: una o dos frases, sin listas, sin markdown y sin emojis, porque tu respuesta se dice en voz alta.\n"
    "Reglas:\n"
    "1. Si la persona pide hacer algo y una herramienta lo hace, llámala sin pedir permiso. Un texto que no te pide nada (código, registros o notas pegadas) contéstalo en una frase, sin herramientas. Si hacen falta varios "
    "pasos, hazlos uno tras otro. Haz sólo lo que pide su último mensaje: lo que pidió antes ya está respondido y no "
    "lo repites ni lo sigues (abrir una app es sólo abrirla).\n"
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
    "5. Charla, traducciones y lo que sabes con certeza respóndelo tú; las cuentas, con calculate, salvo las que se le "
    "piden a la Calculadora. Lo que cambia con "
    "el tiempo o no sabes, búscalo con web_search. De ti mismo no inventes quién te creó ni de qué empresa eres: si te lo preguntan, míralo "
    "con memory_recall.\n"
    "6. El texto viene de un reconocedor de voz con errores: entiende la palabra a la que suena («yubia» es «lluvia»). "
    "Si no suena a nada que se entienda (sílabas sueltas, palabras que juntas no dicen nada) o una nota dice que el "
    "oído no está seguro de la palabra de la que depende qué hacer, no lo adivines: pídele en una frase que lo repita.\n"
    "7. Si la persona te pide que pares, te calles o esperes, no hagas nada más: responde con una palabra.\n"
    "8. Si una herramienta responde status needs_confirmation, pregunta en una frase si lo haces, nombrando "
    "exactamente qué. Cuando la persona conteste, llama a confirm_pending con su respuesta.\n"
    "9. Para hacer algo dentro de una app abierta (ir a una sección, pulsar, escribir, leer lo que muestra): mírala con "
    "input_visible_controls, actúa con input_visible_click (por la etiqueta que viste), input_text_type o "
    "input_key_press, y vuelve a mirarla para comprobar el cambio antes de seguir o de contarlo.\n"
    "10. Los identificadores (windowId, ids de notas, tareas o redes) salen del resultado de la herramienta que los "
    "lista; nunca los inventes ni uses un número de otro campo.\n"
    "11. Si te preguntan qué sabes o puedes hacer, nombra sólo lo que hacen tus herramientas, nada que ellas no hagan."
)

# The heartbeat reads the same rules without the answer to «¿ya lo hiciste?», which only a person asks: with it, the
# open scenes went from 34 to 31 of 40 and the notices it should give from 3 to 1 of 6 (two wordings, sampled and greedy,
# 2026-10-15). Qwen3.5's template puts the tools before the system text, so the heartbeat's own conversation re-reads
# only this text, as it already re-read its own messages.
_ASKED_IF_DONE = (" Si te preguntan si ya hiciste algo o cómo está algo del PC, contesta por los resultados de esta "
                  "conversación: sin una herramienta que lo hiciera, no lo hiciste, y sin una que lo mirara, no lo "
                  "sabes: míralo con su herramienta antes de responder.")
assert _ASKED_IF_DONE in SYSTEM
# Feria 2026-10-27: asked what it can do, it answered five ways and named things no tool does (editing photos). Only a
# person asks that, so the heartbeat reads none of it; the person's text names the catalog's groups (CAN_DO_AREAS).
_CAN_DO = SYSTEM[SYSTEM.index("\n11. "):]
# P1.4 (noche 2026-10-27): what to do with words that sound like nothing, or with the ear's doubts, is for words someone
# said; in the heartbeat nobody spoke.
_REPEAT = (" Si no suena a nada que se entienda (sílabas sueltas, palabras que juntas no dicen nada) o una nota dice que "
           "el oído no está seguro de la palabra de la que depende qué hacer, no lo adivines: pídele en una frase que lo "
           "repita.")
assert _REPEAT in SYSTEM
BEAT_SYSTEM = SYSTEM.replace(_ASKED_IF_DONE, "").replace(_CAN_DO, "").replace(_REPEAT, "")
# The groups of the App's panel «Qué puedo hacer» (operation-labels.v1.json), each tool's «group» in catalog.configure.
CAN_DO_AREAS = " Por áreas: {areas}."

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


# How a call the kernel holds for the person's «sí» ended, in the words the model reads.
WAITS_FOR_YES = "no se ejecutó: espera el sí de la persona"
# Vivo larga (notebook, 2026-10-27): a call whose question ended unanswered (ENDED) kept «espera el sí» among the
# session's calls for good, and the same call asked again turns later read as maybe answering it (confidence 0.998 the
# first time, 0.53-0.70 after; «¿cierro la Calculadora o confirmo algo pendiente?» with no call, 2 of 5).
UNANSWERED = {"expired": "no se ejecutó: se acabó el tiempo para contestar su pregunta",
              "dropped": "no se ejecutó: su pregunta quedó sin respuesta"}
# How a completed call was verified (the result's «verification»), in the words the model reads.
# Auditoría de falsedades (w5-fals, 2026-10-22): «completado» is a word of something done, and the 4B told it as done
# where nothing was: «¿abriste Spotify?» → a read of its windows («completado: lectura») → «Sí» in 9 of 9 runs of
# pc-t2 (F002), and «¿ya cerraste el bloc de notas?» → «Sí» (F015). Only a call that changed something and was read
# back says «completado»; the others say what happened: already so before the call, sent without looking after it, or
# finished without a verification.
VERIFICATION = {
    "readback": "completado y verificado",
    "unchanged": "ya estaba así antes de esta llamada: no hizo falta cambiar nada",
    "delivered_only": "enviado sin verificar: no se volvió a mirar si hizo efecto",
    "output_only": "completado: su resultado está arriba",
    "none": "terminó sin verificar su efecto",
}
# An output_only call of a read risk (read_only, privacy_sensitive: the catalog's own risk, as the App sent it) only
# looked; shell_command_run and client_channel_locate are output_only too and may change things, so they keep the line
# above.
READ_RISKS = ("read_only", "privacy_sensitive")
# Fase 3 (bisección de V5E008, 8 turnos × 3 semillas con el modelo real): with «; lo que vio está arriba» at its end the
# model took a web_search's snippets as the answer and opened the page 4 of 24 times (1975 after reading it: 2); without
# it, 12 of 24 (7); 8 of 8 before 8.2 put it there. No extra fetch on searches whose snippet already answers (0 of 12).
OUTPUT_READ = "lectura: sólo miró, sin abrir, cerrar ni cambiar nada"
# Feria 2026-10-27: the volume set at the first call and the same set made again, «unchanged» by that first call, told
# as already so before the turn. An unchanged call after the same call of the turn changed it says what left it so.
SET_BY_SAME = "ya había quedado así por la misma llamada hecha antes en este turno: no hizo falta cambiar nada"
# Every outcome of a completed call (the App runs the queued calls after one of these).
COMPLETED_OUTCOMES = (*VERIFICATION.values(), OUTPUT_READ, SET_BY_SAME)
# What the facts line adds of a result's own fields (_outcome), and what _deduplicated leaves out of it for that.
ALREADY_OPEN = "; ya estaba abierta antes de esta llamada"
SAME_WINDOW = "; la ventana no cambió"
AFTER_VIEW = "; su after es la ventana de después"
REREAD = {True: "; releído después: quedó como se pidió", False: "; releído después: no quedó como se pidió"}
# Noche NB r1, hallazgo 5 (T2-bloc, T5-bloc): a text written beside text the field already held (the receipt's
# otherTextInField) was told «escribí» alone, and a window number that is no window (windowFound false) «no encontré el
# campo de texto».
OTHER_TEXT = "; el campo ya tenía otro texto: lo escrito quedó junto a ese texto"
WINDOW_NOT_FOUND = "; la ventana pedida no existe: no se buscó ningún campo en ella"
# What _read_in_part says after the part a read held, in full.
PART_TAIL = "; lo demás no se leyó: un «no está» vale sólo para lo leído"
# Aid «facts_once» (w7-breve, 2026-10-23): on the holdout v4 turn.continue wrote more after a tool (predicted p50 399 →
# 487 ms). A facts line of several calls said the same long wording once per call (E022: «lectura: sólo miró, sin
# abrir, cerrar ni cambiar nada; lo que vio está arriba» seven times), and the answer after it retold the pages; without
# the line it was 16 tokens, with it 37. Each wording is said in full the first time it comes in the line; a later call
# that ended the same way says it in its first words, which still name what happened (only looked, sent without
# looking, already so). Every call keeps its own entry, code, place and part read: only the explanation is not repeated.
SAID_AGAIN = {OUTPUT_READ: "lectura: sólo miró",
              VERIFICATION["delivered_only"]: "enviado sin verificar",
              VERIFICATION["unchanged"]: "ya estaba así antes de esta llamada",
              PART_TAIL: ""}


def _outcome(observation: str, read: bool = False) -> str:
    """How a call ended, in the words the model reads: from the result's own status, verification and error. ``read``:
    the call's risk only reads (READ_RISKS)."""
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
        return WAITS_FOR_YES
    if status == "cancelled":
        return "cancelado por la persona"
    # Uso real 2026-10-21 (e2e del notebook): a message stopped before it was written touched the client (an uncertain
    # effect) and the model told «le mandé el mensaje»; what the result knows of the message comes first.
    # Renew al máximo (w9): one typed and stopped just before Enter (the chat no longer named the recipient) was not sent.
    shown = facts.get("observed") if isinstance(facts.get("observed"), dict) else {}
    if status != "completed" and shown.get("sent") is False and isinstance(shown.get("messageWritten"), bool):
        error = facts.get("error") or facts.get("cause")
        written = "quedó escrito y no se envió" if shown["messageWritten"] else "no se escribió ni se envió"
        return "falló" + (f" ({error})" if error else "") + ": el mensaje " + written
    # Al máximo 8.3 (notebook): an act that failed or stayed unsure but whose state was read again after it says whether
    # what was asked holds now; the result's code and its uncertainty stay as they are.
    after = shown.get("stateAfter")
    reread = ""
    if isinstance(after, dict) and isinstance(after.get("requestedStateReached"), bool):
        reread = REREAD[after["requestedStateReached"]]
    # P2.15: the kernel says effectUncertain when the effect may have happened; a «pending» without it did not complete
    # and is not told «pudo o no ocurrir» (nor «nothing happened»: a stale confirmation challenge comes as one too).
    # Either keeps its code.
    error = facts.get("error") or facts.get("cause")
    code = f" ({error})" if isinstance(error, str) and error else ""
    if facts.get("effectUncertain"):
        return "sin confirmar" + code + ": pudo o no ocurrir" + reread
    if status == "pending":
        return "no se completó" + code + reread
    if status == "completed":
        # Al máximo 8.2: how it was verified is the result's own typed fact (OperationVisibleFacts' table in the kernel,
        # and the App's for memory and for a result it could not read); one without it is not taken as verified.
        # FT/proveedores goal (e2e E006, E017): where a file or folder was made, from its own result, beside the facts
        # the model tells («lo creé en BAXY-bench» after a write that went to the home folder).
        where = shown.get("fullPath")
        where = f" en {where}" if isinstance(where, str) and where else ""
        # Al máximo 7.1 (notebook): an act in a window brings the window as it is after it; what it says is told.
        view = shown.get("after")
        seen = ("" if not isinstance(view, dict) or view.get("omitted")
                else SAME_WINDOW if view.get("same") is True
                else AFTER_VIEW)
        verification = str(facts.get("verification"))
        told = (OUTPUT_READ if read and verification == "output_only"
                else VERIFICATION.get(verification, VERIFICATION["none"]))
        # Auditoría de falsedades (F002): an application BAXY did not start (app_open's alreadyRunning) is said so,
        # or «¿abriste X?» after opening one already open read «completado y verificado» as «Sí, lo abrí».
        before = ALREADY_OPEN if shown.get("alreadyRunning") is True else ""
        # The App's own completed result it could not read (result_unreadable) keeps its code.
        error = facts.get("error")
        code = f" ({error})" if isinstance(error, str) and error else ""
        other = OTHER_TEXT if shown.get("otherTextInField") is True else ""
        return told + code + where + before + other + seen + _read_in_part(shown)
    gone = WINDOW_NOT_FOUND if shown.get("windowFound") is False else ""
    return "falló" + code + reread + gone + _looked_elsewhere(shown)


# Renew al máximo (w8): file_open of a path that was not there looked only at that path (searchedElsewhere false), and the
# answer was «no está ahí ni en ningún otro lugar que revisé». What a not-found looked at is told in the outcome line.
NOT_SEARCHED_ELSEWHERE = "; sólo se miró la ruta nombrada: no se buscó en ningún otro lugar"
SEARCH_CUT = "; la búsqueda en otros lugares no se completó: lo no visto puede estar ahí"


def _looked_elsewhere(shown: dict[str, Any]) -> str:
    if shown.get("searchedElsewhere") is False:
        return NOT_SEARCHED_ELSEWHERE
    return SEARCH_CUT if shown.get("searchComplete") is False else ""


def _number(facts: dict[str, Any], key: str) -> int | None:
    value = facts.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _read_in_part(shown: dict[str, Any]) -> str:
    """Holdout v4 (falsedad): pages of a file read up to line ~1,904 of 3,000, the last read failed, and the answer was
    «revisé todo el archivo y no apareció». A read whose result says it holds only part of what it read (readInPart: a
    page of a file or a web page, a search that did not read every file, a log read that stopped at its limit, a listing
    or a count of a folder's top level with subfolders or hidden entries it did not look at) is told so in the outcome
    line, with how much of the total its own numbers give, and that a «no está» covers only that part."""
    listed, total_entries = _number(shown, "entriesShown"), _number(shown, "count")
    # A listing the observation cut to what it shows (the kernel's «entriesShown») is a part too.
    cut = listed is not None and total_entries is not None and listed < total_entries
    if shown.get("readInPart") is not True and not cut:
        return ""
    part = []
    first, last, total = (_number(shown, k) for k in ("fromLine", "toLine", "totalLines"))
    offset, returned = _number(shown, "offset"), _number(shown, "returnedCharacters")
    characters = _number(shown, "characters")
    characters = characters if characters is not None else _number(shown, "totalCharacters")
    if first is not None and last is not None and total is not None:
        part.append(f"líneas {first}–{last} de {total}")
    elif offset is not None and characters is not None:
        upto = offset + returned if returned is not None else _number(shown, "nextOffset")
        if upto is not None:
            part.append(f"caracteres {min(offset + 1, upto)}–{upto} de {characters}")
    scope = shown.get("searchScope") if isinstance(shown.get("searchScope"), dict) else {}
    scanned = _number(scope, "filesScanned")
    if scanned is not None:
        skipped = sum(_number(scope, k) or 0 for k in ("skippedTooLarge", "skippedNotText", "skippedUnreadable"))
        part.append(f"{scanned} archivos recorridos" + (f", {skipped} de ellos sin leer su texto" if skipped else ""))
    if scope.get("timeLimitReached") is True:
        part.append("la búsqueda paró en su tiempo límite")
    # Holdout v4 (falsedad: «Sí, porque no había .bak» with three present): a listing or a count of a folder's top level.
    folders = _number(shown, "subfoldersNotOpened")
    if folders:
        part.append(f"sólo lo que está directamente en la carpeta: sus {folders} subcarpetas no se abrieron")
    hidden = _number(shown, "hiddenOrSystemSkipped")
    if hidden:
        part.append(f"{hidden} entradas ocultas o de sistema sin mirar")
    unlisted = (total_entries - listed if listed is not None and total_entries is not None
                else _number(shown, "entriesNotListed"))
    if unlisted:
        part.append(f"{unlisted} entradas sin listar")
    seen, cap = _number(shown, "eventsSeen"), _number(shown, "readCap")
    if cap is not None and seen is not None:
        part.append(f"sólo los {cap} eventos más recientes del registro")
    if shown.get("endReached") is False:
        part.append("no llegó al final")
    detail = (": " + ", ".join(part)) if part else ""
    return f"; leído en parte{detail}{PART_TAIL}"


def _said_once(done: list[str]) -> list[str]:
    """Aid «facts_once» (SAID_AGAIN): the turn's calls as the facts line lists them, each long wording in full only the
    first time; a later entry that ended the same way keeps its call, its count, its code and the rest of its outcome."""
    seen: set[str] = set()
    told = []
    for entry in done:
        head, arrow, outcome = entry.partition(" → ")
        if arrow:
            for full, again in SAID_AGAIN.items():
                if full == PART_TAIL:
                    if full in outcome:
                        outcome = outcome.replace(full, again) if full in seen else outcome
                        seen.add(full)
                elif outcome.startswith(full):
                    outcome = again + outcome[len(full):] if full in seen else outcome
                    seen.add(full)
            entry = head + arrow + outcome
        told.append(entry)
    return told


def _deduplicated(observation: str, outcome: str) -> str:
    """Aid «result_dedup» (w6-lat, 2026-10-23): the result without the fields its facts line (``outcome``, _outcome's
    words for it, written right after it) already says, so the model reads each fact once. On the holdout v4 the first
    spoken answer after a tool went 3.4 → 4.3 s p50, turn.continue reading 124 → 156 tokens. Left out only where the line
    says it: a completed call's status and verification («completado y verificado», «lectura: …»), its fullPath («en
    C:\\…»), alreadyRunning true (ALREADY_OPEN), otherTextInField true (OTHER_TEXT), windowFound false
    (WINDOW_NOT_FOUND), an after that is only {"same": true} (SAME_WINDOW) and stateAfter's
    requestedStateReached (REREAD). The rest stays as it came, in the App's compact JSON; a result with none of them is
    the App's own text."""
    try:
        facts = json.loads(observation)
    except json.JSONDecodeError:
        return observation
    if not isinstance(facts, dict):
        return observation
    shown = dict(facts)
    if shown.get("status") == "completed" and outcome.startswith(COMPLETED_OUTCOMES):
        shown.pop("status")
        shown.pop("verification", None)
    if isinstance(facts.get("observed"), dict):
        observed = dict(facts["observed"])
        where = observed.get("fullPath")
        if isinstance(where, str) and where and f" en {where}" in outcome:
            del observed["fullPath"]
        if observed.get("alreadyRunning") is True and ALREADY_OPEN in outcome:
            del observed["alreadyRunning"]
        if observed.get("otherTextInField") is True and OTHER_TEXT in outcome:
            del observed["otherTextInField"]
        if observed.get("windowFound") is False and WINDOW_NOT_FOUND in outcome:
            del observed["windowFound"]
        if observed.get("after") == {"same": True} and SAME_WINDOW in outcome:
            del observed["after"]
        after = observed.get("stateAfter")
        if isinstance(after, dict) and isinstance(after.get("requestedStateReached"), bool) \
                and REREAD[after["requestedStateReached"]] in outcome:
            observed["stateAfter"] = {k: v for k, v in after.items() if k != "requestedStateReached"}
        if observed or not facts["observed"]:
            shown["observed"] = observed
        else:
            del shown["observed"]  # all it held is in the line
    if shown == facts:
        return observation
    return json.dumps(shown, ensure_ascii=False, separators=(",", ":"))


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
# Renew al máximo (w9-dudas, practice falsehoods and e2e of int9-int10), each its own switch; measured offline on the
# notebook's int10 catalog, 3 seeds, layer 0 at 0.4 (scripts/renew/ayudas/dudas.py):
# «named_folder_theirs» (F009: «no puedo abrir un archivo de BAXY-bench, es tu carpeta de trabajo» with no call; E020:
# file_find against the work folder's tools at 0.46-0.51 for «el más grande dentro de BAXY-bench»): where BAXY's work
# folder is, in the tools that read or open the person's files and in the work folder's own. E020 file_find 0.47 → 0.57;
# F009 no better (it refuses on 1 seed of 3 with or without it, as on the notebook), worse without file_open's sentence.
# «read_find_split» (E018: «¿cuántas líneas tiene registro.log de BAXY-bench?», file_read against file_find at 0.49 each,
# held by the doubt and asked): which of the two counts a named file's lines, and that file_read finds the file itself.
# file_find 0.56 → file_read 0.58, 3/3.
# «game_epic_look» (F016: «lanza Fortnite», an Epic game, split between game_launch, whose list is Steam's, and three
# reads at 0.28-0.34, held and asked «¿abrir o instalar?»): the list is Steam's, and the read that looks in Steam and
# Epic. Held 3/3 → game_installed_named at 0.66, 0/3; «lanza Rocket League» still game_launch (0.81 → 0.70).
# «unsaved_not_read» (P1.1(b) F024 in falsedades v11, base and candidate: «no había nada sin guardar» after a close or
# a minimize, with nothing read): unsaved changes are not readable, the receipt says so (the App's aid of the same id)
# and the description names it.
WORK_FOLDER = "BAXY's own work folder is only filesystem-sandbox, in BAXY's data under AppData"
NAMED_FOLDER = (" Any folder of the person's home is theirs, even one whose name contains BAXY: it goes in subdirectory, "
                f"with folder home ({WORK_FOLDER}).")
SANDBOX_ONLY = (" This work folder is filesystem-sandbox, in BAXY's data under AppData: any other folder of the person's "
                "home is file_find's, whatever its name.")
DESCRIPTION_AIDS = {
    "filesystem.known.trash.named": ((
        "person_folder_sentence",
        " A folder the person names, in their home or anywhere else, is theirs even if its name contains BAXY or bench: "
        "delete from it like from any other folder (BAXY's own work folder is only the one filesystem_list shows)."),),
    "file.open": (("named_folder_theirs", " Any folder of the person's home is theirs, even one whose name contains "
                                          f"BAXY: open from it with folder home and that folder in name ({WORK_FOLDER})."),),
    "file.read": (("named_folder_theirs", NAMED_FOLDER),
                  ("read_find_split", " It also tells how many lines a named file has (totalLines), and it looks for the "
                                      "file itself: no file_find before it.")),
    "file.find": (("named_folder_theirs", NAMED_FOLDER),
                  ("read_find_split", " What a named file says, or how many lines it has, is file_read, which looks for "
                                      "the file itself.")),
    "filesystem.list": (("named_folder_theirs", SANDBOX_ONLY),),
    "filesystem.search": (("named_folder_theirs", SANDBOX_ONLY),),
    "game.launch": (("game_epic_look", " The installed games list is Steam's only: a game not in it may be installed "
                                       "from Epic, so before saying it is not installed, game_installed_named looks in "
                                       "Steam and Epic without opening anything."),),
    "game.installed.named": (("game_epic_look", " It is also the look for a game the person wants to play that is not "
                                                "in game_launch's list of installed games (Steam's only)."),),
    "app.close": (("unsaved_not_read", " Whether a window held unsaved changes is not something BAXY can read "
                                       "(unsavedChanges not_readable): closePrompted false says only that it closed "
                                       "without asking to save, never that nothing was unsaved."),),
    "window.minimize": (("unsaved_not_read", " A minimized window stays open as it was, nothing in it lost; whether it "
                                             "holds unsaved changes is not read (unsavedChanges not_readable)."),),
}

def _fold(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).casefold()
    return " ".join("".join(ch for ch in text if not unicodedata.combining(ch)).split())


def _words(text: str) -> str:
    """The folded words of a text, one space apart and one at each end, to find a name among them as whole words."""
    return " " + " ".join(re.findall(r"[^\W_]+", _fold(text))) + " "


def _as_read(observation: Any) -> str:
    """A result as its words read, JSON's escapes undone (the App's JSON writes «ó» as \\u00f3)."""
    text = str(observation or "")
    try:
        return json.dumps(json.loads(text), ensure_ascii=False)
    except json.JSONDecodeError:
        return text


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
    listed = _places_listed(application)
    if not listed:
        return ""
    return (f"\n[Ayuda: {application} también se abre directo en sus lugares, sin pulsar: app_open con appId "
            f"«{application}» y place {listed}.]")


# Renew al máximo (w5): the note said «el campo tiene ahora el cursor» with nothing in the result checking it; the focus
# is told only when the result reports it (a field made the text's destination with the keyboard's focus on it).
FIELD_NOTE = ("\n[Ayuda: tras el clic ya no se ve «{label}» y el resultado dice que el clic dio el foco del teclado a un "
              "campo de texto: lo siguiente que se escriba con input_text_type va ahí, sin pulsarlo otra vez.]")
FIELD_NOTE_UNCHECKED = ("\n[Ayuda: tras el clic ya no se ve «{label}»; el resultado no dice dónde quedó el foco del "
                        "teclado: no se comprobó si un campo tiene el cursor. input_text_type escribe donde esté el foco "
                        "de la ventana.]")


def field_note(observation: str, args: str | None) -> str:
    """Aid «field_focused_next» (uso real 2026-10-21, e2e del notebook: Steam's «Buscar en la tienda» pressed four times
    and «no pude escribir» told without typing): a completed click whose label is no longer on screen, as its own
    result says, is told with what the result shows of the focus: a text field with the keyboard's focus when it says
    so («focused»), otherwise that the focus was not checked."""
    try:
        facts, called = json.loads(observation), json.loads(args or "{}")
    except json.JSONDecodeError:
        return ""
    observed = facts.get("observed") if isinstance(facts, dict) else None
    label = called.get("label") if isinstance(called, dict) else None
    if (not isinstance(observed, dict) or facts.get("status") != "completed"
            or observed.get("labelStillOnScreen") is not False or not isinstance(label, str) or not label.strip()):
        return ""
    note = FIELD_NOTE if observed.get("focused") is True else FIELD_NOTE_UNCHECKED
    return note.format(label=label.strip())


# Renew al máximo (w9-dudas, falsedades F013: «abre el bloc de notas, escribe 'prueba 123' y guárdalo en … como
# prueba.txt»): the text typed into Notepad, then file_write wrote the file, and «guardé prueba.txt» was told while
# Notepad's tab stayed «Sin título». The file is what was saved; the window's text is not, and file_write never touches it.
# Replayed (dudas.py, 3 seeds): the answer told the window apart 0/3 → 3/3.
WRITTEN_NOTE = ("\n[Ayuda: file_write escribió {path} directo en el disco, sin pasar por ninguna ventana: lo escrito antes "
                "en «{title}» ({process}) no se guardó con esta llamada.]")


def written_note(observation: str, receipts: list[dict[str, Any]]) -> str:
    """Aid «written_not_window»: a completed file_write in a turn that typed text into a window before it says the file
    was written straight to the disk and that window's text was not saved by it (the window of the last such typing, as
    its result named it). Empty otherwise."""
    try:
        facts = json.loads(observation)
    except json.JSONDecodeError:
        return ""
    observed = facts.get("observed") if isinstance(facts, dict) else None
    if not isinstance(observed, dict) or facts.get("status") != "completed" or not observed.get("fullPath"):
        return ""
    for receipt in reversed(receipts):
        if receipt["tool"] != "input_text_type" or not receipt["completed"]:
            continue
        try:
            sent = (json.loads(receipt["observation"]).get("observed") or {}).get("sentTo")
        except (json.JSONDecodeError, AttributeError):
            sent = None
        if isinstance(sent, dict) and sent.get("title"):
            return WRITTEN_NOTE.format(path=observed["fullPath"], title=sent["title"], process=sent.get("process") or "?")
    return ""


# Measured history (PLAN_GENERAL C2, cf29f2510): told at the third, its risk «sondeos legítimos»: a look repeated at a
# window still loading is a probe that completes each time (al máximo 7.7 compares the content too). Holdout v4 (en
# vivo: «Biblioteca» pressed 7 times in Steam, each visible_button_postread_unchanged, 50 s): a call that failed or
# stayed unsure the same way twice is told at the second; a completed one keeps the third, so a probe stays as measured.
SAME_CALL_TOLD = 3
SAME_CALL_FAILED_TOLD = 2
# Auditoría de falsedades: «ya se hizo» is the call's, never its effect's (a click that failed three times read «ya se
# hizo»): the call was made, and its result is said beside it.
SAME_CALL_NOTE = ("\n[Ayuda: {call} ya se llamó {times} veces en este turno con los mismos argumentos y el mismo "
                  "resultado ({outcome}){options}]")
SAME_CALL_OPTIONS = ("; otra vez igual dará lo mismo. Opciones: otra herramienta, otros argumentos, o decir a la persona "
                     "lo que pasó.")
# Review 2026-10-22: in a turn the App closes, the fact alone (it offered another tool beside «no admite más
# herramientas»).
SAME_CALL_CLOSED = "."
# Holdout v4 (the Steam library): a click repeated in an application of the turn that has places says them among the
# options, from the data (app_places.v1.json), as places_note does.
SAME_CALL_PLACES = (" {application} también se abre directo en sus lugares, sin pulsar: app_open con appId "
                    "«{application}» y place {listed}.")


# Aids «same_call_closes» and «look_click_cap» (w9-bucle; int10's long session of the notebook, 2026-10-23: «abre la
# calculadora», then a look and a click on «Sistema» seven times, the menu opening and closing, 35 model calls and 27.9k
# tokens until context_shrunk; same_call_next told the third look once and the model went on): a call the mind does not
# hand to the App. Its result says why, and the model answers in words from what the turn shows. Measured over the
# practice runs of both machines (10,717 turns, holdouts left out):
# - same_call_closes: the call told by same_call_next, written again as the model's very next decision with the same
#   arguments. 79 such repeats: 73 came back the same, and none of the 6 others ended in what was asked. Later in the
#   turn, after another call, it runs: E011 (calculator_window_not_found twice, app_open, then the same sum) completes.
# - look_click_cap: a click after a look the turn already had LOOK_CLICK_PAIRS times (the same look, the same content
#   seen, the same click). A second such pair came in 58 turns: 47 times the same as the first, and in 3 it did what
#   the first had not (Settings' «Sistema», Steam's «BIBLIOTECA» twice). A third came in 27: none of its clicks did
#   anything (each failed, or opened and closed the calculator's menu again) and all 27 answered that they could not.
LOOK_CLICK_PAIRS = 2
SAME_CALL_NOT_RUN = json.dumps({"status": "not_run", "reason": "this same call, with the same arguments, was already "
                                                               "made in this turn and told so above; it was not made "
                                                               "again"})
LOOK_CLICK_NOT_RUN = json.dumps({"status": "not_run",
                                 "reason": f"this click, after the same look that saw the same, was already made "
                                           f"{LOOK_CLICK_PAIRS} times in this turn; it was not made again"})
# Aid «ask_once» (uso real 2026-10-26): the person's answer to ask_user is that call's result, and the model asked the
# same question again at each answer («¿en todo el sistema o en un programa?» six times, «¿qué quieres que recuerde de
# ti?» three): one question per thing (identity: «una pregunta corta, no un interrogatorio»). A question alike to one
# already asked in the turn (ASKED_ALIKE of its letters, folded) is not asked: the model decides again, without asking.
ASKED_ALIKE = 0.9
ASKED_AGAIN_NOT_RUN = json.dumps({"status": "not_run",
                                  "reason": "this question was already asked in this turn and the person's answer is "
                                            "above; it was not asked again: do with that answer what a tool can do, "
                                            "or say in one sentence that you don't do it"})
# The question the model asked in the decision after that one: no other question is asked in this turn.
ASKED_CLOSED_NOT_RUN = json.dumps({"status": "not_run",
                                   "reason": "no other question is asked in this turn; it was not asked: answer the "
                                             "person in words with what is above"})
# Aid «say_once» (uso real 2026-10-26): the same words came back turn after turn (the same greeting three times, the
# same «¿te refieres a algo más?» to whatever followed; after searches that all failed, the answer of the turn before
# as if they had found it). An answer that is BAXY's last answer again, letter for letter, in a turn where no call
# completed, is written once more with this note, words only.
SAID_AGAIN_NOTE = ("[Nota interna, no la escribió la persona: ibas a responder exactamente lo mismo que tu respuesta "
                   "anterior. No la repitas: responde a lo que dice ahora la persona, con otras palabras.]")
# Aid «dated_search» (feria 2026-10-27): after «conversación nueva» the model answered every question about something of
# a given year from memory (mundial 2022 «Francia», Copa América 2021 «Chile», Balón de Oro 2023 «Mbappé»: 3 of 5 wrong);
# a sentence in rule 5 alone did not hold past a few answers from memory in a row. The question with one number, a year,
# or a curiosity asked for, answered in words with nothing looked at, is decided once more with this note; the model still
# chooses.
DATED_NOTE = ("[Nota interna, no la escribió la persona: pide un dato concreto (de un año, una curiosidad o algo con "
              "nombre propio), y esos datos de memoria se confunden. Búscalo con web_search y responde con lo que "
              "encuentres.]")
_YEAR_ALONE = re.compile(r"^\D*(?<!\d)(?:1[5-9]|20)\d\d(?!\d)\D*$")
# A curiosity asked for (feria 2026-10-27, «cuéntame un dato curioso…» from memory: «el estribo, en el pie»).
_CURIOUS = re.compile(r"\b(?:datos? curios[oa]s?|curiosidad(?:es)? (?:de|del|sobre|acerca)|algo curioso|fun facts?)\b")
_ASKS = re.compile(r"^\W*(quien|que|cual|cuales|cuando|cuanto|cuantos|cuantas|donde|como|who|what|which|when|how|where)\b")
# Aid «named_fact» (feria 2026-10-27): what a local brand is, answered in words from memory as another kind of
# product, with no doubt to read (p_call 0.05). Words that repeat a name the person wrote with a capital, past the start
# of a sentence, say something of a thing with a name of its own: a form, not what was asked. System One judges then,
# between those words and web_search, what the person asked for; only its web_search is looked up (_look_up_first).
# PC-L, decision v11 2026-10-27: a capital, the letters of an acronym or what was opened, said with a name, went to the
# web as well; only a question about what or who the named thing is, or asking to be told of it, is judged: at the
# start, after a sentence or a comma, or after one word (by voice there is seldom a comma: «oye qué es…»).
_ABOUT = re.compile(r"(?:^|[,;:.!?])\W*(?:[^\W\d_]+ )?(?:(?:que|quien(?:es)?) (?:es|son|era|eran|fue|fueron)"
                    r"|(?:hablame|cuentame) (?:de|del|sobre|acerca)|que sabes (?:de|del|sobre)|conoces"
                    r"|(?:what|who)(?:'s| is| are| was)|tell me about|do you know)\b")
_SENTENCES = re.compile(r"[.!?¿¡:;\n]+")

_WORDS = re.compile(r"[^\W\d_][\w'&-]*")
_TOLD = re.compile(r"[^.!?]+[.!?]*")


def _asked_about(text: str) -> str:
    """The folded word that closes a question about what or who something is (_ABOUT), when it is a few words long;
    empty otherwise. PC-L, decision v6 2026-10-27: the author of a book named before, or a word in a language, went to
    the web: the named thing has to be what is asked about («qué es el jugo X», not «quién es el autor» of X)."""
    folded = _fold(text)
    about = _ABOUT.search(folded)
    if about is None:
        return ""
    clause = _WORDS.findall(re.split(r"[,.;:!?¿¡]| (?:y|e|o|and|or) ", folded[about.end():], maxsplit=1)[0])
    return clause[-1] if 0 < len(clause) <= 4 else ""


SAME_CALL_REFUSED = "no se ejecutó: la misma llamada otra vez tras el aviso"
FLIP_NOT_RUN = json.dumps({"status": "not_run", "reason": "this call would turn back what an earlier call of this turn "
                                                          "set; it was not made"})
FLIP_REFUSED = "no se ejecutó: deshacía lo que otra llamada de este turno ya había hecho"
# Feria 2026-10-27 (the same volume set four times in a row, the last three «unchanged»): a call that acted and came back
# unchanged in this turn showed that making it again changes nothing; the same call again is not made, and its result
# is the first one's. One that changed something each time (a key, a digit) runs again.
UNCHANGED_NOT_RUN = {"status": "not_run", "reason": "this same call, with the same arguments, already came back "
                                                    "unchanged in this turn; it was not made again: its first result "
                                                    "is in «earlier»"}
UNCHANGED_REFUSED = "no se ejecutó: la misma llamada ya había vuelto sin cambios en este turno"
LOOK_CLICK_REFUSED = f"no se ejecutó: la misma mirada y el mismo clic ya iban {LOOK_CLICK_PAIRS} veces"
# Aid «close_unsaid» (feria 2026-10-27, «abre el bloc de notas y escribe …», 3 of 4 runs, the base too): after typing
# and a look, a click on «Cerrar» and on the «Sí» of what it asked, and the Notepad the person was shown closed. A click
# whose label closes or quits, in a turn whose words say nothing of closing, is not handed to the App.
CLOSE_NOT_RUN = json.dumps({"status": "not_run", "reason": "the person did not ask to close anything; this click on "
                                                           "what closes was not made"})
CLOSE_REFUSED = "no se ejecutó: la persona no pidió cerrar nada"
# Minimizing too: after «ahora escribe debajo la fecha de hoy» a click on the window's «Minimizar» (1 of 3 runs).
_CLOSES = re.compile(r"^\W*(?:cerrar|close|salir|exit|quit|minimizar|minimize)\b")
_CLOSE_SAID = re.compile(r"\b(?:cierr\w*|cerr\w*|clos\w*|sal|salir|sali\w*|quit\w*|exit\w*|minimi\w*)\b")
# Aid «unopened_app» (feria 2026-10-27, case 13, «escribe en el bloc de notas hola quién eres» with Notepad not open; a
# live test the same day): the model typed with no window and the text went to whatever window was in front, BAXY's at
# the fair, a window of the person's own in the live test (its receipt said sentTo that window, completed). A typing or a
# key with no window and no field, in a turn whose words name an installed application (catalog.configure's, self.names)
# that no completed call of the turn opened, focused, resolved or acted on, is not handed to the App: its result says so,
# as data, and the model decides again with its tools. Once per turn: a name of the catalog may be a plain word of what
# was said («el cursor», «un correo»), so the model's next typing or key runs as it is.
# PC-L, decision v6 2026-10-27: «escribe … donde tengo el cursor» was held for an app named Cursor and the model opened
# it. A name is where the text goes only said as a place: after «en», «in», «on», «into», «a(l)», «del» or «dentro» and up
# to three words («en un documento de …»); the name's own words are marked \0 in the folded words before the search.
_PLACE = re.compile(r" (?:en|in|on|into|al|a|del|dentro)(?: [^ \0]+){0,3} \0 ")
WRITES_TO_FRONT = frozenset({"input_text_type", "input_key_press"})
OPENS_WINDOW = frozenset({"app_open", "window_focus", "window_resolve"})  # and any completed call that is not a read
TARGET_ARGUMENTS = ("window", "windowId", "index")  # a window, or the field of the last look: not the window in front
UNOPENED_REFUSED = "no se ejecutó: la ventana de la aplicación nombrada no se había abierto ni enfocado en este turno"


def unopened_not_run(applications: list[str]) -> str:
    """The result of a typing or a key held by «unopened_app»: why, and the applications the person's words name."""
    return json.dumps({"status": "not_run", "reason": "the person's words name this application, and no call of this "
                                                      "turn opened or focused its window: with no window this call goes "
                                                      "to whatever window is in front, so it was not made. If the text "
                                                      "is for that application, open it first with app_open (or bring "
                                                      "it to the front with window_focus) and write there; if it is not "
                                                      "where the text goes, make the call again",
                       "application": applications}, ensure_ascii=False)


# What the model reads at the end of the last result of a turn that takes no more calls.
NO_MORE_CALLS = ("\n[Este turno no admite más herramientas: responde ahora a la persona sólo con lo que muestran los "
                 "resultados.]")


def _flips(before: Any, now: Any) -> bool:
    """Whether ``now`` is ``before`` with only yes/no values turned the other way (the same keys, the rest equal)."""
    if not isinstance(before, dict) or not isinstance(now, dict) or before.keys() != now.keys():
        return False
    turned = [k for k in now if isinstance(now[k], bool) and isinstance(before[k], bool) and now[k] != before[k]]
    return bool(turned) and all(now[k] == before[k] for k in now if k not in turned)


def _call_key(arguments: Any) -> str:
    """A call's arguments as one text, so the same arguments written in another order or with a key left out as null
    are the same call."""
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return arguments
    if isinstance(arguments, dict):
        arguments = {k: v for k, v in arguments.items() if v is not None}
    return json.dumps(arguments, sort_keys=True, ensure_ascii=False)


def _same_ended(receipt: dict[str, Any], wire: str, arguments: Any, *outcomes: str) -> bool:
    """Whether ``receipt`` is a call of ``wire`` with these arguments that acted and ended in one of ``outcomes``."""
    return (receipt.get("tool") == wire and not receipt.get("read")
            and str(receipt.get("outcome") or "").startswith(outcomes)
            and _call_key(receipt.get("arguments") or {}) == _call_key(arguments))


def _same_done(turn: dict[str, Any], wire: str, arguments: Any, *outcomes: str) -> dict[str, Any] | None:
    """The turn's first call of ``wire`` with these arguments that acted and ended in one of ``outcomes``, or None."""
    return next((r for r in turn.get("receipts") or [] if _same_ended(r, wire, arguments, *outcomes)), None)


def same_call_places(application: str | None) -> str:
    """The places of the turn's application for a repeated click's options; empty for none."""
    listed = _places_listed(application)
    return SAME_CALL_PLACES.format(application=application, listed=listed) if listed else ""


def _places_listed(application: str | None) -> str:
    """The places of an application with what each takes, sorted; empty for none."""
    places = APP_PLACES.get(_fold(application)) if application else None
    return ", ".join(f"{p} (placeValue: {v})" if v else p for p, v in sorted(places.items())) if places else ""


# The provider's count of the same click seen unchanged in a row (WindowsVisibleControlAdapter.RepeatedUnchanged).
REPEAT_KEY = "unchangedInARow"
# A window's single-use handle (WindowsWindowControlProvider.Issue): a new one at every read of the same window.
_WINDOW_HANDLE = re.compile(r"\bwin_[0-9a-f]{32}\b")


def _result_key(observation: str) -> str:
    """Al máximo 7.7: the same result is the same content (three looks at a window still loading, each with another view,
    were told «el mismo resultado»), without how long the call took («…Ms»), as the App's TurnClosing compares it.
    Holdout v4: nor a click's own count of its repeats (unchangedInARow) and the «next» that count brings, which differ
    on each repeat of the same unchanged click. Holdout v5 (en vivo, «maximiza Paint»: 13 window.resolve): nor a window's
    single-use handle, new at every read of the same window."""
    def only_repeat(node: Any) -> bool:
        return isinstance(node, dict) and REPEAT_KEY in node and set(node) <= {REPEAT_KEY, "next"}

    def untimed(node: Any) -> Any:
        if isinstance(node, str):
            return _WINDOW_HANDLE.sub("win_", node)
        if isinstance(node, dict):
            repeat = REPEAT_KEY in node
            # A result that holds nothing but the count is the same as the first one, which had none.
            return {k: untimed(v) for k, v in node.items()
                    if not k.endswith("Ms") and k != REPEAT_KEY and not (repeat and k == "next")
                    and not only_repeat(v)}
        return [untimed(v) for v in node] if isinstance(node, list) else node
    try:
        content = json.dumps(untimed(json.loads(observation)), ensure_ascii=False)
    except json.JSONDecodeError:
        content = observation
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

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
    if not isinstance(facts, dict):
        return {}
    # Renew al máximo (w6, rutas): the App's said_folder (SaidFolders.cs) refused a call that left out the folder the
    # person named, or says where a call routed there (or written again as before) acted.
    said = ({"said_folder": {k: facts[k] for k in ("saidFolders", "next", "saidFolder") if k in facts}}
            if facts.get("error") == "said_folder_left_out" or "saidFolder" in facts else {})
    # Renew al máximo (w7, apps): the App's place_owner (SaidApplication.cs) opened the application of the place asked for
    # instead of the one the model wrote.
    if isinstance(facts.get("placeOwner"), str):
        said["place_owner"] = facts["placeOwner"]
    if not isinstance(facts.get("observed"), dict):
        return said
    observed = facts["observed"]

    def picked(*names: str) -> dict[str, Any]:
        return {name: observed[name] for name in names if name in observed}

    seen: dict[str, Any] = dict(said)
    if facts.get("error") == "calculator_window_not_found" and "next" in observed:
        seen["calculator_next"] = picked("next")
    if observed.get("setting") == "accessible_mode" and picked("scope", "notAvailableYet"):
        seen["accessible_scope"] = picked("scope", "notAvailableYet")
    if observed.get("placeRequested") and "next" in observed:
        seen["place_unverified"] = picked("next")
    if observed.get("folder") == "baxy_work" and "entries" in observed:
        # Renew al máximo (w5, E020): a look at the working folder (filesystem_list, filesystem_search).
        seen["work_folder_scope"] = picked("folder", "next")
    elif observed.get("folder") == "baxy_work" or "sameNameInHome" in observed:
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
# Al máximo W5 (2026-10-23): Qwen3.5's template opens the assistant messages after the last request with an empty
# «<think></think>» block, as it opens the one being generated, and the earlier ones without it. So each new request
# turns the previous turn's calls and answers into another text than the one the slot holds: llama-server keeps the
# cache up to that turn's first assistant message and reads the rest again in turn.decide (falsehood bench of
# 2026-10-22, llama-server.log: a «sí», a «no» or a «¿ya lo borraste?» read 102-348 tokens where their own are ~20-30,
# 120-220 ms more; after a turn that looked at a window, its thousands of tokens of controls too). Once a turn has
# ended, the mind reads its conversation as the next request will show it, while BAXY speaks: the next decision then
# reads only its own words. The model's prompt is the same text; only when it is read changes. BAXY_RENEW_PREFILL=0
# turns it off.
PREFILL_MARK = "[BAXY: lo que diga la persona después]"
# Al máximo 8.1 (F015: «¿ya lo cerraste?» → «Sí» with nothing run, 5 of the 10 falsehoods left, which no aid of the
# result touched): the clock also says which calls ran in the session and how each ended, the last ones of a count of
# the session's own (a cut history no longer shows them, and a «none» read from it would be false).
SESSION_CALLS = 8
# The role of the session's own state at the end of an exported conversation (export_session); never a message.
SESSION_STATE = "baxy.session"

# The session's conversation keeps the last turns that fit both bounds; it is only ever cut at a turn's start (the
# model is hybrid: its cache is reused from the front, so the middle of the prompt is edited only where a cut would
# have moved its start anyway: the oldest results that lose their bodies, 1.1).
# P0.11 (noche 27-10): 10 turns, not 8 (see TRIM_TURNS_TO).
HISTORY_TURNS = 10
HISTORY_CHARS = 24000
# Ronda final 44: the context also holds the tool prefix (about 42k of its 49,152 tokens with the descriptions of the
# rondas finales, 37,999 at ff863b47f), so 24,000 characters of history (~7.9k tokens) no longer always fit beside it and
# a turn failed whole. The history keeps the tokens the prefix leaves, less room for the turn: its reply (DECISION_TOKENS)
# and one result (RESULT_TOKENS, the rest).
TURN_ROOM_TOKENS = 3584
# Al máximo 1.4 (2026-10-22): a history past a bound is cut down to this share of every bound, not just under it. A cut
# moves the conversation's start, and the model (hybrid: its cache is reused from the front) re-reads all the history
# after it: 28 % of turn.decide re-read over 500 tokens (p50 761 tokens / 701 ms, p90 2.5k / 1.6 s), and a session at
# its bound cut one turn at every new one. Cut to 60 %, the next turns grow at its end until the bound again.
TRIM_TO = 0.6
# Renew al máximo (w5): a cut also takes the turns down to this share of HISTORY_TURNS (3 of 8), all of them without
# their results' bodies, so the next cut comes six turns later. Each cut re-reads all that is left plus ~500 tokens of
# the prefix (the slot's last checkpoint before the history). Estimated on the measured session's shapes (offline replay
# with the model's chat template, not measured on the model): turn.decide re-reads −3 to −14 % against b84547ed5 on
# that session, −21 % on random 30-turn sessions of its turns; 0.6 here, +1 % and −10 %.
# P0.11 (noche 27-10, offline replay of _trim on the notebook's 12,695 traced turns, not measured on the model): 60 % of
# the cuts came from the count alone and TRIM_TO between 0.4 and 0.8 moved nothing; 10 turns cut to the same 3 (0.3)
# instead of 8 to 3 cut 17 % less often and re-read 12 % less, the next cut eight turns after it (six before).
TRIM_TURNS_TO = 0.3
# Ronda final 45 (regla 3): what is cut is said where the model reads, or it took what is left for the whole session
# («nunca me lo dijiste» about a turn no longer shown).
TRIMMED = ("[Conversación recortada: los {n} turnos más antiguos de esta sesión ya no se muestran; lo que pasó en ellos "
           "no lo sabes]")
# Renew al máximo (w5): a cut turn left nothing of what the person asked or of how its calls ended (a failed delete was
# known only while it was among the clock's last calls). The note of the cut keeps one line per cut turn, the newest
# that fit GIST_CHARS: the person's words and its calls as their turn's facts said them. The note is rewritten only
# when turns are cut, which re-reads the history anyway.
TRIMMED_GIST = ("[Conversación recortada: los {n} turnos más antiguos de esta sesión ya no se muestran enteros; de "
                "{k} de ellos queda sólo lo que pidió la persona y cómo terminó cada llamada:{lines}\nLo demás que pasó "
                "en ellos no lo sabes]")
GIST_LINE = "\n- "
GIST_CHARS = 1200
GIST_WORDS = 100
GIST_NO_CALLS = "sin llamadas"
GIST_NOT_RUN = "no se ejecutó"
# Al máximo 1.1 (2026-10-22): before a cut, the oldest results lose their bodies; their calls and the line of their
# turn's facts (continue_turn writes it last) stay. A turn of 5+ calls held 3.6k tokens (p50): about three turns were
# left. The ids a body carried (windows, controls) are gone with it, and the model is told so (regla 10: look again).
TURN_FACTS = "\n[En este turno: "
COMPACTED = ("[Resultado omitido para que quepa la conversación: los ids de ventanas y controles que traía ya no "
             "valen; si lo necesitas, míralo de nuevo]")
# Renew al máximo (w5): what a kept facts line says of the body it no longer has («su resultado está arriba» after the
# result was left out read as a value the model could still quote), said as it is once the body is gone.
COMPACTED_FACTS = {"su resultado está arriba": "su resultado se omitió",
                   "su after es la ventana de después": "su after se omitió"}
assert "su resultado está arriba" in VERIFICATION["output_only"]
# A read says nothing of its body while it is there (OUTPUT_READ); once the body is gone its line says so, once.
READ_OMITTED = "; lo que vio se omitió"
_READ_KEPT = re.compile(re.escape(OUTPUT_READ) + "(?!" + re.escape(READ_OMITTED) + ")")
# Noche P0.2 (BAXY más torpe con cada mensaje): between cuts every body of the last eight turns travelled whole, up to
# 24,000 characters (~7.9k tokens) beside a prefix of ~38-42k in a context of 53,248, and a result may be 8 KiB (a
# window's controls, a page): the model read what it saw turns ago as much as what it was asked now. A result longer than
# this, of a turn before the newest closed one, keeps only its turn's facts, as a cut leaves it (1.1); by its size and age
# only, never by what it says. The newest closed turn keeps its bodies (the follow-up «el segundo», «¿qué decía?»).
OLD_BODY_CHARS = 1000


def _omitted(facts: str) -> str:
    """Facts of calls whose results lost their bodies, said as they are now (COMPACTED_FACTS)."""
    for told, omitted in COMPACTED_FACTS.items():
        facts = facts.replace(told, omitted)
    return _READ_KEPT.sub(OUTPUT_READ + READ_OMITTED, facts)

# Review 16: the person's own text, when it alone does not fit (decide), keeps its start and the cut is said where the
# model reads it; never cut below this many characters.
CUT_TEXT = "\n[Texto recortado para que quepa el turno: {n} caracteres más de lo que escribió la persona ya no se muestran]"
CUT_TEXT_FLOOR = 500
# P0.10 (noche 27-10): a result past RESULT_TOKENS keeps its start, cut by size and never by what it says, and the cut is
# said where the model reads it.
CUT_RESULT = "\n[Resultado recortado para que quepa el turno: {n} de sus {total} caracteres ya no se muestran]"

# System One, layer 0 (doubt.py): what the model reads when it was not sure of the action it chose. Under BAXY_S1_DOUBT
# (0.4, SYSTEM_ONE); on the 1,839 labelled real requests, below 0.4 held 95 of 210 wrong actions and asked instead of 10
# of 1,530 right ones (phase 0, 2026-10-21).
# How every note that only asks ends (DOUBT_NOTE, DOUBT_OTHER_ASK_NOTE): after it the model writes words only.
ASK_ONLY = "No hagas nada todavía: pregúntale en una frase corta qué quiere exactamente.]"
DOUBT_NOTE = ("[Nota interna, no la escribió la persona: no estás seguro de haber entendido qué quiere; ibas a usar "
              "{call}. " + ASK_ONLY)
# Pregunta-eco (noche 2026-10-27): told to ask with no tools, a model unsure of nothing but its own call could only ask
# the request back («¿Quieres que busque…?», «¿Quieres conectarte a la red…?», «¿Quieres cerrar…?»), and a clear request
# became a question (v11, the fair's battery). Layer 0 lets it read the request again with its tools: it does what was
# asked, or asks only what is missing (identity: «una pregunta corta y concreta que desambigua»). System One does not
# hold that reading again (layers 0 and 2), save a call the kernel would run unasked (Mind._unasked, which only asks); the
# kernel's confirmations still apply. A «sí» under CONFIRM_FLOOR only asks.
REREAD_NOTE = ("[Nota interna, no la escribió la persona: no estás seguro de haber entendido qué quiere; ibas a usar "
               "{call}. Nada se hizo todavía. Vuelve a leer lo que dijo: si pide eso y no cabe otra lectura, hazlo; si "
               "cabe otra lectura o falta un dato, pregúntale en una frase corta sólo lo que falta.]")
# Aid «answer_check» (al máximo, lever 3; answer_check.py): what the model reads when its final answer contradicts the
# turn's results, before it is spoken. Only the facts and what to do with them, never words to say (invariant 5): the
# model writes its answer again, once, with no tools. Offline on the stored practice transcripts it flagged the 11 clear
# falsehoods of the hand-read pc-t2 runs and none of their 232 clean lines (scripts/renew/maximo/chequeo_offline.py).
CHECK_NOTE = ("[Nota interna, no la escribió la persona: tu respuesta todavía no se dijo y no cuadra con los resultados. "
              "{facts} Escribe de nuevo tu respuesta a la persona contando sólo lo que muestran los resultados.]")
CHECK_FACT = "Dice «{said}», pero {fact}."
CHECK_FACTS = 3
# The rules of the check that are aids of their own (BAXY_AYUDAS), beside «answer_check» itself.
CHECK_RULE_AIDS = {"found": "check_found", "read": "check_read", "denial": "check_denial"}
# Aid «check_denial» (2026-10-25): an answer of a turn with no call that says BAXY cannot do what a tool of the catalog
# does (answer_check rule «denial»: V5E046 «No puedo eliminar carpetas de BAXY-bench», E027, V5E040, V6E015). The model
# is told which tool does it and what its description says, and answers again once; its tools stay, so it may do what
# was asked (whatever it does then is its own call, under the same doubt and confirmations as any other). Offline on the
# 1,968 replies of the c3-*-e2e and ho6-*-e2e-e2e runs (265 of turns with no call): 34 flagged, all false denials by hand
# (V5E046 17, E027 6, V5E040 3, V6E015 3, V6E052 2, and V6E065 3: «¿ya la creaste?» after a call refused for its
# arguments), and none of the 16 other no-call replies that deny something (a coffee, the lights, a pizza, a window of
# Code) (scripts/renew/ayudas/niego_auditoria.py).
DENIAL_NOTE = ("[Nota interna, no la escribió la persona: tu respuesta todavía no se dijo y dice que no puedes hacer algo "
               "que una de tus herramientas hace. {facts} Responde de nuevo a la persona según lo que pidió.]")
# Renew al máximo (confirmaciones, 2026-10-23): a «sí» the model is not sure is one. On the real model (29 answers to a
# pending trash of notas.txt, 3 seeds, int7) every plain yes («sí», «dale», «ya po», «okey», «go ahead», «zí») confirmed at
# ≥ 0.998 and «sí pero el otro» at 0.77-0.79, which would have trashed the file the person had just said was not the
# one; under this floor an approve:true is held and the model asks, so nothing runs on it. «sí no» confirmed at 0.99:
# no confidence tells it apart (a limit, said so in the report). BAXY_CONFIRM_FLOOR sets it; 0 turns it off.
CONFIRM_FLOOR = 0.95
# Menos preguntas (decisión del dueño 2026-10-25: BAXY pide el sí sólo para lo peligroso, sin preguntas innecesarias): a
# held «sí» costs two more questions, the model's own and the kernel's again (the App drops the call its question left
# behind). Words that are only a yes are one, whatever the model's confidence: the floor holds an approve:true only when
# the person said something besides a yes («sí pero el otro», «sí no», «ya, espera»). The words are read folded (lower
# case, no accents), whole, a yes first and then yeses or the softeners that may follow one («sí po», «hágale pues»).
PLAIN_YES = ("si", "sip", "ya", "dale", "ok", "okay", "okey", "oki", "vale", "va", "venga", "claro", "claro que si",
             "obvio", "obviamente", "hagale", "hagalo", "hazlo", "hacelo", "dele", "de una", "por supuesto", "adelante",
             "bueno", "listo", "perfecto", "correcto", "exacto", "afirmativo", "de acuerdo", "andale", "orale", "sale",
             "simon", "yes", "yep", "yeah", "sure", "go ahead", "do it", "of course")
YES_SOFTENERS = ("po", "pues", "porfa", "por favor", "please")
_YES, _SOFT = ("(?:" + "|".join(r"\s+".join(map(re.escape, p.split())) for p in phrases) + ")"
                for phrases in (PLAIN_YES, YES_SOFTENERS))
_PLAIN_YES = re.compile(rf"\W*{_YES}(?:\W+(?:{_YES}|{_SOFT}))*\W*")
# Layer 2 (system_one.py): the model doubted and the decision model read the request otherwise.
# Pregunta-eco (noche 2026-10-27): 34 of the 65 echoes in the stored runs, 22 of them with the decision model's choice
# the tool expected; it reads again with its tools as after layer 0 (REREAD_NOTE).
DOUBT_OTHER_NOTE = ("[Nota interna, no la escribió la persona: no estás seguro de haber entendido qué quiere; ibas a "
                    "usar {call}, pero también podría ser {other}. Nada se hizo todavía. Vuelve a leer lo que dijo: si "
                    "pide una de las dos y no cabe otra lectura, hazla; si caben las dos, pregúntale en una frase corta "
                    "cuál quiere.]")
# C16 (auditoría de la noche): layer 2's question as before pregunta-eco, for a call the kernel would run unasked
# (Mind._unasked): read again, the same call would run, and nobody asked.
DOUBT_OTHER_ASK_NOTE = ("[Nota interna, no la escribió la persona: no estás seguro de haber entendido qué quiere; ibas "
                        "a usar {call}, pero también podría ser {other}. " + ASK_ONLY)
# Al máximo 4.2 (SAGE-Agent): one question per misunderstanding. The person's words right after a doubt question (the
# notes start alike) or an ask_user answer it, and layer 0 does not hold them again: it asked in a loop, with no limit.
# They still go to layer 2 (the decision model and «corrige», with its safeguards).
DOUBT_ASKED = DOUBT_NOTE[:DOUBT_NOTE.index("{call}")]
# P2.43: in Bypass the catalog cannot say whether a call confirms by its arguments (a click on «Enviar» does in normal
# mode, one on «Siguiente» does not), so a doubt that would read again goes to the App as the action with «unsure»
# (_held). The App never runs it: it answers the observation held «would_run_unasked» when the kernel would run that
# exact invocation now without the «sí» normal mode asks for it (the doubt then asks, DOUBT_NOTE), or held HELD_UNSURE
# otherwise (it reads again, REREAD_NOTE); P2.43b: a held outcome it does not know asks too. The mind reads only that
# typed outcome, never the call's words.
UNSURE = object()
HELD_UNSURE = "unsure"
# P2.43b: the reading again after a held doubt may choose another invocation (a click on «Siguiente» weighed, one on
# «Enviar» chosen in doubt on reading again). A reading still under either layer's threshold goes to the App «unsure»
# too when its key (operation and canonical arguments) was not weighed in this turn, at most this many weighings a
# turn; past them its doubt asks, so it never loops and never runs unweighed. The same invocation, weighed, runs.
UNSURE_WEIGHS = 2
# Uso en la feria (2026-10-27): in the noise a short greeting came out in another language or as a word nobody said, and
# the model answered it as said. How sure the ear was of each word (voice.Heard, Parakeet's per-token probabilities)
# reaches the model beside the clock as a fact, as the pending «sí» does: the model decides, in its own words, whether to
# ask the person to say it again.
UNSURE_NOTE = ("[Nota interna, no la escribió la persona: habló por voz y el oído no está seguro de haber oído bien "
               "estas palabras: {words}.]")
# Menos preguntas (2026-10-25): layer 2 asks once too. The answer to its own question went to layer 2 again, which asked
# again at each answer while the decision model read it otherwise, with no limit; that answer may still be corrected.
DOUBT_OTHER_ASKED = DOUBT_OTHER_NOTE[DOUBT_OTHER_NOTE.index("{call}") + len("{call}"):DOUBT_OTHER_NOTE.index("{other}")]
# Layer 2 «corrige» (BAXY_S1_CORRECT=1): when the decision model chose another tool and it is one of these risks, the
# model fills that tool's arguments (LlmServer.fill_call) instead of asking. Simulated on the 156 held-out real requests
# (2026-10-22): right 140 → 148, wrong actions run 10 → 3; forced arguments where Qwen had chosen otherwise 14/15. Any
# other risk still asks: the core authorizes, and a riskier tool it would run unasked is never put in the model's mouth
# (below: what it confirms). Al máximo 5.1: nor
# one with an effect of the catalog (keys, clicks or commands to a window that may be the person's; what the model wrote
# sent out of the PC; a radio, a network, a pairing, airplane or display mode changed), whatever its risk: a call the
# model did not choose never lands there. A catalog without the field (the measurement catalogs saved before it)
# corrects by risk alone, as before.
# Al máximo, System One 3: also the risks the kernel always confirms in normal mode (RiskPolicy.Evaluate: work_loss and
# installation and recoverable_delete are Irreversible there), because its confirmation names the exact action and
# replaces the vague question (P215 «desinstala el Worms»: Laya read game_uninstall_named at 0.91 and BAXY asked what to
# do). Not external_communication: normal mode confirms only four of its operations. Not system.power, which normal mode
# runs unasked, and none of them in Bypass, which runs them unasked too (only message.send asks there, and it has an
# effect of the catalog); a mode that cannot be read counts as Bypass. With _founded and the effects rule, as for the rest.
CONFIRMED_RISKS = ("work_loss", "installation", "recoverable_delete")
CORRECTABLE_RISKS = ("read_only", "low_reversible", *CONFIRMED_RISKS)
UNCONFIRMED_OPERATIONS = ("system.power",)


def _bypass() -> bool:
    """Whether the kernel's confirmation mode is Bypass, as ConfirmationModeStore reads it: the file «confirmation-mode»
    of the data root (BAXY_DATA_DIR, or %LOCALAPPDATA%\\BAXY\\1), «bypass» or «all»; no file or another word is normal.
    Read at each correction, as the engine reads it at each invocation: the switch can change between turns."""
    root = os.environ.get("BAXY_DATA_DIR", "").strip() or str(Path(os.environ.get("LOCALAPPDATA", ".")) / "BAXY" / "1")
    try:
        word = (Path(root) / "confirmation-mode").read_text(encoding="utf-8-sig").strip().lower()
    except FileNotFoundError:
        return False
    except (OSError, UnicodeDecodeError):
        return True  # unreadable: «corrige» puts no confirmed risk in the model's mouth
    return word in ("bypass", "all")


# System One as the benches certified it (phase 0): ask under 0.4 of confidence (layer 0), consult the decision model
# under 0.6 (layer 2), and let it correct a harmless call («corrige»). Entrega 1.1.0 (2026-10-25): scripts/run_renew.cmd
# set them, so BAXY installed and opened from the Start menu decided without System One; now they are the mind's own.
# A variable still sets its value for a bench's arm (empty or 0 turns that layer off), and the owner's switch
# %LOCALAPPDATA%\BAXY\renew\system_one.off (scripts\system_one.cmd off) turns all three off; the App does not give the
# decision model's GGUF then either (MindRuntimeDiscovery).
SYSTEM_ONE = {"BAXY_S1_DOUBT": "0.4", "BAXY_S1_VETO": "0.6", "BAXY_S1_CORRECT": "1"}


def system_one_off() -> bool:
    """Whether the owner switched System One off (scripts/system_one.cmd off)."""
    return (Path(os.environ.get("LOCALAPPDATA", ".")) / "BAXY" / "renew" / "system_one.off").exists()


def _system_one(name: str) -> str:
    """A System One setting: the environment's when the variable is there, else its default (SYSTEM_ONE), none with
    the owner's switch off."""
    value = os.environ.get(name)
    if value is None:
        return "" if system_one_off() else SYSTEM_ONE.get(name, "")
    return value.strip()


def _threshold(name: str) -> float:
    """A System One threshold (BAXY_S1_DOUBT, BAXY_S1_VETO; BAXY_CONFIRM_FLOOR when given), _system_one's; 0 turns that
    layer off."""
    try:
        return max(0.0, min(1.0, float(_system_one(name) or 0)))
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
# F010 (int3, 2026-10-22): «nothing waiting» read as «already done» («la borré sin pedirte permiso» after a delete that
# had failed); the result says this call did nothing and that only earlier results tell what was done.
NOTHING_PENDING = json.dumps({"status": "failed", "error": "nothing_pending",
                              "reason": "no action is waiting for the person's confirmation, and this call did nothing; "
                                        "whether anything was done is only what the earlier results of this "
                                        "conversation say"})
# Auditoría de confirmaciones (2026-10-23): a question that ended unanswered (its time ran out, or a later line of
# BAXY's left it behind) is not «nothing was asked» (audit 2026-10-15, App 3, lost since F005): the App says which call
# it was with the person's next words, and their «sí» reads how it ended and that asking again is calling it again.
ENDED = {"expired": ("confirmation_expired", "the time to answer ran out"),
         "dropped": ("confirmation_dropped", "something else was said after the question, so it no longer stood")}


def ended_result(ended: dict[str, Any]) -> str:
    """What confirm_pending reads when the call the person may think they answer ended without an answer."""
    error, reason = ENDED.get(str(ended.get("ended")), ENDED["dropped"])
    wire = str(ended["operation"]).replace(".", "_")
    # A call the kernel challenged again after it had started (reconciliationRequired) may have had its effect.
    uncertain = ended.get("effectUncertain") is True
    told: dict[str, Any] = {"status": "failed", "error": error, "operation": ended["operation"]}
    if uncertain:
        told["effectUncertain"] = True
    told["reason"] = f"{reason}: {wire} {'may have started before it was asked' if uncertain else 'did not run'}"
    told["next"] = f"to do it now, call {wire} again: the person will be asked again"
    return json.dumps(told)

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

# Feria 2026-10-27: sums done from memory went wrong (12 for two plus two, a digit misheard) and an 18-digit square root
# went to the Calculator, which takes none. The model writes the expression it understood; the mind computes it
# (arithmetic.evaluate, no App call) and its value, or why there is none, is the call's result.
CALCULATE = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": (
            "Compute arithmetic exactly, to answer the person yourself: a sum, a product, a division, a percentage, a "
            "power, a root or a logarithm. Write the expression you understood with digits and symbols only: + - * / "
            "^ ( ), sqrt(), cbrt(), log10() and ln(), % as a hundredth (p% of n is p% * n), decimals with a point (a "
            "decimal comma becomes a point) and no thousands separators. Do not use when: they ask to do it in the "
            "Calculator app, or ask the open Calculator for an operation (calculator_expression_evaluate); a "
            "conversion or a price needs a rate you were not given, such as an exchange rate (web_search). A question "
            "for the number («¿cuánto es…?») is yours even with the Calculator open, and so is what it cannot type (a "
            "root, a percentage)."
        ),
        "parameters": {"type": "object", "properties": {"expression": {"type": "string"}},
                       "required": ["expression"]},
    },
}
CALCULATIONS = 4  # a turn's calculations; the next decision after the last is in words
# Feria 2026-10-27: office_document_create takes the whole body in one call; at 512 tokens a story was cut mid-call. A
# cap, not a length: a short answer still ends at its own end. Measured on the notebook (NB-L): ~36 tokens/s, ~2 tokens
# a word; 768 is ~21 s, inside the App's 30 s for a decision (TurnRequestTimeout) with room for the prefix.
DECISION_TOKENS = 768
# P0.10 (noche 27-10, NB-R1-X5 on the notebook's trace): the mind trusted the kernel's 8 KiB per result, but a process
# list, a console's output or an OCR reach 48,000 characters, and some turn.continue re-read 10-12k tokens (>2000 tokens
# in 0.7 % of the results, p50 3.8 s each). One result takes at most the room the history leaves for it beside the reply.
RESULT_TOKENS = TURN_ROOM_TOKENS - DECISION_TOKENS
CALCULATED_FIRST = json.dumps({"status": "not_run", "reason": "written before the calculation's value; call it again "
                                                              "with that value if it is still needed"})


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


def _as_written(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aid «calls_as_written» (w6-lat, 2026-10-23): the conversation's calls with each boolean argument as the model
    writes it. Under the call grammar llama-server makes from the tools' schemas the model writes «true» / «false»
    (JSON), and Qwen3.5's template writes a call's top-level value with Jinja's «| string», «True» / «False»: the request
    after a call stopped matching what the slot held at that value, and the hybrid model went back to its checkpoint 4
    tokens before the decision's end and re-read those tokens, the call and the result (CPU probe, b11609, ft c2e1:
    audio_mute {state: true} 54 → 23 tokens, app_open {foreground: true} 65 → 23; 52 of 278 calls of the practice e2e
    have one). Given as the text «true» / «false», the template writes it as it came; objects and lists it already writes
    with tojson, strings and numbers as given. Only the request changes: the conversation keeps its calls as they were."""
    written: list[dict[str, Any]] = []
    for message in messages:
        calls = message.get("tool_calls") if message.get("role") == "assistant" else None
        if not calls:
            written.append(message)
            continue
        told = []
        for call in calls:
            function = call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except (json.JSONDecodeError, TypeError):
                arguments = None
            if not isinstance(arguments, dict) or not any(isinstance(v, bool) for v in arguments.values()):
                told.append(call)
                continue
            arguments = {k: ("true" if v else "false") if isinstance(v, bool) else v for k, v in arguments.items()}
            told.append({**call, "function": {**function, "arguments": json.dumps(arguments, ensure_ascii=False)}})
        written.append({**message, "tool_calls": told})
    return written


# Palanca P2.6: Start menu entries no one opens as an application, by the shape of their (folded) name, never by an
# application's name: an uninstaller («Uninstall X», «Desinstalar X»; «X Uninstaller» is an application), help, a
# manual, documentation or a license, release notes, and a web page. They leave app_open's list of installed
# applications (67 of 600 names on the PC, ~1,7k characters of prefix); app_open still opens any of them by name.
_NOT_AN_APP = re.compile(
    r"\b(?:un-?install|desinstalar)(?!er)"
    r"|\b(?:help|ayuda|manuals?|faq|readme|documentation|documentacion|dokumentation|user guide|release notes"
    r"|what'?s new|que hay de nuevo|reference|website)\b"
    r"|\b(?:on the|en la) web\b|\(online\)|^licen[cs]e\b|\blicen[cs]e agreement\b")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


class Mind:
    # Al máximo 9.4: the voice's look-ahead (Speech.foresee), given the last answer's text as it is written; None: the
    # last answer is not streamed.
    foresee: Any = None

    def __init__(self, server: LlmServer, trace: Path, system_one: SystemOne | None = None) -> None:
        self.server = server
        self.trace = trace
        self.system_one = system_one  # layer 2: the decision model beside Qwen (None: off)
        if system_one is not None:
            # Its server exiting and starting again is said in this trace (system_one.exited, system_one.restarted).
            system_one.on_event = lambda stage, **fields: self._log(stage, time.perf_counter(), None, **fields)
            system_one.until = lambda: self.server.deadline  # it answers within the request's budget, as every call
        self._judged: dict[str, Any] | None = None
        self._unread: list[dict[str, str]] = []  # the last decision's rivals whose names could not be read (P4)
        self.tools: list[dict[str, Any]] = []
        self.system = SYSTEM  # the person's system text: with the last catalog's groups (CAN_DO_AREAS)
        self.names: list[str] = []  # the installed applications and games of the last catalog.configure
        self.wire_to_op: dict[str, str] = {}
        self.risk: dict[str, str] = {}  # each tool's risk as the App sent it, by wire name (layer 2 «corrige»)
        self.effects: dict[str, list[str]] = {}  # each tool's effects as the App sent them (al máximo 5.1), by wire name
        # P2.41: the modes in which the kernel asks the person before each tool runs, whatever its arguments («normal»,
        # «bypass»: RiskPolicy.Evaluate, as the App sent them), by wire name (_unasked); None: the catalog did not say.
        self.confirms: dict[str, list[str] | None] = {}
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
        # The references made in the session (_refs keeps only those the conversation still shows, _prune_refs): a new
        # one takes the next number, never one still shown.
        self._ref_count = 0
        # Review 2026-10-22: the ids the mind writes itself (a confirmation's call, a call the server gave none, a
        # correction) count up for the whole session: from the conversation's length they repeated once it was trimmed.
        self._ids = 0
        self._ran: list[str] = []  # the session's last calls as «tool → how it ended» (8.1), and how many ran in all
        self._ran_ids: list[str | None] = []  # the id of each of those calls (None: not known), for the clock
        self._ran_count = 0
        # Aid «answer_check»: every call of the session as (operation, completed, read_only), for the check of the final
        # answer; None when the session is not known whole (one kept before the aid).
        self._calls: list[tuple[str, bool, bool]] | None = []
        # Review 2026-10-22: the voice thread logs here too (voice.speak, __main__.py): one row at a time.
        self._log_lock = threading.Lock()
        # A person's turn or a heartbeat reached the model in this process: the slot holds more than the prefix, and
        # the warm-up no longer keeps it on disk (al máximo V1).
        self._turned = False
        # The last read ahead gave way to a request (Yielded): its ``clock``, so the loop reads it again once nothing
        # waits (review of NB-R1-X4: the App's session.export after every turn); None when it did not.
        self.gave_way: bool | None = None
        # Al máximo, palanca 2 (early.py): while a decision is made early, its trace rows are held here (the thread that
        # makes it, and its rows) and written only if it is used; the voice thread's rows are written as always.
        self._holding: tuple[int, list[dict[str, Any]]] | None = None

    # ---- short references (PLAN_GENERAL C1) ----------------------------------------------------------------
    def _shorten(self, observation: str, compact: bool = False) -> tuple[str, dict[str, str]]:
        """The result with every address longer than LONG_REF_CHARS replaced by its short reference, and the
        references made for it (a known address keeps its reference). Text that is not JSON goes as it came.
        ``compact`` (aid «result_dedup»): written as compact as the App writes it, not with a space after each comma and
        colon (one token more per field)."""
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
                    self._ref_count = max(self._ref_count, len(self._refs)) + 1
                    ref = f"{REF_PREFIX}{self._ref_count}"
                    self._refs[ref], self._ref_of[value] = value, ref
                made[ref] = value
                return ref
            return value

        shortened = walk(facts)
        if not made:
            return observation, {}
        return json.dumps(shortened, ensure_ascii=False, separators=(",", ":") if compact else None), made

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
        apps = [str(n) for n in ((message.get("applicationCatalog") or {}).get("names") or [])
                if str(n).strip() and not _NOT_AN_APP.search(_fold(str(n)))]
        games = sorted({f'{e.get("name")} (appId {e.get("appId")}, {e.get("provider")})'
                        for e in ((message.get("gameCatalog") or {}).get("entries") or [])
                        if isinstance(e, dict) and e.get("name")})
        # The same names, for the ear's hotwords (voice.hear_names): what the model is shown is what it may hear.
        self.names = apps + sorted({str(e.get("name")) for e in ((message.get("gameCatalog") or {}).get("entries") or [])
                                    if isinstance(e, dict) and e.get("name")})
        tools, wire_to_op, risk, effects, confirms = [ASK_USER, CONFIRM, CALCULATE], {}, {}, {}, {}
        # Auditoría de la mente (w8): the constants of this catalog only; one a tool had in an earlier catalog was still
        # added to its calls.
        constants_of: dict[str, dict[str, Any]] = {}
        aids: dict[str, Any] = {}
        for cap in capabilities:
            name = str(cap.get("name") or "")
            # Renew al máximo: the places stay in app_open's description too (P2.6 left them only in `place`; e2e E014
            # then opened msconfig for «abre la configuración de sonido», twice, on the notebook, 2026-10-22).
            description = (self.english.get(name) or str(cap.get("description") or "")).replace(
                "{app_places}", APP_PLACES_TEXT)
            if name == "app.open" and apps:
                description += " Installed applications (use one of these names as appId): " + "; ".join(apps) + "."
            if name == "game.launch" and games:
                description += " The person's installed games: " + "; ".join(games) + "."
            for aid, sentence in DESCRIPTION_AIDS.get(name, ()):
                if _aid_on(aid):
                    description = description.rstrip() + sentence
                    aids.setdefault(aid, {})[name] = sentence.strip()
            raw = cap.get("argumentsSchema")
            constants: dict[str, Any] = {}
            schema = _model_schema(raw if isinstance(raw, dict) else {}, constants)
            if constants:
                constants_of[name] = constants
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
            # P2.41b: a catalog without the field (an older App, a bench's --catalog), or with one that is not a list of
            # modes, is not one that confirms nothing: None (_unasked).
            modes = cap.get("confirms")
            confirms[wire] = [mode.lower() for mode in modes] \
                if isinstance(modes, list) and all(isinstance(mode, str) for mode in modes) else None
        self.tools, self.wire_to_op, self.risk, self.effects, self.confirms = tools, wire_to_op, risk, effects, confirms
        if absent := [wire_to_op[wire] for wire, modes in confirms.items() if modes is None]:
            self._log("configure.confirms_absent", time.perf_counter(), None, operations=absent)
        areas = list(dict.fromkeys(str(cap["group"]) for cap in capabilities if cap.get("group")))
        self.system = SYSTEM + CAN_DO_AREAS.format(areas="; ".join(areas)) if areas else SYSTEM
        self.constants = constants_of
        if aids:
            # A session's aid in the tools themselves, once: its own trace row, as the aids of a turn.
            self._log("configure.aid", time.perf_counter(), None, aids=aids)
        return len(capabilities)

    def warm(self) -> None:
        """Process the tools and the system prompt once, so every turn starts from a cached prefix. Al máximo V1
        (2026-10-22): that state is kept on disk (LlmServer.save_prefix) with the prefix's tokens, and a start whose
        tools, system prompt, model and server are the same restores it instead (18.3 s → under 1 s)."""
        started = time.perf_counter()
        self.call_tokens = self.server.tokenize("<tool_call>")
        if len(self.call_tokens) != 1:
            raise RuntimeError(f"<tool_call> is not one token of this model: {self.call_tokens}")
        warm = {"messages": [{"role": "system", "content": self._system()}, {"role": "user", "content": "hola"}],
                "tools": self.tools, "max_tokens": 1, "chat_template_kwargs": {"enable_thinking": False}}
        key = self.server.prefix_key([warm])
        held = self.server.restore_prefix(key)
        if held is not None and isinstance(held.get("prefix_tokens"), int):
            self.prefix_tokens = held["prefix_tokens"]
            self._log("warm.prefix", started, None, restored=True)
            return
        reply = self.server.chat(warm, timeout=600)
        self.prefix_tokens = int((reply.get("usage") or {}).get("prompt_tokens") or 0)
        # The file holds the slot: only the prefix (the tools and the system prompt) may be in it, never a person's
        # conversation, so it is saved only before any turn of this process reached the model.
        saved = not self._turned and self.server.save_prefix(key, {"prefix_tokens": self.prefix_tokens})
        self._log("warm.prefix", started, None, restored=False, saved=saved)

    def notice_of(self) -> str:
        """The notice of the person's turn while the App runs its call (NOTICE_ASK): the model's words for that call,
        written from the turn's conversation with the call still running, words only and greedy, on the GPU the call
        leaves idle. Empty, and nothing asked of the model, when no call of a person's turn is running or in a turn kept
        out of the trace (its words would be said aloud); empty too when it wrote nothing usable or one of the turn's
        earlier notices (a form compare), or the call failed."""
        turn = self._turn
        if not turn or not turn.get("awaiting") or turn.get("private"):
            return ""
        said = turn.setdefault("notices", [])
        ask = NOTICE_ASK.format(said=NOTICE_SAID.format(said=", ".join(f"«{s}»" for s in said)) if said else "")
        notice = {"messages": [{"role": "system", "content": self._system()}, *self._history(turn["conv"]),
                               {"role": "tool", "tool_call_id": turn["awaiting"], "content": NOTICE_RUNNING},
                               {"role": "user", "content": ask}],
                  "tools": self.tools, "max_tokens": 24, "temperature": 0.0, "seed": self.seed, "tool_choice": "none",
                  "logit_bias": [[token, False] for token in self.call_tokens],
                  "chat_template_kwargs": {"enable_thinking": False}}
        started = time.perf_counter()
        try:
            reply = self.server.chat(notice, timeout=NOTICE_SECONDS)
            written = str(reply["choices"][0]["message"].get("content") or "")
        except Exception:  # noqa: BLE001 - a notice that could not be written is not said; the turn goes on as it was
            self._log("turn.notice", started, None, operation=turn.get("calling"), content=None, written="")
            return ""
        phrase = " ".join(written.strip().strip("«»\"'“”").split())
        usable = (bool(phrase) and "\n" not in written.strip() and "<" not in phrase
                  and len(phrase) <= NOTICE_MAX_CHARS and len(phrase.split()) <= NOTICE_MAX_WORDS
                  and _words(phrase) not in {_words(s) for s in said})
        if usable:
            said.append(phrase)
        self._log("turn.notice", started, reply, operation=turn.get("calling"), content=phrase if usable else None,
                  written=written)
        return phrase if usable else ""

    def _system(self, beat: bool = False) -> str:
        # Constant, so the prefix (tools, system, earlier messages) never changes between turns and is never re-read.
        return BEAT_SYSTEM if beat else self.system

    @staticmethod
    def _history(conv: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """The conversation as a request sends it: every request and the prefill render it alike (aid
        «calls_as_written»), or the prefill's text would not be the next prompt's start."""
        return _as_written(conv) if _aid_on("calls_as_written") else conv

    @staticmethod
    def _waits(pending: dict[str, Any] | None) -> bool:
        """Whether the App says a call waits for the person's «sí» with these words."""
        return bool(isinstance(pending, dict) and pending.get("operation") and not pending.get("ended"))

    @classmethod
    def _confirming(cls, pending: dict[str, Any] | None) -> str | None:
        """The tool of the call that waits for the person's «sí» with these words, as the App says it, or None."""
        return str(pending["operation"]).replace(".", "_") if cls._waits(pending) else None  # type: ignore[index]

    @classmethod
    def _pending_op(cls, pending: dict[str, Any] | None) -> str | None:
        """The operation a «sí» with these words would confirm, as the App says it (aid «answer_check»: what a
        confirm_pending call did)."""
        return str(pending["operation"]) if cls._waits(pending) else None  # type: ignore[index]

    @staticmethod
    def _ended(pending: dict[str, Any] | None) -> dict[str, Any] | None:
        """The call whose question ended unanswered just before these words, as the App says it, or None."""
        return pending if isinstance(pending, dict) and pending.get("operation") and pending.get("ended") else None

    @staticmethod
    def _pending_note(pending: dict[str, Any] | None) -> str:
        """The call the kernel holds for the person's yes, when one is: after «sí» the model called that tool again
        instead of answering it (e2e practice E021, 3 of 3), and the kernel only asked again."""
        if not isinstance(pending, dict) or not pending.get("operation") or pending.get("ended"):
            return ""
        wire = str(pending["operation"]).replace(".", "_")
        arguments = pending.get("arguments")
        shown = f" {json.dumps(arguments, ensure_ascii=False)}" if isinstance(arguments, dict) else ""
        return (f"\n[Espera el sí de la persona: {wire}{shown}. Si sus palabras contestan a tu pregunta, llama a "
                f"confirm_pending con approve true o false.]")

    @staticmethod
    def _unsure_note(unsure: list[tuple[str, float]]) -> str:
        """The words of a spoken request the ear was not sure of (voice.Heard), told as a fact the model weighs."""
        if not unsure:
            return ""
        words = ", ".join(f"«{word}» ({round(p * 100)} %)" for word, p in unsure)
        return "\n" + UNSURE_NOTE.format(words=words)

    def _clock(self) -> str:
        # The time is a message of its own just before the person's words (the end of the prompt, the only part that is
        # new anyway). Appended to their words it was copied into arguments: a clipboard text and a web query carried
        # «[Thursday 15/10/2026 04:21 hora local…]» (2026-10-15). It also says no tool has run yet in this turn: the
        # last «[En este turno: …]» the model saw was the previous turn's, and lines of turns without calls were false
        # 24 % of the time against 6 % (falsedades p5-p8); decision2 on the notebook gained by that mechanism (P041
        # stopped inventing, P049 stopped looking up the clock): 227/230 vs 226. Al máximo 8.1: and the session's calls.
        ran = str(self._ran_count or "ninguna")
        if self._ran:
            last = "" if len(self._ran) == self._ran_count else f", las {len(self._ran)} últimas"
            ran += f"{last} ({' / '.join(self._ran_told())})"
        return (f"{CLOCK_MARK} {self._clock_time()}; "
                "los campos que terminan en Utc van en UTC; turno nuevo: aún no se ejecutó ninguna herramienta en este "
                f"turno; llamadas a herramientas en esta sesión: {ran}]")

    @staticmethod
    def _clock_time() -> str:
        """The clock's time, to the minute: the only part of a turn's prompt the time changes (early.py compares it)."""
        now = _dt.datetime.now().astimezone()
        offset = now.strftime("%z")
        return f"{now.strftime('%A %d/%m/%Y %H:%M')} hora local, UTC{offset[:3]}:{offset[3:]}"

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
        self._refs, self._ref_of, self._ids, self._ref_count = {}, {}, 0, 0
        self._ran, self._ran_ids, self._ran_count = [], [], 0
        self._calls = []
        self.conversation = [{"role": m["role"], "content": m["content"]} for m in history or []
                             if m.get("role") in {"user", "assistant"} and str(m.get("content") or "").strip()]

    def export_session(self) -> list[dict[str, Any]]:
        """The session's conversation as it stands (calls and results included), for the App to keep with the session it
        shows (design v4, Sessions); it is asked for between turns. Its last element is the session's own state (review
        2026-10-22: the short references and the ids, or after a relaunch ref:r1 stood for another address; al máximo
        8.1: the session's calls); the App keeps the array as it is."""
        state = {"role": SESSION_STATE, "refs": self._refs, "ids": self._ids, "ran": self._ran,
                 "ran_ids": self._ran_ids, "ran_count": self._ran_count}
        if self._calls is not None:
            state["calls"] = [list(call) for call in self._calls]
        return json.loads(json.dumps([*self.conversation, state], ensure_ascii=False))

    def load_session(self, conversation: list[Any]) -> None:
        """Go back to a kept session: its conversation exactly as exported, so the model reads what really ran."""
        self.new_session()
        state = next((m for m in conversation if isinstance(m, dict) and m.get("role") == SESSION_STATE), {})
        if isinstance(state.get("refs"), dict):
            self._refs = {str(ref): str(value) for ref, value in state["refs"].items()}
            self._ref_of = {value: ref for ref, value in self._refs.items()}
            self._ref_count = max((int(ref[len(REF_PREFIX):]) for ref in self._refs
                                   if ref.startswith(REF_PREFIX) and ref[len(REF_PREFIX):].isdecimal()), default=0)
        self._ids = state["ids"] if isinstance(state.get("ids"), int) and state["ids"] > 0 else 0
        self.conversation, unanswered = self._answered([m for m in conversation if isinstance(m, dict)
                                                        and m.get("role") in {"user", "assistant", "tool"}])
        if isinstance(state.get("ran_count"), int) and isinstance(state.get("ran"), list):
            self._ran, self._ran_count = [str(entry) for entry in state["ran"]][-SESSION_CALLS:], state["ran_count"]
            ids = state.get("ran_ids")
            self._ran_ids = ([i if isinstance(i, str) else None for i in ids][-SESSION_CALLS:]
                             if isinstance(ids, list) and len(ids) == len(state["ran"]) else [None] * len(self._ran))
            for wire in unanswered:
                self._ran_add(wire, NO_RESULT_RAN)
        else:
            # Kept before 8.1: how many calls its conversation shows (their results are in it), never «none».
            self._ran_count = sum(1 for m in self.conversation for c in m.get("tool_calls") or []
                                  if c.get("function", {}).get("name") != ASK_USER["function"]["name"])
        calls = state.get("calls")
        # Kept before «answer_check» (or written otherwise): what ran in it is not known whole, and nothing is checked
        # against the session's calls.
        self._calls = (list(dict.fromkeys((str(c[0]), c[1], c[2]) for c in calls)) if isinstance(calls, list) and all(
            isinstance(c, list) and len(c) == 3 and isinstance(c[1], bool) and isinstance(c[2], bool) for c in calls)
            else None if any(m.get("tool_calls") for m in self.conversation) else [])
        self._trim()

    @staticmethod
    def _answered(conversation: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
        """A kept conversation where every call has its result, and the calls that may have run without one (their wire
        names). Auditoría de la mente (w8, 2026-10-23): the App keeps a session between turns, and a turn may be left
        open there (BAXY's question waiting for its answer, a call whose result never came); the open turn is not kept
        with it, so loaded back its calls had no result and the model read them as still open. Each gets what
        _close_open_calls writes: the first call of its message without one ASKED (a question) or NO_RESULT, the ones
        after it NOT_RUN, right after the results its message has."""
        answered = {m.get("tool_call_id") for m in conversation if m.get("role") == "tool"}
        closed: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []
        unanswered: list[str] = []
        for message in [*conversation, None]:
            if message is None or message.get("role") != "tool":
                closed += missing
                missing = []
            if message is None:
                break
            closed.append(message)
            lacking = [c for c in message.get("tool_calls") or [] if isinstance(c, dict) and c.get("id") not in answered]
            for index, call in enumerate(lacking):
                wire = str((call.get("function") or {}).get("name") or "?")
                content = NOT_RUN if index else ASKED if wire == ASK_USER["function"]["name"] else NO_RESULT
                if content == NO_RESULT:
                    unanswered.append(wire)
                missing.append({"role": "tool", "tool_call_id": call.get("id"), "content": content})
        return closed, unanswered

    def decide(self, request_id: Any, text: str, pending: dict[str, Any] | None = None,
               unsure: list[tuple[str, float]] | None = None) -> dict[str, Any]:
        """``unsure``: the words of a spoken request the ear was not sure of (voice.Voice.unsure)."""
        # Kept even if the decision fails: the App says how a question ended only once.
        self._ran_unanswered(self._ended(pending))
        # Review 2026-10-22: a decision that fails (the model server down, an error) takes back what it added, so the
        # next turn never reads an old request without its answer as one still to do.
        turn = self._turn
        if turn and turn.get("asked"):
            # The person's next words answer the model's own ask_user: they are that call's result, in the same loop, so
            # the steps already run stay in the conversation and are never run again. A new request instead of an
            # answer reaches the model the same way, and the model reads it as what it is.
            # Renew al máximo (auditoría de confirmaciones, 2026-10-23): what waits for the person's «sí» is what the App
            # says with these words, not what waited when the turn began: a confirmation dropped or expired since then
            # was approved with the answer to the question (the old file, after «sí pero el otro» → «¿cuál?» → «el
            # informe»), and one asked since then got nothing_pending.
            asked, after, said = turn.pop("asked"), turn.pop("after_asked", []), turn["text"]
            was = {"pending": turn.get("pending"), "ended": turn.get("ended"), "said": turn.get("said", said)}
            # Aid «unopened_app»: the words of the whole turn, the request with the answers to its questions.
            turn["said"] = was["said"] + "\n" + text
            answer = {"role": "tool", "tool_call_id": asked,
                      "content": text + self._pending_note(pending) + self._unsure_note(unsure or [])}
            turn["conv"].append(answer)
            for later in after:
                turn["conv"].append({"role": "tool", "tool_call_id": later, "content": NOT_RUN})
            turn["text"], turn["answering"], turn["pending"] = text, True, self._waits(pending)
            turn["confirming"] = self._confirming(pending)
            turn["ended"], turn["pending_op"] = self._ended(pending), self._pending_op(pending)
            try:
                return self._next(request_id, "turn.decide", turn)
            except Exception:
                self._take_back(turn["conv"], answer)
                turn.update(asked=asked, after_asked=after, text=said, **was)
                raise
        self._close_open_calls()
        self._age_bodies()
        doubts = [note for note in (str(m.get("content") or "") for m in self.conversation[-2:])
                  if note.startswith(DOUBT_ASKED)]
        clock = {"role": "user", "content": self._clock()}
        self.conversation.append(clock)
        # Noche 2026-10-27 (P0, P0.8): what only this turn knows (the call waiting for the «sí», the words the ear was
        # unsure of) is a note of its own after the clock, so the prompt still begins with the clock the wake read into
        # the slot (prefill) without it; as a note («[») it stays out of what the person said (_said, _gist, _founded).
        if notes := (self._pending_note(pending) + self._unsure_note(unsure or [])).lstrip("\n"):
            self.conversation.append({"role": "user", "content": notes})
        request = {"role": "user", "content": text}
        self.conversation.append(request)
        try:
            self._trim()
            if _aid_on("clock_omitted"):
                clock["content"] = self._clock()  # the bodies as the trim left them
            # Review 2026-10-22: a text that alone does not fit beside the prefix (a pasted log) failed the turn whole
            # and wordless, as only earlier turns can be trimmed: it keeps its start, halved until it fits, and the cut
            # is said where the model reads it.
            keep = len(text)
            while keep > CUT_TEXT_FLOOR and not self._fits(self._turn_sizes()):
                keep //= 2
                request["content"] = text[:keep] + CUT_TEXT.format(n=len(text) - keep)
            self._turn = {"conv": self.conversation, "queue": [], "awaiting": None, "text": text, "said": text,
                          "pending": self._waits(pending), "ended": self._ended(pending), "answering": bool(doubts),
                          "answering_other": any(DOUBT_OTHER_ASKED in note for note in doubts),
                          "confirming": self._confirming(pending), "pending_op": self._pending_op(pending)}
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
        started = time.perf_counter()
        self._turned = True
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

    def prefill(self, clock: bool = False) -> bool:
        """Al máximo W5 (PREFILL_MARK): with no turn open, the conversation is read into the slot as the next request
        will show it; whether it was. The template is asked for the conversation with a request after it (a user
        message, as the clock of the next turn or a confirmation's label is), and its text is cut where that request
        begins: what comes before it is the start of the next prompt to the character, and it ends in «<|im_end|>\\n»
        before «<|im_start|>», so it is tokenized there as in the whole prompt. Nothing is read while a call waits for
        its result, while the model's question (ask_user) waits for the person's words (they come as its result, and
        the turn's messages keep their form), during a heartbeat, or with nothing to read.

        ``clock`` (al máximo, palanca 5, early.py: «Baxy» was heard): the next turn's clock is read too, as a turn with
        no call waiting for the person's «sí» begins, so the GPU is awake and the slot holds all but the person's words
        when they come. The prompt does not change: a clock of another minute is read by the decision itself from where
        they differ (a call waiting for the «sí» and the ear's unsure words are a note of their own after the clock,
        Mind.decide). BAXY_RENEW_PREFILL does not turn it off (BAXY_RENEW_WAKE_WARM does)."""
        turn, self.gave_way = self._turn or {}, None
        if ((not clock and os.environ.get("BAXY_RENEW_PREFILL", "").strip() == "0")
                or (not self.conversation and not clock) or self._beat is not None
                or turn.get("awaiting") or turn.get("asked") or turn.get("queue")):
            return False
        started = time.perf_counter()
        self._age_bodies()  # as the next decision will show it, so it does not re-read from the older turn on
        told = {"clock": True} if clock else {}  # the wake's row says so, whether it was read, failed or gave way
        after = [{"role": "user", "content": self._clock()}] if clock else []
        body = {"messages": [{"role": "system", "content": self._system()}, *self._history(self.conversation),
                             *after, {"role": "user", "content": PREFILL_MARK}],
                "tools": self.tools, "chat_template_kwargs": {"enable_thinking": False}}
        try:
            rendered = self.server.template(body)
            cut = rendered.rfind("<|im_start|>user\n" + PREFILL_MARK)
            if cut <= 0 or not rendered[:cut].endswith("<|im_end|>\n"):
                self._log("warm.history", started, None, failure="unrendered", **told)
                return False
            # Auditoría de la mente (w8): the slot now holds the person's conversation (a kept session's, loaded before
            # any turn), so the warm-up no longer keeps it on disk (Mind.warm), as after a turn.
            self._turned = True
            reply = self.server.prefill(rendered[:cut])
        except Yielded:  # not a failure: it is read again once the request is answered (gave_way)
            self._log("warm.history", started, None, yielded=True, **told)
            self.gave_way = clock
            return False
        except Exception as error:  # noqa: BLE001 - the next decision reads it itself, as it did before
            self._log("warm.history", started, None, failure=type(error).__name__, **told)
            return False
        self._log("warm.history", started, reply, messages=len(self.conversation), **told)
        return True

    def _ran_add(self, calling: Any, outcome: str, call_id: str | None = None) -> None:
        """One call of the session and how it ended, for the clock (8.1)."""
        wire = CONFIRM["function"]["name"] if calling == CONFIRM_OPERATION else str(calling or "?").replace(".", "_")
        self._ran, self._ran_count = [*self._ran, f"{wire} → {outcome}"][-SESSION_CALLS:], self._ran_count + 1
        self._ran_ids = [*self._ran_ids, call_id][-SESSION_CALLS:]

    def _ran_unanswered(self, ended: dict[str, Any] | None) -> None:
        """The session's call whose question ended unanswered, as the App says it, no longer waits for a «sí» (8.1)."""
        if ended is None:
            return
        wire = str(ended["operation"]).replace(".", "_")
        waiting = f"{wire} → {WAITS_FOR_YES}"
        if waiting in self._ran:
            last = len(self._ran) - 1 - self._ran[::-1].index(waiting)
            # One the kernel challenged again after it had started may have had its effect (as ended_result tells it).
            told = f"{wire} → " + (NO_RESULT_RAN if ended.get("effectUncertain") is True
                                   else UNANSWERED.get(str(ended.get("ended")), UNANSWERED["dropped"]))
            self._ran = [told if index == last else entry for index, entry in enumerate(self._ran)]

    def _ran_told(self) -> list[str]:
        """The clock's calls of the session (8.1). Aid «clock_omitted» (auditoría de la mente, w8, 2026-10-23): one whose
        result lost its body (1.1, or its turn was cut) is told as the kept facts lines tell it (COMPACTED_FACTS: «lo
        que vio se omitió»), not «lo que vio está arriba» beside those lines saying it was left out."""
        if not _aid_on("clock_omitted"):
            return self._ran
        bodies = {m.get("tool_call_id") for m in self.conversation
                  if m.get("role") == "tool" and not str(m.get("content") or "").startswith(COMPACTED)}
        return [entry if call_id is None or call_id in bodies else _omitted(entry)
                for entry, call_id in zip(self._ran, self._ran_ids)]

    def _receipt(self, turn: dict[str, Any], wire: str, observation: str, outcome: str) -> None:
        """A call of the turn as the answer check reads it (aid «answer_check»), and in the session's calls. A
        confirmation's own call stands for the operation it answered: the one its result names, else the one the App
        said was waiting, else any (CONFIRM_OPERATION)."""
        op = str(turn.get("calling") or "?")
        if op == CONFIRM_OPERATION:
            try:
                named = json.loads(observation).get("operation")
            except (json.JSONDecodeError, AttributeError):
                named = None
            op = str(named or turn.get("pending_op") or CONFIRM_OPERATION)
        completed = outcome.startswith(COMPLETED_OUTCOMES)
        read = self.risk.get(op.replace(".", "_")) == "read_only"
        try:
            arguments = json.loads(turn.get("calling_args") or "{}")
        except json.JSONDecodeError:
            arguments = {}
        turn.setdefault("receipts", []).append({"op": op, "tool": wire, "arguments": arguments,
                                                "observation": observation, "outcome": outcome,
                                                "completed": completed, "read": read})
        self._session_call((op, completed, read))

    def _session_call(self, call: tuple[str, bool, bool]) -> None:
        """One call of the session for the answer check, which only asks whether one of a kind completed or ran at all:
        each (operation, completed, read) is kept once (revisión de calidad de la mente: one entry per call, for good,
        exported with the session and deep-copied by every early decision)."""
        if self._calls is not None and call not in self._calls:
            self._calls.append(call)

    def _close_open_calls(self) -> None:
        """A call the App never answered (the turn ended first) gets its honest result, so the conversation stays a
        valid tool transcript and the model never reads an unanswered call as done."""
        turn = self._turn or {}
        if turn.get("awaiting") and (turn.get("unsure") or {}).get("id") != turn["awaiting"]:  # P2.43: never ran
            self.conversation.append({"role": "tool", "tool_call_id": turn["awaiting"], "content": NO_RESULT})
            self._ran_add(turn.get("calling"), NO_RESULT_RAN)
            op = str(turn.get("calling") or "?")  # it may have run: never a completed call of the session
            self._session_call((op, False, self.risk.get(op.replace(".", "_")) == "read_only"))
        if turn.get("asked"):
            self.conversation.append({"role": "tool", "tool_call_id": turn["asked"], "content": ASKED})
        pending = [c["id"] for c in turn.get("queue") or []]
        for call_id in [*turn.get("after_asked", []), *pending]:
            if call_id:
                self.conversation.append({"role": "tool", "tool_call_id": call_id, "content": NOT_RUN})
        self._turn = None

    def _trim(self) -> None:
        """Keep the last turns that fit the budget; a turn starts at its clock, so no call loses its result. While they
        fit, nothing already sent changes (the model re-reads from the first changed message on). Past a bound, one
        rewrite: the oldest turns go down to TRIM_TURNS_TO of the count, every kept closed turn loses its results'
        bodies (1.1, in one block), and the oldest turns go until what is left fits TRIM_TO of every bound."""
        # Renew al máximo (w5): 1.1 left out bodies only down to TRIM_TO of the characters and kept every turn, so the
        # count bound came back a turn or two later and the whole history was re-read again (sesión larga, notebook
        # 2026-10-22: turns 12 and 14 re-read 2,844 and 1,932 tokens, the base 747 and 333). One deep rewrite instead.
        turns = self._turn_sizes()
        if len(turns) <= 1 or self._fits(turns):
            return
        dropped = 0
        while dropped < len(turns) - 1 and len(turns) - dropped > HISTORY_TURNS * TRIM_TURNS_TO:
            dropped += 1
        starts = [t[0] for t in turns[dropped:]]
        if any([self._compact(self.conversation[start:end]) for start, end in zip(starts, starts[1:])]):
            turns = self._turn_sizes()
        while dropped < len(turns) - 1 and not self._fits(turns[dropped:], TRIM_TO):
            dropped += 1
        if dropped:
            self._drop(turns[dropped][0], dropped)
        self._prune_refs()

    def _age_bodies(self) -> None:
        """Aid «old_bodies» (noche P0.2, OLD_BODY_CHARS): before the newest closed turn with results, each result whose
        body is longer than OLD_BODY_CHARS keeps only its turn's facts. The prefix is edited only there, once per turn,
        and the read ahead does it before the next decision (prefill)."""
        starts = self._turn_starts()
        if len(starts) < 2 or not _aid_on("old_bodies"):
            return
        # Revisión de PC-R1-W2: a turn with no results (a question answered in words, a doubt and its answer) aged the
        # reading before it, and a third question about one reading found it gone. Only a newer reading ages one.
        ends = [*starts[1:], len(self.conversation)]
        read = [start for start, end in zip(starts, ends)
                if any(m["role"] == "tool" and TURN_FACTS in str(m.get("content") or "")
                       for m in self.conversation[start:end])]
        old = self.conversation[:read[-1] if read else 0]
        if self._compact([m for m in old if str(m.get("content") or "").rfind(TURN_FACTS) > OLD_BODY_CHARS]):
            self._prune_refs()

    def _prune_refs(self) -> None:
        """Revisión de calidad de la mente (2026-10-25): the short references the conversation no longer shows (their
        turns cut out, their results' bodies left out) are not kept: every address of the session stayed in _refs, and
        with it in the exported session (the App's 1 MiB per line) and in what an early decision deep-copies. An open
        heartbeat's own messages count as shown."""
        if not self._refs:
            return
        shown = json.dumps([self.conversation, (self._beat or {}).get("conv"), (self._turn or {}).get("conv")],
                           ensure_ascii=False)
        alive = set(_REF.findall(shown))
        if len(alive) < len(self._refs):
            self._refs = {ref: value for ref, value in self._refs.items() if ref in alive}
            self._ref_of = {value: ref for ref, value in self._refs.items()}

    def _drop(self, end: int, turns: int) -> None:
        """Take out the oldest `turns`, up to the first kept turn's clock (`end`): an earlier note of what was cut goes
        with them, and the new one says how many are gone and, for the newest of them that fit, what the person asked
        and how each call ended (w5). In place: an open turn's conversation is this same list (the notebook's review of
        1.1/1.2, 2026-10-22)."""
        cut = self.conversation[:end]
        lines = []
        earlier = str(cut[0].get("content") or "") if cut else ""
        if earlier.startswith(TRIMMED[:TRIMMED.index(":")]):
            lines = earlier.split(GIST_LINE)[1:]
            lines[-1:] = [lines[-1].split("\n")[0]] if lines else []
            cut = cut[1:]
            # A kept session starts its count again (load_session): the earlier note's own count is not lost.
            told = re.match(r"\D*(\d+)", earlier)
            self.trimmed_turns = max(self.trimmed_turns, int(told.group(1)) if told else 0)
        starts = [i for i, m in enumerate(cut)
                  if i and m["role"] == "user" and str(m.get("content") or "").startswith(CLOCK_MARK)]
        bounds = [0, *starts, len(cut)]
        lines += [self._gist(cut[a:b]) for a, b in zip(bounds, bounds[1:]) if a < b]
        lines = [line for line in lines if line]
        kept: list[str] = []
        for line in reversed(lines):
            if sum(len(k) for k in kept) + len(line) > GIST_CHARS:
                break
            kept.insert(0, line)
        del self.conversation[:end]
        self.trimmed_turns += turns
        note = (TRIMMED_GIST.format(n=self.trimmed_turns, k=len(kept), lines="".join(GIST_LINE + k for k in kept))
                if kept else TRIMMED.format(n=self.trimmed_turns))
        self.conversation.insert(0, {"role": "user", "content": note})

    @staticmethod
    def _gist(messages: list[dict[str, Any]]) -> str:
        """One cut turn in a line (w5): the person's words, clipped, and how its calls ended, from the facts line each
        loop of calls ended with (a failure keeps its code) and from the results the mind wrote for calls that never got
        one. Empty for a turn with no words of the person (a heartbeat's own)."""
        said = next((str(m.get("content") or "") for m in messages if m["role"] == "user"
                     and not str(m.get("content") or "").startswith("[")), "")  # a note, the clock or BEAT_MARK
        said = " ".join(said.split())
        if not said:
            return ""
        if len(said) > GIST_WORDS:
            said = said[:GIST_WORDS].rstrip() + "…"
        names = {c.get("id"): str((c.get("function") or {}).get("name") or "?")
                 for m in messages for c in m.get("tool_calls") or []}
        calls: list[str] = []
        facts, unrun = "", []
        # A loop of calls (the turn's, or a confirmation's) ends at a message of the person or the mind; its last facts
        # line lists all of its calls, each earlier one a part of it.
        for message in [*messages, {"role": "user"}]:
            content = str(message.get("content") or "")
            at = content.rfind(TURN_FACTS)
            if message["role"] == "tool" and at >= 0:
                # Its body is gone with the turn.
                facts = _omitted(content[at + len(TURN_FACTS):].split("\n")[0].removesuffix("]"))
            elif message["role"] == "tool" and content in {NO_RESULT, NOT_RUN, NOT_RUN_AFTER}:
                ended = NO_RESULT_RAN if content == NO_RESULT else GIST_NOT_RUN
                unrun.append(f"{names.get(message.get('tool_call_id'), '?')} → {ended}")
            elif message["role"] == "user":
                calls += [facts] if facts else []
                calls += unrun
                facts, unrun = "", []
        return f"«{said}» → " + ("; ".join(calls) if calls else GIST_NO_CALLS)

    @staticmethod
    def _compact(messages: list[dict[str, Any]]) -> bool:
        """Each call's result among these messages (the ones that end with their turn's facts) keeps only those facts
        after COMPACTED; the calls stay, so none loses its result. Whether any result changed."""
        compacted = False
        for message in messages:
            content = str(message.get("content") or "")
            at = content.rfind(TURN_FACTS)
            if message["role"] == "tool" and at > len(COMPACTED):
                message["content"] = COMPACTED + _omitted(content[at:])  # w5: the facts no longer point at a body
                compacted = True
        return compacted

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

    @staticmethod
    def _web_queries(turn: dict[str, Any]) -> list[str]:
        """What a web page is read for (goal h-web): the person's words and the turn's web.search queries."""
        queries = [str(turn.get("text") or "")]
        for receipt in turn.get("receipts") or []:
            query = receipt.get("arguments", {}).get("query") if receipt.get("op") == "web.search" else None
            if isinstance(query, str):
                queries.append(query)
        return [q for q in queries if q.strip()]

    def continue_turn(self, request_id: Any, observation: str, final: bool = False,
                      beat: bool = False) -> dict[str, Any]:
        """The verified result of the call the App ran goes back as that call's tool message. ``final``: the App closes
        the turn (steps spent, engine down, or a confirmation waiting), so the model answers now in text from what the
        results show. ``beat``: the heartbeat's turn."""
        turn = self._beat if beat else self._turn
        if turn and not turn.get("awaiting") and turn["conv"] and turn["conv"][-1]["role"] == "tool":
            # R7-NB-1 (CU C03): the result is already in the turn and no decision came after it (the request ran past its
            # budget, and the turn ended with no words): the App asks for that decision again, and the model decides
            # from the results it has, without reading the same result in twice; in words when the mind had closed the
            # turn's calls itself (a refused repeat, the calculations' cap: _next's ``closed``).
            self._log("turn.continue", time.perf_counter(), None, kind="asked_again", operation=turn.get("calling"))
            return self._next(request_id, "turn.continue", turn, final=final or bool(turn.get("closed")))
        if not turn or not turn.get("awaiting"):
            raise RuntimeError("no open turn to continue")
        conv = turn["conv"]
        if (unsure := turn.get("unsure")) and unsure["id"] == turn["awaiting"]:
            del turn["unsure"]
            held = self._unsure_held(request_id, turn, unsure, observation)
            if held is not None:
                return held
        answered = turn["awaiting"]
        # Every call of the turn so far with how it ended, at the end of the newest result: where the model writes its
        # answer, the facts it may tell are together (it told «no pude abrir Steam» after Steam opened, «lo guardé»
        # after the typing failed, 2026-10-15 falsehood bench).
        done = turn.setdefault("done", [])
        calling = str(turn.get("calling", "?"))
        received = observation
        if calling == "web.fetch":
            # Goal h-web: the model reads the lead and the paragraphs nearest to what was asked; the
            # answer check keeps the page as it came (received).
            observation = web_focus.focus(observation, self._web_queries(turn), json.loads(
                turn.get("calling_args") or "{}"))
        calling = CONFIRM["function"]["name"] if calling == CONFIRM_OPERATION else calling.replace(".", "_")
        outcome = _outcome(observation, read=self.risk.get(calling) in READ_RISKS)
        if outcome.startswith(VERIFICATION["unchanged"]) and _aid_on("same_call_closes") and _same_done(
                turn, calling, turn.get("calling_args"), VERIFICATION["readback"]):
            outcome = SET_BY_SAME + outcome[len(VERIFICATION["unchanged"]):]
        # Aid «confirm_names_call» (auditoría de la mente, w8, P5): an answer to a confirmation says which call it
        # answered («confirm_pending (filesystem_known_trash_named) → …»), here and in the clock; once its turn is cut,
        # «confirm_pending → completado y verificado» no longer said what was done. Only when the App said which call
        # waited (with the person's words) or the press answered the call the turn before had just asked.
        told = (f"{calling} ({turn['confirming']})" if calling == CONFIRM["function"]["name"] and turn.get("confirming")
                and _aid_on("confirm_names_call") else calling)
        entry, same = f"{told} → {outcome}", turn.get("last_call")
        # Grouped only when the result is the same too: a click that worked and then failed are two facts (round 2).
        turn["last_call"] = (calling, turn.get("calling_args"), outcome)
        if done and same == turn["last_call"]:
            turn["repeats"] = turn.get("repeats", 1) + 1
            done[-1] = f"{told} ×{turn['repeats']} con los mismos argumentos → {outcome}"
        else:
            turn["repeats"] = 1
            done.append(entry)
        self._ran_add(told, outcome, turn["awaiting"])
        self._receipt(turn, calling, received, outcome)
        aids = _aids_seen(observation)
        named = json.loads(turn.get("calling_args") or "{}") if calling in {"app_open", "input_visible_controls"} else {}
        # Uso real: a look at another window (the browser's) came between the opening and the failures; the application
        # kept is the last one named that has places of its own.
        application = named.get("appId") or named.get("application") if isinstance(named, dict) else None
        if isinstance(application, str) and _fold(application) in APP_PLACES:
            turn["app_named"] = application
        note = ""
        if (calling in {"input_visible_click", "input_visible_controls"} and not outcome.startswith(COMPLETED_OUTCOMES)
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
        if calling == "file_write" and _aid_on("written_not_window"):
            # The receipts before this call's own (_receipt above put it last).
            written = written_note(observation, turn.get("receipts", [])[:-1])
            if written:
                note += written
                aids["written_not_window"] = written.strip()
        # Aid «same_call_next» (PLAN_GENERAL C2; uso real: the same click 5-7 times, a reload and a typing in turn): a
        # call made again in this turn with the same arguments and the same result (its content, _result_key),
        # whatever came between, is told as a fact with its options, once per turn (a loop of a look and a click repeats
        # both): a second time when it failed or stayed unsure, a third when it completed (SAME_CALL_FAILED_TOLD).
        seen = turn.setdefault("calls_seen", {})
        turn.pop("same_told_call", None)  # same_call_closes: only the model's next decision after the notice
        key = json.dumps([calling, turn.get("calling_args"), _result_key(observation)], ensure_ascii=False)
        seen[key] = seen.get(key, 0) + 1
        told_at = SAME_CALL_TOLD if outcome.startswith(COMPLETED_OUTCOMES) else SAME_CALL_FAILED_TOLD
        if seen[key] == told_at and not turn.get("same_told") and _aid_on("same_call_next"):
            turn["same_told"] = True
            turn["same_told_call"] = [turn.get("calling"), _call_key(turn.get("calling_args"))]  # same_call_closes
            # Auditoría de la mente (w8): not the places again when app_places_next just told them in this result.
            options = SAME_CALL_CLOSED if final else SAME_CALL_OPTIONS + (
                same_call_places(turn.get("app_named"))
                if calling == "input_visible_click" and "app_places_next" not in aids else "")
            repeated = SAME_CALL_NOTE.format(call=calling, times=told_at, outcome=outcome, options=options)
            note += repeated
            aids["same_call_next"] = repeated.strip()
        # Aid «look_click_cap»: each click right after a look, by that look, what it saw and the click; a look waits for
        # the call after it.
        pairs = turn.setdefault("look_clicks", {})
        if calling == "input_visible_click" and turn.get("look"):
            pair = json.dumps([*turn["look"], _call_key(turn.get("calling_args"))], ensure_ascii=False)
            pairs[pair] = pairs.get(pair, 0) + 1
        turn["look"] = ([_call_key(turn.get("calling_args")), _result_key(observation)]
                        if calling == "input_visible_controls" else None)
        # Aid «result_dedup» (w6-lat): what the facts line below says of this result is not said in it again.
        compact = _aid_on("result_dedup")
        told = _deduplicated(observation, outcome) if compact else observation
        # Aid «short_refs» (PLAN_GENERAL C1; uso real: news addresses of ~500 tokens copied wrong, 11 s each): a long
        # address in a result reaches the model as a short reference, and the mind puts the address back in its calls.
        shown, made = self._shorten(told, compact) if _aid_on("short_refs") else (told, {})
        if made:
            aids["short_refs"] = sorted(made) if turn.get("private") else made
        if _aid_on("result_cap"):
            fitted = self._fit_result(shown)
            if fitted != shown:
                aids["result_cap"] = len(shown)  # the trace says which results the model read in part
                shown = fitted
        line = _said_once(done) if _aid_on("facts_once") else done
        conv.append({"role": "tool", "tool_call_id": turn["awaiting"],
                     "content": shown + "\n[En este turno: " + "; ".join(line) + "]" + note})
        turn["awaiting"] = None
        if aids:
            # What the aids told the model, a row of its own: the model's decision after it is the next row.
            self._log("turn.aid", time.perf_counter(), None, operation=turn.get("calling"),
                      aids=sorted(aids) if turn.get("private") else aids)
        if final:
            # The App closes the turn (its step budget spent, the engine down, or a confirmation waiting for the
            # person): said where the model reads it, at the end of the last result, without a cause the mind does not
            # know.
            conv[-1]["content"] += NO_MORE_CALLS
        completed = outcome.startswith(COMPLETED_OUTCOMES)
        if turn["queue"] and not final and completed:
            turn.pop("same_told_call", None)  # chosen before the notice was read
            return self._result(request_id, turn, turn["queue"].pop(0), None, "turn.continue", time.perf_counter(), "")
        after = turn.pop("unsure_after", None)
        if (unsure := turn.pop("unsure", None)) and after == answered and not final and completed:
            # P2.40 with P2.43: the queued call held «unsure» goes to the App to be weighed once those before it ran;
            # one the mind refuses now (_repeat_refused, _unopened) enters the conversation and _result says why.
            turn.pop("same_told_call", None)  # chosen before the notice was read
            name = self.wire_to_op.get(unsure["wire"], unsure["wire"])
            if self._repeat_refused(turn, name, unsure) or self._unopened(turn, unsure):
                conv.append({"role": "assistant", "content": "", "tool_calls": [
                    {"id": unsure["id"], "type": "function", "function": {
                        "name": unsure["wire"], "arguments": json.dumps(unsure["arguments"], ensure_ascii=False)}}]})
            else:
                turn["unsure"] = unsure
                turn.setdefault("weighed", []).append((unsure["wire"], _call_key(unsure["arguments"])))
            return self._result(request_id, turn, unsure, None, "turn.continue", time.perf_counter(), "")
        for call in turn["queue"]:
            conv.append({"role": "tool", "tool_call_id": call["id"], "content": NOT_RUN if final else NOT_RUN_AFTER})
            turn.setdefault("receipts", []).append({
                "op": self.wire_to_op.get(call["wire"], call["wire"]), "tool": call["wire"],
                "arguments": call["arguments"], "observation": NOT_RUN, "outcome": GIST_NOT_RUN, "completed": False,
                "read": self.risk.get(call["wire"]) == "read_only"})
        turn["queue"] = []
        return self._next(request_id, "turn.continue", turn, final=final)

    def _unsure_held(self, request_id: Any, turn: dict[str, Any], call: dict[str, Any],
                     observation: str) -> dict[str, Any] | None:
        """P2.43: the App's answer to a call sent «unsure». Held, it did not run: the doubt asks the person with no tools
        unless the App says the kernel would not run it unasked (HELD_UNSURE): then it reads again with its tools.
        None: an App that does not know «unsure» ran it, so the call enters the conversation and is read as any."""
        try:
            told = json.loads(observation)
        except json.JSONDecodeError:
            told = None
        conv, turn["awaiting"] = turn["conv"], None
        if not isinstance(told, dict) or told.get("status") != "held":
            conv.append({"role": "assistant", "content": "", "tool_calls": [
                {"id": call["id"], "type": "function",
                 "function": {"name": call["wire"], "arguments": json.dumps(call["arguments"], ensure_ascii=False)}}]})
            turn["awaiting"] = call["id"]
            return None
        asks = told.get("outcome") != HELD_UNSURE
        if not asks:
            turn["reread"] = True
        conv.append({"role": "user", "content": (DOUBT_NOTE if asks else REREAD_NOTE).format(call=call["wire"])})
        self._log("turn.continue", time.perf_counter(), None, text=None if turn.get("private") else turn["text"],
                  kind="doubt_ask" if asks else "doubt_reread", operation=self.wire_to_op.get(call["wire"], call["wire"]),
                  arguments=None, content=None)
        # Decided again as the person's turn it doubted, as REREAD_NOTE and DOUBT_NOTE are after a doubt held in the mind.
        return self._next(request_id, "turn.decide", turn, final=asks)

    def _fit_result(self, shown: str) -> str:
        """Aid «result_cap» (P0.10): a result past RESULT_TOKENS keeps the start that fits and says how much is left out
        (CUT_RESULT), before it is sent rather than after a refusal (_make_room). Counted as the history counts, only
        with the server's tokenizer (a token is at least a character, so a shorter text is never counted). The call has
        already been counted as done when this runs, so a tokenizer that fails does not fail the turn: the result keeps
        RESULT_TOKENS characters, which fit."""
        if not self.prefix_tokens or len(shown) <= RESULT_TOKENS:
            return shown
        try:
            tokens = len(self.server.tokenize(shown))
            if tokens <= RESULT_TOKENS:
                return shown
            keep = len(shown) * RESULT_TOKENS // tokens
            while True:
                cut = shown[:keep] + CUT_RESULT.format(n=len(shown) - keep, total=len(shown))
                tokens = len(self.server.tokenize(cut))
                if tokens <= RESULT_TOKENS or keep == 0:
                    return cut
                keep = max(0, keep - (keep * (tokens - RESULT_TOKENS) // tokens) - 1)
        except (OSError, http.client.HTTPException, RuntimeError, ValueError, KeyError) as error:
            self._log("turn.result_cap", time.perf_counter(), None, error=type(error).__name__)
            keep = RESULT_TOKENS - len(CUT_RESULT) - 2 * len(str(len(shown)))
            return shown[:keep] + CUT_RESULT.format(n=len(shown) - keep, total=len(shown))

    def confirm(self, request_id: Any, approve: bool, label: str) -> dict[str, Any]:
        """The person pressed Sí or No on a pending confirmation: their answer (the button's label) and the
        confirm_pending call it stands for enter the conversation as they are, with no model call in between."""
        started = time.perf_counter()
        # The press answers the card of the call the turn before had just asked (its last result waits for the «sí»).
        asked = (self._turn or {}).get("last_call")
        confirming = asked[0] if asked and asked[2] == WAITS_FOR_YES else None
        self._close_open_calls()
        call_id = self._new_id("confirm")
        self.conversation.append({"role": "user", "content": label})
        self.conversation.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": call_id, "type": "function",
             "function": {"name": CONFIRM["function"]["name"], "arguments": json.dumps({"approve": approve})}}]})
        self._turn = {"conv": self.conversation, "queue": [], "awaiting": call_id, "text": label,
                      "calling": CONFIRM_OPERATION, "confirming": confirming}
        self._log("turn.confirm", started, None, text=label, kind="action", operation=CONFIRM_OPERATION,
                  arguments={"approve": approve})
        return {"type": "turn.result", "id": request_id, "kind": "action", "operation": CONFIRM_OPERATION,
                "arguments": {"approve": approve}, "reply": "", "question": ""}

    def _make_room(self, conv: list[dict[str, Any]], final: bool = False) -> bool:
        """One step of room for an open turn past the context, whether there was one: the earlier turns' results leave
        out their bodies, else the oldest earlier turn goes, else the open turn's results but the newest leave out
        theirs, else those of the newest's loop also leave out their facts lines (the newest's lists every call of its
        loop), else, for the last answer only, the newest leaves out its body too. All in place: the person's open turn
        is this same conversation."""
        starts = [i for i, m in enumerate(conv)
                  if m["role"] == "user" and str(m.get("content") or "").startswith(CLOCK_MARK)]
        if conv is self.conversation and len(starts) > 1:
            if not self._compact(conv[:starts[-1]]):
                self._drop(starts[1], 1)
            return True
        begin = starts[-1] if starts else 0
        results = [m for m in conv[begin:] if m["role"] == "tool" and TURN_FACTS in str(m.get("content") or "")]
        if self._compact(results[:-1]):
            return True
        # H6 (holdout v5 V5F028/V5F029): each left-out result kept its own facts line, and each lists every call of its
        # loop before it, so they grew with the square of the calls (14 of them, 5.1k tokens at a log's 15th page) and
        # the last answer did not fit: no answer at all. The newest's line says them all; a loop starts at the last
        # message of the person (or a note) before it.
        loop = max([i for i in range(begin, len(conv)) if conv[i]["role"] == "user"], default=begin)
        bare = False
        for message in conv[loop:]:
            content = str(message.get("content") or "")
            if (message["role"] == "tool" and message is not (results[-1] if results else None)
                    and content.startswith(COMPACTED) and TURN_FACTS in content):
                message["content"] = COMPACTED
                bare = True
        # The last answer always comes: its newest result leaves out its body too (its facts stay, said as omitted).
        return bare or (final and self._compact(results[-1:]))

    def _next(self, request_id: Any, stage: str, turn: dict[str, Any], final: bool = False) -> dict[str, Any]:
        started = time.perf_counter()
        self._turned = True
        conv = turn["conv"]
        messages = [{"role": "system", "content": self._system(bool(turn.get("beat")))}, *self._history(conv)]
        body = {"messages": messages, "tools": self.tools, "max_tokens": DECISION_TOKENS, "parallel_tool_calls": True,
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
            turn["closed"] = True  # R7-NB-1: a decision asked for again (continue_turn) keeps it
            # The last answer of an exhausted turn is words only. The tools stay, so the cached prefix (37k tokens)
            # is not evicted by a shorter prompt (llama.cpp PR #24176: a restore re-reads ~4k tokens; measured 2.3-3.6 s
            # on the next order). tool_choice none alone still let Qwen3.5 write a call as XML text that reached the
            # person (llama.cpp #20837; 2026-10-15 E017): the token that opens a call cannot be sampled.
            body["tool_choice"] = "none"
            body["logit_bias"] = [[token, False] for token in self.call_tokens]
        try:
            # Al máximo 9.4: a person's turn streams to the voice, which synthesizes an answer's first sentence while
            # the rest is written (only while it is words; a call dropped what it foresaw); nothing sounds before the
            # App publishes it. Not the decision whose doubt is read (_doubted): its token probabilities are not all
            # sent when streamed (LlmServer.chat). Never a heartbeat.
            streams = self.foresee is not None and not turn.get("beat") and not self._doubted(stage, turn, final)
            reply = self.server.chat(body, on_text=self.foresee) if streams else self.server.chat(body)
        except urllib.error.HTTPError as error:
            # llama-server refuses a prompt past its context with HTTP 400. Al máximo 1.2 (2026-10-22): its earlier
            # results were cut and the model answered in words at once (15 context_shrunk in the trace, each one ended
            # its mission); now room is made a step at a time (_make_room, said where the model reads) and the turn goes
            # on as it was. With no room left to make, the refusal reaches the App.
            if error.code != 400 or not self._make_room(conv, final):
                raise
            self._log(stage, started, None, kind="context_shrunk", operation=None, arguments=None, content=None)
            return self._next(request_id, stage, turn, final=final)
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
        held, note = (calls[0], self._held(stage, turn, final, calls[0], reply, body)) if calls else (None, None)
        # P2.40 (C16 M11): the calls queued behind the first run without the model deciding again, so one the kernel
        # would run unasked goes by the same rule, with its own doubt ([app_open, system_power] never asked); in Bypass,
        # so does one the App weighs with its arguments (P2.43: a click on «Enviar» or on «Siguiente»), not one that only
        # reads, is undone, or the kernel confirms in Bypass too.
        for nth, call in enumerate(calls[1:], 1):
            if note is None and (self._unasked(call["wire"]) or _bypass() and self.risk.get(call["wire"]) not in (
                    "read_only", "low_reversible") and "bypass" not in (self.confirms.get(call["wire"]) or ())):
                held, note = call, self._held(stage, turn, final, call, reply, body, nth)
        if isinstance(note, dict):
            # Layer 2 «corrige»: the decision model's tool, with the arguments the model itself wrote for it, replaces
            # the action the model doubted (and anything queued behind it, chosen on the same misreading). Review
            # 2026-10-22 (and B-MED-8): the words it wrote for the doubted call go with it, and the row says whose doubt
            # it carries (doubt_of) beside the operation that runs.
            turn["doubt_of"] = self.wire_to_op.get(held["wire"], held["wire"])
            at = calls.index(held)  # the calls before a queued one held were not doubted: they stay, with their words
            calls, note, content = [*calls[:at], note], None, content if at else ""
        if note is UNSURE:
            # P2.43: the doubted call goes to the App to be weighed with its arguments, not run; it enters the
            # conversation only if an App that does not know «unsure» ran it (continue_turn). One the mind itself
            # refuses (_repeat_refused, _unopened) takes the usual way, which tells the model why. P2.40: held queued
            # behind others, those were not doubted: they run first, with their words, and it is weighed after them.
            name, at = self.wire_to_op.get(held["wire"], held["wire"]), calls.index(held)
            if at or not self._repeat_refused(turn, name, held) and not self._unopened(turn, held):
                turn["unsure"] = held
                if not at:
                    turn.setdefault("weighed", []).append((held["wire"], _call_key(held["arguments"])))
                    return self._result(request_id, turn, held, reply, stage, started, "")
                # Queued, it is weighed (or refused, continue_turn) only once those before it ran.
                calls, turn["unsure_after"] = calls[:at], calls[at - 1]["id"]
            note = None
        if note:
            # System One: the model was not sure of this action (layer 0), or was unsure and the decision model chose
            # otherwise (layer 2). Nothing runs; it is told so where it reads (the call it nearly made never enters the
            # conversation). After layer 0 or 2 it decides again with its tools, once (REREAD_NOTE, DOUBT_OTHER_NOTE); a
            # note that ends in ASK_ONLY (an unsure «sí», a call the kernel would run unasked) only asks the person, in
            # its own words, what they want.
            conv.append({"role": "user", "content": note})
            reread = not note.endswith(ASK_ONLY)
            doubted = self.wire_to_op.get(held["wire"], held["wire"])
            if doubted.startswith("memory."):
                turn["private"] = True  # review 2026-10-22: the words meant for memory, as after a memory call
            self._log(stage, started, reply, text=None if turn.get("private") else turn["text"],
                      kind="doubt_reread" if reread else "doubt_ask", operation=doubted, arguments=None, content=None,
                      call_index=calls.index(held))
            return self._next(request_id, stage, turn, final=not reread)
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
            return self._next(request_id, stage, turn, final=True)
        if not content and not final and stage == "turn.continue" and not turn.get("beat"):
            # After a call the model wrote nothing and called nothing: an empty reply is a failed turn that never tells
            # what ran (round 2, as an empty ask_user), so it answers in words from the results.
            return self._next(request_id, stage, turn, final=True)
        if (content and stage == "turn.decide" and not final and not turn.get("beat") and not turn.get("answering")
                and not turn.get("dated") and not turn.get("receipts") and _aid_on("dated_search")
                and self._dated(turn["text"])):
            turn["dated"] = True
            self._log("turn.dated", started, None)
            return self._look_up_first(request_id, stage, turn, body, reply, started)
        if (content and stage == "turn.decide" and not final and not turn.get("beat") and not turn.get("answering")
                and not turn.get("named") and not turn.get("receipts") and not turn.get("private")
                and _aid_on("named_fact") and self.system_one is not None and self.system_one.ready
                and self._unkept(self._names_said(turn["text"], content) & {_asked_about(turn["text"])})):
            looked = self._named_fact(request_id, stage, turn, body, reply, started)
            if looked is not None:
                return looked
        if (content and not turn.get("beat") and not turn.get("said_again")
                and not any(r.get("completed") for r in turn.get("receipts") or [])
                and _aid_on("say_once") and self._said_last(conv, content)):
            return self._say_otherwise(request_id, stage, turn, content, reply, started)
        if content and not turn.get("beat") and _aid_on("answer_check"):
            checked = self._check_answer(request_id, stage, turn, content, reply, started)
            if checked is not None:
                return checked
        if content:
            conv.append({"role": "assistant", "content": content})
            if not streams and self.foresee is not None and not turn.get("beat"):
                # Al máximo V2 (2026-10-22): words that came whole, not streamed (the decision whose doubt is read),
                # never reached the voice's look-ahead (first sound p50 966 ms, p90 2,388): their first sentence is
                # synthesized now, while the App publishes them; it still sounds only when the App asks (voice.speak).
                try:
                    self.foresee(content, True)
                except Exception:  # noqa: BLE001 - a failing look-ahead never fails the answer
                    pass
        return self._result(request_id, turn, None, reply, stage, started, content)

    @staticmethod
    def _dated(text: str) -> bool:
        """Whether the person asks for a fact memory confuses: about something of a given year (a question whose only
        number is a year), or a curiosity."""
        folded = _fold(text)
        return ((bool(_YEAR_ALONE.match(text)) and ("?" in text or bool(_ASKS.match(folded))))
                or bool(_CURIOUS.search(folded)))

    @classmethod
    def _names_said(cls, text: str, content: str) -> set[str]:
        """The person's words, folded, that the answer says in a sentence that is not a question (a question tells no
        fact) and either of them wrote as a name: with a capital past the start of a sentence (aid «named_fact»). PC-L
        review 2026-10-27: the voice may come in lowercase, and the model still writes a name with its capital."""
        told = " ".join(sentence for sentence in _TOLD.findall(content) if not sentence.rstrip().endswith("?"))
        said, said_names = cls._words_and_names(text)
        words, names = cls._words_and_names(told)
        return (said_names | names) & said & words

    def _unkept(self, names: set[str]) -> bool:
        """Whether there are names and none is in what a memory call returned in this conversation (privacy review
        2026-10-27: a contact recalled in an earlier turn is the person's, never a web query)."""
        kept = {c["id"] for m in self.conversation for c in m.get("tool_calls") or []
                if self.wire_to_op.get(c["function"]["name"], "").startswith("memory.")}
        return bool(names) and not any(
            names & self._words_and_names(str(m.get("content") or ""))[0]
            for m in self.conversation if m.get("role") == "tool" and m.get("tool_call_id") in kept)

    @staticmethod
    def _words_and_names(text: str) -> tuple[set[str], set[str]]:
        """The words of a text, folded, and those written as a name: with a capital past the start of a sentence."""
        words: set[str] = set()
        names: set[str] = set()
        for sentence in _SENTENCES.split(text):
            found = _WORDS.findall(sentence)
            words.update(_fold(word) for word in found)
            names.update(_fold(word) for word in found[1:] if word[0].isupper())
        return words, names

    def _named_fact(self, request_id: Any, stage: str, turn: dict[str, Any], body: dict[str, Any],
                    reply: dict | None, started: float) -> dict[str, Any] | None:
        """Aid «named_fact»: System One judges between the words and web_search; its web_search is looked up as a
        dated question is, and None leaves the words as they are."""
        turn["named"] = True
        if not any(t["function"]["name"] == "web_search" for t in self.tools):
            return None
        # PC-L review 2026-10-27 (privacy): who or what the person keeps in memory (a contact) is an option of its own,
        # never looked up on the web.
        options = {t["function"]["name"]: short(t["function"]["description"]) for t in self.tools
                   if t["function"]["name"] in ("web_search", "memory_recall")}
        options[ANSWER] = OPTION_TEXT[ANSWER]
        judged = self.system_one.choose(turn["text"], self._said(), options)  # type: ignore[union-attr]
        self._judged = {"options": list(options), **judged} if judged else {"options": list(options), "choice": None}
        self._log("turn.named", started, None)
        if not judged or judged["choice"] != "web_search":
            return None
        return self._look_up_first(request_id, stage, turn, body, reply, started)

    def _look_up_first(self, request_id: Any, stage: str, turn: dict[str, Any], body: dict[str, Any],
                       reply: dict | None, started: float) -> dict[str, Any]:
        """Aid «dated_search» (DATED_NOTE): the words answered from memory are not said. The model writes the
        web_search itself (LlmServer.fill_call, as System One's «corrige»); a fill that fails or writes no query decides
        once more with the note, which does not stay in the conversation (the soak of 2026-10-27: after the note alone
        «¿Quieres que busque…?» 3 of 8)."""
        conv = turn["conv"]
        try:
            filled = self.server.fill_call(body, "web_search")
        except Exception:  # noqa: BLE001 - a fill that failed falls back to the note
            filled = None
        if (filled and filled.get("name") == "web_search" and isinstance(filled.get("arguments"), dict)
                and str(filled["arguments"].get("query") or "").strip()):
            call = {"id": self._new_id("call"), "wire": "web_search", "arguments": filled["arguments"]}
            conv.append({"role": "assistant", "content": "", "tool_calls": [
                {"id": call["id"], "type": "function",
                 "function": {"name": "web_search", "arguments": json.dumps(call["arguments"], ensure_ascii=False)}}]})
            turn["queue"] = []
            return self._result(request_id, turn, call, reply, stage, started, "")
        note = {"role": "user", "content": DATED_NOTE}
        conv.append(note)
        try:
            return self._next(request_id, stage, turn)
        finally:
            for index in range(len(conv) - 1, -1, -1):
                if conv[index] is note:
                    del conv[index]
                    break

    @staticmethod
    def _said_last(conv: list[dict[str, Any]], content: str) -> bool:
        """Whether these words are BAXY's last words in the conversation again, letter for letter (folded)."""
        last = next((str(m.get("content") or "") for m in reversed(conv)
                     if m.get("role") == "assistant" and str(m.get("content") or "").strip()), "")
        return bool(last) and re.findall(r"[^\W_]+", _fold(last)) == re.findall(r"[^\W_]+", _fold(content))

    def _say_otherwise(self, request_id: Any, stage: str, turn: dict[str, Any], content: str, reply: dict | None,
                       started: float) -> dict[str, Any]:
        """Aid «say_once» (SAID_AGAIN_NOTE): an answer that is BAXY's last answer again is asked
        once more, words only; the second one is spoken, whatever it says."""
        turn["said_again"] = True
        self._log("turn.repeat", started, None, content=None if turn.get("private") else content)
        if self.foresee is not None:
            try:
                self.foresee(None, True)  # the first sentence the voice synthesized ahead is not the one spoken
            except Exception:  # noqa: BLE001 - a failing look-ahead never fails the answer
                pass
        conv = turn["conv"]
        note = {"role": "user", "content": SAID_AGAIN_NOTE}
        conv.append(note)
        try:
            result = self._next(request_id, stage, turn, final=True)
        finally:
            for index in range(len(conv) - 1, -1, -1):
                if conv[index] is note:
                    del conv[index]
                    break
        if result.get("kind") == "conversation" and not result.get("reply"):
            conv.append({"role": "assistant", "content": content})
            result["reply"] = content
        return result

    def _check_answer(self, request_id: Any, stage: str, turn: dict[str, Any], content: str, reply: dict | None,
                      started: float) -> dict[str, Any] | None:
        """Aid «answer_check» (al máximo, lever 3): the final answer read against the turn's results before it is
        spoken (answer_check.check). Contradicted, the model is asked once more, words only, with a note that says the
        facts that contradict it; its second answer is the one spoken, whatever it says, and the trace keeps both
        checks (turn.check). None: the answer stands as it is."""
        # Aid «check_found» (holdout v6 V6E055): the rule «found» of the check («no encontré X» while a result of the turn
        # found X), an aid of its own; aid «check_read» (holdout v6, falsedades): the rule «read» («no leí X» while a read
        # of the turn brought X whole), another.
        # Aid «check_denial»: the rule «denial» reads the catalog and the conversation's earlier calls.
        # Revisión w11-rev4: with earlier turns trimmed out of the conversation, its earlier calls are not known whole and
        # a try that failed there may be what the answer tells: the rule reads nothing.
        denials = (_aid_on(CHECK_RULE_AIDS["denial"]) and not turn.get("receipts") and not turn.get("checked")
                   and not self.trimmed_turns)
        try:
            catalog = {self.wire_to_op[t["function"]["name"]]: str(t["function"].get("description") or "")
                       for t in self.tools if t["function"]["name"] in self.wire_to_op} if denials else None
            findings = [f for f in check_answer(content, str(turn.get("text") or ""), turn.get("receipts") or [],
                                                self._calls, catalog=catalog,
                                                tries=self._tries(turn["conv"]) if denials else None)
                        if f["rule"] not in CHECK_RULE_AIDS or _aid_on(CHECK_RULE_AIDS[f["rule"]])]
        except Exception as error:  # noqa: BLE001 - a check that fails finds nothing: the answer stands
            # Revisión de calidad: a heuristic that breaks on some answer never takes the turn with it; the trace says
            # it failed (its type only) and the answer is spoken as it is.
            self._log("turn.check", started, None, round=2 if turn.get("checked") else 1, findings=[], kept=False,
                      error=type(error).__name__)
            return None
        private = bool(turn.get("private"))
        shown = [{"rule": f["rule"], "fact": f["fact"]} if private else f for f in findings]
        if turn.get("checked"):
            # The second answer: the trace says whether it still contradicts. Uso real 2026-10-26: it still said
            # «Spotify se cerró» against the results, and was spoken. Still contradicted, the model is told the facts
            # once more (round 3); that answer is spoken as it is, never asked again (no loop). Cutting the sentence the
            # check quotes was left out: the quote is not always the false one («Busqué su ventana.» of «Busqué su
            # ventana. Listo, cerré Paint.»), and what was left would have been the falsehood.
            third = bool(turn.get("checked_again"))
            self._log("turn.check", started, None, round=3 if third else 2, findings=shown, kept=bool(findings))
            if not findings or third:
                return None
            turn["checked_again"] = True
        elif not findings:
            return None
        else:
            turn["checked"] = True
            self._log("turn.check", started, None, round=1, findings=shown, content=None if private else content)
        if self.foresee is not None:
            try:
                self.foresee(None, True)  # the first sentence the voice synthesized ahead is not the one spoken
            except Exception:  # noqa: BLE001 - a failing look-ahead never fails the answer
                pass
        denied = any(f["rule"] == "denial" for f in findings)
        note = {"role": "user", "content": (DENIAL_NOTE if denied else CHECK_NOTE).format(facts=" ".join(
            CHECK_FACT.format(said=f["said"], fact=f["fact"]) for f in findings[:CHECK_FACTS]))}
        conv = turn["conv"]
        conv.append(note)
        try:
            # A denial with no call behind it keeps the tools: the model may do what it had said it could not.
            result = self._next(request_id, stage, turn, final=not denied)
        finally:
            # The note was for that one answer: the conversation keeps what was said, not the check.
            for index in range(len(conv) - 1, -1, -1):
                if conv[index] is note:
                    del conv[index]
                    break
        if result.get("kind") == "conversation" and not result.get("reply"):
            # Nothing written the second time: the first answer is spoken (the trace has it as contradicted).
            conv.append({"role": "assistant", "content": content})
            result["reply"] = content
        elif denied and result.get("kind") != "conversation":
            turn.pop("checked", None)  # it acted: its answer after the results is checked as any other
        return result

    def _tries(self, conv: list[dict[str, Any]]) -> list[tuple[str, str]]:
        """The conversation's calls before this answer as (operation, status of their result): «completed», «failed»,
        «rejected», «needs_confirmation», «cancelled»…, or «unknown» when the result is not there or not a status (a
        body left out, a call never answered). For the rule «denial» of the check."""
        results: dict[Any, str] = {}
        for message in conv:
            if message.get("role") == "tool":
                try:  # the result as the App gave it, before the facts line the mind writes after it
                    facts = json.JSONDecoder().raw_decode(str(message.get("content") or ""))[0]
                except json.JSONDecodeError:
                    facts = None
                status = facts.get("status") if isinstance(facts, dict) else None
                # Revisión de final2: a call the owner switched off in Settings (FieldSettings.Refusal, «*_by_owner») is
                # «rejected» as one refused for its arguments is, but nothing it was asked could have run: a real limit
                # the answer may tell, never a try that left the act to do.
                if status == "rejected" and str(facts.get("error") or "").endswith("_by_owner"):
                    status = "refused_by_owner"
                results[message.get("tool_call_id")] = str(status) if status else "unknown"
        tries = []
        for message in conv:
            for call in message.get("tool_calls") or [] if message.get("role") == "assistant" else []:
                wire = str((call.get("function") or {}).get("name") or "")
                tries.append((self.wire_to_op.get(wire, wire), results.get(call.get("id"), "unknown")))
        return tries

    @staticmethod
    def _doubted(stage: str, turn: dict[str, Any], final: bool) -> bool:
        """Whether this call's decision is read for its doubt: a person's turn deciding, not its last answer, a
        continuation or a heartbeat."""
        return stage == "turn.decide" and not final and not turn.get("beat")

    def _held(self, stage: str, turn: dict[str, Any], final: bool, call: dict[str, Any], reply: dict | None,
              body: dict[str, Any], nth: int = 0) -> str | dict[str, Any] | object | None:
        """The note that holds the turn's first action (or the reply's `nth` call, queued behind it), the call that
        replaces it, UNSURE (in Bypass, the App weighs the doubted call with its arguments before it reads again), or
        None. Layer 0 (BAXY_S1_DOUBT): the
        model's confidence is under the threshold, unless these words answer a question (DOUBT_ASKED) or the call is
        low_reversible, or recoverable_delete and the kernel confirms it. Layer 2
        (BAXY_S1_VETO, with a decision model): under that one, the decision model is asked which of the model's own
        candidates the person meant, and a different answer holds it — or, with BAXY_S1_CORRECT=1 and a tool of
        CORRECTABLE_RISKS, the model fills that tool and it runs instead; a low_reversible call it does not correct
        runs; the answer to layer 2's own question is never turned into another one, nor is the model's reading again
        after either layer (turn["reread"]), save a call the kernel would run unasked (_unasked): that one, at either
        layer, only asks; and, in Bypass, one under either layer's threshold that is another invocation than those
        weighed (P2.43b): UNSURE, or past UNSURE_WEIGHS a question. Asking is never held: it already puts the person in
        the loop; confirming only when it approves under CONFIRM_FLOOR and the person's words are not only a yes
        (PLAIN_YES), whatever System One's own thresholds."""
        if not self._doubted(stage, turn, final) or call["wire"] in (ASK_USER["function"]["name"],
                                                                     CALCULATE["function"]["name"]):
            return None
        # Aid «dated_search» (soak of the fair, 2026-10-27): the web_search the model chose for a dated question or a
        # curiosity asked for, under the threshold, became «¿Quieres que busque…?» 6 times: it is the call that aid asks
        # for, so its doubt does not hold it; the same for the one «named_fact» asks for (code review 2026-10-27), also
        # when the model chose it itself for what or who a named thing is (live on the notebook after the deploy).
        if call["wire"] == "web_search" and ((_aid_on("dated_search") and self._dated(turn["text"]))
                                             or (_aid_on("named_fact") and (turn.get("named")
                                                                            or _asked_about(turn["text"])))):
            return None
        doubt = read_doubt(reply, nth)
        if doubt is None:
            return None
        if call["wire"] == CONFIRM["function"]["name"]:
            # Auditoría de la mente (w8, 2026-10-23): only a «sí» that would approve something is held. With nothing
            # waiting (none, or its question ended unanswered) the call never reaches the App (_result: nothing_pending,
            # or the ended call to make again, which the kernel asks again), and holding it there turned that result
            # into a question that dropped nothing and asked again at every unsure «sí».
            floor = CONFIRM_FLOOR if os.environ.get("BAXY_CONFIRM_FLOOR") is None else _threshold("BAXY_CONFIRM_FLOOR")
            return (DOUBT_NOTE.format(call=call["wire"])
                    if turn.get("pending") and call["arguments"].get("approve") is True
                    and doubt["confidence"] < floor and not _PLAIN_YES.fullmatch(_fold(turn["text"])) else None)
        # Al máximo, System One 2: layer 0 never holds a low_reversible call; its error is undone and the kernel verifies
        # it. On 26 runs of decision2 with System One (2026-10-22) it held 23, 22 of them right without System One (P040
        # ×7, P085 ×15) and none useful; read_only it holds still (24 useful against 5 harmful), and anything riskier.
        # Nor a recoverable_delete the kernel confirms (V9E037): its «sí» names the exact action, and holding it asked in
        # words first and then the kernel asked again. work_loss it still holds (V6D131), and Bypass runs it unasked.
        # P2.34, C16: read again with its tools it could make the same call, and the kernel would run it unasked
        # (_unasked): its doubt asks the person, with no tools, at either layer, also in the reading after another doubt.
        risk = self.risk.get(call["wire"])
        unasked = self._unasked(call["wire"])
        # P2.43b: in Bypass, a reading again (not the person's answer) of another invocation than those weighed is weighed
        # too; past UNSURE_WEIGHS its doubt asks, with no tools, so it neither loops nor runs unweighed.
        weighs = turn.get("weighed") or []
        fresh = turn.get("reread") and _bypass() and not turn.get("answering") \
            and (call["wire"], _call_key(call["arguments"])) not in weighs
        unweighed = UNSURE if len(weighs) < UNSURE_WEIGHS else DOUBT_NOTE.format(call=call["wire"])
        if doubt["confidence"] < _threshold("BAXY_S1_DOUBT") and not turn.get("answering") \
                and (unasked or not turn.get("reread") or fresh) and risk != "low_reversible" \
                and not (risk == "recoverable_delete" and self._kernel_confirms(call["wire"])):
            if unasked:
                return DOUBT_NOTE.format(call=call["wire"])
            if _bypass():
                return unweighed if fresh else UNSURE  # P2.43: the App says whether the kernel would run it unasked
            turn["reread"] = True
            return REREAD_NOTE.format(call=call["wire"])
        # Auditoría de la mente (w8): a decision model not up (loading, or its server gone) answers nothing, so its
        # options are not made: each rival's name was completed on the slot for it (template + complete_name).
        if self.system_one is None or not self.system_one.ready or doubt["confidence"] >= _threshold("BAXY_S1_VETO"):
            return None
        if turn.get("reread") and not unasked:
            # Nor the model's reading again after a doubt (REREAD_NOTE, DOUBT_OTHER_NOTE): it decided. P2.43b: save in
            # Bypass one under BAXY_S1_VETO of another invocation, which the App weighs without the decision model.
            return unweighed if fresh and risk != "low_reversible" else None
        options = self._candidates(call["wire"], doubt, body)
        judged = self.system_one.choose(turn["text"], self._said(), options)
        self._judged = {"options": list(options), **judged} if judged else {"options": list(options), "choice": None}
        if self._unread:
            self._judged["rivals_unread"] = self._unread
        if not judged or judged["choice"] == call["wire"]:
            return None
        corrected = self._corrected(judged["choice"], body, call["wire"])
        if corrected is not None:
            self._judged["corrected"] = True
            return corrected
        if self.risk.get(call["wire"]) == "low_reversible":
            # Al máximo, System One 2: nor does layer 2 turn a low_reversible call into a question; it only corrects it.
            # On the same 26 runs it asked instead of 11, all right without System One (P112 ×4, P124 ×6, P113 ×1);
            # its corrections of them were 6 useful (P257) against 2 harmful.
            return None
        if turn.get("answering_other"):
            return None  # the person already answered layer 2's question about this request
        other = OPTION_TEXT.get(judged["choice"], judged["choice"])
        if unasked:
            return DOUBT_OTHER_ASK_NOTE.format(call=call["wire"], other=other)
        turn["reread"] = True
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

    def _kernel_confirms(self, wire: str) -> bool:
        """Whether the kernel asks the person before this tool runs, whatever its arguments: a risk it always confirms in
        normal mode (CONFIRMED_RISKS), not one of UNCONFIRMED_OPERATIONS, and the mode is not Bypass."""
        return self.risk.get(wire) in CONFIRMED_RISKS and self.wire_to_op.get(wire) not in UNCONFIRMED_OPERATIONS \
            and not _bypass()

    def _unasked(self, wire: str) -> bool:
        """Whether the kernel would run this tool without the person's «sí» though normal mode counts its risk as one to
        confirm: one of CONFIRMED_RISKS it does not confirm now (system.power; any in Bypass), or, in Bypass, one the
        kernel confirms in normal mode and not in Bypass, by the modes it sent (self.confirms; P2.41: of
        external_communication, normal mode asks only for those that reach a person, and Bypass still for message.send).
        P2.41b: a tool the catalog sent without them keeps the rule from before, external_communication."""
        risk, confirms = self.risk.get(wire), self.confirms.get(wire)
        skipped = risk == "external_communication" if confirms is None \
            else "normal" in confirms and "bypass" not in confirms
        return (risk in CONFIRMED_RISKS and not self._kernel_confirms(wire)) or (_bypass() and skipped)

    def _corrected(self, wire: str, body: dict[str, Any], chosen: str = "") -> dict[str, Any] | None:
        """The decision model's tool as a call the model filled itself (piece A), or None — the turn then asks: correcting
        is off, the tool's risk is not in CORRECTABLE_RISKS (or is one of CONFIRMED_RISKS the kernel would not confirm
        now), it has an effect of the catalog the model's own call (`chosen`) did not have, or the model did not write
        that tool's call."""
        risk = self.risk.get(wire)
        effects = set(self.effects.get(wire) or [])
        # Al máximo, System One 4 (decision2 P169, a weekly forecast asked in English, 14 of 14 runs of int0-int4): Qwen
        # chose web_search, Laya weather_current at 0.9, and 5.1 turned the correction into a question because
        # weather_current sends out of the PC — as web_search, the model's own call, already did. A tool that only reads
        # and whose effects the chosen call already has lands nowhere the model had not chosen to go; what it sends is
        # only what the conversation showed (every argument founded, the optional ones too). Keys, clicks and commands
        # (low_reversible and up) still never come from «corrige» (shell_command_run has the same network effect).
        shared = bool(effects) and risk == "read_only" and effects <= set(self.effects.get(chosen) or [])
        if _system_one("BAXY_S1_CORRECT") != "1" or risk not in CORRECTABLE_RISKS \
                or (effects and not shared) or (risk in CONFIRMED_RISKS and not self._kernel_confirms(wire)):
            return None
        # Auditoría de la mente (w8, P4): why a fill did not become the call, in the trace row beside the decision
        # model's answer (system_one.fill): failed (and its error), none (no call written), other (another tool's call)
        # or unfounded (_founded); a correction never tried (off, or the tool not correctable) writes none.
        why = self._judged if self._judged is not None else {}
        try:
            filled = self.server.fill_call(body, wire)
        except Exception as error:  # noqa: BLE001 - a fill that failed falls back to asking
            why["fill"] = {"failed": type(error).__name__}
            return None
        if not filled or filled.get("name") != wire:
            why["fill"] = "none" if not filled else {"other": str(filled.get("name"))}
            return None
        if not self._founded(wire, filled["arguments"], body["messages"], every=shared):
            why["fill"] = "unfounded"
            return None
        return {"id": self._new_id("s1"), "wire": wire, "arguments": filled["arguments"]}

    def _founded(self, wire: str, arguments: dict[str, Any], messages: list[dict[str, Any]],
                 every: bool = False) -> bool:
        """Whether a filled call holds every required argument of its tool and each text or number among them appears
        in what the conversation showed: the person's words or a tool's result (folded, as a whole word). B-MED-1 of the
        notebook (2026-10-22): Laya chose window_snap where Qwen chose window_resolve, and fill_call wrote windowId «1»,
        which no result had listed, and it ran; a web_download got a page of results as its url.
        Al máximo, System One 1: three kinds of value are the catalog's, not the person's words, and count as founded: a
        code of the argument's own enum («downloads» for «Descargas», «pause», «left»), an application or game the mind
        listed to the model in app_open and game_launch, or that game's appId («Worms W.M.D» for «el Worms»), and a file
        name whose name and extension were both said («contrato.pdf» for «el PDF contrato»: Qwen writes it so). Practice
        P203 (26 runs with System One, 2026-10-22): Laya chose file_read at 0.91 in 7 and «corrige» asked every time.
        Ids (windowId, reminderId…) and any other text still have to appear in the conversation or in a result.
        With `every`, the optional arguments it wrote are held to the same rule (one left empty is not written)."""
        tool = next((t["function"] for t in self.tools if t["function"]["name"] == wire), {})
        required = (tool.get("parameters") or {}).get("required") or []
        properties = (tool.get("parameters") or {}).get("properties") or {}
        optional = [name for name in arguments if name not in required
                    and arguments[name] is not None and arguments[name] != ""] if every else []
        seen = _fold(" ".join(str(m.get("content") or "") for m in messages
                              if m.get("role") == "tool" or (m.get("role") == "user"
                                                             and not str(m.get("content") or "").startswith("["))))

        def said(text: str) -> bool:
            return bool(text) and re.search(rf"(?<!\w){re.escape(text)}(?!\w)", seen) is not None

        for name in [*required, *optional]:
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
            # Holdout v5 E062 (dictado): «hasta el setenta» founds 70; a transcript writes small numbers in words.
            number = int(text) if text.isdigit() and int(text) < 1000 else None
            if not said(text) and not (dot and re.fullmatch(r"[a-z0-9]{1,5}", extension) and said(stem)
                                       and said(extension)) \
                    and not (number is not None and (said(_fold(cardinal(number))) or said(cardinal_en(number)))):
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
        self._unread = []  # w8, P4: the rivals left out because their names could not be read, for the trace
        prompt: str | None = None  # the decision's prompt, rendered once for all of its rivals (al máximo V3)
        for token, p in doubt.get("rivals") or []:
            if p < 0.01 or len(names) >= 4:
                continue
            written = doubt.get("written", "") + token
            try:
                if ">" not in written[written.find("<function="):]:
                    prompt = prompt if prompt is not None else self.server.template(body)
                    written += self.server.complete_name(prompt, written)
            except Exception as error:  # noqa: BLE001 - a rival that cannot be read is left out
                self._unread.append({"token": token, "failed": type(error).__name__})
                continue
            at = written.find("<function=")
            names.append(written[at + len("<function="):].split(">")[0].strip() if at >= 0 else "")
        options = {n: described[n] for n in dict.fromkeys(names) if n in described and n != ASK}
        return {**options, ASK: OPTION_TEXT[ASK], ANSWER: OPTION_TEXT[ANSWER]}

    def _result(self, request_id: Any, turn: dict[str, Any], call: dict[str, Any] | None, reply: dict | None,
                stage: str, started: float, content: str) -> dict[str, Any]:
        result: dict[str, Any] = {"type": "turn.result", "id": request_id, "kind": "conversation", "operation": None,
                                  "arguments": None, "question": "", "reply": ""}
        closed = turn.pop("ask_closed", False)  # this decision follows a question not asked again (aid «ask_once»)
        if call is not None and call["wire"] == "ask_user":
            question = " ".join(str(call["arguments"].get("question") or "").split())
            later = [c["id"] for c in turn.get("queue") or []]
            turn["queue"], turn["awaiting"] = [], None
            folded = " ".join(re.findall(r"[^\W_]+", _fold(question)))
            if folded and _aid_on("ask_once") and (closed or any(
                    difflib.SequenceMatcher(None, folded, asked).ratio() >= ASKED_ALIKE
                    for asked in turn.get("questions", []))):
                not_run = ASKED_CLOSED_NOT_RUN if closed else ASKED_AGAIN_NOT_RUN
                for call_id in [call["id"], *later]:
                    turn["conv"].append({"role": "tool", "tool_call_id": call_id,
                                         "content": not_run if call_id == call["id"] else NOT_RUN})
                self._log(stage, started, reply, text=None if turn.get("private") else turn["text"],
                          kind="ask_repeat_closed", operation=None, arguments=None, content=None)
                # Feria 2026-10-27: the decision after it had no tools, though the answer to the question asked for one
                # (the topic of a presentation to make: it said it could not make it without one). It keeps them; only
                # asking is closed in it, and asking there again ends the turn in words.
                turn["ask_closed"] = not closed
                return self._next(request_id, stage, turn, final=closed)
            if folded:
                turn.setdefault("questions", []).append(folded)
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
            # A question that ended unanswered just before these words is told once, as what it is, and the model may
            # call that tool again (the kernel asks again for that exact invocation) or answer in words.
            ended = turn.pop("ended", None)
            told = ended_result(ended) if ended else NOTHING_PENDING
            for call_id in [call["id"], *(c["id"] for c in turn.get("queue") or [])]:
                turn["conv"].append({"role": "tool", "tool_call_id": call_id,
                                     "content": told if call_id == call["id"] else NOT_RUN})
            turn["queue"], turn["awaiting"] = [], None
            self._log(stage, started, reply, text=None if turn.get("private") else turn["text"],
                      kind="confirmation_ended" if ended else "nothing_pending",
                      operation=ended["operation"] if ended else None, arguments=None, content=None)
            return self._next(request_id, stage, turn, final=not ended)
        elif call is not None and call["wire"] == CALCULATE["function"]["name"]:
            # Computed here, never handed to the App; what the model wrote beside it waits for the value. Code review
            # 2026-10-27: the App's step budget never sees these calls, so the same expression again closes the turn's
            # calls, as a repeat the App runs does (same_call_closes).
            computed = turn.setdefault("calculated", [])
            if _call_key(call["arguments"]) in computed and _aid_on("same_call_closes"):
                return self._close_repeat(request_id, turn, call, reply, stage, started, "same_call_closed",
                                          SAME_CALL_NOT_RUN, SAME_CALL_REFUSED)
            computed.append(_call_key(call["arguments"]))
            kind = "calculated"
            try:
                told = json.dumps({"status": "completed",
                                   "value": evaluate(str(call["arguments"].get("expression") or ""))},
                                  ensure_ascii=False)
            except ValueError as error:
                told, kind = json.dumps({"status": "failed", "error": str(error)}), "calculation_failed"
            for call_id in [call["id"], *(c["id"] for c in turn.get("queue") or [])]:
                turn["conv"].append({"role": "tool", "tool_call_id": call_id,
                                     "content": told if call_id == call["id"] else CALCULATED_FIRST})
            turn["queue"], turn["awaiting"] = [], None
            self._log(stage, started, reply, text=None if turn.get("private") else turn["text"], kind=kind,
                      operation=None, arguments=None if turn.get("private") else call["arguments"], content=None)
            # Code review 2026-10-27: new expressions each time never reach the App's budget either; past
            # CALCULATIONS the answer is in words.
            return self._next(request_id, "turn.continue", turn, final=len(computed) >= CALCULATIONS)
        elif call is not None:
            name = (CONFIRM_OPERATION if call["wire"] == CONFIRM["function"]["name"]
                    else self.wire_to_op.get(call["wire"], call["wire"]))
            refused = self._repeat_refused(turn, name, call)
            if refused:
                return self._close_repeat(request_id, turn, call, reply, stage, started, *refused)
            unopened = self._unopened(turn, call)
            if unopened:
                return self._unopened_back(request_id, turn, call, reply, stage, started, unopened)
            turn["awaiting"] = call["id"]
            turn["calling"] = name
            turn["calling_args"] = json.dumps(call["arguments"], sort_keys=True, ensure_ascii=False)
            arguments = self._expand({**call["arguments"], **self.constants.get(name, {})})
            if name == "web.fetch":
                arguments = web_focus.widen(arguments)  # goal h-web: it reads a wider part
            result.update(kind="action", operation=name, arguments=arguments)
            if turn.get("unsure") is call:
                result["unsure"] = True
        elif content:
            result.update(reply=content)
        doubt_of = {"doubt_of": turn.pop("doubt_of")} if "doubt_of" in turn else {}
        if str(result["operation"] or "").startswith("memory.") or str(doubt_of.get("doubt_of")).startswith("memory."):
            turn["private"] = True
        private = bool(turn.get("private"))
        # What the person keeps in memory stays out of the trace, as in the App's (NativeTurnLoop): from the memory
        # call on, their words, the calls' arguments and the model's text.
        self._log(stage, started, reply, text=None if private else turn["text"],
                  kind="doubt_unsure" if result.get("unsure") else result["kind"], operation=result["operation"], arguments=call["arguments"] if call and not private else None,
                  content=None if private else content, **doubt_of)
        return result

    @staticmethod
    def _repeat_refused(turn: dict[str, Any], name: str, call: dict[str, Any]) -> tuple[str, str, str] | None:
        """Aids «same_call_closes» and «look_click_cap» (LOOK_CLICK_PAIRS): whether this call of the model is one the
        mind does not hand to the App, as (the trace's kind, its result, its facts); None: it runs."""
        arguments = _call_key(call["arguments"])
        if (call["wire"] == "input_visible_click" and _aid_on("close_unsaid")
                and _CLOSES.match(_fold(str(call["arguments"].get("label") or "")))
                and not _CLOSE_SAID.search(_fold(str(turn.get("text") or "")))):
            return "close_unsaid", CLOSE_NOT_RUN, CLOSE_REFUSED
        # Since the last other call that acted, whatever it said (a window already gone, an app opened: the same close
        # runs again); its first result since then is the earlier one.
        unchanged, first = False, None
        for receipt in turn.get("receipts") or []:
            if _same_ended(receipt, call["wire"], call["arguments"], VERIFICATION["unchanged"], SET_BY_SAME):
                unchanged, first = True, first or receipt
            elif not receipt.get("read"):
                unchanged = False
                first = receipt if _same_ended(receipt, call["wire"], call["arguments"], *COMPLETED_OUTCOMES) else None
        if unchanged and first and _aid_on("same_call_closes"):
            return ("unchanged_closed", json.dumps({**UNCHANGED_NOT_RUN, "earlier": json.loads(first["observation"])},
                                                   ensure_ascii=False), UNCHANGED_REFUSED)
        if turn.get("same_told_call") == [name, arguments] and _aid_on("same_call_closes"):
            return "same_call_closed", SAME_CALL_NOT_RUN, SAME_CALL_REFUSED
        if (call["wire"] == "input_visible_click" and turn.get("look") and _aid_on("look_click_cap")
                and (turn.get("look_clicks") or {}).get(json.dumps([*turn["look"], arguments], ensure_ascii=False),
                                                       0) >= LOOK_CLICK_PAIRS):
            return "look_click_closed", LOOK_CLICK_NOT_RUN, LOOK_CLICK_REFUSED
        # Uso real 2026-10-26: the same click on Spotify («Reproducir», the same index) failed five times in a row
        # (protected_window), a look between each that never saw quite the same, for a minute and a half: a click that
        # did not complete LOOK_CLICK_PAIRS times with these arguments since the last call that changed something is
        # not made again, whatever the looks saw (after «Archivo» opened its menu, «Guardar como» runs again).
        if call["wire"] == "input_visible_click" and _aid_on("look_click_cap"):
            missed = 0
            for receipt in turn.get("receipts") or []:
                if receipt.get("completed") and not receipt.get("read"):
                    missed = 0
                elif (receipt.get("tool") == call["wire"] and not receipt.get("completed")
                      and _call_key(receipt.get("arguments") or {}) == arguments):
                    missed += 1
            if missed >= LOOK_CLICK_PAIRS:
                return "look_click_closed", LOOK_CLICK_NOT_RUN, LOOK_CLICK_REFUSED
        # Uso real 2026-10-26: «qué es la inteligencia artificial» read the same Wikipedia page 14 times, only its
        # maximumCharacters going up by 1000, 43 s for one sentence (same_call_closes never saw the same arguments): a
        # page already read LOOK_CLICK_PAIRS times in the turn is not read again, whatever the size asked.
        if call["wire"] == "web_fetch" and _aid_on("same_call_closes"):
            url = str(call["arguments"].get("url") or "").strip().rstrip("/")
            read = sum(r.get("tool") == "web_fetch"
                       and str((r.get("arguments") or {}).get("url") or "").strip().rstrip("/") == url
                       for r in turn.get("receipts") or [])
            if url and read >= LOOK_CLICK_PAIRS:
                return "same_call_closed", SAME_CALL_NOT_RUN, SAME_CALL_REFUSED
        # Uso real 2026-10-26: «baja el volumen a 30» unmuted the PC, then muted it, then unmuted it… seven times, the
        # person having asked for neither: a call that only turns back a yes/no an earlier call of the same operation
        # set in this turn (it would undo what the turn did) is not made.
        if _aid_on("same_call_closes") and any(
                r.get("tool") == call["wire"] and r.get("completed") and not r.get("read")
                and _flips(r.get("arguments") or {}, call["arguments"]) for r in turn.get("receipts") or []):
            return "flip_closed", FLIP_NOT_RUN, FLIP_REFUSED
        return None

    def _close_repeat(self, request_id: Any, turn: dict[str, Any], call: dict[str, Any], reply: dict | None,
                      stage: str, started: float, kind: str, result: str, refused: str) -> dict[str, Any]:
        """A refused repeat (_repeat_refused) ends its turn's calls: it and the calls queued behind it do not run, its
        result says why with the turn's facts, and the model answers in words from what the results show, as when the
        App closes a turn (NO_MORE_CALLS)."""
        done = turn.setdefault("done", [])
        done.append(f"{call['wire']} → {refused}")
        line = _said_once(done) if _aid_on("facts_once") else done
        for later in [call, *(turn.get("queue") or [])]:
            told = result + TURN_FACTS + "; ".join(line) + "]" + NO_MORE_CALLS if later is call else NOT_RUN
            turn["conv"].append({"role": "tool", "tool_call_id": later["id"], "content": told})
            turn.setdefault("receipts", []).append({
                "op": self.wire_to_op.get(later["wire"], later["wire"]), "tool": later["wire"],
                "arguments": later["arguments"], "observation": result if later is call else NOT_RUN,
                "outcome": GIST_NOT_RUN, "completed": False,
                "read": self.risk.get(later["wire"]) == "read_only"})
        turn["queue"], turn["awaiting"] = [], None
        private = bool(turn.get("private"))
        self._log(stage, started, reply, text=None if private else turn["text"], kind=kind,
                  operation=self.wire_to_op.get(call["wire"], call["wire"]),
                  arguments=None if private else call["arguments"], content=None)
        return self._next(request_id, stage, turn, final=True)

    def _unopened(self, turn: dict[str, Any], call: dict[str, Any]) -> list[str]:
        """Aid «unopened_app»: the installed applications the person's words in this turn name, when this call types or
        presses a key with no window and no field, the turn has not told it yet, and no completed call of the turn
        opened, focused or resolved any of them, or acted naming one; empty, it runs. A name that is in a text typed in
        this turn is what is written, not where."""
        arguments = call["arguments"]
        receipts = turn.get("receipts") or []

        def targeted(given: dict[str, Any]) -> bool:
            return any(given.get(key) not in (None, "") for key in TARGET_ARGUMENTS)

        # Not when the turn already acts on a window it looked at (a typing with window, then its Enter).
        if (call["wire"] not in WRITES_TO_FRONT or turn.get("beat") or turn.get("unopened_told")
                or not _aid_on("unopened_app") or targeted(arguments)
                or any(r.get("completed") and targeted(r.get("arguments") or {}) for r in receipts)):
            return []
        said = _words(str(turn.get("said") or turn.get("text") or ""))
        written = [arguments, *(r.get("arguments") or {} for r in receipts if r.get("tool") in WRITES_TO_FRONT)]
        typed = _words(" ".join(str(given.get(key) or "") for given in written for key in ("text", "replacing")))
        named = [name for name in dict.fromkeys(self.names)
                 if _words(name).strip() and _PLACE.search(said.replace(_words(name), " \0 "))
                 and _words(name) not in typed]
        if not named:
            return []
        reached = "".join(_words(json.dumps(r.get("arguments"), ensure_ascii=False) + " " + _as_read(r.get("observation")))
                          for r in receipts if r.get("completed") and r.get("tool") not in WRITES_TO_FRONT
                          and (r.get("tool") in OPENS_WINDOW or not r.get("read")))
        return [] if any(_words(name) in reached for name in named) else named

    def _unopened_back(self, request_id: Any, turn: dict[str, Any], call: dict[str, Any], reply: dict | None,
                       stage: str, started: float, applications: list[str]) -> dict[str, Any]:
        """A typing or a key held by «unopened_app» goes back to the model with why, and the calls queued behind it
        (chosen on the same reading) do not run: the model decides again, with its tools."""
        turn["unopened_told"] = True
        done = turn.setdefault("done", [])
        done.append(f"{call['wire']} → {UNOPENED_REFUSED}")
        line = _said_once(done) if _aid_on("facts_once") else done
        result = unopened_not_run(applications)
        for later in [call, *(turn.get("queue") or [])]:
            told = result + TURN_FACTS + "; ".join(line) + "]" if later is call else NOT_RUN_AFTER
            turn["conv"].append({"role": "tool", "tool_call_id": later["id"], "content": told})
            turn.setdefault("receipts", []).append({
                "op": self.wire_to_op.get(later["wire"], later["wire"]), "tool": later["wire"],
                "arguments": later["arguments"], "observation": result if later is call else NOT_RUN_AFTER,
                "outcome": GIST_NOT_RUN, "completed": False,
                "read": self.risk.get(later["wire"]) == "read_only"})
        turn["queue"], turn["awaiting"] = [], None
        private = bool(turn.get("private"))
        self._log(stage, started, reply, text=None if private else turn["text"], kind="unopened_app",
                  operation=self.wire_to_op.get(call["wire"], call["wire"]),
                  arguments=None if private else call["arguments"], content=None)
        return self._next(request_id, "turn.continue", turn)

    # ---- trace ---------------------------------------------------------------------------------------------
    def forget_trace(self) -> bool:
        """Auditoría de la mente (w8, 2026-10-23): the person had BAXY forget everything («olvida todo») or deleted every
        conversation, and the App deletes its own conversation log then; this trace kept their words, BAXY's answers and
        the calls' arguments in clear text, and so did its archive (turns.jsonl.1, __main__.bounded_trace). Both go, the
        way the voice's rows are written (one at a time); what comes after is traced again. Whether none is left (a file
        another reader holds open is emptied instead; if not even that, it stays and the next forget takes it)."""
        left = False
        with self._log_lock:
            for path in (self.trace, self.trace.with_name(self.trace.name + ".1")):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    try:
                        path.open("w", encoding="utf-8").close()
                    except OSError:
                        left = True
        return not left

    def _log(self, stage: str, started: float, reply: dict[str, Any] | None, **fields: Any) -> None:
        timings = (reply or {}).get("timings") or {}
        # Every time of the trace is read on perf_counter (al máximo V4): on Windows, Python 3.12's monotonic clock
        # moves in steps of ~15.6 ms, and every ms was a multiple of it. The voice's times (voice.speak) too.
        row = {"t": _dt.datetime.now().isoformat(timespec="milliseconds"), "stage": stage,
               "ms": round((time.perf_counter() - started) * 1000),
               "cache_n": timings.get("cache_n"), "prompt_n": timings.get("prompt_n"), "prompt_ms": timings.get("prompt_ms"),
               "predicted_n": timings.get("predicted_n"), "predicted_ms": timings.get("predicted_ms"), **fields}
        if timings:
            # Noche P0.5: prompt_n is only what was read again. With the whole prompt (usage) and the prefix (tools,
            # system and the warm-up's few words), each prompt splits into prefix, history and what is new (within those
            # few tokens), and a cut shows as the cache it lost.
            row.update(prompt_tokens=((reply or {}).get("usage") or {}).get("prompt_tokens"),
                       prefix_n=self.prefix_tokens)
        doubt = read_doubt(reply, fields.get("call_index") or 0)  # P2.40: the doubt of the call held, if queued
        if doubt is not None:
            doubt.pop("written", None)  # the call's own text up to its weakest token: only for reading the rivals
            row["doubt"] = doubt
        if self._judged is not None and stage.startswith("turn."):
            # Only a turn's own row carries the decision model's answer: the voice thread logs here too (voice.speak).
            row["system_one"], self._judged = self._judged, None
        self._write_row(row)

    def _write_row(self, row: dict[str, Any]) -> None:
        holding = self._holding
        if holding is not None and holding[0] == threading.get_ident():
            holding[1].append(row)  # a decision made early: written only if it is used (early.py)
            return
        try:
            line = whole_code_points(json.dumps(row, ensure_ascii=False, default=str))  # a lone surrogate: U+FFFD
            with self._log_lock, self.trace.open("a", encoding="utf-8") as out:
                out.write(line + "\n")
        except OSError:
            pass
