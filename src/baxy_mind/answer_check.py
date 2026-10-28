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
- ``place``: «en la biblioteca» after an app_open that only asked for that place and nothing looked after it (F019).
- ``partial``: «no está / no hay / revisé todo / en ningún otro lugar» after a read or a search whose result says it
  covered only part (readInPart, searchScope, subfoldersNotOpened, timeLimitReached, entriesShown < count, a view cut,
  searchedElsewhere false) or after a look that failed with an error that is not itself a «not found», unless the
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
- ``output``: «salió «Hola mundo»», «imprimió «3»» (an output quoted after a verb that tells one) in a turn with calls
  while no result of the turn shows that text (uso real 2026-10-26: a console command sent without reading its output
  and window looks that failed, then «el programa se ejecutó y salió «Hola mundo»»).
- ``answered_by``: a search engine of BAXY's table (search_addresses.v1.json: Google, Bing, DuckDuckGo…) named in a
  statement of a turn with a completed web.search, while no result of the turn brings that name and the statement does
  not name the source that answered («answeredBy») (R7-NB-3: «Google me dio…» when DuckDuckGo answered).

What never counts as a claim: a sentence or the part of one that is a question, a clause with «no / nunca / sin /
tampoco» before the verb («no pude abrirlo», «no lo cerré»), a conditional «si…», quoted text, or a promise («voy a
abrir»). Spanish is read folded (no accents, lower case) with the same length as the original, so quotes are the
model's own words.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
import pathlib
from typing import Any, Callable, Iterable

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
                      "shell.command.run", "client.channel.locate", "window.")},
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
                  "ops": ("audio.", "media.", "input.", "client.microphone", "system.settings.")},
    "escribir": {"said": r"escribi|he escrito|sobrescribi|he sobrescrito|tecle|teclee",
                 "passive": "",
                 "asked": r"escribiste",
                 "ops": ("input.", "file.write", "file.edit", "note.", "message.", "clipboard.", "office.", "memory.",
                         "filesystem.", "task.", "calendar.", "email.", "document.")},
    "guardar": {"said": r"guarde|he guardado",
                "passive": r"se guardo|quedo guardad[oa]",
                "asked": r"guardaste",
                "ops": ("file.write", "file.edit", "input.", "memory.", "note.", "office.", "filesystem.", "backup.",
                        "task.", "clipboard.", "web.download", "capture.", "document.", "calendar.", "schedule.")},
    "crear": {"said": r"cree|he creado",
              "passive": r"se creo",
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
    "agregar": {"said": r"agregue|anadi|he agregado|he anadido|anote|he anotado",
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


def _preterite(text: str, hit: re.Match[str]) -> bool:
    """Whether a folded verb ending in «e» was written «é» («cerré», «borré», «creé»): unaccented it is another form of
    the verb («que el pistón baje», «que lo borre», «él cree»), which claims nothing. A model that drops the accent
    loses the claim, never the other way round."""
    word = hit.group(0).split(" ")[0]
    if word in ("he", "te") or not word.endswith("e"):
        return True
    at = hit.start() + len(word) - 1
    return text[at] in "éÉ"

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
                     r"aparece|aparecen|aparecia|figura|figuran|contiene|contienen|tiene|tienen|tenia|sale|salen|"
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
_PATH = re.compile(r"\b[A-Za-z]:[\\/][^\s«»\"'”“,;()<>*`]*")
# A folder named as where it did not go («no en BAXY-bench», «en vez de Descargas»).
_NOT_THERE = re.compile(r"\b(?:no|ni|en vez de|en lugar de|fuera de|sino|no dentro de)(?: (?:en|a|de|dentro de))?"
                        r"(?: (?:la|tu|mi) carpeta(?: de)?)? ?$")

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


def _told(receipt: Receipt) -> str:
    return f"{receipt.get('tool') or receipt.get('op')} → {receipt.get('outcome') or 'sin resultado'}"


# ---- the check --------------------------------------------------------------------------------------------------------
def check(answer: str, request: str, receipts: list[Receipt], session: list[Call] | None,
          catalog: dict[str, str] | None = None, tries: list[tuple[str, str]] | None = None,
          wire_of: Callable[[str], str] = plain) -> list[dict]:
    """The findings of an answer against its turn: ``receipts`` are the turn's calls in order, ``session`` every call
    of the session before and in this turn as (operation, completed, read), or None when the session is not known whole (a
    kept session, or one past the calls the mind keeps): then nothing is said of calls that may have been there.
    ``catalog`` (each operation and its description) and ``tries`` (the conversation's earlier calls as (operation,
    status)) are for the rule ``denial``, which is not read without the catalog; ``wire_of`` gives an operation the tool name
    shown to the model (wire.Wires.name).
    Each finding: {"rule", "said" (the model's words), "fact" (what contradicts them)}."""
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
            passive = _PASSIVE.get(kind)
            passives = list(passive.finditer(folded, start, end)) if passive else []
            for hit, is_passive in [*((h, False) for h in hits), *((h, True) for h in passives)]:
                if _negated(folded, start, hit.start(), text) or kind in done_kinds:
                    continue
                fact = _act_fact(kind, receipts, session, passive=is_passive,
                                 unsure_said=_UNSURE.search(folded, start, end) is not None)
                if fact:
                    add(fact[0], _clause_start(folded, start, hit.start()), end, fact[1])
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

    # «En la biblioteca» after an app_open that only asked for its place (F019).
    for receipt, words in _places_asked(receipts):
        for start, end in statements:
            hit = re.search(rf"\b(?:en|a) (?:la |el |los |las |su |tu )?(?:seccion (?:de )?)?(?:{words})\b",
                            folded[start:end])
            if hit and not _negated(folded, start, start + hit.start(), text):
                add("place", start, end, f"{_told(receipt)}: pidió ese lugar, pero nada comprobó que se viera")
                break

    # «No hay un botón «Biblioteca»» while the window's reading shows that name (F019 on int10e: its text said «TIENDA
    # BIBLIOTECA» and that a line of it is pressed by its text). Read on the answer with its quotes, where the name is.
    views = [r for r in receipts if r.get("completed") and _matches(r.get("op", ""), ("input.visible.controls",))]
    if views:
        for start, end in statements:
            for hit in _NO_CONTROL.finditer(raw_folded, start, end):
                name = (hit.group("quoted") or hit.group("bare") or "").strip()
                shown = next((r for r in views if len(name) >= 3
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
                told = (f"{_told(receipt)}: {_PARTIAL_TOLD[why]}" if why == "failedRead"
                        else f"{receipt.get('tool')} leyó sólo una parte: {_PARTIAL_TOLD[why]}")
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

    # «Google me dio…» while the search that answered was another engine's (R7-NB-3).
    findings.extend(f for f in _engines_unanswered(answer, folded, statements, receipts) if f not in findings)

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
    return findings


def _does(kind: str, op: str, read: bool) -> bool:
    """Whether an operation can be what did an act of this kind: a read never did one, but for «busqué», «revisé»; a
    confirmation's own call (its operation not known here) can be any."""
    op = operation_of(op)  # a plain wire name (app_open) is its operation's (app.open): the catalog's ids have no «_»
    return op == "confirmation.answer" or ((not read or kind == "mirar") and _matches(op, KINDS[kind]["ops"]))


def _done(kind: str, receipts: list[Receipt], session: list[Call] | None) -> bool:
    """Whether a call of this kind completed in the turn or, as far as it is known, in the session."""
    if any(r.get("completed") and _does(kind, str(r.get("op")), bool(r.get("read"))) for r in receipts):
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
        if unsure_said or passive or any(r.get("completed") and r.get("read") for r in receipts):
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
    view = facts.get("view")
    if isinstance(view, str) and ("texto cortado" in view or "no se listan" in view):
        return "viewCut"
    if observed.get("searchedElsewhere") is False:
        return "searchedElsewhere"
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
    for r in receipts:
        tool = str(r.get("tool") or r.get("op"))
        values = []
        for key, value in [*_walk(_parsed(r)), *_walk(r.get("arguments") or {})]:
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                values.append((key, float(value), tool))
            elif isinstance(value, str) and len(value) < 400:
                values.extend((key, float(n.replace(",", ".")), tool)
                              for n in re.findall(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w])", value))
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
    if where:
        for start, end in statements:
            sentence = folded[start:end]
            put = _PLACED.search(sentence)
            if not put or _negated(folded, start, start + put.start(), answer):
                continue
            named = [(label, shows) for label, pattern, shows in _FOLDERS
                     for m in [pattern.search(sentence)] if m and not _NOT_THERE.search(sentence[:m.start()][-30:])]
            if _HOME.search(sentence):
                named.append(("home", ("home",)))
            for label, shows in named:
                if not any(_in_folder(path, label, shows) for _, path in where):
                    receipt, path = where[-1]
                    found.append({"rule": "folder", "said": _quote(answer, start, end),
                                  "fact": f"{receipt.get('tool')} lo dejó en {_original_path(receipt, path)}"})
                    break
        # The folder the person asked for is not where it went, and the answer tells it as done in no place at all
        # (E024: «Listo, agregué la línea a notas.txt» for «… en la carpeta BAXY-bench», written in the home
        # folder). An answer that names a place (a path, a folder, the asked one said as where it did not go) is read
        # by the rule above: «lo guardé en C:\Users\…\prueba.txt» is literally true (a doubtful one by hand, F013).
        wanted = _asked_folder(request)
        if wanted and not found and not any(_in_asked(path, wanted) for _, path in where) \
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
    shown = _paths(receipts)
    asked = (request or "").replace("/", "\\").lower()
    if shown:
        for m in _PATH.finditer(answer):
            said = m.group(0).replace("/", "\\").rstrip(".\\").lower()
            if not said or said in asked:
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
    backslashes; its place as ``found`` writes one: the known folder, the subfolder and the file; the name the result
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
        names += [arguments.get(key) for key in ("fileName", "name", "relativePath")]
        subdirectory = arguments.get("subdirectory")
        given = arguments.get("fileName") or arguments.get("name")
        if isinstance(subdirectory, str) and isinstance(given, str) and subdirectory.strip():
            names.append(subdirectory.rstrip("\\/") + "\\" + given)
        paths = {n.strip().replace("/", "\\").lower() for n in names if isinstance(n, str) and n.strip()}
        if paths:
            label = next((n for n in names if isinstance(n, str) and n.strip()), "")
            parts = [observed.get("folder") or arguments.get("folder"), subdirectory, given or label]
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
            if act is None:
                continue
            objects = [kind for kind, pattern in _DENIED_OBJECTS.items() if pattern.search(folded, hit.end(), stop)]
            if "window" in objects:
                objects = [o for o in objects if o != "note"]
            ops = [op for kind in objects for op in DENIED_OPS.get((act, kind), ())]
            if not ops or any(op in ops and status not in ("completed", "rejected") for op, status in tries or []):
                continue
            named = [op for op in dict.fromkeys(ops) if op in catalog][:2]
            if named:
                facts = "; ".join(f"{wire_of(op)} lo hace en el PC de la persona: «{_first_sentence(catalog[op])}»"
                                  for op in named)
                return [{"rule": "denial", "said": _quote(answer, start, end), "fact": facts}]
    return []
