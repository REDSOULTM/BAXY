"""Aid «check_stale_state» (encargo 56): an answer that tells how something of the PC is now («ya está instalado», «sigue
sonando», «ya se descargó») in a turn where nothing read it, while the last result of that thing in the conversation shows
another state («queued», 0 of 0 bytes; «paused») or did not complete. The model is asked once more with that result and
keeps its tools, so it may look with the tool that reads it; never a reply. A state read in the turn, one the last result
shows, a question, a negation, a doubt or a chat with nothing of the PC behind it are not checked."""
import json
from pathlib import Path

import pytest

from baxy_mind.answer_check import check
from baxy_mind.mind import CHECK_NOTE, STATE_NOTE, Mind
from test_answer_check import _r
from test_mind_aids import _trace
from test_mind_final import _call, _mind, _say

INSTALL = {"status": "completed", "verification": "readback", "observed": {
    "version": 1, "jobId": "steam_job_x", "appId": "4200001", "name": "Velo Arena", "state": "queued",
    "bytesDownloaded": 0, "bytesTotal": 0,
    "next": 'game_install_status {"appId":"4200001","title":"Velo Arena"} reads its progress later'}}
INSTALLED = {"status": "completed", "verification": "output_only", "observed": {
    "version": 1, "appId": "4200001", "name": "Velo Arena", "state": "installed", "bytesDownloaded": 900,
    "bytesTotal": 900}}
PAUSED = {"status": "completed", "verification": "readback", "observed": {"playbackStatus": "paused",
                                                                          "title": "Canción de prueba"}}


def _stale(answer: str, earlier: list[dict], receipts: list[dict] | None = None, request: str = "") -> list[dict]:
    session = [(r["op"], r["completed"], r["read"]) for r in [*earlier, *(receipts or [])]]
    return [f for f in check(answer, request, receipts or [], session, earlier=[*earlier, *(receipts or [])])
            if f["rule"] == "stale_state"]


def test_installed_said_with_no_read_while_the_last_result_says_queued_is_contradicted() -> None:
    queued = _r("game.install.named", INSTALL)
    found = _stale("Ya está instalado, listo para jugar.", [queued], request="avísame cuando esté instalado")
    assert len(found) == 1
    assert found[0]["said"].startswith("Ya está instalado")
    assert "game_install_named" in found[0]["fact"] and "queued" in found[0]["fact"]
    assert "bytesDownloaded 0" in found[0]["fact"]
    # Its own next, the call that reads it, is told with it.
    assert 'game_install_status {"appId":"4200001","title":"Velo Arena"}' in found[0]["fact"]
    # The same end said as an act that completed long ago is a state too.
    assert _stale("Sí, ya se descargó.", [queued], request="¿ya terminó de bajar?")
    assert _stale("Ya terminó de descargarse.", [queued])


def test_a_state_the_last_result_shows_or_a_read_of_the_turn_is_not_checked() -> None:
    queued = _r("game.install.named", INSTALL)
    read = _r("game.install.status", INSTALLED)
    read["read"] = True
    assert not _stale("Ya está instalado.", [queued, read])
    assert not _stale("Ya está instalado.", [queued], receipts=[read])
    # What the result shows, said as it is.
    assert not _stale("Todavía no está instalado: quedó en cola.", [queued])
    assert not _stale("No sé si ya está instalado; ¿quieres que lo mire?", [queued])
    assert not _stale("¿Ya está instalado?", [queued])
    assert not _stale("Te aviso cuando esté instalado.", [queued])


def test_playing_said_while_the_last_result_says_paused_is_contradicted() -> None:
    paused = _r("media.play", PAUSED)
    assert _stale("Sí, sigue sonando.", [paused], request="¿sigue sonando?")
    assert not _stale("Está en pausa.", [paused])


