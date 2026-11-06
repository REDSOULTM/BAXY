"""When a spoken request closes after the person stops (uso-74, fin de turno): how long after the real end of the speech,
and how often it closes in a pause in the middle (a cut), through voice.py's own path (Voice in direct mode for the
synthetic set, wake mode with the trigger at its time for the owner's clips; its 100 ms blocks, Silero, the speaker's
level, the early transcript and the turn model).

    <mind-runtime python> -X utf8 scripts/voice/medir_fin_de_turno.py sintetizar OUT_DIR
    <mind-runtime python> -X utf8 scripts/voice/medir_fin_de_turno.py clips WAKE_LOG_DIR OUT_JSON
    <mind-runtime python> -X utf8 scripts/voice/medir_fin_de_turno.py medir MANIFEST CATALOG OUT --arm registro|base|turno
        [--conds limpio,10] [--from A] [--to B]
    <mind-runtime python> -X utf8 scripts/voice/medir_fin_de_turno.py simular REGISTRO.json [REGISTRO.json ...]

sintetizar: frases_fin_de_turno.json in the five Spanish OneCore voices (the English lines in Zira); «|» is a pause of
0.6, 1.0 or 1.5 s inside the sentence, an SSML <break>, so the voice does not say the first half as a sentence. The
real end of the speech and the pause are measured on the clean audio (10 ms frames over -40 dB of 0.3). clips: the
owner's «Baxy» clips of BAXY_WAKE_LOG_DIR (voice.WakeLog; 4 s before the trigger and 4 s after it) with a transcript;
their manifest and results stay outside the repository (the owner's voice and words never enter it).

medir, per arm: «base» as before uso-74 (no turn model: 0.9 s, 2.0 s after hanging words), «turno» with the turn model
and voice.py's END_DONE_S / END_SLOW_S (the rule in a loud room), «registro» with the turn model and every wait at 3 s,
so no pause closes the request and every end of voice is heard: its turn probability and early transcript are kept for
simular, which replays any pair of waits (and the hanging words) on those ends without the recognizer. resumir reads
an arm's results against the registro's (cuts need it). BAXY_RENEW_STT_DIR: Parakeet Ultra; BAXY_RENEW_TURN_MODEL: the
turn model. CPU only, one recognizer (~1 GB of RAM).

Per class and condition: requests; cut (closed at an end of voice before the last one the registro heard, so words
were left out); the wait after the real end (p50, p90, mean, share over LONG_S; the requests not cut); WER against the
sentence (the synthetic set) or against the registro transcript (the clips); the turn model's wall and CPU ms per call.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from medir_anticipada import _Speech, bare, blocks, edits, heard_as, read  # noqa: E402
from sintetizar_frases import finish, ps_quote, read_wav, write_wav  # noqa: E402

from baxy_mind import voice  # noqa: E402
from baxy_mind.voice import BLOCK, MAX_S, RATE, Voice  # noqa: E402

PHRASES = HERE / "frases_fin_de_turno.json"
SPANISH = ["Raul", "Sabina", "Pablo", "Laura", "Helena"]
LANGS = {"Raul": "es-MX", "Sabina": "es-MX", "Pablo": "es-ES", "Laura": "es-ES", "Helena": "es-ES", "Zira": "en-US"}
PAUSES = (0.6, 1.0, 1.5)
RECORD_S = 3.0          # «registro»: no pause closes the request
FRAME = RATE // 100
LONG_S = 1.3            # a wait this long after the real end is felt as slow (the requests not cut)


# --- the synthetic set -------------------------------------------------------------------------------------------------

def ssml(text: str, voice_name: str, pause: float | None) -> str:
    body = text.replace("&", "&amp;").replace("<", "&lt;")
    body = body.replace(" | ", f' <break time="{int(pause * 1000)}ms"/> ') if pause else body.replace(" | ", " ")
    return (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{LANGS[voice_name]}">'
            f"{body}</speak>")


def truth(x: np.ndarray) -> dict[str, float | None]:
    """The real end of the speech and the longest pause inside it, on 10 ms frames over -40 dB of the 0.3 peak."""
    frames = x[: len(x) // FRAME * FRAME].reshape(-1, FRAME)
    on = np.flatnonzero(np.sqrt((frames ** 2).mean(axis=1)) >= 0.003)
    gaps = np.diff(on)
    k = int(np.argmax(gaps)) if len(gaps) else -1
    pause = len(gaps) and gaps[k] * FRAME / RATE >= 0.3
    return {"start_s": on[0] * FRAME / RATE, "end_s": (on[-1] + 1) * FRAME / RATE,
            "pause_from_s": (on[k] + 1) * FRAME / RATE if pause else None,
            "pause_to_s": on[k + 1] * FRAME / RATE if pause else None}


def sintetizar(out: Path) -> None:
    phrases = json.loads(PHRASES.read_text(encoding="utf-8"))["frases"]
    jobs = []
    for p in phrases:
        voices = ["Zira"] if p.get("lang") == "en" else SPANISH
        for v in voices:
            for pause in (PAUSES if "|" in p["texto"] else (None,)):
                name = f"{p['id']}-{v}" + (f"-{int(pause * 10):02d}" if pause else "")
                jobs.append((p, v, pause, out / "raw" / f"{name}.wav"))
    lines = [
        "Add-Type -AssemblyName System.Runtime.WindowsRuntime",
        "Add-Type -AssemblyName System.Speech",
        "$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]",
        "$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]",
        "$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and "
        "$_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]",
        "function Await($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); "
        "$task.Wait(-1) | Out-Null; $task.Result }",
        "$s = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer",
        "$z = New-Object System.Speech.Synthesis.SpeechSynthesizer",
        "$z.SelectVoice('Microsoft Zira Desktop')",
        "function One($voice, $text, $out) { $s.Voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | "
        "Where-Object { $_.DisplayName -eq ('Microsoft ' + $voice) } | Select-Object -First 1; "
        "$st = Await ($s.SynthesizeSsmlToStreamAsync($text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream]); "
        "$n = [uint32]$st.Size; $r = New-Object Windows.Storage.Streams.DataReader($st.GetInputStreamAt(0)); "
        "$null = Await ($r.LoadAsync($n)) ([uint32]); $b = New-Object byte[] $n; $r.ReadBytes($b); "
        "[System.IO.File]::WriteAllBytes($out, $b) }",
    ]
    (out / "raw").mkdir(parents=True, exist_ok=True)
    for p, v, pause, raw in jobs:
        if raw.is_file():
            continue
        text = ps_quote(ssml(p["texto"], v, pause))
        if v == "Zira":
            lines.append(f"$z.SetOutputToWaveFile({ps_quote(str(raw))}); $z.SpeakSsml({text}); $z.SetOutputToNull()")
        else:
            lines.append(f"One {ps_quote(v)} {text} {ps_quote(str(raw))}")
    script = out / "onecore.ps1"
    script.write_text("﻿" + "\n".join(lines) + "\n$z.Dispose()\n", encoding="utf-8")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)], check=True)
    manifest = []
    for p, v, pause, raw in jobs:
        x = finish(read_wav(raw))
        dest = out / "wav" / raw.name
        write_wav(dest, x)
        manifest.append({"wav": str(dest), "id": p["id"], "voz": v, "clase": p["clase"], "pausa_s": pause,
                         "texto": p["texto"].replace(" | ", " "), "lang": p.get("lang", "es"), **truth(x)})
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=0), encoding="utf-8")
    print(len(manifest), "utterances")


def clips(folder: Path, out: Path) -> None:
    """The owner's «Baxy» clips that went on with a request (their words stay in OUT, outside the repository)."""
    manifest = []
    for record in sorted(folder.rglob("*.json")):
        data = json.loads(record.read_text(encoding="utf-8"))
        wav = record.with_name(data.get("wav") or "")
        if data.get("near_miss") or not data.get("transcript") or not wav.is_file() or data.get("before_s") is None:
            continue
        manifest.append({"wav": str(wav), "id": record.stem, "voz": "dueño", "clase": "dueño", "pausa_s": None,
                         "trigger_s": float(data["before_s"]), "clip_s": float(data["before_s"]) + float(data["after_s"]),
                         "texto": None, "lang": "es"})
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=0), encoding="utf-8")
    print(len(manifest), "clips")


