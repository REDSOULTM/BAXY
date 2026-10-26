"""System One al máximo (2026-10-22): what «corrige» counts as founded, what layer 0 holds and which risks it corrects.
Each test holds one finding of the flow audit on the practice cases of decision2 (P040, P112, P113, P124, P203, P215)."""
import math

import pytest

from test_mind_doubt_policy import FakeSystemOne, _call, _mind, _say

FOLDERS = ["all_known", "desktop", "documents", "downloads", "home"]
FILE_FIND = {"name": "file.find", "description": "Find files", "risk": "read_only",
             "argumentsSchema": {"type": "object", "properties": {"folder": {"type": "string", "enum": FOLDERS},
                                                                  "query": {"type": "string"}},
                                 "required": ["folder"], "additionalProperties": False}}
FILE_READ = {"name": "file.read", "description": "Read a file", "risk": "read_only",
             "argumentsSchema": {"type": "object", "properties": {"fileName": {"type": "string"},
                                                                  "folder": {"type": "string", "enum": FOLDERS}},
                                 "required": ["fileName", "folder"], "additionalProperties": False}}
APP_OPEN = {"name": "app.open", "description": "Open an application", "risk": "low_reversible",
            "argumentsSchema": {"type": "object", "properties": {"appId": {"type": "string"}}, "required": ["appId"],
                                "additionalProperties": False}}
GAME_LAUNCH = {"name": "game.launch", "description": "Launch a game", "risk": "low_reversible",
               "argumentsSchema": {"type": "object", "properties": {"appId": {"type": "string"}},
                                   "required": ["appId"], "additionalProperties": False}}
WINDOW_RESOLVE = {"name": "window.resolve", "description": "Find a window", "risk": "read_only",
                  "argumentsSchema": {"type": "object", "properties": {"query": {"type": "string"}},
                                      "required": [], "additionalProperties": False}}
WINDOW_SNAP = {"name": "window.snap", "description": "Snap a window", "risk": "low_reversible",
               "argumentsSchema": {"type": "object", "properties": {"side": {"type": "string",
                                                                             "enum": ["left", "right"]},
                                                                    "windowId": {"type": "string"}},
                                   "required": ["side", "windowId"], "additionalProperties": False}}
CATALOGS = {"applicationCatalog": {"names": ["Microsoft Teams", "Spotify"]},
            "gameCatalog": {"entries": [{"provider": "steam", "appId": "327030", "name": "Worms W.M.D"},
                                        {"provider": "steam", "appId": "570", "name": "Dota 2"}]}}


def _corrects(tmp_path, monkeypatch, capabilities, doubted, choice, filled):
    """Qwen chose `doubted` unsure (0.5, under the veto), Laya reads `choice`, and the model fills it with `filled`."""
    monkeypatch.setenv("BAXY_S1_DOUBT", "")
    monkeypatch.setenv("BAXY_S1_VETO", "0.6")
    monkeypatch.setenv("BAXY_S1_CORRECT", "1")
    monkeypatch.setenv("BAXY_DATA_DIR", str(tmp_path))  # no confirmation-mode file: the kernel's normal mode
    reply = _call(doubted, {}, 0.5)
    reply["choices"][0]["logprobs"]["content"][5]["top_logprobs"].append({"token": "x", "logprob": math.log(0.4)})
    mind, server = _mind(tmp_path, [reply, _say("¿Qué quieres exactamente?")])
    server.complete_name = lambda prompt, written: "_y"
    fills: list[str] = []

    def fill_call(body, wire):
        fills.append(wire)
        return {"name": wire, "arguments": filled, "timings": {}}

    server.fill_call = fill_call
    mind.configure({"capabilities": capabilities, **CATALOGS})
    mind.system_one = FakeSystemOne(choice)  # type: ignore[assignment]
    return mind, fills


# ---- 1. _founded: the catalog's own values count -----------------------------------------------------------------
@pytest.mark.parametrize("filled", [{"fileName": "contrato", "folder": "downloads"},
                                    {"fileName": "contrato.pdf", "folder": "downloads"}])
def test_a_correction_with_an_enum_code_and_a_said_file_name_runs(tmp_path, monkeypatch, filled) -> None:
    # P203: «resúmeme el PDF contrato que está en Descargas»; Qwen file_find, Laya file_read at 0.91, and «corrige» asked
    # in 7 of 26 runs because «downloads» is a code the person never says.
    mind, fills = _corrects(tmp_path, monkeypatch, [FILE_FIND, FILE_READ], "file_find", "file_read", filled)
    result = mind.decide(1, "resúmeme el PDF contrato que está en Descargas")
    assert fills == ["file_read"]
    assert result["kind"] == "action" and result["operation"] == "file.read" and result["arguments"] == filled


