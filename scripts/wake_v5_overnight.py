"""Corrida NOCTURNA del wake v5 — desatendida de punta a punta.

Diseño en wake_v5_diseno_entrenamiento_2026-06-11.md (escala prod LiveKit:
25k/5k/2000bg, large, 100k steps, fp 0.25 + patch augment v2). Hace TODO sin
intervención y deja un veredicto auditable:

  0. PREFLIGHT (aborta si algo falta — nada de degradación silenciosa):
     backgrounds verificados, patch v2 aplicado en el venv, YAML a escala v5,
     disco suficiente, held-outs presentes, backup del modelo prod.
  1. Anti-suspensión: SetThreadExecutionState (la PC no se duerme aunque el
     usuario sí; la pantalla puede apagarse).
  2. Train completo (generate reanuda + augment --clean-features + train +
     export) vía el orquestador throttled existente. ~3-4 h en la 4060 Ti.
  3. Candidato → models/livekit/baxy_noise.onnx (prod NO se toca).
  4. GATES (los 6 pre-escritos) + live-test de integración:
     G1 limpio>=0.80 · G2 voces-snr5>=0.60 · G3 musica-snr5>=0.60 ·
     G4 fp/hr<=1.0 · G5 idiomas fuertes no colapsan (>=0.70 limpio) ·
     G6 confusables<=1%. Live-test: B/C/D deben PASS (A se reporta: es UN
     clip a SNR5, estadísticamente puede fallar con recall ~0.6).
  5. SOLO con 6/6 + integración: deploy (copy a baxy.onnx; el .bak
     pre-retrain queda intacto) + re-live-test sobre prod.
  6. Veredicto SIEMPRE: documentacion/_wake_v5_veredicto.json + .log con
     números crudos, pase o falle. El commit lo decide una sesión humana.

Uso:  python scripts/wake_v5_overnight.py [--skip-train]   (skip-train =
      re-evaluar un candidato ya entrenado)
"""
from __future__ import annotations

import argparse
import ctypes
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
VENV_PY = str(ROOT / ".venv_livekit" / "Scripts" / "python.exe")
MODELS = ROOT / "gemma4_agent" / "voice" / "models" / "livekit"
VERDICT_JSON = ROOT / "documentacion" / "_wake_v5_veredicto.json"
LOG_PATH = ROOT / "documentacion" / "_wake_v5_overnight.log"

# Idiomas FUERTES del modelo prod original (recall limpio >= 0.75 medido
# 2026-06-11 con wake_noise_baseline_eval sobre el modelo desplegado).
# G5: ninguno puede caer bajo 0.70 limpio en el candidato.
STRONG_LANGS = {"ar": 0.75, "de": 0.967, "en": 0.99, "es": 0.90, "fr": 0.983,
                "it": 0.85, "pl": 1.0, "pt": 0.75, "ru": 0.925, "sv": 1.0}

_log_fh = None


def log(msg: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line, flush=True)
    if _log_fh:
        _log_fh.write(line + "\n")
        _log_fh.flush()


def keep_awake() -> None:
    """ES_CONTINUOUS|ES_SYSTEM_REQUIRED: la PC no se suspende mientras este
    proceso vive (la pantalla sí puede apagarse). Crítico para el run
    nocturno: un sleep de Windows a mitad de train = run perdido."""
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
        log("anti-suspension activo (SetThreadExecutionState)")
    except Exception as exc:
        log(f"WARN: no pude fijar anti-suspension: {exc}")


def run_step(name: str, cmd: list[str], timeout_s: int | None = None) -> tuple[int, str]:
    log(f"=== {name}: {' '.join(cmd[:3])}... ===")
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout_s,
                          cwd=str(ROOT))
    out = proc.stdout.decode("utf-8", "replace") + \
        proc.stderr.decode("utf-8", "replace")
    if _log_fh:
        _log_fh.write(out + "\n")
        _log_fh.flush()
    log(f"=== {name} exit={proc.returncode} ({(time.time() - t0) / 60:.1f} min) ===")
    return proc.returncode, out