# --- hearing through voice.py ------------------------------------------------------------------------------------------

class Wake:
    """The detector of a clip: «Baxy» heard where the owner's detector heard it (the clip's trigger)."""

    def __init__(self) -> None:
        self.at: float | None = None
        self._heard = 0

    def reset(self) -> None:
        self._heard = 0

    def accept(self, block: np.ndarray) -> list[Any]:
        before, self._heard = self._heard, self._heard + len(block)
        if self.at is not None and before < self.at * RATE <= self._heard:
            return [SimpleNamespace(time_s=self.at, probability=1.0)]
        return []

    def scores(self) -> list[tuple[float, float]]:
        return []


class Told:
    """What one Voice told and decided for one utterance."""

    def __init__(self) -> None:
        self.voice: Voice | None = None
        self.reset()

    def reset(self) -> None:
        self.done = threading.Event()
        self.transcribing = False
        self.final: str | None = None
        self.close_s: float | None = None
        self.runs: list[tuple[float, float]] = []   # the request's voice: (from, to) of each run of voice blocks
        self.turn: dict[float, float] = {}          # end of voice → the turn model's probability
        self.turn_ms: list[float] = []              # the turn model's wall time per call
        self.turn_cpu_ms: list[float] = []          # and its CPU time (onnxruntime runs on this thread)
        self.early: dict[float, str] = {}           # end of voice → the early transcript decoded in its silence

    def write(self, message: dict[str, Any]) -> None:
        if message.get("type") == "voice.transcript":
            self.final = message["text"]
        elif message.get("event") == "transcribing":
            self.transcribing = True
        elif message.get("event") == "state" and self.transcribing:
            if self.final is None:
                self.final = ""
            self.done.set()

    def on_early(self, _seq: int, text: str | None) -> None:
        if text is not None and self.voice is not None and self.voice._early_at is not None:
            self.early[round(self.voice._early_at, 3)] = text


