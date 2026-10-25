"""scripts/voice/hablar.py, the spoken driver of live A/Bs, without the product: a set is the call, a pause and each
order at 16 kHz in the feed's list; an arm is read back from the feed's log and the mind's trace rows (the early
decision's fields, the first sound after the person's voice ended, the notice apart)."""
import json
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "voice"))

import hablar  # noqa: E402
from baxy_mind.voice_feed import listed  # noqa: E402


def _wav(path: Path, seconds: float, rate: int) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.full(int(seconds * rate), 0.2, np.float32) * 32767).astype("<i2").tobytes())
    return path


def test_a_set_is_the_call_a_pause_and_the_order_at_16_khz(tmp_path: Path) -> None:
    call = _wav(tmp_path / "baxy.wav", 0.5, 22050)
    order = _wav(tmp_path / "orden.wav", 1.0, 16000)
    hablar.preparar(tmp_path / "set", [str(order)], None, {}, call, 0.3, 2.5)
    assert listed(str(tmp_path / "set" / "feed.txt")) == [(tmp_path / "set" / "feed" / "0001_orden.wav", 2.5)]
    with wave.open(str(tmp_path / "set" / "feed" / "0001_orden.wav"), "rb") as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
        assert abs(w.getnframes() / 16000 - 1.8) < 0.01


def test_an_arm_is_read_from_the_feed_log_and_the_trace(tmp_path: Path) -> None:
    run = tmp_path / "default1"
    run.mkdir()
    feed = [{"event": "said", "index": 0, "wav": "feed/0001_g001.wav", "started_at": "2026-10-23T18:00:00.000",
             "voice_end_at": "2026-10-23T18:00:02.000", "ended_at": "2026-10-23T18:00:02.300"},
            {"event": "said", "index": 1, "wav": "feed/0002_g002.wav", "started_at": "2026-10-23T18:00:10.000",
             "voice_end_at": "2026-10-23T18:00:12.000", "ended_at": "2026-10-23T18:00:12.300"},
            {"event": "done", "at": "2026-10-23T18:00:20.000"}]
    trace = [
        {"t": "2026-10-23T18:00:03.100", "stage": "turn.decide", "ms": 900, "prompt_ms": 120.0,
         "early": {"hit": True, "ahead_ms": 950, "saved_ms": 700, "waited_ms": 0}},
        {"t": "2026-10-23T18:00:03.200", "stage": "voice.speak", "sound_at": "2026-10-23T18:00:03.500", "notice": False},
        {"t": "2026-10-23T18:00:14.000", "stage": "voice.speak", "sound_at": "2026-10-23T18:00:14.000", "notice": True},
        {"t": "2026-10-23T18:00:15.000", "stage": "turn.decide", "ms": 2500, "prompt_ms": 300.0,
         "early": {"hit": False, "reason": "text", "discarded": 1}},
        {"t": "2026-10-23T18:00:15.100", "stage": "voice.speak", "sound_at": "2026-10-23T18:00:15.400", "notice": False},
    ]
    (run / "feed.jsonl").write_text("".join(json.dumps(r) + "\n" for r in feed), encoding="utf-8")
    (run / "turns.jsonl").write_text("".join(json.dumps(r) + "\n" for r in trace) + "{cut", encoding="utf-8")
    (run / "arm.json").write_text(json.dumps({"early": "default", "wake_warm": "default"}), encoding="utf-8")
    summary = hablar.resumir(run)
    assert summary["said"] == 2 and summary["done"] and summary["decided"] == 2
    assert summary["early_hit"] == 1 and summary["early_miss"] == {"text": 1} and summary["saved_ms_p50"] == 700
    turns = json.loads((run / "summary.json").read_text(encoding="utf-8"))["turns"]
    # From the end of the person's voice: the first sound (the notice counts) and the first answer.
    assert [(t["first_sound_ms"], t["first_answer_ms"]) for t in turns] == [(1500, 1500), (2000, 3400)]


def test_an_arm_runs_on_its_own_profile_never_the_owners(tmp_path: Path, monkeypatch) -> None:
    # Calidad PC 2026-10-25: the arm set BAXY_DATA_DIR, which run_baxy.ps1 always replaces (by dev-mente-v2 or the
    # profile it is given; the core takes only a child of %LOCALAPPDATA%/BAXY): every arm ran on the owner's profile.
    started: list = []

    class Launcher:
        pid = 2 ** 31 - 2  # no such process: the arm has no family to close

        def __init__(self, command, env, **_kw) -> None:
            started.append(command)
            Path(env["BAXY_RENEW_VOICE_FEED_LOG"]).write_text(
                json.dumps({"event": "done", "at": "2026-10-25T20:00:00"}) + "\n", encoding="utf-8")

        def poll(self) -> int:
            return 0

    for var in ("BAXY_RENEW_WAKE_DIR", "BAXY_RENEW_STT_DIR"):
        (tmp_path / var).mkdir()
        monkeypatch.setenv(var, str(tmp_path / var))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(hablar.subprocess, "Popen", Launcher)
    _wav(tmp_path / "uno.wav", 1.0, 16000)
    (tmp_path / "feed.txt").write_text("uno.wav\t3\n", encoding="utf-8")
    hablar.correr(tmp_path, "default1", "default", "default", 60)
    assert started[0][-2:] == ["--profile", "hablar-default1"]