@pytest.mark.parametrize("filled", [{"fileName": "informe.pdf", "folder": "downloads"},  # a name nobody said
                                    {"fileName": "contrato.docx", "folder": "downloads"}])  # an extension nobody said
def test_a_correction_with_a_file_name_or_folder_nobody_said_asks(tmp_path, monkeypatch, filled) -> None:
    mind, _ = _corrects(tmp_path, monkeypatch, [FILE_FIND, FILE_READ], "file_find", "file_read", filled)
    assert mind.decide(1, "resúmeme el PDF contrato que está en Descargas")["operation"] is None


@pytest.mark.parametrize("choice, filled, operation", [
    ("app_open", {"appId": "Microsoft Teams"}, "app.open"),
    ("game_launch", {"appId": "327030"}, "game.launch"),
    ("app_open", {"appId": "Zoom"}, None),  # not in the list it was given
    ("app_open", {"appId": "Microsoft"}, None),  # part of an entry
    ("game_launch", {"appId": "999"}, None)])  # an appId of no listed game
def test_a_correction_with_an_application_or_game_of_the_catalog_runs(tmp_path, monkeypatch, choice, filled,
                                                                         operation) -> None:
    # The doubted call reads (read_only), so a correction that is not founded asks.
    mind, _ = _corrects(tmp_path, monkeypatch, [FILE_FIND, APP_OPEN, GAME_LAUNCH], "file_find", choice, filled)
    assert mind.decide(1, "abre el teams o el worms")["operation"] == operation


def test_an_invented_window_id_still_asks_beside_an_enum_code(tmp_path, monkeypatch) -> None:
    # B-MED-1 stays closed: «left» is the enum's, «1» is an id no result listed.
    mind, fills = _corrects(tmp_path, monkeypatch, [WINDOW_RESOLVE, WINDOW_SNAP], "window_resolve", "window_snap",
                            {"side": "left", "windowId": "1"})
    assert mind.decide(1, "pon la ventana a la izquierda")["operation"] is None
    assert fills == ["window_snap"]


# ---- 2. Layer 0 does not hold what is reversible ----------------------------------------------------------------
@pytest.mark.parametrize("risk, operation", [("low_reversible", "app.open"),  # its error is undone; the kernel verifies
                                             ("read_only", None), ("work_loss", None), ("privacy_sensitive", None),
                                             ("", None)])  # a catalog without the risk holds as before
def test_layer_0_holds_an_unsure_call_unless_it_is_low_reversible(tmp_path, monkeypatch, risk, operation) -> None:
    # 26 runs of decision2 with System One (2026-10-22): layer 0 held low_reversible calls 23 times, 22 of them right
    # without System One (P040 ×7, P085 ×15) and none useful.
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.4")
    mind, _ = _mind(tmp_path, [_call("app_open", {"appId": "Discord"}, 0.3), _say("¿Qué abro?")])
    mind.risk = {"app_open": risk}
    assert mind.decide(1, "abre discord")["operation"] == operation


@pytest.mark.parametrize("doubted, choice, filled, operation", [
    ("app_open", "responder_con_palabras", {}, "app.open"),  # P124: Laya said «answer in words»; the call runs
    ("app_open", "file_find", {"folder": "music"}, "app.open"),  # it cannot be corrected (not founded): it runs
    ("app_open", "game_launch", {"appId": "327030"}, "game.launch"),  # what it can correct, it still corrects
    ("file_find", "responder_con_palabras", {}, None)])  # read_only still asks
def test_layer_2_corrects_a_low_reversible_call_or_lets_it_run(tmp_path, monkeypatch, doubted, choice, filled,
                                                                 operation) -> None:
    # The same 26 runs: layer 2 asked instead of 11 low_reversible calls right without System One (P112 ×4, P124 ×6,
    # P113 ×1) and none useful; its corrections of them, 6 useful (P257) against 2 harmful.
    mind, _ = _corrects(tmp_path, monkeypatch, [APP_OPEN, GAME_LAUNCH, FILE_FIND], doubted, choice, filled)
    assert mind.decide(1, "abre el teams")["operation"] == operation


# ---- 3. «corrige» puts in the model's mouth what the kernel will confirm --------------------------------------------
def _risky(name: str, risk: str, argument: str) -> dict:
    return {"name": name, "description": name, "risk": risk,
            "argumentsSchema": {"type": "object", "properties": {argument: {"type": "string"}},
                                "required": [argument], "additionalProperties": False}}


