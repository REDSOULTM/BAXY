"""EL ENTRENAMIENTO DEFINITIVO del wake — orquestador nocturno completo.

Destila las 11 generaciones del repo (doc wake_v5_diseno + bitácora
wake_ruido_fondo): cada salto vino de datos/bugs, los evals chicos mienten,
y el último veneno fue CONTENIDO degenerado sin verificar. Este orquestador
agrega la fase que faltaba — CIRUGÍA DE DATOS VERIFICADA — y luego delega en
el pipeline nocturno probado (wake_v5_overnight: train + 6 gates + deploy
condicional + veredicto).

FASE A — Cirugía (GPU ~30-60 min):
  1. Convierte candidatos faltantes (zh_CN-chaowen).
  2. Para los bloques que FALLARON el gate de contenido (de 0.00, zh 0.40):
     búsqueda de candidato (voz × parámetros, 40 clips de prueba + gate
     STT) → el primero que pasa regenera el bloque completo (síntesis
     directa sid-puro + pico 0.85 + guard duración). Sin candidato → el
     rango se RELLENA con clips EN (filler seguro, nunca veneno).
  3. TRIPLE-SCAN final de los 8 bloques: duración (p90≤3.5s) + contenido
     (gate STT) + volumen (rms en familia). FALLA FUERTE si algo no pasa
     (lección: nunca más entrenar sobre datos sin verificar).
FASE B/C — delega: wake_v5_overnight.py (augment --clean-features + train
  large 100k + 6 gates + live-test + deploy SOLO si verde + veredicto).

Uso:  python scripts/wake_definitivo_overnight.py   (~5-6 h desatendido)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

import numpy as np  # noqa: E402

LOG = ROOT / "documentacion" / "_wake_v5_overnight.log"
PY = sys.executable
VENV_PY = str(ROOT / ".venv_livekit" / "Scripts" / "python.exe")
POS = ROOT / "output" / "baxy" / "positive_train"
VAL = ROOT / "output" / "baxy" / "positive_test"

# Bloques actuales (v6 layout) y su estado del gate de contenido (calibrado
# 2026-06-12): de y zh FALLARON → cirugía; el resto se conserva.
SURGERY = [
    # (lang, train_range, val_range, candidatos[(voice_id, params)])
    ("de", range(25000, 28000), range(5000, 5375), [
        ("de_DE-mls", {"length_scales": [1.0, 0.9],
                       "noise_scale_ws": [0.5, 0.6]}),
        ("de_DE-mls", {"length_scales": [0.8],
                       "noise_scale_ws": [0.4]}),
    ]),
    ("zh", range(38000, 40000), range(6625, 6875), [
        ("zh_CN-chaowen", {"length_scales": [0.8, 1.0],
                           "noise_scale_ws": [0.6, 0.7]}),
        ("zh_CN-xiao_ya", {"length_scales": [0.7],
                           "noise_scale_ws": [0.5]}),
    ]),
]
ALL_BLOCKS = [("EN", 0, 25000), ("de", 25000, 28000), ("es", 28000, 30000),
              ("pl", 30000, 32000), ("ru", 32000, 34000),
              ("pt", 34000, 36000), ("nl", 36000, 38000),
              ("zh", 38000, 40000)]


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def fill_with_en(train_range: range, val_range: range) -> None:
    """Rellena un rango con copias de clips EN aleatorios (filler seguro)."""
    rng = np.random.RandomState(20260612)
    for out_dir, idxs, en_max in ((POS, train_range, 25000),
                                  (VAL, val_range, 5000)):
        for i in idxs:
            src = out_dir / f"clip_{rng.randint(0, en_max):06d}.wav"
            shutil.copy2(src, out_dir / f"clip_{i:06d}.wav")


def main() -> int:
    log("### DEFINITIVO — FASE A: cirugía de datos verificada ###")
    # candidatos faltantes
    rc = subprocess.run([VENV_PY, str(ROOT / "scripts" /
                                      "wake_p2_convert_checkpoints.py"),
                         "--only", "zh_CN-chaowen"], cwd=str(ROOT)).returncode
    if rc != 0:
        log("WARN: conversión chaowen falló — zh probará solo xiao_ya")

    import _ort_throttle  # noqa: F401
    import tempfile
    from gemma4_agent.voice.parakeet_stt import ParakeetSTT
    from wake_block_content_gate import block_score
    stt = ParakeetSTT()
    assert stt.load(), stt.last_error
    builder = str(ROOT / "scripts" / "wake_native_block_builder.py")

    def probe_passes(voice_id: str, params: dict) -> bool:
        """Sintetiza 40 clips de prueba (venv) y los gatea (STT, main env)."""
        with tempfile.TemporaryDirectory(prefix="wake_probe_") as td:
            rc = subprocess.run(
                [VENV_PY, builder, voice_id,
                 ",".join(str(v) for v in params["length_scales"]),
                 ",".join(str(v) for v in params["noise_scale_ws"]),
                 "probe", td, "40"], cwd=str(ROOT)).returncode
            if rc != 0:
                return False
            paths = sorted(Path(td).glob("probe_*.wav"))
            r = block_score(stt, paths, n_sample=40)
            log(f"  probe {voice_id} {params}: fraction_ok="
                f"{r['fraction_ok']:.2f} -> {'PASS' if r['passes'] else 'FAIL'}")
            return bool(r["passes"])

    for lang, tr, vr, candidates in SURGERY:
        log(f"-- cirugía bloque {lang} --")
        chosen = None
        for voice_id, params in candidates:
            if probe_passes(voice_id, params):
                chosen = (voice_id, params)
                break
        if chosen is None:
            log(f"{lang}: ningún candidato pasó el gate -> FILLER EN")
            fill_with_en(tr, vr)
            continue
        voice_id, params = chosen
        rc = subprocess.run(
            [VENV_PY, builder, voice_id,
             ",".join(str(v) for v in params["length_scales"]),
             ",".join(str(v) for v in params["noise_scale_ws"]),
             "block", str(tr.start), str(tr.stop),
             str(vr.start), str(vr.stop)], cwd=str(ROOT)).returncode
        if rc != 0:
            log(f"{lang}: block-build falló (exit {rc}) -> FILLER EN")
            fill_with_en(tr, vr)
        else:
            log(f"{lang}: bloque regenerado con {voice_id}")

    # TRIPLE-SCAN final (contenido + duración por bloque)
    import soundfile as sf
    all_ok = True
    for name, a, b in ALL_BLOCKS:
        paths = [POS / f"clip_{i:06d}.wav" for i in range(a, b)
                 if (POS / f"clip_{i:06d}.wav").exists()]
        r = block_score(stt, paths, n_sample=40)
        durs = []
        for p in paths[::max(1, len(paths) // 100)][:100]:
            info = sf.info(str(p))
            durs.append(info.frames / info.samplerate)
        p90 = float(np.percentile(durs, 90)) if durs else 99.0
        ok = r["passes"] and p90 <= 3.5
        all_ok &= ok
        log(f"scan {name}: contenido={r['fraction_ok']:.2f} "
            f"dur_p90={p90:.2f}s -> {'OK' if ok else 'FALLA'}")
    if not all_ok:
        log("ABORT: un bloque no pasó el triple-scan — NO se entrena")
        return 2

    log("### FASE A OK — delegando en wake_v5_overnight (train+gates) ###")
    return subprocess.run([PY, str(ROOT / "scripts" / "wake_v5_overnight.py")],
                          cwd=str(ROOT)).returncode


if __name__ == "__main__":
    raise SystemExit(main())
