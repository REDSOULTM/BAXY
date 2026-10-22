"""The measuring scripts of «BAXY Renew al máximo» (R12.5-R12.7), with saved data and doubles: no product or GPU."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew"))

import bench_e2e  # noqa: E402
import rescore_e2e  # noqa: E402

# R12.5: two cases that share the person's «sí»: E001 answers a confirmation with it, E002 says it with nothing pending.
QUESTION = "¿Cierro la Calculadora?"
CLOSED = "Cerré la Calculadora."
WHAT = "¿Sí a qué? No tengo nada pendiente."
EVENTS = [
    {"type": "meta", "t_ms": 1},
    {"type": "runtime", "ready": True, "mindReady": True, "t_ms": 500},
    {"type": "command.done", "session": "new", "ok": True, "t_ms": 900},
    {"type": "turn.start", "index": 0, "input": {"text": "cierra la calculadora"}, "t_ms": 1000},
    {"type": "message", "speaker": "person", "body": "cierra la calculadora", "t_ms": 1000},
    {"type": "speech.start", "text": QUESTION, "notice": False, "t_ms": 2000},
    {"type": "turn.end", "index": 0, "pendingConfirmation": True, "t_ms": 2010},
    {"type": "command.done", "index": 0, "t_ms": 2010},
    {"type": "turn.start", "index": 1, "input": {"text": "sí"}, "t_ms": 3000},
    {"type": "message", "speaker": "person", "body": "sí", "t_ms": 3000},
    {"type": "speech.end", "text": QUESTION, "notice": False, "t_ms": 3100},
    {"type": "speech.start", "text": CLOSED, "notice": False, "t_ms": 4000},
    {"type": "turn.end", "index": 1, "pendingConfirmation": False, "t_ms": 4010},
    {"type": "command.done", "index": 1, "t_ms": 4010},
    {"type": "speech.end", "text": CLOSED, "notice": False, "t_ms": 5000},
    {"type": "command.done", "session": "new", "ok": True, "t_ms": 9000},
    {"type": "turn.start", "index": 2, "input": {"text": "sí"}, "t_ms": 10000},
    {"type": "message", "speaker": "person", "body": "sí", "t_ms": 10000},
    {"type": "speech.start", "text": WHAT, "notice": False, "t_ms": 11000},
    {"type": "turn.end", "index": 2, "pendingConfirmation": False, "t_ms": 11010},
    {"type": "command.done", "index": 2, "t_ms": 11010},
    {"type": "speech.end", "text": WHAT, "notice": False, "t_ms": 12000},
]
CASES = {
    "E001": {"id": "E001", "turns": [{"text": "cierra la calculadora", "reply_if_confirmation": "sí"}],
             "oracle": [{"ps": "Test-Spoken -Turn 1", "expect_regex": "^True$"}]},
    "E002": {"id": "E002", "turns": [{"text": "sí"}],
             "oracle": [{"ps": "Test-Spoken -Turn 1", "expect_regex": "^True$"}]},
}
REPLIES = {
    "E001": [{"turn": 1, "text": CLOSED, "asked_confirmation": True, "confirmation_text": QUESTION, "answered": "sí"}],
    "E002": [{"turn": 1, "text": WHAT, "asked_confirmation": False, "confirmation_text": "", "answered": None}],
}


def saved_run(folder: Path, events: list) -> Path:
    folder.mkdir()
    (folder / "events.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events),
                                         encoding="utf-8")
    rows = [{"summary": {"n": 2}}] + [{"id": cid, "status": "ok", "oracles": [{"ok": True, "out": "True"}]}
                                      for cid in CASES]
    (folder / "results.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                          encoding="utf-8")
    for cid, replies in REPLIES.items():
        (folder / cid).mkdir()
        (folder / cid / "replies.json").write_text(json.dumps(replies, ensure_ascii=False), encoding="utf-8")
    return folder


def rescored_speech(monkeypatch, run_dir: Path, case: dict) -> list:
    """The speech record the speech oracle would read (run_ps is a double that keeps it)."""
    seen = []

    def run_ps(path, env, timeout):
        seen.append(json.loads(Path(env["BAXY_E2E_SPEECH"]).read_text(encoding="utf-8")))
        return 0, "True"

    monkeypatch.setattr(bench_e2e, "ps_file", lambda path, lines: None)
    monkeypatch.setattr(bench_e2e, "run_ps", run_ps)
    rescore_e2e.rescore(run_dir, case, False)
    return seen[0]


def test_rescore_reads_each_case_in_its_own_part_of_the_run(tmp_path, monkeypatch):
    run_dir = saved_run(tmp_path / "run", EVENTS)
    first = rescored_speech(monkeypatch, run_dir, CASES["E001"])
    second = rescored_speech(monkeypatch, run_dir, CASES["E002"])
    assert [s["spoken_text"] for s in first] == [QUESTION, CLOSED]
    assert [s["spoken_text"] for s in second] == [WHAT]
    assert second[0]["first_audio_ms"] == 11000 - 10000


def test_rescore_says_clearly_when_a_turn_is_not_in_its_case(tmp_path, monkeypatch):
    # E002's turn never started (the run was cut after its new session).
    run_dir = saved_run(tmp_path / "run", EVENTS[:16])
    with pytest.raises(rescore_e2e.RunMismatch, match="E002"):
        rescored_speech(monkeypatch, run_dir, CASES["E002"])


# R12.6: a case whose setup failed still runs its cleanup (bench_e2e does), so the next case starts on a clean desktop.
class FakeConductor:
    def __init__(self, run_dir, profile):
        self.events = self

    def wait(self, predicate, timeout):
        return {"type": "runtime", "mindReady": True}

    def close(self):
        pass


def test_falsedades_cleans_up_after_a_failed_setup(tmp_path, monkeypatch):
    import bench_falsedades
    ran = []

    def run_ps(path, env, timeout):
        ran.append(Path(path).name)
        return (1, "setup roto") if Path(path).name == "setup.ps1" else (0, "")

    monkeypatch.setattr(bench_falsedades, "Conductor", FakeConductor)
    monkeypatch.setattr(bench_falsedades, "ps_file", lambda path, lines: None)
    monkeypatch.setattr(bench_falsedades, "run_ps", run_ps)
    monkeypatch.setattr(bench_falsedades, "session_locked", lambda: False)
    monkeypatch.setattr(bench_falsedades, "run_turn", lambda *a: pytest.fail("a case whose setup failed has no turns"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    case = {"id": "F001", "setup": ["exit 1"], "cleanup": ["Remove-Item x"], "turns": [{"text": "abre el bloc"}]}
    transcripts = bench_falsedades.run_conversations([case], tmp_path)
    assert ran == ["setup.ps1", "cleanup.ps1"]
    assert transcripts[0]["status"] == "setup_fallido"
