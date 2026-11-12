"""Aid «answer_check» (al máximo, lever 3 of INVESTIGACION_PALANCAS_2; «Tool Receipts», arXiv 2603.10060): before the
model's final answer is spoken, its claims are read against the turn's own results by rules on typed fields. A finding
is a fact that contradicts a phrase of the answer; the mind then asks the model once more with that fact
(mind.CHECK_NOTE), and every word stays the model's (invariant 5). Nothing here writes a reply, chooses a tool or runs
anything.

The rules, each kept narrow (a false finding costs a regeneration and a worse sentence):

- ``not_completed``: «abrí/cerré/borré…» (or «se cerró», «quedó cerrado») while every call of that kind in the turn
  failed, stayed unsure, waited for a «sí» or did not run, and none completed earlier in the session. A call that only
  stayed unsure contradicts only a bare claim: not one that says its limit, a passive («se envió a…») or one after a look.
- ``no_call``: the same claim with no call of that kind in the turn nor, when the whole session is known, in it; not for
  what an answer may make in words («te escribí un resumen», «te creé una lista»).
- ``implied_yes``: «Sí…» to «¿abriste/cerraste…?» with no completed call of that kind in the session (F002, F015).
- ``unread_state``: «sigue abierto», «no está abierto» to a question about the PC in a session with no call at all.
- ``pending_cell`` (encargo 75): the turn's last call left a text pending over a grid's cell (its receipt's «pendingText»).
- ``stale_state`` (encargo 56): «ya está instalado», «sigue sonando», «ya se descargó» (a state of now) in a turn where
  nothing read anything nor completed an act of that kind, while the last result of that kind in the conversation shows
  another state (its ``state``/``playbackStatus``, or a field named as the state that says false: «queued», 0 of 0
  bytes) or did not complete. A result that shows that state, or an act of that kind that completed and shows none,
  backs it, and so does a failure whose error code ends by naming it or whose fields say it («memory_disabled» for «la
  memoria está apagada»: a reading of it, encargo 76); one whose body was left out says nothing, and a call that waited
  for the person's «sí» (needs_confirmation) ran nothing: the last result is the one before it (uso-87).
- ``place``: «en la biblioteca» after an app_open that only asked for that place and nothing looked after it (F019).
- ``partial``: «no está / no hay / revisé todo / en ningún otro lugar» after a read or a search whose result says it
  covered only part (readInPart, searchScope, subfoldersNotOpened, timeLimitReached, entriesShown < count, a view cut,
  searchedElsewhere false, a ``covers`` that says what it read, a ``checked`` false: it did not look at what its call
  is for finding out) or after a look that failed with an error that is not itself a «not found», unless the
  sentence itself says the limit («en lo que leí», «sólo revisé…»).
- ``number``: a volume, brightness or percentage, or a size in KB/MB/GB, that matches no number of the turn's results
  (0,69 % for a reading of 69 or a fraction 0.69; 3 GB for 3 145 728 bytes).
- ``folder``: a folder named where something was written, created, added or saved (BAXY-bench, Escritorio, Descargas…,
  the user's folder) that is not where the result says it went (fullPath; BAXY's sandbox is not the person's folder); an
  absolute path in the answer that no result shows.
- ``asked_folder``: the person named a folder, the result put it elsewhere, and the answer tells it as done in no place.
- ``named_control``: «no hay un botón «X»», «no veo ningún botón X» while a reading of the window in the turn
  (input_visible_controls) shows X in its controls or its text, which it says is pressed by its text (F019).
- ``already``: «ya estaba» after a call that changed something, with nothing in the turn saying it was already so
  (verification unchanged, alreadyRunning, after.same).
- ``saved_name``: «guardé lista.txt», «lo guardé como notas.docx» while no result of the turn shows that name and what
  was read from the last act that could save on shows another: a window's title («lista pilas, cables.txt: Bloc de
  notas», «x.png - Paint», not a title it left) or the name of a file result (E017: «Guardar como» pressed with no name
  typed). Only a name of the same extension or the same stem counts as the saved file's (a page «Amazon.com: …» is
  not); another extension is another file (lista.md is not lista.txt). Nothing shown, nothing said.
- ``found``: «no encontré ideas.txt» while a result of the turn names that file as one it found, even one that failed
  for another reason: a ``relativePath`` (and the ``name`` beside it) of its own or of one of its listed files (V6E055:
  an edit refused with known_file_search_incomplete had found ideas.txt in BAXY-bench). The name is compared with its
  accents (a name alike that a search offers differs in them), and a place named after it must hold the file found.
- ``read``: «no leí recado.txt», «no pude leer / no he leído / no pude abrir recado.txt» (or «I couldn't read
  recado.txt») while a read of the turn completed with that file's text, whole: a non-empty text and nothing left
  unread (readInPart, hasMore, endReached false, unread PDF pages). The name is compared as in ``found``; «no pude abrir»
  is not read against a read when an open of the turn did not complete (it may tell that one).
- ``denial``: in a turn with no call, «no puedo / no se puede / no tengo acceso / I can't» followed in its clause by an
  act (borrar, copiar, mover, leer, abrir, contar, crear, escribir, buscar, acceder) and a thing of the PC the tools
  reach (a file or folder, a note, a window's text), while an operation of the session's catalog does that act on it
  (DENIED_OPS). Not when the sentence gives a limit of its own (a confirmation, a protected window, something not
  installed or not found, a place outside the person's folders, a program) or a condition («si…»), nor when an earlier
  call of that act did not complete (it may be what the answer tells), except one the core refused for its arguments.
- ``denial_lookup`` (cosecha 04-11 F18): in such a turn, the same «no puedo / no tengo herramientas para» about anything else,
  with the same exceptions, while the catalog has web.search: the fact is what web.search reaches, and the model reads what
  the person asked. «Indícame cómo publicar en Steam» → «No tengo herramientas para abrir Steam, navegar…».
- ``empty_lookup`` (cosecha 04-11 F13, F35): the last call of the turn read BAXY's memory or this PC's game manifests and found
  nothing, and no search ran: the fact is how far that look reaches, and the model reads what the person asked.
- ``unread_memory`` (MEM1, VIVO12 P1): «recuerdo que / me dijiste que / lo tengo guardado / según mi memoria / I remember»
  (something of the person told as remembered) while no call to the memory completed in the conversation: what the person
  told BAXY in another conversation only a memory call brings. «¿Cuál es mi color favorito?» → «Recuerdo que tu color
  favorito es el azul» with turquesa kept and nothing read (4 of 4 in a new conversation). Also «no tengo guardado / mi
  memoria no guarda» with the memory among the tools and no memory call at all. Only when the whole session is known;
  the fact names the call that reads the memory, or says the memory is not among the tools. MEM2 (VIVOM1): in any person
  («Sí, te acuerdas que tu color favorito es el azul», 5 of 6 live), and only of the person (tu/your in the answer, mi/my
  in the question): «¿Recuerdas cómo se hace una tortilla?» → «No tengo esa información guardada» is not one.
- ``unbacked_memory`` (MEM2): the memory was read in the conversation and what the answer tells as remembered is in no
  value it brought («Recuerdo que tu color favorito es el azul» with turquesa read); the fact says what it brought.
- ``memory_subject`` (MEM2, VIVOM1 H10): «Tu color favorito es el verde agua» from the record «color favorito de mi
  hija»: a value given to the person (tu/your) whose record is named «de/of X» or «X's», X said by neither the person nor
  the clause that gives it.
- ``output``: «salió «Hola mundo»», «imprimió «3»» (an output quoted after a verb that tells one) in a turn with calls
  while no result of the turn shows that text (uso real 2026-10-26: a console command sent without reading its output
  and window looks that failed, then «el programa se ejecutó y salió «Hola mundo»»).
- ``answered_by``: a search engine of BAXY's table (search_addresses.v1.json: Google, Bing, DuckDuckGo…) named in a
  statement of a turn with a completed web.search, while no result of the turn brings that name and the statement does
  not name the source that answered («answeredBy») (R7-NB-3: «Google me dio…» when DuckDuckGo answered).
- ``browser`` (encargo 70): «abrí Gmail en Chrome» where Chrome is an application an app_open of the turn opened, while
  a completed result of the turn says the page opened in another browser (its ``browser``: «Opera GX») and the answer
  names that one nowhere (uso real 03-11, F6). The names come from the turn's results only.
- ``future_past`` (encargo 71): a date after today told with a verb in the past in its clause («se estrenó el 20 de
  diciembre de 2026» on 3 November 2026), in a turn with a completed result. Only the date against the clock and the form
  of the verb are compared, never which verb: not one that tells the date through «que» or that the date follows «hasta»,
  «para» or «al» («anunció que saldrá el…», «se retrasó hasta marzo»). A date with no year takes it from a result.
- ``weekday_date`` (VER1, PR-03 «en siete días es el viernes 12»): a weekday told of a date that falls on another one.
  Only the calendar is compared: the weekday right before its date («viernes 12», «viernes 12 de noviembre», «Friday,
  November 13th») or after it as what it is («el 27 de noviembre es un jueves»). A date with no year is the nearest one
  to today, and one with no month is read in last month, this one and the next: no finding if any falls on that
  weekday. Not a pair the person's words or a result of the turn bring as it is, nor a date a result gives on that
  weekday (system.time's calendar).
- ``unread_date`` (VER1, PR-03): such a pair that the calendar has, for a date other than today's, that no result or
  argument of the turn nor the person's words give («pasado mañana es martes 10» on Monday the 9th, with no call): a
  date the model counted. Told once more with its tools, so system.time works it out.
- ``past_future`` (VER1, G-03): the mirror of ``future_past``: a date wholly before today told as coming, in a turn
  with a completed result («la próxima reunión es el 27-28 de octubre de 2026» on 9 November 2026; «la final se jugará en
  octubre de 2026»). Only the date against the clock and the form are compared: a verb in the future or «próximo» before
  the date in its clause, or the date first and the future after it. Not a clause that denies it, asks it or says «si».
- ``unmatched`` (encargo A5, answer_grounding.py): the attribution to a video of words that its result says
  (``titleMatchesQuery: false``) it did not match.
- ``recognized_number`` (uso-89): a number that a look of the turn gives only in its «Texto» lines (OCR) while the
  window gave two or more controls, and that neither those controls, another result nor the person's words give (R06:
  «829» from «calificaclon 829» for the page's «8,9»). Numbers are compared as «8,9» = «8.9», «12.490» = «12490».
- ``already_open`` (uso-106, F20): «abrí Steam» when the only act of the turn that could have opened it is an app_open whose
  result says it was already running: that call opened nothing (it may have brought it to the front).
- ``which_way`` (RUT8, the owner's routine «tiempo»): «pausé», «lo puse en pausa», «ya estaba sonando» after a
  media_control of the turn whose result says it was paused and now plays (its ``previousPlaybackStatus`` and
  ``playbackStatus``), or «reanudé», «ahora suena», «estaba pausado» after one that says it was playing and is now
  paused. Not in a turn that went both ways, nor against a result that does not say the state before.
- ``internal`` (uso-90): a tool's name as the model calls it or a code of a result of the turn, letter for letter as a
  whole word («media_play_youtube», «page_requires_sign_in»): BAXY's own words, never the person's. A second answer that
  carries one is not spoken (Mind._check_answer).
- ``unopened_page`` (encargo A10, U31 with the fleet's receipts, diag-b5bd): a browser navigation of the turn failed, a
  search ran after it (a web.search, or the search page a web.search's result gave), and no later call opened another page
  (no browser.navigate to an address that is not that search page, no click) before the answer. Also with no search in the
  turn at all, unless the address is one the person said themselves (its 404 is what they asked; held-out uso-105: 404 and
  «Netflix no tiene esa página»). The fact is the failure and that nothing opened after it; the note keeps the tools and
  brings the person's words, and the model decides. Nothing of the answer's words is read. Flota: «Open the official Python
  docs page…» → 404, search refused, DuckDuckGo in the browser, results read, and the answer «DuckDuckGo found the venv page
  instead» with the page never opened (3 of 3 traces).

What never counts as a claim: a sentence or the part of one that is a question, a clause with «no / nunca / sin /
tampoco» before the verb («no pude abrirlo», «no lo cerré»), a conditional «si…», quoted text, or a promise («voy a
abrir»). Spanish is read folded (no accents, lower case) with the same length as the original, so quotes are the
model's own words.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import unicodedata
import pathlib
from typing import Any, Callable, Iterable

from .answer_grounding import unmatched as _unmatched
from .wire import operation_of, plain

# How a completed call ended, in mind._outcome's words (mind.COMPLETED_OUTCOMES): passed in by the mind, so this module
# never re-derives the outcome.
Receipt = dict[str, Any]  # {"op": "app.open", "tool": "app_open", "arguments": {...}, "observation": str, "outcome": str,
#                            "completed": bool, "read": bool (its catalog risk only reads: it never did an act)}
Call = tuple[str, bool, bool]  # a call of the session: (operation, completed, read)

# ---- what an answer claims ------------------------------------------------------------------------------------------
# Kinds of act: the folded first-person preterite (and «he + participle») that claims one, the passive or state forms
# that also claim it (only read against failed calls), and the operations (prefixes) that can do it. Generous on
# purpose: a claim is contradicted only when no plausible operation did it.
ANY = ("",)  # every operation
KINDS: dict[str, dict[str, Any]] = {
    "abrir": {"said": r"abri|he abierto|te abri|reabri",
              "passive": r"se (?:abrio|abrieron)|quedo abiert[oa]s?",
              "asked": r"abriste|abristes",
              "ops": ("app.open", "app.restart", "file.open", "filesystem.folder.open", "filesystem.file.open",
                      "browser.", "game.launch", "game.store", "streaming.", "media.play", "input.", "system.settings.",
                      "web.", "office.document.create", "document.presentation.create", "calculator.",
                      "shell.command.run", "client.channel.locate", "client.channel.open", "window.")},
    "cerrar": {"said": r"cerre|he cerrado",
               "passive": r"se (?:cerro|cerraron)|quedo cerrad[oa]s?",
               "asked": r"cerraste|cerrastes",
               "ops": ("app.close", "app.restart", "window.close", "system.process.terminate", "browser.control",
                       "input.", "game.install.cancel")},
    "volumen": {"said": r"subi|baje|he subido|he bajado",
                "passive": "",
                "asked": r"subiste|bajaste",
                "ops": ("audio.", "system.settings.", "display.", "media.", "input.", "browser.control")},
    "silenciar": {"said": r"silencie|he silenciado|quite el silencio|active el sonido",
                  "passive": r"(?:se silencio|quedo silenciad[oa])",
                  "asked": r"silenciaste",
                  "ops": ("audio.", "media.", "input.", "client.microphone", "client.deafen", "system.settings.")},
    "escribir": {"said": r"escribi|he escrito|sobrescribi|he sobrescrito|tecle|teclee",
                 "passive": "",
                 "asked": r"escribiste",
                 "ops": ("input.", "file.write", "file.edit", "note.", "message.", "clipboard.", "office.", "memory.",
                         "filesystem.", "task.", "calendar.", "email.", "document.")},
    "guardar": {"said": r"guarde|he guardado|anote|he anotado",
                "passive": r"se guardo|quedo guardad[oa]",
                "asked": r"guardaste",
                "ops": ("file.write", "file.edit", "input.", "memory.", "note.", "office.", "filesystem.", "backup.",
                        "task.", "clipboard.", "web.download", "capture.", "document.", "calendar.", "schedule.")},
    # TPV7 (VIVO11, 11-11-2026): «Nota creada: "Hola"» after a «sí» that only turned the tool on. The bare participle
    # («nota creada», «recordatorio creado») is the state form of this kind, read like every passive: only against a
    # call of its kind that the turn tried and did not complete.
    "crear": {"said": r"cree|he creado",
              "passive": r"se creo|cread[oa]s?",
              "asked": r"creaste",
              "ops": ("file.write", "file.edit", "filesystem.", "note.", "task.", "calendar.", "schedule.", "office.",
                      "document.", "backup.", "file.compress", "memory.")},
    "borrar": {"said": r"borre|elimine|he borrado|he eliminado|vacie|he vaciado|(?:mande|envie|movi|lleve) a la papelera",
               "passive": r"se (?:borro|elimino|borraron|eliminaron)|quedo borrad[oa]",
               "asked": r"borraste|eliminaste|vaciaste",
               "ops": ("filesystem.", "note.", "task.", "memory.", "system.recyclebin", "input.", "file.",
                       "schedule.", "calendar.", "game.uninstall", "package.uninstall")},
    "enviar": {"said": r"(?:envie|mande|he enviado|he mandado)(?! a la papelera)",
               "passive": r"se (?:envio|mando)",
               "asked": r"enviaste|mandaste",
               "ops": ("message.", "email.", "peripheral.print", "web.", "browser.", "clipboard.", "input.")},
    "mover": {"said": r"(?:movi|copie|pegue|he movido|he copiado|he pegado)(?! a la papelera)",
              "passive": r"se (?:movio|copio)",
              "asked": r"moviste|copiaste|pegaste",
              "ops": ("filesystem.", "clipboard.", "input.", "window.", "file.")},
    "agregar": {"said": r"agregue|anadi|he agregado|he anadido",
                "passive": "",
                "asked": r"agregaste|anadiste|anotaste",
                "ops": ("file.", "task.", "note.", "calendar.", "schedule.", "memory.", "input.", "office.",
                        "clipboard.", "filesystem.")},
    "ventana": {"said": r"minimice|maximice|restaure|he minimizado|he maximizado|traje al frente|puse al frente",
                "passive": r"(?:se minimizo|se maximizo|quedo minimizad[oa]|quedo maximizad[oa])",
                "asked": r"minimizaste|maximizaste",
                "ops": ("window.", "app.open", "input.")},
    "reproducir": {"said": r"pause|reanude|reproduje|he pausado|he reanudado",
                   "passive": r"se paus[oó]",
                   "asked": r"pausaste|reanudaste",
                   "ops": ("media.", "streaming.", "browser.", "input.", "app.open")},
    "lanzar": {"said": r"lance|inicie|ejecute|he lanzado|he iniciado|he ejecutado",
               "passive": "",
               "asked": r"lanzaste|iniciaste|ejecutaste",
               "ops": ("game.launch", "app.", "shell.command.run", "streaming.", "media.", "input.", "browser.")},
    "encender": {"said": r"active|desactive|encendi|apague|he activado|he desactivado|he encendido|he apagado",
                 "passive": "",
                 "asked": r"activaste|desactivaste|encendiste|apagaste",
                 "ops": ("system.", "bluetooth.", "wifi.", "display.", "audio.", "memory.", "input.", "client.",
                         "network.", "app.close", "media.")},
    "instalar": {"said": r"instale|desinstale|descargue|he instalado|he desinstalado|he descargado",
                 "passive": r"se (?:instalo|desinstalo|descargo)",
                 "asked": r"instalaste|desinstalaste|descargaste",
                 "ops": ("package.", "game.install", "game.uninstall", "web.download", "software.")},
    "marcar": {"said": r"marque|tache|he marcado",
               "passive": "",
               "asked": r"marcaste",
               "ops": ("task.", "note.", "input.", "office.")},
    # Generic acts and looks: contradicted only when nothing at all completed.
    "hacer": {"said": r"puse|cambie|ajuste|configure|programe|he puesto|he cambiado|he ajustado|he configurado|"
                      r"he programado",
              "passive": "",
              "asked": r"pusiste|cambiaste|ajustaste|configuraste|programaste|hiciste",
              "ops": ANY},
    # «Revisé», «miré» and «leí» are left out: they also tell a reading of the person's own pasted text.
    "mirar": {"said": r"busque|comprobe|verifique|consulte|he buscado|he comprobado|he verificado|he consultado",
              "passive": "",
              "asked": r"buscaste|revisaste|miraste|comprobaste|verificaste",
              "ops": ANY},
}
# Kinds whose claim with no call at all may tell what the answer itself made («te escribí un resumen», «te creé una
# lista», «agregué un ejemplo», «puse un ejemplo»): read only against calls of their kind that did not complete.
_MADE_IN_WORDS = {"escribir", "crear", "agregar", "hacer"}
_SAID = {kind: re.compile(rf"\b(?:{spec['said']})\b") for kind, spec in KINDS.items()}
_PASSIVE = {kind: re.compile(rf"\b(?:{spec['passive']})\b") for kind, spec in KINDS.items() if spec["passive"]}
_ASKED = re.compile(r"\b(?:" + "|".join(f"(?P<{k}>{s['asked']})" for k, s in KINDS.items()) + r")\b")
# TPV7 (banco, 11-11-2026, Esencial: «Ya está, te puse la cumbia» with the music tool only turned on): the first
# persons of KINDS that are strong preterites, stressed on the stem and written with no accent (RAE, Diccionario
# panhispánico de dudas, apéndice 1: poner → puse, traer → traje, -ducir → -duje).
_STRONG = frozenset({"puse", "reproduje", "traje"})


def _preterite(text: str, hit: re.Match[str]) -> bool:
    """Whether a folded verb ending in «e» was written «é» («cerré», «borré», «creé»): unaccented it is another form of
    the verb («que el pistón baje», «que lo borre», «él cree»), which claims nothing. A model that drops the accent
    loses the claim, never the other way round. A strong preterite is spelled with no accent and is no other form of
    its verb («puse», «reproduje», «traje»): it claims as written."""
    word = hit.group(0).split(" ")[0]
    if word in ("he", "te") or not word.endswith("e") or word in _STRONG:
        return True
    at = hit.start() + len(word) - 1
    return text[at] in "éÉ"


# GUA1 (VIVO13, 11-11-2026, Completo with the memory off, no call: «¡Claro! Acabo de guardar en mi memoria que tu perro
# se llama Chispo.», then «Ya tengo guardado…»; base K01: «Ahora lo tengo guardado en mi memoria»). The other forms a
# first person tells an act already done with, built from each kind's own verbs: «acabo de + infinitive» (recent past)
# and «tengo / dejé + participle» (resultative) (RAE y ASALE, Nueva gramática de la lengua española, cap. 28), and
# the English simple past and present perfect («I saved», «I've just saved»). The resultative tells a state: a
# completed read of its kind (memory.recall) backs it, as «lo tengo guardado» of what the memory showed is true.
_DONE_EN = {"abrir": "opened", "cerrar": "closed", "guardar": "saved|stored|noted down|written down",
            "crear": "created", "borrar": "deleted|removed|erased", "enviar": "sent", "agregar": "added",
            "encender": "turned (?:on|off)|enabled|disabled", "instalar": "installed|uninstalled|downloaded"}


def _done_forms(kind: str) -> tuple[re.Pattern[str], re.Pattern[str] | None]:
    """The recent-past and English claims of ``kind``, and its resultative (None if the kind has no participle)."""
    words = [w for alt in KINDS[kind]["said"].split("|") for w in [alt.split(" ")[-1]] if w.isalpha()]
    participles = [w for w in words if w.endswith(("ado", "ido"))]
    stems = {w[:-3] for w in participles} | {w[:-1] for w in words if w.endswith("i") and len(w) > 3}
    recent = [rf"acab(?:o|amos) de (?:{'|'.join(sorted(stems))})(?:ar|er|ir)(?:me|te|se|nos)?(?:lo|la|los|las|le|les)?"]
    if kind in _DONE_EN:
        recent.append(rf"i(?:'ve|’ve| have)?(?: just| already)? (?:{_DONE_EN[kind]})")
    held = (re.compile(rf"\b(?:tengo|tenemos|deje) (?:ya |bien )?(?:{'|'.join(participles)})s?\b")
            if participles else None)
    return re.compile(rf"\b(?:{'|'.join(recent)})\b"), held


# Looks («acabo de comprobar») are not acts of the PC: left to the rule of looks with no result.
_DONE = {kind: _done_forms(kind) for kind in KINDS if kind != "mirar"}


# GUA3 (REV11 C-1, 11-11-2026: «If I deleted it by mistake, you can restore it…», «Unless I closed it, Chrome should still
# be open.», «When I opened Word yesterday it was slow…»): before the verb in its clause, a negation, a condition or a
# time clause turns these forms off as _NEGATED does the Spanish preterite: they tell no act of this turn (Quirk et al.,
# A Comprehensive Grammar of the English Language, 1985, §15.17-15.25: conditional and temporal adverbial clauses;
# «cuando / cada vez que + acabo de» is the habitual present, RAE y ASALE, Nueva gramática, §23.5).
_DONE_OFF = re.compile(r"\b(?:not|never|if|unless|whether|in case|when|whenever|once|before|after|until|till|while|"
                       r"as soon as|let me|i(?:'|’)?ll|i will|i(?:'|’)?d|can|could|should|would|might|may|"
                       r"cuando|cada vez que|siempre que|en cuanto|apenas|mientras)\b")


def _en_clause(folded: str, start: int, at: int) -> int:
    """Where the clause holding position ``at`` begins, with the English joins too («…, and I've saved it»)."""
    cut = _clause_start(folded, start, at)
    for m in re.finditer(r"\b(?:and|but|so|because|then)\b", folded[cut:at]):
        cut = max(cut, cut + m.end())
    return cut


# GUA3 (REV11 C-1: «Te anoté los pasos aquí abajo: 1. Abre Word…», «I've just sent you the summary below: the meeting is
# at 5.»): the clause of the claim points after its verb at the answer itself, and the answer goes on past that: what it
# tells written or sent is the answer's own text, there for the person to read, no act of the PC. A pointer in another
# clause («Lo guardé, aquí está: …») or with nothing after it («Lo anoté aquí abajo.») still claims the act.
_HERE = re.compile(r"\b(?:aqui abajo|aqui debajo|mas abajo|abajo|debajo|a continuacion|below|as follows)\b")


def _in_the_answer(folded: str, hit: re.Match[str], end: int) -> bool:
    stop = re.search(r"[,;:]", folded[hit.end():end])
    here = _HERE.search(folded, hit.end(), hit.end() + stop.start() if stop else end)
    return here is not None and re.search(r"\w", folded[here.end():]) is not None


def _done_hits(kind: str, text: str, folded: str, start: int, end: int, receipts: list[Receipt],
               session: list[Call] | None) -> list[re.Match[str]]:
    if kind not in _DONE:
        return []
    recent, held = _DONE[kind]
    hits = [h for h in recent.finditer(folded, start, end)
            if not _DONE_OFF.search(folded, _en_clause(folded, start, h.start()), h.start())]
    if held and not any(r.get("completed") and r.get("read") and _matches(operation_of(str(r.get("op"))),
                                                                          KINDS[kind]["ops"]) for r in receipts) \
            and not any(done and read and _matches(operation_of(op), KINDS[kind]["ops"]) for op, done, read in session or []):
        hits += [h for h in held.finditer(folded, start, end) if _preterite(text, h)]  # «dejé», not «deje»
    return hits


# GUA3 (REV11 C-1): the orders of each kind of act, as the person says them: its verbs in the imperative, the
# subjunctive or the infinitive («guarda», «guárdame», «acuérdate», «que lo guardes», «puedes guardar», RAE y ASALE,
# Nueva gramática, §42.2-42.4: the imperative and its substitutes) and the English imperative («save», «note down»).
# Only what mind.UNDONE_NOTE needs to know: whether the person's turn asked for the act the answer told done.
_ORDERS = {"abrir": ("abr|reabr", "open|reopen"), "cerrar": ("cierr|cerr", "close|quit"),
           "volumen": ("sub|baj", "turn (?:it )?(?:up|down)|raise|lower"),
           "silenciar": ("silenci", "mute|unmute|silence"), "escribir": ("escrib|tecle", "write|type"),
           "guardar": ("guard|anot|apunt|recuerd|record|acuerd|acord|memoriz", "save|store|remember|note|keep"),
           "crear": ("cre|hac", "create|make"), "borrar": ("borr|elimin|vaci", "delete|remove|erase|empty"),
           "enviar": ("envi|mand", "send|mail"), "mover": ("muev|mov|copi|peg", "move|copy|paste"),
           "agregar": ("agreg|anad|anot", "add"), "ventana": ("minimiz|maximiz|restaur", "minimize|maximize|restore"),
           "reproducir": ("paus|reanud|reproduc", "play|pause|resume"),
           "lanzar": ("lanz|inici|ejecut", "launch|start|run"),
           "encender": ("activ|desactiv|enciend|encend|apag|prend", "turn (?:it )?(?:on|off)|switch|enable|disable"),
           "instalar": ("instal|desinstal|descarg", "install|uninstall|download"), "marcar": ("marc|tach", "mark"),
           "hacer": ("cambi|ajust|configur|program", "set|change|adjust|configure|schedule")}
_ORDERED = {kind: re.compile(rf"\b(?:(?:{es})(?:a|e|as|es|an|en|ar|er|ir)(?:me|te|se|nos)?(?:lo|la|los|las|le|les)?"
                             rf"|(?:{en}))\b") for kind, (es, en) in _ORDERS.items()}
# Before the order in its clause: what turns it off («no lo guardes», «if I delete it», «did you save it?»).
_UNASKED = re.compile(r"\b(?:no|nunca|jamas|tampoco|ni|sin|si|not|never|don(?:'|’)?t|dont|did|didn(?:'|’)?t|have you|"
                      r"has|had|if|unless|whether)\b")
_REFUSED = re.compile(r"^\W*(?:no|nah|nope|mejor no)\b")


def asked_for(said: str, request: str, offered: str = "") -> bool:
    """Whether the person's turn ``request`` asked for an act of the kind that ``said`` (a finding's quote) tells done:
    its words order it, or they answer BAXY's own question ``offered`` (its last line, when it ended in «?») that
    offered it, and do not begin with a «no». Form only, as the rest of this module: nothing of what the act was for."""
    folded_said = _fold(said)
    kinds = {k for k, pattern in _SAID.items() if pattern.search(folded_said)} | {
        k for k, (recent, held) in _DONE.items() if recent.search(folded_said) or (held and held.search(folded_said))}
    folded = _fold(request or "")
    question = (offered or "").rstrip()
    question = _fold(question[question.rfind("¿") + 1:]) if question.endswith("?") else ""
    for kind in kinds & _ORDERED.keys():
        for hit in _ORDERED[kind].finditer(folded):
            clause = _en_clause(folded, 0, hit.start())
            if not any(not (m.group(0) == "si" and (request or "")[m.start():m.start() + 2].lower() == "sí")
                       for m in _UNASKED.finditer(folded, clause, hit.start())):
                return True
        if question and _ORDERED[kind].search(question) and not _REFUSED.match(folded):
            return True
    return False

# Before the verb in its clause: a negation, a condition or a wish turns the claim off («no pude abrirlo», «si quieres
# lo abro», «antes de cerrar»).
_NEGATED = re.compile(r"\b(?:no|nunca|tampoco|ni|sin|jamas|aun no|todavia no|antes de|para|quieres que|puedo|voy a|"
                      r"vas a|deberia|podria|intente|trate de|si)\b")
# The sentence says itself that the act was not verified: a claim over a call that stayed unsure is told with its limit.
_UNSURE = re.compile(r"\b(?:no pude (?:comprobar|verificar|confirmar|leer|ver)|no (?:se|lo) (?:pude )?(?:comprobo|verifico|"
                     r"confirmo)|sin (?:comprobar|verificar|confirmar)|no se si|no estoy seguro|parece|al parecer|"
                     r"no (?:se )?pudo (?:comprobar|verificar|confirmar|leer))\b")
_YES = re.compile(r"^\W*(?:s[íi]|claro|yes|yep)\b(?!\s+(?:quieres|puedo|deseas))", re.IGNORECASE)

# A state of the PC said of something (an application, a window, the sound, a connection): only read against a session
# with no call at all.
_STATE = re.compile(r"\b(?:sigue|siguen|esta|estan|quedo|quedaron|estaba|estaban) (?:todavia |aun |ya )?"
                    r"(?:abiert|cerrad|minimizad|maximizad|silenciad|encendid|apagad|conectad|desconectad|instalad|"
                    r"desinstalad|sonando|reproduciendo|en pausa|pausad|al frente|corriendo|en ejecucion)")

# ---- partial reads ----------------------------------------------------------------------------------------------------
_ABSENT = re.compile(r"\bno (?:(?:lo|la|los|las|le|les|se) )?(?:esta|estan|estaba|estaban|hay|habia|existe|existen|"
                     r"aparece|aparecen|aparecia|figura|figuran|contiene|contienen|tiene|tienes|tienen|tenia|tenias|sale|salen|"
                     r"quedan?|queda)\b|\bningun[oa]?s?\b|\bnada\b")
_TOTAL = re.compile(r"\b(?:revise|lei|mire|busque|recorri|he revisado|he leido|he buscado|he mirado) "
                    r"(?:(?:todo|todos|todas|completo|entero|entera|enteros)\b|(?:el|la|los|las) \w+ (?:complet|enter))"
                    r"|\btodo el (?:archivo|documento|texto|registro|log|pc|equipo|disco|sistema|contenido)\b"
                    r"|\b(?:archivo|documento|pagina|texto|registro|lista|carpeta)s? (?:complet[oa]s?|enter[oa]s?)\b"
                    r"|\ben (?:ningun|ninguna|ningunos) (?:otr[oa]s? )?(?:lugar|lado|sitio|parte|carpeta|ubicacion)"
                    r"|\b(?:ningun|ninguna) otr[oa]\b|\ben ninguna (?:otra )?(?:parte|carpeta|ubicacion)"
                    r"|\ben todo el (?:pc|equipo|disco|sistema)\b|\ben (?:todas|ninguna de) (?:las|tus) carpetas\b")
_ELSEWHERE = re.compile(r"\b(?:ningun|ninguna) otr[oa]|\ben (?:ningun|ninguna) (?:lugar|lado|sitio|parte|carpeta)"
                        r"|\ben todo el (?:pc|equipo|disco|sistema)\b|\bel resto\b")
_HEDGED = re.compile(r"\b(?:en lo que|de lo que|lo que (?:lei|revise|vi|mire|alcance)|hasta donde|hasta (?:la|el|las|"
                     r"los) |en (?:la|esa|esta) parte|en parte|la parte|primer[oa]s?|parcial|solo (?:revise|mire|lei|"
                     r"busque|en|hasta|las?|los?|el|la|una|un|lo|directamente)|no (?:revise|lei|busque|mire|abri|"
                     r"llegue|termine|recorri|lo busque)|sin (?:abrir|revisar|leer|mirar|contar|buscar|llegar)|al menos|"
                     r"directamente|cortad[oa]|se corto|limite|tope|por ahora|que (?:revise|lei|mire|busque|vi)|"
                     r"subcarpetas|ocult[oa]s|mas de|resto sin)\b")

# ---- numbers ----------------------------------------------------------------------------------------------------------
_NUM = r"(\d+(?:[.,]\d+)?)(?![.,]?\d)"
_PERCENT = re.compile(r"(?<![\d.,])" + _NUM + r"\s*(?:%|por ciento)")
# A level said of the volume, the brightness or the battery: every number after the word, each after its preposition
# («subí el volumen en 10 y quedó en 40»), but not a count of something else («3 veces», «10 minutos»).
_LEVEL_WORD = re.compile(r"\b(?:volumen|brillo|bateria|carga)\b")
_LEVEL = re.compile(r"\b(?:en|a|al|de|es|esta|queda|quedo|hasta)\s+(?:el |un )?(?<![\d.,])" + _NUM
                    + r"(?!\s*(?:veces|segundos|minutos|horas|dias|pasos|puntos|niveles|cancion|juego|archivo))")
_SIZE = re.compile(_NUM + r"\s*(bytes?|b|kb|kib|mb|mib|gb|gib|tb)\b")
_SIZE_POWER = {"b": 0, "byte": 0, "bytes": 0, "kb": 1, "kib": 1, "mb": 2, "mib": 2, "gb": 3, "gib": 3, "tb": 4}
_LEVEL_OPS = ("audio.", "system.settings.", "display.", "media.", "system.status", "power.", "battery.")

# ---- folders ----------------------------------------------------------------------------------------------------------
# A folder named in the answer, folded, and how a result's path shows it (lower case, «\» separators).
_FOLDERS = (
    ("baxy-bench", re.compile(r"\bbaxy[- ]?bench\b"), ("\\baxy-bench",)),
    ("escritorio", re.compile(r"\b(?:escritorio|desktop)\b"), ("\\desktop", "\\escritorio")),
    ("descargas", re.compile(r"\b(?:descargas|downloads)\b"), ("\\downloads", "\\descargas")),
    ("documentos", re.compile(r"\b(?:documentos|documents|mis documentos)\b"), ("\\documents", "\\documentos")),
    ("imagenes", re.compile(r"\b(?:imagenes|pictures)\b"), ("\\pictures", "\\imagenes")),
    ("musica", re.compile(r"\b(?:musica|music)\b"), ("\\music", "\\musica")),
    ("videos", re.compile(r"\b(?:videos)\b"), ("\\videos",)),
)
_HOME = re.compile(r"\b(?:tu|mi) carpeta (?:de usuario|personal|de inicio|home)\b|\bcarpeta (?:de )?(?:tu )?usuario\b"
                   r"|\bcarpeta home\b|\bcarpeta de inicio\b|\bcarpeta personal\b")
_WORK = re.compile(r"\b(?:mi|la) carpeta de trabajo\b|\bcarpeta de baxy\b|\bmi carpeta\b")
_SANDBOX = ("\\appdata\\local\\baxy", "filesystem-sandbox")
# Holdout v6 V6E058 (s1): also a claim that opens with the participle («Creada la carpeta fotos_2026 dentro de BAXY-bench»);
# only opening the sentence (after «listo», «ya»): «estaba guardado en Descargas» says where it was (revisión de
# nb-w11-multi).
_PLACED = re.compile(r"\b(?:guarde|cree|escribi|agregue|anadi|movi|copie|deje|puse|anote|sobrescribi|he guardado|"
                     r"he creado|he escrito|he agregado|he anadido|he movido|he copiado|he dejado|he sobrescrito|"
                     r"se guardo|se creo|quedo|quedaron|esta guardad[oa]|esta en|estan en)\b"
                     r"|^\W*(?:(?:listo|hecho|ok|perfecto)\W+)?(?:ya )?"
                     r"(?:guardad[oa]s?|cread[oa]s?|escrit[oa]s?|movid[oa]s?|copiad[oa]s?)\b")
_PLACE_OPS = ("file.write", "file.edit", "file.compress", "filesystem.", "office.document.create",
              "document.presentation.create", "capture.", "web.download", "backup.")
# An absolute Windows path said in prose. Its parts may hold spaces and parentheses («C:\Program Files (x86)\…»,
# «…\OneDrive - Universidad\…», «C:\Archivos de programa\…»): Windows allows both in a name, and quoting is how a path
# with spaces is written whole (Microsoft Learn, «Naming Files, Paths, and Namespaces» and the reference of cmd: a path
# with spaces goes «in quotation marks»). F16 (cosecha 03-11 22:40): read up to the first space,
# «C:\Program Files\Notepad++» was «C:\Program». So a path in quotes is read whole, and one in prose goes on past a space
# while a word within the next three has a backslash (another part follows: «Files\Notepad++», «de programa\Editor»;
# «y/o» or «3/11» are not one) or the next word ends a file name («informe final.docx»). A last part with spaces and no
# extension («…\Mis documentos.») is not told from prose by its form: _folders reads it against the results' paths.
_PATH_CHAR = r"(?:[^\s«»\"'”“,;()<>*`|?]|\([^\s«»\"'”“,;()<>*`|?]*\))"  # a balanced «(x86)» belongs to the name
_PATH_WORD = rf"(?![A-Za-z]:[\\/]){_PATH_CHAR}+"  # a word of a path part: never the start of another path
_PATH = re.compile(rf"(?<=[«\"“`])[A-Za-z]:[\\/][^«»\"“”`\n<>|?*]*?(?=[»\"”`])"
                   rf"|\b[A-Za-z]:[\\/]{_PATH_CHAR}*"
                   rf"(?: (?:{_PATH_WORD} ){{0,2}}(?![A-Za-z]:[\\/]){_PATH_CHAR}*\\{_PATH_CHAR}*"
                   rf"| {_PATH_CHAR}+\.(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{{1,5}}(?![\w-]))*")
# A folder named as where it did not go («no en BAXY-bench», «en vez de Descargas»).
_NOT_THERE = re.compile(r"\b(?:no|ni|en vez de|en lugar de|fuera de|sino|no dentro de)(?: (?:en|a|de|dentro de))?"
                        r"(?: (?:la|tu|mi) carpeta(?: de)?)? ?$")

# Encargo 82 (vivo del 81): what a file dialog saved is said in its own receipt. After a place verb, the place said first
# («en la carpeta X», «en X», «en Documentos\X\y.txt»); in the person's words, the name after «carpeta».
_SAID_AT = re.compile(r"\ben (?:(?:la|tu|mi|su) )?(?:carpeta )?([^\s,;()«»\"]+)")
_ASKED_AT = re.compile(r"\bcarpeta (?!(?:de|del|que|donde|en|a|y|la|el|mi|mis|tu|tus|su|sus)\b)([^\s,;:()«»\"]+)")

# ---- already ----------------------------------------------------------------------------------------------------------
_ALREADY = re.compile(r"\bya (?:(?:lo|la|los|las|se) )?(?:estaba|estaban|tenia|tenias|habia|habias|sonaba|era)\b"
                      r"|\bno hizo falta\b|\bno (?:hubo|habia) que\b")
_ALREADY_SEEN = re.compile(r"unchanged|already|\"same\":true|\"changed\":false|nochange|no_change|wasAlready|"
                           r"ya estaba", re.IGNORECASE)

# ---- saved names ------------------------------------------------------------------------------------------------------
# A file said saved, created or written with its name (folded), and the name in its clause: a bare name or a path's last
# part, with an extension that has a letter (not «2.5»).
_SAVED = re.compile(r"\b(?:guarde|he guardado|cree|he creado|escribi|he escrito|se guardo|se creo|quedo guardad[oa]|"
                    r"quedo cread[oa]|esta guardad[oa])\b")
_FILE_NAME = re.compile(r"(?<![\w.-])(?:[^\s«»\"'“”,;()<>*?|]*[\\/])?"
                        r"(?P<name>[^\s«»\"'“”,;:()<>*?|\\/]+\.(?=[a-z0-9]*[a-z])[a-z0-9]{1,5})(?![\w-])")
# Where the clause of a claim ends: a «:» of a path («C:\…») does not end it.
_CLAUSE_END = re.compile(r"[,;]|:(?![\\/])|\b(?:pero|aunque|y|o|porque|asi que|mientras|luego|despues|entonces)\b")
# A window's title in a result: «Ventana «…»» and «TitleBar «…»» of a view, or a field named title; the file it names
# is its first part («*lista.txt: Bloc de notas», «x.png - Paint»), never an address («…@gmail.com - Gmail»).
_TITLED = re.compile(r"\b(?:Ventana|TitleBar|Window) «([^»\n]+)»")
_TITLE_NAME = re.compile(r"^[\s*●•]*(?P<name>[^\\/:*?\"<>|@\n]+?\.(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{1,5})"
                         r"(?: - | — | – |: )\S")
_NAME_FIELDS = ("name", "fileName", "fullPath", "destinationFullPath", "path")


def _fold(text: str) -> str:
    """Lower case without accents, one character for each: positions in it are positions in ``text``."""
    return "".join(unicodedata.normalize("NFD", c)[0].lower() if c.strip() else " " for c in text)


def _blank_quotes(text: str) -> str:
    """Quoted spans («…», "…", “…”, '…' of two words or more) as spaces: what was typed, played or titled is not a claim."""
    def blank(m: re.Match[str]) -> str:
        return m.group(0)[0] + " " * (len(m.group(0)) - 2) + m.group(0)[-1]
    text = re.sub(r"«[^»]*»|\"[^\"]*\"|“[^”]*”", blank, text)
    return re.sub(r"(?<!\w)'[^']*\s[^']*'(?!\w)", blank, text)


def _statements(text: str) -> list[tuple[int, int]]:
    """The spans of the answer that state something: each sentence up to its first «¿» (what follows is a question),
    and none of a sentence ending in «?»."""
    spans = []
    # A stop inside a word (notas.txt, 2.5) does not end the sentence.
    for m in re.finditer(r"(?:[^.!?\n]|[.!?](?=[^\s.!?]))+[.!?]*", text):
        start, end = m.start(), m.end()
        chunk = text[start:end]
        if "¿" in chunk:
            end = start + chunk.index("¿")
        elif chunk.rstrip().endswith("?"):
            continue
        if text[start:end].strip():
            spans.append((start, end))
    return spans


def _clause_start(folded: str, start: int, at: int) -> int:
    """Where the clause holding position ``at`` begins, within its statement starting at ``start``."""
    cut = start
    for m in re.finditer(r"[,;:]|\b(?:pero|aunque|y|o|porque|asi que|mientras|luego|despues|entonces)\b",
                         folded[start:at]):
        cut = start + m.end()
    return cut


def _negated(folded: str, start: int, at: int, text: str = "") -> bool:
    """Whether the clause before position ``at`` turns its claim off. «si» counts only as the conditional: not «sí»."""
    clause = _clause_start(folded, start, at)
    return any(not (m.group(0) == "si" and text[m.start():m.start() + 2].lower() == "sí")
               for m in _NEGATED.finditer(folded, clause, at))


def _quote(text: str, start: int, end: int) -> str:
    """The model's own words around a finding: its clause, at most 15 words."""
    words = text[start:end].strip().split()
    return " ".join(words[:15]) + ("…" if len(words) > 15 else "")


def _matches(op: str, ops: tuple[str, ...]) -> bool:
    return ops == ANY or any(op == p or (p.endswith((".", "_")) and op.startswith(p)) or op.startswith(p + ".")
                             for p in ops)


def _opened_page(receipt: Receipt) -> bool:
    """Whether a result names the page its call opened (its observed ``openedUrl``)."""
    observed = _parsed(receipt).get("observed")
    return isinstance(observed, dict) and isinstance(observed.get("openedUrl"), str) and bool(observed["openedUrl"])


# A result's code as the App writes it (page_requires_sign_in, external_effect_ambiguous): lower case words joined by
# «_»; one inside the parentheses of an outcome («sin confirmar (page_requires_sign_in)»).
_CODE = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+")
_CODE_TOLD = re.compile(r"\(([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\)")


def _internal(answer: str, statements: list[tuple[int, int]], receipts: list[Receipt]) -> list[dict]:
    """Rule ``internal`` (uso-90, diag-9dea c3-g10 and diag-6f20 c4-g10): the answer carries a tool's name as the model
    calls it (``media_play_youtube``) or a code of a result of the turn (``page_requires_sign_in``), words of BAXY's
    results and notes and never of the person; the voice said «media_play_youtube → sin confirmar
    (page_requires_sign_in): pudo o no ocurrir». Only the turn's own names and codes, letter for letter as whole words:
    a file the person named with a «_» (borrador_viejo.txt) is none of them."""
    names: set[str] = set()
    for receipt in receipts:
        tool = str(receipt.get("tool") or "")
        if _CODE.fullmatch(tool):
            names.add(tool)
        facts = _parsed(receipt)
        names.update(code for code in (facts.get("error"), facts.get("cause"))
                     if isinstance(code, str) and _CODE.fullmatch(code))
        names.update(_CODE_TOLD.findall(str(receipt.get("outcome") or "")))
    hits = sorted(((hit.start(), name) for name in names
                   for hit in [re.search(rf"(?<![\w.]){re.escape(name)}(?![\w.])", answer)] if hit),
                  key=lambda found: found[0])
    if not hits:
        return []
    at = hits[0][0]
    start, end = next(((s, e) for s, e in statements if s <= at < e), (0, len(answer)))
    told = list(dict.fromkeys(name for _, name in hits))
    return [{"rule": "internal", "said": _quote(answer, start, end),
             "fact": " y ".join(f"«{name}»" for name in told) + (" son nombres" if len(told) > 1 else " es un nombre")
             + " de los resultados de BAXY, no palabras para la persona"}]


def _parsed(receipt: Receipt) -> dict[str, Any]:
    try:
        facts = json.loads(receipt.get("observation") or "")
    except (json.JSONDecodeError, TypeError):
        return {}
    return facts if isinstance(facts, dict) else {}


def _walk(value: Any, key: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _walk(v, str(k))
    elif isinstance(value, list):
        for v in value:
            yield from _walk(v, key)
    else:
        yield key, value


def _control_names(receipt: Receipt) -> set[str]:
    """The names of what a look at a window listed, folded."""
    return {_fold(value).strip() for key, value in _walk(_parsed(receipt)) if key == "name" and isinstance(value, str)}


def _sizes_with_their_unit(value: Any) -> Iterable[tuple[float, int]]:
    """A size whose unit is the field beside it, as (number, unit's power): {"value": 4.78, "unit": "GB"} (assistant_status).
    Cosecha 05-11: «4,78 GB» was told that number is not in the results, with that value in the fact."""
    if isinstance(value, dict):
        number, unit = value.get("value"), value.get("unit")
        if (isinstance(number, (int, float)) and not isinstance(number, bool) and isinstance(unit, str)
                and unit.lower() in _SIZE_POWER and math.isfinite(number)):
            yield float(number), _SIZE_POWER[unit.lower()]
        for inner in value.values():
            yield from _sizes_with_their_unit(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _sizes_with_their_unit(inner)


def _only_reused(receipts: list[Receipt]) -> list[Receipt]:
    """The turn's completed acts of opening, when every one is an app_open that found the application already running."""
    acts = [r for r in receipts if r.get("completed") and not r.get("read")
            and _matches(r.get("op", ""), KINDS["abrir"]["ops"])]
    return acts if all(r.get("op") == "app.open" and any(k == "alreadyRunning" and v is True for k, v in _walk(_parsed(r)))
                       for r in acts) else []


def _told(receipt: Receipt) -> str:
    return f"{receipt.get('tool') or receipt.get('op')} → {receipt.get('outcome') or 'sin resultado'}"


# RUT10 (RUT8's bench, «pausa o reproduce» said directly, 3 of 12 with no media_control in the turn: «Pauso lo que está
# sonando y le doy play para que continúe», «…y le doy play para que siga reproduciéndose» after only reading what
# sounds): the first person of the present, told as the act of this turn, is a claim of its kind as the preterite is
# (RAE, Diccionario panhispánico de dudas, apéndice 1: pausar → pauso, reanudar → reanudo, reproducir → reproduzco; dar
# → doy, poner → pongo). Read as the preterite is, and more narrowly: not in a question («¿lo pauso?») nor after a
# negation, a condition or a wish anywhere before it in its sentence («si quieres, lo pauso»); only against the calls of
# its kind.
_PRESENT = {"reproducir": re.compile(r"\b(?:pauso|reanudo|reproduzco|(?:doy|pongo) (?:play|pausa))\b")}


# ---- the check --------------------------------------------------------------------------------------------------------
def check(answer: str, request: str, receipts: list[Receipt], session: list[Call] | None,
          catalog: dict[str, str] | None = None, tries: list[tuple[str, str]] | None = None,
          wire_of: Callable[[str], str] = plain, earlier: list[Receipt] | None = None,
          today: dt.date | None = None, unsourced: list[dict[str, Any]] | None = None,
          memory: str | None = None, memory_off: bool = False) -> list[dict]:
    """The findings of an answer against its turn: ``receipts`` are the turn's calls in order, ``session`` every call
    of the session before and in this turn as (operation, completed, read), or None when the session is not known whole (a
    kept session, or one past the calls the mind keeps): then nothing is said of calls that may have been there.
    ``catalog`` (each operation and its description) and ``tries`` (the conversation's earlier calls as (operation,
    status)) are for the rule ``denial``, which is not read without the catalog; ``wire_of`` gives an operation the tool name
    shown to the model (wire.Wires.name). ``earlier``: the calls the conversation still shows, this turn's too, in order,
    as receipts (``observation`` None when its body was left out), for the rule ``stale_state``. ``today``: the clock's
    date, for the rule ``future_past``, which is not read without it. ``unsourced``: the calculations of the turn whose
    expression had numbers nobody gave ({"numbers": ["900"], "value": "55.55"}), for the rule ``unsourced_number``.
    ``memory``: the tool name that reads BAXY's memory, or "" when the catalog has none, for the rule ``unread_memory``,
    which is not read without it. ``memory_off``: the App said BAXY's memory is switched off (catalog.configure
    «memoryOff»), or a memory call of the conversation failed off, for the rule ``memory_off_empty``. Each finding: {"rule", "said" (the model's words), "fact" (what contradicts them)}."""
    if not answer or not answer.strip():
        return []
    text = _blank_quotes(answer)
    folded = _fold(text)
    raw_folded = _fold(answer)
    statements = _statements(text)
    findings: list[dict] = []
    done_kinds = {kind for kind in KINDS if _done(kind, receipts, session)}

    def add(rule: str, start: int, end: int, fact: str) -> None:
        said = _quote(answer, start, end)
        if not any(f["rule"] == rule and f["fact"] == fact for f in findings):
            findings.append({"rule": rule, "said": said, "fact": fact})

    # Claims of an act.
    for start, end in statements:
        for kind, pattern in _SAID.items():
            hits = [h for h in pattern.finditer(folded, start, end) if _preterite(text, h)]
            if kind in _PRESENT and "?" not in text[start:end]:
                # a condition or a wish anywhere before it in the sentence turns it off («si quieres, lo pauso»)
                hits += [h for h in _PRESENT[kind].finditer(folded, start, end) if not any(
                    not (m.group(0) == "si" and text[m.start():m.start() + 2].lower() == "sí")
                    for m in _NEGATED.finditer(folded, start, h.start()))]
            hits += _done_hits(kind, text, folded, start, end, receipts, session)
            passive = _PASSIVE.get(kind)
            passives = list(passive.finditer(folded, start, end)) if passive else []
            for hit, is_passive in [*((h, False) for h in hits), *((h, True) for h in passives)]:
                if _negated(folded, start, hit.start(), text) or kind in done_kinds or _in_the_answer(folded, hit, end):
                    continue
                fact = _act_fact(kind, receipts, session, passive=is_passive,
                                 unsure_said=_UNSURE.search(folded, start, end) is not None)
                if fact:
                    add(fact[0], _clause_start(folded, start, hit.start()), end, fact[1])
                    break

    # «Abrí Steam» of an application that was already open (F20).
    reused = _only_reused(receipts)
    if reused:
        for start, end in statements:
            hit = next((h for h in _SAID["abrir"].finditer(folded, start, end)
                        if _preterite(text, h) and not _negated(folded, start, h.start(), text)), None)
            if hit:
                add("already_open", _clause_start(folded, start, hit.start()), end,
                    f"{_told(reused[0])}: alreadyRunning es true: ya estaba abierta y esa llamada no la abrió")
                break

    # «Sí» to «¿abriste…?».
    asked = _ASKED.search(_fold(request or "")) if "?" in (request or "") or "¿" in (request or "") else None
    if asked and _YES.match(answer):
        kind = next(k for k, v in asked.groupdict().items() if v)
        negates = any(_negated(folded, s, h.start(), text) for s, e in statements for h in _SAID[kind].finditer(folded, s, e))
        if kind not in done_kinds and not negates and session is not None:
            first = statements[0] if statements else (0, len(answer))
            ran = [r for r in receipts if r.get("completed")]
            add("implied_yes", first[0], first[1],
                f"la persona pregunta si lo hiciste ({asked.group(0)}) y en esta sesión ninguna llamada completada lo "
                "hizo" + (f"; en este turno sólo: {'; '.join(_told(r) for r in ran[:3])}" if ran else ""))

    # A state of the PC told in a session where nothing was ever called or read («sigue abierto», «no está abierto»),
    # when the person asked about one («¿ya cerraste…?», «si Chrome está abierto…»): not a lesson on engines.
    folded_request = _fold(request or "")
    if session == [] and not receipts and (_ASKED.search(folded_request) or _STATE.search(folded_request)
                                           or re.search(r"\b(?:abiert|cerrad)", folded_request)):
        for start, end in statements:
            hit = _STATE.search(folded, start, end)
            if hit and not _UNSURE.search(folded, start, end) and not any(
                    m.group(0) == "si" and text[m.start():m.start() + 2].lower() != "sí"
                    for m in re.finditer(r"\bsi\b", folded[:hit.start()])):
                add("unread_state", start, end, "en esta sesión no se llamó a ninguna herramienta: nada miró eso")
                break

    # ACT1 (VER2 V08): «Yes, I'm up to date. I checked…» with no look for a newer version in the conversation.
    unchecked = _unchecked_update(folded, statements, receipts, session, text, request)
    if unchecked:
        add("unchecked_update", *unchecked, UNCHECKED_UPDATE.format(tool=wire_of(UPDATE_OP)))

    # «Ya está instalado» with nothing read in the turn while the last result of that thing shows another state.
    findings.extend(f for f in _stale_states(answer, folded, statements, receipts, earlier, text) if f not in findings)
    # Encargo 75 (R01): the turn's last text is still pending over a cell: nothing ended it, whatever the answer says of it.
    pending = _pending_cell(receipts)
    if pending and statements:
        add("pending_cell", statements[0][0], statements[-1][1],
            f"«{pending[1]}» sigue pendiente en la celda {pending[0]}: ninguna tecla la terminó, así que aún no está en ella")

    # «En la biblioteca» after an app_open that only asked for its place (F019).
    for receipt, words in _places_asked(receipts):
        for start, end in statements:
            hit = re.search(rf"\b(?:en|a) (?:la |el |los |las |su |tu )?(?:seccion (?:de )?)?(?:{words})\b",
                            folded[start:end])
            if hit and not _negated(folded, start, start + hit.start(), text):
                add("place", start, end, f"{_told(receipt)}: pidió ese lugar, pero nada comprobó que se viera")
                break

    # «Windows la guarda para el próximo reinicio» of a display mode the result says was only shown (uso real 04-11).
    for receipt, saved_figures in _modes_not_saved(receipts):
        for start, end in statements:
            hit = _MODE_KEPT.search(folded, start, end)
            # «Windows lo tiene guardado en 1920x1080» says the mode that is saved: true, and no claim of this one.
            if hit and not _negated(folded, start, hit.start(), text) and not any(
                    re.search(rf"(?<!\d){figure}(?!\d)", folded[start:end]) for figure in saved_figures):
                add("mode_not_saved", start, end, f"{_told(receipt)}: savedForRestart es false: ese modo sólo se muestra "
                                                  "ahora y no quedó guardado; un reinicio vuelve al modo guardado")
                break

    # «No hay un botón «Biblioteca»» while the window's reading shows that name (F019 on int10e: its text said «TIENDA
    # BIBLIOTECA» and that a line of it is pressed by its text). Read on the answer with its quotes, where the name is.
    views = [r for r in receipts if r.get("completed") and _matches(r.get("op", ""), ("input.visible.controls",))]
    if views:
        for start, end in statements:
            for hit in _NO_CONTROL.finditer(raw_folded, start, end):
                name = (hit.group("quoted") or hit.group("bare") or "").strip()
                # Cosecha 05-11: «no hay un botón con ese nombre» was read as a button called «con», a word every page's
                # text has. A word with no quotes is a name when it is written as one, or begins a control's name.
                candidates = views if hit.group("quoted") or answer[hit.start("bare")].isupper() else [
                    r for r in views if any(c == name or c.startswith(name + " ") for c in _control_names(r))]
                shown = next((r for r in candidates if len(name) >= 3
                              and re.search(rf"(?<!\w){re.escape(name)}(?!\w)", _fold(r.get("observation") or ""))), None)
                if shown:
                    add("named_control", start, end, f"{_told(shown)}: su lectura muestra «{name}» (se pulsa por su texto)")
                    break

    # «No está», «revisé todo» after a partial read.
    partial = [(r, why) for r in receipts for why in [_partial(r)] if why]
    if partial:
        for start, end in statements:
            sentence = folded[start:end]
            total = _TOTAL.search(sentence)
            absent = _ABSENT.search(sentence)
            if not (total or absent) or _HEDGED.search(sentence):
                continue
            for receipt, why in partial:
                if why == "searchedElsewhere" and not _ELSEWHERE.search(sentence):
                    continue
                if why != "searchedElsewhere" and not total and not _absence_about(sentence, absent):
                    continue
                told = (_told(receipt) if why == "notChecked" and _PARTIAL_TOLD[why] in _told(receipt)
                        else f"{_told(receipt)}: {_PARTIAL_TOLD[why]}" if why in ("failedRead", "notChecked")
                        else f"{receipt.get('tool')} leyó sólo una parte: " + _PARTIAL_TOLD[why].format(
                            covers=str((_parsed(receipt).get("observed") or {}).get("covers", "")).strip()))
                add("partial", start, end, told)
                break

    # Numbers.
    findings.extend(f for f in _numbers(answer, folded, statements, receipts) if f not in findings)

    # Folders and paths.
    findings.extend(f for f in _folders(answer, folded, raw_folded, statements, receipts, request) if f not in findings)

    # A file's name said saved that the turn shows otherwise (E017).
    findings.extend(f for f in _saved_names(answer, text, folded, statements, receipts) if f not in findings)

    # «No encontré X» while a result of the turn found X (V6E055).
    findings.extend(f for f in _not_found_names(answer, folded, raw_folded, statements, receipts) if f not in findings)

    # «No leí X» while a result of the turn read X whole (holdout v6, falsedades).
    findings.extend(f for f in _not_read_names(answer, folded, raw_folded, statements, receipts) if f not in findings)

    # «No puedo borrar carpetas de X» with no call in the turn while a tool of the catalog does it (aid check_denial).
    findings.extend(f for f in _denials(answer, folded, statements, receipts, catalog, tries, wire_of) if f not in findings)

    # «Salió «Hola mundo»» while no result of the turn shows that text.
    findings.extend(f for f in _outputs(answer, raw_folded, statements, receipts) if f not in findings)

    # «829» told from a look whose only source of it is the OCR of the window beside its controls (uso-89, R06).
    findings.extend(f for f in _recognized_numbers(answer, text, folded, statements, receipts, request)
                    if f not in findings)

    # «Google me dio…» while the search that answered was another engine's (R7-NB-3).
    findings.extend(f for f in _engines_unanswered(answer, folded, statements, receipts) if f not in findings)

    # «Abrí Gmail en Chrome» while the page's result says it opened in another browser (encargo 70, F6).
    findings.extend(f for f in _browser_contradicted(answer, folded, statements, receipts) if f not in findings)
    # A page asked to open that failed, a search after it, and nothing opened since (encargo A10, U31).
    findings.extend(f for f in _unopened_page(answer, receipts, wire_of, request) if f not in findings)
    # «Se estrenó el 20 de diciembre de 2026» on 3 November 2026 (uso real 2026-11-03, F8).
    findings.extend(f for f in _future_past(answer, text, folded, statements, receipts, today) if f not in findings)
    # «La próxima reunión es el 27-28 de octubre de 2026» on 9 November 2026 (VER1, G-03).
    findings.extend(f for f in _past_future(answer, text, folded, statements, receipts, today) if f not in findings)
    # «En siete días es el viernes 12» when the 12th is a Thursday (VER1, PR-03).
    findings.extend(f for f in _weekday_date(answer, folded, statements, receipts, request, today) if f not in findings)

    # «No tengo nada guardado de X» with nothing else looked at (F13, F35).
    findings.extend(f for f in _empty_lookup(answer, receipts, wire_of) if f not in findings)
    # «Recuerdo que tu color favorito es el azul» with no memory call in the conversation (MEM1, VIVO12 P1).
    findings.extend(f for f in _unread_memory(folded, text, statements, receipts, session, memory, request) if f not in findings)
    # «No tengo nada guardado de ti» with the memory switched off and nothing read (MEM4, REM7 D-1).
    if memory_off:
        findings.extend(f for f in _memory_off_empty(folded, text, statements, receipts, session, request)
                        if f not in findings)

    # A datum the answer bends against what a result says it brought (encargo A5; answer_grounding.py).
    findings.extend(f for f in _unmatched(answer, statements, receipts) if f not in findings)
    # A calculation's number nobody gave, told in the answer (encargo A2, HP3).
    findings.extend(f for f in _unsourced_told(answer, folded, statements, unsourced) if f not in findings)

    # A tool's name or a result's code in the answer: BAXY's own words, never the person's (uso-90, diag-9dea U06).
    findings.extend(f for f in _internal(answer, statements, receipts) if f not in findings)

    # «Ya estaba». Feria 2026-10-27: a call repeated after it changed something comes back «unchanged» because of that
    # first call; only the first call of an operation with its arguments that ran in the turn tells what was so before.
    changed = [r for r in receipts if r.get("completed") and _parsed(r).get("verification") == "readback"]
    firsts = {(r.get("op"), json.dumps({k: v for k, v in (r.get("arguments") or {}).items() if v is not None},
                                       sort_keys=True, ensure_ascii=False)): r
              for r in reversed(receipts) if _parsed(r).get("status") != "not_run"}.values()
    if changed and not any(_ALREADY_SEEN.search(r.get("observation") or "") or "ya estaba" in (r.get("outcome") or "")
                           for r in firsts):
        for start, end in statements:
            hit = _ALREADY.search(folded, start, end)
            if hit and not re.search(r"\bno\b", folded[_clause_start(folded, start, hit.start()):hit.start()]):
                add("already", _clause_start(folded, start, hit.start()), end,
                    f"{_told(changed[-1])}: cambió algo y nada dice que ya estuviera así")
                break

    # Which way a play/pause went (RUT8): told the other way round against the two states its result read.
    way = _way_went(receipts)
    if way is not None:
        receipt, before, after, claim, fact = way
        for start, end in statements:
            hit = next((h for h in claim.finditer(folded, start, end)
                        if _accented(text, h) and not _negated(folded, start, h.start(), text)), None)
            if hit:
                add("which_way", _clause_start(folded, start, hit.start()), end,
                    f"{_told(receipt)}: previousPlaybackStatus «{before}» y playbackStatus «{after}»: {fact}")
                break
    return findings


# ---- which_way ----------------------------------------------------------------------------------------------------------
# What tells a pause that did not happen (after a control that resumed) and a resume that did not happen (after one that
# paused): the act in the past, or the state of now or of before said the other way round. «que estaba pausado» after a
# resume and «que estaba sonando» after a pause are true and are not here.
_PAUSE_TOLD = re.compile(
    r"\b(?:pause|pauso|pausaste|(?:he|has|ha) pausado|(?:puse|pusiste|puso|he puesto|has puesto) en pausa|"
    r"se (?:ha )?paus(?:o|ado)|ahora esta (?:pausad[oa]|en pausa)|quedo (?:pausad[oa]|en pausa)|"
    r"(?:ya )?estaba (?:sonando|reproduciendo(?:se)?)|i(?:'ve| have)? paused|is now paused)\b")
_RESUME_TOLD = re.compile(
    r"\b(?:reproduje|reanude|reanudo|reanudaste|(?:he|has|ha) (?:reanudado|reproducido)|se (?:ha )?reanud(?:o|ado)|"
    r"le di play|(?:puse|he puesto) en (?:reproduccion|play|marcha)|"
    r"ahora (?:suena|esta sonando|se esta reproduciendo|esta reproduciendo(?:se)?|se reproduce|sigue sonando)|"
    r"ya esta (?:sonando|reproduciendo(?:se)?)|estaba (?:pausad[oa]|en pausa)|"
    r"i(?:'ve| have)? resumed|now playing|is playing again)\b")


def _accented(text: str, hit: re.Match[str]) -> bool:
    """Whether a folded «pause», «pauso», «reanude» or «reanudo» was written with its accent («pausé», «pausó»): without
    it, it is an order or a present («pausa o reproduce», «pauso lo que suena»), which tells nothing done."""
    word = hit.group(0).split(" ")[0]
    if word not in ("pause", "pauso", "reanude", "reanudo"):
        return True
    return text[hit.start() + len(word) - 1] in "éÉóÓ"


def _way_went(receipts: list[Receipt]) -> tuple[Receipt, str, str, re.Pattern[str], str] | None:
    """The turn's media_control that changed the state, with the two states its result read and what an answer would say
    to tell it the other way round; None when no result of the turn says both states, or when the turn went both ways."""
    went: list[tuple[Receipt, str, str]] = []
    for receipt in receipts:
        observed = _parsed(receipt).get("observed") if receipt.get("completed") and receipt.get("op") == "media.control" else None
        if isinstance(observed, dict):
            before, after = observed.get("previousPlaybackStatus"), observed.get("playbackStatus")
            if isinstance(before, str) and isinstance(after, str) and before != after:
                went.append((receipt, before.lower(), after.lower()))
    if not went or len({after == "playing" for _receipt, _before, after in went}) != 1:
        return None
    receipt, before, after = went[-1]
    if after == "playing" and before in ("paused", "stopped"):
        return receipt, before, after, _PAUSE_TOLD, "estaba en pausa y ahora suena; en este turno nada se pausó"
    if before == "playing" and after in ("paused", "stopped"):
        return receipt, before, after, _RESUME_TOLD, "estaba sonando y ahora está en pausa; en este turno nada se reanudó"
    return None


def _does(kind: str, op: str, read: bool) -> bool:
    """Whether an operation can be what did an act of this kind: a read never did one, but for «busqué», «revisé»; a
    confirmation's own call (its operation not known here) can be any."""
    op = operation_of(op)  # a plain wire name (app_open) is its operation's (app.open): the catalog's ids have no «_»
    return op == "confirmation.answer" or ((not read or kind == "mirar") and _matches(op, KINDS[kind]["ops"]))


def _done(kind: str, receipts: list[Receipt], session: list[Call] | None) -> bool:
    """Whether a call of this kind completed in the turn or, as far as it is known, in the session."""
    if any(r.get("completed") and _does(kind, str(r.get("op")), bool(r.get("read"))) for r in receipts):
        return True
    # TPV7: the «sí» that turned a tool on in the person's profile ran nothing of what was asked (its result is
    # «rejected»), and it did turn that tool on: the result says which («turnedOn»), so «encendí las notas» is true.
    if kind == "encender" and any(_parsed(r).get("turnedOn") for r in receipts):
        return True
    return any(done and _does(kind, op, read) for op, done, read in session or [])


def _act_fact(kind: str, receipts: list[Receipt], session: list[Call] | None,
              passive: bool, unsure_said: bool = False) -> tuple[str, str] | None:
    """What contradicts a claim of ``kind`` that nothing of the turn or session completed, or None. ``unsure_said``: the
    sentence itself says it could not be verified, which is what a call that stayed unsure («sin confirmar») shows."""
    tried = [r for r in receipts if _does(kind, str(r.get("op")), bool(r.get("read")))]
    if tried and all(str(r.get("outcome") or "").startswith("sin confirmar") for r in tried):
        # Only unsure: it may have happened. Told so in the sentence, it is the verified with its limits; told by a
        # passive («el texto se envió a…»), it is what was delivered; and a look that completed in the turn may be what
        # the claim tells (the window it opened is there). Only a bare «abrí/escribí» over nothing else is contradicted.
        # uso-90 (diag-9dea U06, 6 of 6): an unsure call whose own result names the page it opened (openedUrl: what
        # stayed unsure is what played, not the opening) backs «abrí»; asked again, the answer once took the note's
        # internal words into the voice.
        opened = kind == "abrir" and any(_opened_page(r) for r in tried)
        if unsure_said or passive or opened or any(r.get("completed") and r.get("read") for r in receipts):
            return None
    if tried:
        return "not_completed", "no se completó: " + "; ".join(_told(r) for r in tried[-3:])
    if passive or session is None or kind in _MADE_IN_WORDS:
        # «Se abrió» with no call of its own may tell what a look saw; an unknown session may hold the call; and a
        # text, a list or an example may be what the answer itself made.
        return None
    ran = [r for r in receipts if r.get("completed")]
    return "no_call", ("ninguna llamada de esta sesión lo hizo" +
                       (f"; en este turno sólo: {'; '.join(_told(r) for r in ran[:3])}" if ran else
                        "; en este turno no se llamó a ninguna herramienta"))


# ---- up to date (ACT1) ------------------------------------------------------------------------------------------------
# VER2 (held-out V08, 10-11-2026): to «are you up to date?» the model said «Yes, I'm up to date. I checked and there's no
# newer version» (and «Sí, estoy al día») with no call at all: it has its installed version (mind.VERSION_FACT), never
# whether a newer one exists, which only baxy.update's check reads (its «checked», «latest», «newer»). The claim is a
# reading of that state, as «sigue abierto» is of a window: told in the first person of BAXY, or of the person's copy
# («tienes la última versión»), or as «no hay una versión más nueva». The first person is backed only by a completed
# baxy.update of the conversation (or a try of the turn, left to «partial»); the impersonal forms by any completed call
# of the turn too (they may tell what another reading showed, a program's own version). Read folded, Spanish and
# English; a clause with a negation or a
# condition before it («no sé si estoy al día», «I'm not sure if I'm up to date») claims nothing.
_SELF_LATEST = re.compile(
    r"\b(?:estoy|estas|esta baxy|baxy esta) (?:ya |totalmente |completamente |del todo )?(?:al dia|actualizad[oa]|"
    r"en (?:la|mi|tu|su) (?:ultima|mas reciente|mas nueva|version mas (?:reciente|nueva|actual)))"
    r"|\b(?:soy|tengo|tienes|uso|usas) (?:ya )?la (?:ultima|mas reciente|mas nueva|version mas (?:reciente|nueva|actual))"
    r"|\b(?:i(?:'|’)?m|i am|you(?:'|’)?re|you are|baxy is) (?:already |fully |completely )?(?:up to date|up-to-date|"
    r"on the (?:latest|newest|most recent)|running the (?:latest|newest|most recent))"
    r"|\b(?:you have|you(?:'|’)?ve got|i have) the (?:latest|newest|most recent) (?:version|release|update)")
_NONE_NEWER = re.compile(
    r"\bno (?:hay|existe|tengo|tienes) (?:ninguna |una |otra )?(?:version|actualizacion)(?:es)? (?:mas (?:nueva|reciente)|"
    r"nueva|pendiente|disponible)"
    r"|\b(?:there(?:'|’)?s|there is|there are) no (?:newer|new|more recent) (?:version|update|release)s?"
    r"|\bno (?:newer|new) (?:version|update|release)s? (?:is |are )?available")
_EN_OFF = re.compile(r"\b(?:not|never|if|whether|unless|cannot|can(?:'|’)?t|don(?:'|’)?t know|to see|let me|i(?:'|’)?ll)\b"
                     r"|n(?:'|’)?t\b")
UPDATE_OP = "baxy.update"
# REG1 (REV11 C-3): «Sí, tienes la última versión de Chrome», «Estás al día con tus pagos», «Estás al día: no te queda
# ninguna tarea» (after task.list) were read as BAXY's, and the note kept the tools toward baxy.update. The second person
# and the impersonal form are BAXY's only when the sentence names BAXY, or the person asked BAXY of itself (named it, or
# in the second person of the same state: «¿estás al día?», «are you up to date?») and no reading of the turn completed,
# which may be what they tell. «al día con / hasta / en … / up to date on / with …» says of what, in any person: of
# anything but a version or an update, it is not this state («estoy al día hasta mi entrenamiento»).
_YOU_SAID = re.compile(r"(?:estas|tienes|usas|you)\b")
_OF_WHAT = re.compile(r"\s+(?:con|hasta|sobre|en cuanto a|on|with|about|in)\s+(?!(?:(?:las|los|la|el|lo|tus|mis|sus|the|your|"
                      r"my|its)\s+)?(?:actualizacion|version|ultima|mas reciente|update|release|latest|newest|baxy))")
_ASKED_SELF = re.compile(
    r"\b(?:estas|estai|eres|sos|tienes|tenes|tenis|usas|te falta|te faltan) (?:ya |bien )?(?:al dia|actualizad[oa]|"
    r"(?:la |una |alguna )?(?:ultima|mas reciente|mas nueva|version|actualizacion))"
    r"|\b(?:are you|you(?:'|’)?re|you are|do you have|have you got) (?:already |fully )?(?:up to date|up-to-date|updated|"
    r"on the (?:latest|newest)|running the (?:latest|newest)|the (?:latest|newest))"
    r"|\b(?:version|actualizacion|update)(?:es|s)? (?:[a-z]+ )?(?:de ti|tuya|of you)\b")
_BAXY_NAMED = re.compile(r"\bbaxy\b")
UNCHECKED_UPDATE = ("en esta conversación nada comprobó si hay una versión más nueva de BAXY: ningún resultado lo "
                    "muestra (de la tuya sólo se sabe cuál está instalada); {tool} con action «check» sólo lo consulta")


def _asked_of_self(request: str) -> bool:
    """Whether the person asked BAXY of itself: named it, or asked its state in the second person, not of something
    else («¿estás al día con las noticias?»)."""
    asked = _fold(request or "")
    return bool(_BAXY_NAMED.search(asked)) or any(not _OF_WHAT.match(asked, hit.end())
                                                  for hit in _ASKED_SELF.finditer(asked))


def _unchecked_update(folded: str, statements: list[tuple[int, int]], receipts: list[Receipt],
                      session: list[Call] | None, text: str, request: str = "") -> tuple[int, int] | None:
    """The span of the first statement that tells BAXY up to date or no newer version while nothing of the conversation
    looked (ACT1), or None. Not read when the session is not known whole: a look may be in what was left out."""
    if session is None:
        return None
    # A look of the turn that failed is read by «partial» on its own fields (MEN1: «checked» false), never guessed here.
    checked = any(done and operation_of(op) == UPDATE_OP for op, done, _read in session) or any(
        operation_of(str(r.get("op"))) == UPDATE_OP for r in receipts)
    if checked:
        return None
    read_now = any(r.get("completed") for r in receipts)
    of_self = _asked_of_self(request) and not read_now
    for start, end in statements:
        named = bool(_BAXY_NAMED.search(folded, start, end))
        for pattern in (_SELF_LATEST, _NONE_NEWER):
            for hit in pattern.finditer(folded, start, end):
                clause = _clause_start(folded, start, hit.start())
                if _negated(folded, start, hit.start(), text) or _EN_OFF.search(folded, clause, hit.start()):
                    continue
                if _OF_WHAT.match(folded, hit.end(), end):
                    continue  # «al día con tus pagos»: of something else
                if (pattern is _NONE_NEWER or _YOU_SAID.match(hit.group(0))) and not (named or of_self):
                    continue
                return _clause_start(folded, start, hit.start()), end
    return None


# ---- states of now (encargo 56) ---------------------------------------------------------------------------------------
# A state of the PC said as it is now, folded: «está/sigue/quedó (ya) instalado», «ya se descargó», «terminó de bajar»;
# and how a result says it, like _PLACE_WORDS: the kind of act that makes it (KINDS), the values of a result's own state
# field that are that state, and the fields named as it with the value that says so. Real uso 03-11: «Ya está instalado,
# listo para jugar» after a game_install_named that read «queued», 0 of 0 bytes, with no call in the turn.
_STATE_NOW = re.compile(r"\b(?:(?:sigue|siguen|esta|estan|quedo|quedaron) (?:todavia |aun |ya )?(?P<state>"
                        r"desinstalad|instalad|descargad|abiert|cerrad|minimizad|maximizad|silenciad|encendid|prendid|"
                        r"apagad|activad|desactivad|desconectad|conectad|sonando|reproduciendo|en pausa|pausad|"
                        r"corriendo|en ejecucion)"
                        r"|se (?P<passive>desinstalo|instalo|descargo|bajo|desconecto|conecto|prendio|encendio|apago|"
                        r"abrio|cerro)"
                        r"|termino de (?P<ended>instalar|descargar|bajar))")
_INSTALLED = ("instalar", {"installed", "already_installed"}, {"installed": True})
_STATES: dict[str, tuple[str, set[str], dict[str, bool]]] = {
    "instalad": _INSTALLED, "instalo": _INSTALLED, "instalar": _INSTALLED,
    "descargad": ("instalar", {"installed", "already_installed", "downloaded", "completed"},
                  {"installed": True, "downloaded": True}),
    "desinstalad": ("instalar", {"uninstalled", "not_installed"}, {"installed": False}),
    "abiert": ("abrir", {"open", "opened", "running", "already_running"}, {"open": True, "running": True}),
    "cerrad": ("cerrar", {"closed", "exited", "not_running"}, {"open": False, "running": False}),
    "minimizad": ("ventana", {"minimized"}, {"minimized": True}),
    "maximizad": ("ventana", {"maximized"}, {"maximized": True}),
    "silenciad": ("silenciar", {"muted"}, {"muted": True}),
    "encendid": ("encender", {"on", "enabled", "connected"}, {"on": True, "enabled": True}),
    "apagad": ("encender", {"off", "disabled"}, {"on": False, "enabled": False}),
    "conectad": ("encender", {"connected"}, {"connected": True}),
    "desconectad": ("encender", {"disconnected"}, {"connected": False}),
    "sonando": ("reproducir", {"playing"}, {"playing": True}),
    "en pausa": ("reproducir", {"paused"}, {"paused": True}),
}
for _same, _as in (("descargo", "descargad"), ("bajo", "descargad"), ("descargar", "descargad"),
                   ("bajar", "descargad"), ("desinstalo", "desinstalad"), ("activad", "encendid"),
                   ("desactivad", "apagad"), ("reproduciendo", "sonando"), ("pausad", "en pausa"),
                   ("corriendo", "abiert"), ("en ejecucion", "abiert"), ("prendid", "encendid"),
                   ("prendio", "encendid"), ("encendio", "encendid"), ("apago", "apagad"), ("conecto", "conectad"),
                   ("desconecto", "desconectad"), ("abrio", "abiert"), ("cerro", "cerrad")):
    _STATES[_same] = _STATES[_as]
# A result's own field that tells the state it read (top level of observed, never a nested part: an installed game's
# «update» has a state of its own).
_STATE_FIELDS = ("state", "playbackStatus")
# What the fact tells of that result besides its state: its name and how far it went.
_STATE_SHOWN = re.compile(r"^(?:name|title|bytes\w*|progress\w*|downloaded|total)$")
# Every word a result uses for a state (the values and fields above), the longest first: the end of an error code may
# name one («memory_disabled», «app_not_running», «steam_game_not_installed», «microphone_already_muted»).
_STATE_WORDS = sorted({word for _kind, values, named in _STATES.values() for word in (*values, *named)},
                      key=lambda word: -word.count("_"))


def _pending_cell(receipts: list[Receipt]) -> tuple[str, str] | None:
    """The cell and text the turn's last call left pending (ActiveCell.cs in the App: «cell» with «pendingText»), else None.
    Compares the receipt's own fields, nothing of the answer's words."""
    if not receipts:
        return None
    observed = _parsed(receipts[-1]).get("observed")
    cell = observed.get("cell") if isinstance(observed, dict) else None
    if isinstance(cell, dict) and isinstance(cell.get("pendingText"), str) and isinstance(cell.get("address"), str):
        return cell["address"], cell["pendingText"]
    return None


def _code_state(code: str) -> str | None:
    """The state an error code ends by naming, or None; one denied before it («input_never_enabled»,
    «download_not_completed») names none."""
    parts = code.lower().split("_")
    for word in _STATE_WORDS:
        size = word.count("_") + 1
        if parts[-size:] == word.split("_"):
            return None if len(parts) > size and parts[-size - 1] in ("not", "no", "never") else word
    return None


def _stale_states(answer: str, folded: str, statements: list[tuple[int, int]], receipts: list[Receipt],
                  earlier: list[Receipt] | None, text: str) -> list[dict]:
    """Rule ``stale_state``: a state of now said while nothing of the turn read anything or completed an act of its
    kind, and the last result of that kind the conversation shows says another state or did not complete."""
    if not earlier or any(r.get("completed") and r.get("read") for r in receipts):
        return []
    found: list[dict] = []
    for start, end in statements:
        for hit in _STATE_NOW.finditer(folded, start, end):
            if _negated(folded, start, hit.start(), text) or _UNSURE.search(folded, start, end):
                continue
            kind, backs, fields = _STATES[hit.group("state") or hit.group("passive") or hit.group("ended")]
            if any(r.get("completed") and _does(kind, str(r.get("op")), False) for r in receipts):
                continue
            # A call that waited for the person's «sí» ran nothing (uso-87, diag-bc8c F13: «mi memoria está apagada,
            # ¿lo enciendo?» after memory_save read memory_disabled and memory_enable waited): the state is the one read
            # before it.
            last = next((r for r in reversed(earlier) if _matches(operation_of(str(r.get("op"))), KINDS[kind]["ops"])
                         and _parsed(r).get("status") != "needs_confirmation"), None)
            fact = _stale_fact(last, backs, fields) if last is not None else None
            if fact:
                found.append({"rule": "stale_state", "said": _quote(answer, _clause_start(folded, start, hit.start()),
                                                                    end), "fact": fact})
                return found
    return found


def _stale_fact(last: Receipt, backs: set[str], fields: dict[str, bool]) -> str | None:
    """What the last result of a state's kind says against it, or None when it backs it or its body is not known."""
    if last.get("observation") is None:
        return None
    facts = _parsed(last)
    observed = facts.get("observed") if isinstance(facts.get("observed"), dict) else {}
    if not last.get("completed"):
        # Only an act that would have made it: a look that failed is what the answer may tell («está desactivado»), and
        # so is a failure whose code or fields tell that state (diag-fd2b F13: memory_save failed with memory_disabled,
        # «la memoria está apagada»; read as «nothing read it», the note led the model to turn the memory on unasked).
        named = _code_state(str(facts.get("error") or ""))
        if last.get("read") or (named is not None and (named in backs or fields.get(named) is True)) or any(
                (key in _STATE_FIELDS and isinstance(value, str) and value.lower() in backs)
                or (key in fields and isinstance(value, bool) and value == fields[key])
                for where in (observed, facts) for key, value in where.items()):
            return None
        return f"lo último de eso fue {_told(last)}, y en este turno nada lo leyó"
    shown: list[str] = []
    against = False
    for where in (observed, facts):
        for key, value in where.items():
            if key in _STATE_FIELDS and isinstance(value, str):
                if value.lower() in backs:
                    return None
                against = True
            elif key in fields and isinstance(value, bool):
                if value == fields[key]:
                    return None
                against = True
            elif not (_STATE_SHOWN.match(key) and isinstance(value, (str, int, float))) or isinstance(value, bool):
                continue
            shown.append(f"{key} «{value}»" if isinstance(value, str) else f"{key} {value}")
    if not against:
        return None
    told = f"lo último que se leyó de eso, {last.get('tool') or last.get('op')}, dice {', '.join(shown)}"
    after = observed.get("next") or facts.get("next")
    if isinstance(after, str) and after.strip():
        told += f"; su next: {after.strip()}"
    return told + "; en este turno nada lo leyó"


# A place app_open asks for (its «place» argument) and how an answer names it, folded.
_PLACE_WORDS = {"library": "biblioteca", "store": "tienda", "community": "comunidad", "results": "resultados",
                "friends": "amigos", "downloads": "descargas", "settings": "configuracion|ajustes", "sound": "sonido",
                "display": "pantalla", "network": "red|redes", "home": "inicio|pagina principal", "search": "busqueda",
                "playlists": "listas|playlists", "profile": "perfil", "game": "juego"}


def _places_asked(receipts: list[Receipt]) -> list[tuple[Receipt, str]]:
    """The app_open calls of the turn that asked for a place nothing read back (placeRequested, no effectReadBack
    true), with the words that name it, when no look completed after them (a view may show the place: not read here)."""
    asked = []
    for index, r in enumerate(receipts):
        place = (r.get("arguments") or {}).get("place")
        observed = _parsed(r).get("observed")
        if str(r.get("op")) != "app.open" or not r.get("completed") or not isinstance(place, str) or not place \
                or not isinstance(observed, dict) or observed.get("placeRequested") is not True \
                or observed.get("effectReadBack") is True:
            continue
        if any(later.get("completed") and later.get("read") for later in receipts[index + 1:]):
            continue
        words = [_PLACE_WORDS.get(place.lower(), re.escape(_fold(place)))]
        value = (r.get("arguments") or {}).get("placeValue")
        if isinstance(value, str) and value.strip():
            words.append(re.escape(_fold(value.strip())))
        asked.append((r, "|".join(words)))
    return asked


# A display mode told as kept: the words of keeping it, read against the result's savedForRestart.
_MODE_KEPT = re.compile(r"\b(?:guarda|guardo|guarde|guardad[oa]|permanente|permanentemente|para siempre)\b")


def _modes_not_saved(receipts: list[Receipt]) -> list[tuple[Receipt, set[str]]]:
    """The last display_mode_set of the turn when it left its mode only shown (savedForRestart false), with the figures of
    the mode Windows has saved (savedMode) this one does not share: a call after it that saved it leaves nothing to
    contradict."""
    modes = [r for r in receipts if str(r.get("op")) == "display.mode.set" and r.get("completed")]
    if not modes:
        return []
    observed = _parsed(modes[-1]).get("observed")
    if not isinstance(observed, dict) or observed.get("savedForRestart") is not False:
        return []
    saved, final = observed.get("savedMode"), observed.get("final")
    figures = {str(v) for v in saved.values()} if isinstance(saved, dict) else set()
    return [(modes[-1], figures - ({str(v) for v in final.values()} if isinstance(final, dict) else set()))]


# A control said not to be there, and its name (F019): «no hay un botón de «X»», «no veo ningún botón X».
_NO_CONTROL = re.compile(r"\bno (?:hay|veo|encuentro|aparece|existe)\s+(?:un |una |ningun |ninguna |el |la )?"
                         r"(?:boton|control|opcion|pestana|enlace)(?:es)?\s+(?:(?:de|que diga|llamad[oa])\s+)?"
                         r"(?:«(?P<quoted>[^»\n]{2,40})»|(?P<bare>[^\s»\"'.,;:!?…]{3,40}))")

_PARTIAL_TOLD = {
    "readInPart": "lo demás no se leyó",
    "entriesShown": "la lista que muestra no tiene todas las entradas",
    "timeLimitReached": "la búsqueda paró en su tiempo límite",
    "skipped": "hubo archivos cuyo texto no se leyó",
    "subfoldersNotOpened": "sus subcarpetas no se abrieron",
    "hiddenOrSystemSkipped": "no miró las entradas ocultas o de sistema",
    "entriesNotListed": "hay entradas sin listar",
    "endReached": "no llegó al final",
    "bodyTruncated": "el texto se cortó",
    "viewCut": "la vista se cortó: parte de lo que mostraba no se listó",
    "searchedElsewhere": "no se buscó fuera de esa carpeta",
    "failedRead": "no leyó nada: la lectura falló",
    "notChecked": "no se comprobó lo pedido",  # the words its outcome line already has (mind.NOT_CHECKED)
    "covers": "lo que cubre su lectura, según su campo covers, es: {covers}",
}
# Errors of a look that are its reading that something is not there (file_not_found, window_not_found…).
_ABSENCE_ERROR = re.compile(r"not_found|no_match|not_installed|absent|missing|not_running|not_open|no_window|"
                            r"nothing|empty|unknown_(?:app|file|window)")


def _partial(receipt: Receipt) -> str:
    """Which of its own fields says a result covered only part of what it read, or ""."""
    facts = _parsed(receipt)
    if not facts:
        return ""
    observed = facts.get("observed") if isinstance(facts.get("observed"), dict) else {}
    # MEN1 (AMD2 §9, hallazgo E): a result that says in its own field that it did not look at what its call is for
    # finding out («checked» false: a failure before looking, a store that updates by itself) backs no absence, whatever
    # its status: «No hay una versión más reciente» after baxy_update failed with baxy_update_development_build.
    if observed.get("checked") is False:
        return "notChecked"
    for where in (observed, facts):
        if where.get("readInPart") is True:
            return "readInPart"
        shown, count = where.get("entriesShown"), where.get("count")
        if isinstance(shown, int) and isinstance(count, int) and shown < count:
            return "entriesShown"
        scope = where.get("searchScope") if isinstance(where.get("searchScope"), dict) else {}
        if scope.get("timeLimitReached") is True:
            return "timeLimitReached"
        if any(isinstance(scope.get(k), int) and scope[k] > 0
               for k in ("skippedTooLarge", "skippedNotText", "skippedUnreadable")):
            return "skipped"
        for key in ("subfoldersNotOpened", "hiddenOrSystemSkipped", "entriesNotListed"):
            if isinstance(where.get(key), int) and not isinstance(where.get(key), bool) and where[key] > 0:
                return key
        if where.get("endReached") is False:
            return "endReached"
        if where.get("bodyTruncated") is True:
            return "bodyTruncated"
    # The App's own cut mark (ScreenViewProjection); «N líneas de texto no se listan: repiten…» leaves nothing out.
    view = facts.get("view")
    if isinstance(view, str) and "(texto cortado:" in view:
        return "viewCut"
    if observed.get("searchedElsewhere") is False:
        return "searchedElsewhere"
    # uso-106 (F2): a result that says in its own field what its reading covered (email.latest.read: only the newest mail
    # of one Inbox, no sender searched) read only that: an absence of anything else is not its reading.
    if isinstance(observed.get("covers"), str) and observed["covers"].strip():
        return "covers"
    # A look that failed read nothing, unless its error is itself the reading that something is not there.
    error = str(facts.get("error") or facts.get("cause") or "")
    if receipt.get("read") and facts.get("status") == "failed" and not _ABSENCE_ERROR.search(error):
        return "failedRead"
    return ""


def _absence_about(sentence: str, absent: re.Match[str] | None) -> bool:
    """Whether an absence in the sentence is a plain «no está / no hay / ninguno» about what was read (not «no pude»,
    «no tiene ventana», «nada más»)."""
    if absent is None:
        return False
    word = absent.group(0)
    if word == "nada":
        return bool(re.search(r"\b(?:no (?:encontre|hay|aparece|vi)|encontre) nada\b", sentence))
    if word.startswith("ningun"):
        return bool(re.search(r"\b(?:no (?:hay|encontre|aparece|vi|existe)|sin) [\w ]{0,20}ningun", sentence))
    return True


def _numbers(answer: str, folded: str, statements: list[tuple[int, int]],
             receipts: list[Receipt]) -> list[dict]:
    readings: list[tuple[str, float, str]] = []  # (key, value, tool)
    level_readings: list[tuple[str, float, str]] = []
    # Uso real 04-11: the sizes a text read writes with their unit («8 GB» in vision.describe's description).
    written_sizes: list[tuple[float, int]] = []
    for r in receipts:
        tool = str(r.get("tool") or r.get("op"))
        values = []
        written_sizes.extend(_sizes_with_their_unit(_parsed(r)))
        for key, value in [*_walk(_parsed(r)), *_walk(r.get("arguments") or {})]:
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                values.append((key, float(value), tool))
            elif isinstance(value, str):
                # Uso real 04-11: what a text read says is a reading however long the text is: a slide read whole past
                # 400 characters gave no number, and the second round took out all that was read.
                values.extend((key, float(n.replace(",", ".")), tool)
                              for n in re.findall(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w])", value))
                written_sizes.extend((float(m.group(1).replace(",", ".")), _SIZE_POWER[m.group(2)])
                                     for m in _SIZE.finditer(_fold(value)))
        # A number of 309 digits or more is no float (inf): no reading, and int() of it failed the check and the turn.
        values = [reading for reading in values if math.isfinite(reading[1])]
        readings.extend(values)
        if _matches(operation_of(str(r.get("op"))), _LEVEL_OPS):
            level_readings.extend(values)
    found: list[dict] = []

    def percent_ok(n: float, pool: list[tuple[str, float, str]], with_sign: bool) -> bool:
        for key, v, _ in pool:
            fraction = 0 < v <= 1 and not re.search(r"percent|pct|level|volume|brightness", key, re.IGNORECASE)
            if abs(n - v) < 0.51 and not (with_sign and fraction and n <= 1 and v != int(v)):
                return True
            if fraction and abs(n - v * 100) < 0.51:
                return True
        return False

    for start, end in statements:
        for m in _PERCENT.finditer(folded, start, end):
            n = float(m.group(1).replace(",", "."))
            pool = level_readings or readings
            if pool and not percent_ok(n, pool, with_sign=True):
                found.append({"rule": "number", "said": _quote(answer, start, end),
                              "fact": _readings_told(pool)})
                break
        word = _LEVEL_WORD.search(folded, start, end)
        for m in _LEVEL.finditer(folded, word.end(), end) if word and level_readings else ():
            n = float(m.group(1).replace(",", "."))
            if re.search(r"\b(?:no|ni|sino|en vez de|en lugar de|antes)\s*$", folded[max(start, m.start() - 15):m.start()]):
                continue  # «quedó en 0, no en 40»: the number said as what it is not
            if not percent_ok(n, level_readings, with_sign=False) and not any(f["rule"] == "number" for f in found):
                found.append({"rule": "number", "said": _quote(answer, start, end),
                              "fact": _readings_told(level_readings)})
                break
        for m in _SIZE.finditer(folded, start, end):
            n, unit = float(m.group(1).replace(",", ".")), m.group(2)
            sizes = [(k, v, t) for k, v, t in readings if v >= 1]
            if not sizes or unit == "b" and n < 1:
                continue
            # The reading in the unit said: a field in bytes unless its name says KB, MB or GB; base 1000 or 1024; the
            # said number rounded (to its own decimals, or within 6 %).
            power = _SIZE_POWER[unit]
            tolerance = max(0.06 * n, 0.051 if "." in m.group(1) or "," in m.group(1) else 0.5)
            if any(abs(n - told) <= tolerance for told, told_power in written_sizes if told_power == power):
                continue
            if not any(abs(n - v / base ** (power - field)) <= tolerance
                       for key, v, _ in sizes for field in [_field_power(key)] if field <= power
                       for base in (1000, 1024)):
                found.append({"rule": "number", "said": _quote(answer, start, end),
                              "fact": _readings_told([s for s in sizes if re.search(r"size|bytes|length", s[0],
                                                                                    re.IGNORECASE)] or sizes)})
                break
    return found


def _field_power(key: str) -> int:
    """The unit a size field is in, by its name (sizeKb, freeGb…): bytes when it does not say."""
    found = re.search(r"(kb|kib|mb|mib|gb|gib|tb)(?![a-z])", key.lower())
    return _SIZE_POWER[found.group(1)] if found else 0


def _readings_told(pool: list[tuple[str, float, str]]) -> str:
    seen = []
    for key, value, tool in pool:
        shown = f"{tool} dice {key} {int(value) if value == int(value) else value}"
        if shown not in seen:
            seen.append(shown)
    return "ese número no está en los resultados: " + "; ".join(seen[:4])


def _paths(receipts: list[Receipt]) -> list[str]:
    out = []
    for r in receipts:
        for key, value in [*_walk(_parsed(r)), *_walk(r.get("arguments") or {})]:
            if isinstance(value, str) and re.match(r"^[A-Za-z]:[\\/]", value):
                out.append(value.replace("/", "\\").rstrip("\\").lower())
    return out


def _folders(answer: str, folded: str, raw_folded: str, statements: list[tuple[int, int]], receipts: list[Receipt],
             request: str) -> list[dict]:
    found: list[dict] = []
    placed = [r for r in receipts if r.get("completed") and _matches(operation_of(str(r.get("op"))), _PLACE_OPS)]
    where = []
    for r in placed:
        facts = _parsed(r)
        observed = facts.get("observed") if isinstance(facts.get("observed"), dict) else {}
        path = observed.get("fullPath") or observed.get("destinationFullPath") or observed.get("path")
        if isinstance(path, str) and re.match(r"^[A-Za-z]:[\\/]", path):
            where.append((r, path.replace("/", "\\").lower()))
    dialogs = _dialog_saves(receipts)
    if where or dialogs:
        for start, end in statements:
            sentence = folded[start:end]
            put = _PLACED.search(sentence)
            if not put or _negated(folded, start, start + put.start(), answer):
                continue
            # A dialog's whole path said is read against the results below, name by name of it.
            if not where and _PATH.search(answer[start:end]):
                continue
            named = [(label, shows) for label, pattern, shows in _FOLDERS
                     for m in [pattern.search(sentence)] if m and not _NOT_THERE.search(sentence[:m.start()][-30:])]
            if _HOME.search(sentence):
                named.append(("home", ("home",)))
            for label, shows in named:
                if not any(_in_folder(path, label, shows) for _, path in where + dialogs):
                    receipt, path = (where + dialogs)[-1]
                    found.append({"rule": "folder", "said": _quote(answer, start, end),
                                  "fact": f"{receipt.get('tool')} lo dejó en {_original_path(receipt, path)}"})
                    break
        # The folder the person asked for is not where it went, and the answer tells it as done in no place at all
        # (E024: «Listo, agregué la línea a notas.txt» for «… en la carpeta BAXY-bench», written in the home
        # folder). An answer that names a place (a path, a folder, the asked one said as where it did not go) is read
        # by the rule above: «lo guardé en C:\Users\…\prueba.txt» is literally true (a doubtful one by hand, F013).
        wanted = _asked_folder(request)
        if where and wanted and not found and not any(_in_asked(path, wanted) for _, path in where) \
                and not _mentions(raw_folded, wanted) and not _PATH.search(answer) and not _HOME.search(raw_folded) \
                and not _WORK.search(raw_folded) and not any(p.search(raw_folded) for _, p, _ in _FOLDERS):
            for start, end in statements:
                sentence = folded[start:end]
                put = _PLACED.search(sentence)
                if put and not _negated(folded, start, start + put.start(), answer):
                    receipt, path = where[-1]
                    found.append({"rule": "asked_folder", "said": _quote(answer, start, end),
                                  "fact": f"la persona pidió {wanted[1]} y {receipt.get('tool')} lo dejó en "
                                          f"{_original_path(receipt, path)}"})
                    break
    if dialogs and not found:
        found.extend(_dialog_place(answer, folded, raw_folded, statements, dialogs[-1], request))
    shown = _paths(receipts)
    asked = (request or "").replace("/", "\\").lower()
    if shown:
        told = answer.replace("/", "\\").lower()
        for m in _PATH.finditer(answer):
            said = m.group(0).replace("/", "\\").rstrip(".\\").lower()
            if not said or said in asked or _says_shown(told, m.start(), shown):
                continue
            base = said.rsplit("\\", 1)[-1]
            if any(p == said or p.startswith(said + "\\") or (said.startswith(p + "\\") and base in
                                                                (json.dumps([r.get("observation") for r in receipts],
                                                                            ensure_ascii=False).lower()))
                   for p in shown):
                continue
            found.append({"rule": "folder", "said": m.group(0),
                          "fact": "esa ruta no está en los resultados; dicen: " + "; ".join(dict.fromkeys(shown[:3]))})
            break
    return found


def _dialog_saves(receipts: list[Receipt]) -> list[tuple[Receipt, str]]:
    """Each file a file dialog of the turn saved or opened and closed on, by its receipt (fileDialog.path), folded."""
    saves = []
    for r in receipts:
        observed = _parsed(r).get("observed")
        dialog = observed.get("fileDialog") if isinstance(observed, dict) else None
        if r.get("completed") and isinstance(dialog, dict) and dialog.get("closed") is True \
                and isinstance(dialog.get("path"), str) and re.match(r"^[A-Za-z]:[\\/]", dialog["path"]):
            saves.append((r, dialog["path"].replace("/", "\\").lower()))
    return saves


def _plain(text: str) -> str:
    """Only the letters and digits of a folded name: «baxy-bench» and «baxy bench» are one."""
    return "".join(c for c in text if c.isascii() and c.isalnum())


def _dialog_place(answer: str, folded: str, raw_folded: str, statements: list[tuple[int, int]],
                  saved: tuple[Receipt, str], request: str) -> list[dict]:
    """Encargo 82 (vivo del 81, «Guardar como»: «lo guardé en <la carpeta pedida>» of a file left in another one, 3 of 4
    answers told nothing the check could read): the folder an answer says against the path the dialog's receipt shows. A
    name is compared by its form, with the person's own word: a known folder is the rule above's, a plain word no name of
    a place. Only what the answer says; the words stay the model's."""
    receipt, path = saved
    folders = [_plain(part) for part in path.split("\\")[:-1]]
    asked_at = _ASKED_AT.search(_fold(request or ""))
    asked = asked_at.group(1).rstrip(".:") if asked_at else ""
    fact = f"{receipt.get('tool')} lo dejó en {_original_path(receipt, path)}"
    told = False
    for start, end in statements:
        sentence = folded[start:end]
        put = _PLACED.search(sentence)
        if not put or _negated(folded, start, start + put.start(), answer):
            continue
        told = True
        at = _SAID_AT.search(sentence, put.start())
        if not at or _NOT_THERE.search(sentence[:at.start()][-30:]):
            continue
        said = answer[start + at.start(1):start + at.end(1)].rstrip(".:")
        if re.match(r"^[A-Za-z]:[\\/]", said):
            continue  # a whole path is read against the results below
        parts = re.split(r"[\\/]", said)
        routed = len(parts) > 1
        if re.search(r"\.[A-Za-z0-9]{1,5}$", parts[-1]):
            parts = parts[:-1]  # the file's own name
        for part in parts:
            name = _fold(part)
            if any(pattern.search(name) for _, pattern, _ in _FOLDERS) or not _plain(name):
                continue
            named = routed or part[:1].isupper() or re.search(r"[\d_-]", part) or name == asked
            if named and not any(_plain(name) in folder for folder in folders):
                return [{"rule": "folder", "said": _quote(answer, start, end), "fact": fact}]
    plain_answer = _plain(raw_folded)
    if told and asked and not any(_plain(asked) in folder for folder in folders) and _plain(asked) not in plain_answer \
            and not _PATH.search(answer) and not _HOME.search(raw_folded) and not _WORK.search(raw_folded) \
            and not any(pattern.search(raw_folded) for _, pattern, _ in _FOLDERS) \
            and not any(folder and folder in plain_answer for folder in folders[1:]):
        return [{"rule": "asked_folder", "said": _quote(answer, 0, len(answer)),
                 "fact": f"la persona pidió la carpeta {asked} y {fact}"}]
    return []


def _says_shown(told: str, start: int, shown: list[str]) -> bool:
    """Whether the answer (lower case, backslashes) says, from ``start``, a path a result shows or one of its folders,
    ending where a name ends: a last part with spaces («…\\Mis documentos.») is read whole against the results."""
    for path in shown:
        while path.count("\\") and len(path) > 3:
            end = start + len(path)
            if told.startswith(path, start) and (end == len(told) or told[end].isspace() or told[end] in ",;:»\"”)'!?"
                                                  or told[end] == "." and (end + 1 == len(told)
                                                                           or told[end + 1].isspace())):
                return True
            path = path.rsplit("\\", 1)[0]
    return False


def _asked_folder(request: str) -> tuple[str, str, tuple[str, ...]] | None:
    """The folder the person's words name as where to put something: an absolute path (without a file name of its
    own) or one of _FOLDERS, as (kind, how to say it, what a path shows); None when they name none or several."""
    paths = [m.group(0).rstrip(".\\/") for m in _PATH.finditer(request or "")]
    if len(paths) == 1:
        path = paths[0].replace("/", "\\")
        if re.search(r"\.[A-Za-z0-9]{1,5}$", path):
            path = path.rsplit("\\", 1)[0]
        return "path", path, (path.lower(),)
    if paths:
        return None
    folded = _fold(request or "")
    named = [(label, shows) for label, pattern, shows in _FOLDERS if pattern.search(folded)]
    if len(named) == 1:
        label, shows = named[0]
        return "named", "BAXY-bench" if label == "baxy-bench" else label.capitalize(), shows
    return None


def _mentions(folded_answer: str, wanted: tuple[str, str, tuple[str, ...]]) -> bool:
    kind, said, shows = wanted
    if kind == "path":
        last = said.replace("/", "\\").rsplit("\\", 1)[-1].lower()
        return shows[0] in folded_answer.replace("/", "\\") or bool(last) and last in folded_answer
    return any(pattern.search(folded_answer) for label, pattern, s in _FOLDERS if s == shows)


def _in_asked(path: str, wanted: tuple[str, str, tuple[str, ...]]) -> bool:
    kind, _, shows = wanted
    if kind == "path":
        return path == shows[0] or path.startswith(shows[0] + "\\")
    return _in_folder(path, "named", shows)


def _in_folder(path: str, label: str, shows: tuple[str, ...]) -> bool:
    sandboxed = any(s in path for s in _SANDBOX)
    if label == "work":
        return sandboxed
    if label == "home":
        return not sandboxed and bool(re.match(r"^[a-z]:\\users\\[^\\]+\\", path))
    return not sandboxed and any(s + "\\" in path + "\\" for s in shows)


def _original_path(receipt: Receipt, folded_path: str) -> str:
    for key, value in _walk(_parsed(receipt)):
        if isinstance(value, str) and value.replace("/", "\\").lower() == folded_path:
            return value
    return folded_path


def _saved_names(answer: str, text: str, folded: str, statements: list[tuple[int, int]],
                 receipts: list[Receipt]) -> list[dict]:
    """«Guardé lista.txt» while no result of the turn shows lista.txt and what was read from the last act that could
    save on names the file otherwise (E017)."""
    acts = [i for i, r in enumerate(receipts) if _does("guardar", str(r.get("op")), bool(r.get("read")))]
    shown = _names_shown(receipts[acts[-1]:]) if acts else []
    if not shown:
        return []
    seen = _fold("\n".join(_texts(r) for r in receipts))
    for start, end in statements:
        for hit in _SAVED.finditer(folded, start, end):
            if not _preterite(text, hit) or _negated(folded, start, hit.start(), text):
                continue
            stop = next((m.start() for m in _CLAUSE_END.finditer(folded, hit.end(), end)), end)
            for m in _FILE_NAME.finditer(folded, _clause_start(folded, start, hit.start()), stop):
                said = m.group("name")
                if re.search(rf"(?<![\w.-]){re.escape(said)}(?![\w-]|\.[a-z0-9])", seen):
                    continue
                stem, ext = said.rsplit(".", 1)
                other = [(name, where) for name, where in shown if _fold(name) != said
                         and (_fold(name).rsplit(".", 1)[0] == stem or _fold(name).rsplit(".", 1)[1] == ext)]
                if other:
                    name, where = other[-1]
                    return [{"rule": "saved_name", "said": _quote(answer, start, end),
                             "fact": f"ningún resultado muestra {answer[m.start('name'):m.end('name')]}; {where} dice "
                                     f"que el archivo es {name}"}]
    return []


def _texts(receipt: Receipt) -> str:
    """Every text of a result and of its arguments, unescaped (a name in a path or a view is found as it is)."""
    facts = _parsed(receipt)
    values = [v for _, v in _walk(facts)] if facts else [receipt.get("observation") or ""]
    values += [v for _, v in _walk(receipt.get("arguments") or {})]
    return "\n".join(str(v) for v in values if isinstance(v, str))


def _names_shown(receipts: list[Receipt]) -> list[tuple[str, str]]:
    """The file names these results show, in order, with who shows them: the first part of a window's title (not one
    it left, «gone», or had «before»), and the name of what a file result wrote."""
    shown: list[tuple[str, str]] = []
    for r in receipts:
        facts = _parsed(r)
        for key, value in _walk(facts):
            if not isinstance(value, str) or key == "gone" or re.search(r"before|was", key, re.IGNORECASE):
                continue
            titles = [value] if re.search(r"title", key, re.IGNORECASE) else []
            titles += [m.group(1) for m in _TITLED.finditer(value)]
            shown += [(hit.group("name").strip(), "la ventana") for t in titles
                      for hit in [_TITLE_NAME.match(t.strip())] if hit]
        observed = facts.get("observed") if isinstance(facts.get("observed"), dict) else {}
        if not r.get("read") and _matches(operation_of(str(r.get("op"))), _PLACE_OPS):
            for key in _NAME_FIELDS:
                value = observed.get(key)
                base = value.replace("/", "\\").rsplit("\\", 1)[-1] if isinstance(value, str) else ""
                if re.search(r"\.(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{1,5}$", base):
                    shown.append((base, str(r.get("tool") or r.get("op"))))
                    break
    return shown


# ---- names found ------------------------------------------------------------------------------------------------------
# «No encontré X», «no pude encontrar X», and the file named right after it in its clause as what was not found: only an
# article or the word for a file between them (not «otro X», another one; nor «errores en X», where X is the place).
_NOT_FOUND = re.compile(r"\bno (?:(?:lo|la|los|las|pude|logre|se) )*(?:encontre|halle|localice|ubique|encontro|"
                        r"(?:pude|logre) (?:encontrar|hallar|localizar|ubicar)(?:lo|la)?)\b")
_FOUND_OBJECT = re.compile(r"(?:[\s«\"“']|\b(?:el|la|los|las|un|una|tu|su|tus|sus|ningun|ninguna|archivo|fichero|"
                           r"documento|llamad[oa])\b)*")


def _found_files(receipts: list[Receipt]) -> list[tuple[str, str, Receipt]]:
    """Every file a result of the turn names as found, as (its place: the known folder and its relative path, lower
    case with backslashes; the name as the result writes it; the receipt): each object of the result with a relativePath."""
    found = []

    def objects(value: Any) -> Iterable[dict]:
        if isinstance(value, dict):
            yield value
            for v in value.values():
                yield from objects(v)
        elif isinstance(value, list):
            for v in value:
                yield from objects(v)

    for r in receipts:
        for item in objects(_parsed(r)):
            relative = item.get("relativePath")
            if isinstance(relative, str) and relative.strip():
                place = "\\" + str(item.get("folder") or "") + "\\" + relative.replace("/", "\\")
                found.append((place.lower(), relative, r))
    return found


def _not_found_names(answer: str, folded: str, raw_folded: str, statements: list[tuple[int, int]],
                     receipts: list[Receipt]) -> list[dict]:
    """«No encontré ideas.txt» while a result of the turn found ideas.txt (rule ``found``)."""
    found = _found_files(receipts)
    if not found:
        return []
    for start, end in statements:
        for hit in _NOT_FOUND.finditer(folded, start, end):
            stop = next((m.start() for m in _CLAUSE_END.finditer(folded, hit.end(), end)), end)
            name = next(_FILE_NAME.finditer(raw_folded, hit.end(), stop), None)
            if name is None or not _FOUND_OBJECT.fullmatch(folded, hit.end(), name.start()):
                continue
            # With its accents: a name alike that a search offers (known_file_not_found) differs only in them.
            said = answer[name.start():name.end()].replace("/", "\\").lower()
            rest = folded[name.end():stop]
            places = [shows for label, pattern, shows in _FOLDERS if pattern.search(rest)]
            for place, relative, receipt in found:
                same = place.endswith("\\" + said) if "\\" in said else place.rsplit("\\", 1)[-1] == said
                if same and all(any(s + "\\" in place for s in shows) for shows in places):
                    return [{"rule": "found", "said": _quote(answer, start, end),
                             "fact": f"{_told(receipt)}: su resultado muestra que encontró {relative}"}]
    return []


# ---- texts read -------------------------------------------------------------------------------------------------------
# «No leí X», «no pude leer X», «no he leído X», «no pude abrir X» (and «I couldn't read X»), and the file named right
# after it in its clause as what was not read: only an article or the word for a file or its text between them (not «el
# resto de X», «todo»: a part of it).
_NOT_READ = re.compile(r"\bno (?:(?:lo|la|los|las|le|se) )*(?:(?P<read>lei|he leido|(?:pude|logre) leer(?:lo|la)?)"
                       r"|(?P<open>(?:pude|logre) abrir(?:lo|la)?))\b"
                       r"|\bi (?:did not|didn['’]?t|could not|couldn['’]?t|have not|haven['’]?t|was not able to|"
                       r"wasn['’]?t able to|was unable to) (?:(?P<eread>read)|(?P<eopen>open))\b")
_READ_OBJECT = re.compile(r"(?:[\s«\"“']|\b(?:el|la|los|las|un|una|tu|su|tus|sus|archivo|fichero|documento|texto|"
                          r"contenido|de|del|the|file|your|document|text|of)\b)*")


def _read_whole(receipts: list[Receipt]) -> list[tuple[set[str], str, str, Receipt]]:
    """The files a completed read of the turn brought whole, as (their names and relative paths, lower case with
    backslashes; its place as ``found`` writes one: the known folder and the path the call gave; the name the result
    gives; the receipt): a non-empty text with nothing of it left unread."""
    whole = []
    for r in receipts:
        if not r.get("completed"):
            continue
        facts = _parsed(r)
        observed = facts.get("observed") if isinstance(facts.get("observed"), dict) else facts
        text = observed.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        if any(where.get("readInPart") is True or where.get("hasMore") is True or where.get("endReached") is False
               or (isinstance(where.get("unreadPages"), int) and where["unreadPages"] > 0)
               for where in (observed, facts)):
            continue
        arguments = r.get("arguments") or {}
        names = [observed.get(key) for key in ("reviewLabel", "name", "fileName", "relativePath")]
        # P2.4: the path the call gave, as the person said it, and its last part (the file's own name).
        given = arguments.get("path") or arguments.get("name")
        given = given.strip().replace("/", "\\").rstrip("\\") if isinstance(given, str) and given.strip() else None
        if given:
            names += [given, given.rsplit("\\", 1)[-1]]
        paths = {n.strip().replace("/", "\\").lower() for n in names if isinstance(n, str) and n.strip()}
        if paths:
            label = next((n for n in names if isinstance(n, str) and n.strip()), "")
            parts = [observed.get("folder") or arguments.get("folder"), given or label]
            place = "\\" + "\\".join(str(p).strip("\\/") for p in parts if isinstance(p, str) and p.strip())
            whole.append((paths, place.replace("/", "\\").lower(), str(observed.get("reviewLabel") or label), r))
    return whole


def _not_read_names(answer: str, folded: str, raw_folded: str, statements: list[tuple[int, int]],
                    receipts: list[Receipt]) -> list[dict]:
    """«No leí recado.txt» while a result of the turn read recado.txt whole (rule ``read``)."""
    whole = _read_whole(receipts)
    if not whole:
        return []
    # An open of the turn that did not complete is what «no pude abrir» may tell (file_open failed, file_read did not).
    open_failed = any(not r.get("completed") and _does("abrir", str(r.get("op")), bool(r.get("read"))) for r in receipts)
    for start, end in statements:
        for hit in _NOT_READ.finditer(folded, start, end):
            if (hit.group("open") or hit.group("eopen")) and open_failed:
                continue
            stop = next((m.start() for m in _CLAUSE_END.finditer(folded, hit.end(), end)), end)
            name = next(_FILE_NAME.finditer(raw_folded, hit.end(), stop), None)
            if name is None or not _READ_OBJECT.fullmatch(folded, hit.end(), name.start()):
                continue
            said = answer[name.start():name.end()].replace("/", "\\").lower()
            # A place named after it must hold the file read («no pude leer recado.txt de Descargas» of another one).
            rest = folded[name.end():stop]
            places = [shows for _, pattern, shows in _FOLDERS if pattern.search(rest)]
            for paths, place, label, receipt in whole:
                if not all(any(s + "\\" in place for s in shows) for shows in places):
                    continue
                if "\\" in said:
                    same = any("\\" in p and (p == said or p.endswith("\\" + said) or said.endswith("\\" + p))
                               for p in paths)
                else:
                    same = any(p.rsplit("\\", 1)[-1] == said for p in paths)
                if same:
                    return [{"rule": "read", "said": _quote(answer, start, end),
                             "fact": f"{_told(receipt)}: su resultado trae el texto entero de {label}"}]
    return []


# ---- denials (aid «check_denial») -------------------------------------------------------------------------------------
# A turn with no call whose answer says BAXY cannot do an act on the person's PC that a tool of the catalog does (V5E046
# «No puedo eliminar carpetas de BAXY-bench», 17 c3 runs; E027 / V6E052 «no puedo borrar archivos de la carpeta
# BAXY-bench, es mi carpeta de trabajo privada»; V5E040 «No tengo acceso a tu carpeta BAXY-bench»; V6E015 «No puedo leer
# el texto del bloc de notas»): nothing behind the claim. Read only when the act and its object are both said in the
# clause after the denial, the object is a thing of the PC that the tools reach (a file or a folder, a note, the text of a
# window), and an operation of the catalog does that act on it. Kept narrow: a false finding costs a regeneration.
_DENIAL = re.compile(
    r"\bno (?:(?:lo|la|los|las|le|les|te|me) )?(?:puedo|podria|soy capaz de|logro|me es posible|es posible|"
    r"tengo (?:como|forma de|manera de|la capacidad de|capacidad de|permiso para|permisos para|"
    r"herramientas? para|(?:una|ninguna) herramienta para))\b"
    r"|\bno (?:(?:lo|la|los|las) )?se (?:puede|pueden|permite)\b"
    r"|\bno tengo acceso\b"
    r"|\bi (?:can[’']?t|cannot|can not|am not able to|am unable to)\b|\bi[’']m (?:not able to|unable to)\b"
    r"|\bi (?:don[’']?t|do not) have (?:access|permission)\b|\bi have no access\b")
# F18 (uso-105): «No subo canciones a Spotify», «No instalo…», «I don't publish…»: a first person that denies an act with no
# «puedo» in it; only for the rule «denial_lookup» (a fact of what web_search reaches, and the model decides). Not the words in
# -o that are no verb of the speaker.
_DENIAL_ANY = re.compile(
    r"\bno (?:(?:lo|la|los|las|le|les|te|me) )?(?!solo\b|mucho\b|tanto\b|todo\b|poco\b|como\b|pero\b|creo\b|claro\b|"
    r"cierto\b|mismo\b|nuevo\b|caso\b|recuerdo\b)[a-z]{2,}o\b"
    r"|\bi (?:don[’']?t|do not) (?!know\b|think\b|remember\b|see\b)[a-z]+\b")
# The acts, folded (a Spanish infinitive with its clitics, an English base form). «acceso»: the denial is access itself.
_DENIED_ACTS = {
    "borrar": r"borrar|eliminar|suprimir|delete|remove|erase",
    "copiar": r"copiar|duplicar|hacer una copia|copy|duplicate",
    "mover": r"mover|trasladar|move",
    "leer": r"leer|read",
    "abrir": r"abrir|open",
    "contar": r"contar|count",
    "crear": r"crear|create|make",
    "escribir": r"escribir|editar|modificar|guardar|agregar|anadir|write|edit|modify|save|append",
    "buscar": r"buscar|encontrar|listar|search|find|list",
    "acceso": r"acceder|access",
    "enviar": r"enviar|mandar|send",
}
_DENIED_ACT = re.compile(r"(?:\s+(?:directamente|realmente|tampoco|aun|todavia|en|a|al|el|the|to|into))*\s*(?:"
                         + "|".join(f"(?P<{act}>(?:{verbs})(?:lo|la|los|las|le|les|te|me)?)"
                                    for act, verbs in _DENIED_ACTS.items()) + r")\b")
# The objects, by what reaches them: the text of a window, a file or a folder, a note. What names a window is data
# (window_words.v1.json: generic words and the applications whose window shows a text), never an application named in
# code (00_IDENTIDAD.md, aclaración 2026-10-10); an application whose name says «notas» is a window, not a note: a window
# found in the clause drops the note (_denials).
def _window_words() -> re.Pattern[str]:
    data = json.loads((pathlib.Path(__file__).with_name("data") / "window_words.v1.json").read_bytes())
    words = sorted({_fold(w).strip() for w in (*data["generic"], *data["applications"]) if w.strip()}, key=len,
                   reverse=True)
    return re.compile(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b")


_DENIED_OBJECTS = {
    "window": _window_words(),
    "file": re.compile(r"\b(?:archivos?|ficheros?|carpetas?|subcarpetas?|directorios?|documentos?|files?|folders?|"
                       r"director(?:y|ies)|escritorio|descargas|desktop|downloads)\b"
                       r"|[\w-]+\.(?:txt|md|docx?|xlsx?|pptx?|pdf|csv|json|png|jpe?g|zip|log)\b"),
    "note": re.compile(r"\b(?:notas?|notes?)\b"),
    "message": re.compile(r"\b(?:mensajes?|messages?)\b"),
}
# Which operations of the catalog do an act on an object: the first ones the catalog has are named, in this order.
DENIED_OPS: dict[tuple[str, str], tuple[str, ...]] = {
    ("borrar", "file"): ("filesystem.known.trash.named",),
    ("copiar", "file"): ("filesystem.sandbox.move.named",),
    ("mover", "file"): ("filesystem.sandbox.move.named",),
    ("leer", "file"): ("file.read",),
    ("abrir", "file"): ("file.open", "filesystem.folder.open"),
    ("contar", "file"): ("filesystem.explorer.count", "file.find"),
    ("crear", "file"): ("filesystem.create.directory", "file.write"),
    ("escribir", "file"): ("file.write", "file.edit"),
    ("buscar", "file"): ("file.find",),
    ("acceso", "file"): ("file.find", "file.read"),
    ("leer", "window"): ("input.visible.controls",),
    ("leer", "note"): ("note.read",),
    ("borrar", "note"): ("note.trash",),
    ("crear", "note"): ("note.create",),
    ("buscar", "note"): ("note.search",),
    ("escribir", "note"): ("note.update",),
    ("enviar", "message"): ("message.send", "message.draft"),
}
# What the sentence itself gives as a limit the tools have, or a refusal of policy: a confirmation, a protected window,
# a pending «sí», what is not installed or not found, a place outside the person's folders (a USB, the cloud, another PC,
# Windows' own folders), a kind of file the tools refuse (a program, an installer).
_REAL_LIMIT = re.compile(
    r"\b(?:confirm\w*|autoriz\w*|tu permiso|protegid\w*|bloquead\w*|por seguridad|hasta que|antes de que|sin que|"
    r"no (?:esta|estan|aparece|aparecen|existe|existen) (?:instalad\w*|en el catalogo)|no (?:lo |la )?encontre|"
    r"not installed|not found|usb|pendrive|disco externo|unidad|nube|cloud|onedrive|google drive|dropbox|icloud|"
    r"servidor|server|otro (?:pc|computador|ordenador|equipo)|celular|telefono|movil|phone|system32|"
    r"archivos de programa|program files|ejecutables?|executables?|instalador\w*|installers?|programas?|"
    # Revisión w11-rev4: a place outside the person's folders, as the rule says, and what the person asked BAXY not to
    # do («me pediste que no lo tocara»), which no earlier call of the session holds.
    r"fuera de|outside|me pediste|me dijiste|pediste que no|dijiste que no|you asked me|you told me)\b"
    r"|\.exe\b|\bc:\\windows")
_IF = re.compile(r"\b(?:si|if)\b")
# A condition after the denial («no puedo abrir el archivo si no me dices cuál», «sin un nombre»): no limit either.
_IF_AFTER = re.compile(r"\b(?:si|if|sin|unless|without|mientras no)\b")


def _first_sentence(description: str) -> str:
    sentence = re.split(r"(?<=[.!?])\s+(?=[A-Z¿«])", description.strip(), maxsplit=1)[0]
    return sentence if len(sentence) <= 400 else sentence[:400].rsplit(" ", 1)[0] + "…"


# ---- an output told ---------------------------------------------------------------------------------------------------
# A verb that tells an output, and the text quoted right after it in its clause (read on the answer with its quotes).
_OUTPUT = re.compile(r"\b(?:salio|salieron|imprimio|mostro|devolvio|arrojo|dio como resultado|printed|returned|output)\b"
                     r"[^«\"“.;!?\n]{0,25}[«\"“]([^»\"”\n]+)[»\"”]")


def _outputs(answer: str, raw_folded: str, statements: list[tuple[int, int]], receipts: list[Receipt]) -> list[dict]:
    """Rule ``output``: a quoted output that no result of the turn shows (not their arguments: what was written or sent
    is not what came out)."""
    if not receipts:
        return []
    shown = " ".join(_fold("\n".join(
        "\n".join(str(v) for _, v in _walk(facts) if isinstance(v, str)) if (facts := _parsed(r))
        else str(r.get("observation") or "") for r in receipts)).split())
    findings: list[dict] = []
    for start, end in statements:
        for hit in _OUTPUT.finditer(raw_folded, start, end):
            quoted = " ".join(hit.group(1).split()).strip(" .,;:!¡")
            if len(quoted) < 2 or quoted in shown or _negated(raw_folded, start, hit.start(), answer):
                continue
            findings.append({"rule": "output", "said": _quote(answer, _clause_start(raw_folded, start, hit.start()), end),
                             "fact": f"ningún resultado de este turno muestra «{answer[hit.start(1):hit.end(1)].strip()}»; "
                                     f"en este turno: {'; '.join(_told(r) for r in receipts[-3:])}"})
            break
    return findings


# ---- a number only the OCR of a window gives --------------------------------------------------------------------------
_NUMBER = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)*(?![\w])")
# A look's «Controles» entries; a window drawn without controls (one at most) has only its OCR, as the App says.
_CONTROL_LINE = re.compile(r"^\[\d+\] ", re.MULTILINE)
# What the view itself numbers (a control's index, the window's handle, how many were cut): never a number it shows.
_VIEW_BOOKKEEPING = re.compile(r"^\[\d+\] |\[\d+\]|\bwindow \d+|\(\+\d+ más|faltan \d+ caracteres|^\(\d+ líneas", re.MULTILINE)
# A view that says its list is not whole: a number missing from its controls may be in one it did not list.
_NOT_WHOLE = re.compile(r"no es la lista completa|\(\+\d+ más|la lectura quedó incompleta|nombre cortado")


def _number_forms(token: str) -> set[str]:
    """«8,9» and «8.9» are one number, and «12.490» and «12490» another: the forms a number is compared in."""
    return {token, token.replace(",", "."), token.replace(".", "").replace(",", "")}


def _recognized_numbers(answer: str, text: str, folded: str, statements: list[tuple[int, int]],
                        receipts: list[Receipt], request: str) -> list[dict]:
    """Rule ``recognized_number``: a number of the answer (outside quotes and negated clauses) that a look of the turn
    (input_visible_controls) gives only in its «Texto» lines, read by OCR, while the window gave its controls (two or
    more, the list whole) and neither they, nor any other result of the turn, nor the person's words give it.
    Windows.Media.Ocr has no confidence (OcrLine, OcrWord: Text and box only) and misreads a decimal comma as a digit
    (uso-89, R06: «829» for the page's «8,9»)."""
    looks = [r for r in receipts if r.get("completed") and _matches(r.get("op", ""), ("input.visible.controls",))]
    if not looks:
        return []
    ocr_numbers: dict[str, Receipt] = {}
    elsewhere: set[str] = set()
    for receipt in receipts:
        facts = _parsed(receipt)
        view = facts.get("view") if receipt in looks else None
        if isinstance(view, str) and len(_CONTROL_LINE.findall(view)) >= 2 and not _NOT_WHOLE.search(view):
            for line in _VIEW_BOOKKEEPING.sub(" ", view).splitlines():
                numbers = {form for token in _NUMBER.findall(line) for form in _number_forms(token)}
                if line.startswith("Texto "):
                    for form in numbers:
                        ocr_numbers.setdefault(form, receipt)
                else:
                    elsewhere |= numbers
            rest = {k: v for k, v in facts.items() if k != "view"}
        else:
            rest = facts or receipt.get("observation") or ""
        elsewhere |= {form for _, value in _walk(rest) for token in _NUMBER.findall(str(value))
                      for form in _number_forms(token)}
    elsewhere |= {form for token in _NUMBER.findall(request or "") for form in _number_forms(token)}
    for start, end in statements:
        for hit in _NUMBER.finditer(text, start, end):
            token = hit.group(0)
            forms = _number_forms(token)
            look = next((ocr_numbers[f] for f in forms if f in ocr_numbers), None)
            if look and forms.isdisjoint(elsewhere) and not _negated(folded, start, hit.start(), text):
                return [{"rule": "recognized_number", "said": _quote(answer, start, end),
                         "fact": f"{_told(look)}: «{token}» sale sólo de su texto reconocido de la imagen (OCR), que "
                                 "puede leer mal cifras y comas; ni sus controles ni otro resultado lo dicen"}]
    return []


# ---- a number nobody gave, told as the result of a calculation ----------------------------------------------------------
_NUMBER_IN_TEXT = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)*")


def _readings(token: str) -> set[float]:
    """Every value a number as a text writes it can be: its separators all of thousands («3.670»), or its last one a
    decimal point («55,56»)."""
    digits = token.replace(",", ".")
    head, separator, tail = digits.rpartition(".")
    values = {float(token.replace(".", "").replace(",", ""))}
    if separator:
        values.add(float(head.replace(".", "") + "." + tail))
    return values


def _unsourced_told(answer: str, folded: str, statements: list[tuple[int, int]],
                    unsourced: list[dict[str, Any]] | None) -> list[dict]:
    """Rule ``unsourced_number`` (encargo A2; HP3 «abre la calculadora y dime cuánto son 50.000 pesos en dólares»): a
    statement that tells a number of a calculation's expression that nobody gave (the mind found it when the result
    came: not the person's words nor a result of any tool), or the value that expression gave, within a percent of the
    figure said. Only forms are compared: whether that number is a rate that changes is the model's to say."""
    for entry in unsourced or []:
        wanted = {float(n) for n in entry.get("numbers") or [] if n}
        try:
            value = float(entry["value"]) if entry.get("value") else None
        except ValueError:
            value = None
        for start, end in statements:
            for hit in _NUMBER_IN_TEXT.finditer(folded, start, end):
                for read in _readings(hit.group()):
                    if read in wanted or (value and abs(value) > 1 and abs(read - value) <= abs(value) * 0.01):
                        numbers = ", ".join(entry["numbers"])
                        return [{"rule": "unsourced_number", "said": _quote(answer, start, end),
                                 "fact": f"{numbers} de la cuenta de la Calculadora no lo dijo la persona ni salió de ningún "
                                         "resultado de herramienta: si es una tasa, un precio o una cotización que "
                                         "cambia con los días, la cifra no es un cálculo hasta tener el dato real"}]
    return []


# ---- a date after today told in the past ------------------------------------------------------------------------------
_MONTHS = {name: number for number, names in enumerate((
    ("enero", "january"), ("febrero", "february"), ("marzo", "march"), ("abril", "april"), ("mayo", "may"), ("junio", "june"),
    ("julio", "july"), ("agosto", "august"), ("septiembre", "setiembre", "september"), ("octubre", "october"),
    ("noviembre", "november"), ("diciembre", "december")), start=1) for name in names}
_MONTH = "|".join(_MONTHS)
_DATE = re.compile(rf"\b(?P<day>\d{{1,2}}) de (?P<month>{_MONTH})(?: (?:de|del) (?P<year>\d{{4}}))?\b"
                   rf"|\b(?P<month2>{_MONTH}) (?:de |del )?(?P<year2>\d{{4}})\b"
                   r"|\b(?P<day3>\d{1,2})[/-](?P<month3>\d{1,2})[/-](?P<year3>\d{4})\b"
                   r"|(?<=\ben )(?P<year4>\d{4})\b")
# The same day as a result may write it, for the year a date of the answer leaves out.
_DAY_WITH_YEAR = re.compile(rf"\b(?P<day>\d{{1,2}}) de (?P<month>{_MONTH}) (?:de|del) (?P<year>\d{{4}})\b"
                            rf"|\b(?P<month2>{_MONTH}) (?P<day2>\d{{1,2}}),? (?P<year2>\d{{4}})\b")
# The past by its form alone: a Spanish preterite or a perfect, whatever the verb.
_PAST_FORM = re.compile(r"(?<!\w)(?:\w+ó|\w+(?:aron|ieron|yeron)|fue|fueron|han? \w+(?:ado|ido))(?!\w)", re.IGNORECASE)
# What puts a date out of the verb's reach: a clause of its own, or the end a change aims at.
_NOT_THE_VERBS = re.compile(r"\b(?:que|hasta|para|al|a|desde)(?: el| la)?(?: dia)?\s*$")


def _date_of(hit: re.Match[str], results: str) -> dt.date | None:
    """The first day a date of the answer can mean. A day with no year takes it from a result that brings that day; none
    does, and it is not known. Not a date: None."""
    try:
        if hit.group("year4"):
            return dt.date(int(hit.group("year4")), 1, 1)
        if hit.group("year2"):
            return dt.date(int(hit.group("year2")), _MONTHS[hit.group("month2")], 1)
        if hit.group("year3"):
            return dt.date(int(hit.group("year3")), int(hit.group("month3")), int(hit.group("day3")))
        day, month = int(hit.group("day")), _MONTHS[hit.group("month")]
        if hit.group("year"):
            return dt.date(int(hit.group("year")), month, day)
        for shown in _DAY_WITH_YEAR.finditer(results):
            if (int(shown.group("day") or shown.group("day2")),
                    _MONTHS[shown.group("month") or shown.group("month2")]) == (day, month):
                return dt.date(int(shown.group("year") or shown.group("year2")), month, day)
    except ValueError:  # 31/02: not a date
        pass
    return None


def _future_past(answer: str, text: str, folded: str, statements: list[tuple[int, int]], receipts: list[Receipt],
                 today: dt.date | None) -> list[dict]:
    """Rule ``future_past``: a statement of a turn with a completed result that tells, with a verb in the past in the same
    clause, a date that has not come yet. Not when the clause denies it or says «si», nor when the verb reaches the
    date only through «que», «hasta», «para», «al»…: another clause tells the date, or the date is what a change aims at."""
    done = [r for r in receipts if r.get("completed")]
    if today is None or not done:
        return []
    results = _fold(" ".join(str(r.get("observation") or "") for r in done))
    for start, end in statements:
        for hit in _DATE.finditer(folded, start, end):
            date = _date_of(hit, results)
            if date is None or date <= today:
                continue
            clause = _clause_start(folded, start, hit.start())
            after = _CLAUSE_END.search(folded, hit.end(), end)
            before = text[clause:hit.start()]
            past = list(_PAST_FORM.finditer(before))
            told = bool(past) and not _NOT_THE_VERBS.search(_fold(before)) and not re.search(
                r"\bque\b", _fold(before[past[-1].end():]))
            # The date first: «El 20 de diciembre de 2026 se estrenó…».
            told = told or bool(not past and not _fold(before).strip(" ,el") and _PAST_FORM.search(
                text, hit.end(), after.start() if after else end))
            if told and not _negated(folded, start, hit.start(), text):
                return [{"rule": "future_past", "said": _quote(answer, clause, after.start() if after else end),
                         "fact": f"hoy es {today.strftime('%d/%m/%Y')}: esa fecha todavía no llega y lo que trae aún no "
                                 "ocurrió"}]
    return []


# ---- a weekday told of a date that falls on another --------------------------------------------------------------------
_WEEKDAYS = {name: number for number, names in enumerate((
    ("lunes", "monday"), ("martes", "tuesday"), ("miercoles", "wednesday"), ("jueves", "thursday"), ("viernes", "friday"),
    ("sabado", "saturday"), ("domingo", "sunday"))) for name in names}
_WEEKDAY = "|".join(_WEEKDAYS)
_WEEKDAY_SAID = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MONTH_SAID = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre",
               "diciembre")
# The weekday right before its date. A bare day («viernes 12») only where the number ends there: not a time («12:30»,
# «12 h»), an amount («12 %», «12 personas») nor a longer number.
_WEEKDAY_THEN_DATE = re.compile(
    rf"\b(?P<weekday>{_WEEKDAY}),? (?:el |the )?(?:dia )?(?:"
    rf"(?P<day>\d{{1,2}})(?: de (?P<month>{_MONTH})(?: (?:de|del) (?P<year>\d{{4}}))?|(?=\s*(?:$|[.,;!?)»\"*])))"
    rf"|(?P<month2>{_MONTH}) (?P<day2>\d{{1,2}})(?:st|nd|rd|th)?(?:,? (?P<year2>\d{{4}}))?)(?![\d:%])")
# The date first, then the weekday as what it is, with no number, sentence end nor other clause between them.
_DATE_THEN_WEEKDAY = re.compile(
    rf"\b(?:(?P<day>\d{{1,2}}) de (?P<month>{_MONTH})(?: (?:de|del) (?P<year>\d{{4}}))?"
    rf"|(?P<month2>{_MONTH}) (?P<day2>\d{{1,2}})(?:st|nd|rd|th)?(?:,? (?P<year2>\d{{4}}))?)"
    rf"(?P<between>[^.;:!?\d]{{1,40}}?)\b(?P<weekday>{_WEEKDAY})\b")
_BETWEEN_BREAK = re.compile(r"\b(?:pero|aunque|y|o|porque|mientras|luego|despues|entonces|no|ni|but|and|or|not)\b")


def _date_candidates(hit: re.Match[str], today: dt.date) -> tuple[list[dt.date], tuple[int | None, int]]:
    """The days a date of the answer can be, and its (month, day): its own with a year; with a month and no year, the
    nearest one to today (the last or the coming one: «el 18 de septiembre» in November is this year's); with no month,
    that day of last month, this one and the next. Not a date: none."""
    day = int(hit.group("day") or hit.group("day2"))
    month_name = hit.group("month") or hit.group("month2")
    year = hit.group("year") or hit.group("year2")
    found: list[dt.date] = []
    if month_name:
        month = _MONTHS[month_name]
        for y in ([int(year)] if year else range(today.year - 8, today.year + 9)):
            try:
                found.append(dt.date(y, month, day))
            except ValueError:  # 31/02, or a 29/02 of a common year: not a date
                pass
        if not year and found:
            least = min(abs((d - today).days) for d in found)
            found = [d for d in found if abs((d - today).days) == least]
        return found, (month, day)
    first = today.replace(day=1)
    for start in ((first - dt.timedelta(days=1)).replace(day=1), first, (first + dt.timedelta(days=32)).replace(day=1)):
        try:
            found.append(start.replace(day=day))
        except ValueError:
            pass
    return found, (None, day)


_ISO_DAY = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def _weekday_date(answer: str, folded: str, statements: list[tuple[int, int]], receipts: list[Receipt], request: str,
                  today: dt.date | None) -> list[dict]:
    """Rules ``weekday_date`` and ``unread_date``, over a weekday told with its date. ``weekday_date``: the calendar puts
    that date on another weekday, in every year (or month) the date can mean; the fact is the weekday of the nearest of
    those days to today. ``unread_date``: the calendar has the pair, it is not today's, and nothing of the turn gave
    that date. Nothing is read of what was asked."""
    if today is None:
        return []
    given = _fold(request + " " + " ".join(
        str(r.get("observation") or "") + " " + json.dumps(ensure_ascii=False, obj=r.get("arguments") or {}) for r in receipts))
    shown = []
    for y, m, d in _ISO_DAY.findall(given):
        try:
            shown.append(dt.date(int(y), int(m), int(d)))
        except ValueError:
            pass
    unread: list[dict] = []
    for start, end in statements:
        for pattern in (_WEEKDAY_THEN_DATE, _DATE_THEN_WEEKDAY):
            for hit in pattern.finditer(folded, start, end):
                if "between" in hit.groupdict() and _BETWEEN_BREAK.search(hit.group("between")):
                    continue
                said = _WEEKDAYS[hit.group("weekday")]
                days, (month, day) = _date_candidates(hit, today)
                # The person's own words or a result that bring the pair as it is are theirs to be wrong; and a date a
                # result gives (system.time's calendar: «2025-11-27») that is that day on that weekday backs it.
                if not days or hit.group(0) in given:
                    continue
                if any(d.weekday() == said for d in shown if d.day == day and month in (None, d.month)):
                    continue
                meant = [d for d in days if d.weekday() == said]
                if not meant:
                    near = min(days, key=lambda d: abs((d - today).days))
                    return [{"rule": "weekday_date", "said": _quote(answer, hit.start(), hit.end()),
                             "fact": f"el {near.day} de {_MONTH_SAID[near.month - 1]} de {near.year} es "
                                     f"{_WEEKDAY_SAID[near.weekday()]}, no {_WEEKDAY_SAID[said]}"}]
                # The calendar has it. Today's own is the clock line's; a date a result or the person wrote without its
                # weekday («28 de noviembre», «November 28») is given too.
                names = [(d, name) for d in meant for name, number in _MONTHS.items() if number == d.month]
                written = [f"{d.day} de {name}" for d, name in names] + [f"{name} {d.day}" for d, name in names]
                if today in meant or any(re.search(rf"\b{re.escape(w)}\b", given) for w in written):
                    continue
                # Within a year of today: a date of history told with its weekday is not one counted from the clock.
                if min(abs((d - today).days) for d in meant) > 366:
                    continue
                if not unread:
                    unread = [{"rule": "unread_date", "said": _quote(answer, hit.start(), hit.end()),
                               "fact": "esa fecha no la dio ningún resultado de este turno ni la dijo la persona: la contaste tú"}]
    return unread


# ---- a date before today told as coming ---------------------------------------------------------------------------------
# What comes by its form alone: a Spanish future («se jugará», «será»), «va a …», or the date named the next one.
_FUTURE_FORM = re.compile(r"(?<!\w)(?:\w+(?:ará|erá|irá|arán|erán|irán)|será|serán|va a \w+|van a \w+|próxim[oa]s?"
                          r"|will(?: be)?|next|upcoming)(?!\w)", re.IGNORECASE)


def _last_day_of(hit: re.Match[str], results: str) -> dt.date | None:
    """The last day a date of the answer can mean: its own day, the last of its month or of its year."""
    first = _date_of(hit, results)
    if first is None:
        return None
    if hit.group("year4"):
        return dt.date(first.year, 12, 31)
    if hit.group("year2"):
        return (first.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
    return first


def _past_future(answer: str, text: str, folded: str, statements: list[tuple[int, int]], receipts: list[Receipt],
                 today: dt.date | None) -> list[dict]:
    """Rule ``past_future``: a statement of a turn with a completed result that tells as coming a date that is wholly
    before today: a future form before the date in its clause, or the date first and the future after it."""
    done = [r for r in receipts if r.get("completed")]
    if today is None or not done:
        return []
    results = _fold(" ".join(str(r.get("observation") or "") for r in done))
    for start, end in statements:
        if text[start:end].rstrip().endswith("?"):
            continue
        for hit in _DATE.finditer(folded, start, end):
            date = _last_day_of(hit, results)
            if date is None or date >= today:
                continue
            clause = _clause_start(folded, start, hit.start())
            after = _CLAUSE_END.search(folded, hit.end(), end)
            before = text[clause:hit.start()]
            told = bool(_FUTURE_FORM.search(before)) and not _PAST_FORM.search(before)
            # The date first: «El 27 de octubre de 2026 se jugará la final».
            told = told or bool(not _fold(before).strip(" ,el") and _FUTURE_FORM.search(
                text, hit.end(), after.start() if after else end))
            # «para» belongs here («programada para el 27»): only a denial or a condition turn the claim off; «sí» is
            # neither (its accent is still in ``before``).
            if told and not re.search(r"\b(?:no|nunca|tampoco|ni|jamas|si)\b", _fold(re.sub(r"\bsí\b", " ", before, flags=re.I))):
                return [{"rule": "past_future", "said": _quote(answer, clause, after.start() if after else end),
                         "fact": f"hoy es {today.isoformat()}: esa fecha ya pasó, no es la que viene"}]
    return []


# ---- a page that failed to open, searched for, and never opened -------------------------------------------------------
def _address_key(address: Any) -> str:
    return str(address or "").strip().rstrip("/").lower()


def _bare_address(address: Any) -> str:
    """An address as a person says it: no scheme, no «www.», no last «/»."""
    return re.sub(r"^(?:https?://)?(?:www\.)?", "", _address_key(address))


def _unopened_page(answer: str, receipts: list[Receipt], wire_of: Callable[[str], str] = plain,
                   request: str = "") -> list[dict]:
    """Rule ``unopened_page``: the turn's last failed ``browser.navigate*`` was followed by a search that found something to
    open (results, or the ``searchPageUrl`` to read them in), and after that failure no call opened another page: no
    navigation to an address that is not such a search page (any outcome: one that went unconfirmed was still a try) and
    no ``input.visible.click`` (a result opened by its link). Only typed facts of the receipts; the model decides."""
    failed_at = None
    for index, receipt in enumerate(receipts):
        op = operation_of(str(receipt.get("op") or ""))
        if (op.startswith("browser.navigate") and not receipt.get("completed")
                and _parsed(receipt).get("status") == "failed"):
            failed_at = index
    if failed_at is None:
        return []
    search_pages: set[str] = set()
    searched = found = False
    for receipt in receipts[failed_at + 1:]:
        op = operation_of(str(receipt.get("op") or ""))
        if op == "web.search":
            searched = True
            facts = _parsed(receipt)
            page = (facts.get("observed") or {}).get("searchPageUrl")
            if page:
                search_pages.add(_address_key(page))
            # INT10: a search with something to open, its results or a page to read them in. Since srch1 a refused one
            # gives neither (WebSearchRefused: no next, no searchPageUrl), nor does one the engine answered with nothing.
            found = found or bool(page) or facts.get("status") == "completed"
        elif op == "input.visible.click":
            return []
        elif op.startswith("browser.navigate"):
            if _address_key((receipt.get("arguments") or {}).get("url")) not in search_pages:
                return []
    if searched and not found:
        return []  # nothing was found to open: «I could not find it» leaves no page unopened
    failed = receipts[failed_at]
    facts = _parsed(failed)
    url = (failed.get("arguments") or {}).get("url") or (facts.get("observed") or {}).get("requestedUrl") or ""
    call = f"{failed.get('tool') or wire_of('browser.navigate')} {json.dumps({'url': url}, ensure_ascii=False)}"
    told = f"{call} no abrió la página ({facts.get('error') or failed.get('outcome') or 'falló'})"
    if not searched and any(operation_of(str(r.get("op") or "")) == "web.search" for r in receipts[:failed_at]):
        return []  # a result it searched for and tried: the search was made
    if not searched and ((facts.get("observed") or {}).get("httpStatus") != 404
                         or _bare_address(url) in (request or "").lower()):
        # Only a page its site says does not exist: a navigation left unconfirmed may have opened (F25, F24), and a host
        # with no address has its own next (encargo 82). And not the address the person said themselves: its 404 is what
        # they asked (controls A10-K404, e35-K-U31).
        return []
    if not searched:
        # Held-out uso-105: 404 and «Netflix no tiene esa página», with the search its next offered never made.
        return [{"rule": "unopened_page", "said": _quote(answer, 0, len(answer)), "unsearched": True,
                 "fact": f"{told}, y en este turno no se buscó su dirección real"}]
    return [{"rule": "unopened_page", "said": _quote(answer, 0, len(answer)),
             "fact": f"{told}, después se buscó, y ninguna llamada de este turno abrió otra página que la de resultados de "
                     "la búsqueda"}]


# ---- a look at the person's own things that found nothing, and nothing else looked at ---------------------------------
def _empty_lookup(answer: str, receipts: list[Receipt], wire_of: Callable[[str], str] = plain) -> list[dict]:
    """Rule ``empty_lookup`` (cosecha 04-11 F13, F35): the turn's last call read what BAXY keeps or what this PC has, found
    nothing of it, and no search ran in the turn. The fact is only how far that look reaches; the model reads what the person
    asked. «¿Sabes algo de X?» → memory_recall → «no tengo nada guardado»; «¿conoces el juego X?» → game_installed_named →
    «no lo veo instalado»."""
    if not receipts or any(operation_of(str(r.get("op") or "")) == "web.search" for r in receipts):
        return []
    last = receipts[-1]
    op, facts = operation_of(str(last.get("op") or "")), _parsed(last)
    observed = facts.get("observed") if isinstance(facts.get("observed"), dict) else {}
    tool = last.get("tool") or wire_of(op)
    if op == "memory.recall" and facts.get("error") == "memory_none":
        fact = f"{tool} sólo lee lo que la persona le contó a BAXY, y no trae nada de eso; no dice nada de lo que hay en internet"
    elif op == "game.installed.named" and observed.get("state") == "no_steam_or_epic_manifest_with_that_name":
        fact = f"{tool} sólo lee lo que hay en este PC, y no lo tiene con ese nombre; no dice nada del juego"
    else:
        return []
    return [{"rule": "empty_lookup", "said": _quote(answer, 0, len(answer)), "fact": fact}]


# ---- something of the person told as remembered that no memory read backs ---------------------------------------------
# A datum told as remembered or known, in any person: «recuerdo que», «te acuerdas que» (VIVOM1: «Sí, te acuerdas que tu
# color favorito es el azul», 5 of 6 live), «recordás», «me acuerdo», «te acordé», «sé que», «ya sabes que», «I remember»,
# «you remember», «I know». Only of the person (``_PERSON``): «recuerdo que se hace con huevo» is not of them.
_REMEMBERED = re.compile(
    r"\b(?:(?:lo |la |te )?(?:recuerdo|recuerdas|recorde|recordaste|recordas)|(?:me|te) (?:acuerdo|acuerdas|acordas|"
    r"acorde|acordaste)|i (?:remember|recall)|you remember)\b")
# REG1 (REV11 C-2): «sé que / ya sabes que / I know / you know» are also said of nothing kept («Sé que te puede resultar
# confuso, pero…», «I know you are busy», «You know, the best laptop…»): they tell a datum of the person only when one of
# theirs begins what they know («sé que tu color favorito…», «I know your…»), never by a «te / you» of the clause.
_KNOWN = re.compile(r"\b(?:(?:ya )?(?:se|sabes|sabias) que|i know|you know)\b")
_KNOWN_THEIRS = re.compile(r"\s*(?:that\s+)?(?:(?:ya|a|de)\s+)?(?:tu|tus|tuyo|tuya|tuyos|tuyas|your|yours)\b")
# A datum told as told before or kept: «me dijiste / me contaste», «lo tengo guardado», «según mi memoria», «you told me»:
# of what the person said, whatever it is of.
_TOLD = re.compile(
    r"\b(?:(?:lo |la |los |las )?tengo (?:guardad|anotad|registrad)[oa]s?|"
    r"tengo en (?:mi |la )?memoria|(?:mi|la) memoria (?:dice|tiene|guarda|muestra|indica)|segun (?:mi|la) memoria|"
    r"me (?:dijiste|contaste|comentaste|mencionaste|habias dicho|habias contado|has dicho|has contado)|"
    r"i have (?:it )?(?:saved|stored)|you (?:told|mentioned)|my memory (?:says|has|shows))\b")
# The same memory said not to hold it: «no tengo guardado / no lo tengo en mi memoria / mi memoria no guarda / no tengo
# registro» (VIVO11, «No tengo guardado ese dato» with it kept, and MEM1's base 3 of 48). Only words of the memory's
# content: a bare «no recuerdo» may be of anything.
_NOT_KEPT = re.compile(
    r"\b(?:no (?:lo |la |los |las )?tengo (?:(?:eso|esa informacion|ese dato|nada|registro)(?: de [^.,;]*?)? )?"
    r"(?:guardad|anotad|registrad)[oa]s?|no (?:lo |la )?tengo (?:nada )?en (?:mi|la) memoria|"
    r"(?:mi|la) memoria no (?:guarda|tiene|dice|muestra)|no tengo (?:ningun )?registro(?=(?: de [^.,;:]*?)? en (?:mi|la) memoria)|"
    r"i (?:don'?t|do not) have (?:that|it|anything)(?: [a-z]+)? (?:saved|stored))\b")
# REG1 (REV11 C-2): a bare «no tengo registro» is of any record («No tengo registro de tus llamadas: no veo el teléfono»):
# it is of the memory only answering a question of theirs (mi, my: «¿Cuándo es mi cumpleaños?» → «No tengo registro de tu
# cumpleaños», MEM1/MEM2 bench rows), or said of the memory (``_NOT_KEPT``).
_NO_RECORD = re.compile(r"\bno tengo (?:ningun )?registro\b")
# Whose the datum is, by its grammar: the answer says it of the person (tu, tus, te, ti, your, you) or the person asked it
# of theirs (mi, mis, my). «¿Recuerdas cómo se hace una tortilla?» → «No tengo esa información guardada» has neither: it is
# a question of the world (VIVOM1: told to read the memory, 2 of 2 without the recipe the base gave).
_PERSON = re.compile(r"\b(?:tu|tus|te|ti|tuyo|tuya|tuyos|tuyas|vos|usted|your|yours|you)\b")
_THEIRS = re.compile(r"\b(?:mi|mis|mio|mia|mios|mias|my|mine)\b")
# A question of BAXY remembering or knowing: «¿te acuerdas…?», «¿sabés…?», «do you remember…?».
_ASKED_KNOWN = re.compile(r"\b(?:recuerdas|recordas|te acuerdas|te acordas|sabes|sabias|you (?:remember|recall|know))\b")
_POSSESSIVE = re.compile(r"\b(?:tu|tus|tuyo|tuya|tuyos|tuyas|your|yours)\b")
# Where the clause of a claim ends: «No tengo guardado ese dato en mi memoria, pero te cuento: se marinan…» (MEM2 held-out
# K08) says nothing of the person; the «te» is of the next clause.
_CUT = re.compile(r"[,;]|\b(?:pero|aunque|porque|mientras|sino|but|although)\b")


def _own_clause(folded: str, start: int, end: int, at: int, to: int) -> str:
    """The clause of a claim found at ``at``-``to`` within its statement, the claim itself blanked."""
    cut = _CUT.search(folded, to, end)
    begin = _clause_start(folded, start, at)
    return folded[begin:at] + " " * (to - at) + folded[to:cut.start() if cut else end]
# Of whom a record is, by its own name: «color favorito de mi hija», «jefe de mi hermano», «my sister's birthday».
_OF = re.compile(r"\b(?:de|del|of)\s+(?P<whose>.+)$|^(?P<owner>.+?)['’]s\b")
_WORD = re.compile(r"[a-z0-9]+")
# Words that tell no datum by themselves: what is left of a statement without them is what it tells.
_FILLER = {"de", "del", "la", "el", "los", "las", "lo", "le", "mi", "mis", "my", "the", "a", "an", "of", "su", "sus", "un",
           "una", "uno", "que", "con", "por", "para", "and", "that", "you", "your", "tus", "esa", "ese", "eso", "esta",
           "este", "esto", "como", "pero", "muy", "mas", "has", "have", "was", "are", "is", "es", "son", "al", "en", "y"}


def _stems(text: str) -> set[str]:
    """The words of a folded text of three letters or more (and every number), each by its first five letters, without
    ``_FILLER``: «favorita» is «favorito», «cumple» is «cumpleaños»."""
    return {w[:5] for w in _WORD.findall(text) if (len(w) >= 3 or w.isdigit()) and w not in _FILLER}


def _memory_values(receipts: list[Receipt]) -> tuple[bool, list[tuple[str, str]], bool]:
    """What this turn's memory calls brought: whether one completed, the (label, value) of each record they bring or keep
    (folded), and whether one completed whose body is not known (then what it brought is not known either)."""
    completed, records, unknown = False, [], False
    for receipt in receipts:
        if not str(receipt.get("op") or "").startswith("memory.") or not receipt.get("completed"):
            continue
        completed = True
        arguments = receipt.get("arguments") if isinstance(receipt.get("arguments"), dict) else {}
        if receipt.get("op") in ("memory.save", "memory.sensitive.save", "memory.correct") and arguments.get("value"):
            records.append((_fold(str(arguments.get("selector") or "")), _fold(str(arguments["value"]))))
        observed = _parsed(receipt).get("observed")
        found = observed.get("records") if isinstance(observed, dict) else None
        if isinstance(found, list):
            records.extend((_fold(str(r.get("label") or "")), _fold(str(r.get("value") or "")))
                           for r in found if isinstance(r, dict))
        elif receipt.get("observation") is None:
            unknown = True
    return completed, records, unknown


# MEM4 (REM7 D-1): with the memory switched off and 4 records kept, «¿qué tienes guardado de mí?» → «No tengo nada
# guardado de ti porque la memoria está apagada» 23 of 30 (bench, Esencial and Completo; 1.3.1 18, 1.4.2 19-21). Off, the
# store keeps its records and nothing reads them (MemoryHandlers: memory_disabled), so a claim that nothing is kept of the
# person has no read behind it. A shape: a denial («no», «nada», «don't») of having, keeping, remembering or knowing
# something of the person (``_PERSON``, or the person asked of theirs) in one clause, and no memory read that completed. «No puedo leer lo que tengo
# guardado» denies the reading, not the records: not this shape. REM8 (REV16 M-1): nor a doubt, what MEMORY_OFF_FACT asks
# for: «no sé si / qué tengo guardado», «no hay forma de saber si…», «I don't know whether / what…» say no «no hay».
_NOTHING_KEPT = re.compile(
    r"\b(?:(?:no (?:lo |la |los |las )?(?:tengo|hay|guardo|recuerdo|se|conozco)\b|i (?:don'?t|do not) (?:have|remember|know)\b)"
    r"(?! (?:que|cual|cuant|what|which)\b)"
    r"(?:(?!\b(?:puedo|leer|ver|acceder|acceso|can'?t|cannot|read|see|access|si|saber|whether|if)\b)[^.;:?!])*?"
    r"\b(?:nada|ningun[oa]?|informacion|datos?|recuerdos?|registros?|anything|nothing|information|records?|memories"
    r"|guardad|anotad|almacenad)"
    r"|nada (?:esta |se |hay |tengo )?(?:guardad|anotad|registrad|almacenad)|nothing (?:is )?(?:saved|stored|kept))")
# REM8 (REV16 M-2): what makes a denial one of what is kept: kept or remembered by its own word, or of the person whole
# («nada de ti», «información sobre vos», «ningún dato tuyo»); «ningún correo tuyo» or «ningún archivo» is another tool's.
_OF_KEPT = re.compile(
    r"\b(?:guardad|anotad|almacenad|recuerd|memori|saved|stored|kept|remember|memor)"
    r"|\b(?:de|sobre|acerca de|about|of) (?:ti|vos|usted|you)\b"
    r"|\b(?:nada|informacion|datos?|recuerdos?|anything|nothing|information) (?:tuy|de los tuy|about you)")
MEMORY_OFF_FACT = ("la memoria de BAXY está apagada en este PC y lo que guarda no se lee mientras esté apagada: puede tener "
                   "recuerdos de la persona de antes, y no sabes si los hay ni cuáles; dilo así, sin decir que no hay nada, "
                   "y si quiere saberlo, ofrece encenderla")


def _memory_off_empty(folded: str, text: str, statements: list[tuple[int, int]], receipts: list[Receipt],
                      session: list[Call] | None, request: str) -> list[dict]:
    """Rule ``memory_off_empty``: with the memory off, a statement says nothing is kept of the person (by its grammar, or
    the person asked of theirs, as ``unread_memory`` reads it) while no memory read completed in the conversation
    (``session``) nor in the turn. With ``session`` None a read may have been earlier: nothing is said (REM8, REV16 M-3:
    the turn's read was looked for as ``outcome == "completed"``, which the mind never writes; «completed» is the flag)."""
    reads = ("memory.recall", "memory.list")
    if session is None or any(op in reads and done for op, done, _ in session) or any(
            r.get("op") in reads and r.get("completed") for r in receipts):
        return []
    # REM8 (REV16 M-2; puerta INT33K u121-B10): off is how the memory is born, and «no hay ningún archivo con tu
    # currículum» after files.search, or «no tengo ningún correo tuyo» after reading the mail, were struck: a completed
    # read of another tool in the turn backs its «no hay», and only a denial of what is kept is this shape.
    if any(r.get("completed") and r.get("read") and not str(r.get("op") or "").startswith("memory.") for r in receipts):
        return []
    theirs = bool(_THEIRS.search(_fold(request or "")))
    for start, end in statements:
        hit = _NOTHING_KEPT.search(folded, start, end)
        if hit and _OF_KEPT.search(folded, _clause_start(folded, start, hit.start()), end) and (
                theirs or _PERSON.search(folded, hit.start(), end)):
            return [{"rule": "memory_off_empty", "said": _quote(text, _clause_start(folded, start, hit.start()), end),
                     "fact": MEMORY_OFF_FACT}]
    return []


def _unread_memory(folded: str, text: str, statements: list[tuple[int, int]], receipts: list[Receipt],
                   session: list[Call] | None, memory: str | None, request: str) -> list[dict]:
    """Rules of the person's memory (MEM1, VIVO12 P1; MEM2, VIVOM1), read only in the person's first turn of the
    conversation (``memory`` None otherwise), so nothing but a memory call brought what they told BAXY before:
    - ``unread_memory``: a statement tells a datum of the person as remembered, known, told or kept while no call to the
      memory completed in the conversation, or says the memory does not hold it while no call looked at the memory at all
      and it is among the tools;
    - ``unbacked_memory``: the memory was read, and what the statement tells as remembered is in no value it brought
      («Recuerdo que tu color favorito es el azul» with turquesa read);
    - ``memory_subject``: the statement gives the person (tu, your) a value whose record is named as someone else's or
      something else's («de mi hija») that neither the person nor the answer names (VIVOM1 H10, 3 of 3).
    Whose a datum is, only by grammar (``_PERSON``, ``_THEIRS``); a claim is not read in a clause that denies it, asks it
    or says «si»; nothing with the session not known whole, nor without ``memory``."""
    if memory is None or session is None:
        return []
    completed = any(op.startswith("memory.") and done for op, done, _ in session)
    looked = any(op.startswith("memory.") for op, _, _ in session)
    read, records, unknown = _memory_values(receipts)
    asked = _fold(request or "")
    asked_stems = _stems(asked)
    theirs = bool(_THEIRS.search(asked))
    backing = set().union(*(_stems(value) for _, value in records)) if records else set()
    # «Do you remember my dog's name?» → «Sí, tu perro se llama Toby» (MEM2 held-out P03, nothing read): the «sí» that
    # answers a question of BAXY remembering or knowing tells the rest as remembered. Then only with whose it is said
    # (tu, your): «Sí, te explico: el IVA se calcula…» is not.
    yes_to = _ASKED_KNOWN.search(asked)
    # REG1 (REV11 C-2): what the person told in this conversation backs a datum as a value read does («Mi perro se llama
    # Toby. ¿Qué nombre le pongo al gato?» → «Me dijiste que tu perro se llama Toby…»): the words of their statements, not
    # of their questions («¿Mi color favorito es el azul?» tells nothing). Read only in their first turn (``memory``), the
    # request is all they said.
    stated = set().union(*(_stems(asked[s:e]) for s, e in _statements(asked) if not re.search(r"[?¿]", asked[s:e])))
    for start, end in statements:
        if not completed or (read and not unknown):
            yes = _YES.match(folded[start:end]) if yes_to else None
            hits = [(h.start(), h.end(), True) for h in _REMEMBERED.finditer(folded, start, end)]
            hits += [(h.start(), h.end(), True) for h in _KNOWN.finditer(folded, start, end)
                     if _KNOWN_THEIRS.match(folded, h.end(), end)]
            hits += [(h.start(), h.end(), False) for h in _TOLD.finditer(folded, start, end)]
            hits += [(start, start + yes.end(), None)] if yes else []
            for at, to, remembered in hits:
                if _negated(folded, start, at, text):
                    continue
                rest = folded[start:at] + " " * (to - at) + folded[to:end]
                own = _own_clause(folded, start, end, at, to)
                if remembered and not (theirs or _PERSON.search(own)):
                    continue  # «recuerdo que se hace con huevo»: not of the person
                if remembered is None and not _POSSESSIVE.search(rest):
                    continue
                datum = (_stems(own) if remembered is not None else set()) or _stems(rest)
                if datum and not datum - stated:
                    continue  # all it tells, the person said
                said = _stems(rest) - asked_stems
                if not completed:
                    rule = "unread_memory"
                elif said and not said & backing:
                    rule = "unbacked_memory"
                else:
                    continue
                fact = (f"en esta conversación ninguna llamada a tu memoria se completó: lo que la persona te contó en "
                        f"otras conversaciones sólo lo trae {memory}" if rule == "unread_memory" and memory else
                        "tu memoria no está entre tus herramientas en este PC: nada de lo que la persona te contó en otras "
                        "conversaciones te llega" if rule == "unread_memory" else
                        "lo que trajo tu memoria en esta conversación no lo dice: " + (
                            "; ".join(f"«{label}»: «{value}»" for label, value in records[:5]) or "nada"))
                return [{"rule": rule, "said": _quote(text, _clause_start(folded, start, at), end), "fact": fact}]
        # Without the memory among the tools, «no lo tengo guardado» is so (MEM1, Esencial: told again 3 rounds).
        hit = None if looked or not memory else _NOT_KEPT.search(folded, start, end)
        if hit and (theirs or _PERSON.search(_own_clause(folded, start, end, hit.start(), hit.end()))) or (
                not hit and not looked and memory and theirs and (hit := _NO_RECORD.search(folded, start, end))):
            return [{"rule": "unread_memory", "said": _quote(text, _clause_start(folded, start, hit.start()), end),
                     "fact": f"en esta conversación ninguna llamada miró tu memoria: lo que la persona te contó en otras "
                             f"conversaciones sólo lo trae {memory}"}]
        for label, value in records:
            whose = _OF.search(label)
            at = folded.find(value.strip(), start, end) if value.strip() else -1
            if not whose or at < 0:
                continue
            # The clause that gives the value: «Tu color favorito es el verde agua, pero eso es de tu hija» gives it.
            begin = _clause_start(folded, start, at)
            stop = _CLAUSE_END.search(folded, at + len(value.strip()), end)
            clause = folded[begin:stop.start() if stop else end]
            owner = _stems(whose.group("whose") or whose.group("owner"))
            if owner and not owner & (_stems(clause) | asked_stems) and _PERSON.search(clause):
                return [{"rule": "memory_subject", "said": _quote(text, begin, stop.start() if stop else end),
                         "fact": f"«{value.strip()}» lo trajo el recuerdo guardado como «{label}»: su nombre dice de "
                                 f"quién o de qué es, y ni la persona ni tu respuesta lo nombran"}]
    return []


# ---- a search engine named that did not answer ------------------------------------------------------------------------
# The engines BAXY knows by their host (the table the Windows provider reads), each by the label before its domain:
# google.com → google, search.brave.com → brave.
_ENGINES = tuple(dict.fromkeys(engine["host"].split(".")[-2] for engine in json.loads(
    (pathlib.Path(__file__).with_name("data") / "search_addresses.v1.json").read_bytes())["engines"]))


def _engines_unanswered(answer: str, folded: str, statements: list[tuple[int, int]],
                        receipts: list[Receipt]) -> list[dict]:
    """Rule ``answered_by``: a statement that names an engine beside a result of the turn's completed web.search (its
    site's name or its title), while that search said another source answered, no result of the turn brings that
    engine's name (a page opened there, a result of its own: not what was asked, nor the query a result echoes) and the
    answer names none of the sources that answered. Not in a clause after «si / if» («si quieres, lo busco en Bing»)."""
    searches = [observed for r in receipts if r.get("completed") and r.get("op") == "web.search"
                for observed in [_parsed(r).get("observed")] if isinstance(observed, dict)]
    sources = list(dict.fromkeys(by for observed in searches
                                 for by in [observed.get("answeredBy")] if isinstance(by, str) and by))
    if not sources or any(_fold(source) in folded for source in sources):
        return []
    # A result told: the name of its site (mechanicalkeyboards of https://mechanicalkeyboards.com/) or its title.
    told = {_fold(name).strip() for observed in searches for item in observed.get("results") or [] if isinstance(item, dict)
            for name in [str(item.get("title") or ""),
                         *(re.findall(r"^https?://(?:www\.)?([^/.]+)", str(item.get("url") or "")))]}
    told = {name for name in told if len(name) >= 3}
    brought = _fold(" ".join(str(v) for r in receipts for k, v in _walk(_parsed(r)) if k != "query"))
    for start, end in statements:
        if not any(re.search(rf"\b{re.escape(name)}\b", folded[start:end]) for name in told):
            continue
        for engine in _ENGINES:
            hit = re.search(rf"\b{re.escape(engine)}\b", folded[start:end])
            if (not hit or re.search(rf"\b{re.escape(engine)}\b", brought)
                    or _negated(folded, start, start + hit.start(), answer)
                    or any(not (m.group(0) == "si" and answer[m.start():m.start() + 2].lower() == "sí")
                           for m in _IF.finditer(folded, start, start + hit.start()))):
                continue
            return [{"rule": "answered_by", "said": _quote(answer, start, end),
                     "fact": f"web_search: lo respondió {', '.join(sources)} (answeredBy); ningún resultado de este "
                             f"turno viene de «{answer[start + hit.start():start + hit.end()]}»"}]
    return []


# ---- a page placed in a program the turn opened while its result names another browser ---------------------------------
_IN_PROGRAM = r"\b(?:en|in|desde|from) (?:el |tu |su |the |your )?(?:navegador |browser )?"
# What puts a page in a program: an opening told in the clause of «en X» («abrí Gmail en Chrome», «quedó abierto en…»),
# not another act there («pegué la receta en el editor», «suena en Spotify», «lo busqué en Google»).
_OPENED_IN = re.compile(rf"\b(?:{KINDS['abrir']['said']}|{KINDS['abrir']['passive']}|abiert[oa]s?|opened)\b")


def _site_name(address: str) -> str:
    """The name of a page's site as an answer says it: the label before its domain's ending, past one of three letters or
    less (web.whatsapp.com → whatsapp, www.tiktok.com → tiktok, ejemplo.com.ar → ejemplo); empty when there is none."""
    labels = [label for label in re.sub(r"^[a-z]+://", "", address).split("/")[0].split(":")[0].split(".") if label]
    for label in reversed(labels[:-1]):
        if len(label) >= 4 and label != "www":
            return label
    return ""


def _browser_contradicted(answer: str, folded: str, statements: list[tuple[int, int]],
                          receipts: list[Receipt]) -> list[dict]:
    """Rule ``browser`` (encargo 70, uso real 03-11 F6: app_open «Google Chrome», then browser_navigate, whose result
    said browser «Opera GX», then «abrí Gmail en Chrome»; in the held-out bench «abrí Chrome y entré a Facebook», «Chrome
    ya estaba abierto y ahora está en tiktok.com»). X is an application an app_open of the turn opened (its name whole, or
    a word of it of four letters or more: «Chrome» of «Google Chrome»), while a completed result of the turn says the page
    opened in another browser (its ``browser``) and the answer names that browser nowhere. A statement places the page in
    X when it tells something opened «en X» (an opening in that clause: not «pegué la receta en el editor»), or
    when it names X and the page's site (the name of its address: tiktok of www.tiktok.com) together. Every name comes from
    the turn's results, none from a list of browsers. Not in a negated clause nor after «si / if»."""
    shown = [(r, browser) for r in receipts if r.get("completed")
             for observed in [_parsed(r).get("observed")] if isinstance(observed, dict)
             for browser in [observed.get("browser")] if isinstance(browser, str) and browser.strip()]
    if not shown or any(_fold(browser).strip() in folded for _, browser in shown):
        return []
    browsers = {_fold(browser).strip() for _, browser in shown}
    addresses = [_fold(str(value)) for receipt, _ in shown for key, value in _walk(_parsed(receipt))
                 if key in ("requestedUrl", "finalUrl", "url")]
    # A word of a site the turn opened is that site, not the application («en Google» for a google.com page).
    sites = " ".join(addresses)
    site_names = {name for name in map(_site_name, addresses) if name}
    variants: dict[str, str] = {}
    for r in receipts:
        if not (r.get("completed") and r.get("op") == "app.open"):
            continue
        observed = _parsed(r).get("observed")
        observed = observed if isinstance(observed, dict) else {}
        for name in (observed.get("displayName"), observed.get("appId"), (r.get("arguments") or {}).get("appId")):
            folded_name = _fold(name).strip() if isinstance(name, str) else ""
            if not folded_name or any(b in folded_name or folded_name in b for b in browsers):
                continue  # the browser the page did open in (Opera GX opened, or «chrome» for Google Chrome)
            for variant in {folded_name, *(w for w in folded_name.split() if len(w) >= 4)}:
                if not re.search(rf"\b{re.escape(variant)}\b", sites):
                    variants.setdefault(variant, name.strip())

    def turned_off(start: int, at: int) -> bool:
        return _negated(folded, start, at, answer) or any(
            not (m.group(0) == "si" and answer[m.start():m.start() + 2].lower() == "sí")
            for m in _IF.finditer(folded, start, at))

    for start, end in statements:
        for variant, name in variants.items():
            opened_in = re.search(_IN_PROGRAM + re.escape(variant) + r"\b", folded[start:end])
            placed = bool(opened_in) and _OPENED_IN.search(
                folded, _clause_start(folded, start, start + opened_in.start()), start + opened_in.start()) is not None
            if placed and turned_off(start, start + opened_in.start()):
                placed = False
            if not placed:
                named = re.search(rf"\b{re.escape(variant)}\b", folded[start:end])
                placed = (bool(named) and not turned_off(start, start + named.start())
                          and any(re.search(rf"\b{re.escape(site)}\b", folded[start:end]) for site in site_names))
            if not placed:
                continue
            receipt, browser = shown[-1]
            return [{"rule": "browser", "said": _quote(answer, start, end),
                     "fact": f"{receipt.get('tool')}: la página se abrió en {browser} (browser de su resultado), no en "
                             f"{name}; {name} sólo se abrió con app_open"}]
    return []


def _denials(answer: str, folded: str, statements: list[tuple[int, int]], receipts: list[Receipt],
             catalog: dict[str, str] | None, tries: list[tuple[str, str]] | None,
             wire_of: Callable[[str], str] = plain) -> list[dict]:
    """«No puedo borrar carpetas de X» in a turn with no call while the catalog has an operation that does it (rule
    ``denial``). ``catalog``: each operation of the session's catalog and the description the model reads; ``tries``:
    the session's earlier calls as (operation, status of their result): one of that act that did not complete (it
    failed, waits for a «sí», was declined, its result unknown) may be what the answer tells, and holds the finding; one
    the core refused for its arguments («rejected»: nothing was tried) does not."""
    if receipts or not catalog:
        return []
    other: tuple[int, int] | None = None  # the first «no puedo» no operation of the table answers
    for start, end in statements:
        if _REAL_LIMIT.search(folded, start, end):
            continue
        for hit in _DENIAL.finditer(folded, start, end):
            if any(not (m.group(0) == "si" and answer[m.start():m.start() + 2].lower() == "sí")
                   for m in _IF.finditer(folded, start, hit.start())):
                continue  # «si no me dices dónde, no puedo…»: a condition, not a limit
            if any(not (m.group(0) == "si" and answer[m.start():m.start() + 2].lower() == "sí")
                   for m in _IF_AFTER.finditer(folded, hit.end(), end)):
                continue  # «no puedo abrirlo si no me dices cuál»: a condition after it
            stop = next((m.start() for m in _CLAUSE_END.finditer(folded, hit.end(), end)), end)
            if "acces" in hit.group(0):
                act = "acceso"
            else:
                verb = _DENIED_ACT.match(folded, hit.end(), stop)
                act = next((k for k, v in verb.groupdict().items() if v), None) if verb else None
            objects = [kind for kind, pattern in _DENIED_OBJECTS.items() if pattern.search(folded, hit.end(), stop)]
            if "window" in objects:
                objects = [o for o in objects if o != "note"]
            ops = [op for kind in objects for op in DENIED_OPS.get((act, kind), ())] if act else []
            if not ops:
                other = other or (start, end)
                continue
            if any(op in ops and status not in ("completed", "rejected") for op, status in tries or []):
                continue
            named = [op for op in dict.fromkeys(ops) if op in catalog][:2]
            if named:
                facts = "; ".join(f"{wire_of(op)} lo hace en el PC de la persona: «{_first_sentence(catalog[op])}»"
                                  for op in named)
                return [{"rule": "denial", "said": _quote(answer, start, end), "fact": facts}]
    if other is None:
        for start, end in statements:
            if _REAL_LIMIT.search(folded, start, end):
                continue
            for hit in _DENIAL_ANY.finditer(folded, start, end):
                if not any(not (m.group(0) == "si" and answer[m.start():m.start() + 2].lower() == "sí")
                           for m in _IF.finditer(folded, start, hit.start())) and not _IF_AFTER.search(folded, hit.end(), end):
                    other = other or (start, end)
    if other is not None and "web.search" in catalog:
        return [{"rule": "denial_lookup", "said": _quote(answer, *other),
                 "fact": f"{wire_of('web.search')} busca en internet con las palabras que le des"}]
    return []
