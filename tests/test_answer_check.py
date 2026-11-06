"""Aid «answer_check» (al máximo, lever 3): the final answer read against the turn's results before it is spoken
(src/baxy_mind/answer_check.py), and the one regeneration the mind asks for when it contradicts them (Mind._check_answer).
The rules flag only a fact that contradicts the answer; Spanish paraphrases, «no pude», hedges and questions pass."""
import json
from pathlib import Path

import pytest

from baxy_mind.answer_check import check
from baxy_mind.mind import CHECK_NOTE, COMPLETED_OUTCOMES, Mind, _outcome
from test_mind_aids import _trace
from test_mind_final import _call, _mind, _say

READS = {"window.application.status", "file.read", "filesystem.list", "file.find", "input.visible.controls",
         "system.status", "audio.status", "file.open.read"}


def _r(op: str, facts: dict, arguments: dict | None = None) -> dict:
    """A receipt as the mind builds it (Mind._receipt), from a result's JSON."""
    observation = json.dumps(facts, ensure_ascii=False)
    read = op in READS
    outcome = _outcome(observation, read=read)
    return {"op": op, "tool": op.replace(".", "_"), "arguments": arguments or {}, "observation": observation,
            "outcome": outcome, "completed": outcome.startswith(COMPLETED_OUTCOMES), "read": read}


def _rules(answer: str, receipts: list[dict], request: str = "", session: list | None = None) -> list[str]:
    calls = [(r["op"], r["completed"], r["read"]) for r in receipts] if session is None else session
    return [f["rule"] for f in check(answer, request, receipts, calls)]


FAILED_CLOSE = {"status": "failed", "error": "window_not_found"}
DONE = {"status": "completed", "verification": "readback"}


# ---- success claimed on what did not complete ------------------------------------------------------------------------
@pytest.mark.parametrize("answer,flagged", [
    ("Cerré Paint.", True),
    ("Listo, he cerrado Paint.", True),
    ("Paint se cerró.", True),
    ("No pude cerrar Paint: no encontré su ventana.", False),
    ("No cerré Paint porque no tenía ninguna ventana abierta.", False),
    ("Intenté cerrar Paint, pero no encontré su ventana.", False),
    ("¿Quieres que cierre Paint de otra forma?", False),
    ("Paint no se cerró: no encontré su ventana.", False),
])
def test_a_close_that_failed_is_never_told_as_done(answer: str, flagged: bool) -> None:
    assert ("not_completed" in _rules(answer, [_r("app.close", FAILED_CLOSE)], "cierra paint")) is flagged


@pytest.mark.parametrize("facts", [
    {"status": "needs_confirmation", "next": "nothing ran"},
    {"status": "cancelled", "error": "declined_by_person"},
    {"status": "pending"},
])
def test_a_delete_that_waited_or_was_declined_is_not_told_as_done(facts: dict) -> None:
    receipts = [_r("filesystem.known.trash.named", facts)]
    assert _rules("Borré notas.txt y está en la papelera.", receipts) == ["not_completed"]
    assert _rules("No borré notas.txt.", receipts) == []


def test_an_unsure_act_is_contradicted_only_when_told_bare() -> None:
    typed = _r("input.text.type", {"status": "failed", "error": "input_text_not_read_back", "effectUncertain": True})
    assert _rules("Escribí «hola» en el Bloc de notas.", [typed]) == ["not_completed"]
    # Told with its limit, or as what was delivered, or after a look that completed: the verified with its limits.
    assert _rules("Escribí «hola», pero no pude comprobar que quedara en el Bloc de notas.", [typed]) == []
    assert _rules("El texto se envió a la Calculadora.", [typed]) == []
    looked = _r("input.visible.controls", {"status": "completed", "verification": "output_only", "view": "…"})
    assert _rules("Escribí «hola» en la Calculadora.", [typed, looked]) == []


def test_an_act_with_no_call_of_its_kind_in_the_session_is_contradicted() -> None:
    looked = _r("window.application.status", {"status": "completed", "verification": "output_only",
                                              "observed": {"hasVisibleWindow": True}})
    assert _rules("Listo, abrí Spotify.", [looked], "abre spotify") == ["no_call"]
    # A completed open earlier in the session is what it tells.
    assert _rules("Listo, abrí Spotify.", [looked], session=[("app.open", True, False),
                                                              ("window.application.status", True, True)]) == []
    # A session not known whole (a kept one) says nothing of calls that may be in it.
    assert check("Listo, abrí Spotify.", "abre spotify", [looked], None) == []


def test_the_sound_of_a_discord_call_silenced_by_its_deafen_is_an_act_of_its_kind() -> None:
    # Uso real 2026-11-03 (G5): «silencié el audio de la llamada» after a completed client.deafen.set is that act, not
    # one with no call of its kind; with only a look at Discord it still is.
    deafened = _r("client.deafen.set", {"status": "completed", "verification": "readback",
                                        "observed": {"deafened": True, "deafenedBefore": False, "micMuted": True}},
                  {"client": "discord", "deafened": True})
    looked = _r("input.visible.controls", {"status": "completed", "verification": "output_only", "view": "…"})
    assert _rules("Silencié el audio de la llamada de Discord.", [deafened], "ensordéceme en discord") == []
    assert _rules("Silencié el audio de la llamada de Discord.", [looked], "ensordéceme en discord") == ["no_call"]


def test_what_the_answer_itself_made_is_not_an_act_on_the_pc() -> None:
    # Pasted text read and answered in words (rule 1): nothing was called, and nothing is contradicted.
    for answer in ("Te escribí un resumen corto: el error está en la línea 3.", "Revisé tu código: falta un paréntesis.",
                   "Leí el texto que pegaste y está bien.", "Te creé una lista: pan, leche y huevos.",
                   "Hice la cuenta: 12 por 7 es 84.", "Te puse un ejemplo abajo."):
        assert _rules(answer, [], "revisa esto", session=[]) == [], answer
    # A search told with no search in the session is not.
    assert _rules("Busqué en internet y mañana llueve.", [], "¿llueve mañana?", session=[]) == ["no_call"]


@pytest.mark.parametrize("answer", [
    "Voy a abrir Paint ahora.",
    "Si quieres, abro Paint.",
    "Puedo abrir Paint si me lo pides.",
    "El pistón baje y la válvula se cierre: así funciona el motor.",  # subjunctive, not a preterite
    "Te cuento: «abrí la puerta y cerré la ventana» es una frase en pasado.",  # quoted
    "Abri la Calculadora.",  # an open that completed (unaccented «abrí» still read)
])
def test_paraphrases_promises_conditionals_and_quotes_claim_nothing(answer: str) -> None:
    opened = _r("app.open", {**DONE, "observed": {"appId": "Calculadora"}})
    assert _rules(answer, [opened]) == []


# ---- «Sí» to «¿abriste…?» ----------------------------------------------------------------------------------------
def test_a_yes_to_did_you_open_it_needs_an_open_in_the_session() -> None:
    # F002 (9 of 9 hand-read runs of pc-t2): a look at its windows is not opening it.
    looked = _r("window.application.status", {"status": "completed", "verification": "output_only",
                                              "observed": {"hasVisibleWindow": True, "visibleWindowCount": 1}})
    assert _rules("Sí, Spotify está abierto con una ventana.", [looked], "¿abriste Spotify?") == ["implied_yes"]
    assert _rules("No lo abrí yo, pero Spotify tiene una ventana abierta.", [looked], "¿abriste Spotify?") == []
    assert _rules("Sí, Spotify está abierto.", [looked], "¿abriste Spotify?",
                  session=[("app.open", True, False), ("window.application.status", True, True)]) == []
    # F015: «¿ya cerraste…?» with nothing closed.
    assert _rules("Sí, el Bloc de notas no tiene ventana abierta.", [looked],
                  "¿ya cerraste el bloc de notas que te pedí?") == ["implied_yes"]


def test_a_state_told_in_a_session_with_no_call_is_contradicted_only_when_asked_about() -> None:
    asked = "¿ya cerraste el bloc de notas que te pedí?"
    assert _rules("No, el Bloc de notas sigue abierto. ¿Quieres que lo cierre?", [], asked, session=[]) \
        == ["unread_state"]
    assert _rules("No lo sé: no he mirado si sigue abierto.", [], asked, session=[]) == []
    # A lesson is not the PC's state.
    assert _rules("En el motor, las dos válvulas están cerradas en la compresión.", [], "explícame un motor",
                  session=[]) == []


# ---- a «no está» after a partial read ---------------------------------------------------------------------------------
PAGE = {"status": "completed", "verification": "output_only",
        "observed": {"readInPart": True, "fromLine": 1, "toLine": 1904, "totalLines": 3000}}


@pytest.mark.parametrize("answer,flagged", [
    ("Revisé todo el archivo y no aparece la palabra clave.", True),
    ("La palabra clave no está en el archivo.", True),
    ("En las líneas que leí no aparece la palabra clave; me faltan las demás.", False),
    ("Hasta la línea 1904 no aparece; lo demás no lo leí.", False),
    ("No pude leer todo el archivo: sólo hasta la línea 1904.", False),
    ("¿Quieres que siga leyendo el resto?", False),
])
def test_a_page_of_a_file_is_not_the_whole_file(answer: str, flagged: bool) -> None:
    assert ("partial" in _rules(answer, [_r("file.read", PAGE)])) is flagged


def test_a_listing_without_its_subfolders_and_a_search_that_stopped() -> None:
    listing = _r("filesystem.list", {"status": "completed", "verification": "output_only",
                                     "observed": {"entries": [], "count": 0, "subfoldersNotOpened": 3}})
    assert _rules("No hay archivos .bak en esa carpeta.", [listing]) == ["partial"]
    assert _rules("Directamente en esa carpeta no hay .bak; sus subcarpetas no las abrí.", [listing]) == []
    search = _r("file.find", {"status": "completed", "verification": "output_only",
                              "observed": {"count": 0, "searchScope": {"timeLimitReached": True}}})
    assert _rules("Revisé todas las carpetas y no hay ningún informe.", [search]) == ["partial"]
    nowhere = _r("file.open", {"status": "failed", "error": "file_not_found",
                               "observed": {"folder": "home", "searchedElsewhere": False}})
    assert _rules("No lo encontré en BAXY-bench ni en ningún otro lugar.", [nowhere]) == ["partial"]
    assert _rules("No lo encontré en BAXY-bench; no lo busqué en otras carpetas.", [nowhere]) == []
    # A plain «no lo encontré» there is what the result says.
    assert _rules("No encontré informe_final.docx en BAXY-bench.", [nowhere]) == []


def test_a_look_that_failed_read_nothing() -> None:
    failed = _r("window.application.status", {"status": "failed", "error": "inventory_failed"})
    assert _rules("El Bloc de notas no aparece en la lista de aplicaciones abiertas.", [failed]) == ["partial"]
    # Its error is itself the reading that the window is not there.
    gone = _r("window.application.status", {"status": "failed", "error": "window_not_found"})
    assert _rules("El Bloc de notas no está abierto.", [gone]) == []


