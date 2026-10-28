"""Audit of the mind (w8-mente, 2026-10-23): each test holds one finding fixed in src/baxy_mind."""
import json

import pytest

from test_mind_doubt_policy import _call as _sure_call
from test_mind_doubt_policy import _mind as _doubt_mind
from test_mind_doubt_policy import _say as _doubt_say
from test_mind_doubt_policy import _token


def _unsure_yes() -> dict:
    reply = _sure_call("confirm_pending", {"approve": True}, 0.78)
    reply["choices"][0]["logprobs"]["content"][0] = _token("<tool_call>", 1.0)
    return reply


@pytest.mark.parametrize("pending, error", [
    (None, "nothing_pending"),
    ({"operation": "filesystem.known.trash.named", "ended": "dropped"}, "confirmation_dropped")])
def test_an_unsure_yes_with_nothing_waiting_reads_why_instead_of_a_doubt_question(tmp_path, monkeypatch, pending,
                                                                                 error) -> None:
    # The confirm floor held an unsure «sí» even when nothing waited for one: the result that says so (nothing_pending,
    # or the question that ended and the call to make again) never reached the model, which asked a question instead.
    monkeypatch.delenv("BAXY_S1_DOUBT", raising=False)
    monkeypatch.delenv("BAXY_CONFIRM_FLOOR", raising=False)
    mind, server = _doubt_mind(tmp_path, [_unsure_yes(), _doubt_say("No había nada esperando tu sí.")])
    result = mind.decide(1, "sí pero el otro", pending)
    assert result["kind"] == "conversation" and result["operation"] is None
    told = [m["content"] for m in server.bodies[1]["messages"] if m["role"] == "tool"]
    assert json.loads(told[-1])["error"] == error
    assert not any("Nota interna" in str(m["content"]) for m in server.bodies[1]["messages"])


def _calls(*calls: tuple[str, dict]) -> dict:
    return {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": f"c{i}", "function": {"name": name, "arguments": json.dumps(arguments)}}
        for i, (name, arguments) in enumerate(calls, 1)]}}]}