def make_voice(arm: str, names: list[str], shared: dict[str, Any]) -> tuple[Voice, Told]:
    voice.Speech = _Speech  # type: ignore[misc]

    def load(self: Voice) -> None:
        try:
            loading(self)
        except Exception as error:  # noqa: BLE001 - told by the assert after the wait, without waiting it out
            self.failure = repr(error)
        finally:
            self._loaded.set()

    def loading(self: Voice) -> None:
        import sherpa_onnx
        self._input = True
        self._vad = voice.Vad(sherpa_onnx)
        self._detector = Wake()
        if arm != "base":
            self._load_turn()
            assert self._turn is not None, "no turn model (BAXY_RENEW_TURN_MODEL)"
            complete = self._turn.complete

            def timed(audio: np.ndarray) -> float:
                t, cpu = time.perf_counter(), time.thread_time()
                p = complete(audio)
                self._told_by.turn_ms.append((time.perf_counter() - t) * 1000)  # type: ignore[attr-defined]
                self._told_by.turn_cpu_ms.append((time.thread_time() - cpu) * 1000)  # type: ignore[attr-defined]
                return p
            self._turn.complete = timed  # type: ignore[method-assign]
        if "recognizer" in shared:
            self._recognizer, self._hotwords = shared["recognizer"], shared["hotwords"]
        else:
            self.hear_names(names)
            self._recognize(sherpa_onnx, Path(os.environ["BAXY_RENEW_STT_DIR"]))
            shared.update(recognizer=self._recognizer, hotwords=self._hotwords)

    Voice._load = load  # type: ignore[method-assign]
    Voice._open = lambda self: None  # type: ignore[method-assign]
    Voice._live = lambda self, start: None  # type: ignore[method-assign]  # captions decide nothing
    finish_ = Voice._finish
    turn_wait = Voice._turn_wait

    def finished(self: Voice, start: float) -> Any:
        told: Told = self._told_by  # type: ignore[attr-defined]
        told.close_s = self._total / RATE
        runs: list[list[float]] = []
        for i in self._request_voice(start):
            at = start + i * BLOCK / RATE
            if runs and abs(runs[-1][1] - at) < 1e-6:
                runs[-1][1] = at + BLOCK / RATE
            else:
                runs.append([at, at + BLOCK / RATE])
        told.runs = [(round(a, 3), round(b, 3)) for a, b in runs]
        return finish_(self, start)

    def waited(self: Voice, start: float, end: float, now: float) -> float | None:
        wait = turn_wait(self, start, end, now)
        if self._turn_heard is not None and self._turn_heard[1] is not None:
            self._told_by.turn[round(self._turn_heard[0], 3)] = round(self._turn_heard[1], 4)  # type: ignore[attr-defined]
        return wait

    Voice._finish = finished  # type: ignore[method-assign]
    Voice._turn_wait = waited  # type: ignore[method-assign]
    told = Told()
    v = Voice(told.write, on_early=told.on_early, early_s=0.2)
    v._told_by = told  # type: ignore[attr-defined]
    told.voice = v
    v._loaded.wait(600)
    assert v._recognizer is not None, v.failure
    return v, told