def test_a_view_is_cut_only_by_its_cut_mark() -> None:
    def look(note: str) -> dict:
        return _r("input.visible.controls", {"status": "completed", "verification": "output_only",
                                             "view": "Ventana «Sin título - Paint.NET» (paintdotnet, window 7), al frente\n"
                                                     "Controles:\n[0] Button «Cerrar» (arriba)\n"
                                                     f"Texto centro: Cerrar | 800 × 600\n{note}\n"},
                  {"application": "Paint.NET", "includeText": True})
    answer = "No hay nada escrito en la pizarra, Paint.NET está en blanco."
    assert _rules(answer, [look("(texto cortado: 3 líneas leídas no se listan, por largas o pasado el tope)")]) \
        == ["partial"]
    # C3-155 s1: lines left out because they repeat a listed control's name hide nothing of what the window shows.
    assert _rules(answer, [look("(8 líneas de texto no se listan: repiten el nombre de un control listado)")]) == []


# ---- numbers --------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("facts,answer,flagged", [
    ({"observed": {"percent": 69}}, "La batería está al 0,69 %.", True),
    ({"observed": {"percent": 69}}, "La batería está al 69 %.", False),
    ({"observed": {"charge": 0.69}}, "La batería está al 69 %.", False),
    ({"observed": {"charge": 0.69}}, "La batería está al 0,69 %.", True),
    ({"observed": {"usedPercent": 0.69}}, "El disco está al 69 % de uso.", True),  # a percent field: 0,69 %
    ({"observed": {"usedPercent": 0.69}}, "El disco está al 0,69 % de uso.", False),
    ({"observed": {"level": 40}}, "Subí el volumen y quedó en 30.", True),
    ({"observed": {"level": 40}}, "Subí el volumen en 10 y quedó en 40.", False),
    ({"observed": {"level": 0}}, "El volumen ahora está en 0, no en 40.", False),  # p4 E028: said as what it is not
])
def test_a_level_or_a_percentage_that_is_not_the_reading(facts: dict, answer: str, flagged: bool) -> None:
    receipt = _r("audio.volume.adjust" if "volumen" in answer else "system.status",
                 {"status": "completed", "verification": "readback", **facts}, {"delta": 10})
    assert ("number" in _rules(answer, [receipt])) is flagged


def test_a_size_in_other_units_than_the_reading() -> None:
    read = _r("file.read", {"status": "completed", "verification": "output_only", "observed": {"size": 3145728}})
    assert _rules("El archivo pesa 3 MB.", [read]) == []
    assert _rules("El archivo pesa 3,1 MB.", [read]) == []
    assert _rules("El archivo pesa 30 MB.", [read]) == ["number"]
    assert _rules("El archivo pesa 3 GB.", [read]) == ["number"]


# ---- folders and paths ----------------------------------------------------------------------------------------------
def _written(path: str) -> dict:
    return _r("file.write", {**DONE, "observed": {"name": "notas.txt", "fullPath": path}})


def test_a_folder_named_is_where_the_result_says_it_went() -> None:
    home = _written(r"C:\Users\ana\notas.txt")
    assert _rules("Listo, agregué la línea a notas.txt en la carpeta BAXY-bench.", [home]) == ["folder"]
    assert _rules("Listo, agregué la línea a notas.txt en BAXY-bench.",
                  [_written(r"C:\Users\ana\BAXY-bench\notas.txt")]) == []
    # BAXY's own sandbox is not the person's BAXY-bench.
    sandbox = _written(r"C:\Users\ana\AppData\Local\BAXY\bench\filesystem-sandbox\BAXY-bench\notas.txt")
    assert _rules("Lo guardé en BAXY-bench.", [sandbox]) == ["folder"]
    # Said as where it did not go, the folder is the truth.
    assert _rules("Lo guardé en tu carpeta de usuario, no en BAXY-bench.", [home]) == []


def test_a_folder_named_after_a_participle_is_where_the_result_says_it_went() -> None:
    # Holdout v6 V6E058 (s1): «Creada la carpeta fotos_2026 dentro de BAXY-bench.» of a folder made in the home folder
    # went unread: the claim opened with the participle, not with «creé».
    made = _r("filesystem.create.directory", {**DONE, "observed": {"name": "fotos_2026",
                                                                    "fullPath": r"C:\Users\ana\fotos_2026"}})
    assert _rules("Creada la carpeta fotos_2026 dentro de BAXY-bench.", [made]) == ["folder"]
    assert _rules("Guardado notas.txt en BAXY-bench.", [_written(r"C:\Users\ana\notas.txt")]) == ["folder"]
    assert _rules("Creada la carpeta fotos_2026 dentro de BAXY-bench.", [_r(
        "filesystem.create.directory", {**DONE, "observed": {"fullPath": r"C:\Users\ana\BAXY-bench\fotos_2026"}})]) == []
    assert _rules("Listo: creada la carpeta fotos_2026 dentro de BAXY-bench.", [made]) == ["folder"]
    # Revisión de nb-w11-multi: a participle that says where something was, not that this turn left it there, is no claim
    # of where it went («estaba guardado en Descargas» of the file moved to Documentos).
    moved = _written(r"C:\Users\ana\Documents\notas.txt")
    assert _rules("Lo moví a Documentos. Estaba guardado en Descargas.", [moved]) == []


def test_an_absolute_path_that_no_result_shows() -> None:
    home = _written(r"C:\Users\ana\notas.txt")
    assert _rules(r"Lo guardé en C:\Users\ana\notas.txt.", [home]) == []
    # Both say it: the folder named (Documentos) and the path no result shows.
    assert set(_rules(r"Creé notas.txt en C:\Users\ana\Documentos\notas.txt.", [home])) == {"folder"}
    assert _rules(r"Está en C:\Users\ana\Proyectos\x.txt.", [home]) == ["folder"]


# F16 (cosecha 03-11 22:40): «guardé hola_mundo.py en C:\Program Files\Notepad++» was read «C:\Program», which no result
# shows: three rounds of turn.check and 21 s more for a true answer. A Windows path has spaces in its parts (Program
# Files, Archivos de programa, «OneDrive - …», Mis documentos): it is read whole, quoted or not.
def _saved_by_dialog(path: str) -> dict:
    return _r("input.visible.click", {**DONE, "observed": {"clicked": "Guardar", "fileDialog": {"path": path,
                                                                                                 "exists": True}}})


@pytest.mark.parametrize("path,answer", [
    (r"C:\Program Files\Notepad++\hola_mundo.py",
     r"Guardé hola_mundo.py en C:\Program Files\Notepad++, pero no en tu carpeta de Descargas."),
    (r"C:\Program Files\Notepad++\hola_mundo.py", r"Quedó en «C:\Program Files\Notepad++\hola_mundo.py»."),
    (r"C:\Program Files (x86)\Editor Libre\notas.txt", r"Lo guardé en C:\Program Files (x86)\Editor Libre\notas.txt."),
    (r"C:\Archivos de programa\Editor\nota.txt", r"Quedó en C:\Archivos de programa\Editor y no en Descargas."),
    (r"C:\Users\ana\OneDrive - Universidad\Mis documentos\informe final.docx",
     r"Lo guardé en C:\Users\ana\OneDrive - Universidad\Mis documentos."),
    (r"C:\Users\ana\OneDrive - Universidad\Mis documentos\informe final.docx",
     r"Está en C:\Users\ana\OneDrive - Universidad\Mis documentos\informe final.docx, listo para abrir."),
])
def test_a_path_with_spaces_that_a_result_shows_is_read_whole(path: str, answer: str) -> None:
    assert _rules(answer, [_saved_by_dialog(path)]) == []


def test_a_path_with_spaces_that_no_result_shows_is_still_flagged_whole() -> None:
    saved = _saved_by_dialog(r"C:\Program Files\Notepad++\hola_mundo.py")
    found = check(r"Lo guardé en C:\Program Files\Otro Editor\hola_mundo.py.", "", [saved],
                  [(saved["op"], True, False)])
    assert [(f["rule"], f["said"]) for f in found] == [("folder", r"C:\Program Files\Otro Editor\hola_mundo.py.")]
    assert _rules(r"Quedó en «C:\Users\ana\Mis documentos\otro.txt».", [saved]) == ["folder"]


def test_a_folder_with_spaces_asked_for_is_read_whole() -> None:
    written = _written(r"C:\Users\ana\Mis Proyectos\web\notas.txt")
    assert _rules("Listo, guardé notas.txt.", [written], r"crea notas.txt en C:\Users\ana\Mis Proyectos\web") == []
    assert _rules("Listo, guardé notas.txt.", [_written(r"C:\Users\ana\notas.txt")],
                  r"crea notas.txt en C:\Users\ana\Mis Proyectos\web") == ["asked_folder"]


def test_a_place_asked_for_and_not_reached_told_as_done_in_no_place() -> None:
    # E024: «añade … en la carpeta BAXY-bench» written in the home folder, told as done.
    home = _written(r"C:\Users\ana\notas.txt")
    request = "agrega una línea con «comprar pan» a notas.txt, en la carpeta BAXY-bench"
    assert _rules("Listo, agregué «comprar pan» a notas.txt.", [home], request) == ["asked_folder"]
    # Naming where it went is literally true (F013, doubtful by hand): left to the person.
    assert _rules(r"Listo, lo agregué en C:\Users\ana\notas.txt.", [home], request) == []


# ---- the name a file was saved with ---------------------------------------------------------------------------------
# E017 (practice e2e, notebook, every version): «Guardar como» opened, no name nor folder typed, «Guardar» pressed: Windows
# saved «lista pilas, cables.txt» in the home folder, and the answer said «guardé lista.txt en …\BAXY-bench».
SAVE_REQUEST = r"abre el bloc de notas, escribe 'lista: pilas, cables' y guárdalo como lista.txt en C:\Users\ana\BAXY-bench"
SAVE_ANSWER = r"Listo, guardé lista.txt en C:\Users\ana\BAXY-bench."


def _view(title: str) -> dict:
    return _r("input.visible.controls", {"status": "completed", "verification": "output_only",
                                         "view": f"Ventana «{title}» (Notepad, window 7), al frente\nControles:\n"
                                                 f"[0] Document «Editor de texto» (centro)\n[1] TitleBar «{title}» (arriba)"},
              {"application": "Bloc de notas"})


def _click(label: str, after: dict | None = None) -> dict:
    observed = {"ok": True, "name": label, "kind": "Button", "effectObserved": True, **({"after": after} if after else {})}
    return _r("input.visible.click", {**DONE, "observed": observed}, {"label": label})


def _saving(*after_save: dict) -> list[dict]:
    """E017's turn up to the press of «Guardar» in the dialog, with what was read after it."""
    dialog = _r("input.visible.controls", {"status": "completed", "verification": "output_only",
                                           "view": "Ventana «Guardar como» (Notepad, window 9), al frente, es el diálogo "
                                                   "modal\nFoco: [41] Edit «Nombre de archivo:» = lista pilas, cables.txt"})
    return [_r("app.open", {**DONE, "observed": {"appId": "Bloc de notas"}}),
            _r("input.text.type", {**DONE, "observed": {"windowTitle": "Sin título: Bloc de notas"}},
               {"text": "lista: pilas, cables"}),
            _click("Archivo"), _click("Guardar como"), dialog, _click("Guardar"), *after_save]


