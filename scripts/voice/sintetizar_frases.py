"""Synthetic set for scripts/voice/medir_hotwords.py: every phrase of frases_hotwords.json in 5 Spanish voices (BAXY's
Supertonic voice and the OneCore Raul, Sabina, Pablo and Laura), the English lines also in Zira; clean and with pink
noise at 10 dB SNR. Nothing is played: every voice writes to a file. A Spanish voice reads «dicho» (how a Chilean says
the name) or speech_text.spoken(texto). The set stays outside the repository.

    <mind-runtime python> -X utf8 scripts/voice/sintetizar_frases.py OUT_DIR
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import wave
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

ROOT = Path(sys.argv[1])
WORKTREE = Path(__file__).resolve().parents[2]
PHRASES = Path(__file__).with_name("frases_hotwords.json")
sys.path.insert(0, str(WORKTREE / "src"))
from baxy_mind.speech_text import spoken  # noqa: E402

ONECORE = ["Raul", "Sabina", "Pablo", "Laura"]
SNR_DB = 10.0
RATE = 16000


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        rate, width, channels = w.getframerate(), w.getsampwidth(), w.getnchannels()
        data = w.readframes(w.getnframes())
    assert width == 2, (path, width)
    x = np.frombuffer(data, "<i2").astype(np.float32) / 32768
    if channels > 1:
        x = x.reshape(-1, channels).mean(axis=1)
    return to16k(x, rate)


def to16k(x: np.ndarray, rate: int) -> np.ndarray:
    if rate != RATE:
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


def pink(n: int, rng: np.random.Generator) -> np.ndarray:
    spectrum = np.fft.rfft(rng.standard_normal(n))
    f = np.arange(len(spectrum))
    f[0] = 1
    y = np.fft.irfft(spectrum / np.sqrt(f), n)
    return (y / np.std(y)).astype(np.float32)


def finish(x: np.ndarray) -> np.ndarray:
    x = x / max(1e-6, float(np.max(np.abs(x)))) * 0.3
    pad = np.zeros(int(0.3 * RATE), np.float32)
    return np.concatenate([pad, x.astype(np.float32), pad])


def ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def main() -> None:
    phrases = json.loads(PHRASES.read_text(encoding="utf-8"))["frases"]
    raw = ROOT / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    jobs = []  # (voice, phrase, raw path)
    for p in phrases:
        said = p.get("dicho") or spoken(p["texto"])
        for v in ONECORE:
            jobs.append((v, p, raw / v / f"{p['id']}.wav", said))
        if p.get("lang") == "en":
            jobs.append(("Zira", p, raw / "Zira" / f"{p['id']}.wav", p["texto"]))
    # OneCore (WinRT) and Zira (SAPI desktop) in one PowerShell, to files only.
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
        "$st = Await ($s.SynthesizeTextToStreamAsync($text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream]); "
        "$n = [uint32]$st.Size; $r = New-Object Windows.Storage.Streams.DataReader($st.GetInputStreamAt(0)); "
        "$null = Await ($r.LoadAsync($n)) ([uint32]); $b = New-Object byte[] $n; $r.ReadBytes($b); "
        "[System.IO.File]::WriteAllBytes($out, $b) }",
    ]
    for v, _p, out, said in jobs:
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.is_file():
            continue
        if v == "Zira":
            lines.append(f"$z.SetOutputToWaveFile({ps_quote(str(out))}); $z.Speak({ps_quote(said)}); $z.SetOutputToNull()")
        else:
            lines.append(f"One {ps_quote(v)} {ps_quote(said)} {ps_quote(str(out))}")
    script = ROOT / "onecore.ps1"
    script.write_text("\ufeff" + "\n".join(lines) + "\n$z.Dispose()\n", encoding="utf-8")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)], check=True)

    # Supertonic: BAXY's own voice as the product synthesizes it (voice_output.Speech._synthesize), to memory.
    # Calidad PC 2026-10-25: this took the recipe's speed alone, without its «shift» (pitch and formants, by
    # resampling) and the speed by the phrase's length (_speed): another voice than BAXY's. The cache folder is new,
    # so a set made before is not mixed with it.
    os.environ.setdefault("BAXY_RENEW_TTS_DIR",
                          str(Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime/assets/voice/baxy-supertonic"))
    from baxy_mind.voice_output import Speech
    speech = Speech(lambda _speaking: None, lambda *_spoken: None)
    speech._ready.wait()
    if speech.failure:
        raise SystemExit(f"the voice did not load: {speech.failure}")
    manifest = []
    try:
        for p in phrases:
            said = p.get("dicho") or spoken(p["texto"])
            out = raw / "Supertonic-voz" / f"{p['id']}.npy"
            if not out.is_file():
                out.parent.mkdir(parents=True, exist_ok=True)
                np.save(out, to16k(speech._synthesize(said, pause=False), speech.rate))
            jobs.append(("Supertonic", p, out, said))
    finally:
        speech.close()

    rng_seed = 0
    for v, p, src, said in jobs:
        x = np.load(src) if src.suffix == ".npy" else read_wav(src)
        x = finish(x)
        for cond in ("limpio", "ruido"):
            y = x
            if cond == "ruido":
                rng_seed += 1
                rng = np.random.default_rng(rng_seed)
                noise = pink(len(x), rng)
                speech_rms = float(np.sqrt(np.mean(x[np.abs(x) > 0.01] ** 2)))
                y = x + noise * speech_rms / (10 ** (SNR_DB / 20))
            dest = ROOT / "wav" / cond / v / f"{p['id']}.wav"
            write_wav(dest, y)
            manifest.append({"wav": str(dest), "id": p["id"], "voz": v, "cond": cond, "texto": p["texto"],
                             "dicho": said, "clase": p["clase"], "nombre": p.get("nombre"),
                             "acepta": p.get("acepta"), "lang": p.get("lang", "es")})
    (ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=0), encoding="utf-8")
    print(len(manifest), "utterances")


if __name__ == "__main__":
    main()
