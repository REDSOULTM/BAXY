"""F44: what the PC plays and says «Baxy» after a silence, on this PC's own speakers and microphone: does the wake word
fire, and what do the microphone, the canceller and the loopback each hear at that moment.

1. ``frases``: writes one WAV per line of a JSON list ({"id", "voz", "texto"}) with the OneCore voices. Only synthetic
   voices; the installer's lines (its own voice) can be added to the playlist as they are.
2. ``grabar``: for each WAV of the playlist, SILENCIO s of nothing playing and then the clip on the default output
   (sounddevice), recording what the product would hear: the microphone as voice.py opens it, the loopback reference
   as voice_echo.Loopback hands it to each block, and the stage's output, in the microphone's callback as in the
   product. Its own process, closed at the end; ``--ganancia`` scales the clip, ``--volumen`` sets the system's volume
   for the recording and puts it back.
3. ``medir``: replays that recording through the product's detectors (load_wake, EitherWake, wake_gain, its reset) on
   the microphone, on the stage's output and on the reference: one row per clip, and what Voice._played_it says of
   each firing.
4. ``simular`` and ``persona``: the same stage and check with no speakers: the reference goes through a simulated room
   (soft clipping, a decaying path, noise) into the microphone; ``persona`` adds a voice to the microphone only, over
   what the PC plays. For when the speakers do not reach the microphone, and for voices no loopback can carry.

    <mind-runtime python> -X utf8 scripts/voice/medir_disparos.py grabar OUT --lista frases.json --silencio 20

BAXY_RENEW_WAKE_DIR and BAXY_RENEW_WAKE_FAST_DIR as for the mind. Everything recorded stays in OUT, outside the
repository; only figures are printed.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
import wave
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
from scipy.signal import resample_poly

WORKTREE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE / "src"))
from baxy_mind import voice as V  # noqa: E402
from baxy_mind import voice_echo  # noqa: E402
from baxy_mind.voice_output import default_follower  # noqa: E402

RATE = V.RATE
TAIL_S = 2.0


def below_normal() -> None:
    kernel = ctypes.windll.kernel32
    kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x00004000)


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        rate, channels, width, frames = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.readframes(w.getnframes())
    kind, scale = {2: (np.int16, 32768.0), 4: (np.int32, 2147483648.0)}[width]
    return (np.frombuffer(frames, kind).reshape(-1, channels).mean(axis=1) / scale).astype(np.float32), rate


def write_wav(path: Path, x: np.ndarray, rate: int = RATE) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def frases(out: Path, lista: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    lines = [
        "Add-Type -AssemblyName System.Runtime.WindowsRuntime",
        "$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]",
        "$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]",
        "$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and "
        "$_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]",
        "function Await($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); "
        "$task.Wait(-1) | Out-Null; $task.Result }",
        "$s = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer",
        "function One($voice, $text, $out) { $s.Voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | "
        "Where-Object { $_.DisplayName -eq ('Microsoft ' + $voice) } | Select-Object -First 1; "
        "$st = Await ($s.SynthesizeTextToStreamAsync($text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream]); "
        "$n = [uint32]$st.Size; $r = New-Object Windows.Storage.Streams.DataReader($st.GetInputStreamAt(0)); "
        "$null = Await ($r.LoadAsync($n)) ([uint32]); $b = New-Object byte[] $n; $r.ReadBytes($b); "
        "[System.IO.File]::WriteAllBytes($out, $b) }",
    ]
    for item in json.loads(lista.read_text(encoding="utf-8")):
        lines.append(f"One {ps_quote(item['voz'])} {ps_quote(item['texto'])} {ps_quote(str(out / (item['id'] + '.wav')))}")
    script = out / "frases.ps1"
    script.write_text("﻿" + "\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)], check=True)


def master_volume():
    """The default output's volume control (pycaw, in the mind's runtime)."""
    from pycaw.pycaw import AudioUtilities
    return AudioUtilities.GetSpeakers().EndpointVolume


def grabar(out: Path, clips: list[Path], silencio: float, ganancia: float, volumen: float | None) -> None:
    import sounddevice as sd
    below_normal()
    control = master_volume()
    before = control.GetMasterVolumeLevelScalar()
    if volumen is not None:
        control.SetMasterVolumeLevelScalar(volumen, None)
    loopback = voice_echo.Loopback(RATE)
    mic, ref, cancelled = [], [], []

    def take(count: int) -> np.ndarray:
        ref.append(loopback.take(count))
        return ref[-1]

    canceller = voice_echo.EchoCanceller(RATE, take)

    def heard(indata, _frames, _when, _status) -> None:
        block = np.array(indata[:, 0], dtype=np.float32, copy=True)
        cancelled.append(canceller(block))
        mic.append(block)

    device_in, device_out = default_follower(sd, "input"), default_follower(sd, "output")
    stream = sd.InputStream(device=device_in, samplerate=RATE, channels=1, dtype="float32", blocksize=V.BLOCK,
                            callback=heard)
    placed = []
    stream.start()
    try:
        for clip in clips:
            time.sleep(silencio)
            x, rate = read_wav(clip)
            placed.append({"clip": clip.stem, "at_s": sum(len(b) for b in mic) / RATE, "s": len(x) / rate})
            sd.play(x * ganancia, rate, device=device_out, blocking=True)
        time.sleep(TAIL_S)
    finally:
        stream.close()
        loopback.close()
        control.SetMasterVolumeLevelScalar(before, None)
    for name, parts in (("mic", mic), ("ref", ref), ("aec", cancelled)):
        write_wav(out / f"{name}.wav", np.concatenate(parts))
    meta = {"placed": placed, "loopback": loopback.name, "input": sd.query_devices(device_in)["name"],
            "output": sd.query_devices(device_out)["name"], "silencio_s": silencio, "ganancia": ganancia,
            "volumen": before if volumen is None else volumen}
    (out / "grabacion.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))


def detector():
    main = V.load_wake(Path(os.environ["BAXY_RENEW_WAKE_DIR"]))
    fast = V.load_fast_wake()
    return main if fast is None else V.EitherWake(main, fast)


def firings(wake, audio: np.ndarray) -> list[tuple[float, float]]:
    """(when, probability) of each firing on ``audio`` heard as voice.py hears it: wake_gain, reset every WAKE_RESET_S."""
    fired: list[tuple[float, float]] = []
    wake.reset()
    peak, at_reset = V.WAKE_TARGET, 0.0
    for at in range(0, len(audio) // V.BLOCK * V.BLOCK, V.BLOCK):
        now = (at + V.BLOCK) / RATE
        if now - at_reset >= V.WAKE_RESET_S:
            wake.reset()
            at_reset = at / RATE
        peak, raised = V.wake_gain(peak, audio[at:at + V.BLOCK])
        fired += [(at_reset + d.time_s, float(getattr(d, "probability", 0.0) or 0.0)) for d in wake.accept(raised)]
    return fired


def dbfs(x: np.ndarray) -> float:
    return 20 * float(np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)) if len(x) else -180.0


def replay_stage(mic: np.ndarray, ref: np.ndarray) -> np.ndarray:
    blocks = iter(ref[at:at + V.BLOCK] for at in range(0, len(ref), V.BLOCK))
    stage = voice_echo.EchoCanceller(RATE, lambda _count: next(blocks))
    out = np.zeros_like(mic)
    for at in range(0, len(mic) // V.BLOCK * V.BLOCK, V.BLOCK):
        out[at:at + V.BLOCK] = stage(mic[at:at + V.BLOCK])
    return out


def medir(out: Path) -> None:
    below_normal()
    meta = json.loads((out / "grabacion.json").read_text(encoding="utf-8"))
    mic, _ = read_wav(out / "mic.wav")
    ref, _ = read_wav(out / "ref.wav")
    aec, _ = read_wav(out / "aec.wav")
    wake = detector()
    heard = {"mic": firings(wake, mic), "aec": firings(wake, aec), "ref": firings(wake, ref)}
    print(json.dumps({k: len(v) for k, v in heard.items()}))
    for item in meta["placed"]:
        a, b = item["at_s"], item["at_s"] + item["s"] + 1.5
        row = {k: [f"{t - a:.2f}/{p:.2f}" for t, p in v if a <= t <= b] for k, v in heard.items()}
        i, j = int(a * RATE), int((a + item["s"]) * RATE)
        print(f"{item['clip']:<14} mic {dbfs(mic[i:j]):6.1f} ref {dbfs(ref[i:j]):6.1f} aec {dbfs(aec[i:j]):6.1f} dBFS  "
              f"sala {dbfs(mic[i - RATE * 5:i - RATE]):6.1f}  {json.dumps(row)}")
    check = checker()
    for name in ("mic", "aec"):
        for t, p in heard[name]:
            print(f"{name} fired {t:7.2f} p={p:.2f}: {'played by the PC' if played_it(check, ref, t) else 'opens a request'}")
    a0 = meta["placed"][0]["at_s"]
    outside = {k: [round(t, 1) for t, _ in v if t < a0] for k, v in heard.items()}
    print("before the first clip:", outside)


# --- 4. without the speakers ---------------------------------------------------------------------------------------

def room_path(rng: np.random.Generator, delay_ms: float) -> np.ndarray:
    """A small room's echo path at 16 kHz: the direct sound ``delay_ms`` late and a 0.3 s decaying tail."""
    n = int(0.3 * RATE)
    tail = rng.standard_normal(n) * np.exp(-np.arange(n) / (0.05 * RATE)) * 0.25
    tail[0] = 1.0
    return np.concatenate([np.zeros(int(delay_ms * RATE / 1000)), tail]).astype(np.float32)