def test_a_name_said_saved_that_the_window_after_the_save_contradicts() -> None:
    receipts = _saving(_view("lista pilas, cables.txt: Bloc de notas"))
    findings = check(SAVE_ANSWER, SAVE_REQUEST, receipts, [(r["op"], r["completed"], r["read"]) for r in receipts])
    assert [f["rule"] for f in findings] == ["saved_name"]
    assert "lista.txt" in findings[0]["fact"] and "lista pilas, cables.txt" in findings[0]["fact"]
    # The press's own result may carry the title it left (its «after»), and a path said holds the name too.
    titled = _saving()[:-1] + [_click("Guardar", {"changed": ["[29] TitleBar «lista pilas, cables.txt: Bloc de notas»"],
                                                  "gone": ["[30] TitleBar «Sin título: Bloc de notas»"]})]
    assert _rules(SAVE_ANSWER, titled, SAVE_REQUEST) == ["saved_name"]
    assert _rules(r"Lo guardé en C:\Users\ana\BAXY-bench\lista.txt.", receipts, SAVE_REQUEST) == ["saved_name"]


@pytest.mark.parametrize("answer", [
    "No pude guardarlo como lista.txt: la ventana dice lista pilas, cables.txt.",  # negated
    "No guardé lista.txt; Windows lo llamó lista pilas, cables.txt.",
    "¿Guardé lista.txt donde querías?",  # a question
    "Lo guardé. ¿Quieres que lo renombre a lista.txt?",  # the name is in the question
    "Guardé «lista.txt» en BAXY-bench.",  # quoted
    "Guardé lista pilas, cables.txt en tu carpeta de usuario.",  # the name the window says
])
def test_a_name_told_as_not_saved_asked_or_quoted_claims_nothing(answer: str) -> None:
    assert "saved_name" not in _rules(answer, _saving(_view("lista pilas, cables.txt: Bloc de notas")), SAVE_REQUEST)


def test_a_name_the_turn_shows_or_no_name_shown_at_all_is_not_contradicted() -> None:
    # The window says the name said (unsaved mark included).
    assert _rules(SAVE_ANSWER, _saving(_view("*lista.txt: Bloc de notas")), SAVE_REQUEST) == []
    # A result of the turn shows it (the name typed in the dialog, a file result): the window is not all there is.
    typed = _saving(_view("lista pilas, cables.txt: Bloc de notas"))
    typed.insert(5, _r("input.text.type", {**DONE, "observed": {}}, {"text": "lista.txt"}))
    assert _rules(SAVE_ANSWER, typed, SAVE_REQUEST) == []
    # Nothing read after the save, or a title with no extension (hidden extensions): no name is shown, and the rule
    # is silent (what was not verified is other rules' to tell).
    assert _rules(SAVE_ANSWER, _saving(), SAVE_REQUEST) == []
    assert _rules(SAVE_ANSWER, _saving(_view("lista pilas, cables: Bloc de notas")), SAVE_REQUEST) == []
    # A name shown only before the save is not what the save left.
    before = _saving()
    before.insert(2, _view("borrador.txt: Bloc de notas"))
    assert _rules(SAVE_ANSWER, before, SAVE_REQUEST) == []
    # A window that names no file of that kind (a page, an e-mail address) is not the file's window.
    assert _rules(SAVE_ANSWER, _saving(_view("(sin asunto) - ana@gmail.com - Gmail - Opera")), SAVE_REQUEST) == []
    assert _rules(SAVE_ANSWER, _saving(_view("Amazon.com: compras - Opera")), SAVE_REQUEST) == []


def test_the_same_name_with_another_extension_is_another_file() -> None:
    # On Windows the extension is part of the name: lista.md is not lista.txt, and a person who looks for lista.txt
    # does not find it. Same stem or same extension is what makes a window's name the saved file's.
    assert _rules(SAVE_ANSWER, _saving(_view("lista.md: Bloc de notas")), SAVE_REQUEST) == ["saved_name"]
    assert _rules(SAVE_ANSWER, _saving(_view("LISTA.TXT: Bloc de notas")), SAVE_REQUEST) == []  # case is not a name


def test_a_saved_name_is_read_the_same_in_any_app_and_from_a_file_result() -> None:
    paint = [_r("app.open", {**DONE, "observed": {"appId": "Paint"}}), _click("Guardar"),
             _r("input.visible.controls", {"status": "completed", "verification": "output_only",
                                           "view": "Ventana «Sin título.png - Paint» (mspaint, window 3), al frente"})]
    assert _rules("Listo, lo guardé como dibujo.png.", paint, "guarda el dibujo como dibujo.png") == ["saved_name"]
    written = _r("file.write", {**DONE, "observed": {"name": "notas.txt", "fullPath": r"C:\Users\ana\notas.txt"}})
    findings = check("Creé lista.txt con tu texto.", "crea lista.txt", [written], [("file.write", True, False)])
    assert [f["rule"] for f in findings] == ["saved_name"] and "notas.txt" in findings[0]["fact"]
    assert _rules("Creé notas.txt con tu texto.", [written]) == []


def test_a_place_app_open_only_asked_for() -> None:
    # F019: «abre Steam y ve a la biblioteca» → app_open with place, nothing read back, nothing looked after it.
    asked = _r("app.open", {"status": "completed", "verification": "delivered_only",
                            "observed": {"appId": "Steam", "placeRequested": True, "effectReadBack": False}},
               {"appId": "Steam", "place": "library"})
    assert _rules("Abrí Steam en la biblioteca y está al frente.", [asked]) == ["place"]
    assert _rules("Abrí Steam y pedí la biblioteca, pero no comprobé que se vea.", [asked]) == []
    looked = _r("input.visible.controls", {"status": "completed", "verification": "output_only", "view": "BIBLIOTECA"})
    assert _rules("Abrí Steam en la biblioteca.", [asked, looked]) == []


# ---- «ya estaba» ----------------------------------------------------------------------------------------------------
def test_already_so_needs_a_result_that_says_it() -> None:
    changed = _r("audio.mute", {**DONE, "observed": {"muted": True}})
    assert _rules("El audio ya estaba silenciado.", [changed]) == ["already"]
    same = _r("audio.mute", {"status": "completed", "verification": "unchanged", "observed": {"muted": True}})
    assert _rules("El audio ya estaba silenciado.", [same]) == []
    running = _r("app.open", {**DONE, "observed": {"appId": "Bloc de notas", "alreadyRunning": True}})
    assert _rules("El Bloc de notas ya estaba abierto, así que lo traje al frente.", [running]) == []


# Feria 2026-10-27: a volume set changed it at the first call and its repeats in the turn came back «unchanged»; the
# answer said it already was so. Only the first call of an operation in the turn tells what was so before the turn.
def test_already_so_is_the_first_call_of_its_operation() -> None:
    level = {"level": 100}
    changed = _r("audio.volume", {**DONE, "observed": {"before": 30, "final": 100}}, level)
    again = _r("audio.volume", {"status": "completed", "verification": "unchanged", "observed": {"final": 100}}, level)
    assert _rules("El volumen ya estaba en 100.", [changed, again, again]) == ["already"]
    assert _rules("El volumen ya estaba en 100.", [again, changed]) == []
    # Another operation's first call that came back so still tells it (the volume set, the sound already on).
    unmuted = _r("audio.mute", {"status": "completed", "verification": "unchanged", "observed": {"muted": False}})
    assert _rules("Lo puse en 100; el sonido ya estaba activado.", [changed, again, unmuted]) == []
    # Review of the branch: the same operation on another thing is that call's first time; a call that never ran
    # (queued behind a failure) is no call of the turn.
    other = _r("audio.volume", {"status": "completed", "verification": "unchanged", "observed": {"final": 40}},
               {"level": 40, "device": "auriculares"})
    assert _rules("Los auriculares ya estaban en 40.", [changed, other]) == []
    queued = _r("audio.mute", {"status": "not_run", "reason": "the call before it in this turn did not complete"})
    assert _rules("Lo puse en 100; el sonido ya estaba activado.", [queued, changed, unmuted]) == []


# ---- the mind: one more answer, never a loop ------------------------------------------------------------------------
def _closing(tmp_path: Path, *answers: str) -> tuple[Mind, object, dict]:
    mind, server = _mind(tmp_path, [_call("app_close", {"appId": "Paint"}), *(_say(a) for a in answers)])
    mind.wire_to_op = {"app_close": "app.close"}
    mind.decide(1, "cierra paint")
    result = mind.continue_turn(2, json.dumps(FAILED_CLOSE))
    return mind, server, result


def test_a_contradicted_answer_is_written_again_once_with_the_fact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server, result = _closing(tmp_path, "Cerré Paint.", "No pude cerrar Paint: no encontré su ventana.")
    assert result["reply"] == "No pude cerrar Paint: no encontré su ventana."
    note = server.bodies[-1]["messages"][-1]
    assert note["role"] == "user" and note["content"].startswith(CHECK_NOTE[:40])
    assert "«Cerré Paint.»" in note["content"] and "app_close → falló (window_not_found)" in note["content"]
    assert server.bodies[-1]["tool_choice"] == "none"  # words only: it cannot loop through a tool
    # The conversation keeps what was said, not the check: no note, no first answer.
    said = [m["content"] for m in mind.conversation if m["role"] == "assistant" and m.get("content")]
    assert said == ["No pude cerrar Paint: no encontré su ventana."]
    assert not any(str(m.get("content")).startswith(CHECK_NOTE[:20]) for m in mind.conversation)
    checks = [r for r in _trace(mind) if r["stage"] == "turn.check"]
    assert [c["round"] for c in checks] == [1, 2] and checks[0]["content"] == "Cerré Paint."
    assert checks[0]["findings"][0]["rule"] == "not_completed" and checks[1]["kept"] is False


def test_a_second_answer_that_still_contradicts_is_told_the_facts_once_more(tmp_path: Path, monkeypatch) -> None:
    # Uso real 2026-10-26: the second answer still said what the results denied, and was spoken.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server, result = _closing(tmp_path, "Cerré Paint.", "Listo, cerré Paint.", "No pude cerrar Paint.")
    assert result["reply"] == "No pude cerrar Paint." and len(server.bodies) == 4
    assert server.bodies[-1]["messages"][-1]["content"].startswith(CHECK_NOTE[:40])
    assert [c["round"] for c in _trace(mind) if c["stage"] == "turn.check"] == [1, 2, 3]


