"""Aid «power_unnamed», INT36D (held-out HA-07, Completo: «pues apágalo, el que sale abajo con las flechitas al lado de
la hora», after a close that failed, became system_power {action: shutdown} 10 of 10 on the 1.5.2, int36c and int36d;
in Bypass a shutdown asks nothing, RiskPolicy). As «screen_unnamed»: a shutdown, restart or sign-out in a turn where
neither the person's words, BAXY's words before them nor the person's turn before name the computer or the session is
held once and goes back to the model as data; the same call again runs as written. POW1: only a shutdown; restarting,
signing out, locking and sleeping are not held (none was called unasked in POW1's held-out, save one sign-out
whose hold also lost a sign-out asked for)."""
import json
import re
from pathlib import Path

from baxy_mind.mind import POWER_AGAIN_SYSTEM
from test_mind_final import _call, _mind, _say

FAILED = [{"role": "user", "content": "Cierra Clevanto"},
          {"role": "assistant", "content": "No pude cerrar Clevanto: sigue abierto en segundo plano."}]
SHUTDOWN = {"action": "shutdown"}


def _not_run(mind) -> list[dict]:
    told = []
    for message in mind.conversation:
        if message["role"] == "tool" and str(message.get("content")).startswith("{"):
            body = json.loads(str(message["content"]).split("\n", 1)[0])
            if body.get("status") == "not_run":
                told.append(body)
    return told


def test_a_shutdown_nobody_named_goes_back_and_the_model_decides_again(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("system_power", SHUTDOWN), _say("Clevanto sigue abierto. ¿Lo cierro a la fuerza?")])
    mind.new_session(FAILED)
    step = mind.decide(1, "pues apágalo, el que sale abajo al lado de la hora")
    assert step["kind"] != "action"
    told = _not_run(mind)
    assert len(told) == 1 and told[0]["error"] == "computer_not_named"
    assert told[0]["theirWordsBefore"] == "Cierra Clevanto"
    # POW1: «do not tell them about this call» was answered «No puedo apagar el PC…» 12 of 20 (false); this, 1 of 20.
    assert "say nothing of turning the computer off: they did not ask for it" in told[0]["next"]


def test_called_again_in_the_turn_it_is_held_again_and_answered_in_words(tmp_path: Path, monkeypatch) -> None:
    # DIAX5 (CASX1, H-049 «apágalo y vuelve a prenderlo»): told once, the 4B called the same shutdown again 6 of 6 and
    # it ran. In the turn it does not run while their words name no computer: the model answers in words.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("system_power", SHUTDOWN), _call("system_power", SHUTDOWN),
                                    _say("¿Qué quieres que apague: el PC o Spotify?")])
    step = mind.decide(1, "apágalo y vuelve a prenderlo")
    assert step["kind"] != "action"
    assert [t["error"] for t in _not_run(mind)] == ["computer_not_named", "computer_not_named"]
    assert server.bodies[-1].get("tool_choice") == "none"


def test_the_window_in_front_is_told_with_the_hold(tmp_path: Path, monkeypatch) -> None:
    # DIAX5: the datum the model lacked to ask «¿el PC o Spotify?».
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("system_power", SHUTDOWN), _say("¿Apago el PC o cierro Spotify?")])
    mind.decide(1, "apágalo y vuelve a prenderlo", front={"title": "Spotify Premium", "process": "Spotify"})
    told = _not_run(mind)
    assert told[0]["windowInFront"] == "«Spotify Premium» (Spotify)"
    assert "ask them in a short question" in told[0]["next"]


def test_a_restart_or_a_sign_out_nobody_named_is_held_too(tmp_path: Path, monkeypatch) -> None:
    # DIAX5: what ends the session (RiskPolicy.EndsTheSession) loses unsaved work as a shutdown does.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    for said, args in (("reinícialo", {"action": "restart"}), ("se trabó, reinícialo", {"action": "restart"}),
                       ("sácame de aquí", {"action": "signout"})):
        mind, _ = _mind(tmp_path, [_call("system_power", args), _say("¿Qué quieres que reinicie?")])
        assert mind.decide(1, said)["kind"] != "action", said
        assert [t["error"] for t in _not_run(mind)] == ["computer_not_named"], said


