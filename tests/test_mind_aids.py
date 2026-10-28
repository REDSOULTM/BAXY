"""The model aids of the mind (goal «ayudas al modelo», 2026-10-19): what they add to a result, that the trace keeps them
in a row apart from the model's decision, and that BAXY_AYUDAS=none gives back the mind as it was before them."""
import json
from pathlib import Path

import pytest

from baxy_mind.mind import Mind, field_note

from test_mind_final import _call, _mind, _say

CLOSE_FAILED = json.dumps({"status": "failed", "error": "window_not_found"})
OPENED = json.dumps({"status": "completed", "verification": "readback", "observed": {"applicationName": "Paint"}})


def _two_calls(tmp_path: Path) -> tuple[Mind, list[str]]:
    mind, server = _mind(tmp_path, [_call("app_open", {"appId": "Paint"}), _call("app_close", {"appId": "Paint"}),
                                    _say("No pude cerrar Paint.")])
    mind.decide(1, "abre paint y ciérralo")
    mind.continue_turn(2, OPENED)
    mind.continue_turn(3, CLOSE_FAILED)
    tools = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"]
    return mind, tools


def _trace(mind: Mind) -> list[dict]:
    return [json.loads(line) for line in mind.trace.read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("setting", ["all", "none"])
def test_the_turn_line_is_the_one_of_the_starting_product_with_or_without_aids(tmp_path: Path, monkeypatch,
                                                                             setting: str) -> None:
    # Lever 5a (turn_facts, the line parted into done and not done) was measured and left out: falsedades s0-1 2+4
    # with it against 2+2 without it, and «de mi carpeta de trabajo» in 3 confirmation questions only with it.
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    mind, tools = _two_calls(tmp_path)
    assert tools[1].endswith("\n[En este turno: app_open → completado y verificado; "
                             "app_close → falló (window_not_found)]")
    assert not [r for r in _trace(mind) if r["stage"] == "turn.aid"]


def test_the_cores_aids_are_traced_by_their_fields_and_never_change_the_result(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    calculator = json.dumps({"status": "failed", "error": "calculator_window_not_found",
                             "observed": {"next": "app_open can start the Calculator"}})
    mind, server = _mind(tmp_path, [_call("calculator_expression_evaluate", {"expression": "6*7"}),
                                    _say("Abro la Calculadora.")])
    mind.decide(1, "cuánto es 6 por 7 en la calculadora")
    mind.continue_turn(2, calculator)
    tool = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert tool.startswith(calculator + "\n")
    aid = [r for r in _trace(mind) if r["stage"] == "turn.aid"][0]
    assert aid["aids"] == {"calculator_next": {"next": "app_open can start the Calculator"}}
    # The model's own decision after the aid is its own row.
    assert _trace(mind)[-1]["stage"] == "turn.continue"


CLICK_UNSURE = json.dumps({"status": "failed", "error": "visible_surface_changed_while_waiting"})
CLICKED = json.dumps({"status": "completed", "observed": {"ok": True, "name": "TIENDA"}})


@pytest.mark.parametrize("setting,clicks,told", [("all", [CLICK_UNSURE, CLICK_UNSURE], 1), ("none", [CLICK_UNSURE], 0),
                                                 ("all", [CLICKED], 0)])
def test_a_click_that_fails_in_an_application_with_places_tells_them_once(tmp_path: Path, monkeypatch, setting: str,
                                                                          clicks: list[str], told: int) -> None:
    # Uso real 2026-10-20: seven clicks in Steam's web-drawn store while app_open opens its store and its search.
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    script = [_call("app_open", {"appId": "Steam"})] + [_call("input_visible_click", {"label": "TIENDA"})] * len(clicks)
    mind, server = _mind(tmp_path, [*script, _say("Listo.")])
    mind.decide(1, "abre steam y entra en la tienda")
    mind.continue_turn(2, OPENED)
    for index, click in enumerate(clicks):
        mind.continue_turn(3 + index, click)
    tools = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"]
    notes = [t for t in tools if "[Ayuda: Steam también se abre directo en sus lugares" in t]
    assert len(notes) == told
    if told:
        assert notes[0].endswith("place community, game (placeValue: el número del juego), library, "
                                 "results (placeValue: lo que se busca), store.]")
        assert [r for r in _trace(mind) if r["stage"] == "turn.aid"][0]["aids"]["app_places_next"].startswith("[Ayuda")
    else:
        assert not [r for r in _trace(mind) if r["stage"] == "turn.aid"]


def test_a_look_that_fails_after_another_windows_look_still_names_the_opened_applications_places(
        tmp_path: Path, monkeypatch) -> None:
    # Uso real 2026-10-21: Epic opened and pressed, then its look found no window and the model looked at the browser.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    not_found = json.dumps({"status": "failed", "error": "application_window_not_found"})
    looked = json.dumps({"status": "completed", "observed": {"ok": True}})
    script = [_call("app_open", {"appId": "Epic Games Launcher"}),
              _call("input_visible_controls", {"application": "Fortnite | Epic Games Store - Opera"}),
              _call("input_visible_controls", {"application": "Epic Games Launcher"}), _say("Listo.")]
    mind, server = _mind(tmp_path, script)
    mind.decide(1, "ahora en la app")
    mind.continue_turn(2, OPENED)
    mind.continue_turn(3, looked)
    mind.continue_turn(4, not_found)
    tool = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert tool.endswith("[Ayuda: Epic Games Launcher también se abre directo en sus lugares, sin pulsar: app_open con "
                         "appId «Epic Games Launcher» y place game (placeValue: el nombre del juego), results "
                         "(placeValue: lo que se busca), store.]")


LONG = "https://news.google.com/rss/articles/" + "CBMi" + "x" * 300 + "?oc=5"


@pytest.mark.parametrize("setting", ["all", "none"])
def test_a_long_address_reaches_the_model_as_a_short_reference_and_goes_back_whole(tmp_path: Path, monkeypatch,
                                                                                setting: str) -> None:
    # PLAN_GENERAL C1 (uso real 2026-10-20: ~500-token news addresses copied wrong, a 400 and a cut JSON).
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    found = json.dumps({"status": "completed", "observed": {"results": [
        {"title": "Lluvia en Santiago", "url": LONG}, {"title": "Corto", "url": "https://example.org/a"}]}})
    shown = "ref:r1" if setting == "all" else LONG
    mind, server = _mind(tmp_path, [_call("web_search", {"query": "clima"}), _call("web_fetch", {"url": shown}),
                                    _say("Listo.")])
    mind.decide(1, "el clima de mañana")
    fetched = mind.continue_turn(2, found)
    tool = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert (LONG in tool) is (setting == "none")
    assert ("ref:r1" in tool) is (setting == "all")
    assert "https://example.org/a" in tool
    assert fetched["arguments"]["url"] == LONG


def test_the_same_failed_call_a_second_time_is_told_once(tmp_path: Path, monkeypatch) -> None:
    # PLAN_GENERAL C2 (uso real: the same click 5-7 times with a look between each); holdout v4 (en vivo, «Biblioteca»
    # 7 times in Steam): a failure is told at the second, a completed call (the looks between) still at the third. The
    # aid alone: with same_call_closes the click after it does not run (test_mind_bucle.py).
    monkeypatch.setenv("BAXY_AYUDAS", "same_call_next")
    missed = json.dumps({"status": "failed", "error": "visible_button_not_found"})
    looked = json.dumps({"status": "completed", "observed": {"ok": True}})
    click, look = _call("input_visible_click", {"label": "FORTNITE"}), _call("input_visible_controls", {})
    mind, server = _mind(tmp_path, [click, look, click, look, click, look, click, _say("No pude.")])
    mind.decide(1, "busca fortnite ahí")
    for index, result in enumerate([missed, looked, missed, looked, missed, looked, missed]):
        mind.continue_turn(2 + index, result)
    tools = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"]
    told = [i for i, t in enumerate(tools) if "ya se llamó" in t]
    assert told == [2]
    assert "input_visible_click ya se llamó 2 veces en este turno" in tools[2]
    assert "app_open" not in tools[2]


def test_a_click_repeated_unchanged_in_an_application_with_places_names_them(tmp_path: Path, monkeypatch) -> None:
    # Holdout v4 (en vivo): «abre la biblioteca de Steam» opened Steam without a place and pressed «Biblioteca» 7 times.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    unchanged = json.dumps({"status": "failed", "error": "visible_button_postread_unchanged"})
    # The provider's own count from the second (WindowsVisibleControlAdapter.RepeatedUnchanged) is no other result.
    again = json.dumps({"status": "failed", "error": "visible_button_postread_unchanged",
                        "observed": {"unchangedInARow": 2, "next": "this click on «Biblioteca» changed nothing 2 times"}})
    opened = json.dumps({"status": "completed", "verification": "readback", "observed": {"applicationName": "Steam"}})
    click = _call("input_visible_click", {"label": "Biblioteca"})
    mind, server = _mind(tmp_path, [_call("app_open", {"appId": "Steam"}), click, click, _say("No cambió.")])
    mind.decide(1, "abre la biblioteca de steam")
    for index, result in enumerate([opened, unchanged, again]):
        mind.continue_turn(2 + index, result)
    last = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert "input_visible_click ya se llamó 2 veces en este turno" in last
    assert "Steam también se abre directo en sus lugares, sin pulsar: app_open con appId «Steam» y place " in last
    assert "library" in last.split("ya se llamó 2 veces")[1]


@pytest.mark.parametrize("views,told", [(["Cargando…", "Biblioteca", "Biblioteca · Tienda"], False),
                                        (["Cargando…"] * 3, True)])
def test_the_same_call_is_told_only_when_its_result_is_the_same_too(tmp_path: Path, monkeypatch, views: list[str],
                                                                    told: bool) -> None:
    # Al máximo 7.7: three looks at a window still loading, each with another view, were told «el mismo resultado».
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    look = _call("input_visible_controls", {"application": "steam"})
    mind, server = _mind(tmp_path, [look, look, look, _say("Ya cargó.")])
    mind.decide(1, "mira steam")
    for index, view in enumerate(views):
        mind.continue_turn(2 + index, json.dumps({"status": "completed", "view": f"window 1 Steam\n{view}",
                                                  "observed": {"elapsedMs": {"read": 300 + index}}}))
    last = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert ("ya se llamó 3 veces en este turno" in last) is told


@pytest.mark.parametrize("setting,still,told", [("all", False, 1), ("all", True, 0), ("all", None, 0), ("none", False, 0)])
def test_a_click_whose_label_left_the_screen_tells_the_field_may_have_the_cursor_once(
        tmp_path: Path, monkeypatch, setting: str, still: bool | None, told: int) -> None:
    # Uso real 2026-10-21 (e2e del notebook): Steam's «Buscar en la tienda» pressed four times, no typing.
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    observed = {"ok": True, "name": "Buscar"} | ({} if still is None else {"labelStillOnScreen": still})
    pressed = json.dumps({"status": "completed", "observed": observed})
    click = _call("input_visible_click", {"label": "Buscar en la tienda"})
    mind, server = _mind(tmp_path, [click, click, _say("Listo.")])
    mind.decide(1, "busca un juego en la tienda")
    mind.continue_turn(2, pressed)
    mind.continue_turn(3, pressed)
    tools = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"]
    notes = [t for t in tools if "tras el clic ya no se ve «Buscar en la tienda»" in t]
    assert len(notes) == told
    if told:
        assert "input_text_type" in notes[0]
        assert "no se comprobó si un campo tiene el cursor" in notes[0]
        assert [r for r in _trace(mind) if r["stage"] == "turn.aid"][0]["aids"]["field_focused_next"].startswith("[Ayuda")


@pytest.mark.parametrize("focused,says", [(True, "dio el foco del teclado a un campo de texto"),
                                          (None, "no se comprobó si un campo tiene el cursor")])
def test_the_field_note_tells_the_focus_only_as_the_click_result_shows_it(focused: bool | None, says: str) -> None:
    # Renew al máximo (w5): «el campo tiene ahora el cursor» was told with nothing in the result checking it.
    observed = {"ok": True, "labelStillOnScreen": False} | ({} if focused is None else {"focused": focused})
    note = field_note(json.dumps({"status": "completed", "observed": observed}), json.dumps({"label": "Buscar"}))
    assert says in note and "«Buscar»" in note
    assert "tiene ahora el cursor" not in note


def test_the_applications_with_places_are_named_from_the_data(tmp_path: Path) -> None:
    # PLAN_GENERAL A6 (uso real 2026-10-21: Epic had places in the data, but the hand-written sentences did not name it).
    mind, _ = _mind(tmp_path, [])
    mind.configure({"capabilities": [{"name": "app.open", "description": "Open an app.", "argumentsSchema": {
        "type": "object", "properties": {"appId": {"type": "string"}, "place": {"type": "string"}}}}]})
    tool = next(t for t in mind.tools if t["function"]["name"] == "app_open")["function"]
    texts = tool["description"] + tool["parameters"]["properties"]["place"]["description"]
    assert "{app_places}" not in texts
    for app in ("«Epic Games Launcher» (game, results, store)", "«Steam» (", "«Discord» (directs)", "«Configuración» ("):
        assert app in texts


def test_an_applications_own_volume_says_what_its_app_is_and_where_the_whole_pc_goes(tmp_path: Path) -> None:
    # Hallazgo 6 del notebook (27-10): «pon el volumen a 20» llamó audio_app_volume_set con app «PC»; el app de las dos
    # herramientas por aplicación no tenía descripción.
    mind, _ = _mind(tmp_path, [])
    app = {"type": "object", "properties": {"app": {"type": "string"}, "level": {"type": "integer"}}}
    mind.configure({"capabilities": [{"name": name, "description": "Volume.", "argumentsSchema": app}
                                     for name in ("audio.app.volume.set", "audio.app.volume.adjust")]})
    for wire, whole in (("audio_app_volume_set", "audio_volume"), ("audio_app_volume_adjust", "audio_volume_adjust")):
        tool = next(t for t in mind.tools if t["function"]["name"] == wire)["function"]
        assert tool["parameters"]["properties"]["app"]["description"].endswith(f"that is {whole}.")


SETTINGS_AND_TRASH = {"capabilities": [
    {"name": "system.settings.set", "description": "Set a setting.", "argumentsSchema": {"type": "object", "properties": {}}},
    {"name": "filesystem.known.trash.named", "description": "Delete by name.",
     "argumentsSchema": {"type": "object", "properties": {}}}]}


def _description(mind: Mind, wire: str) -> str:
    return next(t for t in mind.tools if t["function"]["name"] == wire)["function"]["description"]


@pytest.mark.parametrize("setting,modes,folder", [("modes_sentence", False, False),
                                                  ("person_folder_sentence", False, True), ("none", False, False)])
def test_a_sentence_aid_ends_its_tools_description_only_when_on(tmp_path: Path, monkeypatch, setting: str,
                                                                modes: bool, folder: bool) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    mind, _ = _mind(tmp_path, [])
    mind.configure(SETTINGS_AND_TRASH)
    settings, trash = _description(mind, "system_settings_set"), _description(mind, "filesystem_known_trash_named")
    assert settings.endswith("do not turn on the accessible mode in its place.") is modes
    assert trash.endswith("the one filesystem_list shows).") is folder


FILES_AND_GAMES = {"capabilities": [
    {"name": name, "description": f"{name}.", "argumentsSchema": {"type": "object", "properties": {}}}
    for name in ("file.open", "file.read", "file.find", "filesystem.list", "filesystem.search", "game.launch",
                 "game.installed.named", "app.close", "window.minimize")]}


@pytest.mark.parametrize("setting,on", [
    ("named_folder_theirs", {"file_open", "file_read", "file_find", "filesystem_list", "filesystem_search"}),
    ("read_find_split", {"file_read", "file_find"}),
    ("game_epic_look", {"game_launch", "game_installed_named"}),
    ("unsaved_not_read", {"app_close", "window_minimize"}),
    ("none", set())])
def test_the_dudas_sentence_aids_end_only_their_tools_descriptions(tmp_path: Path, monkeypatch, setting: str,
                                                                   on: set[str]) -> None:
    # Renew al máximo (w9-dudas): F009 and E020 (a folder of the person's named with BAXY taken for BAXY's own), E018
    # (file_read against file_find for a file's lines), F016 (an Epic game not in game_launch's Steam list). P1.1(b)
    # F024: «nada sin guardar» said after a close or a minimize with nothing read.
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    before, _ = _mind(tmp_path / "before", [])
    before.configure(FILES_AND_GAMES)
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    mind, _ = _mind(tmp_path, [])
    mind.configure(FILES_AND_GAMES)
    for cap in FILES_AND_GAMES["capabilities"]:
        wire = cap["name"].replace(".", "_")
        plain, told = _description(before, wire), _description(mind, wire)
        assert told.startswith(plain) and (told != plain) is (wire in on), wire
    if on:
        traced = [r for r in _trace(mind) if r["stage"] == "configure.aid"][0]["aids"]
        assert {tool.replace(".", "_") for tool in traced[setting]} == on


def test_two_aids_of_one_tool_add_their_sentences_in_order(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "named_folder_theirs,read_find_split")
    mind, _ = _mind(tmp_path, [])
    mind.configure(FILES_AND_GAMES)
    read = _description(mind, "file_read")
    assert "contains BAXY" in read and read.endswith("no file_find before it.")
    assert read.index("contains BAXY") < read.index("(totalLines), and it looks")


TEXT_TYPE = {"capabilities": [{"name": "input.text.type", "description": "Type a text.", "argumentsSchema": {
    "type": "object", "properties": {"text": {"type": "string"}, "replacing": {"type": ["string", "null"]},
                                     "window": {"type": ["integer", "null"]}}, "required": ["text"]}}]}


@pytest.mark.parametrize("setting", [None, "all", "none"])
def test_input_text_type_shows_replacing_with_or_without_aids(tmp_path: Path, monkeypatch, setting: str | None) -> None:
    # Práctica V5E061 («cámbialo, era el miércoles, no el martes»: the new text went in at the caret, after the old one):
    # the argument that changes one part of the text, and the sentence that says it, reach the model always (decision
    # bench v6-abierto ×3, 2026-10-25: 614.67 without them, 616.00 with them).
    if setting is None:
        monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    else:
        monkeypatch.setenv("BAXY_AYUDAS", setting)
    mind, _ = _mind(tmp_path, [])
    mind.configure(TEXT_TYPE)
    tool = next(t for t in mind.tools if t["function"]["name"] == "input_text_type")["function"]
    assert tool["description"].endswith(" To change one part of a text already written, pass replacing = that part and "
                                        "text = what goes in its place.")
    assert "exactly once" in tool["parameters"]["properties"]["replacing"]["description"]


TYPED = json.dumps({"status": "completed", "verification": "readback", "observed": {
    "ok": True, "delivered": True, "sentTo": {"title": "Sin título: Bloc de notas", "process": "Notepad"}}})
WRITTEN = json.dumps({"status": "completed", "verification": "readback", "observed": {
    "name": "prueba.txt", "fullPath": "C:\\Users\\ana\\proyectos\\prueba.txt", "created": True}})


@pytest.mark.parametrize("setting,typed,told", [("all", True, True), ("written_not_window", True, True),
                                                ("all", False, False), ("none", True, False)])
def test_a_file_written_after_typing_into_a_window_says_that_window_was_not_saved(
        tmp_path: Path, monkeypatch, setting: str, typed: bool, told: bool) -> None:
    # Falsedades F013: «guardé prueba.txt» with Notepad's tab still «Sin título» after file_write wrote the file.
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    calls = [_call("input_text_type", {"text": "prueba 123"})] if typed else []
    mind, server = _mind(tmp_path, [*calls, _call("file_write", {"relativePath": "proyectos/prueba.txt",
                                                                 "text": "prueba 123", "folder": "home"}),
                                    _say("Listo.")])
    mind.decide(1, "escribe prueba 123 y guárdalo en proyectos como prueba.txt")
    if typed:
        mind.continue_turn(2, TYPED)
    mind.continue_turn(3, WRITTEN)
    last = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    note = ("[Ayuda: file_write escribió C:\\Users\\ana\\proyectos\\prueba.txt directo en el disco, sin pasar por "
            "ninguna ventana: lo escrito antes en «Sin título: Bloc de notas» (Notepad) no se guardó con esta llamada.]")
    assert last.endswith(note) is told
    aids = [r for r in _trace(mind) if r["stage"] == "turn.aid"]
    assert ("written_not_window" in (aids[-1]["aids"] if aids else {})) is told


def test_a_file_write_that_failed_says_nothing_of_the_window() -> None:
    from baxy_mind.mind import written_note
    receipts = [{"tool": "input_text_type", "completed": True, "observation": TYPED}]
    assert written_note(json.dumps({"status": "failed", "error": "file_exists"}), receipts) == ""
    assert written_note(WRITTEN, [{**receipts[0], "completed": False}]) == ""
    assert "«Sin título: Bloc de notas»" in written_note(WRITTEN, receipts)


def test_a_message_stopped_before_it_was_written_is_never_told_as_sent() -> None:
    # Uso real 2026-10-21 (e2e del notebook): «le mandé el mensaje» after a send stopped at the person's draft.
    from baxy_mind.mind import _outcome
    stopped = json.dumps({"status": "failed", "error": "composer_has_person_draft", "effectUncertain": True,
                          "observed": {"version": 1, "messageWritten": False, "sent": False}})
    unsure = json.dumps({"status": "failed", "error": "message_delivery_not_verified", "effectUncertain": True})
    assert _outcome(stopped) == "falló (composer_has_person_draft): el mensaje no se escribió ni se envió"
    assert _outcome(unsure) == "sin confirmar (message_delivery_not_verified): pudo o no ocurrir"
    typed = json.dumps({"status": "failed", "error": "message_recipient_changed_before_enter", "effectUncertain": True,
                        "observed": {"version": 1, "messageWritten": True, "enterPressed": False, "sent": False}})
    assert _outcome(typed) == "falló (message_recipient_changed_before_enter): el mensaje quedó escrito y no se envió"


@pytest.mark.parametrize("verification,told", [
    ("readback", "completado y verificado"),
    ("unchanged", "ya estaba así antes de esta llamada: no hizo falta cambiar nada"),
    ("delivered_only", "enviado sin verificar: no se volvió a mirar si hizo efecto"),
    ("output_only", "completado: su resultado está arriba"),
    ("none", "terminó sin verificar su efecto"),
    (None, "terminó sin verificar su efecto"),
])
def test_a_completed_call_is_told_by_its_typed_verification_alone(verification: str | None, told: str) -> None:
    # Al máximo 8.2: «ya estaba así» (changed:false) was told «completado y verificado», and a verified result whose
    # observation did not fit (observedLimit omitted) «sin verificar»; the field names no longer decide it.
    from baxy_mind.mind import _outcome
    facts = {"status": "completed", "observedLimit": "omitted", "observed": {"changed": False, "delivered": True}}
    if verification is not None:
        facts["verification"] = verification
    assert _outcome(json.dumps(facts)) == told


def test_a_failed_act_read_again_after_it_tells_whether_what_was_asked_holds() -> None:
    # Al máximo 8.3 (notebook): the failure keeps its code; the reread after it says whether the state asked for holds.
    from baxy_mind.mind import _outcome
    reached = {"status": "failed", "error": "window_state_not_verified",
               "observed": {"stateAfter": {"state": "minimized", "requestedStateReached": True, "authority": "win32"}}}
    unsure = {"status": "failed", "error": "verification_failed", "effectUncertain": True,
              "observed": {"stateAfter": {"level": 40, "requestedStateReached": False}}}
    assert _outcome(json.dumps(reached)) == "falló (window_state_not_verified); releído después: quedó como se pidió"
    assert _outcome(json.dumps(unsure)) == ("sin confirmar (verification_failed): pudo o no ocurrir; releído después: "
                                            "no quedó como se pidió")
    assert _outcome(json.dumps({"status": "failed", "error": "x", "observed": {}})) == "falló (x)"


def test_a_retryable_call_that_did_nothing_is_never_told_as_maybe_done() -> None:
    # P2.15 (resultados honestos): «pending» is a retryable outcome; the kernel adds effectUncertain only when the effect
    # may have happened. Without it, «pudo o no ocurrir» told a call that did nothing as maybe done, and one that stayed
    # unsure lost its code (the clicks read back unchanged or unread, a text not read back: all the same words).
    from baxy_mind.mind import _outcome
    # The volume's retryable failure to keep its state when nothing was applied (AudioVolumeHandler.ProviderFailure).
    nothing = json.dumps({"status": "pending", "error": "audio_reconciliation_required", "cause": "state_unavailable"})
    unsure = json.dumps({"status": "failed", "error": "visible_click_postread_unread", "effectUncertain": True})
    assert _outcome(nothing) == "no se completó (audio_reconciliation_required)"
    assert _outcome(unsure) == "sin confirmar (visible_click_postread_unread): pudo o no ocurrir"
    assert _outcome(json.dumps({"status": "failed", "effectUncertain": True})) == "sin confirmar: pudo o no ocurrir"


def test_a_not_found_tells_whether_other_places_were_searched() -> None:
    # Renew al máximo (w8): «ni en ningún otro lugar que revisé» after a file_open whose result said searchedElsewhere false.
    from baxy_mind.mind import _outcome
    only_there = {"status": "failed", "error": "file_not_found",
                  "observed": {"seenElsewhere": [], "searchedElsewhere": False}}
    cut = {"status": "failed", "error": "file_not_found", "observed": {"seenElsewhere": [], "searchComplete": False}}
    whole = {"status": "failed", "error": "file_not_found", "observed": {"seenElsewhere": [], "searchComplete": True}}
    assert _outcome(json.dumps(only_there)) == (
        "falló (file_not_found); sólo se miró la ruta nombrada: no se buscó en ningún otro lugar")
    assert _outcome(json.dumps(cut)) == (
        "falló (file_not_found); la búsqueda en otros lugares no se completó: lo no visto puede estar ahí")
    assert _outcome(json.dumps(whole)) == "falló (file_not_found)"


def test_an_act_in_a_window_tells_what_its_after_view_shows() -> None:
    # Al máximo 7.1 (notebook): the click's receipt brings the window after it; with entries omitted it is not whole.
    from baxy_mind.mind import _outcome
    def told(after: dict) -> str:
        return _outcome(json.dumps({"status": "completed", "verification": "delivered_only", "observed": {"after": after}}))
    assert told({"same": True}) == "enviado sin verificar: no se volvió a mirar si hizo efecto; la ventana no cambió"
    assert told({"changed": [{"index": 3}]}).endswith("; su after es la ventana de después")
    assert told({"changed": [], "omitted": 4}) == "enviado sin verificar: no se volvió a mirar si hizo efecto"


def test_a_read_says_it_only_looked_and_changed_nothing() -> None:
    # Auditoría de falsedades (F002, 9 of 9 runs of pc-t2): «¿abriste Spotify?» → window_application_status, told
    # «completado: lectura», answered «Sí, Spotify está abierto». A call of a read risk says it only looked; an
    # output_only call that may change things (shell_command_run) does not.
    from baxy_mind.mind import OUTPUT_READ, _outcome
    read = json.dumps({"status": "completed", "verification": "output_only",
                       "observed": {"displayName": "Spotify", "hasVisibleWindow": True}})
    assert _outcome(read, read=True) == OUTPUT_READ
    assert "sin abrir, cerrar ni cambiar nada" in OUTPUT_READ and "completado" not in OUTPUT_READ
    assert _outcome(read) == "completado: su resultado está arriba"


def test_an_application_already_running_is_told_as_not_opened_by_this_call() -> None:
    # Auditoría de falsedades (F002): app_open of an application already open is not «lo abrí».
    from baxy_mind.mind import _outcome
    opened = {"status": "completed", "verification": "readback", "observed": {"appId": "Spotify", "alreadyRunning": True}}
    assert _outcome(json.dumps(opened)) == "completado y verificado; ya estaba abierta antes de esta llamada"
    opened["observed"]["alreadyRunning"] = False
    assert _outcome(json.dumps(opened)) == "completado y verificado"


def test_a_completed_result_the_app_could_not_read_keeps_its_code() -> None:
    from baxy_mind.mind import _outcome
    unread = json.dumps({"status": "completed", "verification": "none", "error": "result_unreadable"})
    assert _outcome(unread) == "terminó sin verificar su efecto (result_unreadable)"


def test_a_read_in_a_turn_is_told_by_the_risk_the_app_sent(tmp_path: Path) -> None:
    # The risk comes from the catalog the App configured; the queued call after a read still runs (it completed).
    mind, server = _mind(tmp_path, [_call("window_application_status", {"name": "Spotify"}), _say("No lo abrí yo.")])
    mind.configure({"capabilities": [{"name": "window.application.status", "risk": "read_only",
                                      "argumentsSchema": {"type": "object", "properties": {}}}]})
    mind.decide(1, "¿abriste Spotify?")
    mind.continue_turn(2, json.dumps({"status": "completed", "verification": "output_only",
                                      "observed": {"hasVisibleWindow": True}}))
    tool = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert tool.endswith("[En este turno: window_application_status → lectura: sólo miró, sin abrir, cerrar ni "
                         "cambiar nada]")


def test_the_apps_place_owner_is_traced_and_reaches_the_model_as_it_came(tmp_path: Path, monkeypatch) -> None:
    # Renew al máximo (w7, apps): the App opened «Configuración» at sound instead of «Configuración del sistema»
    # (SaidApplication.cs); the trace keeps it as the aid place_owner, and the model reads the result untouched.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    note = ("the person did not name Configuración del sistema, and sound is a place of Configuración alone: this call "
            "opened Configuración at sound instead of Configuración del sistema, as it was written")
    opened = json.dumps({"status": "completed", "observed": {"appId": "Configuración"}, "placeOwner": note},
                        ensure_ascii=False)
    mind, server = _mind(tmp_path, [_call("app_open", {"appId": "Configuración del sistema", "place": "sound"}),
                                    _say("Abrí Configuración en Sonido.")])
    mind.decide(1, "abre la configuración de sonido")
    mind.continue_turn(2, opened)
    tool = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert note in tool
    aid = [r for r in _trace(mind) if r["stage"] == "turn.aid"][0]
    assert aid["aids"] == {"place_owner": note}


def test_the_apps_said_folder_refusal_is_traced_and_reaches_the_model_as_it_came(tmp_path: Path, monkeypatch) -> None:
    # Renew al máximo (w6, rutas): the App refused a write that left out the folder the person named (SaidFolders.cs);
    # the trace keeps it as the aid said_folder, and the model reads the result untouched.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    refused = json.dumps({"status": "rejected", "error": "said_folder_left_out", "saidFolders": ["C:/perfil/obra"],
                          "next": "nothing ran: call file_write again with relativePath \"obra/lista.txt\""},
                         ensure_ascii=False)
    mind, server = _mind(tmp_path, [_call("file_write", {"relativePath": "lista.txt", "text": "x", "folder": "home"}),
                                    _say("Lo guardo en obra.")])
    mind.decide(1, "guarda lista.txt en la carpeta obra")
    mind.continue_turn(2, refused)
    tool = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert tool.startswith(refused + "\n")
    aid = [r for r in _trace(mind) if r["stage"] == "turn.aid"][0]
    assert aid["aids"] == {"said_folder": {"saidFolders": ["C:/perfil/obra"], "next": json.loads(refused)["next"]}}


