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


@pytest.mark.parametrize("setting, told", [("", "lo que vio se omitió"), ("none", "lo que vio está arriba")])
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
    assert f"file_read → lectura: sólo miró, sin abrir, cerrar ni cambiar nada; {told}" in _clock_of(server)


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
    assert "file_read → lectura: sólo miró, sin abrir, cerrar ni cambiar nada; lo que vio está arriba" in _clock_of(
        server)