def test_a_session_kept_with_its_question_open_loads_back_with_the_question_answered_as_asked(tmp_path) -> None:
    # The App keeps a session between turns, also while BAXY's question waits for its answer; loaded back, the
    # ask_user call had no result and the next request followed a call still open.
    from baxy_mind.mind import ASKED, NOT_RUN
    from test_mind_final import _mind, _say
    mind, _ = _mind(tmp_path, [_calls(("ask_user", {"question": "¿Cuál archivo?"}), ("file_read", {"path": "x"}))])
    assert mind.decide(1, "léelo")["kind"] == "clarify"
    kept = mind.export_session()
    relaunched, server = _mind(tmp_path, [_say("Vale.")])
    relaunched.load_session(kept)
    relaunched.decide(2, "nada, olvídalo")
    told = {m["tool_call_id"]: m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"}
    assert told == {"c1": ASKED, "c2": NOT_RUN}
    roles = [m["role"] for m in server.bodies[-1]["messages"]]
    assert roles[roles.index("assistant") + 1:roles.index("assistant") + 3] == ["tool", "tool"]


def test_a_session_kept_with_a_call_whose_result_never_came_says_it_may_have_run(tmp_path) -> None:
    from baxy_mind.mind import NO_RESULT, NOT_RUN
    from test_mind_final import _mind, _say
    mind, _ = _mind(tmp_path, [_calls(("app_open", {"appId": "Paint"}), ("input_text_type", {"text": "hola"}))])
    mind.wire_to_op = {"app_open": "app.open", "input_text_type": "input.text.type"}
    assert mind.decide(1, "abre paint y escribe hola")["kind"] == "action"
    kept = mind.export_session()
    relaunched, server = _mind(tmp_path, [_say("No sé si se abrió.")])
    relaunched.load_session(kept)
    relaunched.decide(2, "¿lo abriste?")
    messages = server.bodies[-1]["messages"]
    told = {m["tool_call_id"]: m["content"] for m in messages if m["role"] == "tool"}
    assert told == {"c1": NO_RESULT, "c2": NOT_RUN}
    clock = next(m["content"] for m in reversed(messages) if m["content"].startswith("[Reloj:"))
    assert "app_open → sin resultado: pudo o no ocurrir" in clock


def test_a_kept_session_with_every_call_answered_loads_as_it_was_kept(tmp_path) -> None:
    from test_mind_final import _mind, _say
    mind, _ = _mind(tmp_path, [_calls(("app_open", {"appId": "Paint"})), _say("Abrí Paint.")])
    mind.decide(1, "abre paint")
    mind.continue_turn(2, json.dumps({"status": "completed", "verification": "readback"}))
    kept = mind.export_session()
    relaunched, _ = _mind(tmp_path, [])
    relaunched.load_session(kept)
    assert relaunched.conversation == [m for m in kept if m.get("role") in {"user", "assistant", "tool"}]


def test_a_fill_does_not_ask_for_the_decisions_token_probabilities() -> None:
    # «corrige» fills with the decision's body, which asks for logprobs and top_logprobs 10 (doubt.read): the server
    # sorted the vocabulary at every argument token of the fill for probabilities nothing reads.
    from baxy_mind.llm_server import LlmServer
    server = LlmServer("model.gguf", "llama-server.exe")
    sent: list = []
    server._post = lambda path, body, timeout: sent.append(body) or {"choices": [{"message": {"tool_calls": [
        {"function": {"name": "app_close", "arguments": '{"appId": "Spotify"}'}}]}}]}
    decision = {"messages": [{"role": "user", "content": "ciérralo"}], "tools": [], "logprobs": True,
                "top_logprobs": 10, "seed": 0, "temperature": 0.2}
    assert server.fill_call(decision, "app_close")["arguments"] == {"appId": "Spotify"}
    assert not {"logprobs", "top_logprobs"} & set(sent[0])
    assert sent[0]["temperature"] == 0.0 and sent[0]["seed"] == 0 and sent[0]["tool_choice"] == "required"


def test_a_decision_model_not_up_costs_the_doubtful_turn_no_rival_names(tmp_path, monkeypatch) -> None:
    # Laya still loading, or its server gone: choose() answers None, but the options were made first, completing each
    # rival's name on the slot (template + complete_name) for nothing.
    from test_mind_doubt_policy import _layer2, _rival_call
    mind, server, one = _layer2(tmp_path, monkeypatch, "app_close", [_rival_call(0.5)])
    one.ready = False
    server.template = lambda body: pytest.fail("rendered for a decision model that is not up")
    assert mind.decide(1, "apaga el pc")["operation"] == "system.power"
    assert one.asked == []


def test_a_conversation_read_ahead_into_the_slot_is_never_kept_on_disk_as_the_prefix(tmp_path, monkeypatch) -> None:
    # Mind.warm keeps the slot on disk only before any person's conversation reached it (_turned); the prefill of a
    # loaded session put one there without saying so.
    from test_mind_prefill import SlotServer, _mind as _slot_mind
    from test_mind_final import _say

    class Server(SlotServer):
        saved: list = []

        def tokenize(self, text: str) -> list[int]:
            return [248058] if text == "<tool_call>" else super().tokenize(text)

        def prefix_key(self, warm) -> str:
            return "key"

        def restore_prefix(self, key: str) -> None:
            return None

        def save_prefix(self, key: str, facts: dict) -> bool:
            self.saved.append(key)
            return True

    mind, _ = _slot_mind(tmp_path, [], monkeypatch)
    mind.server = server = Server([{**_say("H"), "usage": {"prompt_tokens": 100}}, _say("Un momento.")])
    mind.load_session([{"role": "user", "content": "[Reloj: jueves]"}, {"role": "user", "content": "hola"},
                       {"role": "assistant", "content": "Hola."}])
    assert mind.prefill() is True
    mind.warm()
    assert server.saved == []


def test_a_new_catalog_drops_the_constants_of_the_one_before(tmp_path) -> None:
    from test_mind_final import _call, _mind
    mind, _ = _mind(tmp_path, [_call("memory_save", {"value": "azul"})])
    schema = {"type": "object", "properties": {"value": {"type": "string"}, "scope": {"const": "person"}},
              "required": ["value", "scope"]}
    mind.configure({"capabilities": [{"name": "memory.save", "description": "Save", "argumentsSchema": schema}]})
    assert mind.constants == {"memory.save": {"scope": "person"}}
    del schema["properties"]["scope"]
    schema["required"] = ["value"]
    mind.configure({"capabilities": [{"name": "memory.save", "description": "Save", "argumentsSchema": schema}]})
    assert mind.decide(1, "recuerda que me gusta el azul")["arguments"] == {"value": "azul"}


def test_a_result_that_tells_the_places_does_not_list_them_twice(tmp_path, monkeypatch) -> None:
    # app_places_next and same_call_next fired on the same result (a click failed, a look named Steam, the same click
    # failed the same way): the places of Steam were listed twice in one message.
    from test_mind_final import _call, _mind, _say
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    unchanged = json.dumps({"status": "failed", "error": "visible_button_postread_unchanged"})
    looked = json.dumps({"status": "completed", "verification": "output_only", "view": "window 1 Steam\nBiblioteca"})
    click = _call("input_visible_click", {"label": "Biblioteca"})
    mind, server = _mind(tmp_path, [click, _call("input_visible_controls", {"application": "Steam"}), click,
                                    _say("No cambió.")])
    mind.decide(1, "entra a la biblioteca")
    for index, result in enumerate([unchanged, looked, unchanged]):
        mind.continue_turn(2 + index, result)
    last = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert "input_visible_click ya se llamó 2 veces en este turno" in last
    assert last.count("también se abre directo en sus lugares") == 1


def _clock_of(server) -> str:
    return next(m["content"] for m in reversed(server.bodies[-1]["messages"])
                if str(m["content"]).startswith("[Reloj:"))


@pytest.mark.parametrize("setting, told", [("", "; lo que vio se omitió"), ("none", "")])
def test_the_clock_says_a_call_whose_body_was_cut_away_was_left_out(tmp_path, monkeypatch, setting, told) -> None:
    # Aid «clock_omitted»: the clock's calls of the session (8.1) said «lo que vio está arriba» for a read whose result
    # the trim had taken away, beside the kept facts lines saying «lo que vio se omitió».
    from baxy_mind import mind as mind_module
    from test_mind_final import _call, _mind, _say
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    monkeypatch.setattr(mind_module, "HISTORY_TURNS", 2)
    mind, server = _mind(tmp_path, [_call("file_read", {"path": "notas.txt"}), _say("Dice hola."), _say("Bien."),
                                    _say("Decía hola.")])
    mind.risk = {"file_read": "read_only"}
    mind.decide(1, "lee notas.txt")
    mind.continue_turn(2, json.dumps({"status": "completed", "verification": "output_only", "text": "hola"}))
    mind.decide(3, "gracias")
    mind.decide(4, "¿qué decía?")
    assert mind.trimmed_turns == 2
    clock = _clock_of(server)
    assert f"file_read → lectura: sólo miró, sin abrir, cerrar ni cambiar nada{told}" in clock
    assert ("se omitió" in clock) is bool(told)


def test_the_clock_keeps_its_words_for_a_body_still_in_the_conversation(tmp_path, monkeypatch) -> None:
    from test_mind_final import _call, _mind, _say
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("file_read", {"path": "notas.txt"}), _say("Dice hola."), _say("Hola.")])
    mind.risk = {"file_read": "read_only"}
    mind.decide(1, "lee notas.txt")
    mind.continue_turn(2, json.dumps({"status": "completed", "verification": "output_only", "text": "hola"}))
    kept = mind.export_session()
    mind.load_session(kept)
    mind.decide(3, "¿qué decía?")
    clock = _clock_of(server)
    assert "file_read → lectura: sólo miró, sin abrir, cerrar ni cambiar nada" in clock and "se omitió" not in clock