def test_the_same_window_read_with_a_new_handle_each_time_is_the_same_result(tmp_path: Path, monkeypatch) -> None:
    # Holdout v5 (en vivo, «maximiza Paint»): 13 window.resolve after the maximize, each with the same window but a new
    # single-use windowId (WindowsWindowControlProvider.Issue), so no read was «the same call with the same result».
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    resolve = _call("window_resolve", {"applicationName": "Paint"})
    mind, server = _mind(tmp_path, [resolve, resolve, resolve, _say("Paint quedó maximizado.")])
    mind.decide(1, "maximiza paint")
    for index, handle in enumerate(["0" * 32, "1" * 32, "a" * 32]):
        mind.continue_turn(2 + index, json.dumps({"status": "completed", "verification": "output_only", "observed": {"windows": [
            {"windowId": f"win_{handle}", "title": "Sin título - Paint", "state": "maximized"}], "count": 1}}))
    last = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert "window_resolve ya se llamó 3 veces en este turno" in last


MESSAGE_SCHEMA = {"type": "object", "properties": {"channel": {"type": "string", "enum": ["discord", "whatsapp"]},
                                                   "recipient": {"type": "string"}, "text": {"type": "string"}},
                  "required": ["channel", "recipient", "text"]}
MESSAGES = {"capabilities": [{"name": name, "description": "Write to someone.", "argumentsSchema": MESSAGE_SCHEMA}
                             for name in ("message.draft", "message.send")]}


