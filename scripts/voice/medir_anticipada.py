"""How often the early transcript (palanca 2, src/baxy_mind/early.py) is the request's own: the early decision is used
only when the two are the same text, so this share bounds what it can save.

    <mind-runtime python> -X utf8 scripts/voice/medir_anticipada.py MANIFEST CATALOG OUT [--waits 0.2,0.3,0.5]
        [--only N] [--noise-faithful N]

MANIFEST: the synthetic set of sintetizar_frases.py (clean and pink noise at 10 dB, the same utterance sample-aligned).
CATALOG: a catalog.configure message; its names are the recognizer's hotwords, as mind.configure gives them to the voice
(BAXY_RENEW_STT_HOTWORDS, 1.5 by default). BAXY_RENEW_STT_DIR: Parakeet Ultra. CPU only, one recognizer (~1 GB of RAM).

Each clean utterance goes through voice.py's own path: a Voice per wait (early_s), in direct mode (no «Baxy» in the set:
the call is cut at the start, the end of the request is the same), its blocks of 100 ms, its RMS end of voice, its live
captions, early transcripts (taken back when the voice goes on after a pause) and the request's transcript after
END_SILENCE_S. A hit: the early transcript standing when the request ends is the request's transcript, character for
character (early.py compares them so).

Noise. At 10 dB the noise floor is above VOICE_RMS in almost every file, so voice.py never hears the silence: the request
ends at MAX_S and no early transcript exists. --noise-faithful N checks that on N noisy files. The «ruido» rows instead
cut each noisy file where its clean twin was cut (its early and its final cuts, same samples) and decode both with
voice.py's _transcribe: whether more tail changes the words when there is noise, had the end of voice been found.
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
from baxy_mind.voice import BLOCK, END_SILENCE_S, MAX_S, RATE, Voice  # noqa: E402
from medir_hotwords import catalog_names  # noqa: E402

TAIL_S = 1.6  # silence after each file (its own 0.3 s pad comes first): past END_SILENCE_S with room


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


def blocks(audio: np.ndarray) -> list[np.ndarray]:
    audio = np.concatenate([audio, np.zeros(-len(audio) % BLOCK, np.float32)])
    return [audio[i:i + BLOCK].copy() for i in range(0, len(audio), BLOCK)]


def make_voices(waits: list[float], names: list[str]) -> tuple[list[Voice], list[Heard]]:
    voice.Speech = _Speech  # type: ignore[misc]
    shared: dict[str, Any] = {}

    def load(self: Voice) -> None:
        import sherpa_onnx
        self._input = True
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


def main() -> None:
    manifest, catalog, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    option = lambda name, default: sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default  # noqa: E731
    waits = [float(w) for w in option("--waits", "0.2,0.3,0.5").split(",")]
    rows = json.loads(manifest.read_text(encoding="utf-8"))
    clean = [r for r in rows if r["cond"] == "limpio"]
    noisy = {(r["id"], r["voz"]): r for r in rows if r["cond"] == "ruido"}
    if "--only" in sys.argv:
        clean = clean[:int(option("--only", "0"))]
    voices, heard = make_voices(waits, catalog_names(catalog))
    print(f"{len(clean)} clean utterances, waits {waits}, hotwords {len(voices[0]._hotwords)} chars", flush=True)
    results: list[dict[str, Any]] = []
    started = time.perf_counter()
    for n, r in enumerate(clean, 1):
        audio = np.concatenate([read(r["wav"]), np.zeros(int(TAIL_S * RATE), np.float32)])
        twin = noisy.get((r["id"], r["voz"]))
        noise_audio = None
        if twin is not None:
            x = read(twin["wav"])
            level = float(np.sqrt(np.mean(x[-int(0.25 * RATE):] ** 2)))  # its pad: noise alone
            noise_audio = np.concatenate([x, pink(int(TAIL_S * RATE), np.random.default_rng(n)) * level])
        row: dict[str, Any] = {"id": r["id"], "voz": r["voz"], "clase": r["clase"], "texto": r["texto"], "waits": {}}
        for wait, v, h in zip(waits, voices, heard):
            hear(v, h, audio)
            standing = h.standing()
            cell: dict[str, Any] = {"final": h.final, "final_s": round(h.final_len / RATE, 2),
                                    "early": standing[0] if standing else None,
                                    "early_s": round(standing[1] / RATE, 2) if standing else None,
                                    "told": h.told, "taken_back": h.taken_back}
            if noise_audio is not None and standing is not None:
                final_noisy = v._transcribe(noise_audio[:h.final_len], None)
                cell["ruido"] = {"final": final_noisy, "early": v._transcribe(noise_audio[:standing[1]], None)}
            row["waits"][f"{wait:g}"] = cell
        finals = {cell["final"] for cell in row["waits"].values()}
        row["same_final"] = len(finals) == 1
        results.append(row)
        if n % 25 == 0:
            print(f"{n}/{len(clean)} {time.perf_counter() - started:.0f} s", flush=True)
    faithful: list[dict[str, Any]] = []
    for r in list(noisy.values())[:int(option("--noise-faithful", "0"))]:
        x = read(r["wav"])
        level = float(np.sqrt(np.mean(x[-int(0.25 * RATE):] ** 2)))
        tail = int((MAX_S + 1.0) * RATE) - len(x)
        audio = np.concatenate([x, pink(max(0, tail), np.random.default_rng(7)) * level])
        v, h = voices[0], heard[0]
        hear(v, h, audio)
        faithful.append({"id": r["id"], "voz": r["voz"], "told": h.told, "final_s": round(h.final_len / RATE, 2),
                         "final": h.final, "texto": r["texto"]})
    summary = summarize(results, waits, faithful)
    out.write_text(json.dumps({"summary": summary, "rows": results, "noise_faithful": faithful}, ensure_ascii=False,
                              indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


def summarize(results: list[dict[str, Any]], waits: list[float], faithful: list[dict[str, Any]]) -> dict[str, Any]:
    def share(cells: list[dict[str, Any]], cond: str) -> dict[str, Any]:
        pairs = [(c.get("ruido") if cond == "ruido" else c) for c in cells]
        pairs = [p for p in pairs if p is not None]
        early = [p for p in pairs if p.get("early") is not None]
        hits = sum(p["early"] == p["final"] for p in early)
        bare_hits = sum(bare(p["early"]) == bare(p["final"]) for p in early)
        return {"n": len(cells), "early": len(early), "hit": hits, "hit_pct": round(100 * hits / max(1, len(cells)), 1),
                "same_words_pct": round(100 * bare_hits / max(1, len(cells)), 1)}

    summary: dict[str, Any] = {"utterances": len(results), "end_silence_s": END_SILENCE_S,
                               "finals_equal_across_waits": sum(r["same_final"] for r in results), "waits": {}}
    for wait in waits:
        key = f"{wait:g}"
        cells = [r["waits"][key] for r in results]
        entry: dict[str, Any] = {"limpio": share(cells, "limpio"), "ruido": share(cells, "ruido"),
                                 "taken_back": sum(c["taken_back"] for c in cells), "by_voz": {}, "by_clase": {}}
        for field in ("voz", "clase"):
            for value in sorted({r[field] for r in results}):
                chosen = [r["waits"][key] for r in results if r[field] == value]
                entry[f"by_{field}"][value] = {"limpio": share(chosen, "limpio")["hit_pct"],
                                               "ruido": share(chosen, "ruido")["hit_pct"]}
        summary["waits"][key] = entry
    if faithful:
        summary["noise_faithful"] = {"n": len(faithful), "with_early": sum(f["told"] > 0 for f in faithful),
                                     "ended_at_max_s": sum(f["final_s"] >= MAX_S - 0.05 for f in faithful)}
    return summary


if __name__ == "__main__":
    main()