def preflight() -> list[str]:
    errs: list[str] = []
    # backgrounds verificados (música/speech/noise + heldouts)
    rc, out = run_step("preflight-backgrounds",
                       [PY, "scripts/wake_backgrounds_setup.py",
                        "--skip-download", "--skip-tar"])
    if rc != 0:
        errs.append("backgrounds NO verificados")
    # patch v2 aplicado en el venv
    aug = (ROOT / ".venv_livekit" / "Lib" / "site-packages" / "livekit"
           / "wakeword" / "data" / "augment.py")
    if "[gemma4 noise-patch v2]" not in aug.read_text(encoding="utf-8"):
        errs.append("patch augment v2 NO aplicado (correr "
                    "scripts/_patch_livekit_augment_noise.py)")
    # YAML a escala v5
    import yaml
    cfg = yaml.safe_load(open(ROOT / "data" / "livekit_train" / "configs"
                              / "baxy.yaml", encoding="utf-8"))
    expected = {"n_samples": 25000, "n_samples_val": 5000,
                "n_background_samples": 2000, "steps": 100000}
    for k, v in expected.items():
        if cfg.get(k) != v:
            errs.append(f"config {k}={cfg.get(k)} != {v}")
    if cfg.get("model", {}).get("model_size") != "large":
        errs.append("config model_size != large")
    if cfg.get("target_fp_per_hour") != 0.25:
        errs.append(f"config target_fp_per_hour={cfg.get('target_fp_per_hour')} != 0.25")
    # disco: generate 25k + augment x3 + features ≈ 15-20 GB
    free_gb = shutil.disk_usage(ROOT).free / 1e9
    if free_gb < 25:
        errs.append(f"disco insuficiente: {free_gb:.0f} GB libres (< 25)")
    # held-outs de eval
    for d, n_min in (("positives_baxy", 400), ("confusables_baxy", 400)):
        n = len(list((ROOT / "data" / "wake_universal_eval" / d).glob("*.wav")))
        if n < n_min:
            errs.append(f"eval {d}: {n} < {n_min}")
    if not list((ROOT / "data" / "wake_universal_eval" / "negatives").glob("**/*.flac")):
        errs.append("negatives flac ausentes")
    if not list((ROOT / "data" / "wake_universal_eval" / "noise_heldout"
                 / "music").glob("*.wav")):
        errs.append("noise_heldout/music ausente")
    # prod + backup
    if not (MODELS / "baxy.onnx").exists():
        errs.append("modelo prod baxy.onnx ausente")
    if not (MODELS / "baxy.onnx.bak_pre_noise_retrain").exists():
        errs.append("backup pre-retrain ausente")
    return errs


def parse_noise_eval(out: str) -> dict:
    res: dict = {"by_lang": {}}
    for cond in ("limpio", "voces_snr10dB", "voces_snr5dB", "voces_snr0dB",
                 "musica_snr5dB", "musica_snr0dB"):
        m = re.search(rf"{cond}\s+recall=([\d.]+)", out)
        if m:
            res[cond] = float(m.group(1))
    for m in re.finditer(r"^\s+(\w{2,3})\s+limpio (\d+)/(\d+)", out, re.M):
        lang, a, b = m.group(1), int(m.group(2)), int(m.group(3))
        res["by_lang"][lang] = a / max(1, b)
    m = re.search(r"FP solo-voces: (\d+)/(\d+)", out)
    if m:
        res["fp_voces"] = int(m.group(1))
    m = re.search(r"FP solo-musica: (\d+)/(\d+)", out)
    if m:
        res["fp_musica"] = int(m.group(1))
    return res


