"""SIS3 (F1 of REV10, SIS2): whether the person's words after a call that waits for their «sí» are their yes is the model's
to read, in a closed question of its own (Mind._their_answer): yes, no or other, by a grammar. Only yes runs what waits;
the model's own confirm_pending yes after words read otherwise is not their yes."""
import json
import urllib.error

import pytest

from test_mind_final import _call, _mind, _say

PENDING = {"operation": "baxy.settings.set", "arguments": {"setting": "web_search", "value": "on"}}


class Closed:
    """A fake model whose closed question answers `verdict` (a string, or an exception it raises)."""

    def __init__(self, server, verdict) -> None:
        self.server, self.verdict, self.asked = server, verdict, []
        server.ask_apart = self.answer

    def answer(self, body: dict, **kwargs) -> dict:
        self.asked.append(json.loads(json.dumps(body)))
        if isinstance(self.verdict, Exception):
            raise self.verdict
        return {"choices": [{"message": {"content": self.verdict}}]}


def _asked_mind(tmp_path, replies, verdict):
    """BAXY asked whether to turn the web search on (the call waits); the person's words come next."""
    mind, server = _mind(tmp_path, [_call("baxy_settings_set", PENDING["arguments"]), _say("¿Enciendo la búsqueda web?"),
                                    *replies])
    mind.wire_to_op = {"baxy_settings_set": "baxy.settings.set"}
    mind.decide(1, "busca el horario del museo")
    mind.continue_turn(2, json.dumps({"status": "needs_confirmation", "next": "ask the person"}), final=True)
    return mind, server, Closed(server, verdict)


def test_their_yes_read_by_its_own_question_answers_the_waiting_call(tmp_path) -> None:
    mind, server, closed = _asked_mind(tmp_path, [], "now")
    decisions = len(server.bodies)
    result = mind.decide(3, "dale nomás", PENDING)
    assert (result["kind"], result["operation"], result["arguments"]) == ("action", "confirmation.answer",
                                                                         {"answer": "yes"})
    assert len(server.bodies) == decisions  # no decision of the model: their answer is that question's
    assert result.get("theirYes") is True
    body = closed.asked[0]
    assert body["grammar"] == 'root ::= "now" | "no" | "later" | "maybe" | "ask" | "different" | "yours"'
    # Only the exchange (SIS2 arm b): BAXY's question and their words, no tools and none of the conversation.
    assert "tools" not in body and [m["role"] for m in body["messages"]] == ["system", "user"]
    note = body["messages"][-1]["content"]
    assert "«¿Enciendo la búsqueda web?»" in note and "«dale nomás»" in note


def test_the_question_holds_only_the_exchange_not_the_conversation(tmp_path) -> None:
    # SIS3B, banco: on the whole conversation, where BAXY's own offer stands, «puede ser» was read as a yes.
    mind, server, closed = _asked_mind(tmp_path, [_say("Mañana a primera hora, entonces. ¿La enciendo ahora o espero?")],
                                       "other")
    mind.decide(3, "sí, pero mañana", PENDING)
    asked = json.dumps(closed.asked[0], ensure_ascii=False)
    assert "busca el horario del museo" not in asked and mind._system(False)[:200] not in asked
    assert server.bodies[-1]["messages"][-1]["content"].startswith("sí, pero mañana")  # the turn reads them after it


@pytest.mark.parametrize("verdict", ["later", "maybe", "no", "yes", "other", urllib.error.URLError("down"), TimeoutError("slow")])
def test_words_read_as_no_yes_leave_it_waiting_and_the_models_yes_is_not_theirs(tmp_path, verdict) -> None:
    # SIS2: «puede ser», «I guess?», «sí, pero mañana»: the 4B answered yes for them. Read as other or no (or not read),
    # the model's own confirm_pending yes never reaches the App: it reads why and answers in words. A no is not given
    # for them (SIS3, banco: the questions «¿y eso qué significa…?», «wait, is that safe?» were read as no, 3 of 3).
    mind, server, _ = _asked_mind(tmp_path, [_call("confirm_pending", {"answer": "yes"}),
                                             _say("Vale, la dejo para mañana. ¿La enciendo entonces?")], verdict)
    # REM2 (REV13 A-1): it reaches the App as «unclear», which keeps it waiting, and the model reads why.
    result = mind.decide(3, "puede ser", PENDING)
    assert result["operation"] == "confirmation.answer" and result["arguments"] == {"answer": "unclear"}
    said = mind.continue_turn(4, json.dumps({"status": "needs_confirmation", "operation": "baxy.settings.set"}))
    assert said["operation"] is None and said["reply"].startswith("Vale, la dejo")
    told = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert json.loads(told.split("\n[En este turno")[0])["error"] == "not_their_yes"


def test_the_models_no_or_unclear_still_reaches_the_app(tmp_path) -> None:
    # Only a yes is the person's to give: a no drops nothing that would run, an unclear asks again.
    mind, _, _ = _asked_mind(tmp_path, [_call("confirm_pending", {"answer": "unclear"})], "other")
    assert mind.decide(3, "¿y eso qué es?", PENDING)["arguments"] == {"answer": "unclear"}


