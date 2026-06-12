"""Patch v2 del augment de livekit-wakeword (venv .venv_livekit).

Mismo patrón que _patch_feature_extractor_gpu.py: parchea EN EL VENV
(idempotente, --revert, .bak). Si se recrea .venv_livekit, re-aplicar
(gotcha conocido, como el patch de espeak — ver CLAUDE.md).

HISTORIA MEDIDA (2026-06-11, doc wake_ruido_fondo_2026-06-11.md):
- Modelo original (backgrounds VACÍO): limpio 0.832 / voces-snr5 0.000 /
  confusables 66%.
- Retrain v1 (backgrounds + patch parcial SNR-activo + negativos al final,
  PERO conservando el encadenado de rondas): el ruido se APILA (r2 lee r1
  que lee r0) → SNR efectivo ~-5 dB, imposible de aprender → limpio
  0.832→0.370 (es 0/20). FAIL.

DISEÑO v2 — multi-condición SIN compounding (estilo Amazon/Alexa
arXiv:1808.00563: limpio + corrupto a varios SIR):
  r0 = limpio ALINEADO (EQ/RIR sí, sin fondo)  → competencia base
  r1 = fondo a SNR uniforme(5, 15) dB          → caso moderado
  r2 = fondo a SNR uniforme(0, 10) dB          → caso película/voces
Cada ronda parte SIEMPRE del clip ORIGINAL. Se alinea PRIMERO (positivos y
negativos al FINAL — centrar negativos enseña el atajo posicional
"contenido al final = wake": 66-71% fake-fires medidos con confusables
held-out) y se mezcla DESPUÉS (el fondo cubre la ventana completa).
Además: potencia de señal sobre muestras ACTIVAS (contar los ceros del
padding subestima la frase ~5-7 dB) y pick de fondo balanceado por
categoría music/speech/noise (uniforme por archivo daba 15% speech).

Uso:
  .venv_livekit/Scripts/python.exe scripts/_patch_livekit_augment_noise.py
  .venv_livekit/Scripts/python.exe scripts/_patch_livekit_augment_noise.py --revert
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = (ROOT / ".venv_livekit" / "Lib" / "site-packages" / "livekit"
          / "wakeword" / "data" / "augment.py")
BAK = TARGET.with_suffix(".py.orig_pre_noise_patch")
MARKER = "[gemma4 noise-patch v2]"

OLD_INIT = """        self.background_files = self._collect_wavs(background_paths)
        self.rir_files = self._collect_wavs(rir_paths)"""

NEW_INIT = """        self.background_files = self._collect_wavs(background_paths)
        self.rir_files = self._collect_wavs(rir_paths)
        # [gemma4 noise-patch v2] grupos por categoria (music/speech/noise):
        # eleccion uniforme POR ARCHIVO sesga hacia la categoria con mas
        # archivos (noise 61%) y deja speech (el caso de campo) en 15%.
        _groups: dict[str, list[Path]] = {}
        for _f in self.background_files:
            _parts = _f.parts
            _cat = _f.parent.name
            if "backgrounds" in _parts:
                _i = _parts.index("backgrounds")
                if _i + 1 < len(_parts) - 1:
                    _cat = _parts[_i + 1]
            _groups.setdefault(_cat, []).append(_f)
        self._bg_groups = [v for v in _groups.values() if v]"""

OLD_POWER = """        snr_db = random.uniform(*snr_db_range)
        audio_power = np.mean(audio**2) + 1e-8"""

NEW_POWER = """        snr_db = random.uniform(*snr_db_range)
        # [gemma4 noise-patch v2] potencia sobre muestras ACTIVAS: la ventana
        # alineada es ~50-70% ceros y contarlos subestima la frase ~5-7 dB
        # (el SNR nominal queda mucho mas suave que lo pedido).
        _peak = float(np.max(np.abs(audio))) + 1e-9
        _active = audio[np.abs(audio) > 0.02 * _peak]
        audio_power = (float(np.mean(_active**2)) if _active.size
                       else float(np.mean(audio**2))) + 1e-8"""

OLD_PICK = "        bg_path = random.choice(self.background_files)"

NEW_PICK = """        _groups = getattr(self, "_bg_groups", None)  # [gemma4 noise-patch v2]
        bg_path = (random.choice(random.choice(_groups)) if _groups
                   else random.choice(self.background_files))"""

OLD_AUGDIR = '''def _augment_directory(
    clip_dir: Path,
    augmentor: AudioAugmentor,
    is_positive: bool,
    target_duration_s: float = 2.0,
    sample_rate: int = 16000,
    round_idx: int = 0,
) -> None:
    """Augment all WAV files in a directory.

    Round 0 reads the original TTS clips (``clip_000000.wav``).
    Subsequent rounds read the previous round's output so that
    augmentation compounds (stacks) progressively.  Every round
    writes to its own file (``clip_000000_r0.wav``, ``_r1.wav``, …)
    so the originals are always preserved.
    """
    import re

    import soundfile as sf
    from tqdm import tqdm

    target_length = int(target_duration_s * sample_rate)

    if round_idx == 0:
        # Round 0: read original TTS clips
        _src_re = re.compile(r"^clip_\\d{6}\\.wav$")
    else:
        # Round N: read previous round's output
        _src_re = re.compile(rf"^clip_\\d{{6}}_r{round_idx - 1}\\.wav$")

    wav_files = sorted(p for p in clip_dir.glob("*.wav") if _src_re.match(p.name))

    for wav_path in tqdm(wav_files, desc=f"Augmenting {clip_dir.name} r{round_idx}", unit="clip"):
        audio, sr = sf.read(str(wav_path))
        if audio.ndim > 1:
            audio = audio[:, 0]
        audio = audio.astype(np.float32)

        # Apply per-sample augmentations
        audio = augmentor.augment_clip(audio)

        # Apply RIR
        audio = augmentor.apply_rir(audio)

        # Mix with background
        audio = augmentor.mix_with_background(audio)

        # Align to target duration only on round 0 (raw TTS clips vary in
        # length).  Later rounds already have the correct duration.
        if round_idx == 0:
            if is_positive:
                audio = align_clip_to_end(audio, target_length)
            else:
                # Center-pad or crop negatives
                if len(audio) < target_length:
                    padded = np.zeros(target_length, dtype=np.float32)
                    start = (target_length - len(audio)) // 2
                    padded[start : start + len(audio)] = audio
                    audio = padded
                elif len(audio) > target_length:
                    start = (len(audio) - target_length) // 2
                    audio = audio[start : start + target_length]

        # Derive output name from the original stem (strip any _rN suffix)
        orig_stem = re.sub(r"_r\\d+$", "", wav_path.stem)
        out_path = wav_path.with_name(f"{orig_stem}_r{round_idx}.wav")
        sf.write(str(out_path), audio, sample_rate)'''

NEW_AUGDIR = '''def _augment_directory(
    clip_dir: Path,
    augmentor: AudioAugmentor,
    is_positive: bool,
    target_duration_s: float = 2.0,
    sample_rate: int = 16000,
    round_idx: int = 0,
) -> None:
    """[gemma4 noise-patch v2] Multi-condicion por ronda, SIN compounding.

    El diseno original encadenaba rondas (r1 lee r0, r2 lee r1): el ruido se
    APILA y el SNR efectivo de la frase queda incontrolable (~-5 dB en r2)
    -> el modelo no aprende ni el caso limpio (recall 0.832->0.370 medido).
    Curriculum multi-condicion en su lugar (estilo arXiv:1808.00563):
      r0 = limpio alineado (EQ/RIR si, sin fondo)
      r1 = fondo a SNR uniforme(5, 15) dB
      r2 = fondo a SNR uniforme(0, 10) dB
    Cada ronda parte SIEMPRE del clip ORIGINAL; se alinea PRIMERO (positivos
    Y negativos al FINAL: centrar negativos ensena el atajo posicional
    "contenido al final = wake" — 66-71% fake-fires medidos) y se mezcla
    DESPUES (el fondo cubre la ventana completa, como la vida real).
    """
    import re

    import soundfile as sf
    from tqdm import tqdm

    target_length = int(target_duration_s * sample_rate)
    _src_re = re.compile(r"^clip_\\d{6}\\.wav$")
    wav_files = sorted(p for p in clip_dir.glob("*.wav") if _src_re.match(p.name))

    snr_by_round = {1: (5.0, 15.0), 2: (0.0, 10.0)}

    for wav_path in tqdm(wav_files, desc=f"Augmenting {clip_dir.name} r{round_idx}", unit="clip"):
        audio, sr = sf.read(str(wav_path))
        if audio.ndim > 1:
            audio = audio[:, 0]
        audio = audio.astype(np.float32)

        audio = augmentor.augment_clip(audio)
        audio = augmentor.apply_rir(audio)
        # alinear ANTES de mezclar: el fondo debe cubrir la ventana entera.
        audio = align_clip_to_end(audio, target_length)
        _rng = snr_by_round.get(round_idx)
        if _rng is not None:
            audio = augmentor.mix_with_background(audio, snr_db_range=_rng)

        out_path = wav_path.with_name(f"{wav_path.stem}_r{round_idx}.wav")
        sf.write(str(out_path), audio, sample_rate)'''

PATCHES = [
    (OLD_INIT, NEW_INIT),
    (OLD_POWER, NEW_POWER),
    (OLD_PICK, NEW_PICK),
    (OLD_AUGDIR, NEW_AUGDIR),
]


def apply() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("ya parcheado v2 (idempotente, no-op)")
        return 0
    if not BAK.exists():
        shutil.copy2(TARGET, BAK)
    missing = [old for old, _ in PATCHES if old not in text]
    if missing:
        print("FALLO: no encuentro estos bloques (¿version distinta del paquete?"
              " ¿quedo el patch v1 aplicado? correr --revert primero):")
        for m in missing:
            print("---\n" + m[:300])
        return 1
    for old, new in PATCHES:
        text = text.replace(old, new, 1)
    TARGET.write_text(text, encoding="utf-8")
    print(f"patch v2 aplicado a {TARGET} (backup en {BAK.name})")
    return 0


def revert() -> int:
    if BAK.exists():
        shutil.copy2(BAK, TARGET)
        print("revertido desde", BAK.name)
        return 0
    print("no hay backup; nada que revertir")
    return 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--revert", action="store_true")
    sys.exit(revert() if ap.parse_args().revert else apply())