def main() -> int:
    global _log_fh
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-train", action="store_true")
    ap.add_argument("--preflight-only", action="store_true",
                    help="solo verifica precondiciones, no entrena")
    args = ap.parse_args()
    _log_fh = open(LOG_PATH, "a", encoding="utf-8")
    log("### WAKE V5 OVERNIGHT — inicio ###")
    keep_awake()

    errs = preflight()
    if errs:
        log("PREFLIGHT FALLO:")
        for e in errs:
            log(f"  - {e}")
        VERDICT_JSON.write_text(json.dumps(
            {"status": "PREFLIGHT_FAIL", "errors": errs}, ensure_ascii=False,
            indent=1), encoding="utf-8")
        return 2
    log("preflight OK")
    if args.preflight_only:
        log("(--preflight-only: listo para lanzar)")
        return 0

    if not args.skip_train:
        rc, _ = run_step("train-pipeline",
                         [VENV_PY, "scripts/_train_carter_throttled.py",
                          "all", "--clean-features"])
        if rc != 0:
            VERDICT_JSON.write_text(json.dumps(
                {"status": "TRAIN_FAIL", "exit": rc}, indent=1),
                encoding="utf-8")
            return 3

    onnx = ROOT / "output" / "baxy" / "baxy.onnx"
    if not onnx.exists():
        log("FALLO: no hay output/baxy/baxy.onnx")
        return 3
    shutil.copy2(onnx, MODELS / "baxy_noise.onnx")
    log("candidato copiado a baxy_noise.onnx")

    gates: dict = {}
    # G1/G2/G3/G5 + FP ventanas
    rc, out = run_step("eval-noise",
                       [PY, "scripts/wake_noise_baseline_eval.py",
                        "--stem", "baxy_noise"])
    noise = parse_noise_eval(out)
    gates["G1_limpio"] = (noise.get("limpio", 0), noise.get("limpio", 0) >= 0.80)
    gates["G2_voces_snr5"] = (noise.get("voces_snr5dB", 0),
                              noise.get("voces_snr5dB", 0) >= 0.60)
    gates["G3_musica_snr5"] = (noise.get("musica_snr5dB", 0),
                               noise.get("musica_snr5dB", 0) >= 0.60)
    weak = {l: round(noise["by_lang"].get(l, 0.0), 3)
            for l in STRONG_LANGS if noise["by_lang"].get(l, 0.0) < 0.70}
    gates["G5_idiomas"] = (weak, not weak)
    gates["FP_ventanas"] = ((noise.get("fp_voces", 99), noise.get("fp_musica", 99)),
                            noise.get("fp_voces", 99) == 0
                            and noise.get("fp_musica", 99) <= 3)

    # G6 confusables
    rc6, out6 = run_step("eval-confusables",
                         [PY, "scripts/wake_confusables_eval.py",
                          "--stem", "baxy_noise"])
    m = re.search(r"fake-fires: (\d+)/(\d+) = ([\d.]+)%", out6)
    rate = float(m.group(3)) / 100 if m else 1.0
    gates["G6_confusables"] = (rate, rc6 == 0)

    # G4 fp/hr (10 h, ~25 min CPU)
    rc4, out4 = run_step("eval-fp-hours",
                         [PY, "scripts/wake_fp_hours_eval.py",
                          "--stem", "baxy_noise"])
    m = re.search(r"fp/hr = ([\d.]+)", out4)
    fph = float(m.group(1)) if m else 99.0
    gates["G4_fp_hr"] = (fph, rc4 == 0)

    # live-test integración (B/C/D obligatorios; A informativo)
    rcl, outl = run_step("live-test",
                         [PY, "scripts/_diag/_live_wake_noise_pipeline.py",
                          "--stem", "baxy_noise"])
    bcd_ok = all(re.search(rf"^{s} .*PASS", outl, re.M) for s in ("B", "C", "D"))
    a_pass = bool(re.search(r"^A .*PASS", outl, re.M))
    gates["integracion_BCD"] = ((f"A={'PASS' if a_pass else 'FAIL'}"), bcd_ok)

    all_pass = all(ok for _, ok in gates.values())
    log("--- GATES ---")
    for k, (val, ok) in gates.items():
        log(f"  {k}: {val} -> {'PASS' if ok else 'FAIL'}")

    deployed = False
    if all_pass:
        shutil.copy2(MODELS / "baxy_noise.onnx", MODELS / "baxy.onnx")
        deployed = True
        log("DEPLOY: baxy.onnx actualizado (backup pre-retrain intacto)")
        rc2, _ = run_step("live-test-prod",
                          [PY, "scripts/_diag/_live_wake_noise_pipeline.py",
                           "--stem", "baxy"])
        log(f"live-test sobre prod: exit={rc2}")
    else:
        log("NO-DEPLOY: gates incompletos; prod intacto")

    verdict = {
        "status": "DEPLOYED" if deployed else "GATES_FAIL",
        "gates": {k: {"valor": v, "pass": ok} for k, (v, ok) in gates.items()},
        "noise_eval": noise,
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    VERDICT_JSON.write_text(json.dumps(verdict, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    log(f"### FIN — {verdict['status']} (veredicto en {VERDICT_JSON.name}) ###")
    return 0 if deployed else 1


if __name__ == "__main__":
    raise SystemExit(main())