def test_with_nothing_waiting_no_question_is_asked(tmp_path) -> None:
    mind, server = _mind(tmp_path, [_say("Hola.")])
    closed = Closed(server, "now")
    mind.decide(1, "hola")
    assert closed.asked == []


def _offered_mind(tmp_path, replies, verdict):
    """The memory was off (memory_disabled) and BAXY asked whether to turn it on (TPV3)."""
    mind, server = _mind(tmp_path, [_call("memory_save", {"text": "x"}), _say("La memoria está apagada. ¿La activo?"),
                                    *replies])
    mind.wire_to_op = {"memory_save": "memory.save", "memory_enable": "memory.enable"}
    mind.decide(1, "recuerda que mi gata se llama Mora")
    mind.continue_turn(2, json.dumps({"status": "rejected", "error": "memory_disabled"}))
    return mind, server, Closed(server, verdict)


@pytest.mark.parametrize("verdict, theirs", [("now", True), ("yours", None), ("no", None)])
def test_baxys_offer_is_taken_only_with_their_yes(tmp_path, verdict, theirs) -> None:
    # TPV3's offer (NativeTurnLoop.TakesTheOffer): the App takes the memory_enable call as their answer only with the
    # mind's theirYes, read by the same question.
    mind, _, closed = _offered_mind(tmp_path, [_call("memory_enable", {})], verdict)
    result = mind.decide(3, "ya, actívala", None)
    assert result["operation"] == "memory.enable" and result.get("theirYes") is theirs
    assert len(closed.asked) == 1 and "«La memoria está apagada. ¿La activo?»" in closed.asked[0]["messages"][-1]["content"]


def test_the_question_apart_sets_the_slots_state_aside_and_back(tmp_path, monkeypatch) -> None:
    # LlmServer.ask_apart: the one slot keeps one prompt (-cram 0), so its state is saved before and restored after, as
    # the App's vision question does; the file, which holds the conversation, is removed.
    from baxy_mind import llm_server

    server = llm_server.LlmServer.__new__(llm_server.LlmServer)
    server.slot, server.remote, server.slot_dir, server.resident = 0, None, tmp_path, "x"
    server.wait_ready = lambda timeout: None
    server._within = lambda timeout: timeout
    server._advance = lambda: None
    posts = []

    def post(path, body, timeout):
        posts.append((path, body.get("filename") or body.get("grammar")))
        if path.endswith("action=save"):
            (tmp_path / body["filename"]).write_bytes(b"state")
            return {"n_saved": 47000}
        return {"n_restored": 47000} if "action=restore" in path else {"choices": [{"message": {"content": "no"}}]}

    server._post = post
    reply = server.ask_apart({"messages": [], "grammar": "g"})
    assert reply["choices"][0]["message"]["content"] == "no"
    assert posts == [("/slots/0?action=save", "baxy_answer_hold_0.bin"), ("/v1/chat/completions", "g"),
                     ("/slots/0?action=restore", "baxy_answer_hold_0.bin")]
    assert not list(tmp_path.iterdir()) and server.resident is None


def test_each_step_of_the_question_apart_is_the_server_advancing(tmp_path, monkeypatch) -> None:
    # SIS4 (VIVO15, «Luego.» in Esencial): the slot's save, the question and the restore took the request's whole window
    # (LlmServer.REQUEST_SECONDS, 24 s) with no advance told; the question failed (TimeoutError, read as other) and the
    # decision after it found the budget spent: «El modelo no respondió». Each step done is the server advancing, as a
    # streamed read is (uso-124): the next one, and the decision, have the window again. Times scaled down: 0.3 s.
    import io
    import time

    from baxy_mind import llm_server

    took = 0.2

    def urlopen(request, timeout):
        if timeout < took:
            raise TimeoutError("timed out")
        time.sleep(took)
        path = request.full_url
        if "action=save" in path:
            (tmp_path / "baxy_answer_hold_0.bin").write_bytes(b"state")
            return io.BytesIO(b'{"n_saved": 47000}')
        if "action=restore" in path:
            return io.BytesIO(b'{"n_restored": 47000}')
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": "other"}}]}).encode("utf-8"))

    monkeypatch.setattr(llm_server.urllib.request, "urlopen", urlopen)
    monkeypatch.setenv("BAXY_VISION_SLOT_DIR", str(tmp_path))
    server = llm_server.LlmServer("model.gguf", "llama-server.exe")
    server._ready.set()
    server.slot_dir = tmp_path
    window = 0.3
    monkeypatch.setattr(llm_server.LlmServer, "REQUEST_SECONDS", window)
    server.deadline = time.monotonic() + window
    reply = server.ask_apart({"messages": [], "grammar": "g"})
    assert reply["choices"][0]["message"]["content"] == "other"
    assert server._within(1.0) > window / 2  # the decision after it still has its window
    assert not list(tmp_path.iterdir())
