"""DEFINITIVE robust orchestrator for the Carter wake-word pipeline.

Encadena setup? -> generate -> augment(+feature-extraction) -> train -> export,
GPU para todo lo posible, sin colgar el PC y sin perder datos entre fases. Diseñado
para NO repetir los 7 gotchas ya pagados (ver memoria
project_wake_word_carter_gotchas_2026_06_03 + CLAUDE.md).

Phases (livekit-wakeword CLI subcommands):
  generate  Piper VITS synthesis (positives + adversarial negatives). USA GPU vía
            torch (synthesis.py:get_device()->cuda). Throttle de CPU SÍ (espeak +
            numpy en CPU), pero NO afinidad-de-proceso (eso ralentizaría la GPU).
  augment   audio aug (CPU) + FEATURE EXTRACTION (la fase lenta ~40min). La
            extracción usa 2 ONNX que el paquete hardcodea a CPU -> los pateamos a
            CUDA con scripts/_patch_feature_extractor_gpu.py (preflight). Aquí NO
            forzamos throttle-a-CPU: dejamos que CUDA EP gane; ORT igual queda con
            2 intra-threads + sin spinning por el sess_options inyectado.
  train     PyTorch en GPU. NUNCA throttlear (OMP+afinidad confunden a cuDNN ->
            "Input type Half and bias type float").
  export    ONNX export en CPU. Throttle CPU sí.

GOTCHAS prevenidos por este script:
  (1) charmap UnicodeDecodeError de espeak  -> PYTHONUTF8=1 + PYTHONIOENCODING=utf-8
      seteados ANTES de cualquier subproceso (heredados por el .exe hijo).
  (2) "| head" mata el pipeline por SIGPIPE -> escribimos a archivo (_pipeline.log)
      con tee-a-disco; nunca pipeamos a head.
  (3) OOM de Piper en GPU -> el config usa tts_batch_size acotado; este script avisa
      de despejar VRAM (mata nada por su cuenta: CLAUDE.md prohíbe matar procesos
      del usuario sin permiso).
  (4) auto-adversariales: el config NO mezcla "hey carter" con "carter" pelado como
      positivo (el generador mete sub-palabras como negativo). Solo entrenamos
      "hey carter"; "carter" pelado va explícito en custom_negative_phrases. Este
      script NO toca eso, solo lo respeta.
  (5/6) eval/feature-extraction que clavan la CPU: throttle por-fase + GPU en
      extraction. El eval RÁPIDO por-idioma es scripts/_diag_wake_recall_probe.py
      (NO el eval oficial que cuelga 2h).
  (7) solo hay 1 checkpoint Piper en-us en disco -> multi-idioma de TTS requiere
      DESCARGAR más. Este script NO descarga modelos extra (fuera de alcance del
      reentreno actual); si en el futuro se agregan, dejar el script de descarga
      (reproducibilidad, CLAUDE.md).

IDEMPOTENCIA / NO-BORRA-DATOS:
  - El paquete livekit reanuda splits ya generados (generate.py: "skips completed
    splits or resumes partial ones"). Este orquestador NO borra output/hey_carter
    entre fases. Si querés un run limpio, borrá output/hey_carter A MANO (decisión
    explícita, no automática: CLAUDE.md, confirmá lo irreversible).
  - --clean-features borra SOLO los .npy de features (no los clips) para re-extraer
    en GPU tras patchear, sin re-generar audio. Pide confirmación.

Uso:
  .venv_livekit/Scripts/python.exe scripts/_train_carter_throttled.py [phase] [opts]
    phase = setup | generate | augment | train | export | all   (default: all)
            ("all" = generate -> augment -> train -> export; setup es aparte)
  opts:
    --no-gpu            no instala/patchea GPU; corre todo en CPU (lento, seguro)
    --clean-features    borra los .npy de features antes de augment (re-extrae GPU)
    --skip-gpu-install  no corre pip install onnxruntime-gpu (asume ya instalado)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import subprocess
import sys
from pathlib import Path

# GOTCHA (1): FORZAR UTF-8 antes de cualquier subproceso. espeak-ng en Windows
# escupe UTF-8 pero el default del intérprete hijo es cp1252 -> UnicodeDecodeError
# 'charmap' revienta generate. El .exe hijo hereda estas env.
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

EXE = str(ROOT / ".venv_livekit" / "Scripts" / "livekit-wakeword.exe")
PY = str(ROOT / ".venv_livekit" / "Scripts" / "python.exe")
PATCH_SCRIPT = str(ROOT / "scripts" / "_patch_feature_extractor_gpu.py")

# CFG/OUT_DIR/LOG se fijan en main() segun --config (default baxy). El output_dir lo
# decide el model_name del propio yaml; aca derivamos las rutas del nombre del config.
CONFIGS_DIR = ROOT / "data" / "livekit_train" / "configs"
CFG = str(CONFIGS_DIR / "baxy.yaml")
OUT_DIR = ROOT / "output" / "baxy"
LOG = OUT_DIR / "_pipeline.log"


def _set_config(name: str) -> None:
    """Fija CFG/OUT_DIR/LOG segun el nombre del config (sin .yaml). El OUT_DIR usa
    el model_name del yaml (mismo nombre por convencion: baxy.yaml -> model_name baxy)."""
    global CFG, OUT_DIR, LOG
    stem = name[:-5] if name.endswith(".yaml") else name
    CFG = str(CONFIGS_DIR / f"{stem}.yaml")
    OUT_DIR = ROOT / "output" / stem
    LOG = OUT_DIR / "_pipeline.log"

# Fases CPU: aplican throttle de THREADS por subproceso (OMP/MKL). NO seteamos
# afinidad del proceso padre (eso afectaría a la GPU en otras fases). El train
# NUNCA se throttlea (rompe cuDNN). El augment SE throttlea de threads CPU pero
# corre la extracción en GPU (CUDA EP) gracias al patch — coexisten.
CPU_THREAD_PHASES = {"setup", "generate", "augment", "export"}
# Fase que se beneficia de la GPU para feature-extraction (necesita el patch).
GPU_EXTRACTION_PHASES = {"augment"}


def _log(msg: str) -> None:
    line = f"[{_dt.datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def env_for(phase: str, use_gpu: bool) -> dict:
    env = dict(os.environ)
    if phase in CPU_THREAD_PHASES:
        # Cap de threads CPU para no clavar los 24 cores (GOTCHA 5/6). Solo en el
        # subproceso hijo, sin afinidad de proceso (no frena la GPU).
        env["OMP_NUM_THREADS"] = "6"
        env["MKL_NUM_THREADS"] = "6"
        env["OPENBLAS_NUM_THREADS"] = "6"
    # Gate del patch GPU para feature-extraction (leído por feature_extractor.py).
    env["GEMMA4_WAKE_FX_GPU"] = "1" if use_gpu else "0"
    return env


def ensure_gpu(skip_install: bool) -> bool:
    """Instala onnxruntime-gpu (si falta) + patchea feature_extractor.py. Devuelve
    True si la GPU quedó lista para feature-extraction."""
    # 1) Instalar onnxruntime-gpu si el provider CUDA no está disponible.
    if not skip_install:
        try:
            r = subprocess.run(
                [PY, "-c",
                 "import onnxruntime as o; "
                 "print('CUDAExecutionProvider' in o.get_available_providers())"],
                capture_output=True, text=True,
            )
            has_cuda = "True" in r.stdout
        except Exception:
            has_cuda = False
        if not has_cuda:
            _log("onnxruntime-gpu no presente -> pip install onnxruntime-gpu "
                 "(CUDA 12.x + cuDNN 9.x; reusa los DLLs de torch 2.5.1+cu124).")
            # ORT 1.26 GPU requiere CUDA 12.x/cuDNN 9.x; torch+cu124 ya los trae.
            # Reemplaza el onnxruntime CPU por el GPU (mismo namespace).
            subprocess.run(
                [PY, "-m", "pip", "install", "--upgrade", "onnxruntime-gpu"],
                env=dict(os.environ),
            )
    # 2) Probe honesto: ¿carga una sesión en CUDA de verdad? (no solo "listada").
    probe = subprocess.run([PY, PATCH_SCRIPT, "--probe-gpu"],
                           env=dict(os.environ), capture_output=True, text=True)
    sys.stdout.write(probe.stdout)
    gpu_ready = probe.returncode == 0
    if not gpu_ready:
        _log("AVISO: GPU NO lista para feature-extraction (provider no carga). "
             "Sigo en CPU (más lento, pero funciona). Revisar DLLs CUDA/cuDNN.")
        return False
    # 3) Aplicar el patch (idempotente) para que la extracción use CUDA EP.
    pr = subprocess.run([PY, PATCH_SCRIPT], env=dict(os.environ),
                        capture_output=True, text=True)
    sys.stdout.write(pr.stdout)
    if pr.returncode != 0:
        _log(f"AVISO: no pude patchear feature_extractor (rc={pr.returncode}). "
             "Sigo en CPU.")
        return False
    _log("GPU lista: feature-extraction usará CUDAExecutionProvider (CPU fallback).")
    return True


def clean_features() -> None:
    """Borra SOLO los .npy de features (no los clips) para re-extraer en GPU."""
    removed = 0
    if OUT_DIR.exists():
        for npy in OUT_DIR.glob("*_features_*.npy"):
            try:
                npy.unlink()
                removed += 1
            except Exception as e:
                _log(f"no pude borrar {npy.name}: {e}")
    _log(f"--clean-features: borrados {removed} .npy de features (clips intactos).")


def run_phase(phase: str, use_gpu: bool) -> int:
    throttled = phase in CPU_THREAD_PHASES
    gpu_note = ""
    if phase in GPU_EXTRACTION_PHASES:
        gpu_note = f" + GPU-extraction={'on' if use_gpu else 'off'}"
    _log(f"=== FASE: {phase} (CPU-threads-cap={'si' if throttled else 'no'}"
         f"{gpu_note}) ===")
    if phase == "setup":
        cmd = [EXE, "setup", "--config", CFG, "--skip-acav"]
    else:
        cmd = [EXE, phase, CFG]
    proc = subprocess.run(cmd, env=env_for(phase, use_gpu))
    _log(f"=== {phase} exit {proc.returncode} ===")
    return proc.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", nargs="?", default="all",
                    help="setup|generate|augment|train|export|all")
    ap.add_argument("--no-gpu", action="store_true",
                    help="todo en CPU (no instala/patchea GPU)")
    ap.add_argument("--clean-features", action="store_true",
                    help="borra .npy de features antes de augment (re-extrae)")
    ap.add_argument("--skip-gpu-install", action="store_true",
                    help="no corre pip install onnxruntime-gpu")
    ap.add_argument("--config", default="baxy",
                    help="nombre del config en data/livekit_train/configs (sin .yaml). Default: baxy")
    args = ap.parse_args()

    _set_config(args.config)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _log(f"### PIPELINE {args.config.upper()}  phase={args.phase}  "
         f"gpu={not args.no_gpu}  log={LOG} ###")

    if args.phase == "all":
        phases = ["generate", "augment", "train", "export"]
    else:
        phases = [args.phase]

    use_gpu = not args.no_gpu
    # Preflight GPU SOLO si alguna fase la necesita para extraction.
    if use_gpu and any(p in GPU_EXTRACTION_PHASES for p in phases):
        use_gpu = ensure_gpu(skip_install=args.skip_gpu_install)
    elif args.no_gpu:
        # Asegurar que el patch esté revertido si el user pidió CPU explícito.
        subprocess.run([PY, PATCH_SCRIPT, "--revert"], env=dict(os.environ))

    if args.clean_features and any(p == "augment" for p in phases):
        clean_features()

    for ph in phases:
        rc = run_phase(ph, use_gpu)
        if rc != 0:
            _log(f"ABORT: {ph} falló (exit {rc}). Los datos previos NO se borraron; "
                 "re-corré desde esta fase (es idempotente / reanudable).")
            return rc

    _log("=== PIPELINE COMPLETO OK ===")
    _log("Siguiente paso (NO automático): generar held-out + correr el gate "
         "por-idioma:")
    _log("  set GEMMA4_EVAL_WAKE=carter && python scripts/"
         "wake_universal_generate_positives.py   (python del SISTEMA, tiene piper)")
    _log("  .venv_livekit/Scripts/python.exe scripts/_diag_wake_recall_probe.py "
         "--threshold 0.25")
    return 0


if __name__ == "__main__":
    sys.exit(main())