def hear(v: Voice, told: Told, audio: np.ndarray, trigger_s: float | None) -> None:
    told.reset()
    v._detector.at = trigger_s  # type: ignore[union-attr]
    assert v.start("wake" if trigger_s is not None else "direct")
    with v._lock:
        while not v._blocks.empty():
            v._blocks.get_nowait()
        for block in blocks(audio):
            v._blocks.put(block)
    if not told.done.wait(180):
        raise TimeoutError("the request did not end")
    v.stop()


def medir(manifest: Path, catalog: Path, out: Path, arm: str, conds: list[str], first: int, last: int) -> None:
    from medir_hotwords import catalog_names
    if arm == "registro":
        voice.END_DONE_S = voice.END_UNSURE_S = voice.END_SLOW_S = voice.END_SILENCE_S = RECORD_S
    rows = json.loads(manifest.read_text(encoding="utf-8"))[first:last]
    v, told = make_voice(arm, catalog_names(catalog), {})
    results = []
    started = time.perf_counter()
    for n, r in enumerate(rows, 1):
        x = read(r["wav"])
        trigger = r.get("trigger_s")
        for k, cond in enumerate(conds if trigger is None else ["limpio"]):
            if trigger is None:
                audio = heard_as(x, cond, 7919 * (first + n) + k)
            else:
                audio = np.concatenate([x, np.zeros(int((trigger + MAX_S + 1.0) * RATE) - len(x), np.float32)])
            hear(v, told, audio, trigger)
            results.append({**{key: r.get(key) for key in ("id", "voz", "clase", "pausa_s", "texto", "end_s",
                                                           "pause_from_s", "pause_to_s", "trigger_s", "clip_s")},
                            "cond": cond, "arm": arm, "final": told.final, "close_s": told.close_s,
                            "runs": told.runs, "turn": told.turn, "early": told.early,
                            "turn_ms": [round(t, 1) for t in told.turn_ms],
                            "turn_cpu_ms": [round(t, 1) for t in told.turn_cpu_ms]})
        if n % 20 == 0:
            print(f"{n}/{len(rows)} {time.perf_counter() - started:.0f} s", flush=True)
    out.write_text(json.dumps(results, ensure_ascii=False, indent=0), encoding="utf-8")
    print(json.dumps(summarize(results, {}), ensure_ascii=False, indent=1))