def test_forgetting_everything_takes_the_trace_and_its_archive(tmp_path, monkeypatch) -> None:
    # Privacy (App audit, 2026-10-23): after «olvida todo» or deleting every conversation the App deletes its own
    # conversation log, and the mind's trace kept the person's words in clear text. trace.forget takes it, its archive
    # (turns.jsonl.1) and the slot states a vision question set aside; the kept prefix stays.
    from baxy_mind import __main__ as sidecar
    from baxy_mind.mind import Mind
    renew = tmp_path / "BAXY" / "renew"
    (renew / "slots").mkdir(parents=True)
    (renew / "turns.jsonl").write_text('{"text": "mi clave es pez"}\n', encoding="utf-8")
    (renew / "turns.jsonl.1").write_text('{"text": "vivo en la calle falsa"}\n', encoding="utf-8")
    (renew / "slots" / "baxy_vision_hold.bin").write_bytes(b"conversation")
    (renew / "slots" / "baxy_prefix_key.slot").write_bytes(b"prefix")
    sent: list[dict] = []
    incoming = [{"type": "trace.forget", "id": 7}, None]

    from baxy_mind.llm_server import LlmServer

    class Server(LlmServer):
        def start(self) -> None:
            pass

        def close(self) -> None:
            pass

    class Speech:
        def foresee(self, text, done):
            return True

        def close(self) -> None:
            pass

    class Voice:
        def __init__(self, *args, **kwargs) -> None:
            self.speech = Speech()

        def stop(self) -> None:
            pass

    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", "llama-server.exe")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_VISION_SLOT_DIR", raising=False)
    monkeypatch.delenv("BAXY_MIND_LLAMA_PORT", raising=False)
    monkeypatch.delenv("BAXY_S1_GGUF", raising=False)
    monkeypatch.setattr(sidecar, "declared_build", lambda path: "b11609")  # the server is a fake
    monkeypatch.setattr(sidecar, "LlmServer", Server)
    monkeypatch.setattr(sidecar, "Mind", Mind)
    monkeypatch.setattr(sidecar, "Voice", Voice)
    monkeypatch.setattr(sidecar.protocol, "read_message", lambda: incoming.pop(0))
    monkeypatch.setattr(sidecar.protocol, "write_message", sent.append)
    assert sidecar.main() == 0
    assert "trace.forget" in sent[0]["requests"]
    assert sent[-1] == {"type": "trace.forgotten", "id": 7, "cleared": True}
    assert not (renew / "turns.jsonl.1").exists()
    rows = [json.loads(line) for line in (renew / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["stage"] for row in rows] == ["trace.forget"] and rows[0]["cleared"] is True
    assert sorted(p.name for p in (renew / "slots").iterdir()) == ["baxy_prefix_key.slot"]


def test_a_trace_another_reader_holds_open_is_emptied(tmp_path, monkeypatch) -> None:
    from pathlib import Path
    from test_mind_final import _mind, _say
    mind, _ = _mind(tmp_path, [_say("Hola.")])
    mind.decide(1, "mi clave es pez")
    assert "pez" in mind.trace.read_text(encoding="utf-8")
    monkeypatch.setattr(Path, "unlink", lambda self, missing_ok=False: (_ for _ in ()).throw(PermissionError(self)))
    assert mind.forget_trace() is True
    assert mind.trace.read_text(encoding="utf-8") == ""


class _Process:
    """A llama-server that runs until told to exit (returncode)."""

    def __init__(self) -> None:
        self.returncode = None

    def poll(self):
        return self.returncode

    def terminate(self) -> None:
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode


def _laya(tmp_path, monkeypatch, restarts: int):
    import time as _time
    from baxy_mind import system_one as module
    from baxy_mind.mind import Mind
    from test_mind_final import FakeServer
    launched: list[_Process] = []

    def popen(*args, **kwargs):
        launched.append(_Process())
        return launched[-1]

    class Healthy:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            pass

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(module.subprocess, "Popen", popen)
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *args, **kwargs: Healthy())
    monkeypatch.setattr(module, "WATCH_SECONDS", 0.01)
    monkeypatch.setattr(module, "RESTARTS", restarts)
    real_wait = module.threading.Event.wait  # the pauses between starts, short
    monkeypatch.setattr(module.threading.Event, "wait",
                        lambda self, timeout=None: real_wait(self, min(timeout or 0.01, 0.01)))
    laya = module.SystemOne("laya.gguf", "llama-server.exe")
    mind = Mind(FakeServer([]), tmp_path / "turns.jsonl", laya)  # type: ignore[arg-type]
    laya.start()
    deadline = _time.monotonic() + 5
    while not laya.ready and _time.monotonic() < deadline:
        _time.sleep(0.01)
    return laya, launched, mind


