"""When a spoken request closes and how often the early transcript (palanca 2, src/baxy_mind/early.py) is the request's
own, in a quiet room and under steady noise: the early decision is used only when the two are the same text, so this
share bounds what it can save.

    <mind-runtime python> -X utf8 scripts/voice/medir_anticipada.py MANIFEST CATALOG OUT [--waits 0.2,0.3,0.5]
        [--conds limpio,20,10,5] [--only N] [--every K]

MANIFEST: the synthetic set of sintetizar_frases.py; its clean utterances are used. CATALOG: a catalog.configure
message; its names are the recognizer's hotwords, as mind.configure gives them to the voice (BAXY_RENEW_STT_HOTWORDS,
1.5 by default). BAXY_RENEW_STT_DIR: Parakeet Ultra. CPU only, one recognizer (~1 GB of RAM). --only N: the first N
utterances; --every K: one of every K (a slow arm on a sample).

Each utterance is heard in every condition of --conds: «limpio» as it is, and each number the same utterance with pink
noise at that SNR (sintetizar_frases.py's: against the RMS of its voiced samples), all along what the voice hears: the
file and then until MAX_S + 1 s, zeros in the clean case and the same noise in the others, so a request that never
hears the silence ends at MAX_S. It goes through voice.py's own path: a Voice per wait (early_s), in direct mode (no
«Baxy» in the set: the call is cut at the start, the end of the request is the same), its blocks of 100 ms, its end of
voice (loud and heard as speech), its live captions, early transcripts (taken back when the voice goes on after a
pause) and the request's transcript after END_SILENCE_S.

Per wait and condition: the requests that closed before MAX_S; how long after the end of the voice they closed (p50,
p90; the end of the voice is the clean twin's last block above VOICE_RMS); closed early, before that end (cut in a pause
or under the last words); the final transcript's WER against the sentence, the same as the clean one and empty; the
early hits: the early transcript standing when the request ends is the request's transcript, character for character
(early.py compares them so), and the same words.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import unicodedata
import wave
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from baxy_mind import voice  # noqa: E402
from baxy_mind.voice import BLOCK, END_SILENCE_S, MAX_S, RATE, VOICE_RMS, Voice  # noqa: E402
from medir_hotwords import catalog_names  # noqa: E402


class _Speech:
    """No voice output: nothing is spoken, so nothing mutes the ear."""
    speaking = False
    ready = False

    def __init__(self, *_args: Any) -> None:
        pass


class Heard:
    """What one Voice told for one utterance."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.done = threading.Event()
        self.transcribing = False
        self.final: str | None = None
        self.final_len = 0
        self.early: dict[int, tuple[str, int]] = {}   # standing early transcripts: seq → (text, samples decoded)
        self.told = 0
        self.taken_back = 0
        self.last_len = 0

    def write(self, message: dict[str, Any]) -> None:
        if message.get("type") == "voice.transcript":
            self.final, self.final_len = message["text"], self.last_len
        elif message.get("event") == "transcribing":
            self.transcribing = True
        elif message.get("event") == "state" and self.transcribing:
            if self.final is None:
                self.final, self.final_len = "", self.last_len
            self.done.set()

    def on_early(self, seq: int, text: str | None) -> None:
        if text is None:
            self.taken_back += self.early.pop(seq, None) is not None
        else:
            self.told += 1
            self.early[seq] = (text, self.last_len)

    def standing(self) -> tuple[str, int] | None:
        return self.early[max(self.early)] if self.early else None


