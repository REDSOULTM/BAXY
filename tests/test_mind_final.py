"""A turn of the mind (src/baxy_mind/mind.py) whose prompt grew past the context (llama-server's HTTP 400), and one that
answers in words after its calls because the model wrote nothing after a call (FT/proveedores goal, e2e E022)."""
import io
import json
import urllib.error
from pathlib import Path

import pytest

from baxy_mind.llm_server import REREAD_TOKENS
from baxy_mind.mind import COMPACTED, NO_MORE_CALLS, Mind


class FakeServer:
    context = 49152
    reread_tokens = REREAD_TOKENS  # CUDA's (LlmServer.reread_tokens)

    def __init__(self, replies: list) -> None:
        self.replies = replies
        self.bodies: list[dict] = []
        self.closed: list[dict] = []

    def ask_apart(self, body: dict, timeout: float = 60.0) -> dict:
        self.closed.append(json.loads(json.dumps(body)))
        return their_answer(self.replies)

    def chat(self, body: dict, timeout: float = 120.0, gives_way: bool = False) -> dict:
        self.bodies.append(json.loads(json.dumps(body)))
        self.gave_way = gives_way
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def tokenize(self, text: str) -> list[int]:
        return [0] * (len(text) // 4)


def their_answer(replies: list) -> dict:
    """SIS3: the closed question on the person's words (Mind._their_answer), answered as the scripted model's next reply
    would answer: a confirm_pending yes or no is that answer; a yes is taken, since the mind gives it itself, and
    anything else stays for the decision (the model's no still answers); anything else is «maybe» (SIS4: the kinds
    of Mind.THEIR_ANSWER_KINDS, «now» the yes)."""
    after = replies[0] if replies and isinstance(replies[0], dict) else {}
    calls = ((after.get("choices") or [{}])[0].get("message") or {}).get("tool_calls") or []
    answer = "maybe"
    if calls and calls[0]["function"]["name"] == "confirm_pending":
        given = json.loads(calls[0]["function"].get("arguments") or "{}").get("answer")
        if given in ("yes", "no"):
            answer = {"yes": "now", "no": "no"}[given]
        if given == "yes":
            replies.pop(0)
    return {"choices": [{"message": {"content": answer}}]}


def _call(name: str, arguments: dict) -> dict:
    return {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": "c1", "function": {"name": name, "arguments": json.dumps(arguments)}}]}}]}


def _say(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


def _overflow() -> urllib.error.HTTPError:
    body = b'{"error":{"code":400,"type":"exceed_context_size_error"}}'
    return urllib.error.HTTPError("http://127.0.0.1/v1/chat/completions", 400, "Bad Request", {}, io.BytesIO(body))


def _mind(tmp_path: Path, replies: list) -> tuple[Mind, FakeServer]:
    server = FakeServer(replies)
    mind = Mind(server, tmp_path / "turns.jsonl")  # type: ignore[arg-type]
    mind.call_tokens = [248058]  # set at warm-up from the server's vocabulary: the token that opens a call
    return mind, server


def test_a_turn_past_the_context_leaves_out_its_earlier_results_and_goes_on(tmp_path: Path) -> None:
    # Al máximo 1.2: with nothing before it, the turn's earlier results leave out their bodies (their facts stay) and
    # the model goes on with its tools; it was made to answer in words at once.
    page = {"url": "https://example.org/rfc"}
    mind, server = _mind(tmp_path, [_call("web_fetch", page), _call("web_fetch", page), _overflow(),
                                    _say("La página no dice el código.")])
    assert mind.decide(1, "lee la página")["kind"] == "action"
    assert mind.continue_turn(2, json.dumps({"status": "completed", "text": "a" * 6000}))["kind"] == "action"
    result = mind.continue_turn(3, json.dumps({"status": "completed", "text": "b" * 6000}))
    assert result["reply"] == "La página no dice el código."
    last = server.bodies[-1]
    assert "tool_choice" not in last
    tools = [m["content"] for m in last["messages"] if m["role"] == "tool"]
    # 8.2: a result with no typed verification is «sin verificar».
    assert tools[0] == COMPACTED + "\n[En este turno: web_fetch → terminó sin verificar su efecto]"
    assert "b" * 6000 in tools[1]


def test_a_turn_near_the_context_makes_room_before_it_asks(tmp_path: Path) -> None:
    # Pedido del dueño 2026-11-02 («arregla el problema del contexto»): a long turn only made room once llama-server had
    # refused it (400) or cut its answer («Listo,»). The last reply's usage says how full the context already is: with a
    # result and the next answer it would not fit, so the earlier results leave out their bodies before the next request.
    page = {"url": "https://example.org/rfc"}
    near = _call("web_fetch", page)
    near["usage"] = {"prompt_tokens": FakeServer.context - 2000, "completion_tokens": 20}
    mind, server = _mind(tmp_path, [_call("web_fetch", page), near, _say("La página no dice el código.")])
    mind.decide(1, "lee la página")
    mind.continue_turn(2, json.dumps({"status": "completed", "text": "a" * 6000}))
    result = mind.continue_turn(3, json.dumps({"status": "completed", "text": "b" * 6000}))
    assert result["reply"] == "La página no dice el código."
    tools = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"]
    assert tools[0].startswith(COMPACTED)
    assert "b" * 6000 in tools[1]


def test_a_turn_with_room_to_spare_keeps_its_results(tmp_path: Path) -> None:
    page = {"url": "https://example.org/rfc"}
    roomy = _call("web_fetch", page)
    roomy["usage"] = {"prompt_tokens": 20000, "completion_tokens": 20}
    mind, server = _mind(tmp_path, [_call("web_fetch", page), roomy, _say("Listo.")])
    mind.decide(1, "lee la página")
    mind.continue_turn(2, json.dumps({"status": "completed", "text": "a" * 6000}))
    mind.continue_turn(3, json.dumps({"status": "completed", "text": "b" * 6000}))
    tools = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"]
    assert "a" * 6000 in tools[0]


def _cut(text: str) -> dict:
    # What llama-server answers when the prompt fits but the context fills while the answer is written: «length» before
    # the max_tokens asked for (uso real 02-11: 53,245 + 3 = 53,248 tokens, the slot's context; the person heard «Listo,»).
    return {"choices": [{"finish_reason": "length", "message": {"content": text}}],
            "usage": {"prompt_tokens": 53245, "completion_tokens": 3}}


def test_an_answer_cut_by_a_full_context_makes_room_and_is_written_again(tmp_path: Path) -> None:
    page = {"url": "https://example.org/rfc"}
    mind, server = _mind(tmp_path, [_call("web_fetch", page), _call("web_fetch", page), _cut("Listo,"),
                                    _say("La página no dice el código.")])
    mind.decide(1, "lee la página")
    mind.continue_turn(2, json.dumps({"status": "completed", "text": "a" * 6000}))
    result = mind.continue_turn(3, json.dumps({"status": "completed", "text": "b" * 6000}))
    assert result["reply"] == "La página no dice el código."
    tools = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"]
    assert tools[0].startswith(COMPACTED)


def test_an_answer_that_reached_max_tokens_is_not_taken_for_a_full_context(tmp_path: Path) -> None:
    long = {"choices": [{"finish_reason": "length", "message": {"content": "Una respuesta larga"}}],
            "usage": {"prompt_tokens": 40000, "completion_tokens": 768}}
    mind, server = _mind(tmp_path, [long])
    assert mind.decide(1, "cuéntame algo largo")["reply"] == "Una respuesta larga"
    assert len(server.bodies) == 1


def test_an_overflow_with_nothing_to_cut_is_not_hidden(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [_overflow()])
    try:
        mind.decide(1, "hola")
    except urllib.error.HTTPError:
        return
    raise AssertionError("the refused prompt must reach the App as a failed turn")


def test_nothing_written_after_a_call_is_answered_in_words(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("audio_volume", {"level": 30}), _say(""), _say("Puse el volumen al 30.")])
    mind.decide(1, "pon el volumen al 30")
    result = mind.continue_turn(2, json.dumps({"status": "completed", "verified": True}))
    assert result["reply"] == "Puse el volumen al 30."
    assert server.bodies[-1]["tool_choice"] == "none"


def test_a_decision_that_did_not_come_after_a_result_is_asked_again_from_that_result(tmp_path: Path) -> None:
    # R7-NB-1 (CU C03): the decision after app_open ran past the request's budget and the turn ended with no words; asked
    # again, the model decides from the result already in the turn, which is not read in twice.
    mind, server = _mind(tmp_path, [_call("app_open", {"appId": "Lanzador", "place": "library"}), TimeoutError("spent"),
                                    _say("Pedí abrirlo en la biblioteca; no miré si se ve.")])
    mind.decide(1, "abre el lanzador en la biblioteca")
    observation = json.dumps({"status": "completed", "verification": "delivered_only"})
    with pytest.raises(TimeoutError):
        mind.continue_turn(2, observation)
    result = mind.continue_turn(3, observation)
    assert result["reply"] == "Pedí abrirlo en la biblioteca; no miré si se ve."
    assert server.bodies[-1]["messages"] == server.bodies[-2]["messages"]
    assert [m["role"] for m in server.bodies[-1]["messages"]].count("tool") == 1


def test_a_decision_asked_again_keeps_the_turn_closed_in_words(tmp_path: Path) -> None:
    # R7-NB-1, review: a decision in words only (here the App's final; the mind closes a turn's calls itself the same
    # way, _next with final) ran past the budget; asked again with final false, the model still answers in words only.
    mind, server = _mind(tmp_path, [_call("audio_volume", {"level": 30}), TimeoutError("spent"),
                                    _say("Puse el volumen al 30.")])
    mind.decide(1, "pon el volumen al 30")
    observation = json.dumps({"status": "completed", "verified": True})
    with pytest.raises(TimeoutError):
        mind.continue_turn(2, observation, final=True)
    assert mind.continue_turn(3, observation)["reply"] == "Puse el volumen al 30."
    assert server.bodies[-2]["tool_choice"] == server.bodies[-1]["tool_choice"] == "none"


def test_a_continuation_with_no_result_to_decide_from_is_still_refused(tmp_path: Path) -> None:
    mind, _ = _mind(tmp_path, [_call("audio_volume", {"level": 30}), _say("Puse el volumen al 30.")])
    mind.decide(1, "pon el volumen al 30")
    mind.continue_turn(2, json.dumps({"status": "completed", "verified": True}))
    with pytest.raises(RuntimeError):
        mind.continue_turn(3, json.dumps({"status": "completed", "verified": True}))


def test_the_turns_facts_say_where_a_file_was_made(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("file_write", {"path": "compras.txt"}),
                                    _say("Lo creé.")])
    mind.decide(1, "crea un archivo")
    observed = {"status": "completed", "verification": "readback",
                "observed": {"name": "compras.txt", "fullPath": r"C:\Users\ana\compras.txt"}}
    mind.continue_turn(2, json.dumps(observed))
    tool = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert r"file_write → completado y verificado en C:\Users\ana\compras.txt" in tool


# H6 (holdout v5 V5F028/V5F029): 15 paged reads of a long log; each left-out result kept a facts line listing every call
# before it, the last answer (tool_choice none) did not fit and the person got no answer at all. The context is in
# characters here (a fake slot that refuses past LIMIT).
LIMIT = 24000
LOG = "".join(f"2026-10-01 03:{m:02d}:{s:02d} INFO request served\r\n" for m in range(60) for s in range(60))


def _page(offset: int) -> str:
    """A file_read result as the kernel gives it: a 4,000-character page of a 367,504-character log."""
    return json.dumps({"status": "completed", "verification": "output_only", "observed": {
        "version": 1, "kind": "text", "reviewLabel": "server.log", "folder": "home", "characters": 367504,
        "totalLines": 9000, "offset": offset, "lines": 99, "fromLine": offset // 40 + 1, "toLine": offset // 40 + 99,
        "returnedCharacters": 4000, "hasMore": True, "nextOffset": offset + 4000, "endReached": False,
        "readInPart": True, "bytes": 367504, "fileSha256": "11" * 32, "text": LOG[offset:offset + 4000]}},
        separators=(",", ":"))


def _refusing_past(server, limit: int) -> None:
    chat = server.chat

    def refuse(body):
        if len(json.dumps(body["messages"][1:], ensure_ascii=False)) > limit:
            raise _overflow()
        return chat(body)

    server.chat = refuse


def test_the_last_answer_of_a_turn_of_paged_reads_always_comes(tmp_path: Path) -> None:
    pages = [_call("file_read", {"path": "home/server.log", "offset": 4000 * n}) for n in range(15)]
    mind, server = _mind(tmp_path, [*pages, _say("Leí sólo una parte del archivo; en esa parte no vi errores.")])
    _refusing_past(server, LIMIT)
    assert mind.decide(1, "check server.log and tell me if there were any errors anywhere in the file")["kind"] == "action"
    for step in range(14):
        assert mind.continue_turn(step, _page(4000 * step))["kind"] == "action"
    # The App's 15th call closes the turn: the model answers in words from what the results show.
    result = mind.continue_turn(15, _page(4000 * 14), final=True)
    assert result["kind"] == "conversation" and result["reply"]
    last = server.bodies[-1]
    assert last["tool_choice"] == "none"
    told = [m["content"] for m in last["messages"] if m["role"] == "tool"][-1]
    assert NO_MORE_CALLS.strip() in told
    assert "de 9000" in told and "no llegó al final" in told


def test_the_last_answer_comes_even_when_its_newest_result_alone_does_not_fit(tmp_path: Path) -> None:
    # The last resort, only for the last answer: the newest result leaves out its body too, and its facts line (how much
    # of the file was read) stays where the model reads, said as omitted.
    mind, server = _mind(tmp_path, [_call("file_read", {"path": "home/server.log"}),
                                    _say("No llegué a leer el final del archivo.")])
    _refusing_past(server, 3000)
    assert mind.decide(1, "check server.log")["kind"] == "action"
    result = mind.continue_turn(2, _page(0), final=True)
    assert result["reply"] == "No llegué a leer el final del archivo."
    told = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert told.startswith(COMPACTED) and "de 9000" in told and NO_MORE_CALLS.strip() in told


def test_a_decision_has_room_for_a_document_and_stays_inside_the_apps_budget(tmp_path: Path) -> None:
    # Feria 2026-10-27 (W6): office_document_create takes the body; at 512 tokens a story was cut mid-call. Measured on
    # the notebook (NB-L): ~36 tokens/s and ~2 tokens a word; the App gives a decision 30 s (TurnRequestTimeout), so the
    # cap leaves room for the prefix: about 350 words, never a decision the App gives up on
    mind, server = _mind(tmp_path, [_say("Listo.")])
    mind.decide(1, "Escribe un cuento largo en un documento.")
    assert 640 <= server.bodies[0]["max_tokens"] <= 900


def _server_error(code: int = 500) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://127.0.0.1/v1/chat/completions", code, "Internal Server Error", {},
                                  io.BytesIO(b'{"error":{"code":500,"type":"server_error"}}'))


