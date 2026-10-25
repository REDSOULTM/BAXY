"""H-ctx «cerrados» (BAXY_RENEW_CTX_MODE=cerrados): a closed turn's views lose their controls, its long texts and lists are
cut with a note of how much, never a failure field nor a facts line; off by default."""
import json
from pathlib import Path

from baxy_mind.context_cerrados import CLOSED_VIEW, CUT_LIST, CUT_TEXT, TEXT_CAP, clean_closed

from test_mind_final import _call, _mind, _say

CONTROLS = "\n".join(f"[{i}] Button «Botón {i}» (centro)" for i in range(2, 30))
VIEW = json.dumps({"status": "completed", "verification": "output_only",
                   "view": "Ventana «Sin título: Bloc de notas» (Notepad, window 4242), al frente\nFoco: [1] Document\n"
                           f"Controles:\n[0] MenuItem «Archivo»\n[1] Document «Texto»\n{CONTROLS}"}, ensure_ascii=False)
PAGE = json.dumps({"status": "completed", "verification": "output_only",
                   "observed": {"title": "RFC 2324", "hasMore": True, "nextOffset": 4000, "text": "t" * 4000}})
TYPED = json.dumps({"status": "completed", "verification": "readback", "observed": {"delivered": True}})
FAILED = json.dumps({"status": "failed", "error": "window_not_found", "reason": "r" * 2000,
                     "observed": {"candidates": [{"title": f"Ventana {i}"} for i in range(10)]}})


def _session(tmp_path: Path, monkeypatch, setting: str | None) -> tuple:
    if setting is None:
        monkeypatch.delenv("BAXY_RENEW_CTX_MODE", raising=False)
    else:
        monkeypatch.setenv("BAXY_RENEW_CTX_MODE", setting)
    tmp_path.mkdir(parents=True, exist_ok=True)
    mind, server = _mind(tmp_path, [
        _call("input_visible_controls", {"application": "Bloc de notas"}),
        _call("web_fetch", {"url": "https://www.rfc-editor.org/rfc/rfc2324"}),
        _call("window_resolve", {"name": "Paint"}),
        _say("Escribí «reunión con Pedro el martes»."),
        _call("input_text_type", {"text": "miércoles", "window": 4242}),
        _say("Listo, ahora dice miércoles.")])
    step = mind.decide(1, "abre el bloc de notas y escribe: reunión con Pedro el martes")
    for index, result in enumerate([VIEW, PAGE, FAILED]):
        assert step["kind"] == "action"
        step = mind.continue_turn(index + 2, result)
    assert step["kind"] == "conversation"
    mind.decide(5, "cámbialo, era el miércoles, no el martes")
    mind.continue_turn(6, TYPED)
    return mind, server


def _tools(body: dict) -> list[str]:
    return [m["content"] for m in body["messages"] if m["role"] == "tool"]


def test_off_by_default_closed_turns_stay_whole(tmp_path: Path, monkeypatch) -> None:
    _, server = _session(tmp_path, monkeypatch, None)
    tools = _tools(server.bodies[-1])
    assert "Botón 29" in tools[0] and "t" * 4000 in tools[1] and "r" * 2000 in tools[2]


def test_the_next_turn_reads_the_closed_turns_results_in_short(tmp_path: Path, monkeypatch) -> None:
    _, plain = _session(tmp_path / "a", monkeypatch, None)
    mind, server = _session(tmp_path / "b", monkeypatch, "cerrados")
    # The first turn read its results whole while it was open.
    assert "Botón 29" in _tools(server.bodies[3])[0] and "t" * 4000 in _tools(server.bodies[3])[1]
    decide = server.bodies[4]
    tools = _tools(decide)
    view = json.loads(tools[0].split("\n[En este turno: ")[0])
    assert view["view"].startswith("Ventana «Sin título: Bloc de notas» (Notepad, window 4242), al frente\nFoco:")
    assert view["view"].endswith(CLOSED_VIEW.format(n=31)) and "Botón 29" not in tools[0]
    page = json.loads(tools[1].split("\n[En este turno: ")[0])["observed"]
    assert page["text"] == "t" * TEXT_CAP + CUT_TEXT.format(n=4000 - TEXT_CAP)
    assert page["hasMore"] is True and page["nextOffset"] == 4000 and page["title"] == "RFC 2324"
    # A failure keeps every word of how it failed; only its long list is cut, with how many more.
    failed = json.loads(tools[2].split("\n[En este turno: ")[0])
    assert failed["status"] == "failed" and failed["error"] == "window_not_found" and failed["reason"] == "r" * 2000
    assert failed["observed"]["candidates"][-1] == CUT_LIST.format(n=4) and len(failed["observed"]["candidates"]) == 7
    # Facts lines, the person's words, BAXY's words and calls, and the fixed prefix stay as they were.
    before = _tools(plain.bodies[4])
    assert [t.split("\n[En este turno: ")[1] for t in tools] == [t.split("\n[En este turno: ")[1] for t in before]
    assert [m for m in decide["messages"] if m["role"] != "tool"] == \
        [m for m in plain.bodies[4]["messages"] if m["role"] != "tool"]
    assert decide["tools"] == plain.bodies[4]["tools"] and decide["messages"][0] == plain.bodies[4]["messages"][0]
    # The open turn's own result is whole, and the closed turn is not changed a second time.
    last = _tools(server.bodies[-1])
    assert last[:3] == tools and last[3].startswith(_tools(plain.bodies[-1])[3].split("\n[En este turno: ")[0])
    rows = [json.loads(line) for line in mind.trace.read_text(encoding="utf-8").splitlines()]
    assert [r["results"] for r in rows if r["stage"] == "ctx.cerrados"] == [3]


def test_the_cut_is_idempotent_and_leaves_text_that_is_not_json(tmp_path: Path) -> None:
    conv = [{"role": "user", "content": "x"},
            {"role": "tool", "tool_call_id": "a", "content": PAGE + "\n[En este turno: web_fetch → leído]"},
            {"role": "tool", "tool_call_id": "b", "content": "No se ejecutó.\n[En este turno: x → no se ejecutó]"}]
    assert clean_closed(conv, len(conv), "\n[En este turno: ") == 1
    once = json.dumps(conv, ensure_ascii=False)
    assert clean_closed(conv, len(conv), "\n[En este turno: ") == 0
    assert json.dumps(conv, ensure_ascii=False) == once
    assert conv[2]["content"] == "No se ejecutó.\n[En este turno: x → no se ejecutó]"