def read(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768


def pink(n: int, rng: np.random.Generator) -> np.ndarray:
    spectrum = np.fft.rfft(rng.standard_normal(n))
    f = np.arange(len(spectrum))
    f[0] = 1
    y = np.fft.irfft(spectrum / np.sqrt(f), n)
    return (y / np.std(y)).astype(np.float32)


def heard_as(x: np.ndarray, cond: str, seed: int) -> np.ndarray:
    """What the voice hears of the clean utterance ``x`` in ``cond`` (see the docstring)."""
    audio = np.concatenate([x, np.zeros(max(0, int((MAX_S + 1.0) * RATE) - len(x)), np.float32)])
    if cond == "limpio":
        return audio
    speech_rms = float(np.sqrt(np.mean(x[np.abs(x) > 0.01] ** 2)))
    return audio + pink(len(audio), np.random.default_rng(seed)) * speech_rms / (10 ** (float(cond) / 20))


def voice_end_s(x: np.ndarray) -> float:
    """The end of the clean utterance's last block above VOICE_RMS (where voice.py closed it before Silero)."""
    frames = x[: len(x) // BLOCK * BLOCK].reshape(-1, BLOCK)
    loud = np.flatnonzero(np.sqrt((frames ** 2).mean(axis=1)) >= VOICE_RMS)
    return (int(loud[-1]) + 1) * BLOCK / RATE


def blocks(audio: np.ndarray) -> list[np.ndarray]:
    audio = np.concatenate([audio, np.zeros(-len(audio) % BLOCK, np.float32)])
    return [audio[i:i + BLOCK].copy() for i in range(0, len(audio), BLOCK)]


def make_voices(waits: list[float], names: list[str]) -> tuple[list[Voice], list[Heard]]:
    voice.Speech = _Speech  # type: ignore[misc]
    shared: dict[str, Any] = {}

    def load(self: Voice) -> None:
        import sherpa_onnx
        self._input = True
        self._vad = voice.Vad(sherpa_onnx)  # each Voice hears on its own
        if shared:
            self._recognizer, self._hotwords = shared["recognizer"], shared["hotwords"]
        else:
            self.hear_names(names)
            self._recognize(sherpa_onnx, Path(os.environ["BAXY_RENEW_STT_DIR"]))
            shared.update(recognizer=self._recognizer, hotwords=self._hotwords)
        self._loaded.set()

    Voice._load = load  # type: ignore[method-assign]
    Voice._open = lambda self: None  # type: ignore[method-assign]  # the blocks are put in its queue here
    transcribe = Voice._transcribe

    def measured(self: Voice, audio: np.ndarray, wake_at: float | None) -> str:
        self._heard_by.last_len = len(audio)  # type: ignore[attr-defined]
        return transcribe(self, audio, wake_at)

    Voice._transcribe = measured  # type: ignore[method-assign]
    voices, heard = [], []
    for wait in waits:
        h = Heard()
        v = Voice(h.write, on_early=h.on_early, early_s=wait)
        v._heard_by = h  # type: ignore[attr-defined]
        v._loaded.wait(600)
        assert v._recognizer is not None, v.failure
        voices.append(v)
        heard.append(h)
    return voices, heard


def hear(v: Voice, h: Heard, audio: np.ndarray, timeout: float = 120.0) -> None:
    h.reset()
    assert v.start("direct")
    with v._lock:  # the listening thread waits: every block is queued before it hears the first
        while not v._blocks.empty():
            v._blocks.get_nowait()
        for block in blocks(audio):
            v._blocks.put(block)
    if not h.done.wait(timeout):
        raise TimeoutError("the request did not end")


def bare(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return " ".join("".join(c for c in text if c.isalnum() or c.isspace()).split())


def edits(said: list[str], heard: list[str]) -> int:
    row = list(range(len(heard) + 1))
    for i, word in enumerate(said, 1):
        prev, row[0] = row[0], i
        for j, other in enumerate(heard, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (word != other))
    return row[-1]


def main() -> None:
    manifest, catalog, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    option = lambda name, default: sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default  # noqa: E731
    waits = [float(w) for w in option("--waits", "0.2,0.3,0.5").split(",")]
    conds = option("--conds", "limpio,20,10,5").split(",")
    clean = [r for r in json.loads(manifest.read_text(encoding="utf-8")) if r["cond"] == "limpio"]
    clean = clean[::int(option("--every", "1"))][:int(option("--only", str(len(clean))))]
    voices, heard = make_voices(waits, catalog_names(catalog))
    print(f"{len(clean)} utterances, conditions {conds}, waits {waits}, hotwords {len(voices[0]._hotwords)} chars",
          flush=True)
    results: list[dict[str, Any]] = []
    started = time.perf_counter()
    for n, r in enumerate(clean, 1):
        x = read(r["wav"])
        row: dict[str, Any] = {"id": r["id"], "voz": r["voz"], "clase": r["clase"], "texto": r["texto"],
                               "voice_end_s": voice_end_s(x), "conds": {}}
        for k, cond in enumerate(conds):
            audio = heard_as(x, cond, 1000 * n + k)
            cells: dict[str, Any] = {}
            for wait, v, h in zip(waits, voices, heard):
                hear(v, h, audio)
                standing = h.standing()
                cells[f"{wait:g}"] = {"final": h.final, "final_s": round(h.final_len / RATE, 2),
                                      "early": standing[0] if standing else None,
                                      "early_s": round(standing[1] / RATE, 2) if standing else None,
                                      "told": h.told, "taken_back": h.taken_back}
            row["conds"][cond] = cells
        results.append(row)
        if n % 25 == 0:
            print(f"{n}/{len(clean)} {time.perf_counter() - started:.0f} s", flush=True)
    summary = summarize(results, waits, conds)
    out.write_text(json.dumps({"summary": summary, "rows": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


def summarize(results: list[dict[str, Any]], waits: list[float], conds: list[str]) -> dict[str, Any]:
    summary: dict[str, Any] = {"utterances": len(results), "end_silence_s": END_SILENCE_S, "max_s": MAX_S,
                               "waits": {}}
    for wait in waits:
        key = f"{wait:g}"
        entry: dict[str, Any] = {}
        for cond in conds:
            rows = [(r, r["conds"][cond][key]) for r in results]
            after = np.array([c["final_s"] - r["voice_end_s"] for r, c in rows])
            early = [c for _, c in rows if c["early"] is not None]
            said = [bare(r["texto"]).split() for r, _ in rows]
            n = max(1, len(rows))
            entry[cond] = {
                "closed_pct": round(100 * sum(c["final_s"] < MAX_S - 0.05 for _, c in rows) / n, 1),
                "after_voice_p50_s": round(float(np.percentile(after, 50)), 2) if len(after) else None,
                "after_voice_p90_s": round(float(np.percentile(after, 90)), 2) if len(after) else None,
                "closed_early": int((after < -1e-6).sum()),
                "wer_pct": round(100 * sum(edits(s, bare(c["final"]).split()) for s, (_, c) in zip(said, rows))
                                 / max(1, sum(len(s) for s in said)), 2),
                "final_as_clean_pct": round(100 * sum(c["final"] == r["conds"][conds[0]][key]["final"]
                                                      for r, c in rows) / n, 1),
                "empty": sum(not c["final"] for _, c in rows),
                "early_hit_pct": round(100 * sum(c["early"] == c["final"] for c in early) / n, 1),
                "early_same_words_pct": round(100 * sum(bare(c["early"]) == bare(c["final"]) for c in early) / n, 1),
                "taken_back": sum(c["taken_back"] for _, c in rows)}
        summary["waits"][key] = entry
    return summary


if __name__ == "__main__":
    main()