def _rows_of(mind) -> list[dict]:
    return [json.loads(line) for line in mind.trace.read_text(encoding="utf-8").splitlines()] \
        if mind.trace.exists() else []


def test_a_decision_model_whose_server_exits_is_started_again_and_the_trace_says_so(tmp_path, monkeypatch) -> None:
    # P3 of the audit: Laya's server, once down, stayed down for the rest of the process, and nothing said so.
    import time as _time
    laya, launched, mind = _laya(tmp_path, monkeypatch, restarts=3)
    assert laya.ready and len(launched) == 1
    launched[0].returncode = 3221225477
    deadline = _time.monotonic() + 5
    while not (len(launched) == 2 and laya.ready) and _time.monotonic() < deadline:
        _time.sleep(0.01)
    laya.close()
    assert len(launched) == 2 and laya.restarts == 1
    rows = [(r["stage"], r.get("exit_code"), r.get("restart")) for r in _rows_of(mind)]
    assert rows == [("system_one.exited", 3221225477, 1), ("system_one.restarted", None, 1)]


def test_a_decision_model_that_keeps_exiting_is_left_off_and_the_trace_says_so(tmp_path, monkeypatch) -> None:
    import time as _time
    laya, launched, mind = _laya(tmp_path, monkeypatch, restarts=0)
    launched[0].returncode = 1
    deadline = _time.monotonic() + 5
    while not _rows_of(mind) and _time.monotonic() < deadline:
        _time.sleep(0.01)
    _time.sleep(0.05)
    laya.close()
    assert len(launched) == 1 and not laya.ready
    assert [(r["stage"], r["exit_code"], r["restart"]) for r in _rows_of(mind)] == [("system_one.exited", 1, None)]