def test_a_radio_said_on_or_connected_while_its_result_says_otherwise_is_contradicted() -> None:
    # Held-out of encargo 56 (H4, H5): «prendido» is «encendido», and «se conectó» a state reached.
    radio = _r("bluetooth.radio.set", {"status": "failed", "error": "radio_state_unchanged", "effectUncertain": True})
    assert _stale("Sí, el Bluetooth ya está prendido.", [radio], request="¿ya quedó prendido el bluetooth?")
    wifi = _r("wifi.radio.set", {"status": "completed", "verification": "readback",
                                 "observed": {"radio": "on", "connected": False, "connectionState": "connecting"}})
    assert _stale("Ya se conectó, tienes internet de nuevo.", [wifi])
    on = _r("bluetooth.radio.set", {"status": "completed", "verification": "readback", "observed": {"state": "On"}})
    assert not _stale("Sí, el Bluetooth está prendido.", [on])


def test_a_last_result_that_did_not_complete_backs_no_state() -> None:
    failed = _r("app.open", {"status": "failed", "error": "app_launch_timeout"})
    assert _stale("Sí, ya está abierto.", [failed], request="¿ya está abierto?")
    opened = _r("app.open", {"status": "completed", "verification": "readback", "observed": {"windowId": "w1"}})
    assert not _stale("Sí, ya está abierto.", [opened])
    # A look that failed is what the answer may tell.
    looked = _r("input.visible.controls", {"status": "rejected", "error": "screen_disabled_by_owner"})
    assert not _stale("No pude: está desactivado.", [looked])


def test_a_failure_whose_code_or_fields_tell_the_state_is_a_reading_of_it() -> None:
    # Banco diag-fd2b (F13, 6 of 6): memory_save failed with memory_disabled and the answer said so; the rule counted that
    # failure as «nothing read it», and its note led the model to turn the owner's memory on unasked.
    disabled = _r("memory.save", {"status": "failed", "error": "memory_disabled"})
    request = "guarda en tu memoria que de chiquito me decían «Chispa», ese era mi apodo"
    assert not _stale("No pude guardarlo: la memoria de BAXY está apagada.", [], receipts=[disabled], request=request)
    assert not _stale("Sigue desactivada: la memoria está apagada.", [disabled])
    # The same shape of other things: the code's end names the state («app_not_running», «steam_game_not_installed»).
    assert not _stale("No hizo falta: Spotify ya está cerrado.", [],
                      receipts=[_r("app.close", {"status": "failed", "error": "app_not_running"})])
    assert not _stale("No lo desinstalé: ya está desinstalado.", [],
                      receipts=[_r("game.uninstall.named", {"status": "failed", "error": "steam_game_not_installed"})])
    # Or a field of the failure says it.
    assert not _stale("No pude conectarme: el wifi está apagado.", [], receipts=[
        _r("wifi.connect", {"status": "failed", "error": "connect_failed", "observed": {"enabled": False}})])
    # A failure that names another state, a denied one or none still backs nothing.
    assert _stale("Sí, la memoria está encendida.", [disabled])
    assert _stale("Ya está instalado.", [_r("game.install.named", {"status": "failed", "error": "download_not_completed"})])
    assert _stale("Ya está encendido.", [_r("system.settings.set", {"status": "failed", "error": "input_never_enabled"})])


def test_a_call_waiting_for_the_persons_yes_tells_nothing_of_the_state() -> None:
    # uso-87 (diag-bc8c F13, 2 of 6 turns mute; 5 of 10 seeds on 8483): memory_save failed with memory_disabled, then
    # memory_enable waited for the «sí» (needs_confirmation, effectStarted false) and the answer told the state the
    # failure read before asking. The rule took the call that waited as the last result of the memory, «no se ejecutó, y
    # en este turno nada lo leyó»; nothing ran there, so the state is the one read before it.
    disabled = _r("memory.save", {"status": "failed", "error": "memory_disabled"})
    waiting = _r("memory.enable", {"status": "needs_confirmation", "effectStarted": False, "next": "nothing ran: ask"})
    request = "guarda en tu memoria que de chiquito me decían «Chispa», ese era mi apodo"
    for said in ("No puedo guardar eso todavía: mi memoria está apagada, ¿lo enciendo?",
                 "La memoria está desactivada. ¿Quieres que la encienda?"):
        assert not _stale(said, [], receipts=[disabled, waiting], request=request)
        # So in a later turn, while it still waits or after a «no».
        assert not _stale(said, [disabled, waiting])
    # What the last result before it read still contradicts the opposite state.
    found = _stale("Ya está encendida la memoria, ¿guardo el apodo?", [], receipts=[disabled, waiting])
    assert len(found) == 1 and "memory_save" in found[0]["fact"] and "memory_enable" not in found[0]["fact"]
    # With nothing before the call that waits, nothing says the state.
    assert not _stale("La memoria está encendida.", [], receipts=[waiting])