PACKAGE_UNINSTALL = _risky("package.uninstall", "work_loss", "packageId")
GAME_UNINSTALL = _risky("game.uninstall.named", "work_loss", "title")
NOTE_TRASH = _risky("note.trash", "recoverable_delete", "noteId")
PACKAGE_INSTALL = _risky("package.install", "installation", "packageId")
SYSTEM_POWER = {"name": "system.power", "description": "Power", "risk": "work_loss",
                "argumentsSchema": {"type": "object", "properties": {"action": {"type": "string",
                                                                                "enum": ["restart", "shutdown"]}},
                                    "required": ["action"], "additionalProperties": False}}
CALENDAR = _risky("calendar.event.create", "external_communication", "title")
# Decisión del dueño 2026-10-25: the own game library goes without a yes though the catalog labels it installation or
# work_loss (RiskPolicy.UnaskedDespiteTheirRisk), so «corrige» never puts it in the model's mouth.
GAME_INSTALL = _risky("game.install.named", "installation", "title")
GAME_CANCEL = _risky("game.install.cancel", "work_loss", "appId")
RISKY = [PACKAGE_UNINSTALL, GAME_UNINSTALL, NOTE_TRASH, PACKAGE_INSTALL, SYSTEM_POWER, CALENDAR, GAME_INSTALL,
         GAME_CANCEL, GAME_LAUNCH]  # the games list


@pytest.mark.parametrize("choice, filled, operation", [
    ("game_uninstall_named", {"title": "Worms W.M.D"}, "game.uninstall.named"),  # P215: work_loss, from the catalog
    ("note_trash", {"noteId": "worms"}, "note.trash"),  # recoverable_delete
    ("package_install", {"packageId": "worms"}, "package.install"),  # installation
    ("system_power", {"action": "shutdown"}, None),  # work_loss in the catalog, but the kernel runs it without asking
    ("calendar_event_create", {"title": "worms"}, None),  # external_communication: the kernel asks for only some
    ("game_install_named", {"title": "Worms W.M.D"}, None),  # installation, but the kernel runs it without asking
    ("game_install_cancel", {"appId": "worms"}, None),  # work_loss, but the kernel runs it without asking
    ("game_uninstall_named", {"title": "Age of Empires"}, None)])  # still founded or nothing (B-MED-1)
def test_in_normal_mode_a_correction_the_kernel_confirms_arrives_as_the_action(tmp_path, monkeypatch, choice, filled,
                                                                                operation) -> None:
    # P215 «desinstala el Worms»: Qwen doubted package_uninstall, Laya read game_uninstall_named at 0.91, and work_loss was
    # not correctable: a vague question (3 runs) instead of the kernel's confirmation, which names the exact action.
    mind, _ = _corrects(tmp_path, monkeypatch, RISKY, "package_uninstall", choice, filled)
    result = mind.decide(1, "desinstala el Worms")
    assert result["operation"] == operation
    if operation:
        assert result["kind"] == "action" and result["arguments"] == filled


@pytest.mark.parametrize("mode", ["bypass", "Bypass\n", "all", None])  # None: a file that cannot be read
def test_in_bypass_a_confirmed_risk_is_not_corrected(tmp_path, monkeypatch, mode) -> None:
    # RiskPolicy.Evaluate: Bypass allows everything but message.send, so a work_loss correction would run unasked.
    mind, fills = _corrects(tmp_path, monkeypatch, RISKY, "package_uninstall", "game_uninstall_named",
                            {"title": "Worms W.M.D"})
    if mode is None:
        (tmp_path / "confirmation-mode").mkdir()
    else:
        (tmp_path / "confirmation-mode").write_text(mode, encoding="utf-8")
    assert mind.decide(1, "desinstala el Worms")["operation"] is None
    assert fills == []


@pytest.mark.parametrize("mode", ["normal", "risk-aware", "otra cosa"])
def test_a_normal_mode_file_corrects_like_no_file(tmp_path, monkeypatch, mode) -> None:
    mind, _ = _corrects(tmp_path, monkeypatch, RISKY, "package_uninstall", "game_uninstall_named",
                        {"title": "Worms W.M.D"})
    (tmp_path / "confirmation-mode").write_text(mode, encoding="utf-8")
    assert mind.decide(1, "desinstala el Worms")["operation"] == "game.uninstall.named"


# ---- 4. «corrige» lands on a read with the effects the model's own call already had ---------------------------------
def _network(name: str, risk: str, properties: dict, required: list) -> dict:
    return {"name": name, "description": name, "risk": risk, "effects": ["network"],
            "argumentsSchema": {"type": "object", "properties": properties, "required": required,
                                "additionalProperties": False}}