def test_a_third_answer_is_spoken_whatever_it_says(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server, result = _closing(tmp_path, "Cerré Paint.", "Listo, cerré Paint.", "Ya cerré Paint.")
    assert result["reply"] == "Ya cerré Paint." and len(server.bodies) == 4  # no loop
    assert [c["kept"] for c in _trace(mind) if c["stage"] == "turn.check" and c["round"] == 3] == [True]


def test_an_empty_second_answer_leaves_the_first(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _, result = _closing(tmp_path, "Cerré Paint.", "")
    assert result["reply"] == "Cerré Paint."
    assert mind.conversation[-1] == {"role": "assistant", "content": "Cerré Paint."}


@pytest.mark.parametrize("setting", ["none", "result_dedup,short_refs"])
def test_the_check_is_an_aid_that_turns_off(tmp_path: Path, monkeypatch, setting: str) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    mind, server, result = _closing(tmp_path, "Cerré Paint.")
    assert result["reply"] == "Cerré Paint." and len(server.bodies) == 2
    assert not [r for r in _trace(mind) if r["stage"] == "turn.check"]


def test_an_answer_that_agrees_costs_no_call(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "answer_check")
    mind, server, result = _closing(tmp_path, "No pude cerrar Paint: no encontré su ventana.")
    assert len(server.bodies) == 2 and not [r for r in _trace(mind) if r["stage"] == "turn.check"]


def test_the_voice_drops_what_it_foresaw_of_a_contradicted_answer(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    told: list = []
    mind, server = _mind(tmp_path, [_say("Sí, lo abrí."), _say("No, no lo abrí.")])
    server.chat = (lambda chat: lambda body, on_text=None: chat(body))(server.chat)  # type: ignore[method-assign]
    mind.foresee = lambda text, done: told.append((text, done)) or True
    result = mind.decide(1, "¿abriste Spotify?")
    assert result["reply"] == "No, no lo abrí."
    assert (None, True) in told  # the first answer's look-ahead is dropped before the second is written


def test_a_memory_turn_keeps_its_words_out_of_the_check_trace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("memory_save", {"text": "mi clave es 4321"}), _say("Guardé tu clave."),
                               _say("No pude guardarla.")])
    mind.wire_to_op = {"memory_save": "memory.save"}
    mind.decide(1, "recuerda que mi clave es 4321")
    mind.continue_turn(2, json.dumps({"status": "failed", "error": "memory_disabled"}))
    row = next(r for r in _trace(mind) if r["stage"] == "turn.check")
    assert row["content"] is None and set(row["findings"][0]) == {"rule", "fact"}


def test_the_session_calls_go_with_a_kept_session(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("app_open", {"appId": "Spotify"}), _say("Abrí Spotify."),
                                    _say("Sí, lo abrí antes.")])
    mind.wire_to_op = {"app_open": "app.open"}
    mind.decide(1, "abre spotify")
    mind.continue_turn(2, json.dumps({**DONE, "observed": {"appId": "Spotify"}}))
    kept = mind.export_session()
    mind.load_session(kept)
    assert mind._calls == [("app.open", True, False)]
    assert mind.decide(3, "¿abriste Spotify?")["reply"] == "Sí, lo abrí antes."  # the open is known: no check
    # A session kept before the aid, with calls in it: what ran is not known whole, and nothing is said of it.
    mind.load_session([m for m in kept if m.get("role") != "baxy.session"])
    assert mind._calls is None


# ---- a number only the OCR of a window gives --------------------------------------------------------------------------
# uso-89 (diag-b5bd, R06, 5 of 6): the look at a fresh Edge read its frame's controls and the page by OCR only
# («2. El del norte - calificaclon 829» for «El faro del norte - calificacion 8,9»); the answer told «829».
EDGE_FRAME = ("Ventana «Ranking de prueba - Microsoft Edge» (msedge, window 131406), al frente\nControles:\n"
              "[3] Button «Back» (arriba izq.)\n[16] TabItem «Ranking de prueba» (arriba izq.) (selected)\n"
              "[19] Pane «Ranking de prueba - Microsoft Edge» (centro)\n")
EDGE_OCR = ("Texto arriba: Ranking de prueba | 1 _ Rio de inviemo - calificacion 724 | 2. El del norte - calificaclon 829 | "
            "3 _ Ciudad de papel - calificacion 8.1")
EDGE_PAGE = ("[17] ListItem «El faro del norte - calificacion 8,9» (arriba)\n"
             "[19] ListItem «Ciudad de papel - calificacion 8,1» (arriba)\n")


@pytest.mark.parametrize("answer,view,flagged", [
    ("En la lista que veo, El del norte tiene la mejor calificación, 829.", EDGE_FRAME + EDGE_OCR, True),
    ("El del norte tiene la mejor calificación, 829.", EDGE_FRAME + EDGE_PAGE + EDGE_OCR, True),
    ("El faro del norte tiene la mejor calificación, 8,9.", EDGE_FRAME + EDGE_PAGE + EDGE_OCR, False),
    ("Ciudad de papel tiene 8.1.", EDGE_FRAME + EDGE_PAGE + EDGE_OCR, False),  # the controls say 8,1
    ("Hay 4 elementos en la lista.", EDGE_FRAME + EDGE_OCR, False),  # a number the OCR does not give
    ("La línea dice «calificaclon 829», que no se lee bien.", EDGE_FRAME + EDGE_OCR, False),  # quoted
    ("No pude confirmar si es 829.", EDGE_FRAME + EDGE_OCR, False),  # negated
    ("Tiene 829.", EDGE_FRAME + "(+40 más, sin listar por el tope)\n" + EDGE_OCR, False),  # the list is not whole
    ("Tiene 19.", EDGE_FRAME + EDGE_OCR.replace("829", "19"), True),  # [19] is an index, not a number shown
])
def test_a_number_only_the_ocr_of_a_window_gives(answer: str, view: str, flagged: bool) -> None:
    look = _r("input.visible.controls", {"status": "completed", "verification": "output_only", "view": view},
              {"application": "Microsoft Edge", "includeText": True})
    assert ("recognized_number" in _rules(answer, [look])) is flagged


def test_a_number_of_a_window_drawn_without_controls_or_of_another_result_is_not_read_so() -> None:
    drawn = ("Ventana «Steam» (steamwebhelper, window 7), al frente\nControles (no es la lista completa de la ventana: "
             "puede tener más):\n(no se leyó ninguno)\nTexto arriba: FAVORITOS (324)")
    steam = _r("input.visible.controls", {"status": "completed", "verification": "output_only", "view": drawn})
    look = _r("input.visible.controls", {"status": "completed", "verification": "output_only",
                                         "view": EDGE_FRAME + EDGE_OCR})
    page = _r("browser.page.read", {"status": "completed", "verification": "output_only",
                                    "observed": {"text": "El faro del norte - calificacion 829"}})
    assert _rules("Tienes 324 favoritos.", [steam]) == []
    assert "recognized_number" not in _rules("Tiene 829.", [look, page])
    assert "recognized_number" not in _rules("Tiene 829.", [look], request="¿tiene 829?")


# ---- a control said not to be there while the reading shows its name -----------------------------------------------
# F019 on int10e (notebook, 6 seeds, clear in 3): «abre Steam y ve a la biblioteca» → the reading of Steam has no
# controls but its text says «TIENDA BIBLIOTECA», «se pulsa por su texto», and the answer said there was no such button.
STEAM_VIEW = {"status": "completed", "verification": "output_only",
              "view": "Ventana «Steam» (steamwebhelper, window 24905238), al frente\nLugar a la vista: library de Steam\n"
                      "Controles (no es la lista completa de la ventana: puede tener más):\n(no se leyó ninguno)\n"
                      "(esta ventana no da sus controles: una línea de ahí se pulsa por su texto, como label, y que algo "
                      "no salga en «Controles» no significa que no esté)\n"
                      "Texto arriba: Steam Ver Amigos Productos Ayuda | TIENDA BIBLIOTECA COMUNIDAD | Página principal"}


@pytest.mark.parametrize("answer,flagged", [
    ("Abrí Steam y me quedé en la biblioteca, pero no hay un botón de «Biblioteca»…", True),
    ("No veo ningún botón «Comunidad» en esa ventana.", True),
    ("Ahí no hay botón de «Página principal», así que no pude ir.", True),  # E015: the whole quoted name
    ("No hay un botón «Descargas» en lo que leí de Steam.", False),  # a name the reading does not show
    ("Pulsé «Biblioteca» por su texto.", False),
    ("¿No hay un botón de «Biblioteca»?", False),
])
def test_a_control_said_absent_whose_name_the_reading_shows(answer: str, flagged: bool) -> None:
    view = _r("input.visible.controls", STEAM_VIEW, {"application": "Steam", "includeText": True})
    assert ("named_control" in _rules(answer, [view])) is flagged


# ---- «no encontré X» while a result found X ----------------------------------------------------------------------------
# Holdout v6 V6E055 (s1): an edit refused because the search stopped at its limit after finding BAXY-bench\ideas.txt was
# told «No lo cambié: no encontré BAXY-bench\ideas.txt en todo el tiempo».
SEARCH_STOPPED = {"status": "failed", "error": "known_file_search_incomplete",
                  "observed": {"version": 1, "name": "ideas.txt", "folder": "home",
                               "relativePath": "BAXY-bench\\ideas.txt", "changed": False,
                               "searchScope": {"timeLimitSeconds": 8, "timeLimitReached": True, "exhaustive": False}}}


@pytest.mark.parametrize("answer,flagged", [
    ("No lo cambié: no encontré BAXY-bench\\ideas.txt en todo el tiempo.", True),
    ("No pude encontrar ideas.txt, así que no lo cambié.", True),
    ("No encontré ideas.txt en BAXY-bench.", True),
    ("No lo cambié: la búsqueda encontró BAXY-bench\\ideas.txt y paró antes del resto de la carpeta.", False),
    ("No encontré notas.txt.", False),  # another file
    ("No encontré otro ideas.txt aparte del de BAXY-bench.", False),  # another one of that name
    ("No encontré ideas.txt en Descargas.", False),  # a place that does not hold the one found
    # Revisión de nb-w11-mente: the file is where something else was not found, not what was not found.
    ("Lo revisé y no encontré errores en ideas.txt.", False),
    ("No encontré la palabra cactus en BAXY-bench\\ideas.txt.", False),
    ("No encontré nada raro dentro de ideas.txt.", False),
    ("No encontré el archivo ideas.txt.", True),
    ("No encontré ningún archivo llamado «ideas.txt».", True),
    ("¿No encontré ideas.txt?", False),
])
def test_a_file_said_not_found_that_a_result_of_the_turn_found(answer: str, flagged: bool) -> None:
    edit = _r("file.edit", SEARCH_STOPPED, {"path": "home/ideas.txt"})
    assert ("found" in _rules(answer, [edit], "en ideas.txt cambia regar los cactus por regar las orquídeas")) is flagged


def test_a_file_a_search_listed_or_only_a_name_alike_it_offered() -> None:
    listed = _r("file.find", {"status": "completed", "verification": "output_only",
                              "observed": {"mode": "name", "count": 1, "files": [
                                  {"name": "informe.pdf", "folder": "documents", "relativePath": "trabajo\\informe.pdf"}]}})
    assert "found" in _rules("No encontré informe.pdf en tus carpetas.", [listed])
    # A name that differs only in its accents is the one the search offered as alike, not the one asked: not found.
    alike = _r("file.read", {"status": "failed", "error": "known_file_not_found", "observed": {"candidates": [
        {"name": "canción.txt", "folder": "home", "relativePath": "canción.txt"}]}})
    assert "found" not in _rules("No encontré cancion.txt; hay uno parecido, canción.txt.", [alike])


