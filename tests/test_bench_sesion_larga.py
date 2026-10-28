"""The long-session bench (scripts/renew/bench_sesion_larga.py, noche P0.1) without a GPU: the session it builds from the
banks, the turns it runs through Renew's own Mind on a fake llama-server, the tandas that go on from the session the one
before left, and the stretches it reports."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew"))

import bench_sesion_larga as bench  # noqa: E402
from baxy_mind.mind import Mind  # noqa: E402

CATALOG = {"capabilities": [
    {"name": "web.search", "risk": "read_only", "argumentsSchema": {"type": "object", "properties": {
        "query": {"type": "string"}}}},
    {"name": "file.read", "risk": "read_only", "argumentsSchema": {"type": "object", "properties": {
        "path": {"type": "string"}}}},
    {"name": "audio.volume", "risk": "low_reversible", "argumentsSchema": {"type": "object", "properties": {
        "level": {"type": "integer"}}}}]}
RISK = {c["name"]: c["risk"] for c in CATALOG["capabilities"]}
LECTURAS = [f"Párrafo {i} de un texto largo de prueba. " * 40 for i in range(6)]


def _call(name: str, arguments: dict) -> dict:
    return {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": "c1", "function": {"name": name, "arguments": json.dumps(arguments)}}]}}]}


def _say(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


class FakeServer:
    """Answers by the person's last words (a call or words, as `script` says) and in words after a result; counts the
    prompt's tokens as a quarter of its characters."""
    context = 53248

    def __init__(self, script: dict[str, dict]) -> None:
        self.script = script
        self.bodies: list[dict] = []

    def chat(self, body: dict, timeout: float = 120.0) -> dict:
        self.bodies.append(json.loads(json.dumps(body)))
        last = body["messages"][-1]
        reply = (self.script.get(str(last.get("content"))) if last["role"] == "user" else None) or _say("Hecho.")
        size = len(json.dumps(body["messages"], ensure_ascii=False)) // 4
        return {**reply, "usage": {"prompt_tokens": size + 1000}}

    def tokenize(self, text: str) -> list[int]:
        return [0] * (len(text) // 4)


def _mind(tmp_path: Path, script: dict[str, dict]) -> tuple[Mind, bench.RecordingServer]:
    server = bench.RecordingServer(FakeServer(script))
    mind = Mind(server, tmp_path / "turns.jsonl")  # type: ignore[arg-type]
    mind.configure(CATALOG)
    mind.call_tokens = [248058]
    mind.prefix_tokens = 1000
    mind.new_session([])
    return mind, server


def _turn(n: int, text: str, expect: dict, category: str = "accion") -> dict:
    return {"n": n, "id": f"L{n:02d}-b-c{n}", "case": f"c{n}", "bank": "b", "category": category, "family": "f",
            "text": text, "expect": expect}


def _case(case_id: str, text: str, expect: dict, **more) -> dict:
    return {"id": case_id, "text": text, "expect": expect, "family": "f", **more}


def test_the_session_takes_cases_without_their_own_history_mixed_by_category_and_bank() -> None:
    banks = {
        "a": [_case("a1", "sube el volumen", {"kind": "call", "op": "audio.volume"}),
              _case("a2", "busca noticias", {"kind": "call", "op": "web.search"}),
              _case("a3", "hola", {"kind": "text"}),
              _case("a4", "con historia", {"kind": "text"}, history=[{"role": "user", "content": "antes"}]),
              _case("a5", "sí", {"kind": "call", "op": "audio.volume"}, pending={"operation": "audio.volume"})],
        "b": [_case("b1", "lee el fichero", {"kind": "call", "op": "file.read"}),
              _case("b2", "pon el volumen al 3", {"kind": "call", "op": "audio.volume"}),
              _case("b3", "¿qué tal?", {"kind": "any", "options": [{"kind": "text"}]})]}
    session = bench.armar(banks, 50, 0, RISK, LECTURAS)
    cases = [t["case"] for t in session["turnos"]]
    assert sorted(cases) == ["a1", "a2", "a3", "b1", "b2", "b3"]  # no own history, no confirmation waiting
    assert [t["n"] for t in session["turnos"]] == list(range(1, 7))
    assert len({t["id"] for t in session["turnos"]}) == 6
    first = session["turnos"][:3]
    assert [t["category"] for t in first] == ["accion", "charla", "busqueda"]  # PATTERN's order
    assert {t["bank"] for t in session["turnos"] if t["category"] == "accion"} == {"a", "b"}
    assert bench.armar(banks, 50, 0, RISK, LECTURAS) == session  # the same seed, the same session
    assert session["lecturas"] == LECTURAS


def test_a_read_gets_a_long_body_and_an_effect_a_verified_result() -> None:
    read = json.loads(bench.observation("file.read", {"path": "x"}, "read_only", LECTURAS, 0))
    assert read["status"] == "completed" and len(read["observed"]["text"]) == bench.LONG_READ[0]
    found = json.loads(bench.observation("web.search", {"query": "lluvia"}, "read_only", LECTURAS, 1))
    assert found["observed"]["query"] == "lluvia" and len(found["observed"]["results"]) == 7
    done = json.loads(bench.observation("audio.volume", {"level": 3}, "low_reversible", LECTURAS, 2))
    assert done == {"status": "completed", "verification": "readback", "observed": {}}


def test_each_turn_is_judged_on_its_decision_closed_with_its_results_and_measured_by_part(tmp_path: Path) -> None:
    script = {"busca el tiempo": _call("web_search", {"query": "tiempo"}),
              "pon el volumen al 3": _call("audio_volume", {"level": 3}),
              "cuéntame algo": _say("Claro, algo.")}
    mind, server = _mind(tmp_path, script)
    turns = [_turn(1, "busca el tiempo", {"kind": "call", "op": "web.search"}, "busqueda"),
             _turn(2, "pon el volumen al 3", {"kind": "call", "op": "audio.volume", "args": {"level": 4}}),
             _turn(3, "cuéntame algo", {"kind": "text"}, "charla")]
    rows = bench.correr_turnos(mind, server, turns, LECTURAS, {}, tmp_path / "turns.jsonl")
    assert [r["ok"] for r in rows] == [True, False, True]  # turn 2 called with level 3, not the expected 4
    assert [r["calls"] for r in rows] == [["web.search"], ["audio.volume"], []]
    assert [r["final_kind"] for r in rows] == ["conversation"] * 3
    first, third = rows[0]["context"], rows[2]["context"]
    assert first["tool_results"] == 0 and third["tool_results"] > 800  # turn 1's search is in turn 3's history
    assert third["history"] > first["history"]
    assert third["system"] == len(mind._system()) // 4 and third["catalog"] == 1000 - third["system"]
    assert third["total"] == third["system"] + third["catalog"] + third["history"] + third["tool_results"] + third["otros"]
    assert rows[2]["context_max"] >= third["total"] and rows[2]["n_ctx"] == 53248
    assert all(r["error"] is None and not r["open_ask_before"] for r in rows)


def test_a_failed_decision_is_a_failed_turn_and_the_session_goes_on(tmp_path: Path) -> None:
    class Down(FakeServer):
        def chat(self, body: dict, timeout: float = 120.0) -> dict:
            if body["messages"][-1].get("content") == "falla":
                raise TimeoutError("server")
            return super().chat(body, timeout)

    server = bench.RecordingServer(Down({"hola": _say("Hola.")}))
    mind = Mind(server, tmp_path / "turns.jsonl")  # type: ignore[arg-type]
    mind.configure(CATALOG)
    mind.call_tokens = [248058]
    mind.new_session([])
    rows = bench.correr_turnos(mind, server, [_turn(1, "falla", {"kind": "text"}), _turn(2, "hola", {"kind": "text"})],
                               LECTURAS, {}, tmp_path / "turns.jsonl")
    assert rows[0]["ok"] is False and "TimeoutError" in rows[0]["error"] and rows[0]["kind"] == "error"
    assert rows[1]["ok"] is True and rows[1]["error"] is None


def test_a_tanda_goes_on_from_the_session_the_one_before_left(tmp_path: Path) -> None:
    script = {"lee notas.txt": _call("file_read", {"path": "notas.txt"}), "y ahora qué": _say("Nada más.")}
    mind, server = _mind(tmp_path, script)
    bench.correr_turnos(mind, server, [_turn(1, "lee notas.txt", {"kind": "call", "op": "file.read"}, "lectura")],
                        LECTURAS, {}, tmp_path / "turns.jsonl")
    kept = json.loads(json.dumps(mind.export_session()))
    later, later_server = _mind(tmp_path, script)
    later.load_session(kept)
    rows = bench.correr_turnos(later, later_server, [_turn(2, "y ahora qué", {"kind": "text"}, "charla")],
                               LECTURAS, {}, tmp_path / "turns.jsonl")
    sent = json.dumps(later_server.inner.bodies[0]["messages"], ensure_ascii=False)
    assert "lee notas.txt" in sent and "Párrafo" in sent  # the earlier turn and its read reach the next tanda
    assert rows[0]["ok"] and rows[0]["context"]["tool_results"] > 0


def _row(n: int, ok: bool, total: int, case: str | None = None, **more) -> dict:
    return {"n": n, "case": case or f"c{n}", "category": "accion" if n % 2 else "charla", "ok": ok, "excluded": False,
            "latency_s": 1.0, "open_ask_before": False, "error": None, "context_max": total + 10, "n_ctx": 53248,
            "trimmed_turns": n // 9, "context_shrunk": 0,
            "context": {"total": total, "system": 100, "catalog": 900, "history": total - 1000, "tool_results": 0,
                        "otros": 0}, **more}


def test_the_report_aggregates_by_stretches_with_the_later_tanda_winning_and_the_cases_alone() -> None:
    rows = [_row(n, n != 3, 1000 + 100 * n) for n in range(1, 13)] + [_row(3, True, 1300)]  # turn 3 run again
    summary = bench.resumir(rows, 10, {(None, "c1"): True, (None, "c2"): False, (None, "c11"): True})
    first, second = summary["tramos"]
    assert first["turnos"] == [1, 10] and first["ok"] == 10 and first["n"] == 10
    assert first["aislado"] == {"ok": 1, "n": 2}
    assert first["context_mean"]["total"] == 1550 and first["context_max"] == 2010
    assert second["n"] == 2 and second["trimmed_turns_end"] == 1
    assert summary["missing"] == [] and summary["categories"] == {"accion": [6, 6], "charla": [6, 6]}
    text = bench.resumen_md("x", summary)
    assert "| 1-10 | 10/10 | 1/2 | 1550 |" in text and "| 11-20 | 2/2 |" in text
    assert bench.resumir([_row(1, True, 1000), _row(3, True, 1000)])["missing"] == [2]


class FakeLlmServer(FakeServer):
    """llama-server as correr starts it (LlmServer's constructor, start, warm-up and close), answering as FakeServer."""
    made: list = []

    def __init__(self, gguf, server, **options) -> None:
        import os
        import types
        super().__init__({"lee notas.txt": _call("file_read", {"path": "notas.txt"}), "hola": _say("Hola.")})
        self._process = types.SimpleNamespace(pid=os.getpid())
        self.closed = False
        FakeLlmServer.made.append(self)

    def start(self) -> None:
        pass

    def wait_ready(self, timeout) -> None:
        pass

    def tokenize(self, text: str) -> list[int]:
        return [248058] if text == "<tool_call>" else super().tokenize(text)

    def prefix_key(self, warm) -> str:
        return "k"

    def restore_prefix(self, key: str) -> None:
        return None

    def save_prefix(self, key: str, facts: dict) -> bool:
        return False

    def close(self) -> None:
        self.closed = True


def test_correr_runs_a_session_in_tandas_and_resumir_joins_them(tmp_path: Path, monkeypatch) -> None:
    import baxy_mind.llm_server
    import bench_decision

    FakeLlmServer.made.clear()
    monkeypatch.setattr(baxy_mind.llm_server, "LlmServer", FakeLlmServer)
    monkeypatch.setattr(bench_decision, "gpu_used_mib", lambda: None)
    monkeypatch.setattr(bench, "BANKS", tmp_path)
    monkeypatch.setenv("BAXY_RENEW_BANKS", str(tmp_path))
    monkeypatch.delenv("BAXY_S1_GGUF", raising=False)
    monkeypatch.setenv("BAXY_DATA_DIR", str(tmp_path / "datos"))
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps(CATALOG), encoding="utf-8")
    session = tmp_path / "sesion.json"
    session.write_text(json.dumps({"turnos": [
        _turn(1, "lee notas.txt", {"kind": "call", "op": "file.read"}, "lectura"),
        _turn(2, "hola", {"kind": "text"}, "charla"), _turn(3, "hola", {"kind": "text"}, "charla")],
        "lecturas": LECTURAS}), encoding="utf-8")

    def run(*argv: str) -> None:
        monkeypatch.setattr(sys, "argv", ["bench_sesion_larga.py", *argv])
        bench.main()

    common = ["--sesion", str(session), "--catalog", str(catalog), "--src", str(Path(bench.ROOT) / "src")]
    try:
        run("correr", "x", "--desde", "2", "--hasta", "3", *common)
    except SystemExit as stop:
        assert "sesion-01.json is missing" in str(stop)  # a later tanda needs the one before it
    else:
        raise AssertionError("a tanda ran without the session the one before left")
    run("correr", "x", "--desde", "1", "--hasta", "1", *common)
    run("correr", "x", "--desde", "2", "--hasta", "3", *common)
    runs = tmp_path / "runs"
    assert (runs / "x.sesion-01.json").is_file() and (runs / "x.sesion-03.json").is_file()
    later = runs / "x-t02-03.jsonl"
    summary = json.loads(later.read_text(encoding="utf-8").splitlines()[0])["summary"]
    assert summary["tanda"] == [2, 3] and summary["ok"] == 2 and summary["from_snapshot"].endswith("x.sesion-01.json")
    assert summary["run"]["judge_sha256"] and all(s.closed for s in FakeLlmServer.made)
    sent = json.dumps(FakeLlmServer.made[-1].bodies[1]["messages"], ensure_ascii=False)
    assert "lee notas.txt" in sent  # tanda 2 read tanda 1's turn
    run("resumir", "x")
    report = json.loads((runs / "x.resumen.json").read_text(encoding="utf-8"))
    assert report["turnos"] == 3 and report["ok"] == 3 and report["missing"] == []
    assert (runs / "x.resumen.md").read_text(encoding="utf-8").startswith("# Sesión larga x")
    assert json.loads(later.read_text(encoding="utf-8").splitlines()[0])["summary"]["open_ask_at_end"] is False
    (runs / "x-t04-04.jsonl").write_text(json.dumps({"summary": {"sesion": "otra.json"}}) + "\n", encoding="utf-8")
    try:
        run("resumir", "x")
    except SystemExit as stop:
        assert "different sessions" in str(stop)  # never a report that mixes two sessions' turns
    else:
        raise AssertionError("resumir joined tandas of two sessions")
