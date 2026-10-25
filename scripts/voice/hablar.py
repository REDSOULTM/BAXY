"""Spoken turns for live A/Bs: BAXY hears WAV files as if they were said into its microphone (BAXY_RENEW_VOICE_FEED,
src/baxy_mind/voice_feed.py), in real time, each after BAXY answered the one before and a gap of silence. No driver
and no virtual device: the voice takes the files in place of the microphone; the wake word, the end of the request, the
early transcript and the transcript are the microphone's own.

    py -3.12 -X utf8 scripts/voice/hablar.py llamada OUT.wav [--voz Raul] [--dicho "Baxi"]
    py -3.12 -X utf8 scripts/voice/hablar.py preparar RUN (WAV... | --manifest M [--cond limpio] [--voz V] [--clase C]
        [--ids a,b] [--max N]) --llamada CALL.wav [--pausa 0.3] [--gap 3]
    <mind-runtime python> -X utf8 scripts/voice/hablar.py probar RUN --catalog CATALOG
    py -3.12 -X utf8 scripts/voice/hablar.py correr SET LABEL [--early default|0|S] [--wake-warm default|0]
        [--timeout 1800]
    py -3.12 -X utf8 scripts/voice/hablar.py resumir SET/LABEL
    py -3.12 -X utf8 scripts/voice/hablar.py comparar SET/LABEL_A SET/LABEL_B [...]

llamada: «Baxy» said by a Windows OneCore voice into OUT.wav (16 kHz mono; written to a file, nothing is played). The
product listens in wake mode, so every turn starts with the call.
preparar: SET/feed/NNNN_<id>.wav (the call, a pause, the order; 16 kHz mono 16-bit) and SET/feed.txt (one file per
line, a tab and its gap). From a manifest of sintetizar_frases.py the texts go to SET/feed.json.
probar: each file of SET through voice.py's own path offline (the k4 wake word and Parakeet Ultra with the catalog's
names as hotwords, CPU, ~1 GB of RAM, faster than real time; no product, no microphone): whether «Baxy» is heard and
what is transcribed. Run it once per set before the product.
correr: one arm in SET/LABEL (a new folder): the product (scripts/run_renew.cmd, its window) with
BAXY_VOICE_WAKE_ON_START=1, the profile %LOCALAPPDATA%/BAXY/hablar-LABEL and SET's feed, until the feed says done (or --timeout),
then it is closed. The mind's trace rows written meanwhile (%LOCALAPPDATA%/BAXY/renew/turns.jsonl from the byte it had
when the arm began) are copied to SET/LABEL/turns.jsonl; the feed's times are SET/LABEL/feed.jsonl. Then resumir.
resumir: per file, the turn.decide row after its voice ended (its «early»: hit, saved_ms, waited_ms, or hit false and
the reason) and the first sound after it (voice.speak rows: sound_at; the notice counts as sound, first_answer is the
first that is not the notice), as ms from the end of the person's voice (voice.py's RMS end, as the feed logged it).
SET/LABEL/summary.json. comparar: the summaries side by side.

Live A/B on the notebook (benches belong there; the PC's RAM is tight)
1. The ear on the notebook: copy the k4 package (WakewordBaxy/models/final/baxy-wake-k4) and Parakeet Ultra
   (parakeet-ultra-sherpa-int8-oli) from the PC; set BAXY_RENEW_WAKE_DIR and BAXY_RENEW_STT_DIR to them (run_renew.cmd
   sets neither on REDNOTE). Close any other BAXY. Copy the synthetic set (D:/BAXYWork/w5-stt-synth) or make it there
   with sintetizar_frases.py.
2. A call and a set: ``llamada D:/BAXYeval/hablar/baxy.wav``; ``preparar D:/BAXYeval/hablar/base --manifest
   .../manifest.json --cond limpio --voz Supertonic --ids g001,g003,g004,g005,g009,g013,g015,g019,g023,g025
   --llamada D:/BAXYeval/hablar/baxy.wav --gap 3`` (questions and harmless settings: the rest of «general» turns the
   wifi off, closes or moves windows, deletes a file or answers a confirmation; every turn still acts on the notebook,
   as the e2e benches do). ``probar`` it: a file whose «Baxy» is not heard or whose transcript is wrong is taken out of
   feed.txt (a line starting with #), or the call is made with another voice. On the PC (2026-10-23) the OneCore
   Raul and Sabina calls («Baxi») were heard 25/25 before the 25 Supertonic «general» orders, all transcribed.
3. Arms, each a fresh product on the same set: ``correr SET default1``; ``correr SET early0-1 --early 0``; ``correr
   SET warm0-1 --wake-warm 0``; then again in the opposite order (warm0-2, early0-2, default2), the GPU idle otherwise.
   ``comparar SET/default1 SET/early0-1 ...`` reads the saving of palanca 2: first_answer_ms p50 with and without it,
   and in the default arms the hits (early.hit, saved_ms) and the misses by reason (text: the final transcript
   differed; pending, clock, request, cancelled, expired); default against warm0, palanca 5 (decide_prompt_ms_p50, the
   tokens read when deciding, and first_answer_ms). The hit rate on these synthetic files is measured offline in
   scripts/voice/medir_anticipada.py; the live arm says whether the mind's side holds it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import wave
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RATE = 16000
ONECORE = ("Raul", "Sabina", "Pablo", "Laura")


# --- audio -----------------------------------------------------------------------------------------------------------

def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        rate, width, channels = w.getframerate(), w.getsampwidth(), w.getnchannels()
        data = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError(f"{path}: {8 * width}-bit; 16-bit PCM is read")
    x = np.frombuffer(data, "<i2").astype(np.float32) / 32768
    if channels > 1:
        x = x.reshape(-1, channels).mean(axis=1)
    if rate != RATE:
        from scipy.signal import resample_poly
        f = Fraction(RATE, rate).limit_denominator(1000)
        x = resample_poly(x, f.numerator, f.denominator).astype(np.float32)
    return x


def write_wav(path: Path, x: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def trim(x: np.ndarray, floor: float = 0.01) -> np.ndarray:
    """The call without its leading and trailing silence (so the pause after it is the one asked for)."""
    loud = np.flatnonzero(np.abs(x) >= floor)
    return x[loud[0]:loud[-1] + 1] if len(loud) else x


def ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def llamada(out: Path, voz: str, dicho: str) -> None:
    """«Baxy» by a OneCore voice, to a file (nothing is played)."""
    with tempfile.TemporaryDirectory(prefix="baxy-llamada-") as folder:
        raw = Path(folder) / "raw.wav"
        script = Path(folder) / "llamada.ps1"
        script.write_text("\ufeff" + "\n".join([
            "Add-Type -AssemblyName System.Runtime.WindowsRuntime",
            "$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]",
            "$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]",
            "$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and "
            "$_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]",
            "function Await($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); "
            "$task.Wait(-1) | Out-Null; $task.Result }",
            "$s = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer",
            f"$s.Voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object {{ $_.DisplayName "
            f"-eq ('Microsoft ' + {ps_quote(voz)}) }} | Select-Object -First 1",
            f"$st = Await ($s.SynthesizeTextToStreamAsync({ps_quote(dicho)})) "
            "([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])",
            "$n = [uint32]$st.Size; $r = New-Object Windows.Storage.Streams.DataReader($st.GetInputStreamAt(0))",
            "$null = Await ($r.LoadAsync($n)) ([uint32]); $b = New-Object byte[] $n; $r.ReadBytes($b)",
            f"[System.IO.File]::WriteAllBytes({ps_quote(str(raw))}, $b)",
        ]) + "\n", encoding="utf-8")
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)], check=True)
        x = trim(read_wav(raw))
    write_wav(out, x / max(1e-6, float(np.max(np.abs(x)))) * 0.3)  # the synthetic set's level (sintetizar_frases.py)
    print(f"{out}: {len(x) / RATE:.2f} s")


# --- preparing a set -------------------------------------------------------------------------------------------------

def preparar(run: Path, wavs: list[str], manifest: str | None, filters: dict[str, Any], call: Path, pause: float,
             gap: float) -> None:
    items: list[dict[str, Any]] = []
    if manifest:
        rows = json.loads(Path(manifest).read_text(encoding="utf-8"))
        for key in ("cond", "voz", "clase"):
            if filters.get(key):
                rows = [r for r in rows if r[key] == filters[key]]
        if filters.get("ids"):
            wanted = filters["ids"].split(",")
            rows = [r for r in rows if r["id"] in wanted]
        items = [{"source": r["wav"], "id": r["id"], "texto": r["texto"], "voz": r["voz"], "cond": r["cond"],
                  "clase": r["clase"]} for r in rows]
    items += [{"source": w, "id": Path(w).stem} for w in wavs]
    if filters.get("max"):
        items = items[:int(filters["max"])]
    if not items:
        raise SystemExit("no file: give WAVs or a manifest whose filters keep some")
    feed = run / "feed"
    if feed.exists():
        raise SystemExit(f"{feed} exists: a set is prepared once per folder")
    said = trim(read_wav(call))
    lines = []
    for n, item in enumerate(items, 1):
        name = f"{n:04d}_{item['id']}.wav"
        x = np.concatenate([said, np.zeros(int(pause * RATE), np.float32), read_wav(Path(item["source"]))])
        write_wav(feed / name, x)
        item.update(file=f"feed/{name}", call_s=round(len(said) / RATE, 3))
        lines.append(f"feed/{name}\t{gap:g}")
    (run / "feed.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (run / "feed.json").write_text(json.dumps({"call": str(call), "pause_s": pause, "gap_s": gap, "items": items},
                                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(items)} files in {feed}; feed list {run / 'feed.txt'}")


def feed_files(set_dir: Path) -> list[Path]:
    sys.path.insert(0, str(ROOT / "src"))
    from baxy_mind.voice_feed import listed
    return [path for path, _ in listed(str(set_dir / "feed.txt"))]


# --- offline check: voice.py's own path, wake mode -------------------------------------------------------------------

def probar(run: Path, catalog: Path) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from baxy_mind import voice
    from baxy_mind.voice import BLOCK, Voice
    from medir_hotwords import catalog_names
    for var in ("BAXY_RENEW_WAKE_DIR", "BAXY_RENEW_STT_DIR"):
        if not os.environ.get(var):
            raise SystemExit(f"{var} is not set")
    os.environ["BAXY_RENEW_VOICE_FEED"] = str(run / "feed.txt")  # the voice reads the set as the product would
    os.environ.pop("BAXY_RENEW_VOICE_FEED_LOG", None)

    class Silent:
        speaking = False
        ready = False

        def __init__(self, *_args: Any) -> None:
            pass

    voice.Speech = Silent  # type: ignore[misc]
    Voice._open = lambda self: None  # type: ignore[method-assign]  # the blocks are queued here, faster than real time
    seen: list[dict[str, Any]] = []
    ended = threading.Event()

    def write(message: dict[str, Any]) -> None:
        seen.append(message)
        if message.get("type") == "voice.transcript" or (message.get("event") == "state" and any(
                m.get("event") == "transcribing" for m in seen)):
            ended.set()

    listening = Voice(write)
    listening.hear_names(catalog_names(catalog))
    listening._loaded.wait(600)
    if listening.failure or listening._detector is None or listening._recognizer is None:
        raise SystemExit(f"the voice did not load: {listening.failure}")
    meta = {item["file"]: item for item in json.loads((run / "feed.json").read_text(encoding="utf-8"))["items"]} \
        if (run / "feed.json").is_file() else {}
    report = []
    for path in feed_files(run):
        seen.clear()
        ended.clear()
        audio = np.concatenate([np.zeros(RATE, np.float32), read_wav(path), np.zeros(3 * RATE, np.float32)])
        assert listening.start("wake")
        with listening._lock:
            while not listening._blocks.empty():
                listening._blocks.get_nowait()
            padded = np.concatenate([audio, np.zeros(-len(audio) % BLOCK, np.float32)])
            for block in padded.reshape(-1, BLOCK):
                listening._blocks.put(block.copy())
        idle_since = None  # «Baxy» not heard: nothing ends, so the file is over once its blocks were all heard
        while not ended.wait(0.05):
            idle_since = (idle_since or time.monotonic()) if listening._blocks.empty() else None
            if idle_since is not None and time.monotonic() - idle_since > 5.0:
                break
        item = meta.get(f"feed/{path.name}", {})
        text = next((m["text"] for m in seen if m.get("type") == "voice.transcript"), None)
        row = {"file": path.name, "wake": any(m.get("event") == "wake_detected" for m in seen), "transcript": text,
               "texto": item.get("texto")}
        report.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    (run / "probar.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wake heard {sum(r['wake'] for r in report)}/{len(report)}, transcribed "
          f"{sum(bool(r['transcript']) for r in report)}/{len(report)}")


# --- the product -----------------------------------------------------------------------------------------------------

def trace_path() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "renew" / "turns.jsonl"


def correr(set_dir: Path, label: str, early: str, warm: str, timeout: float) -> None:
    import psutil
    run = set_dir / label
    for var in ("BAXY_RENEW_WAKE_DIR", "BAXY_RENEW_STT_DIR"):
        folder = os.environ.get(var, "")
        if not folder or not Path(folder).is_dir():
            raise SystemExit(f"{var} must name the ear's models on this PC (run_renew.cmd sets it only on the PC)")
    if not feed_files(set_dir):
        raise SystemExit(f"{set_dir / 'feed.txt'} names no file")
    if run.exists():
        raise SystemExit(f"{run} exists: each arm is a new label")
    run.mkdir(parents=True)
    log = run / "feed.jsonl"
    # Calidad PC 2026-10-25: BAXY_DATA_DIR was set here, and run_baxy.ps1 always replaces it (the core takes only a
    # child of %LOCALAPPDATA%/BAXY): every arm ran on the owner's development profile. Each arm its own profile.
    env = dict(os.environ, BAXY_VOICE_WAKE_ON_START="1",
               BAXY_RENEW_VOICE_FEED=str(set_dir / "feed.txt"), BAXY_RENEW_VOICE_FEED_LOG=str(log))
    for var, value in (("BAXY_RENEW_EARLY", early), ("BAXY_RENEW_WAKE_WARM", warm)):
        env.pop(var, None)
        if value != "default":
            env[var] = value
    trace = trace_path()
    offset = trace.stat().st_size if trace.is_file() else 0
    (run / "arm.json").write_text(json.dumps({"early": early, "wake_warm": warm, "started": dt.datetime.now().isoformat(
        timespec="seconds"), "trace_offset": offset, "computer": os.environ.get("COMPUTERNAME")}), encoding="utf-8")
    console = (run / "console.txt").open("w", encoding="utf-8")
    process = subprocess.Popen(["cmd", "/c", str(ROOT / "scripts" / "run_renew.cmd"), "--profile", f"hablar-{label}"],
                               cwd=str(ROOT), env=env, stdout=console, stderr=subprocess.STDOUT)
    family: dict[int, psutil.Process] = {}
    deadline = time.monotonic() + timeout
    done = False
    try:
        while time.monotonic() < deadline:
            try:
                for child in psutil.Process(process.pid).children(recursive=True):
                    family[child.pid] = child
                for child in list(family.values()):
                    for grandchild in child.children(recursive=True):
                        family[grandchild.pid] = grandchild
            except psutil.Error:
                pass
            if log.is_file() and any(json.loads(line).get("event") == "done"
                                     for line in log.read_text(encoding="utf-8").splitlines() if line.strip()):
                done = True
                break
            time.sleep(2)
    finally:
        for child in family.values():
            try:
                child.kill()
            except psutil.Error:
                pass
        if process.poll() is None:  # run_renew.cmd may have ended once the app was launched
            process.kill()
        console.close()
    rows = []
    if trace.is_file():
        with trace.open("rb") as source:
            source.seek(offset if trace.stat().st_size >= offset else 0)  # the mind starts a new file past 50 MB
            rows = source.read().decode("utf-8", "replace").splitlines()
    (run / "turns.jsonl").write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    print(f"{'done' if done else 'TIMEOUT'}: {len(rows)} trace rows")
    resumir(run)


# --- reading a run ---------------------------------------------------------------------------------------------------

def _at(text: str | None) -> float | None:
    return dt.datetime.fromisoformat(text).timestamp() if text else None


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(q * len(ordered)))])


def resumir(run: Path) -> dict[str, Any]:
    said = [json.loads(line) for line in (run / "feed.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    done = next((r for r in said if r.get("event") == "done"), None)
    said = [r for r in said if r.get("event") == "said"]
    rows = []
    for line in (run / "turns.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    arm = json.loads((run / "arm.json").read_text(encoding="utf-8")) if (run / "arm.json").is_file() else {}
    turns = []
    for i, row in enumerate(said):
        end = _at(row.get("voice_end_at")) or _at(row["ended_at"])
        until = _at(said[i + 1]["started_at"]) if i + 1 < len(said) else (_at(done["at"]) if done else float("inf"))
        inside = [r for r in rows if end <= (_at(r.get("t")) or 0) < until]
        decide = next((r for r in inside if r.get("stage") == "turn.decide"), None)
        sounds = [(r, _at(r.get("sound_at"))) for r in rows if r.get("stage") == "voice.speak" and r.get("sound_at")]
        sounds = [(r, at) for r, at in sounds if at is not None and end <= at < until]
        first = min((at for _, at in sounds), default=None)
        answer = min((at for r, at in sounds if not r.get("notice")), default=None)
        turns.append({"file": Path(row["wav"]).name, "decided": decide is not None,
                      "early": (decide or {}).get("early"), "prompt_ms": (decide or {}).get("prompt_ms"),
                      "decide_ms": (decide or {}).get("ms"),
                      "first_sound_ms": None if first is None else round((first - end) * 1000),
                      "first_answer_ms": None if answer is None else round((answer - end) * 1000)})
    early = [t["early"] for t in turns if t["early"]]
    reasons: dict[str, int] = {}
    for e in early:
        if not e.get("hit"):
            reasons[str(e.get("reason"))] = reasons.get(str(e.get("reason")), 0) + 1
    saved = [e["saved_ms"] for e in early if e.get("hit")]
    answers = [t["first_answer_ms"] for t in turns if t["first_answer_ms"] is not None]
    sounds = [t["first_sound_ms"] for t in turns if t["first_sound_ms"] is not None]
    prompts = [t["prompt_ms"] for t in turns if isinstance(t["prompt_ms"], (int, float))]
    summary = {"arm": {k: arm.get(k) for k in ("early", "wake_warm")}, "said": len(said), "done": done is not None,
               "decided": sum(t["decided"] for t in turns), "early_hit": len(saved),
               "early_miss": reasons, "saved_ms_p50": _pct(saved, 0.5),
               "saved_ms_mean": round(statistics.mean(saved)) if saved else None,
               "first_sound_ms_p50": _pct(sounds, 0.5), "first_sound_ms_p90": _pct(sounds, 0.9),
               "first_answer_ms_p50": _pct(answers, 0.5), "first_answer_ms_p90": _pct(answers, 0.9),
               "answered": len(answers), "decide_prompt_ms_p50": _pct(prompts, 0.5)}
    (run / "summary.json").write_text(json.dumps({"summary": summary, "turns": turns}, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def comparar(runs: list[Path]) -> None:
    summaries = [json.loads((run / "summary.json").read_text(encoding="utf-8"))["summary"] for run in runs]
    keys = [k for k in summaries[0] if k != "arm"]
    width = max(len(run.name) for run in runs) + 2
    print(" " * 24 + "".join(run.name.ljust(width) for run in runs))
    print("arm".ljust(24) + "".join(json.dumps(s["arm"]).ljust(width) for s in summaries))
    for key in keys:
        print(key.ljust(24) + "".join(json.dumps(s.get(key), ensure_ascii=False).ljust(width) for s in summaries))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("llamada")
    p.add_argument("out", type=Path)
    p.add_argument("--voz", default="Raul", choices=ONECORE)
    p.add_argument("--dicho", default="Baxi")
    p = sub.add_parser("preparar")
    p.add_argument("run", type=Path)
    p.add_argument("wavs", nargs="*")
    p.add_argument("--manifest")
    for key in ("cond", "voz", "clase", "ids", "max"):
        p.add_argument(f"--{key}")
    p.add_argument("--llamada", type=Path, required=True)
    p.add_argument("--pausa", type=float, default=0.3)
    p.add_argument("--gap", type=float, default=3.0)
    p = sub.add_parser("probar")
    p.add_argument("run", type=Path)
    p.add_argument("--catalog", type=Path, required=True)
    p = sub.add_parser("correr")
    p.add_argument("set", type=Path)
    p.add_argument("label")
    p.add_argument("--early", default="default")
    p.add_argument("--wake-warm", default="default")
    p.add_argument("--timeout", type=float, default=1800.0)
    p = sub.add_parser("resumir")
    p.add_argument("run", type=Path)
    p = sub.add_parser("comparar")
    p.add_argument("runs", type=Path, nargs="+")
    args = parser.parse_args()
    if args.command == "llamada":
        llamada(args.out, args.voz, args.dicho)
    elif args.command == "preparar":
        preparar(args.run, args.wavs, args.manifest, {k: getattr(args, k) for k in ("cond", "voz", "clase", "ids", "max")},
                 args.llamada, args.pausa, args.gap)
    elif args.command == "probar":
        probar(args.run, args.catalog)
    elif args.command == "correr":
        correr(args.set, args.label, args.early, args.wake_warm, args.timeout)
    elif args.command == "resumir":
        resumir(args.run)
    else:
        comparar(args.runs)


if __name__ == "__main__":
    main()