def speakers(far: np.ndarray, path: np.ndarray, gain_db: float, room_db: float, rng: np.random.Generator) -> np.ndarray:
    """What the microphone hears of ``far``: small speakers' soft clipping, the room's path, ``gain_db`` over the
    reference as measured on the PC (mic -30 dBFS for a reference at -49), and a room's noise at ``room_db``."""
    raised = far * 10 ** (gain_db / 20)
    echo = np.convolve(np.tanh(raised * 2) / 2, path)[:len(far)]
    noise = np.cumsum(rng.standard_normal(len(far))) * 0.02
    noise = noise - np.convolve(noise, np.ones(800) / 800, "same")
    return (echo + noise * 10 ** (room_db / 20) / (np.std(noise) + 1e-9)).astype(np.float32)


def level_to(x: np.ndarray, db: float) -> np.ndarray:
    voiced = x[np.abs(x) > 0.01 * np.max(np.abs(x))]
    return x * np.float32(10 ** (db / 20) / np.sqrt(np.mean(voiced ** 2)))


def at_rate(path: Path) -> np.ndarray:
    x, rate = read_wav(path)
    return resample_poly(x, RATE, rate).astype(np.float32) if rate != RATE else x


class OldGain:
    """voice_echo.ReferenceGain before F44: its peak aged in the silences too."""

    def __init__(self) -> None:
        self._peak = 0.0

    def __call__(self, reference: np.ndarray) -> np.ndarray:
        self._peak = max(self._peak * voice_echo.REF_PEAK_HOLD, float(np.max(np.abs(reference))) if len(reference) else 0.0)
        return reference * np.float32(min(voice_echo.REF_GAIN_CAP, voice_echo.REF_TARGET / max(self._peak, 1e-9)))


