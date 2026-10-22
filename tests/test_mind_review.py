"""Review of the mind (2026-10-22): each test holds one finding of the reviewers fixed in src/baxy_mind."""
import json
import urllib.error
from pathlib import Path

import pytest

from test_mind_final import _call, _mind, _say


def _calls(*calls: tuple[str, dict]) -> dict:
    return {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": f"c{i}", "function": {"name": name, "arguments": json.dumps(arguments)}}
        for i, (name, arguments) in enumerate(calls, 1)]}}]}


def test_a_queued_call_does_not_run_after_the_call_before_it_failed(tmp_path: Path) -> None:
    # Review 1: app_open failed and input_text_type then typed into the person's own window.
    mind, server = _mind(tmp_path, [_calls(("app_open", {"appId": "Bloc de notas"}),
                                           ("input_text_type", {"text": "hola"})),
                                    _say("No pude abrir el Bloc de notas.")])
    mind.wire_to_op = {"app_open": "app.open", "input_text_type": "input.text.type"}
    assert mind.decide(1, "abre el bloc de notas y escribe hola")["operation"] == "app.open"
    result = mind.continue_turn(2, json.dumps({"status": "failed", "error": "application_not_found"}))
    assert result["kind"] == "conversation" and result["operation"] is None
    tools = {m["tool_call_id"]: m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"}
    assert json.loads(tools["c2"])["status"] == "not_run"


def test_a_queued_call_runs_after_the_call_before_it_completed(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [_calls(("app_open", {"appId": "Bloc de notas"}), ("input_text_type", {"text": "hola"}))])
    mind.wire_to_op = {"app_open": "app.open", "input_text_type": "input.text.type"}
    mind.decide(1, "abre el bloc de notas y escribe hola")
    assert mind.continue_turn(2, json.dumps({"status": "completed"}))["operation"] == "input.text.type"


class _Dead:
    returncode = 1

    def poll(self) -> int:
        return 1


@pytest.mark.parametrize("call", [
    lambda s: s.tokenize("hola"), lambda s: s.chat({"messages": []}),
    lambda s: s.template({"messages": [], "tools": [], "chat_template_kwargs": {}}),
    lambda s: s.complete_name("PROMPT", "<tool_call>"),
    lambda s: s.fill_call({"messages": []}, "app_open")])
def test_a_dead_model_server_ends_the_mind_from_any_call(monkeypatch, call) -> None:
    # Review 2: only chat() exited, and tokenize (the history's trim) raised URLError first: the mind never relaunched.
    from baxy_mind import llm_server

    class Exited(Exception):
        pass

    def exit_(code: int) -> None:
        raise Exited(code)

    monkeypatch.setattr(llm_server.os, "_exit", exit_)
    server = llm_server.LlmServer("model.gguf", "llama-server.exe")
    server._process = _Dead()  # type: ignore[assignment]
    server._ready.set()
    with pytest.raises(Exited) as exited:
        call(server)
    assert exited.value.args == (70,)


def test_a_decision_that_failed_leaves_nothing_of_its_request_in_the_conversation(tmp_path: Path) -> None:
    # Review 2: the clock and the words of a failed decide stayed, and the next turn could run that old request.
    down = urllib.error.URLError(ConnectionRefusedError())
    mind, server = _mind(tmp_path, [_say("Hola."), down, _say("Son las siete.")])
    mind.decide(1, "hola")
    before = json.loads(json.dumps(mind.conversation))
    with pytest.raises(urllib.error.URLError):
        mind.decide(2, "borra la carpeta de descargas")
    assert mind.conversation == before
    mind.decide(3, "qué hora es")
    assert "borra la carpeta de descargas" not in json.dumps(server.bodies[-1]["messages"], ensure_ascii=False)


def test_an_answer_to_a_question_whose_decision_failed_still_answers_it_next_time(tmp_path: Path) -> None:
    down = urllib.error.URLError(ConnectionRefusedError())
    mind, server = _mind(tmp_path, [_call("ask_user", {"question": "¿A qué hora?"}), down,
                                    _call("schedule_alarms", {"time": "07:00"})])
    assert mind.decide(1, "pon una alarma")["kind"] == "clarify"
    with pytest.raises(urllib.error.URLError):
        mind.decide(2, "a las 7")
    assert mind.decide(3, "a las 7")["kind"] == "action"
    messages = server.bodies[-1]["messages"]
    assert [m["content"] for m in messages if m["role"] == "tool"] == ["a las 7"]
    assert [m["role"] for m in messages[-2:]] == ["assistant", "tool"]  # the answer, not a new request


def _snap_correction(tmp_path: Path, monkeypatch, filled: dict):
    # B-MED-1 (notebook traces): Qwen chose window_resolve, Laya window_snap, and fill_call wrote windowId "1", invented.
    from test_mind_doubt_policy import FakeSystemOne, _call as _doubted, _mind as _doubt_mind
    monkeypatch.setenv("BAXY_S1_DOUBT", "")
    monkeypatch.setenv("BAXY_S1_VETO", "0.6")
    monkeypatch.setenv("BAXY_S1_CORRECT", "1")
    reply = _doubted("window_resolve", {"query": "la ventana"}, 0.5)
    reply["choices"][0]["logprobs"]["content"][5]["top_logprobs"].append({"token": "app", "logprob": -0.7})
    mind, server = _doubt_mind(tmp_path, [reply, _say("¿Qué ventana pongo a la izquierda?")])
    server.complete_name = lambda prompt, written: "_snap"
    server.fill_call = lambda body, wire: {"name": wire, "arguments": filled, "timings": {}}
    schema = {"type": "object", "properties": {"windowId": {"type": "string"}, "position": {"type": "string"}},
              "required": ["windowId", "position"]}
    mind.tools = [{"type": "function", "function": {"name": n, "description": "Window. More.", "parameters": p}}
                  for n, p in (("window_resolve", {}), ("app_snap", schema))]
    mind.wire_to_op = {"window_resolve": "window.resolve", "app_snap": "app.snap"}
    mind.risk = {"window_resolve": "read_only", "app_snap": "low_reversible"}
    mind.system_one = FakeSystemOne("app_snap")  # type: ignore[assignment]
    return mind, server


def test_a_correction_with_an_argument_the_conversation_never_showed_asks(tmp_path: Path, monkeypatch) -> None:
    mind, server = _snap_correction(tmp_path, monkeypatch, {"windowId": "1", "position": "left"})
    result = mind.decide(1, "pon la ventana de la izquierda")
    assert result["kind"] == "conversation" and result["operation"] is None
    assert "app_snap" not in json.dumps([m.get("tool_calls") for m in server.bodies[-1]["messages"]])


def test_a_correction_missing_a_required_argument_asks(tmp_path: Path, monkeypatch) -> None:
    mind, _ = _snap_correction(tmp_path, monkeypatch, {"position": "left"})
    assert mind.decide(1, "pon la ventana 1 a la left")["operation"] is None


def test_a_correction_whose_arguments_the_person_said_runs(tmp_path: Path, monkeypatch) -> None:
    mind, _ = _snap_correction(tmp_path, monkeypatch, {"windowId": "1", "position": "Left"})
    result = mind.decide(1, "pon la ventana 1 a la left")
    assert result["operation"] == "app.snap" and result["arguments"] == {"windowId": "1", "position": "Left"}


LONG = "https://news.google.com/rss/articles/" + "CBMi" + "x" * 300 + "?oc=5"
FOUND = json.dumps({"status": "completed", "observed": {"results": [{"title": "Lluvia", "url": LONG}]}})


def test_short_references_go_with_the_exported_session_and_a_new_session_forgets_them(tmp_path: Path,
                                                                                         monkeypatch) -> None:
    # Review 3: after a relaunch ref:r1 stood for another address, or for none.
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("web_search", {"query": "clima"}), _say("Encontré una noticia.")])
    mind.decide(1, "el clima")
    mind.continue_turn(2, FOUND)
    kept = mind.export_session()
    relaunched, _ = _mind(tmp_path, [_call("web_fetch", {"url": "ref:r1"})])
    relaunched.load_session(kept)
    assert relaunched.conversation == [m for m in kept if m.get("role") in {"user", "assistant", "tool"}]
    assert relaunched.decide(3, "ábrela")["arguments"]["url"] == LONG
    relaunched.server.replies.append(_call("web_fetch", {"url": "ref:r1"}))
    relaunched.new_session()
    assert relaunched.decide(4, "ábrela")["arguments"]["url"] == "ref:r1"