def test_a_chat_with_nothing_of_that_kind_behind_it_is_not_checked() -> None:
    queued = _r("game.install.named", INSTALL)
    assert not _stale("El museo está cerrado los lunes.", [queued])
    assert not _stale("En el motor, las dos válvulas están cerradas en la compresión.", [])


def test_a_result_whose_body_was_left_out_says_nothing() -> None:
    queued = _r("game.install.named", INSTALL)
    queued["observation"] = None
    assert not _stale("Ya está instalado.", [queued])


# ---- the mind --------------------------------------------------------------------------------------------------------
def _configured(tmp_path: Path, replies: list) -> tuple[Mind, object]:
    mind, server = _mind(tmp_path, replies)
    mind.configure({"capabilities": [
        {"name": "game.install.named", "description": "Instala un juego.", "risk": "low_reversible",
         "argumentsSchema": {"type": "object", "properties": {"title": {"type": "string"}}}},
        {"name": "game.install.status", "description": "Lee el estado de una instalación.", "risk": "read_only",
         "argumentsSchema": {"type": "object", "properties": {"appId": {"type": "string"},
                                                              "title": {"type": "string"}}}}]})
    return mind, server


SAID = "Ya está instalado, listo para jugar."


def _installing(tmp_path: Path, then: list) -> tuple[Mind, object]:
    mind, server = _configured(tmp_path, [_call("game_install_named", {"title": "Velo Arena"}),
                                          _say("Quedó en cola, sin descargar todavía."), *then])
    mind.decide(1, "instálame Velo Arena")
    mind.continue_turn(1, json.dumps(INSTALL))
    return mind, server


