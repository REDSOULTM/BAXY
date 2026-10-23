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


def test_an_absolute_path_that_no_result_shows() -> None:
    home = _written(r"C:\Users\ana\notas.txt")
    assert _rules(r"Lo guardé en C:\Users\ana\notas.txt.", [home]) == []
    # Both say it: the folder named (Documentos) and the path no result shows.
    assert set(_rules(r"Creé notas.txt en C:\Users\ana\Documentos\notas.txt.", [home])) == {"folder"}
    assert _rules(r"Está en C:\Users\ana\Proyectos\x.txt.", [home]) == ["folder"]


def test_a_place_asked_for_and_not_reached_told_as_done_in_no_place() -> None:
    # E024: «añade … en la carpeta BAXY-bench» written in the home folder, told as done.
    home = _written(r"C:\Users\ana\notas.txt")
    request = "agrega una línea con «comprar pan» a notas.txt, en la carpeta BAXY-bench"
    assert _rules("Listo, agregué «comprar pan» a notas.txt.", [home], request) == ["asked_folder"]
    # Naming where it went is literally true (F013, doubtful by hand): left to the person.
    assert _rules(r"Listo, lo agregué en C:\Users\ana\notas.txt.", [home], request) == []


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
    assert _rules("Abrí el Bloc de notas; ya estaba abierto, así que lo traje al frente.", [running]) == []


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


def test_a_second_answer_that_still_contradicts_is_spoken_and_traced(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server, result = _closing(tmp_path, "Cerré Paint.", "Listo, cerré Paint.")
    assert result["reply"] == "Listo, cerré Paint." and len(server.bodies) == 3  # decide, first, second: no loop
    assert [c["kept"] for c in _trace(mind) if c["stage"] == "turn.check" and c["round"] == 2] == [True]


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