def test_the_ids_the_mind_writes_never_repeat_in_a_session(tmp_path: Path, monkeypatch) -> None:
    # Review 13: confirm_{len(conversation)} repeated once the conversation was trimmed to the same length.
    from baxy_mind import mind as mind_module
    monkeypatch.setattr(mind_module, "HISTORY_TURNS", 1)
    mind, _ = _mind(tmp_path, [_say("¿Lo borro?"), _say("Listo."), _say("¿Lo borro?"), _say("Listo.")])
    ids = []
    for request in ("borra a.txt", "borra b.txt"):
        mind.decide(1, request)
        mind.confirm(2, True, "Sí")
        ids.append(mind.conversation[-1]["tool_calls"][0]["id"])
        mind.continue_turn(3, json.dumps({"status": "completed"}))
    kept = mind.export_session()
    mind.load_session(kept)
    mind.server.replies.append(_say("¿Lo borro?"))
    mind.decide(4, "borra c.txt")
    mind.confirm(5, True, "Sí")
    ids.append(mind.conversation[-1]["tool_calls"][0]["id"])
    assert len(set(ids)) == 3


def _rows(tmp_path: Path) -> list[dict]:
    return [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]


def test_a_heartbeat_that_read_the_persons_memory_keeps_it_out_of_the_trace(tmp_path: Path) -> None:
    # Review 4: the heartbeat's JSON and its words carried what it deduced from memory into turns.jsonl.
    decision = {"pedido": "ninguno", "preferencia": "le gusta el jazz de noche", "vence": "nada", "bloqueo": "nada",
                "analisis": "Es de noche y le gusta el jazz.", "intervenir": True}
    mind, _ = _mind(tmp_path, [_say(json.dumps(decision, ensure_ascii=False)), _say("¿Te pongo jazz?")])
    mind.beat(1, {"now": "22:00", "memory": ["le gusta el jazz de noche"]})
    rows = _rows(tmp_path)
    assert "jazz" not in json.dumps(rows, ensure_ascii=False)
    assert rows[0]["intervene"] is True


