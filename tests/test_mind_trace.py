"""The mind's trace (src/baxy_mind/__main__.py, BAXY Renew al máximo 11.6): it has a size cap."""
from pathlib import Path

from baxy_mind.__main__ import bounded_trace


def test_a_trace_past_its_cap_is_kept_once_as_dot_one_and_a_new_one_starts(tmp_path: Path) -> None:
    trace = tmp_path / "renew" / "turns.jsonl"
    trace.parent.mkdir()
    (trace.parent / "turns.jsonl.1").write_text("older\n", encoding="utf-8")
    trace.write_text("x" * 101, encoding="utf-8")

    assert bounded_trace(trace, limit=100) == trace

    assert not trace.exists()
    assert (trace.parent / "turns.jsonl.1").read_text(encoding="utf-8") == "x" * 101


def test_a_trace_under_its_cap_stays_and_a_missing_folder_is_made(tmp_path: Path) -> None:
    trace = tmp_path / "renew" / "turns.jsonl"
    assert bounded_trace(trace, limit=100) == trace
    assert trace.parent.is_dir()

    trace.write_text("x" * 100, encoding="utf-8")
    bounded_trace(trace, limit=100)

    assert trace.read_text(encoding="utf-8") == "x" * 100
    assert not (trace.parent / "turns.jsonl.1").exists()


def test_a_bench_puts_the_trace_in_its_run_and_the_product_keeps_the_owners_folder(tmp_path: Path) -> None:
    # Audit w8-medir: the e2e and falsedades benches wrote their turns into the owner's turns.jsonl.
    from baxy_mind.__main__ import trace_dir
    assert trace_dir({"LOCALAPPDATA": str(tmp_path)}) == tmp_path / "BAXY" / "renew"
    run = tmp_path / "runs" / "x-e2e" / "mente"
    assert trace_dir({"LOCALAPPDATA": str(tmp_path), "BAXY_RENEW_TRACE_DIR": str(run)}) == run
    assert trace_dir({"LOCALAPPDATA": str(tmp_path), "BAXY_RENEW_TRACE_DIR": "  "}) == tmp_path / "BAXY" / "renew"


def test_the_products_trace_keeps_no_words_and_a_benchs_run_or_an_owner_who_asks_keeps_them(tmp_path: Path) -> None:
    # PRV1 (PRIV-02): the product's trace is for times and names; what was said is kept only where someone set it so.
    from baxy_mind.__main__ import trace_words
    assert trace_words({"LOCALAPPDATA": str(tmp_path)}) is False
    assert trace_words({"LOCALAPPDATA": str(tmp_path), "BAXY_TRACE_WORDS": "0"}) is False
    assert trace_words({"LOCALAPPDATA": str(tmp_path), "BAXY_TRACE_WORDS": "1"}) is True
    assert trace_words({"LOCALAPPDATA": str(tmp_path), "BAXY_RENEW_TRACE_DIR": str(tmp_path / "run")}) is True
    assert trace_words({"LOCALAPPDATA": str(tmp_path), "BAXY_RENEW_TRACE_DIR": "  "}) is False


def test_a_trace_without_words_keeps_times_and_names_and_nothing_of_what_was_said(tmp_path: Path) -> None:
    # PRV1 (PRIV-02): every row held the person's words, the call's arguments and BAXY's answer in clear text.
    import json

    from test_mind_final import _call, _mind, _say
    mind, _ = _mind(tmp_path, [_call("web_fetch", {"url": "https://tulipan.example/rojo"}),
                               _say("La clave tulipán quedó anotada.")])
    mind.trace_words = False
    mind.wire_to_op = {"web_fetch": "web_fetch"}  # a tool of the catalog, by the name the model sees
    assert mind.decide(1, "mi clave es tulipán, mira esa página")["kind"] == "action"
    result = mind.continue_turn(2, json.dumps({"status": "completed", "text": "página de tulipanes"}))
    assert result["reply"] == "La clave tulipán quedó anotada."

    written = mind.trace.read_text(encoding="utf-8")
    assert "tulip" not in written and "clave" not in written and "anotada" not in written
    rows = [json.loads(line) for line in written.splitlines()]
    decided = next(row for row in rows if row["stage"] == "turn.decide")
    assert decided["operation"] == "web_fetch" and decided["kind"] == "action" and isinstance(decided["ms"], int)
    assert all(set(row) <= mind.TRACE_FACTS for row in rows)
    assert not any(key in row for row in rows for key in ("text", "content", "arguments", "written"))