@pytest.mark.parametrize("wire", ["message_draft", "message_send"])
def test_a_message_tool_says_the_channel_is_the_persons_and_words_for_someone_with_them_are_said(
        tmp_path: Path, wire: str) -> None:
    # Feria 2026-10-27 (a greeting asked for someone in the room drafted a WhatsApp message by a channel nobody named;
    # decision bench 0/9): the model reads that the channel is one the person named, and that words for someone with
    # them, with no channel named, are said in its reply, not written to a client.
    mind, _ = _mind(tmp_path, [])
    mind.configure(MESSAGES)
    tool = next(t for t in mind.tools if t["function"]["name"] == wire)["function"]
    assert "say them yourself in your reply" in tool["description"]
    channel = tool["parameters"]["properties"]["channel"]["description"]
    assert "never one they did not name" in channel and "ask them which" in channel


def test_a_relative_volume_change_says_its_amount_when_no_number_was_said(tmp_path: Path) -> None:
    # P2.38 (noche 28-10): «sube el volumen» sin cantidad quedaba entre actuar y preguntar «¿Cuánto le subo?» (audio 0,21
    # a 0,57 en la primera decisión según el prompt); amount es obligatorio y su descripción sólo hablaba de un número dicho.
    mind, _ = _mind(tmp_path, [])
    schema = {"type": "object", "properties": {"amount": {"type": "integer"}, "direction": {"type": "string"}}}
    mind.configure({"capabilities": [{"name": name, "description": "Volume.", "argumentsSchema": schema}
                                     for name in ("audio.volume.adjust", "audio.app.volume.adjust")]})
    for wire in ("audio_volume_adjust", "audio_app_volume_adjust"):
        tool = next(t for t in mind.tools if t["function"]["name"] == wire)["function"]
        assert tool["parameters"]["properties"]["amount"]["description"].endswith("or 10 when they said no number.")