def test_a_heartbeat_without_memory_keeps_its_trace(tmp_path: Path) -> None:
    decision = {"pedido": "ninguno", "preferencia": "ninguna", "vence": "nada", "bloqueo": "disco lleno",
                "analisis": "El disco está lleno.", "intervenir": True}
    mind, _ = _mind(tmp_path, [_say(json.dumps(decision, ensure_ascii=False)), _say("Tu disco está lleno.")])
    mind.beat(1, {"now": "22:00"})
    assert "disco lleno" in _rows(tmp_path)[0]["content"]


def test_a_doubted_memory_call_keeps_the_persons_words_out_of_the_trace(tmp_path: Path, monkeypatch) -> None:
    from test_mind_doubt_policy import _call as _doubted, _mind as _doubt_mind
    monkeypatch.setenv("BAXY_S1_DOUBT", "0.9")
    mind, _ = _doubt_mind(tmp_path, [_doubted("memory_save", {"text": "mi clave es 4321"}, 0.3), _say("¿Lo guardo?")])
    mind.wire_to_op["memory_save"] = "memory.save"
    mind.decide(1, "recuerda que mi clave es 4321")
    assert "4321" not in json.dumps(_rows(tmp_path), ensure_ascii=False)


def test_the_tool_chosen_is_not_completed_again_as_its_own_rival(tmp_path: Path, monkeypatch) -> None:
    # Review 9: the first «rival» was the chosen token itself: one more call to the server and one less real rival.
    from test_mind_doubt_policy import _layer2, _rival_call
    mind, server, _ = _layer2(tmp_path, monkeypatch, "system_power", [_rival_call(0.5)])
    written: list[str] = []
    server.complete_name = lambda prompt, text: written.append(text) or "_close"
    mind.decide(1, "apaga el pc")
    assert [text[-3:] for text in written] == ["app"]


