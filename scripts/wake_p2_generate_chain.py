"""P2: cadena de GENERACIÓN multi-idioma para los positivos del wake.

Tras convertir los checkpoints nativos (wake_p2_convert_checkpoints.py),
este script genera positivos/negativos "baxy" EN CADA IDIOMA aprovechando
la lógica de resume del paquete: todos los configs comparten
model_name=baxy (mismo output/baxy) y el n_samples es ACUMULATIVO — cada
corrida agrega SOLO los clips nuevos con el checkpoint nativo siguiente.
espeak fonemiza "baxy" y los confusables ("taxi", "boxeo"...) en la
fonología de cada idioma — el fix estructural del colapso por idioma
medido en v4/v5 (de 0.58 / pl 0.50 / zh 0.05 limpio).

Composición final (~40k positivos + ~40k negativos):
  25.000 EN (LibriTTS 904 voces, existentes) + 3.000 de (MLS 236 voces!)
  + 3.000 fr (MLS multi) + 1.500 × {es, pl, ru, pt, nl, zh}

Uso: .venv_livekit/Scripts/python.exe scripts/wake_p2_generate_chain.py
     (cada voz tarda ~5-20 min de TTS; total ~1.5-2 h; reanudable)
"""
from __future__ import annotations

import copy
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
VENV_PY = str(ROOT / ".venv_livekit" / "Scripts" / "python.exe")
CONFIGS = ROOT / "data" / "livekit_train" / "configs"
PIPER = ROOT / "data" / "piper"

# (voice_id, clips a AGREGAR). Multi-speaker (de/fr MLS) aportan más.
VOICES = [
    ("de_DE-mls", 3000),
    ("fr_FR-mls", 3000),
    ("es_ES-sharvard", 1500),
    ("pl_PL-mc_speech", 1500),
    ("ru_RU-dmitri", 1500),
    ("pt_BR-cadu", 1500),
    ("nl_NL-pim", 1500),
    ("zh_CN-xiao_ya", 1500),
]


def main() -> int:
    import yaml
    base = yaml.safe_load(open(CONFIGS / "baxy.yaml", encoding="utf-8"))
    cum = int(base["n_samples"])          # 25000 EN ya generados
    cum_val = int(base["n_samples_val"])  # 5000

    for voice_id, add in VOICES:
        pt = PIPER / f"{voice_id}-p2.pt"
        if not pt.exists() or not pt.with_suffix(".json").exists():
            print(f"SKIP {voice_id}: checkpoint convertido ausente ({pt.name})")
            continue
        free_gb = shutil.disk_usage(ROOT).free / 1e9
        if free_gb < 12:
            print(f"ABORT: {free_gb:.0f} GB libres (<12) — liberar disco")
            return 2
        cum += add
        cum_val += max(150, add // 8)
        cfg = copy.deepcopy(base)
        cfg["piper_tts"] = {"checkpoint_relpath": f"piper/{voice_id}-p2.pt"}
        cfg["n_samples"] = cum
        cfg["n_samples_val"] = cum_val
        stem = f"baxy_p2_{voice_id.split('_')[0]}_{voice_id.split('-')[-1]}"
        cfg_path = CONFIGS / f"{stem}.yaml"
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
        print(f"== {voice_id}: generate hasta {cum} pos / {cum_val} val "
              f"(config {stem}) ==", flush=True)
        rc = subprocess.run(
            [VENV_PY, str(ROOT / "scripts" / "_train_carter_throttled.py"),
             "generate", "--config", stem], cwd=str(ROOT)).returncode
        if rc != 0:
            print(f"FALLO generate {voice_id} (exit {rc}) — abortando cadena")
            return rc
    print("CADENA COMPLETA: positivos multi-idioma generados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