# --- the numbers -------------------------------------------------------------------------------------------------------

def real_end(r: dict[str, Any], reference: dict[str, Any] | None) -> float | None:
    """The real end of the speech: the clean audio's (synthetic), or the last voice the registro heard (clips; None for
    a clip whose voice runs into its end, cut by the clip and not by the ear)."""
    if r.get("end_s") is not None:
        return float(r["end_s"])
    ref = reference or r
    if not ref["runs"]:
        return None
    end = ref["runs"][-1][1]
    return None if r.get("clip_s") is not None and end > r["clip_s"] - 0.3 else end


def row_numbers(r: dict[str, Any], reference: dict[str, Any] | None) -> dict[str, Any] | None:
    end = real_end(r, reference)
    if end is None or r["close_s"] is None or not (reference or r)["runs"]:
        return None
    # Cut: it closed at an end of voice before the last one the registro heard (the same audio, the same ear).
    closed_end = max((b for _, b in r["runs"] if b <= r["close_s"] + 1e-6), default=None)
    cut = closed_end is not None and closed_end < (reference or r)["runs"][-1][1] - 0.05
    said = r["texto"] if r.get("texto") else (reference or r)["final"] or ""
    words = bare(said).split()
    return {"cut": cut, "wait": r["close_s"] - end, "errors": edits(words, bare(r["final"] or "").split()),
            "words": len(words), "max": r["close_s"] >= (r.get("trigger_s") or 0) + MAX_S - 0.05}


def summarize(results: list[dict[str, Any]], references: dict[tuple[str, str, Any, str], dict[str, Any]]
              ) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        numbers = row_numbers(r, references.get(key(r)))
        if numbers is None:
            continue
        for g in ("todo", f"{r['clase']}", f"{r['clase']}@{r['cond']}", f"pausa {r['pausa_s']}@{r['cond']}"):
            groups.setdefault(g, []).append({**numbers, "turn_ms": r.get("turn_ms") or [],
                                             "turn_cpu_ms": r.get("turn_cpu_ms") or []})
    out = {}
    for g, rows in sorted(groups.items()):
        waits = np.array([x["wait"] for x in rows if not x["cut"]])
        ms = [t for x in rows for t in x["turn_ms"]]
        cpu = [t for x in rows for t in x["turn_cpu_ms"]]
        out[g] = {"n": len(rows), "cortes_pct": round(100 * sum(x["cut"] for x in rows) / len(rows), 1),
                  "espera_p50_s": round(float(np.percentile(waits, 50)), 2) if len(waits) else None,
                  "espera_p90_s": round(float(np.percentile(waits, 90)), 2) if len(waits) else None,
                  "larga_pct": round(100 * float((waits >= LONG_S).mean()), 1) if len(waits) else None,
                  "espera_media_s": round(float(waits.mean()), 2) if len(waits) else None,
                  "wer_pct": round(100 * sum(x["errors"] for x in rows) / max(1, sum(x["words"] for x in rows)), 2),
                  "a_max_s": sum(x["max"] for x in rows),
                  "turno_ms_p50": round(float(np.percentile(ms, 50)), 1) if ms else None,
                  "turno_cpu_ms_p50": round(float(np.percentile(cpu, 50)), 1) if cpu else None}
    return out


def key(r: dict[str, Any]) -> tuple[str, str, Any, str]:
    return (r["id"], r["voz"], r["pausa_s"], r["cond"])