def _laya(monkeypatch):
    from baxy_mind.system_one import SystemOne
    monkeypatch.setattr(SystemOne, "ready", property(lambda self: True))
    return SystemOne("laya.gguf", "llama-server.exe")


OPTIONS = {"app_close": "Close an application.", "ask_user": "preguntar", "responder_con_palabras": "contestar"}


@pytest.mark.parametrize("probabilities", [{"app_close": "alta"}, ["app_close"], {"app_close": None}])
def test_an_answer_of_the_decision_model_that_cannot_be_read_goes_on_as_qwen_decided(monkeypatch, probabilities) -> None:
    # Review 9: a value that is not a number raised out of choose(), and the turn failed (turn_runtime_failure).
    laya = _laya(monkeypatch)
    laya._ask = lambda text, history, options, timeout: {"probabilities": probabilities}
    assert laya.choose("ciérralo", [], OPTIONS) is None


@pytest.mark.parametrize("payload", [{"answers": ["operacion"]}, {"answers": {"operacion": "app_close"}}, []])
def test_a_reply_of_the_decision_model_that_is_not_its_shape_is_no_answer(monkeypatch, payload) -> None:
    import io
    from baxy_mind import system_one
    laya = _laya(monkeypatch)
    monkeypatch.setattr(system_one.urllib.request, "urlopen",
                        lambda request, timeout: io.BytesIO(json.dumps(payload).encode("utf-8")))
    assert laya.choose("ciérralo", [], OPTIONS) is None


@pytest.mark.parametrize("raw", ["<tool_call>\n<function=app_open>\n<parameter=appId>\nSpotify",
                                 "Claro. <function=app_open><parameter=appId>Spotify</parameter></function>"])
def test_a_call_written_as_text_is_a_failed_call_never_an_answer(tmp_path: Path, raw: str) -> None:
    # Review 7: a malformed call llama-server left in content reached the person as BAXY's words.
    mind, server = _mind(tmp_path, [_say(raw), _say("Esa aplicación no respondió.")])
    result = mind.decide(1, "abre spotify")
    assert result["reply"] == "Esa aplicación no respondió."
    assert server.bodies[-1]["tool_choice"] == "none" and server.bodies[-1]["logit_bias"]
    assert raw not in json.dumps(mind.conversation, ensure_ascii=False)