@pytest.mark.parametrize("filled, why", [
    (None, "none"),
    ({"name": "system_power", "arguments": {}, "timings": {}}, {"other": "system_power"}),
    ({"name": "app_close", "arguments": {"appId": "Inventada"}, "timings": {}}, "unfounded"),
    (TimeoutError("budget"), {"failed": "TimeoutError"})])
def test_why_a_correction_did_not_run_is_in_the_trace(tmp_path, monkeypatch, filled, why) -> None:
    # P4 of the audit: a fill that failed, wrote nothing or another tool, or held a value nobody said, all read as
    # «not corrected» in the trace, with nothing apart for each.
    from test_mind_doubt_policy import _correcting
    from test_mind_aids import _trace
    mind, server, _ = _correcting(tmp_path, monkeypatch, "low_reversible", filled)
    close = next(t["function"] for t in mind.tools if t["function"]["name"] == "app_close")
    close["parameters"] = {"type": "object", "properties": {"appId": {"type": "string"}}, "required": ["appId"]}
    if isinstance(filled, Exception):
        server.fill_call = lambda body, wire: (_ for _ in ()).throw(filled)
    assert mind.decide(1, "ahora ciérralo")["operation"] is None
    rows = [r for r in _trace(mind) if "system_one" in r]
    assert rows[0]["system_one"]["fill"] == why and "corrected" not in rows[0]["system_one"]


def test_a_correction_that_ran_or_was_never_tried_writes_no_fill_field(tmp_path, monkeypatch) -> None:
    from test_mind_doubt_policy import _correcting
    from test_mind_aids import _trace
    mind, _, _ = _correcting(tmp_path, monkeypatch, "low_reversible",
                             {"name": "app_close", "arguments": {"appId": "Spotify"}, "timings": {}})
    monkeypatch.setenv("BAXY_S1_CORRECT", "")
    mind.decide(1, "ahora ciérralo")
    assert "fill" not in [r for r in _trace(mind) if "system_one" in r][0]["system_one"]


