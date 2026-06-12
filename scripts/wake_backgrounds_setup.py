"""Backgrounds de entrenamiento del wake-word: descarga MUSAN + holdout de eval.

POR QUÉ EXISTE (2026-06-11): baxy.onnx se entrenó con data/backgrounds VACÍO.
El `livekit-wakeword setup` intenta bajar MUSAN-noise de HF y si la descarga
muere solo emite un WARNING — el training siguió sin ruido y el modelo colapsó
con CUALQUIER audio de fondo (recall 0.000 a SNR 10/5/0 medido con
scripts/wake_noise_baseline_eval.py; en limpio 0.820).

Qué hace:
  1. Descarga MUSAN COMPLETO (music + speech + noise; CC/USA-PD) a
     data/backgrounds. Música y voz son CLAVE: el escenario real del fallo es
     "película/serie/otras voces" y Amazon midió -30-45% FRR bajo playback
     mezclando música+TV en train (arXiv:1808.00563). Fuentes:
       - noise: mirror HF `FluidInference/musan` (solo trae el audio de noise;
         music/speech del mirror son solo LICENSE/ANNOTATIONS — verificado).
       - music + speech: canónico OpenSLR-17 musan.tar.gz (~11 GB), se
         extraen esas dos categorías del tar.
  2. HOLDOUT de eval: mueve 1 de cada 12 archivos de music/ y speech/ a
     data/wake_universal_eval/noise_heldout/<cat>/ — esos archivos NO se usan
     en training, así el eval de ruido mide generalización, no memoria.
  3. Verifica el resultado (conteo y horas por categoría) y FALLA fuerte si
     falta una categoría (nada de degradación silenciosa otra vez).

Uso: python scripts/wake_backgrounds_setup.py [--skip-download]
"""
from __future__ import annotations

import argparse
import sys
import tarfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
BG_DIR = ROOT / "data" / "backgrounds"
TAR_PATH = ROOT / "data" / "musan.tar.gz"
HELDOUT_DIR = ROOT / "data" / "wake_universal_eval" / "noise_heldout"
HOLDOUT_EVERY = 12  # 1 de cada 12 → ~8% por categoría para eval
# Submuestreo de music/speech del tar: el `generate` de livekit-wakeword
# PRE-CARGA todos los backgrounds a RAM como float32 (~2 bytes/muestra →
# MUSAN completo ≈ 25 GB float32, inviable). Mitad de music y mitad de
# speech + noise completo ≈ 56 h ≈ 13 GB float32 durante generate: seguro
# en 32 GB y diversidad de sobra para 3 rondas de augment.
TAKE_EVERY = {"music": 2, "speech": 2}


def download_noise_hf() -> None:
    from huggingface_hub import snapshot_download
    snapshot_download(
        repo_id="FluidInference/musan", repo_type="dataset",
        allow_patterns="**/*.wav", local_dir=str(BG_DIR), max_workers=8,
    )


def extract_music_speech_from_tar() -> None:
    """Extrae music/ y speech/ (submuestreados) del musan.tar.gz canónico.
    El tar es `musan/<cat>/<sub>/<file>.wav`; aplanamos a BG_DIR/<cat>/."""
    assert TAR_PATH.exists(), f"falta {TAR_PATH} (curl openslr/17 primero)"
    counters: dict[str, int] = {"music": 0, "speech": 0}
    extracted = {"music": 0, "speech": 0}
    with tarfile.open(TAR_PATH, "r:gz") as tf:
        for member in tf:
            parts = Path(member.name).parts
            if len(parts) < 3 or parts[0] != "musan" or not member.isfile():
                continue
            cat = parts[1]
            if cat not in TAKE_EVERY or not member.name.endswith(".wav"):
                continue
            idx = counters[cat]
            counters[cat] += 1
            if idx % TAKE_EVERY[cat] != 0:
                continue
            dest = BG_DIR / cat / Path(member.name).name
            if dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            src = tf.extractfile(member)
            if src is None:
                continue
            with open(dest, "wb") as out:
                out.write(src.read())
            extracted[cat] += 1
    print(f"extraídos del tar: music={extracted['music']} "
          f"speech={extracted['speech']} (1 de cada {TAKE_EVERY})")


def carve_holdout() -> None:
    for cat in ("music", "speech"):
        src_files = sorted((BG_DIR / cat).glob("**/*.wav"))
        dest = HELDOUT_DIR / cat
        if list(dest.glob("*.wav")):
            print(f"holdout {cat}: ya existe, no se re-mueve")
            continue
        dest.mkdir(parents=True, exist_ok=True)
        moved = 0
        for i, f in enumerate(src_files):
            if i % HOLDOUT_EVERY == 0:
                f.rename(dest / f.name)
                moved += 1
        print(f"holdout {cat}: {moved} archivos movidos a {dest}")


def verify() -> int:
    import soundfile as sf
    ok = True
    for cat in ("music", "speech", "noise"):
        files = sorted((BG_DIR / cat).glob("**/*.wav"))
        secs = 0.0
        for f in files[:2000]:
            try:
                info = sf.info(str(f))
                secs += info.frames / info.samplerate
            except Exception:
                pass
        hours = secs / 3600
        status = "OK" if files else "FALTA"
        if not files:
            ok = False
        print(f"  {cat:7} {len(files):5} wavs  {hours:6.1f} h  {status}")
    for cat in ("music", "speech"):
        n = len(list((HELDOUT_DIR / cat).glob("*.wav")))
        print(f"  heldout/{cat}: {n} wavs")
        if n == 0:
            ok = False
    if not ok:
        print("FALLO: falta una categoría — NO entrenar con esto.")
        return 1
    print("backgrounds VERIFICADOS para training.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-download", action="store_true",
                    help="no baja el noise de HF (ya presente)")
    ap.add_argument("--skip-tar", action="store_true",
                    help="no extrae music/speech del musan.tar.gz")
    args = ap.parse_args()
    if not args.skip_download:
        download_noise_hf()
    if not args.skip_tar:
        extract_music_speech_from_tar()
    carve_holdout()
    return verify()


if __name__ == "__main__":
    raise SystemExit(main())