def test_a_tool_name_the_model_made_up_is_not_written_in_a_trace_without_words(tmp_path: Path) -> None:
    # Revisión a ciegas de PRV1: «operation» is the name the model wrote for its call, and one that is no tool of BAXY's
    # (a call written as text, another model through the translator) went into the row as written, with whatever words
    # it was made of. The App still gets the name, and refuses it; the row says only that the tool is not listed.
    import json

    from baxy_mind.mind import Mind
    from test_mind_final import _call, _mind, _say
    mind, _ = _mind(tmp_path, [_call("anotar_clave_tulipan", {}), _call("web_fetch", {"url": "https://example.org/"}),
                               _say("Listo.")])
    mind.trace_words = False
    mind.wire_to_op = {"web_fetch": "web.fetch"}
    assert mind.decide(1, "mi clave es tulipán")["operation"] == "anotar_clave_tulipan"
    assert mind.continue_turn(2, json.dumps({"status": "failed", "code": "unknown_operation"}))["operation"] == "web.fetch"
    mind.continue_turn(3, json.dumps({"status": "completed", "text": "una página"}))

    written = mind.trace.read_text(encoding="utf-8")
    assert "tulip" not in written and "anotar" not in written
    named = [row["operation"] for row in map(json.loads, written.splitlines()) if row.get("kind") == "action"]
    assert named == [Mind.UNLISTED, "web.fetch"]
    assert Mind._without_words({"operation": "x", "operations": ["web.fetch", "x"], "doubt_of": "x"}, {"web.fetch"}) == {
        "operation": Mind.UNLISTED, "operations": ["web.fetch", Mind.UNLISTED], "doubt_of": Mind.UNLISTED}


def test_a_trace_with_words_is_the_whole_row_as_before(tmp_path: Path) -> None:
    import json

    from test_mind_final import _mind, _say
    mind, _ = _mind(tmp_path, [_say("Hola.")])
    mind.decide(1, "mi clave es tulipán")
    row = json.loads(mind.trace.read_text(encoding="utf-8").splitlines()[-1])
    assert row["text"] == "mi clave es tulipán" and row["content"] == "Hola."


def test_a_row_without_words_names_its_aids_and_its_rules_only() -> None:
    from baxy_mind.mind import Mind
    row = Mind._without_words({
        "stage": "turn.check", "ms": 3, "aids": {"said_query": "busca «tulipán»"}, "own": "háblame de tú",
        "findings": [{"rule": "unsourced_number", "said": "tulipán 7", "fact": "«tulipán» es un nombre"}],
        "nuevo_campo": "tulipán"})
    assert row == {"stage": "turn.check", "ms": 3, "aids": ["said_query"], "findings": [{"rule": "unsourced_number"}]}
    # Whatever shape a row brings, a row without words is written: the trace never fails a turn.
    assert Mind._without_words({"stage": "turn.aid", "aids": None, "findings": "tulipán"}) == {"stage": "turn.aid"}


def test_forgetting_removes_the_trace_and_its_archive_file_by_file(tmp_path: Path) -> None:
    # PRV1 (PRIV-02): «Olvidar todo» and deleting every conversation ask the mind for this (trace.forget); with the
    # App's own files (tests/Baxy.App.Tests/LeftInClearTests.cs) nothing of what was said stays in clear text.
    from test_mind_final import _mind, _say
    mind, _ = _mind(tmp_path, [_say("Hola.")])
    mind.decide(1, "mi clave es tulipán")
    archive = mind.trace.with_name("turns.jsonl.1")
    archive.write_text('{"text": "vivo en Viña del Mar"}\n', encoding="utf-8")
    assert mind.trace.name == "turns.jsonl" and mind.trace.is_file() and archive.is_file()

    assert mind.forget_trace() is True

    assert not mind.trace.exists(), "turns.jsonl stayed"
    assert not archive.exists(), "turns.jsonl.1 stayed"
