"""Eval-set sintético multi-voz para STT Spanglish (comandos con apps en inglés).

Genera comandos con nombres propios EN INGLÉS (Steam, Spotify, Chrome, Disney+,
etc.) sobre varias voces Piper en español (acentos ES/MX/AR), los pasa por el
PIPELINE REAL de STT (VAD trim -> Whisper-small -> strip wake -> corrector) y
mide:
  - WER (vs el texto exacto que se sintetizó = ground truth perfecto)
  - Entity-Recall: ¿el nombre propio en inglés sobrevivió en la salida?
    (la métrica que de verdad importa para ejecutar el comando)

Compara DOS configs sobre los MISMOS audios:
  - baseline : sin corrector (solo strip wake)
  - tier1    : con corrector fonético + stop-list (lo aplicado)

Es sintético (Piper), válido para EVAL (no para training). Ground truth = el
texto que pedimos sintetizar -> alineación perfecta, cero etiquetado manual.
(compass research R13; mandato #3: medir con números confiables.)

Uso:
    python scripts/stt_synthetic_eval.py            # genera (si falta) + evalúa
    python scripts/stt_synthetic_eval.py --regen    # re-generar audios
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.voice.corrector import FuzzyCorrector
from gemma4_agent.voice.inventory import build_initial_prompt, build_hotwords, get_inventory
from gemma4_agent.voice.stt import STT, SAMPLE_RATE
from gemma4_agent.voice.vad import SileroVAD

VOICES_DIR = ROOT / "data" / "stt_eval" / "voices"
AUDIO_DIR = ROOT / "data" / "stt_eval" / "audio"

# Comandos Spanglish: generados por PLANTILLA (1000+, diversos) en
# scripts/stt_eval_commands.py. (texto, entidad_inglesa_clave|None).
from stt_eval_commands import build_commands as _build_commands

# N comandos sintéticos (env STT_EVAL_N, default 1000). Cada uno se sintetiza
# con UNA voz rotada entre las disponibles -> diversidad de comando Y voz sin
# explotar el tiempo (1000 clips vs 6000).
import os as _os
N_SYNTH = int(_os.environ.get("STT_EVAL_N", "1000"))
COMMANDS = _build_commands(seed=0, target=N_SYNTH)


def _synth(voice, text):
    from piper.config import SynthesisConfig
    cfg = SynthesisConfig(length_scale=1.0, noise_scale=0.667)
    chunks = []
    for c in voice.synthesize(text, syn_config=cfg):
        chunks.append(c.audio_int16_bytes if hasattr(c, "audio_int16_bytes") else c)
    audio = np.frombuffer(b"".join(chunks), dtype=np.int16)
    return audio, int(voice.config.sample_rate)


def _resample(audio, sr_in, sr_out):
    if sr_in == sr_out:
        return audio
    from math import gcd
    import scipy.signal
    g = gcd(sr_in, sr_out)
    out = scipy.signal.resample_poly(audio.astype(np.float32), sr_out // g, sr_in // g)
    return np.clip(out, -32768, 32767).astype(np.int16)


def generate(regen=False):
    """Sintetiza 1 voz ROTADA por comando (N clips, no N×voces). Agrupa por voz
    para cargar cada modelo Piper una sola vez."""
    import scipy.io.wavfile as wavf
    from piper import PiperVoice
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    voices = sorted(VOICES_DIR.glob("*.onnx"))
    if not voices:
        return []
    # Asignar voz por índice de comando (round-robin) -> diversidad de voz.
    by_voice: dict[int, list[int]] = {vi: [] for vi in range(len(voices))}
    for ci in range(len(COMMANDS)):
        by_voice[ci % len(voices)].append(ci)

    manifest = [None] * len(COMMANDS)
    for vi, vp in enumerate(voices):
        cidxs = by_voice[vi]
        if not cidxs:
            continue
        # ¿hace falta cargar la voz? (solo si algún clip falta o regen)
        need = regen or any(
            not (AUDIO_DIR / f"{vp.stem}__c{ci:04d}.wav").exists() for ci in cidxs
        )
        voice = PiperVoice.load(str(vp)) if need else None
        for ci in cidxs:
            text, entity = COMMANDS[ci]
            wav_path = AUDIO_DIR / f"{vp.stem}__c{ci:04d}.wav"
            manifest[ci] = (wav_path, text, entity)
            if wav_path.exists() and not regen:
                continue
            audio, sr = _synth(voice, text)
            audio = _resample(audio, sr, SAMPLE_RATE)
            wavf.write(str(wav_path), SAMPLE_RATE, audio)
    return [m for m in manifest if m]


def _norm(s):
    s = s.lower()
    s = re.sub(r"[^\w\sáéíóúüñ]", " ", s)
    return " ".join(s.split())


def _wer(ref, hyp):
    r, h = _norm(ref).split(), _norm(hyp).split()
    if not r:
        return 0.0 if not h else 1.0
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev = d[0]; d[0] = i
        for j in range(1, len(h) + 1):
            cur = d[j]
            cost = 0 if r[i - 1] == h[j - 1] else 1
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + cost); prev = cur
    return d[len(h)] / len(r)


def _strip_wake(text):
    return re.sub(r"^\s*(hey\s+)?gemma[\s,.!]*", "", text, flags=re.IGNORECASE).strip()


def _load_real_manifest():
    """Clips de habla HUMANA real (FLEURS + Chilean). Devuelve [(path,text,None)].
    entity=None: no medimos entity-recall en estos (no tienen apps en inglés),
    solo WER + que el corrector NO los corrompa (non-regression)."""
    real_dir = ROOT / "data" / "stt_eval" / "real_es"
    out = []
    for mf in ("manifest.tsv", "manifest_cl.tsv"):
        p = real_dir / mf
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines()[1:]:
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            wav = real_dir / parts[0]
            if wav.exists():
                out.append((wav, parts[1], None))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regen", action="store_true")
    ap.add_argument("--real-only", action="store_true")
    ap.add_argument("--limit-real", type=int, default=0,
                     help="evaluar solo N clips reales (rápido)")
    args = ap.parse_args()

    if args.real_only:
        manifest = []
    else:
        print("Generando audios sintéticos (Piper, ES/MX/AR)...")
        manifest = generate(regen=args.regen)
        print(f"  {len(manifest)} clips sintéticos")
    real = _load_real_manifest()
    if args.limit_real:
        real = real[:args.limit_real]
    print(f"  {len(real)} clips REALES (habla humana, FLEURS+Chilean)")
    manifest = manifest + real

    inv = get_inventory(include_discovery=False)
    prompt = build_initial_prompt(inv, lang="es")
    hotwords = build_hotwords(inv)
    stt = STT(); stt.load()
    vad = SileroVAD(); vad.load()
    corr = FuzzyCorrector(inv)

    # Acumuladores separados por fuente. Cada uno: wer_base, wer_t1, n,
    # ent_hit_base, ent_hit_t1, ent_total.
    import scipy.io.wavfile as wavf
    syn = [0.0, 0.0, 0, 0, 0, 0]
    rea = [0.0, 0.0, 0, 0, 0, 0]
    entity_fail = []
    real_corrupted = []  # clips reales donde tier1 EMPEORÓ vs baseline

    for idx, (wav_path, text, entity) in enumerate(manifest):
        sr, audio = wavf.read(str(wav_path))
        if audio.ndim > 1:
            audio = audio[:, 0]
        vad.reset()
        trimmed = vad.trim_silence(audio)
        if trimmed is not None and trimmed.size >= int(0.08 * SAMPLE_RATE):
            audio = trimmed
        raw = stt.transcribe(audio, initial_prompt=prompt, language="es", hotwords=hotwords)
        stripped = _strip_wake(raw)
        ref = _strip_wake(text)
        hyp_base = stripped
        hyp_t1 = corr.correct(stripped)

        is_syn = entity is not None or "__c" in wav_path.stem
        bucket = syn if is_syn else rea
        bucket[0] += _wer(ref, hyp_base)
        bucket[1] += _wer(ref, hyp_t1)
        bucket[2] += 1
        if entity:
            bucket[5] += 1
            if entity in _norm(hyp_base):
                bucket[3] += 1
            if entity in _norm(hyp_t1):
                bucket[4] += 1
            else:
                entity_fail.append((entity, text, hyp_t1))
        if not is_syn:
            # non-regression: el corrector NO debe empeorar habla real
            wb, wt = _wer(ref, hyp_base), _wer(ref, hyp_t1)
            if wt > wb + 0.001:
                real_corrupted.append((text[:50], hyp_base[:50], hyp_t1[:50]))
        if (idx + 1) % 40 == 0:
            print(f"  ...{idx+1}/{len(manifest)}", flush=True)

    print("\n================ RESULTADOS ================")
    if syn[2]:
        print(f"\nSINTÉTICO (comandos Spanglish con apps inglesas, n={syn[2]}):")
        print(f"  WER          baseline={syn[0]/syn[2]:.4f}  tier1={syn[1]/syn[2]:.4f}")
        if syn[5]:
            print(f"  Entity-Recall baseline={syn[3]}/{syn[5]}={syn[3]/syn[5]:.1%}"
                  f"  tier1={syn[4]}/{syn[5]}={syn[4]/syn[5]:.1%}  <-- la métrica clave")
    if rea[2]:
        print(f"\nREAL (habla humana FLEURS+Chilean, n={rea[2]}):")
        print(f"  WER          baseline={rea[0]/rea[2]:.4f}  tier1={rea[1]/rea[2]:.4f}")
        print(f"  Clips donde tier1 EMPEORÓ vs baseline: {len(real_corrupted)} "
              f"({len(real_corrupted)/rea[2]:.1%})  <-- non-regression")
    if entity_fail:
        print(f"\nEntidades NO recuperadas con tier1 ({len(entity_fail)}/{syn[5]}):")
        for ent, text, hyp in entity_fail[:12]:
            print(f"  [{ent}] {text[:45]!r} -> {hyp[:45]!r}")
    if real_corrupted:
        print(f"\nEjemplos de habla real corrompida por el corrector:")
        for ref, hb, ht in real_corrupted[:10]:
            print(f"  REF {ref!r}\n   base {hb!r}\n   t1   {ht!r}")


if __name__ == "__main__":
    main()