def test_a_decision_the_model_server_failed_is_answered_in_words(tmp_path: Path) -> None:
    # Uso real 2026-11-03 (F4, 14:47): turn.decide got llama-server's HTTP 500 (after LlmServer's retry) and BAXY said
    # nothing. The model is asked once more for words only, told why; its words are the answer, the note is not kept.
    from baxy_mind.mind import SERVER_ERROR_NOTE
    mind, server = _mind(tmp_path, [_server_error(), _say("No pude pensar la respuesta, ¿me lo repites?")])
    result = mind.decide(1, "qué es un agujero negro")
    assert result["kind"] == "conversation"
    assert result["reply"] == "No pude pensar la respuesta, ¿me lo repites?"
    last = server.bodies[-1]
    assert last["tool_choice"] == "none" and last["logit_bias"]
    assert last["messages"][-1] == {"role": "user", "content": SERVER_ERROR_NOTE.format(code=500)}
    assert SERVER_ERROR_NOTE[:40] not in json.dumps(mind.conversation, ensure_ascii=False)
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(row.get("kind") == "server_error" and row.get("code") == 500 for row in rows)


def test_a_model_server_that_keeps_failing_reaches_the_app(tmp_path: Path) -> None:
    # Asked once in words: a second 5xx is the App's decision_unavailable, never a loop.
    mind, server = _mind(tmp_path, [_server_error(), _server_error(503)])
    with pytest.raises(urllib.error.HTTPError):
        mind.decide(1, "qué es un agujero negro")
    assert len(server.bodies) == 2


def test_a_client_error_of_the_model_server_is_not_answered_in_words(tmp_path: Path) -> None:
    # A 4xx is the request's own (a 400 past the context makes room instead): only the server's failure is told.
    error = urllib.error.HTTPError("http://127.0.0.1/v1/chat/completions", 404, "Not Found", {}, io.BytesIO(b"{}"))
    mind, server = _mind(tmp_path, [error])
    with pytest.raises(urllib.error.HTTPError):
        mind.decide(1, "hola")
    assert len(server.bodies) == 1
