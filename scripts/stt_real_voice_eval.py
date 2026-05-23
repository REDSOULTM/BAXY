"""A/B de STT sobre VOZ HUMANA REAL (la métrica que decide — CLAUDE.md mandato #3).

Compara, sobre los MISMOS audios reales:
  - whisper      : Whisper-small int8 (motor de prod actual) + corrector
  - parakeet     : Parakeet-TDT-0.6b-v3 int8 greedy (motor candidato), crudo
  - parakeet+corr: Parakeet greedy + corrector fonético (la apuesta del plan)

Fuentes (separadas en el reporte para detectar overfit por subgrupo):
  - RED      : 84 clips guiados de RED (data/stt_eval/real_mic, 2 tandas).
               Tienen `expected` = ground-truth exacto -> WER + Entity-Recall.
  - TERCEROS : 180 clips humanos (FLEURS es_419 + chilenos, data/stt_eval/real_es).
               NO son RED -> guardia anti-overfit. Solo WER + non-regression
               (no tienen apps inglesas que medir como entidad).

Métricas:
  - WER (Levenshtein a nivel palabra, normalizado).
  - Entity-Recall: ¿la entidad clave (app/artista en inglés) sobrevive en la
    salida? Es lo que de verdad decide si el comando se ejecuta. Con Wilson CI
    al 95% (honestidad estadística: n es chico, el punto solo no alcanza).
  - non-regression: en TERCEROS, ¿el corrector EMPEORA algún clip? (debe ser ~0).

Uso:
    python scripts/stt_real_voice_eval.py                  # las 3 configs, todo
    python scripts/stt_real_voice_eval.py --engines parakeet,parakeet_corr
    python scripts/stt_real_voice_eval.py --red-only       # solo clips de RED
    python scripts/stt_real_voice_eval.py --threshold 70   # override umbral corr
"""
from __future__ import annotations

import argparse
import math
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SR = 16000
MD = ROOT / "data" / "stt_eval" / "sherpa" / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
REAL_MIC = ROOT / "data" / "stt_eval" / "real_mic"
REAL_ES = ROOT / "data" / "stt_eval" / "real_es"

# Las 2 tandas guiadas buenas (el resto del manifest real_mic son pruebas sueltas).
RED_GOOD_STAMPS = {"20260523_015719", "20260523_020155"}


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\sáéíóúüñ]", " ", s)
    return " ".join(s.split())