def checker():
    """The product's check (Voice._played_it) on its detector, without a Voice."""
    return SimpleNamespace(_played_twin=None, _detector=detector())


def played_it(check: Any, far: np.ndarray, at_s: float) -> bool:
    i = int(at_s * RATE)
    first = max(0, i - int(voice_echo.PLAYED_BACK_S * RATE))
    seen = far[first:i + int(getattr(check._detector, "played_hold_s", voice_echo.PLAYED_HOLD_S) * RATE)]
    return bool(seen.any()) and V.Voice._played_it(check, seen, (i - first) / RATE)


def simular(clips: list[Path], silencio: float, gain_db: float, seed: int, old_gain: bool) -> None:
    """The PC plays each clip after ``silencio`` s of nothing, on a simulated room: does the wake word fire on the
    stage's output (a request before F44), and does the check say it was played (no request now). One row per clip."""
    rng = np.random.default_rng(seed)
    path = room_path(rng, 40.0)
    wake, check = detector(), checker()
    print(f"silencio {silencio:.0f} s, eco {gain_db:+.0f} dB sobre la referencia, semilla {seed}, "
          f"ganancia {'vieja' if old_gain else 'nueva'}")
    stage_blocks: list[np.ndarray] = []
    stage = voice_echo.EchoCanceller(RATE, lambda _n: stage_blocks.pop(0))
    if old_gain:
        stage._gain = OldGain()
    fired_total, opened, out_db = 0, 0, []
    for clip in clips:
        far = np.concatenate([np.zeros(int(silencio * RATE), np.float32), level_to(at_rate(clip), -49.0),
                              np.zeros(RATE, np.float32)])
        mic = speakers(far, path, gain_db, -68.0, rng)
        heard = np.zeros_like(mic)
        for at in range(0, len(mic) // V.BLOCK * V.BLOCK, V.BLOCK):
            stage_blocks.append(far[at:at + V.BLOCK])
            heard[at:at + V.BLOCK] = stage(mic[at:at + V.BLOCK])
        begin = int(max(0.0, silencio - 2.0) * RATE)
        row = []
        for t, p in firings(wake, heard[begin:]):
            played = played_it(check, far, begin / RATE + t)
            row.append(f"{t - 2.0:.2f}/{p:.2f} {'del PC' if played else 'ABRE PEDIDO'}")
            fired_total += 1
            opened += not played
        s, n = int(silencio * RATE), int(1.5 * RATE)
        out_db.append(dbfs(mic[s:s + n]) - dbfs(heard[s:s + n]))
        print(f"{clip.stem:<12} quita {out_db[-1]:4.1f} dB en 1,5 s | {row}", flush=True)
    print(json.dumps({"clips": len(clips), "disparos": fired_total, "pedidos abiertos": opened,
                      "dB quitados, media": round(float(np.mean(out_db)), 1)}))


def persona(fondo: Path, voces: list[Path], ser: float, gain_db: float, seed: int) -> None:
    """A person says ``voces`` over ``fondo`` (played by the PC, its echo on a simulated room): the same stage and check.
    The voice is added to the microphone only, as a person is, at ``ser`` dB over the echo's level."""
    rng = np.random.default_rng(seed)
    path = room_path(rng, 40.0)
    wake, check = detector(), checker()
    far = level_to(at_rate(fondo), -49.0)
    mic = speakers(far, path, gain_db, -68.0, rng)
    echo_db = dbfs(mic[mic != 0])
    at_s, placed = 6.0, []
    blocks = iter(far[at:at + V.BLOCK] for at in range(0, len(far), V.BLOCK))
    for voice_clip in voces:
        x = level_to(at_rate(voice_clip), echo_db + ser)
        a = int(at_s * RATE)
        if a + len(x) >= len(mic):
            break
        mic[a:a + len(x)] += x
        placed.append((voice_clip.stem, at_s, at_s + len(x) / RATE))
        at_s += len(x) / RATE + 6.0
    stage = voice_echo.EchoCanceller(RATE, lambda _n: next(blocks))
    heard = np.zeros_like(mic)
    for at in range(0, len(mic) // V.BLOCK * V.BLOCK, V.BLOCK):
        heard[at:at + V.BLOCK] = stage(mic[at:at + V.BLOCK])
    fired = firings(wake, heard)
    rows = {"voces": len(placed), "oídas": 0, "abren pedido": 0, "fondo": fondo.stem, "voz sobre el eco, dB": ser}
    for _stem, a, b in placed:
        near = [t for t, _ in fired if a - 0.2 <= t <= b + 1.5]
        if near:
            rows["oídas"] += 1
            rows["abren pedido"] += not played_it(check, far, near[0])
    print(json.dumps(rows, ensure_ascii=False), flush=True)


def recognizer():
    import sherpa_onnx
    stt = Path(os.environ["BAXY_RENEW_STT_DIR"])
    return sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(stt / "encoder.int8.onnx"), decoder=str(stt / "decoder.int8.onnx"),
        joiner=str(stt / "joiner.int8.onnx"), tokens=str(stt / "tokens.txt"), num_threads=2,
        model_type="nemo_transducer", feature_dim=128, provider="cpu", decoding_method="greedy_search")


def said(rec, audio: np.ndarray) -> str:
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak < 0.008:
        return ""
    stream = rec.create_stream()
    stream.accept_waveform(RATE, np.ascontiguousarray(audio * min(8.0, 0.45 / peak), dtype=np.float32))
    rec.decode_stream(stream)
    return stream.result.text.strip()


def pedido(fondo: Path | None, voz: Path, lineas: list[Path], ser: float, gain_db: float, seed: int,
           orden: Path | None) -> None:
    """A person says «Baxy» (``voz``, on the microphone only) and right after it the PC plays ``lineas``, each an order:
    what the request is heard saying, and what is left of it without what the PC said over the same time (Heard.
    without_played). ``fondo``: what played before, so the stage has learned the room; without it the PC was silent.
    ``orden``: the control, a person's own request (on the microphone only) over each line: it must stay."""
    rng = np.random.default_rng(seed)
    path = room_path(rng, 40.0)
    rec = recognizer()
    call = at_rate(voz)
    before = level_to(at_rate(fondo), -49.0)[:12 * RATE] if fondo is not None else np.zeros(4 * RATE, np.float32)
    for line in lineas:
        order = level_to(at_rate(line), -49.0)
        at = len(before)
        far = np.concatenate([before, np.zeros(len(call), np.float32), order, np.zeros(RATE, np.float32)])
        mic = speakers(far, path, gain_db, -68.0, rng)
        echo_db = dbfs(mic[:at]) if fondo is not None else dbfs(mic[at + len(call):at + len(call) + len(order)])
        mic[at:at + len(call)] += level_to(call, echo_db + ser)
        blocks = iter(far[k:k + V.BLOCK] for k in range(0, len(far), V.BLOCK))
        stage = voice_echo.EchoCanceller(RATE, lambda _n: next(blocks))
        heard = np.zeros_like(mic)
        for k in range(0, len(mic) // V.BLOCK * V.BLOCK, V.BLOCK):
            heard[k:k + V.BLOCK] = stage(mic[k:k + V.BLOCK])
        s = at + len(call)
        ear, played = said(rec, heard[s:]), said(rec, far[s:])
        left = V.Heard(ear).without_call().without_played(played).text
        print(f"{line.stem}: oído «{ear}» → pedido «{left}»", flush=True)
    if orden is None:
        return
    for line in lineas:
        far = np.concatenate([before, level_to(at_rate(line), -49.0), np.zeros(RATE, np.float32)])
        mic = speakers(far, path, gain_db, -68.0, rng)
        at = len(before)
        person = level_to(at_rate(orden), dbfs(mic[at:at + 2 * RATE]) + ser)
        mic[at:at + len(person)] += person[:len(mic) - at]
        blocks = iter(far[k:k + V.BLOCK] for k in range(0, len(far), V.BLOCK))
        stage = voice_echo.EchoCanceller(RATE, lambda _n: next(blocks))
        heard = np.zeros_like(mic)
        for k in range(0, len(mic) // V.BLOCK * V.BLOCK, V.BLOCK):
            heard[k:k + V.BLOCK] = stage(mic[k:k + V.BLOCK])
        ear, played = said(rec, heard[at:]), said(rec, far[at:])
        left = V.Heard(ear).without_call().without_played(played).text
        print(f"persona sobre {line.stem}: oído «{ear}» → pedido «{left}»", flush=True)


class Fed:
    """voice.Voice with its real detectors, recognizer, check and rules, a simulated room instead of the devices: blocks
    go in as the microphone's callback puts them (one at a time, waiting for the thread that hears them, so what was
    played is what it would be), with the real canceller."""

    def __init__(self, gate: bool) -> None:
        self.told: list[dict[str, Any]] = []
        self.gate = gate
        self.far: list[np.ndarray] = []
        self.voice = V.Voice(self.told.append)
        self.voice.hear_names([])
        self.voice._open = lambda: None  # type: ignore[method-assign]
        self.voice._close = lambda: None  # type: ignore[method-assign]
        if not self.voice.start("wake"):
            raise RuntimeError(self.voice.failure or "the ear did not load")
        self.voice._revive = lambda: None  # type: ignore[method-assign]
        self.blocks: list[np.ndarray] = []
        self.stage = voice_echo.EchoCanceller(RATE, lambda _n: self.blocks.pop(0))
        if gate:
            self.voice._echo = voice_echo.Stage(self.stage, lambda: None, self.stage.played)

    def play(self, far: np.ndarray, mic: np.ndarray) -> None:
        for at in range(0, len(mic) // V.BLOCK * V.BLOCK, V.BLOCK):
            self.blocks.append(far[at:at + V.BLOCK])
            heard = self.stage(mic[at:at + V.BLOCK])
            self.voice._blocks.put(heard)
            while not self.voice._blocks.empty():
                time.sleep(0.002)
        time.sleep(0.05)

    def take(self) -> tuple[int, list[str]]:
        told, self.told[:] = list(self.told), []
        return (sum(1 for m in told if m.get("event") == "wake_detected"),
                [m["text"] for m in told if m.get("type") == "voice.transcript"])


def producto(clips: list[Path], persona_clips: list[Path], silencio: float, gain_db: float, seed: int, gate: bool,
             fondo: Path | None = None, ser: float = 0.0) -> None:
    """The product's whole ear, clip by clip: what the PC plays alone, after ``silencio`` s; then a person's request
    (on the microphone only) over what the PC plays: how many requests open and what reaches the mind."""
    rng = np.random.default_rng(seed)
    path = room_path(rng, 40.0)
    fed = Fed(gate)
    tail = np.zeros(int((V.NO_COMMAND_S + 2.0) * RATE), np.float32)
    opened, reached = 0, 0
    for clip in clips:
        far = np.concatenate([np.zeros(int(silencio * RATE), np.float32), level_to(at_rate(clip), -49.0), tail])
        fed.play(far, speakers(far, path, gain_db, -68.0, rng))
        wakes_, words = fed.take()
        opened += wakes_
        reached += len(words)
        print(f"{clip.stem:<12} pedidos {wakes_} | a la mente {words}", flush=True)
    print(json.dumps({"lineas del PC": len(clips), "pedidos abiertos": opened, "llegan a la mente": reached, "con comprobación": gate}))
    if not persona_clips:
        return
    under = np.resize(level_to(at_rate(fondo if fondo is not None else clips[0]), -49.0), 600 * RATE)
    kept, at = 0, 0
    for voice_clip in persona_clips:
        person = at_rate(voice_clip)
        far = np.concatenate([under[at:at + 3 * RATE + len(person) + RATE], tail])
        at += 3 * RATE + len(person) + RATE
        mic = speakers(far, path, gain_db, -68.0, rng)
        person = level_to(person, dbfs(mic[RATE:3 * RATE]) + ser)
        mic[3 * RATE:3 * RATE + len(person)] += person
        fed.play(far, mic)
        wakes_, words = fed.take()
        kept += bool(words)
        print(f"persona {voice_clip.stem:<8} pedidos {wakes_} | a la mente {words}", flush=True)
    print(json.dumps({"personas": len(persona_clips), "llegan": kept}))


def vivo(clip: Path) -> None:
    """The real Voice on this PC's real microphone and loopback, ``clip`` on the default output: the stage opens, what was
    played is what it keeps, and the check hears the word in it. The ear is stopped and every device closed at the end."""
    import sounddevice as sd
    told: list[dict[str, Any]] = []
    ear = V.Voice(told.append)
    ear.hear_names([])
    if not ear.start("wake"):
        raise RuntimeError(ear.failure or "the ear did not start")
    try:
        status = ear.status()
        x, rate = read_wav(clip)
        time.sleep(2.0)
        sd.play(x, rate, device=default_follower(sd, "output"), blocking=True)
        time.sleep(1.5)
        far = ear._echo.played(len(x) / rate + 3.0) if ear._echo is not None else np.zeros(0)
        seconds = len(far) / RATE
        sounding = np.flatnonzero(far)
        # The word is near the start of a clip that says it first; the real check is asked about a firing there.
        started = float(sounding[0]) / RATE if len(sounding) else 0.0
        said_on_it = bool(far.any()) and ear._played_it(far, started + 1.0)
        print(json.dumps({"echo": status["echo"], "wake": status["wake"], "stt": status["stt"], "segundos guardados": seconds,
                          "suena desde": started, "referencia dBFS": round(dbfs(far), 1),
                          "la palabra en lo reproducido": said_on_it,
                          "pedidos abiertos": sum(1 for m in told if m.get("event") == "wake_detected"),
                          "a la mente": [m["text"] for m in told if m.get("type") == "voice.transcript"]},
                         ensure_ascii=False))
    finally:
        ear.stop()
    print(json.dumps({"tras parar, micrófono abierto": ear._stream is not None, "etapa": ear._echo is not None}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["frases", "grabar", "medir", "simular", "persona", "pedido", "producto", "vivo"])
    parser.add_argument("--personas", type=Path, nargs="*", default=[], help="requests a person says over the PC (producto)")
    parser.add_argument("--sin-comprobar", action="store_true", help="the ear without F44's check and taking out (producto)")
    parser.add_argument("out", type=Path)
    parser.add_argument("--lista", type=Path, help="JSON list of {id, voz, texto}")
    parser.add_argument("--clips", type=Path, nargs="*", default=[], help="the playlist's WAVs, in order")
    parser.add_argument("--silencio", type=float, default=20.0)
    parser.add_argument("--ganancia", type=float, default=1.0)
    parser.add_argument("--volumen", type=float, help="the system's volume during the recording (put back at the end)")
    parser.add_argument("--eco", type=float, default=19.0, help="the echo's dB over the reference (simular, persona)")
    parser.add_argument("--semilla", type=int, default=1)
    parser.add_argument("--ganancia-vieja", action="store_true", help="the reference's gain as it was before F44")
    parser.add_argument("--fondo", type=Path, help="what the PC plays under the person (persona)")
    parser.add_argument("--ser", type=float, default=0.0, help="dB of the person's voice over the echo (persona)")
    parser.add_argument("--orden", type=Path, help="a person's request over each line (pedido)")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.step == "frases":
        frases(args.out, args.lista)
    elif args.step == "grabar":
        grabar(args.out, args.clips, args.silencio, args.ganancia, args.volumen)
    elif args.step == "simular":
        below_normal()
        simular(args.clips, args.silencio, args.eco, args.semilla, args.ganancia_vieja)
    elif args.step == "persona":
        below_normal()
        persona(args.fondo, args.clips, args.ser, args.eco, args.semilla)
    elif args.step == "vivo":
        vivo(args.clips[0])
    elif args.step == "producto":
        below_normal()
        producto(args.clips, args.personas, args.silencio, args.eco, args.semilla, not args.sin_comprobar, args.fondo,
                 args.ser)
    elif args.step == "pedido":
        below_normal()
        pedido(args.fondo, args.clips[0], args.clips[1:], args.ser, args.eco, args.semilla, args.orden)
    else:
        medir(args.out)


if __name__ == "__main__":
    main()