def simular(paths: list[Path]) -> None:
    """Each policy replayed on the registro's ends of voice: the request closes at the first end whose silence reaches
    its wait (the turn model's, or the hanging words' on the early transcript), else MAX_S."""
    rows = [r for p in paths for r in json.loads(p.read_text(encoding="utf-8"))]
    policies: dict[str, Any] = {}
    for fixed in (0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4):  # the rule without the model, its fixed silence moved
        policies[f"base {fixed}/colgando 2.0"] = lambda p, early, f=fixed: (
            voice.END_SLOW_S if early is not None and voice.end_silence(early) > voice.END_SILENCE_S else f)
    hanging = lambda early: early is not None and voice.end_silence(early) > voice.END_SILENCE_S  # noqa: E731
    for unsure in (1.2, 1.5):  # the three waits, alone and with the hanging words' wait as a floor
        tiers = lambda p, u=unsure: (voice.END_SLOW_S if p is None or p < voice.TURN_OPEN_P else  # noqa: E731
                                     u if p < voice.TURN_P else voice.END_DONE_S)
        policies[f"tres {voice.END_DONE_S}/{unsure}/{voice.END_SLOW_S}"] = lambda p, early, t=tiers: t(p)
        policies[f"tres+colgando {voice.END_DONE_S}/{unsure}/{voice.END_SLOW_S}"] = (
            lambda p, early, t=tiers: max(t(p), voice.END_SLOW_S if hanging(early) else 0.0))
    for done in (0.6, 0.7, 0.8, 0.9):
        for open_ in (1.5, 1.8, 2.0, 2.5):
            for threshold in (0.5, 0.7):
                policies[f"turno p>={threshold} {done}/{open_}"] = (
                    lambda p, early, d=done, o=open_, t=threshold: o if p is None or p < t else d)
                policies[f"turno+colgando p>={threshold} {done}/{open_}"] = (
                    lambda p, early, d=done, o=open_, t=threshold: o if p is None or p < t or hanging(early) else d)
    for name, policy in policies.items():
        simulated = []
        for r in rows:
            runs, close_s = r["runs"], None
            turn = {round(float(k), 3): p for k, p in r["turn"].items()}
            early_at = {round(float(k), 3): text for k, text in r["early"].items()}
            for i, (_, end) in enumerate(runs):
                gap = runs[i + 1][0] - end if i + 1 < len(runs) else float("inf")
                wait = policy(turn.get(round(end, 3)), early_at.get(round(end, 3)))
                if gap >= wait - 1e-6:
                    close_s = end + wait
                    break
            start = (r.get("trigger_s") or 0.0)
            close_s = min(close_s if close_s is not None else start + MAX_S, start + MAX_S)
            kept = [run for run in runs if run[1] <= close_s + 1e-6]
            simulated.append({**r, "close_s": close_s, "runs": kept or runs[:1],
                              "final": r["final"] if len(kept) == len(runs) else None})
        summary = summarize(simulated, {key(r): r for r in rows})
        print(name, json.dumps({g: (c["n"], c["cortes_pct"], c["espera_p50_s"], c["espera_p90_s"], c["larga_pct"],
                                    c["espera_media_s"])
                                for g, c in summary.items()}, ensure_ascii=False))


def main() -> None:
    command = sys.argv[1]
    option = lambda name, default: sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default  # noqa: E731
    if command == "sintetizar":
        sintetizar(Path(sys.argv[2]))
    elif command == "clips":
        clips(Path(sys.argv[2]), Path(sys.argv[3]))
    elif command == "medir":
        medir(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), option("--arm", "turno"),
              option("--conds", "limpio").split(","), int(option("--from", "0")), int(option("--to", "100000")))
    elif command == "simular":
        simular([Path(p) for p in sys.argv[2:]])
    elif command == "resumir":  # resumir OUT.json [OUT.json ...] --ref REGISTRO.json[;REGISTRO.json ...]
        paths = [Path(p) for p in sys.argv[2:sys.argv.index("--ref") if "--ref" in sys.argv else None]]
        references = {key(r): r for p in option("--ref", "").split(";") if p
                      for r in json.loads(Path(p).read_text(encoding="utf-8"))}
        results = [r for p in paths for r in json.loads(p.read_text(encoding="utf-8"))]
        print(json.dumps(summarize(results, references), ensure_ascii=False, indent=1))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