WEB_SEARCH = _network("web.search", "read_only", {"query": {"type": "string"}}, ["query"])
WEATHER = _network("weather.current", "read_only", {"location": {"type": ["null", "string"]}}, [])
SHELL = _network("shell.command.run", "low_reversible", {"command": {"type": "string"}}, ["command"])
NETWORK = [WEB_SEARCH, WEATHER, SHELL, FILE_FIND]


@pytest.mark.parametrize("doubted, choice, filled, text, operation", [
    # P169: Qwen web_search, Laya weather_current at 0.9; both send out of the PC, and 5.1 asked in every seed.
    ("web_search", "weather_current", {}, "forecast this week please", "weather.current"),
    ("web_search", "weather_current", {"location": "Curicó"}, "el pronóstico de la semana en Curico",
     "weather.current"),
    ("web_search", "weather_current", {"location": "Santiago"}, "forecast this week please",
     None),  # an optional value nobody said is never sent out of the PC
    ("file_find", "weather_current", {}, "forecast please", None)])  # the model's call stayed in the PC
def test_a_correction_to_a_read_with_the_effects_of_the_chosen_call_runs(tmp_path, monkeypatch, doubted, choice,
                                                                          filled, text, operation) -> None:
    mind, fills = _corrects(tmp_path, monkeypatch, NETWORK, doubted, choice, filled)
    result = mind.decide(1, text)
    assert result["operation"] == operation
    if operation:
        assert result["kind"] == "action" and result["arguments"] == filled
    else:
        assert fills in ([], [choice])


AUDIO_APP = {"name": "audio.app.volume.set", "description": "Set an app's volume", "risk": "low_reversible",
             "argumentsSchema": {"type": "object", "properties": {"app": {"type": "string"},
                                                                  "level": {"type": "integer"}},
                                 "required": ["app", "level"], "additionalProperties": False}}
AUDIO = {"name": "audio.volume", "description": "Set the PC's volume", "risk": "low_reversible",
         "argumentsSchema": {"type": "object", "properties": {"level": {"type": "integer"}}, "required": ["level"],
                             "additionalProperties": False}}


@pytest.mark.parametrize("words, operation", [("ponle volumen hasta el setenta que no escucho el video", "audio.volume"),
                                              ("set the volume to seventy please", "audio.volume"),
                                              ("ponle volumen hasta el 70", "audio.volume"),
                                              ("ponle volumen hasta el sesenta", "audio.app.volume.set")])
def test_a_number_said_in_words_founds_a_correction(tmp_path, monkeypatch, words, operation) -> None:
    # Holdout v5 E062 (dictado): Laya chose audio_volume at 0.86 for «hasta el setenta», but «70» was not in the words,
    # the correction was unfounded and Qwen's app volume for «video» ran and failed in both seeds.
    mind, _ = _corrects(tmp_path, monkeypatch, [AUDIO_APP, AUDIO], "audio_app_volume_set", "audio_volume", {"level": 70})
    assert mind.decide(1, words)["operation"] == operation


# ---- 4. Layer 2 lets a look run where the decision model's action would land ----------------------------------------
LOOK = {"name": "input.visible.controls", "description": "Look at a window's controls", "risk": "read_only",
        "effects": ["window_input"], "argumentsSchema": {"type": "object", "properties": {}, "required": [],
                                                          "additionalProperties": False}}
KEY = {"name": "input.key.press", "description": "Press a key", "risk": "low_reversible", "effects": ["window_input"],
       "argumentsSchema": {"type": "object", "properties": {"key": {"type": "string", "enum": ["escape"]}},
                           "required": ["key"], "additionalProperties": False}}


@pytest.mark.parametrize("doubted, choice, operation", [
    # Holdout v6 V6E024 (final5): «hit the C button» on the calculator; Qwen looked first (0.42), Laya read a key press
    # (0.90) it does not fill, and BAXY asked «¿Quieres que presione la tecla C?». Holdout v5 V5E023 («agrega al final» in
    # the Notepad open): the same hold before typing in 10 runs, every one a question and no step.
    ("input_visible_controls", "input_key_press", "input.visible.controls"),
    ("web_search", "shell_command_run", "web.search"),  # the search sends out of the PC as the command would
    ("input_visible_controls", "web_search", None),  # the look stays in the PC; the search would not
    ("file_find", "responder_con_palabras", None)])  # a read with no effect still asks
def test_layer_2_lets_a_read_run_where_the_choice_would_land(tmp_path, monkeypatch, doubted, choice, operation) -> None:
    mind, fills = _corrects(tmp_path, monkeypatch, [LOOK, KEY, *NETWORK], doubted, choice, {"key": "escape"})
    result = mind.decide(1, "on the calculator, hit the C button to clear what's on the display")
    assert result["operation"] == operation
    assert fills == []  # nothing with an effect of the catalog is put in the model's mouth
