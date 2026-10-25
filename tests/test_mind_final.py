"""A turn of the mind (src/baxy_mind/mind.py) whose prompt grew past the context (llama-server's HTTP 400), and one that
answers in words after its calls because the model wrote nothing after a call (FT/proveedores goal, e2e E022)."""
import io
import json
import urllib.error
from pathlib import Path

from baxy_mind.mind import COMPACTED, NO_MORE_CALLS, Mind


class FakeServer:
    context = 49152

    def __init__(self, replies: list) -> None:
        self.replies = replies
        self.bodies: list[dict] = []

    def chat(self, body: dict) -> dict:
        self.bodies.append(json.loads(json.dumps(body)))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def tokenize(self, text: str) -> list[int]:
        return [0] * (len(text) // 4)


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


def test_the_turns_facts_say_where_a_file_was_made(tmp_path: Path) -> None:
    mind, server = _mind(tmp_path, [_call("file_write", {"relativePath": "compras.txt", "folder": "home"}),
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
    pages = [_call("file_read", {"fileName": "server.log", "folder": "home", "offset": 4000 * n}) for n in range(15)]
    mind, server = _mind(tmp_path, [*pages, _say("I read only part of the file; in that part I saw no errors.")])
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
    mind, server = _mind(tmp_path, [_call("file_read", {"fileName": "server.log", "folder": "home"}),
                                    _say("No llegué a leer el final del archivo.")])
    _refusing_past(server, 3000)
    assert mind.decide(1, "check server.log")["kind"] == "action"
    result = mind.continue_turn(2, _page(0), final=True)
    assert result["reply"] == "No llegué a leer el final del archivo."
    told = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"][-1]
    assert told.startswith(COMPACTED) and "de 9000" in told and NO_MORE_CALLS.strip() in told