def test_a_rival_whose_name_could_not_be_read_is_in_the_trace(tmp_path, monkeypatch) -> None:
    from test_mind_doubt_policy import _layer2, _rival_call
    from test_mind_aids import _trace
    mind, server, one = _layer2(tmp_path, monkeypatch, "system_power", [_rival_call(0.5)])
    server.complete_name = lambda prompt, written: (_ for _ in ()).throw(TimeoutError("budget"))
    assert mind.decide(1, "apaga el pc")["operation"] == "system.power"
    judged = [r for r in _trace(mind) if "system_one" in r][0]["system_one"]
    assert judged["rivals_unread"] == [{"token": "app", "failed": "TimeoutError"}]
    assert "app_close" not in one.asked[0]["options"]


TRASHED = json.dumps({"status": "completed", "verification": "readback", "observed": {"fileName": "notas.txt"}})
ASKS = json.dumps({"status": "needs_confirmation", "next": "ask the person"})


@pytest.mark.parametrize("setting, told", [("", "confirm_pending (filesystem_known_trash_named) → completado"),
                                           ("none", "confirm_pending → completado")])
def test_an_answer_to_a_confirmation_says_which_call_it_answered(tmp_path, monkeypatch, setting, told) -> None:
    # Aid «confirm_names_call» (P5): «confirm_pending → completado y verificado» said nothing of what was done once the
    # turn that asked was cut; the App says which call waits with the person's words.
    from test_mind_final import _call, _mind, _say
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    mind, server = _mind(tmp_path, [_call("confirm_pending", {"approve": True}), _say("Listo, a la papelera."),
                                    _say("Sí.")])
    pending = {"operation": "filesystem.known.trash.named", "arguments": {"fileName": "notas.txt"}}
    assert mind.decide(1, "sí", pending)["operation"] == "confirmation.answer"
    mind.continue_turn(2, TRASHED)
    facts = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert f"[En este turno: {told}" in facts
    mind.decide(3, "¿ya la borraste?")
    assert told in _clock_of(server)


def test_a_press_answers_the_call_the_turn_before_asked(tmp_path, monkeypatch) -> None:
    from test_mind_final import _call, _mind, _say
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("filesystem_known_trash_named", {"fileName": "notas.txt"}),
                                    _say("¿La mando a la papelera?"), _say("Listo.")])
    mind.wire_to_op = {"filesystem_known_trash_named": "filesystem.known.trash.named"}
    mind.decide(1, "borra notas.txt")
    mind.continue_turn(2, ASKS, final=True)
    assert mind.confirm(3, True, "Sí")["operation"] == "confirmation.answer"
    mind.continue_turn(4, TRASHED)
    facts = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert "[En este turno: confirm_pending (filesystem_known_trash_named) → completado y verificado" in facts


def test_a_press_with_no_question_just_before_it_names_no_call(tmp_path, monkeypatch) -> None:
    from test_mind_final import _mind, _say
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_say("Hola."), _say("Listo.")])
    mind.decide(1, "hola")
    mind.confirm(2, True, "Sí")
    mind.continue_turn(3, TRASHED)
    facts = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert "[En este turno: confirm_pending → completado y verificado" in facts


@pytest.mark.parametrize("ended", ["dropped", "expired"])
def test_a_question_that_ended_unanswered_no_longer_waits_in_the_clock(tmp_path, ended) -> None:
    # Vivo larga (notebook, 2026-10-27): a close BAXY asked about and nobody answered stayed «espera el sí» in the
    # session's calls for every later turn; the next close of the same app was read as maybe answering it (confidence
    # 0.998 the first time, 0.53-0.70 after) and asked «¿cierro o confirmo algo pendiente?» with no call.
    from baxy_mind.mind import WAITS_FOR_YES
    from test_mind_final import _call, _mind, _say
    mind, server = _mind(tmp_path, [_call("app_close", {"appId": "Calculadora"}), _say("¿Cierro la Calculadora?"),
                                    _say("Vale."), _say("Hecho.")])
    mind.wire_to_op = {"app_close": "app.close"}
    mind.decide(1, "ciérrala")
    mind.continue_turn(2, ASKS, final=True)
    mind.decide(3, "otra cosa", {"operation": "app.close", "ended": ended})
    clock = _clock_of(server)
    assert f"app_close → {WAITS_FOR_YES}" not in clock and "app_close → no se ejecutó" in clock
    mind.decide(4, "y otra más")
    assert f"app_close → {WAITS_FOR_YES}" not in _clock_of(server)