@pytest.mark.parametrize("move", [0.025, 0.015])
def test_the_decision_model_reads_the_options_it_was_trained_on(tmp_path: Path, monkeypatch, move: float) -> None:
    # B-MED-3 (notebook): served, the chosen token took one of the 4 places and a rival needed p ≥ 0.02; trained
    # (scripts/renew/system_one/qwen_signals.py, rollouts), the chosen tool and up to 3 rivals of p ≥ 0.01.
    import math
    from test_mind_doubt_policy import _layer2, _token
    weakest = _token("_resolve", 0.54)
    weakest["top_logprobs"] += [{"token": t, "logprob": math.log(q)}
                                for t, q in (("_active", 0.41), ("_snap", 0.03), ("_move", move))]
    tokens = [_token("<tool_call>", 0.95), _token("\n", 1.0), _token("<", 1.0), _token("function", 1.0),
              _token("=", 1.0), _token("window", 1.0), weakest, _token(">", 1.0)]
    reply = {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": "c1", "function": {"name": "window_resolve", "arguments": "{}"}}]}, "logprobs": {"content": tokens}}]}
    mind, server, one = _layer2(tmp_path, monkeypatch, "window_resolve", [reply])
    server.complete_name = lambda prompt, written: ""
    mind.tools = [{"type": "function", "function": {"name": f"window{n}", "description": "Window. More.",
                                                    "parameters": {}}} for n in ("_resolve", "_active", "_snap", "_move")]
    mind.decide(1, "esa ventana")
    tools = [o for o in one.asked[0]["options"] if o.startswith("window")]
    assert tools == ["window_resolve", "window_active", "window_snap", "window_move"]


def test_a_correction_drops_the_words_written_for_the_doubted_call_and_its_row_names_both(tmp_path: Path,
                                                                                         monkeypatch) -> None:
    # Review 11 and B-MED-8: «Apago el PC.» stayed beside the corrected app_close, and the row read the doubt of
    # system_power as if it were app_close's.
    from test_mind_doubt_policy import _correcting
    mind, server, _ = _correcting(tmp_path, monkeypatch, "low_reversible",
                                  {"name": "app_close", "arguments": {"appId": "Spotify"}, "timings": {}})
    server.replies[0]["choices"][0]["message"]["content"] = "Apago el PC."
    assert mind.decide(1, "ahora ciérralo")["operation"] == "app.close"
    assert mind.conversation[-1]["content"] == ""
    row = _rows(tmp_path)[-1]
    assert row["operation"] == "app.close" and row["doubt_of"] == "system.power" and row["content"] == ""
    assert row["doubt"]["confidence"] < 0.6


def test_the_trace_written_from_the_voice_thread_and_the_turns_keeps_whole_rows(tmp_path: Path) -> None:
    # Review 8: voice.speak's rows (the voice thread) and the turn's rows were written with no lock between them.
    import threading
    import time
    mind, _ = _mind(tmp_path, [])
    inside, overlaps = [0], []

    class Trace:
        def open(self, mode: str, encoding: str):
            return self

        def __enter__(self):
            inside[0] += 1
            overlaps.append(inside[0] > 1)
            return self

        def __exit__(self, *exc) -> None:
            inside[0] -= 1

        def write(self, row: str) -> None:
            time.sleep(0.002)  # a write long enough for the other thread to arrive

    mind.trace = Trace()  # type: ignore[assignment]
    threads = [threading.Thread(target=lambda stage=stage: [mind._log(stage, time.perf_counter(), None)
                                                            for _ in range(20)])
               for stage in ("voice.speak", "turn.decide")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(overlaps) == 40 and not any(overlaps)


INTERVENE = json.dumps({"pedido": "ninguno", "preferencia": "ninguna", "vence": "nada", "bloqueo": "disco lleno",
                        "analisis": "El disco está lleno.", "intervenir": True}, ensure_ascii=False)


def test_a_heartbeat_joins_the_conversation_with_what_baxy_did_not_its_rules(tmp_path: Path) -> None:
    # Review 14 (R10.2 of the notebook): the heartbeat's whole message, its rules and «Responde en JSON…» included,
    # entered the person's conversation.
    from baxy_mind.mind import BEAT_ACT, BEAT_DECIDE, BEAT_RULES
    mind, _ = _mind(tmp_path, [_say(INTERVENE), _say("Tu disco está casi lleno.")])
    mind.beat(1, {"now": "22:00", "pc": {"disk_free_gb": 1}})
    mind.end_beat()
    text = json.dumps(mind.conversation, ensure_ascii=False)
    for internal in (BEAT_RULES, BEAT_DECIDE, BEAT_ACT, "El disco está lleno.", "disk_free_gb"):
        assert json.dumps(internal, ensure_ascii=False)[1:-1] not in text
    assert mind.conversation[-1] == {"role": "assistant", "content": "Tu disco está casi lleno."}
    assert mind.conversation[-2]["role"] == "user" and mind.conversation[-2]["content"].startswith("[")


def test_a_heartbeat_never_ended_is_closed_honestly_by_the_next_one(tmp_path: Path) -> None:
    # Review 15: beat() overwrote a _beat the App never ended, and what BAXY said or did in it was lost unsaid.
    silent = INTERVENE.replace('"intervenir": true', '"intervenir": false')
    mind, _ = _mind(tmp_path, [_say(INTERVENE), _call("app_close", {"appId": "Juego"}), _say(silent)])
    mind.beat(1, {"now": "22:00"})
    mind.beat(2, {"now": "22:05"})
    calls = [m for m in mind.conversation if m.get("tool_calls")]
    assert calls and calls[0]["tool_calls"][0]["function"]["name"] == "app_close"
    assert mind.conversation[-1]["role"] == "tool" and json.loads(mind.conversation[-1]["content"])["status"] == "unknown"


def test_the_decision_model_reads_the_request_and_the_question_its_answer_answers(tmp_path: Path, monkeypatch) -> None:
    # Review 10: answering ask_user, Laya's history was cut two messages short of the right place, and the question
    # (in tool_calls) was never in it.
    from test_mind_doubt_policy import _call as _doubted, _layer2, _rival_call
    mind, _, one = _layer2(tmp_path, monkeypatch, "system_power",
                           [_doubted("ask_user", {"question": "¿Apago el PC o cierro la ventana?"}, 0.9),
                            _rival_call(0.5), _say("Hola."), _rival_call(0.5)])
    seen: list = []
    choose = one.choose
    one.choose = lambda text, history, options: seen.append(history) or choose(text, history, options)
    mind.decide(1, "ciérralo")
    mind.decide(2, "el PC")
    assert seen[0] == [{"role": "user", "content": "ciérralo"},
                       {"role": "assistant", "content": "¿Apago el PC o cierro la ventana?"}]
    mind.continue_turn(3, json.dumps({"status": "completed"}))
    mind.decide(4, "apágalo otra vez")
    assert seen[1][:2] == seen[0] and seen[1][-1]["content"] != "apágalo otra vez"


@pytest.mark.parametrize("final", [False, True])
def test_the_same_call_aid_offers_more_tools_only_when_the_turn_admits_them(tmp_path: Path, monkeypatch,
                                                                         final: bool) -> None:
    # Review 12: on the third same call, «Opciones: otra herramienta…» beside «Este turno no admite más herramientas».
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    missed = json.dumps({"status": "failed", "error": "visible_button_not_found"})
    click = _call("input_visible_click", {"label": "FORTNITE"})
    mind, server = _mind(tmp_path, [click, click, click, _say("No encontré ese botón.")])
    mind.decide(1, "busca fortnite ahí")
    mind.continue_turn(2, missed)
    mind.continue_turn(3, missed)
    mind.continue_turn(4, missed, final=final)
    last = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert "ya se hizo 3 veces en este turno" in last
    assert ("Opciones: otra herramienta" in last) is not final


def test_a_pasted_text_past_what_the_turn_holds_keeps_its_start_and_the_cut_is_said(tmp_path: Path) -> None:
    # Review 16: one turn alone past the context failed whole and wordless (only earlier turns can be trimmed).
    from test_mind_final import _overflow
    mind, server = _mind(tmp_path, [_say("Es un registro de errores de red.")])
    mind.prefix_tokens = 45000  # with 49,152 of context, about 2,200 characters for the turn
    chat = server.chat
    server.chat = lambda body: (_ for _ in ()).throw(_overflow()) if len(json.dumps(body["messages"][1:])) > 4000 \
        else chat(body)
    pasted = "ERROR timeout en 10.0.0.1 " * 800
    assert mind.decide(1, pasted)["reply"] == "Es un registro de errores de red."
    request = mind.conversation[-2]["content"]
    assert request.startswith(pasted[:500])
    kept = request.split("\n[")[0]
    assert f"{len(pasted) - len(kept)} caracteres" in request


def _server_answering(monkeypatch, timeouts: list):
    import io
    from baxy_mind import llm_server

    def urlopen(request, timeout):
        timeouts.append(timeout)
        return io.BytesIO(json.dumps({"tokens": [1], "prompt": "p", "content": "_close",
                                      "choices": [{"message": {"content": "Hola."}}]}).encode("utf-8"))

    monkeypatch.setattr(llm_server.urllib.request, "urlopen", urlopen)
    server = llm_server.LlmServer("model.gguf", "llama-server.exe")
    server._ready.set()
    return server


ALL_CALLS = [lambda s: s.chat({"messages": []}), lambda s: s.tokenize("hola"),
             lambda s: s.template({"messages": [], "tools": [], "chat_template_kwargs": {}}),
    lambda s: s.complete_name("PROMPT", "<tool_call>"),
             lambda s: s.fill_call({"messages": []}, "app_open")]


@pytest.mark.parametrize("call", ALL_CALLS)
def test_every_call_to_the_model_server_waits_within_the_requests_budget(monkeypatch, call) -> None:
    # Review 17: the App ends a turn's request at 30 s; the mind waited 120 s for a chat, 30 s for a fill, 10 s for a
    # name, and answered after the App had given up.
    import time
    timeouts: list = []
    server = _server_answering(monkeypatch, timeouts)
    server.deadline = time.monotonic() + 5
    call(server)
    assert timeouts and all(t <= 5 for t in timeouts)


@pytest.mark.parametrize("call", ALL_CALLS)
def test_a_spent_budget_ends_the_request_without_calling_the_server(monkeypatch, call) -> None:
    import time
    timeouts: list = []
    server = _server_answering(monkeypatch, timeouts)
    server.deadline = time.monotonic() - 0.1
    with pytest.raises(TimeoutError):
        call(server)
    assert timeouts == []


def test_without_a_budget_the_calls_keep_their_own_timeouts(monkeypatch) -> None:
    timeouts: list = []
    server = _server_answering(monkeypatch, timeouts)
    server.chat({"messages": []}, timeout=600)
    assert timeouts == [600]


def test_a_pinned_port_in_use_fails_the_start_with_its_cause(monkeypatch) -> None:
    # Review 18: another port was taken in silence, and the core's vision kept pointing at the pinned one.
    import socket
    from baxy_mind.llm_server import LlmServer
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        monkeypatch.setenv("BAXY_MIND_LLAMA_PORT", str(port))
        with pytest.raises(RuntimeError, match=str(port)):
            LlmServer("model.gguf", "llama-server.exe")
    assert LlmServer("model.gguf", "llama-server.exe").port == port


@pytest.mark.parametrize("setting, seed", [(None, 0), ("7", 7), ("x", 0)])
def test_the_decisions_seed_comes_from_baxy_renew_seed(tmp_path: Path, monkeypatch, setting, seed) -> None:
    # Review 19: to measure the noise, the decisions' fixed seed 0 can be moved by the environment.
    if setting is None:
        monkeypatch.delenv("BAXY_RENEW_SEED", raising=False)
    else:
        monkeypatch.setenv("BAXY_RENEW_SEED", setting)
    mind, server = _mind(tmp_path, [_say("Hola.")])
    mind.decide(1, "hola")
    assert server.bodies[0]["seed"] == seed


# Renew al máximo (palanca 3.1): Laya runs on the CPU, but with only -ngl 0 the CUDA build of llama-server still made a
# CUDA context and offloaded its big batches (op offload is on by default): with System One on the product's VRAM went
# 3902 → 4091 MiB, 5 MiB under the 4 GB ceiling (notebook, 2026-10-22). Its server is started with no device at all.
def test_laya_is_started_with_no_gpu_device(monkeypatch, tmp_path):
    from baxy_mind import system_one
    started = []

    class Started:
        def __init__(self, args, **_):
            started.append(list(args))

        def poll(self):
            return 0

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(system_one.subprocess, "Popen", Started)
    system_one.SystemOne("laya.gguf", "llama-server.exe").start()
    args = started[0]
    assert args[args.index("-dev") + 1] == "none"