@pytest.mark.parametrize("setting, checked", [(None, True), ("answer_check", False)])
def test_the_found_rule_is_an_aid_of_its_own(tmp_path: Path, monkeypatch, setting, checked) -> None:
    if setting is None:
        monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    else:
        monkeypatch.setenv("BAXY_AYUDAS", setting)
    first = "No lo cambié: no encontré BAXY-bench\\ideas.txt en todo el tiempo."
    mind, server = _mind(tmp_path, [_call("file_edit", {"path": "home/ideas.txt"}), _say(first),
                                    _say("No lo cambié: la búsqueda encontró BAXY-bench\\ideas.txt y paró.")])
    mind.wire_to_op = {"file_edit": "file.edit"}
    mind.decide(1, "en ideas.txt cambia regar los cactus por regar las orquídeas")
    result = mind.continue_turn(2, json.dumps(SEARCH_STOPPED))
    assert (result["reply"] != first) is checked
    if checked:
        note = server.bodies[-1]["messages"][-1]["content"]
        assert "su resultado muestra que encontró BAXY-bench\\ideas.txt." in note


# ---- «no leí X» while a result of the turn read X whole ---------------------------------------------------------------
# Holdout v6 (falsedades, cien s0, the one clear falsehood): the answer denied having read a text the turn had read
# whole. Only a completed read whose result holds the text of that very file, with nothing left unread (readInPart,
# hasMore, endReached false, unread PDF pages), contradicts it.
READ_WHOLE = {"status": "completed", "verification": "output_only",
              "observed": {"version": 1, "kind": "text", "reviewLabel": "recado.txt", "folder": "home", "characters": 36,
                           "totalLines": 2, "offset": 0, "lines": 2, "returnedCharacters": 36, "hasMore": False,
                           "endReached": True, "text": "Comprar pan.\r\nLlamar al dentista.\r\n"}}
READ_PART = {"status": "completed", "verification": "output_only",
             "observed": {"version": 1, "kind": "text", "reviewLabel": "recado.txt", "folder": "home",
                          "characters": 9000, "offset": 0, "returnedCharacters": 4000, "hasMore": True,
                          "nextOffset": 4000, "endReached": False, "readInPart": True, "text": "Comprar pan…"}}


@pytest.mark.parametrize("answer,flagged", [
    ("No leí recado.txt.", True),
    ("No pude leer recado.txt, así que no sé qué dice.", True),
    ("No he leído el archivo recado.txt todavía.", True),
    ("No logré leer BAXY-bench\\recado.txt.", True),
    ("No pude abrir recado.txt.", True),
    ("I couldn't read recado.txt.", True),
    ("I didn't read the file recado.txt.", True),
    ("Leí recado.txt: dice que compres pan y llames al dentista.", False),
    ("No leí todo, sólo el principio de recado.txt.", False),
    ("No leí notas.txt, sólo recado.txt.", False),  # another file
    ("No pude leer el resto de recado.txt.", False),  # not the file named right after the verb
    ("No pude leer recado.txt de Descargas.", False),  # a place that does not hold the one read
    ("No pude leer recado.txt de BAXY-bench.", True),
    ("¿No leí recado.txt?", False),
])
def test_a_file_said_not_read_that_a_result_of_the_turn_read_whole(answer: str, flagged: bool) -> None:
    read = _r("file.read", READ_WHOLE, {"path": "BAXY-bench/recado.txt"})
    assert ("read" in _rules(answer, [read], "léeme el recado.txt de BAXY-bench")) is flagged


@pytest.mark.parametrize("answer", [
    "No leí todo, sólo el principio.",
    "No leí recado.txt entero, sólo el principio.",
    "No pude leer recado.txt completo: es largo.",
    "No leí recado.txt.",
])
def test_a_file_read_only_in_part_may_be_said_not_read(answer: str) -> None:
    read = _r("file.read", READ_PART, {"path": "home/recado.txt"})
    assert "read" not in _rules(answer, [read], "léeme recado.txt")


def test_a_read_that_failed_or_brought_no_text_or_an_open_that_failed_may_be_said_not_read() -> None:
    failed = _r("file.read", {"status": "failed", "error": "known_text_encoding_unsupported",
                              "observed": {"reviewLabel": "recado.txt"}}, {"path": "home/recado.txt"})
    assert "read" not in _rules("No pude leer recado.txt: su codificación no se reconoce.", [failed])
    scanned = _r("file.read", {"status": "completed", "verification": "output_only", "observed": {
        "kind": "pdf", "reviewLabel": "boleta.pdf", "characters": 0, "hasMore": False, "endReached": True,
        "pages": 1, "textPages": 0, "hasText": False, "text": ""}}, {"path": "home/boleta.pdf"})
    assert "read" not in _rules("No pude leer boleta.pdf: no tiene texto.", [scanned])
    # Its text read and its window not opened: «no pude abrir» tells the open that failed.
    read = _r("file.read", READ_WHOLE, {"path": "home/recado.txt"})
    opened = _r("file.open", {"status": "failed", "error": "application_window_not_observed"},
                {"path": "home/recado.txt"})
    assert "read" not in _rules("No pude abrir recado.txt en pantalla, pero lo leí.", [read, opened])


@pytest.mark.parametrize("setting, checked", [(None, True), ("answer_check", False), ("answer_check,check_read", True)])
def test_the_read_rule_is_an_aid_of_its_own(tmp_path: Path, monkeypatch, setting, checked) -> None:
    if setting is None:
        monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    else:
        monkeypatch.setenv("BAXY_AYUDAS", setting)
    first = "No pude leer recado.txt, así que no sé qué dice."
    mind, server = _mind(tmp_path, [_call("file_read", {"path": "home/recado.txt"}), _say(first),
                                    _say("Dice: comprar pan y llamar al dentista.")])
    mind.wire_to_op = {"file_read": "file.read"}
    mind.risk = {**mind.risk, "file_read": "read_only"}
    mind.decide(1, "léeme recado.txt")
    result = mind.continue_turn(2, json.dumps(READ_WHOLE))
    assert (result["reply"] != first) is checked
    if checked:
        note = server.bodies[-1]["messages"][-1]["content"]
        assert "su resultado trae el texto entero de recado.txt" in note


# ---- an output told that no result shows (uso real 2026-10-26) -------------------------------------------------------
SENT = {"status": "completed", "verification": "delivered_only"}
NO_WINDOW = {"status": "failed", "error": "window_not_found"}


@pytest.mark.parametrize("answer,flagged", [
    ("Listo, el programa se ejecutó y salió «Hola mundo».", True),
    ("Lo corrí e imprimió «42».", True),
    ("Mandé el comando, pero no salió «Hola mundo» en nada que pudiera leer.", False),
    ("Mandé el comando; no pude ver su salida.", False),
])
def test_an_output_quoted_that_no_result_shows_is_flagged(answer: str, flagged: bool) -> None:
    receipts = [_r("shell.command.run", SENT, {"command": "python saludo.py"}),
                _r("window.resolve", NO_WINDOW)]
    assert ("output" in _rules(answer, receipts)) is flagged


def test_an_output_a_result_shows_is_not_flagged() -> None:
    receipts = [_r("shell.command.run", {"status": "completed", "verification": "output_only",
                                         "observed": {"stdout": "Hola mundo\r\n", "exitCode": 0}})]
    assert "output" not in _rules("Lo ejecuté y salió «Hola mundo».", receipts)


def test_what_a_call_wrote_is_not_an_output_it_shows() -> None:
    receipts = [_r("file.write", DONE, {"text": "print('Hola mundo')"}), _r("shell.command.run", SENT)]
    assert "output" in _rules("Lo ejecuté y salió «Hola mundo».", receipts)


# ---- a search engine named as the source that no result brings (R7-NB-3) ---------------------------------------------
def _searched(answered_by: str, results: list[dict] | None = None, source: str = "web") -> dict:
    return _r("web.search", {"status": "completed", "verification": "output_only", "observed": {
        "version": 1, "source": source, "query": "mechanical keyboards",
        "results": results or [{"title": "Mechanical Keyboards", "url": "https://mechanicalkeyboards.com/",
                                "snippet": "The Ultimate Mechanical Keyboard Catalog."}],
        "resultCount": 1, "answeredBy": answered_by}}, {"query": "mechanical keyboards"})


@pytest.mark.parametrize("answer,flagged", [
    ("Google me dio mechanicalkeyboards.com, además de un artículo de PCMag.", True),
    ("Google encontró mechanicalkeyboards.com con teclados mecánicos.", True),
    ("Bing found mechanicalkeyboards.com.", True),
    ("Busqué en Google y salió mechanicalkeyboards.com.", True),
    ("DuckDuckGo me dio mechanicalkeyboards.com.", False),
    ("Encontré mechanicalkeyboards.com, un catálogo de teclados.", False),
    ("No busqué en Google: respondió DuckDuckGo, con mechanicalkeyboards.com.", False),
    ("Pediste Google, pero me respondió DuckDuckGo: mechanicalkeyboards.com.", False),
    ("¿Quieres que lo abra en Google?", False),
])
def test_an_engine_named_that_did_not_answer_is_flagged(answer: str, flagged: bool) -> None:
    findings = [f for f in check(answer, "Search DuckDuckGo for mechanical keyboards", [_searched("DuckDuckGo")], [])
                if f["rule"] == "answered_by"]
    assert bool(findings) is flagged
    if flagged:
        assert "DuckDuckGo" in findings[0]["fact"]


def test_an_engine_a_result_brings_is_not_flagged() -> None:
    pixel = [{"title": "Google Pixel 10", "url": "https://store.google.com/pixel", "snippet": "El teléfono de Google."}]
    assert "answered_by" not in _rules("Google vende el Pixel 10 en su tienda.", [_searched("DuckDuckGo", pixel)])
    assert "answered_by" not in _rules("Según Google News, hubo tres noticias.", [_searched("Google News", source="news")])
    opened = _r("browser.navigate", {"status": "completed", "verification": "readback",
                                     "observed": {"host": "google.cl", "title": "lentejas"}})
    assert "answered_by" not in _rules("Abrí Google con lentejas y DuckDuckGo me dio mechanicalkeyboards.com.",
                                       [opened, _searched("DuckDuckGo")])


def test_an_engine_named_with_no_search_in_the_turn_is_not_read() -> None:
    assert "answered_by" not in _rules("Google te lo dice en un segundo.", [])
    assert "answered_by" not in _rules("Google es un buscador.", [_r("file.read", DONE)])