def test_a_question_that_ended_after_its_call_may_have_started_says_so_in_the_clock(tmp_path) -> None:
    from baxy_mind.mind import NO_RESULT_RAN
    from test_mind_final import _call, _mind, _say
    mind, server = _mind(tmp_path, [_call("app_close", {"appId": "Calculadora"}), _say("¿Cierro la Calculadora?"),
                                    _say("Vale.")])
    mind.wire_to_op = {"app_close": "app.close"}
    mind.decide(1, "ciérrala")
    mind.continue_turn(2, ASKS, final=True)
    mind.decide(3, "otra cosa", {"operation": "app.close", "ended": "expired", "effectUncertain": True})
    assert f"app_close → {NO_RESULT_RAN}" in _clock_of(server)


@pytest.mark.parametrize("ended", ["dropped", "expired"])
def test_a_question_that_ended_unanswered_no_longer_waits_in_its_own_turn(tmp_path, ended) -> None:
    # Sesión larga sobre 8fa1e1430 (R7-NB-2): with the clock telling how the question ended, the turn that asked still
    # said «espera el sí» in its facts line; the same close of a new window tramos later was a question again (clarify
    # 0.46 against app 0.41, confirm 0.11 as a rival; «¿cierro la Calculadora o confirmo lo que pediste antes?»).
    from baxy_mind.mind import WAITS_FOR_YES
    from test_mind_final import _call, _mind, _say
    mind, server = _mind(tmp_path, [_call("app_close", {"appId": "Calculadora"}), _say("¿Cierro la Calculadora?"),
                                    _say("Vale."), _say("Hecho.")])
    mind.wire_to_op = {"app_close": "app.close"}
    mind.decide(1, "ciérrala")
    mind.continue_turn(2, ASKS, final=True)
    mind.decide(3, "otra cosa", {"operation": "app.close", "ended": ended})
    mind.decide(4, "y otra más")
    sent = server.bodies[-1]["messages"]
    facts = [m["content"] for m in sent if m["role"] == "tool"]
    assert len(facts) == 1 and f"app_close → {WAITS_FOR_YES}" not in facts[0]
    assert "[En este turno: app_close → no se ejecutó: " in facts[0]


def test_a_question_that_ended_unanswered_is_retold_in_its_turn_when_a_later_call_repeats_its_id(tmp_path) -> None:
    # The model's ids may repeat (here every call is «c1»): the turn that asked is the one retold, not a later one.
    from baxy_mind.mind import WAITS_FOR_YES
    from test_mind_final import _call, _mind, _say
    mind, server = _mind(tmp_path, [_call("app_close", {"appId": "Calculadora"}), _say("¿Cierro?"),
                                    _call("app_open", {"appId": "Paint"}), _say("Abierto."), _say("Vale."),
                                    _say("Hecho.")])
    mind.wire_to_op = {"app_close": "app.close", "app_open": "app.open"}
    mind.decide(1, "ciérrala")
    mind.continue_turn(2, ASKS, final=True)
    mind.decide(3, "abre paint")
    mind.continue_turn(4, TRASHED, final=True)
    mind.decide(5, "otra cosa", {"operation": "app.close", "ended": "dropped"})
    mind.decide(6, "y otra")
    sent = server.bodies[-1]["messages"]
    facts = [m["content"] for m in sent if m["role"] == "tool"]
    assert len(facts) == 2 and not any(f"app_close → {WAITS_FOR_YES}" in told for told in facts)
    assert "app_close → no se ejecutó: su pregunta quedó sin respuesta" in facts[0]