def test_the_arguments_left_to_guess_say_what_the_code_does_with_them(tmp_path: Path) -> None:
    # R13-PC-3 (noche 28-10): tres decisiones que fallaban en todas las corridas o al filo. Un nombre de varias palabras
    # se partía («la carpeta X del Y», como «fotos del escritorio» del ejemplo); ante «¿lo compré?» sin tienda dicha
    # preguntaba la tienda, que es opcional y cuyo valor por omisión nadie le decía; y ante un título de nota preguntaba
    # cuál, sin saber que el título que no existe no borra nada y vuelve con los parecidos si los hay (TitleNotFoundFacts).
    mind, _ = _mind(tmp_path, [])
    schema = {"type": "object", "properties": {"name": {"type": "string"}, "store": {"type": "string"},
                                               "title": {"type": "string"}}}
    mind.configure({"capabilities": [{"name": name, "description": "Tool.", "argumentsSchema": schema}
                                     for name in ("file.compress", "game.entitlement.named", "note.trash")]})
    tools = {t["function"]["name"]: t["function"] for t in mind.tools}
    assert "all its words" in tools["file_compress"]["parameters"]["properties"]["name"]["description"]
    assert tools["game_entitlement_named"]["parameters"]["properties"]["store"]["description"].endswith(
        "(Steam is looked up) rather than asking.")
    assert "did I buy it" in tools["game_entitlement_named"]["description"]
    assert "deletes nothing" in tools["note_trash"]["description"]