def test_the_computer_named_runs_and_lock_and_sleep_are_not_held(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    for said, args in (("apaga el PC", SHUTDOWN), ("reinicia la compu", {"action": "restart"}),
                       ("cierra sesión", {"action": "signout"}), ("shut down the computer", SHUTDOWN),
                       ("apaga el ordenador", SHUTDOWN), ("bloquéalo", {"action": "lock"}),
                       ("ponlo a dormir", {"action": "sleep"}),
                       ("apaga el conputador porfa", SHUTDOWN),  # DIAX5: the ear one letter off
                       ("apaga la máquina y vuelve a prenderla", {"action": "restart"})):
        mind, _ = _mind(tmp_path, [_call("system_power", args)])
        assert mind.decide(1, said)["operation"] == "system_power", said
        assert _not_run(mind) == [], said


def test_a_word_alike_a_name_of_the_computer_is_not_one(tmp_path: Path, monkeypatch) -> None:
    # PA-03: «completito» is no «compu»; DIAX5's one-letter tolerance is for whole names of six letters or more.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    for said in ("apaga el completito", "apaga la window"):
        mind, _ = _mind(tmp_path, [_call("system_power", SHUTDOWN), _say("¿Qué quieres que apague?")])
        assert mind.decide(1, said)["kind"] != "action", said


def test_without_the_aid_it_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, _ = _mind(tmp_path, [_call("system_power", SHUTDOWN)])
    mind.new_session(FAILED)
    assert mind.decide(1, "pues apágalo, el que sale abajo al lado de la hora")["operation"] == "system_power"


def test_the_computer_named_in_a_question_and_its_answer_runs(tmp_path: Path, monkeypatch) -> None:
    # POW1 (test_mind_review): an ask_user's question is BAXY's words and its answer the person's turn.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("ask_user", {"question": "¿Apago el PC o cierro la ventana?"}),
                               _call("system_power", SHUTDOWN)])
    mind.decide(1, "ciérralo")
    assert mind.decide(2, "eso, apágalo")["operation"] == "system_power"
    assert _not_run(mind) == []


def test_in_bypass_it_is_held_alike_and_asks_nobody(tmp_path: Path, monkeypatch) -> None:
    # Owner's decision (07-11): Bypass asks the person nothing; the aid asks nobody either, it tells the model.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    monkeypatch.setenv("BAXY_DATA_DIR", str(tmp_path))
    (tmp_path / "confirmation-mode").write_text("bypass", encoding="utf-8")
    mind, server = _mind(tmp_path, [_call("system_power", SHUTDOWN), _call("app_close", {"appId": "Clevanto"})])
    mind.new_session(FAILED)
    step = mind.decide(1, "pues apágalo, el que sale abajo al lado de la hora")
    assert step["operation"] == "app_close"
    assert len(_not_run(mind)) == 1 and server.bodies[-1].get("tool_choice") != "none"


def test_in_english_what_it_tells_the_model_is_english(tmp_path: Path, monkeypatch) -> None:
    # The language is a setting (ING5): only the person's words stay as they said them.
    from baxy_mind import harness_language
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("system_power", SHUTDOWN), _say("Clevanto is still open.")])
    mind.configure({"capabilities": [], "lang": "en"})
    try:
        mind.new_session([{"role": "user", "content": "Close Clevanto"},
                          {"role": "assistant", "content": "I could not close Clevanto: it keeps running."}])
        mind.decide(1, "turn it off then, the one down by the clock")
        told = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
        assert "computer_not_named" in told and "→ not run]" in told
        assert not re.search(r"[áéíóúñ¿¡]|se ejecutó", told), told
    finally:
        harness_language.use("es")


def _on_again(server, answer: str) -> list:
    asked = []
    plain = server.ask_apart

    def ask_apart(body, timeout=60.0):
        if body["messages"][0]["content"] == POWER_AGAIN_SYSTEM:
            asked.append(body)
            return {"choices": [{"message": {"content": answer}}]}
        return plain(body, timeout)

    server.ask_apart = ask_apart
    return asked


def test_a_shutdown_whose_words_ask_it_back_on_goes_back_with_what_restart_does(tmp_path: Path, monkeypatch) -> None:
    # DIAX5 «power_on_again» (CASX1: «apaga el computador y vuelve a prenderlo» → shutdown 3 of 3, never restart).
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("system_power", SHUTDOWN), _call("system_power", {"action": "restart"})])
    asked = _on_again(server, "reiniciar")
    step = mind.decide(1, "apaga el computador y vuelve a prenderlo")
    assert step["operation"] == "system_power" and step["arguments"] == {"action": "restart"}
    told = _not_run(mind)
    assert [t["error"] for t in told] == ["turn_on_again_asked"] and "restart" in told[0]["next"]
    assert "«apaga el computador y vuelve a prenderlo»" in asked[0]["messages"][1]["content"]
    assert asked[0]["grammar"] == 'root ::= "apagar" | "reiniciar"'


def test_read_apart_as_left_off_the_shutdown_runs_and_it_is_asked_once(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("system_power", SHUTDOWN)])
    asked = _on_again(server, "apagar")
    assert mind.decide(1, "apaga el computador")["arguments"] == SHUTDOWN and _not_run(mind) == []
    mind, server = _mind(tmp_path, [_call("system_power", SHUTDOWN), _call("system_power", SHUTDOWN)])
    asked = _on_again(server, "reiniciar")
    assert mind.decide(1, "apaga el pc y préndelo, no, déjalo apagado")["arguments"] == SHUTDOWN
    assert len(asked) == 1 and len(_not_run(mind)) == 1


def test_the_answer_to_baxys_question_is_read_with_that_question(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("system_power", SHUTDOWN), _call("system_power", {"action": "restart"})])
    asked = _on_again(server, "reiniciar")
    mind.new_session([{"role": "user", "content": "apágalo y vuelve a prenderlo"},
                      {"role": "assistant", "content": "¿Qué quieres que apague y vuelva a encender: el PC o Spotify?"}])
    assert mind.decide(1, "el pc")["arguments"] == {"action": "restart"}
    note = asked[0]["messages"][1]["content"]
    assert "«apágalo y vuelve a prenderlo»" in note and "el PC o Spotify?»" in note and "«el pc»" in note