def test_the_stale_state_is_asked_again_once_with_the_last_result_and_may_look(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _installing(tmp_path, [_say(SAID), _call("game_install_status",
                                                              {"appId": "4200001", "title": "Velo Arena"})])
    result = mind.decide(2, "avísame cuando esté instalado")
    assert result["kind"] == "action" and result["operation"] == "game.install.status"
    note = server.bodies[-1]["messages"][-1]
    assert note["role"] == "user" and note["content"].startswith(STATE_NOTE[:40])
    assert f"«{SAID[:20]}" in note["content"] and "queued" in note["content"]
    assert "tool_choice" not in server.bodies[-1]  # it may use the tool that reads it
    assert not any(SAID in str(m.get("content")) or str(m.get("content")).startswith(STATE_NOTE[:20])
                   for m in mind.conversation)
    checks = [r for r in _trace(mind) if r["stage"] == "turn.check"]
    assert checks[0]["round"] == 1 and checks[0]["findings"][0]["rule"] == "stale_state"


def test_the_last_result_is_read_after_the_conversation_left_its_body_out(tmp_path: Path, monkeypatch) -> None:
    # Measured with the real model (encargo 56): with the owner's history the conversation was trimmed and the install's
    # body left out (COMPACTED); the check must still read what that result said, and a kept session too.
    from baxy_mind.mind import COMPACTED
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _installing(tmp_path, [_say(SAID), _say("No lo he mirado desde que quedó en cola.")])
    for message in mind.conversation:
        if message["role"] == "tool":
            message["content"] = COMPACTED
    kept = mind.export_session()
    mind.new_session()
    mind.load_session(kept)
    result = mind.decide(2, "avísame cuando esté instalado")
    assert result["reply"] != SAID
    assert "queued" in server.bodies[-1]["messages"][-1]["content"]


MEMORY_OFF = {"status": "failed", "error": "memory_disabled",
              "next": "memory_enable {} asks the person whether to turn BAXY's memory on"}
ENABLE_HELD = {"status": "needs_confirmation", "effectStarted": False,
               "next": "nothing ran: ask the person whether to do it; their answer goes in confirm_pending"}
OFFER = "No puedo guardar eso todavía: mi memoria está apagada, ¿lo enciendo?"


def _memory_held(tmp_path: Path, answers: list) -> tuple[Mind, object, dict]:
    """diag-bc8c F13 as the App drives it: memory_save fails with memory_disabled, memory_enable waits for the «sí»,
    and that result goes back final (NativeTurnLoop: HasPendingConfirmation), so a call after it would not run."""
    mind, server = _mind(tmp_path, [_call("memory_save", {"value": "de chiquito me decían Chispa"}),
                                    _call("memory_enable", {}), *answers])
    mind.configure({"capabilities": [
        {"name": name, "description": name, "risk": risk, "argumentsSchema": {"type": "object", "properties": {}}}
        for name, risk in (("memory.save", "low_reversible"), ("memory.enable", "high_reversible"),
                           ("memory.status", "read_only"))]})
    mind.decide(1, "guarda en tu memoria que de chiquito me decían «Chispa», ese era mi apodo")
    mind.continue_turn(1, json.dumps(MEMORY_OFF))
    return mind, server, mind.continue_turn(1, json.dumps(ENABLE_HELD), final=True)


def test_the_offer_after_a_call_held_for_the_yes_is_spoken_as_the_model_wrote_it(tmp_path: Path, monkeypatch) -> None:
    # uso-87: the state it tells is the one memory_save read; the note asked it to look, it called memory_status after
    # the App's final, and the turn ended with no words (decision_unavailable_after_call).
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server, result = _memory_held(tmp_path, [_say(OFFER), _call("memory_status", {})])
    assert result["kind"] == "conversation" and result["reply"] == OFFER
    assert not [r for r in _trace(mind) if r["stage"] == "turn.check"]


def test_a_check_note_never_gives_the_tools_back_to_a_turn_the_app_closed(tmp_path: Path, monkeypatch) -> None:
    # uso-87, defence in depth: whatever a rule finds in the answer of a turn the App closed (a call waiting for the «sí»,
    # the steps or the time spent, the engine down), a call after its final does not run; the model writes its answer
    # again in words, told only what the results show, and with nothing written its first answer is spoken.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    false_state = "Ya está encendida la memoria, ¿guardo el apodo?"
    mind, server, result = _memory_held(tmp_path, [_say(false_state), _say("¿Enciendo la memoria para guardarlo?")])
    assert result["kind"] == "conversation" and result["reply"] == "¿Enciendo la memoria para guardarlo?"
    body = server.bodies[-1]
    assert body["tool_choice"] == "none"
    assert body["messages"][-1]["content"].startswith(CHECK_NOTE[:40])
    first = next(r for r in _trace(mind) if r["stage"] == "turn.check")
    assert first["round"] == 1 and first["findings"][0]["rule"] == "stale_state"
    (tmp_path / "vacia").mkdir()
    mind, server, result = _memory_held(tmp_path / "vacia", [_say(false_state), _say("")])
    assert result["kind"] == "conversation" and result["reply"] == false_state


@pytest.mark.parametrize("setting, checked", [(None, True), ("answer_check", False),
                                              ("answer_check,check_stale_state", True), ("check_stale_state", False)])
def test_the_stale_state_rule_is_an_aid_of_its_own(tmp_path: Path, monkeypatch, setting, checked) -> None:
    if setting is None:
        monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    else:
        monkeypatch.setenv("BAXY_AYUDAS", setting)
    mind, server = _installing(tmp_path, [_say(SAID), _say("No lo he mirado desde que quedó en cola.")])
    result = mind.decide(2, "avísame cuando esté instalado")
    assert (result["reply"] != SAID) is checked
    assert len(server.bodies) == (4 if checked else 3)