def _wer(ref: str, hyp: str) -> float:
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


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Intervalo de confianza de Wilson para una proporción (k éxitos de n).
    Devuelve (p, low, high). Honestidad estadística con n chico (CLAUDE.md #3)."""
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (p, max(0.0, centre - half), min(1.0, centre + half))


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------
def _strip_wake(text: str) -> str:
    return re.sub(r"^\s*(hey\s+)?(gemma|jarvis)[\s,.!]*", "", text,
                  flags=re.IGNORECASE).strip()


def _key_entity(expected: str) -> str | None:
    """Entidad clave a preservar = nombre propio (token capitalizado o multi-word
    en inglés) en el comando. Heurística: el último run de tokens Capitalizados.
    Devuelve la entidad normalizada, o None si el comando es español puro."""
    # tokens con mayúscula inicial que NO sean la 1ª palabra (verbo) ni stopwords
    toks = expected.split()
    caps = []
    run = []
    for i, t in enumerate(toks):
        bare = re.sub(r"[^\wáéíóúüñ]", "", t)
        if i > 0 and bare[:1].isupper():
            run.append(bare)
        else:
            if run:
                caps.append(" ".join(run)); run = []
    if run:
        caps.append(" ".join(run))
    if not caps:
        return None
    return _norm(caps[-1])  # la última entidad propia (app/artista/título)


def load_red() -> list[tuple[Path, str, str | None]]:
    """84 clips guiados de RED. (wav, expected, key_entity)."""
    p = REAL_MIC / "manifest.tsv"
    out = []
    for line in p.read_text(encoding="utf-8").splitlines()[1:]:
        c = line.split("\t")
        if len(c) < 6 or c[5] not in RED_GOOD_STAMPS:
            continue
        wav = REAL_MIC / c[0]
        expected = c[1].strip()
        if not wav.exists() or not expected:
            continue
        out.append((wav, expected, _key_entity(expected)))
    return out


def load_terceros() -> list[tuple[Path, str, None]]:
    """180 clips humanos de terceros (anti-overfit). (wav, ref, None)."""
    out = []
    for mf in ("manifest.tsv", "manifest_cl.tsv"):
        p = REAL_ES / mf
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines()[1:]:
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            wav = REAL_ES / parts[0]
            if wav.exists():
                out.append((wav, parts[1].strip(), None))
    return out


def _read_wav_16k(path: Path) -> np.ndarray:
    import scipy.io.wavfile as wavf
    sr, a = wavf.read(str(path))
    if a.ndim > 1:
        a = a[:, 0]
    a = a.astype(np.float32)
    if a.dtype != np.float32 or a.max() > 1.5:
        a = a / 32768.0
    if sr != SR:
        from math import gcd
        import scipy.signal
        g = gcd(int(sr), SR)
        a = scipy.signal.resample_poly(a, SR // g, int(sr) // g).astype(np.float32)
    return a


# ---------------------------------------------------------------------------
# Motores
# ---------------------------------------------------------------------------
def build_parakeet():
    import sherpa_onnx
    return sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(MD / "encoder.int8.onnx"), decoder=str(MD / "decoder.int8.onnx"),
        joiner=str(MD / "joiner.int8.onnx"), tokens=str(MD / "tokens.txt"),
        num_threads=4, model_type="nemo_transducer", decoding_method="greedy_search",
    )


def parakeet_transcribe(rec, audio_f32: np.ndarray) -> str:
    s = rec.create_stream()
    s.accept_waveform(SR, audio_f32)
    rec.decode_stream(s)
    return s.result.text.strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engines", default="whisper,parakeet,parakeet_corr",
                     help="coma-separado: whisper,parakeet,parakeet_corr")
    ap.add_argument("--red-only", action="store_true")
    ap.add_argument("--terceros-only", action="store_true")
    ap.add_argument("--threshold", type=int, default=None,
                     help="override umbral de texto del corrector")
    ap.add_argument("--limit", type=int, default=0, help="limitar N clips por fuente (rápido)")
    ap.add_argument("--discovery", action="store_true",
                     help="inventario con apps instaladas (realista en prod)")
    args = ap.parse_args()

    engines = [e.strip() for e in args.engines.split(",") if e.strip()]

    red = [] if args.terceros_only else load_red()
    ter = [] if args.red_only else load_terceros()
    if args.limit:
        red, ter = red[:args.limit], ter[:args.limit]

    # Guardia de audio: descartar clips SILENCIOSOS/corruptos (los FLEURS viejos
    # eran int16 max=1 = silencio, inflaban el WER a 0.68 falsamente). Medir
    # contra audio inexistente no es honesto (CLAUDE.md #3).
    def _has_audio(wav: Path) -> bool:
        import scipy.io.wavfile as wavf
        try:
            sr, a = wavf.read(str(wav))
            if a.ndim > 1:
                a = a[:, 0]
            return float(np.max(np.abs(a.astype(np.float32)))) > 2.0
        except Exception:
            return False

    red_n0, ter_n0 = len(red), len(ter)
    red = [r for r in red if _has_audio(r[0])]
    ter = [t for t in ter if _has_audio(t[0])]
    drop = (red_n0 - len(red)) + (ter_n0 - len(ter))
    if drop:
        print(f"  (descartados {drop} clips silenciosos/corruptos)")
    print(f"Clips: RED={len(red)}  TERCEROS={len(ter)}  motores={engines}\n")

    # --- VAD trim (como prod) ---
    from gemma4_agent.voice.vad import SileroVAD
    vad = SileroVAD(); vad.load()

    def trim(a_f32):
        try:
            vad.reset()
            i16 = np.clip(a_f32 * 32768.0, -32768, 32767).astype(np.int16)
            t = vad.trim_silence(i16)
            if t is not None and t.size >= int(0.08 * SR):
                return t.astype(np.float32) / 32768.0
        except Exception:
            pass
        return a_f32

    # --- preparar motores ---
    rec_para = None
    stt_whisper = None
    corr = None
    if "parakeet" in engines or "parakeet_corr" in engines:
        print("Cargando Parakeet...", flush=True)
        t0 = time.time(); rec_para = build_parakeet()
        print(f"  Parakeet listo en {time.time()-t0:.1f}s")
    if "parakeet_corr" in engines:
        from gemma4_agent.voice.corrector import FuzzyCorrector
        from gemma4_agent.voice.inventory import get_inventory
        inv = get_inventory(include_discovery=args.discovery)
        kw = {"threshold": args.threshold} if args.threshold else {}
        corr = FuzzyCorrector(inv, **kw)
    if "whisper" in engines:
        print("Cargando Whisper-small...", flush=True)
        from gemma4_agent.voice.stt import STT
        from gemma4_agent.voice.inventory import get_inventory, build_initial_prompt, build_hotwords
        inv = get_inventory(include_discovery=args.discovery)
        _wprompt = build_initial_prompt(inv, lang="es")
        _whot = build_hotwords(inv)
        t0 = time.time(); stt_whisper = STT(); stt_whisper.load()
        print(f"  Whisper listo en {time.time()-t0:.1f}s")

    def run_engine(name, audio_f32):
        if name == "parakeet":
            return parakeet_transcribe(rec_para, audio_f32)
        if name == "parakeet_corr":
            raw = parakeet_transcribe(rec_para, audio_f32)
            return corr.correct(_strip_wake(raw))
        if name == "whisper":
            raw = stt_whisper.transcribe(
                np.clip(audio_f32 * 32768, -32768, 32767).astype(np.int16),
                initial_prompt=_wprompt, language="es", hotwords=_whot)
            return corr.correct(_strip_wake(raw)) if corr else _strip_wake(raw)
        raise ValueError(name)

    # acumuladores: por (fuente, motor) -> [wer_sum, n, ent_hit, ent_total]
    from collections import defaultdict
    acc = defaultdict(lambda: [0.0, 0, 0, 0])
    latency = defaultdict(list)
    ent_fail = defaultdict(list)   # (fuente,motor) -> [(entidad, expected, hyp)]
    examples = defaultdict(list)   # muestras para inspección

    for src_name, data in (("RED", red), ("TERCEROS", ter)):
        for idx, (wav, ref, entity) in enumerate(data):
            audio = trim(_read_wav_16k(wav))
            ref_clean = _strip_wake(ref)
            for eng in engines:
                t0 = time.time()
                hyp = run_engine(eng, audio)
                latency[(src_name, eng)].append((time.time() - t0) * 1000)
                a = acc[(src_name, eng)]
                a[0] += _wer(ref_clean, hyp); a[1] += 1
                if entity:
                    a[3] += 1
                    if entity in _norm(hyp):
                        a[2] += 1
                    else:
                        ent_fail[(src_name, eng)].append((entity, ref_clean, hyp))
                if len(examples[(src_name, eng)]) < 8:
                    examples[(src_name, eng)].append((ref_clean, hyp))
            if (idx + 1) % 20 == 0:
                print(f"  {src_name} ...{idx+1}/{len(data)}", flush=True)

    # --- reporte ---
    print("\n" + "=" * 64)
    print("RESULTADOS — VOZ REAL")
    print("=" * 64)
    for src_name in ("RED", "TERCEROS"):
        rows = [(eng, acc[(src_name, eng)]) for eng in engines if acc[(src_name, eng)][1]]
        if not rows:
            continue
        print(f"\n### {src_name} (n={rows[0][1][1]})")
        print(f"  {'motor':16} {'WER':>8} {'EntRecall (Wilson 95%)':>30} {'p50ms':>7}")
        for eng, a in rows:
            wer = a[0] / a[1]
            lat = sorted(latency[(src_name, eng)])
            p50 = lat[len(lat) // 2] if lat else 0
            if a[3]:
                p, lo, hi = _wilson(a[2], a[3])
                ent = f"{a[2]}/{a[3]}={p:.0%} [{lo:.0%},{hi:.0%}]"
            else:
                ent = "—"
            print(f"  {eng:16} {wer:>8.4f} {ent:>30} {p50:>7.0f}")

    # entidades no recuperadas (lo que falta)
    for src_name in ("RED",):
        for eng in engines:
            fails = ent_fail[(src_name, eng)]
            if fails:
                print(f"\n  [{src_name}/{eng}] entidades NO recuperadas ({len(fails)}):")
                for ent, ref, hyp in fails[:20]:
                    print(f"     [{ent}] {ref[:40]!r} -> {hyp[:45]!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