def test_the_mind_asks_again_when_the_answer_credits_an_engine_that_did_not_answer(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    first, second = "Google me dio mechanicalkeyboards.com.", "DuckDuckGo me dio mechanicalkeyboards.com."
    mind, server = _mind(tmp_path, [_call("web_search", {"query": "mechanical keyboards"}), _say(first), _say(second)])
    mind.wire_to_op = {"web_search": "web.search"}
    mind.risk = {**mind.risk, "web_search": "read_only"}
    mind.decide(1, "Search DuckDuckGo for mechanical keyboards")
    result = mind.continue_turn(2, _searched("DuckDuckGo")["observation"])
    assert result["reply"] == second
    note = server.bodies[-1]["messages"][-1]["content"]
    assert "lo respondió DuckDuckGo (answeredBy)" in note and "«Google»" in note


@pytest.mark.parametrize("answer", [
    "Si quieres, también lo busco en Bing.",
    "Respondió DuckDuckGo con mechanicalkeyboards.com. Google habría dado más.",
    "Encontré mechanicalkeyboards.com. Puedes ver más en YouTube.",
    "Te lo abro en Google Chrome si quieres.",
])
def test_an_engine_mentioned_but_not_credited_with_a_result_is_not_flagged(answer: str) -> None:
    assert "answered_by" not in _rules(answer, [_searched("DuckDuckGo")])


def test_the_query_a_result_echoes_does_not_bring_the_engine() -> None:
    searched = _searched("DuckDuckGo")
    searched["observation"] = searched["observation"].replace('"query": "mechanical keyboards"',
                                                              '"query": "google mechanical keyboards"')
    searched["arguments"] = {"query": "google mechanical keyboards"}
    assert "answered_by" in _rules("Google me dio mechanicalkeyboards.com.", [searched])


def test_an_odd_observation_or_several_sources_never_break_the_check() -> None:
    odd = _r("web.search", {"status": "completed", "verification": "output_only", "observed": ["x"]})
    assert _rules("Google me dio mechanicalkeyboards.com.", [odd]) == []
    findings = check("Google me dio mechanicalkeyboards.com.", "",
                     [_searched("DuckDuckGo"), _searched("Wikipedia", source="encyclopedia")], [])
    assert [f["fact"] for f in findings if f["rule"] == "answered_by"] == [
        "web_search: lo respondió DuckDuckGo, Wikipedia (answeredBy); ningún resultado de este turno viene de «Google»"]


# ---- a page told opened in a program the turn opened, while its result names another browser (encargo 70, F6) -------
# Uso real 03-11 21:20: «Abre Gmail.» → app_open «Google Chrome» (already running) → browser_navigate, whose result said
# browser «Opera GX» (the person's default) → «Listo, abrí Gmail en Chrome». The browser is read from the receipts only:
# the app the turn opened and the navigation's own «browser», never a list of browsers.
def _opened_app(name: str) -> dict:
    return _r("app.open", {**DONE, "observed": {"appId": name, "displayName": name, "alreadyRunning": True}},
              {"appId": name})


def _navigated(browser: str = "Opera GX", url: str = "https://mail.example.com/") -> dict:
    return _r("browser.navigate", {**DONE, "observed": {
        "version": 1, "requestedUrl": url, "finalUrl": url, "browser": browser, "browserFamily": "opera_gx",
        "authority": "user_browser_uia_address_postread"}}, {"url": url})


@pytest.mark.parametrize("answer,flagged", [
    ("Listo, abrí Gmail en Chrome.", True),
    ("Listo, abrí tu correo en Google Chrome.", True),
    ("Te dejé el correo abierto en el navegador Chrome.", True),
    ("Listo, abrí Gmail en Opera GX.", False),
    ("Abrí Chrome, pero el correo se abrió en Opera GX, tu navegador predeterminado.", False),
    ("Listo, abrí Gmail.", False),
    ("No lo abrí en Chrome.", False),
    ("Si quieres, te lo abro en Chrome.", False),
    ("¿Quieres que lo abra en Chrome?", False),
])
def test_a_page_told_opened_in_the_app_the_turn_opened_while_its_result_names_another_browser(
        answer: str, flagged: bool) -> None:
    findings = [f for f in check(answer, "Abre el correo.", [_opened_app("Google Chrome"), _navigated()], [])
                if f["rule"] == "browser"]
    assert bool(findings) is flagged
    if flagged:
        assert findings[0]["fact"] == ("browser_navigate: la página se abrió en Opera GX (browser de su resultado), "
                                       "no en Google Chrome; Google Chrome sólo se abrió con app_open")


def test_the_browser_the_page_did_open_in_is_never_flagged() -> None:
    # The app opened is the browser the page opened in (Opera GX, or Chrome by browser_navigate_named «chrome»).
    assert "browser" not in _rules("Abrí Gmail en Opera GX.", [_opened_app("Opera GX"), _navigated()])
    assert "browser" not in _rules("Abrí Gmail en Chrome.", [_opened_app("Google Chrome"), _navigated("chrome")])
    # No app opened in the turn, or a navigation that did not complete: nothing to set against the answer.
    assert "browser" not in _rules("Abrí Gmail en Chrome.", [_navigated()])
    failed = _r("browser.navigate", {"status": "failed", "error": "page_host_not_found",
                                     "observed": {"browser": "Opera GX"}})
    assert "browser" not in _rules("Abrí Gmail en Chrome.", [_opened_app("Google Chrome"), failed])


@pytest.mark.parametrize("answer,flagged", [
    # Held-out bench of encargo 70 (base model, AMD): app_open Chrome + browser_navigate (Opera GX) and these finals.
    ("Listo, abrí Chrome y entré a Facebook.", True),
    ("Listo, Chrome ya estaba abierto y ahora está en facebook.com.", True),
    ("Abrí Chrome y Facebook se abrió en Opera GX.", False),
    ("Abrí Chrome. Facebook quedó listo.", False),
    ("No abrí Chrome: entré a Facebook en tu navegador.", False),
])
def test_the_app_the_turn_opened_and_the_pages_site_told_together(answer: str, flagged: bool) -> None:
    receipts = [_opened_app("Google Chrome"), _navigated(url="https://www.facebook.com/")]
    assert ("browser" in _rules(answer, receipts)) is flagged


@pytest.mark.parametrize("address,name", [
    ("https://web.whatsapp.com/", "whatsapp"), ("https://www.tiktok.com", "tiktok"),
    ("https://ejemplo.com.ar/x", "ejemplo"), ("https://x.io/", ""),
])
def test_the_name_of_a_pages_site(address: str, name: str) -> None:
    from baxy_mind.answer_check import _site_name
    assert _site_name(address) == name


@pytest.mark.parametrize("app,answer", [
    ("Spotify", "Abrí Spotify y la canción ya suena en Spotify; la letra quedó en el navegador."),
    ("Bloc de notas", "Abrí la receta y la pegué en el Bloc de notas."),
    ("Google Chrome", "Lo busqué en Google y te dejé el video."),
])
def test_another_act_told_in_the_app_the_turn_opened_is_not_a_page_opened_there(app: str, answer: str) -> None:
    # Revisión del encargo 70: only an opening told in the clause of «en X» places the page there.
    assert "browser" not in _rules(answer, [_opened_app(app), _navigated()])


def test_the_mind_asks_again_when_the_answer_puts_the_page_in_another_browser(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    first, second = "Listo, abrí Gmail en Chrome.", "Listo, abrí Gmail en Opera GX."
    mind, server = _mind(tmp_path, [_call("app_open", {"appId": "Google Chrome"}),
                                    _call("browser_navigate", {"url": "https://mail.example.com/"}),
                                    _say(first), _say(second)])
    mind.wire_to_op = {"app_open": "app.open", "browser_navigate": "browser.navigate"}
    mind.risk = {**mind.risk, "app_open": "low_reversible", "browser_navigate": "low_reversible"}
    mind.decide(1, "Abre el correo.")
    mind.continue_turn(2, _opened_app("Google Chrome")["observation"])
    result = mind.continue_turn(3, _navigated()["observation"])
    assert result["reply"] == second
    note = server.bodies[-1]["messages"][-1]["content"]
    assert "se abrió en Opera GX" in note and "no en Google Chrome" in note


# ---- a send that stopped before Enter (uso real 2026-11-03, F1) -------------------------------------------------------
# 17:21 «Envíalo.» in Discord: message.send failed at the draft check, before Enter, and BAXY said «Le mandé el mensaje a
# …, pero no pude comprobar que llegó». Its result said only effectUncertain («sin confirmar»), which a sentence with its
# limit may tell. The App now says in typed fields that Enter was not pressed and nothing was sent (DesktopMessagingAdapter
# SendNotVerified): that result is a failure, never an unsure one, and the claim is contradicted, limit or not.
SEND_STOPPED_BEFORE = {"status": "failed", "error": "message_draft_not_verified", "cause": "external_effect_ambiguous",
                       "effectUncertain": True}
SEND_STOPPED = {**SEND_STOPPED_BEFORE, "observed": {"version": 1, "messageWritten": False, "enterPressed": False,
                                                    "sent": False, "stoppedAt": "draft_check", "displayName": "Letras"}}


@pytest.mark.parametrize("answer,flagged", [
    ("Le mandé el mensaje a Letras, pero no pude comprobar que llegó.", True),
    ("Listo, le envié el mensaje a Letras.", True),
    ("El mensaje se envió a Letras.", True),
    ("No le mandé el mensaje a Letras: no pude ver el texto en la caja de Discord.", False),
    ("No pude enviar el mensaje a Letras porque no vi el borrador.", False),
])
def test_a_send_stopped_before_enter_is_never_told_as_sent(answer: str, flagged: bool) -> None:
    receipt = _r("message.send", SEND_STOPPED, {"channel": "discord", "recipient": "Letras", "text": "ya voy"})
    assert receipt["outcome"] == "falló (message_draft_not_verified): el mensaje no se escribió ni se envió"
    assert ("not_completed" in _rules(answer, [receipt], "Envíalo.")) is flagged


def test_the_old_receipt_of_a_send_stopped_before_enter_let_the_claim_through() -> None:
    # What the turn of 17:21 had: «sin confirmar», and the sentence said its limit.
    receipt = _r("message.send", SEND_STOPPED_BEFORE)
    assert receipt["outcome"].startswith("sin confirmar")
    assert _rules("Le mandé el mensaje a Letras, pero no pude comprobar que llegó.", [receipt], "Envíalo.") == []


# Encargo 82 (vivo del 81, «Guardar como» 1/4): the path a file dialog saved to is in the click's receipt
# (fileDialog.path), and answers that told another folder passed the check (3 of 3 gave no finding).
def _saved_by_dialog(path: str) -> dict:
    return _r("input.visible.click", {"status": "completed", "verification": "readback", "observed": {
        "name": "Guardar", "kind": "Button", "fileDialog": {"closed": True, "path": path, "exists": True}}})


_ASKED_FOLDER = "usa Guardar como y guárdalo con el nombre lista_ceiba.txt en la carpeta ceiba_guardados de mis documentos"


@pytest.mark.parametrize("answer,path,rule", [
    # The three answers as the live runs wrote them, with invented names.
    ("Listo, lo guardé como lista_ceiba.txt en ceiba_guardados.", r"D:\Perfil\Documentos\borrador_ceiba.txt", "folder"),
    (r"Listo, lo guardé como lista_ceiba.txt en Documentos\CEIBA\lista_ceiba.txt.", r"D:\Perfil\Documentos\lista_ceiba.txt",
     "folder"),
    ("Lo guardé en Descargas.", r"D:\Perfil\Documentos\lista_ceiba.txt", "folder"),
    ("Lo guardé en la carpeta ceiba_guardados.", r"D:\Perfil\Documentos\lista_ceiba.txt", "folder"),
    # The answer names no place and the file is not in the folder the person named.
    ("Listo, lo guardé con ese nombre.", r"D:\Perfil\Documentos\lista_ceiba.txt", "asked_folder"),
])
def test_an_answer_that_tells_another_folder_than_the_file_dialog_saved_to(answer: str, path: str, rule: str) -> None:
    found = check(answer, _ASKED_FOLDER, [_saved_by_dialog(path)], None)
    assert rule in [f["rule"] for f in found]
    assert any(path in f["fact"] for f in found), "the fact says where the file is"


@pytest.mark.parametrize("answer,path", [
    ("Listo, lo guardé como lista_ceiba.txt en ceiba_guardados.", r"D:\Perfil\Documentos\ceiba_guardados\lista_ceiba.txt"),
    (r"Lo guardé en Documentos\ceiba_guardados\lista_ceiba.txt.", r"D:\Perfil\Documentos\ceiba_guardados\lista_ceiba.txt"),
    ("Listo, lo guardé con ese nombre.", r"D:\Perfil\Documentos\ceiba_guardados\lista_ceiba.txt"),
    # True of where it went, and said so.
    ("Listo, lo guardé como lista_ceiba.txt en borradores, que es la carpeta que sale en el diálogo.",
     r"D:\vivo\borradores\lista_ceiba.txt"),
    ("Lo guardé en Documentos, no en ceiba_guardados.", r"D:\Perfil\Documentos\lista_ceiba.txt"),
    ("No lo guardé en ceiba_guardados: quedó en Documentos.", r"D:\Perfil\Documentos\lista_ceiba.txt"),
    # A known folder said in Spanish, on a disk that names it in English.
    ("Lo guardé en Documentos.", r"C:\Users\ana\Documents\lista_ceiba.txt"),
    ("Lo guardé en la carpeta que pediste.", r"D:\Perfil\Documentos\ceiba_guardados\lista_ceiba.txt"),
])
def test_an_answer_true_of_where_the_file_dialog_saved_has_no_finding(answer: str, path: str) -> None:
    assert check(answer, _ASKED_FOLDER, [_saved_by_dialog(path)], None) == []


def test_a_dialog_that_saved_nothing_is_no_place() -> None:
    still_open = _r("input.visible.click", {"status": "failed", "error": "file_dialog_still_open", "observed": {
        "fileDialog": {"closed": False, "path": r"D:\Perfil\Documentos\lista_ceiba.txt"}}})
    assert "folder" not in _rules("Lo guardé en Descargas.", [still_open])


# ---- uso-90: the page the result opened, and BAXY's own words in the voice ----------------------------------------
# The receipt of diag-9dea c3-g10 (U06) as the App gave it: YouTube opened in Edge and its own dialog asks to sign in.
_SIGN_IN_WALL = {
    "status": "failed", "error": "page_requires_sign_in", "cause": "external_effect_ambiguous", "effectUncertain": True,
    "observed": {"version": 1, "openedUrl": "https://www.youtube.com/watch?v=v8F6yJt1ULo", "browser": "Microsoft Edge",
                 "pageDialog": "Sign in to confirm you’re not a bot", "signInLink": "Sign in",
                 "next": "nothing played: the page opened shows its own dialog «Sign in to confirm you’re not a bot» over "
                         "the video, and its link «Sign in» goes to a sign-in page; signing in is the person's own step, "
                         "with their account, and until then a click in that dialog or this call again plays nothing"}}
# diag-9dea c1-g10: the same call, with no dialog read, ended «unconfirmed» and named the page it opened.
_UNCONFIRMED = {"status": "failed", "error": "user_browser_playback_unconfirmed", "cause": "external_effect_ambiguous",
                "effectUncertain": True, "observed": {"openedUrl": "https://www.youtube.com/watch?v=v8F6yJt1ULo",
                                                      "browser": "Microsoft Edge"}}
_U06 = "Abre YouTube y búscame un video de cómo hacer pan casero."


@pytest.mark.parametrize("facts", [_SIGN_IN_WALL, _UNCONFIRMED])
def test_an_open_the_result_names_its_page_for_is_not_contradicted(facts: dict) -> None:
    # diag-9dea U06, 6 of 6: «Abrí YouTube en Edge, pero sale la ventana…» was flagged in every run (the call stayed
    # unsure), asked again twice, and once the second answer copied the note into the voice.
    played = _r("media.play.youtube", facts, {"query": "cómo hacer pan casero"})
    assert _rules("Abrí YouTube en Edge, pero sale la ventana de «Sign in to confirm you're not a bot»; tienes que entrar "
                  "con tu cuenta para que se reproduzca el video.", [played], _U06) == []
    # An unsure call whose result names no page it opened still contradicts a bare «abrí».
    bare = _r("media.play.youtube", {**facts, "observed": {"browser": "Microsoft Edge"}}, {"query": "pan casero"})
    assert _rules("Abrí YouTube en Edge.", [bare], _U06) == ["not_completed"]


def test_an_answer_that_carries_a_tool_name_or_a_result_code_is_flagged() -> None:
    played = _r("media.play.youtube", _SIGN_IN_WALL, {"query": "cómo hacer pan casero"})
    leaked = ("Abrí YouTube en Edge, pero sale la ventana de «Sign in to confirm you're not…», pero no se completó: "
              "media_play_youtube → sin confirmar (page_requires_sign_in): pudo o no ocurrir.")
    found = check(leaked, _U06, [played], [("media.play.youtube", False, False)])
    internal = [f for f in found if f["rule"] == "internal"]
    assert internal and "media_play_youtube" in internal[0]["fact"] and "page_requires_sign_in" in internal[0]["fact"]
    # A file name with an underscore is the person's, not BAXY's.
    trashed = _r("filesystem.known.trash.named", DONE, {"name": "borrador_viejo.txt"})
    assert "internal" not in _rules("Listo, borrador_viejo.txt quedó en la Papelera.", [trashed])


def test_a_second_answer_that_copies_the_note_is_never_spoken(tmp_path: Path, monkeypatch) -> None:
    # diag-9dea c3-g10 and diag-6f20 c4-g10: the second answer copied the check's fact, wire name and code included,
    # and it was spoken. The first answer, the model's own words before any note, is spoken instead.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    first = "Cerré Paint."
    copied = "Cerré Paint, pero no se completó: app_close → falló (window_not_found)."
    mind, server, result = _closing(tmp_path, first, copied)
    assert result["reply"] == first and len(server.bodies) == 3
    said = [m["content"] for m in mind.conversation if m["role"] == "assistant" and m.get("content")]
    assert said == [first]
    checks = [c for c in _trace(mind) if c["stage"] == "turn.check"]
    assert [c["round"] for c in checks] == [1, 2] and checks[1]["kept"] is False and checks[1].get("echo") is True


# ---- a display mode told as kept ----------------------------------------------------------------------------------------
# Uso real 04-11 (F24): twice «Windows la guarda para el próximo reinicio» with savedForRestart false.
def _mode(saved: bool) -> dict:
    observed = {"final": {"width": 1600, "height": 900, "refreshHz": 165}, "savedForRestart": saved}
    return _r("display.mode.set", {**DONE, "observed": observed if saved else {
        **observed, "savedMode": {"width": 1920, "height": 1080, "refreshHz": 60}}})


@pytest.mark.parametrize("answer,flagged", [
    ("Puse la pantalla en 1600x900; Windows la guarda para el próximo reinicio.", True),
    ("Listo, 1600x900 queda guardada.", True),
    ("Cambié a 1600x900 y quedó así para siempre.", True),
    ("Puse la pantalla en 1600x900, pero no quedó guardada: al reiniciar vuelve a 1920x1080.", False),
    ("Está en 1600x900 sólo por ahora; Windows tiene guardada 1920x1080.", False),
    ("Está a 165 Hz ahora, pero Windows lo guardó a 60 Hz.", False),
    ("Puse la pantalla en 1600x900.", False),
])
def test_a_mode_only_shown_told_as_kept(answer: str, flagged: bool) -> None:
    assert ("mode_not_saved" in _rules(answer, [_mode(False)])) is flagged


def test_a_mode_saved_by_the_call_after_it_is_kept() -> None:
    answer = "Listo, 1600x900 queda guardada."
    assert "mode_not_saved" not in _rules(answer, [_mode(False), _mode(True)])
    assert "mode_not_saved" not in _rules(answer, [_mode(True)])


# ---- what a look read is a reading --------------------------------------------------------------------------------------
# Uso real 04-11 (F30): the figures in vision.describe's text were «no está en los resultados», because a text past 400
# characters gave no number and a size written in a text had no unit, and the model's second round took out all it had
# read. The figures of a text the turn read are readings, however long; a figure nobody read still is not.
_LONG_LOOK = ("La diapositiva muestra una tabla de memoria. " + "Fila de relleno sin cifras. " * 20
              + "La primera fila dice 12,5 % de uso con 8 GB; la segunda, 27 % con 2 GB y la tercera 64.2% con 1024 MB.")


@pytest.mark.parametrize("answer,flagged", [
    ("La tabla dice 12,5 %, 27 % y 64,2 % de uso.", False),
    ("Las filas tienen 8 GB, 2 GB y 1024 MB.", False),
    ("La primera fila llega al 61 % de uso.", True),
    ("La primera fila tiene 32 GB.", True),
])
@pytest.mark.parametrize("op,key", [("vision.describe", "description"), ("screen.ocr.read", "text"),
                                    ("web.fetch", "text")])
def test_the_figures_of_a_long_text_read_are_readings(op: str, key: str, answer: str, flagged: bool) -> None:
    shot = _r("screen.capture", {**DONE, "observed": {"version": 1, "width": 3840, "height": 2160}})
    look = _r(op, {"status": "completed", "verification": "output_only", "observed": {key: _LONG_LOOK}})
    assert ("number" in _rules(answer, [shot, look])) is flagged


# Encargo 75 (R01): the last value of a table typed and never ended, told as put.
def _cell_receipt(cell: dict) -> dict:
    return {"op": "input.text.type", "tool": "input_text_type", "completed": True, "read": False, "arguments": {},
            "outcome": "enviado sin verificar",
            "observation": json.dumps({"status": "completed", "verification": "delivered_only", "observed": {"cell": cell}})}


def test_a_text_still_pending_in_a_cell_is_said_to_the_model():
    receipts = [_cell_receipt({"address": "F1", "value": "", "pendingText": "150"})]
    found = [f for f in check("Listo, en la fila 1 puse manzana con 120 y mango con 150.", "pon frutas", receipts, [])
             if f["rule"] == "pending_cell"]
    assert len(found) == 1
    assert "«150» sigue pendiente en la celda F1" in found[0]["fact"]


def test_a_cell_a_key_ended_says_nothing():
    receipts = [_cell_receipt({"address": "F1", "value": "", "pendingText": "150"}),
                {**_cell_receipt({"address": "G1", "value": ""}), "op": "input.key.press", "tool": "input_key_press"}]
    assert not [f for f in check("Listo, puse 150 en F1.", "pon frutas", receipts, []) if f["rule"] == "pending_cell"]


# ---- «abrí X» of an application that was already open (uso-106, F20) ---------------------------------------------------
@pytest.mark.parametrize("answer,flagged", [
    ("Abrí Steam, aunque seguía abierto de antes.", True),
    ("Listo, abrí Discord.", True),
    ("Discord ya estaba abierto, lo traje al frente.", False),
    ("No abrí nada: Steam ya estaba abierto.", False),
    ("Te dejo Steam al frente.", False),
])
def test_opened_is_not_said_of_what_was_already_open(answer: str, flagged: bool) -> None:
    assert ("already_open" in _rules(answer, [_opened_app("Steam")])) is flagged


def test_opened_is_said_of_what_this_call_started_or_of_another_act() -> None:
    started = _r("app.open", {**DONE, "observed": {"appId": "Steam", "alreadyRunning": False}}, {"appId": "Steam"})
    assert "already_open" not in _rules("Abrí Steam.", [started])
    assert "already_open" not in _rules("Abrí Gmail.", [_opened_app("Chrome"), _navigated()])
    assert "already_open" not in _rules("Abrí Steam.", [])


# ---- «no hay correos de X» after a read whose result says what it covered (uso-106, F2) --------------------------------
_COVERS = ("only the newest mail of the default Inbox of the account set up in Outlook on this PC; it searched no sender, "
           "subject nor other mail account")


def _latest_mail(covers: str | None = _COVERS) -> dict:
    observed = {"version": 1, "subject": "Aviso del mes", "sender": "Avisos Banco Andino <avisos@example.com>",
                "receivedUtc": "2026-11-04T11:12:00Z", "body": "Hola.", "readFrom": "Outlook"}
    if covers is not None:
        observed["covers"] = covers
    return _r("email.latest.read", {"status": "completed", "verification": "output_only", "observed": observed})


@pytest.mark.parametrize("answer,flagged", [
    ("No aparece ningún correo de Marta Ríos en Outlook.", True),
    ("No tienes correos de Marta Ríos; el último es de Avisos Banco Andino.", True),
    ("El último correo de tu bandeja es de Avisos Banco Andino, sobre el aviso del mes.", False),
    ("El último correo es de Avisos Banco Andino; no busqué correos de Marta Ríos.", False),
])
def test_an_absence_is_not_told_from_a_read_that_says_it_covered_one_mail(answer: str, flagged: bool) -> None:
    assert ("partial" in _rules(answer, [_latest_mail()])) is flagged


def test_a_read_that_says_no_scope_says_nothing_of_an_absence() -> None:
    assert "partial" not in _rules("No aparece ningún correo de Marta Ríos en Outlook.", [_latest_mail(None)])
    assert "partial" not in _rules("No aparece ningún correo de Marta Ríos en Outlook.", [_latest_mail("")])


# ---- what a turn says when its time ran out on the check ----------------------------------------------------------------
# Cosecha 05-11 (uso real con el modelo local): a turn of two minutes wrote its answer twice, and each time the check asked
# for it again; the second request ran out of its 24 s rereading a shrunk conversation, the App asks only once more, and
# the person heard nothing until they asked.
def _timed_out() -> TimeoutError:
    return TimeoutError("the request's time budget is spent")


def _looking_timed_out(tmp_path: Path, replies: list) -> tuple[Mind, object]:
    mind, server = _mind(tmp_path, [_call("input_visible_controls", {"application": "Steam"}), *replies])
    mind.wire_to_op = {"input_visible_controls": "input.visible.controls"}
    mind.decide(1, "entra a la biblioteca de steam")
    return mind, server


ABSENT = "No hay un botón «Biblioteca» en esa ventana."
ABSENT_AGAIN = "No veo ningún botón «Biblioteca»."


def test_a_check_past_its_time_is_asked_again_before_anything_is_spoken(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _looking_timed_out(tmp_path, [_say(ABSENT), _timed_out()])
    with pytest.raises(TimeoutError):  # the App asks once more (NativeTurnLoop, request_timed_out)
        mind.continue_turn(2, json.dumps(STEAM_VIEW))


def test_the_answer_in_hand_is_spoken_when_the_check_runs_out_of_the_last_request(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _looking_timed_out(tmp_path, [_say(ABSENT), _timed_out(), _say(ABSENT_AGAIN), _timed_out()])
    with pytest.raises(TimeoutError):
        mind.continue_turn(2, json.dumps(STEAM_VIEW))
    result = mind.continue_turn(3, json.dumps(STEAM_VIEW))
    assert result["reply"] == ABSENT_AGAIN
    assert mind.conversation[-1] == {"role": "assistant", "content": ABSENT_AGAIN}
    assert not any(str(m.get("content")).startswith(CHECK_NOTE[:20]) for m in mind.conversation)
    assert [r["kept"] for r in _trace(mind) if r["stage"] == "turn.check" and r.get("timed_out")] == [True]


def test_the_first_answer_is_spoken_when_the_last_request_writes_none(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _looking_timed_out(tmp_path, [_say(ABSENT), _timed_out(), _timed_out()])
    with pytest.raises(TimeoutError):
        mind.continue_turn(2, json.dumps(STEAM_VIEW))
    assert mind.continue_turn(3, json.dumps(STEAM_VIEW))["reply"] == ABSENT


def _found(monkeypatch, rule: str) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    monkeypatch.setattr("baxy_mind.mind.check_answer",
                        lambda *_, **__: [{"rule": rule, "said": "lo dicho", "fact": "lo que lo contradice"}])


def test_a_decision_with_no_call_has_no_second_request(tmp_path: Path, monkeypatch) -> None:
    # The App asks again only after a call that ran (NativeTurnLoop: calls > 1): a decision past its time is the last one.
    _found(monkeypatch, "partial")
    mind, _ = _mind(tmp_path, [_say("No está en lo que leí."), _timed_out()])
    assert mind.decide(1, "busca el dato")["reply"] == "No está en lo que leí."


@pytest.mark.parametrize("rule", ["not_completed", "no_call", "implied_yes", "pending_cell", "saved_name", "browser", "folder",
                                  "mode_not_saved", "already_open", "output", "internal", "number"])
def test_an_answer_found_saying_what_did_not_happen_is_not_spoken_for_lack_of_time(tmp_path: Path, monkeypatch, rule) -> None:
    _found(monkeypatch, rule)
    mind, _ = _looking_timed_out(tmp_path, [_say("Lo hice."), _timed_out(), _say("Ya lo hice."), _timed_out()])
    for request in (2, 3):
        with pytest.raises(TimeoutError):
            mind.continue_turn(request, json.dumps(STEAM_VIEW))
    mind, _ = _mind(tmp_path, [_say("Lo hice."), _timed_out()])
    with pytest.raises(TimeoutError):
        mind.decide(1, "hazlo")


def test_the_later_answer_is_the_one_held_back_when_a_request_wrote_two(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _looking_timed_out(tmp_path, [_say(ABSENT), _say(ABSENT_AGAIN), _timed_out(), _timed_out()])
    with pytest.raises(TimeoutError):
        mind.continue_turn(2, json.dumps(STEAM_VIEW))
    assert mind.continue_turn(3, json.dumps(STEAM_VIEW))["reply"] == ABSENT_AGAIN


def test_the_answer_held_back_is_spoken_when_the_last_request_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _looking_timed_out(tmp_path, [_say(ABSENT), _timed_out(), _say("")])
    with pytest.raises(TimeoutError):
        mind.continue_turn(2, json.dumps(STEAM_VIEW))
    assert mind.continue_turn(3, json.dumps(STEAM_VIEW))["reply"] == ABSENT


def test_a_last_request_with_no_answer_written_still_fails_as_it_did(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _looking_timed_out(tmp_path, [_timed_out(), _timed_out()])
    for request in (2, 3):
        with pytest.raises(TimeoutError):
            mind.continue_turn(request, json.dumps(STEAM_VIEW))


def test_a_turn_with_no_check_keeps_failing_as_it_did(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, _ = _looking_timed_out(tmp_path, [_timed_out(), _say("No pude entrar.")])
    with pytest.raises(TimeoutError):
        mind.continue_turn(2, json.dumps(STEAM_VIEW))
    assert mind.continue_turn(3, json.dumps(STEAM_VIEW))["reply"] == "No pude entrar."


# ---- findings that the reading does not back ------------------------------------------------------------------------------
# Cosecha 05-11: «no hay un botón con ese nombre» was read as a button called «con», which any page's text holds, and the
# rewrite it asked for took the turn past its time.
LONG_VIEW = {"status": "completed", "observed": {"window": "Curso", "controls": [
    {"index": 1, "kind": "Hyperlink", "name": "Tareas"}, {"index": 2, "kind": "Button", "name": "guardar"},
    {"index": 3, "kind": "Button", "name": "Iniciar sesión"}],
    "text": "Presentación 2 con nota sobre la entrega para el curso de este semestre"}}


@pytest.mark.parametrize("answer,flagged", [
    ("No pude abrirla: no hay un botón con ese nombre en la ventana.", False),
    ("No veo ninguna opción para la entrega.", False),
    ("No encuentro un enlace sobre eso.", False),
    ("No hay un botón Presentación en esa ventana.", True),  # a name, as the person reads it
    ("No veo ningún botón guardar.", True),  # lower case, and that control's whole name
    ("No hay un enlace llamado «Presentación 2».", True),
    ("No veo el botón iniciar sesión.", True),  # lower case, a control's name by its first word
])
def test_a_bare_word_after_button_is_a_name_only_when_it_reads_as_one(answer: str, flagged: bool) -> None:
    assert ("named_control" in _rules(answer, [_r("input.visible.controls", LONG_VIEW)])) is flagged


# Cosecha 05-11: assistant_status gives {"value": 4.78, "unit": "GB"}, and «4,78 GB» was told «ese número no está en los
# resultados» with that value beside it, three rounds of the check for a true answer.
OWN_STATUS = {"status": "completed", "videoMemory": {"value": 4.78, "unit": "GB"}, "ram": {"value": 2.9, "unit": "GB"}}


@pytest.mark.parametrize("answer,flagged", [
    ("Uso 4,78 GB de memoria de video y 2,9 GB de RAM.", False),
    ("Uso 4.8 GB de memoria de video y unos 3 GB de RAM.", False),  # rounded
    ("Uso 12 GB de memoria de video.", True),
    ("Uso 4,78 MB de memoria de video.", True),  # the value in another unit
])
def test_a_size_read_with_its_unit_beside_it(answer: str, flagged: bool) -> None:
    assert ("number" in _rules(answer, [_r("assistant.status", OWN_STATUS)])) is flagged
