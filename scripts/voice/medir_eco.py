"""Echo cancellation (src/baxy_mind/voice_echo.py) before and after, on this PC's own speakers and microphone.

1. ``cancion``: a synthetic song (an original Spanish lyric read by the OneCore Raul and Sabina over a synthesized band),
   written to OUT, never played. Nothing in it is anyone's voice or a published recording.
2. ``grabar``: plays it on the default output (sounddevice, BAXY's own path) after SILENCE_S without it, and records
   what the product would hear: the microphone as voice.py opens it, the loopback reference as voice_echo.Loopback
   hands it to each block, and voice_echo.EchoCanceller's output, all in the microphone's callback as in the product.
   Its own process, closed when the song ends; the system volume is never touched.
3. ``medir``: on that recording, without AEC, with the product's stage (AEC3's linear output) and with AEC3's final
   output, one part per run (each a tanda of a few minutes):
   --parte a: echo left, wake-word firings per minute and words the recognizer writes from the song alone; and (c) the
       stage's cost per 100 ms block and the delay it adds;
   --parte baxy: the owner's «Baxy» recordings (--baxy) mixed into the recorded microphone at --ser dB over the echo
       (without --ser: over the silence before the song, the control), and how many the wake word hears;
   --parte pedidos: requests with their text (--pedidos: TranscripcionBaxy pares.json) the same: the word error of
       their transcripts and the song's words that got into them.

    <mind-runtime python> -X utf8 scripts/voice/medir_eco.py cancion OUT
    <mind-runtime python> -X utf8 scripts/voice/medir_eco.py grabar OUT
    <mind-runtime python> -X utf8 scripts/voice/medir_eco.py medir OUT --parte baxy --ser -10 --baxy DIR

BAXY_RENEW_WAKE_DIR and BAXY_RENEW_STT_DIR as for the mind. Everything recorded or mixed stays in OUT, outside the
repository; only figures are printed.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import wave
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

WORKTREE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKTREE / "src"))
from baxy_mind import voice as V  # noqa: E402
from baxy_mind import voice_echo  # noqa: E402
from baxy_mind.voice_output import default_follower  # noqa: E402

RATE = V.RATE
SONG_RATE = 48000
SILENCE_S = 20.0
TAIL_S = 2.0
CONVERGE_S = 3.0         # the first seconds of the song, while AEC3 learns the path, are left out of the figures
SER_DB = (5.0, 0.0, -5.0, -10.0)
CLIP_EVERY_S = 4.0
# An original lyric for this measurement (2026-11-03); no command, no name of an application.
LETRA = [
    "Camino por la orilla cuando cae la tarde",
    "y el viento de la costa me cuenta su canción",
    "las olas van y vienen dibujando la arena",
    "y el cielo se pone naranja sobre el mar",
    "Tengo una ventana que mira hacia los cerros",
    "y cada mañana la luz entra despacio",
    "las calles del puerto suben y se enredan",
    "y la gente camina con frío y sin prisa",
    "Canta la gaviota encima del muelle",
    "el pescador regresa con la red vacía",
    "pero trae en los ojos el color del agua",
    "y una historia nueva para contar en casa",
    "Mañana será otro día dice la radio",
    "la niebla se levanta y se va por la bahía",
    "y yo sigo caminando con las manos frías",
    "pensando en la música que suena en la plaza",
    "Bailan las parejas bajo los faroles",
    "un acordeón antiguo repite la misma nota",
    "y la noche llega lenta como un barco grande",
    "que entra sin ruido al fondo del puerto",
]
ONECORE = ["Raul", "Sabina"]


def below_normal() -> None:
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        rate, width, channels = w.getframerate(), w.getsampwidth(), w.getnchannels()
        data = w.readframes(w.getnframes())
    assert width == 2, (path, width)
    x = np.frombuffer(data, "<i2").astype(np.float32) / 32768
    return (x.reshape(-1, channels).mean(axis=1) if channels > 1 else x), rate


def to_rate(x: np.ndarray, rate: int, target: int) -> np.ndarray:
    if rate == target:
        return x
    f = Fraction(target, rate).limit_denominator(1000)
    return resample_poly(x, f.numerator, f.denominator).astype(np.float32)


def write_wav(path: Path, x: np.ndarray, rate: int = RATE) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


# --- 1. the song ----------------------------------------------------------------------------------------------------

def band(seconds: float, rng: np.random.Generator) -> np.ndarray:
    """Am-F-C-G at 96 bpm: pad chords with harmonics, a bass line, kick and hi-hat."""
    n = int(seconds * SONG_RATE)
    t = np.arange(n) / SONG_RATE
    beat = 60 / 96
    roots = [220.0, 174.61, 261.63, 196.0]
    chord = np.array([roots[int(x // (4 * beat)) % 4] for x in t[::480]]).repeat(480)[:n]
    out = np.zeros(n, np.float32)
    for ratio, gain in ((1.0, 0.25), (1.26, 0.18), (1.5, 0.2), (2.0, 0.1)):
        phase = 2 * np.pi * np.cumsum(chord * ratio) / SONG_RATE
        out += gain * (np.sin(phase) + 0.3 * np.sin(2 * phase) + 0.15 * np.sin(3 * phase))
    out += 0.35 * np.sin(2 * np.pi * np.cumsum(chord / 2) / SONG_RATE)
    pos = (t % beat) / beat
    out += 0.6 * np.sin(2 * np.pi * 55 * t) * np.exp(-pos * 18)
    half = ((t + beat / 2) % beat) / beat
    out += 0.12 * rng.standard_normal(n) * np.exp(-half * 40)
    return out


def cancion(out: Path) -> None:
    raw = out / "letra"
    raw.mkdir(parents=True, exist_ok=True)
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
    for k, line in enumerate(LETRA):
        lines.append(f"One {ps_quote(ONECORE[k // 4 % 2])} {ps_quote(line)} {ps_quote(str(raw / f'{k:02d}.wav'))}")
    script = out / "letra.ps1"
    script.write_text("﻿" + "\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)], check=True)
    rng = np.random.default_rng(3)
    voice = [np.zeros(int(4 * 60 / 96 * 2 * SONG_RATE), np.float32)]  # two bars of intro
    for k in range(len(LETRA)):
        x, rate = read_wav(raw / f"{k:02d}.wav")
        voice += [to_rate(x, rate, SONG_RATE), np.zeros(int(0.7 * SONG_RATE), np.float32)]
    vocal = np.concatenate(voice)
    music = band(len(vocal) / SONG_RATE, rng)[:len(vocal)]
    rms = lambda a: float(np.sqrt(np.mean(a[a != 0] ** 2)))  # noqa: E731
    song = vocal / rms(vocal) + music / rms(music) * 10 ** (-4 / 20)  # the voice 4 dB over the band, as in a pop mix
    song = (song / np.max(np.abs(song)) * 0.7).astype(np.float32)
    write_wav(out / "cancion.wav", song, SONG_RATE)
    print(f"cancion.wav: {len(song) / SONG_RATE:.1f} s, {sum(len(x.split()) for x in LETRA)} words")


# --- 2. the recording -----------------------------------------------------------------------------------------------

def grabar(out: Path) -> None:
    import sounddevice as sd
    below_normal()
    song, rate = read_wav(out / "cancion.wav")
    loopback = voice_echo.Loopback(RATE)
    mic, ref, cancelled, costs = [], [], [], []

    def take(count: int) -> np.ndarray:
        ref.append(loopback.take(count))
        return ref[-1]

    canceller = voice_echo.EchoCanceller(RATE, take)

    def heard(indata, _frames, _when, _status) -> None:
        block = np.array(indata[:, 0], dtype=np.float32, copy=True)
        start = time.perf_counter()
        cancelled.append(canceller(block))
        costs.append(time.perf_counter() - start)
        mic.append(block)

    device_in, device_out = default_follower(sd, "input"), default_follower(sd, "output")
    stream = sd.InputStream(device=device_in, samplerate=RATE, channels=1, dtype="float32", blocksize=V.BLOCK,
                            callback=heard)
    stream.start()
    try:
        time.sleep(SILENCE_S)
        play_at = sum(len(b) for b in mic)
        sd.play(song, rate, device=device_out, blocking=True)
        time.sleep(TAIL_S)
    finally:
        stream.close()
        loopback.close()
    for name, parts in (("mic", mic), ("ref", ref), ("aec", cancelled)):
        write_wav(out / f"{name}.wav", np.concatenate(parts))
    meta = {"play_at_s": play_at / RATE, "song_s": len(song) / rate, "loopback": loopback.name,
            "input": sd.query_devices(device_in)["name"], "output": sd.query_devices(device_out)["name"],
            "trimmed_s": loopback.trimmed / RATE, "cost_ms_p50": 1000 * float(np.percentile(costs, 50)),
            "cost_ms_p95": 1000 * float(np.percentile(costs, 95)), "blocks": len(costs)}
    (out / "grabacion.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta, indent=1))


# --- 3. the figures -------------------------------------------------------------------------------------------------

PRODUCT = "AEC3 lineal (BAXY)"
FINAL = "AEC3 salida final"
KEPT = ("sin AEC", PRODUCT, FINAL)


def aec_variants(mic: np.ndarray, ref: np.ndarray) -> dict[str, np.ndarray]:
    """The product's stage (voice_echo.EchoCanceller: AEC3's linear output, the reference raised), AEC3's final output
    on the same raised reference, and the product's stage on the reference as the loopback gives it."""
    from pywebrtc_audio import EchoCanceller
    blocks = iter(ref[at:at + V.BLOCK] for at in range(0, len(ref), V.BLOCK))
    product = voice_echo.EchoCanceller(RATE, lambda _count: next(blocks))
    plain_blocks = iter(ref[at:at + V.BLOCK] for at in range(0, len(ref), V.BLOCK))
    plain = voice_echo.EchoCanceller(RATE, lambda _count: next(plain_blocks))
    plain._gain = lambda far: far
    final, gain = EchoCanceller(RATE, 1, 0), voice_echo.ReferenceGain()
    out = {name: np.zeros_like(mic) for name in (PRODUCT, FINAL, "lineal sin subir la referencia")}
    for at in range(0, len(mic) // V.BLOCK * V.BLOCK, V.BLOCK):
        block = mic[at:at + V.BLOCK]
        out[PRODUCT][at:at + V.BLOCK] = product(block)
        out[FINAL][at:at + V.BLOCK] = final.process(block, gain(ref[at:at + V.BLOCK]))
        out["lineal sin subir la referencia"][at:at + V.BLOCK] = plain(block)
    return {"sin AEC": mic, **out}


def wake_detector():
    import importlib.util
    wake = Path(os.environ["BAXY_RENEW_WAKE_DIR"])
    spec = importlib.util.spec_from_file_location("baxy_wake_k4", wake / "baxy_wake_runtime.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["baxy_wake_k4"] = module
    spec.loader.exec_module(module)
    config = json.loads((wake / "config.json").read_text(encoding="utf-8"))
    return V.StaggeredWake(lambda: module.BaxyWakeDetector(
        wake / config["encoder"]["file"], wake / config["head"]["file"], threshold=config["threshold"],
        debounce_s=config["debounce_s"], threads=1), V.WAKE_COPIES, float(config["debounce_s"]))


def wakes(detector, audio: np.ndarray, start: int = 0) -> list[float]:
    """When the wake word fired on ``audio`` (seconds from ``start``), heard as voice.py hears it (wake_gain), the
    detector afresh every WAKE_RESET_S as in the product (its frames are kept until a reset)."""
    fired: list[float] = []
    window = int(V.WAKE_RESET_S * RATE)
    for w0 in range(0, len(audio), window):
        detector.reset()
        peak = V.WAKE_TARGET
        chunk = audio[w0:w0 + window]
        for at in range(0, len(chunk) // V.BLOCK * V.BLOCK, V.BLOCK):
            peak, raised = V.wake_gain(peak, chunk[at:at + V.BLOCK])
            fired += [(start + w0) / RATE + d.time_s for d in detector.accept(raised)]
    return fired


def heard_clips(detector, audio: np.ndarray, placed: list[tuple[int, int, int]]) -> int:
    """How many placed clips the wake word heard: each on its own stretch (1.5 s before it to 1.5 s after it)."""
    count = 0
    for _k, a, b in placed:
        s = max(0, a - int(1.5 * RATE))
        fired = wakes(detector, audio[s:b + int(1.5 * RATE)], s)
        count += any(a / RATE - 0.2 <= t <= b / RATE + 1.0 for t in fired)
    return count


def recognizer():
    import sherpa_onnx
    stt = Path(os.environ["BAXY_RENEW_STT_DIR"])
    return sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(stt / "encoder.int8.onnx"), decoder=str(stt / "decoder.int8.onnx"),
        joiner=str(stt / "joiner.int8.onnx"), tokens=str(stt / "tokens.txt"), num_threads=2,
        model_type="nemo_transducer", feature_dim=128, provider="cpu", decoding_method="greedy_search")


def transcribe(rec, audio: np.ndarray) -> str:
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak < 0.008:
        return ""
    stream = rec.create_stream()
    stream.accept_waveform(RATE, np.ascontiguousarray(audio * min(8.0, 0.45 / peak), dtype=np.float32))
    rec.decode_stream(stream)
    return stream.result.text.strip()


def voice_segments(vad: V.Vad, audio: np.ndarray) -> list[tuple[int, int]]:
    """What the ear would transcribe while open: runs of voice blocks (voice.voiced) closed by END_SILENCE_S, at most
    MAX_S each."""
    vad.reset()
    n = len(audio) // V.BLOCK * V.BLOCK
    marks = np.concatenate([vad.marks(audio[at:at + V.BLOCK]) for at in range(0, n, V.BLOCK)])
    voice = V.voiced(audio[:n], marks)
    gap, longest = int(V.END_SILENCE_S * 10), int(V.MAX_S * 10)
    segments, start, last = [], None, None
    for k, on in enumerate(voice):
        if on and start is None:
            start = last = k
        elif on:
            last = k
        if start is not None and (k - last >= gap or k - start >= longest or k == len(voice) - 1):
            segments.append((start * V.BLOCK, (last + 1) * V.BLOCK))
            start = None
    return segments


def words(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", text.lower())
    return re.findall(r"[a-z0-9ñ]+", "".join(c for c in folded if not unicodedata.combining(c)))


def wer(ref: list[str], hyp: list[str]) -> int:
    row = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, row[0] = row[0], i
        for j, h in enumerate(hyp, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (r != h))
    return row[-1]


def mixed(mic: np.ndarray, clips: list[np.ndarray], start_s: float, end_s: float, ser_db: float | None,
          ) -> tuple[np.ndarray, list[tuple[int, int, int]]]:
    """``clips`` added to ``mic`` every CLIP_EVERY_S from ``start_s``; each at ``ser_db`` over the echo under it (the
    recorded microphone's RMS there), or as recorded when None. Returns the mix and (clip, start, end) of each."""
    out, placed = mic.copy(), []
    at = int(start_s * RATE)
    for k, clip in enumerate(clips):
        if at + len(clip) > int(end_s * RATE):
            break
        if ser_db is not None:
            echo = float(np.sqrt(np.mean(mic[at:at + len(clip)] ** 2)))
            clip = clip / max(1e-6, float(np.sqrt(np.mean(clip ** 2)))) * echo * 10 ** (ser_db / 20)
        out[at:at + len(clip)] += clip
        placed.append((k, at, at + len(clip)))
        at += max(len(clip), int(CLIP_EVERY_S * RATE)) + int(0.5 * RATE)
    return np.clip(out, -1, 1), placed


def owner_requests(pares: list[Path]) -> list[tuple[np.ndarray, list[str]]]:
    """The owner's recorded requests and what each says (TranscripcionBaxy's pares.json: «wav», «texto»)."""
    found = []
    for path in pares:
        for row in json.loads(path.read_text(encoding="utf-8")):
            wav = Path(row["wav"])
            wav = wav if wav.is_absolute() else path.parent / wav
            if wav.is_file() and row.get("texto"):
                audio, rate = read_wav(wav)
                if len(audio) / rate <= V.MAX_S:
                    found.append((to_rate(audio, rate, RATE), words(row["texto"])))
    return found


def medir(out: Path, part: str, ser: float | None, count: int, baxy_dir: Path | None, pares: list[Path]) -> None:
    """One part (each a tanda of a few minutes): ``a`` the song alone; ``baxy`` the owner's «Baxy» over the song at
    ``ser`` dB over its echo (None: over the silence before it, as recorded); ``pedidos`` the owner's requests the same."""
    import sherpa_onnx
    below_normal()
    meta = json.loads((out / "grabacion.json").read_text(encoding="utf-8"))
    mic, _ = read_wav(out / "mic.wav")
    ref, _ = read_wav(out / "ref.wav")
    song0 = int((meta["play_at_s"] + CONVERGE_S) * RATE)
    song1 = int((meta["play_at_s"] + meta["song_s"]) * RATE)
    quiet1 = int((meta["play_at_s"] - 0.5) * RATE)
    power = lambda a: float(np.mean(a.astype(np.float64) ** 2))  # noqa: E731
    lyric = {w for line in LETRA for w in words(line)}
    s0, s1 = (1.0, meta["play_at_s"] - 0.5) if ser is None else (song0 / RATE, song1 / RATE)
    label = "sobre el silencio, como se grabó" if ser is None else f"sobre la canción, voz {ser:+.0f} dB sobre el eco"
    if part == "a":
        variants = aec_variants(mic, ref)
        noise = power(mic[int(1.0 * RATE):quiet1])
        print(f"grabación: {meta['input']} ← {meta['output']} (loopback {meta['loopback']}); canción "
              f"{meta['song_s']:.0f} s; en el micrófono: sala {10 * np.log10(noise + 1e-12):.1f} dBFS, con la canción "
              f"{10 * np.log10(power(mic[song0:song1]) + 1e-12):.1f} dBFS; loopback "
              f"{10 * np.log10(power(ref[song0:song1]) + 1e-12):.1f} dBFS", flush=True)
        detector, vad, rec = wake_detector(), V.Vad(sherpa_onnx), recognizer()
        minutes = (song1 - song0) / RATE / 60
        print("(a) la canción sola (eco quitado: sobre el ruido de la sala, que ningún AEC quita)", flush=True)
        for name, audio in variants.items():
            echo_in, echo_out = power(mic[song0:song1]) - noise, power(audio[song0:song1]) - noise
            erle = 10 * np.log10(max(echo_in, 1e-12) / max(echo_out, echo_in * 1e-4))
            fired = wakes(detector, audio[song0:song1])
            said = []
            for a, b in voice_segments(vad, audio[song0:song1]):
                said += words(transcribe(rec, audio[song0 + a:song0 + b]))
            print(f"  {name:30s} eco quitado {erle:5.1f} dB · activaciones falsas {len(fired) / minutes:4.1f}/min "
                  f"· palabras transcritas {len(said):3d} ({len(said) / minutes:.0f}/min, "
                  f"{sum(w in lyric for w in said)} de la letra)", flush=True)
        a, m = variants[PRODUCT][:quiet1], mic[:quiet1]
        lags = range(-400, 401)
        corr = [float(np.dot(m[1000:-1000], a[1000 + d:len(a) - 1000 + d])) for d in lags]
        print(f"(c) la etapa por bloque de 100 ms en el callback del micrófono: p50 {meta['cost_ms_p50']:.2f} ms, p95 "
              f"{meta['cost_ms_p95']:.2f} ms ({meta['blocks']} bloques); retardo que añade: "
              f"{lags[int(np.argmax(corr))] / RATE * 1000:.1f} ms; referencia recortada para no quedar atrás: "
              f"{meta['trimmed_s']:.2f} s", flush=True)
    elif part == "baxy":
        rng = np.random.default_rng(7)
        names = sorted(p for p in baxy_dir.glob("*.wav") if "amigo" not in p.name)
        pick = [names[i] for i in rng.choice(len(names), size=min(count, len(names)), replace=False)]
        clips = [read_wav(p)[0] for p in pick]
        detector = wake_detector()
        totals = {name: [0, 0] for name in KEPT}
        done = 0
        while done < len(clips):
            mix, placed = mixed(mic, clips[done:], s0, s1, ser)
            if not placed:
                break
            outs = aec_variants(mix, ref)
            for name in KEPT:
                totals[name][0] += heard_clips(detector, outs[name], placed)
                totals[name][1] += len(placed)
            done += len(placed)
        print(f"(b) «Baxy» del dueño {label}: " + " · ".join(f"{n} {h}/{t}" for n, (h, t) in totals.items()),
              flush=True)
    else:
        requests = owner_requests(pares)[:count]
        rec = recognizer()
        errors = {name: [0, 0, 0] for name in KEPT}
        done = 0
        while done < len(requests):
            mix, placed = mixed(mic, [a for a, _ in requests[done:]], s0, s1, ser)
            if not placed:
                break
            outs = aec_variants(mix, ref)
            for name in KEPT:
                for k, a, b in placed:
                    truth = requests[done + k][1]
                    got = words(transcribe(rec, outs[name][max(0, a - int(0.3 * RATE)):b + int(0.5 * RATE)]))
                    errors[name][0] += wer(truth, got)
                    errors[name][1] += len(truth)
                    errors[name][2] += sum(w in lyric and w not in truth for w in got)
            done += len(placed)
        print(f"(b) {done} pedidos (--pedidos) {label}: " + " · ".join(
            f"{n} WER {100 * e / max(1, t):.1f} % y {x} palabras de la letra" for n, (e, t, x) in errors.items()),
            flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["cancion", "grabar", "medir"])
    parser.add_argument("out", type=Path)
    parser.add_argument("--parte", choices=["a", "baxy", "pedidos"], default="a")
    parser.add_argument("--ser", type=float, help="dB of the voice over the song's echo; without it, over the silence")
    parser.add_argument("--n", type=int, default=24, help="clips or requests")
    parser.add_argument("--baxy", type=Path, help="the owner's «Baxy» recordings (WAV)")
    parser.add_argument("--pedidos", type=Path, nargs="*", default=[], help="pares.json of the owner's requests")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.step == "cancion":
        cancion(args.out)
    elif args.step == "grabar":
        grabar(args.out)
    else:
        medir(args.out, args.parte, args.ser, args.n, args.baxy, args.pedidos)


if __name__ == "__main__":
    main()
