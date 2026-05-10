"""Orquestador multi-modelo: corre el bench 540 contra cada quant Gemma 4
disponible y compara. Usa chunking (cada chunk en process Python fresco).

Modelos probados (ordenados por VRAM):
    E4B-UD-IQ2_M:  ~5.1 GB (baseline)
    E4B-Q4_K_M:    ~6.1 GB
    E4B-Q5_K_M:    ~6.6 GB
    E4B-Q6_K:      ~7.1 GB
    E4B-Q8_0:      ~8.2 GB

Spawnea/mata llama-server entre modelos. Genera reporte comparativo final.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

MODELS_DIR = Path(r"c:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4\models\E4B")
LLAMA_EXE = r"C:\llamacpp-cuda\bin\llama-server.exe"


def _alive(timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def kill_llama() -> None:
    subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-Process -Name llama-server -ErrorAction SilentlyContinue | Stop-Process -Force"],
        capture_output=True, timeout=15,
    )
    time.sleep(2)


def spawn_llama(model_file: str, no_mmproj: bool = True) -> subprocess.Popen | None:
    """Lanza llama-server con el modelo dado. Retorna Popen o None."""
    model_path = MODELS_DIR / model_file
    if not model_path.is_file():
        print(f"[multi] modelo no encontrado: {model_path}", file=sys.stderr)
        return None

    cmd = [
        LLAMA_EXE,
        "-m", str(model_path),
        "--port", "8080",
        "--host", "127.0.0.1",
        "--jinja",
        "-ngl", "99",
        "-c", "16384",
        "--parallel", "1",
        "--ctx-checkpoints", "1",
        "--flash-attn", "on",
        "--cache-type-k", "f16",
        "--cache-type-v", "f16",
        "--no-context-shift",
        "--reasoning", "off",
        "--reasoning-budget", "0",
    ]
    if not no_mmproj:
        cmd[3:3] = ["--mmproj", str(MODELS_DIR / "mmproj-BF16.gguf")]
    log_path = RESULTS / "llama_server.log"
    log = open(log_path, "wb")
    print(f"[multi] spawn llama-server with {model_file}", flush=True)
    proc = subprocess.Popen(
        cmd, stdout=log, stderr=log,
        creationflags=0x00000200,
    )
    # Wait alive
    t0 = time.monotonic()
    while time.monotonic() - t0 < 120.0:
        if _alive(timeout=1.0):
            print(f"[multi] READY in {int(time.monotonic()-t0)}s", flush=True)
            return proc
        if proc.poll() is not None:
            print(f"[multi] llama-server crashed early", flush=True)
            return None
        time.sleep(1.0)
    print(f"[multi] TIMEOUT 120s waiting for llama-server", flush=True)
    return None


def run_chunk(model_alias: str, start: int, end: int, output_path: Path) -> bool:
    cmd = [
        sys.executable, str(ROOT / "run_bench.py"),
        "--model", model_alias,
        "--start", str(start),
        "--end", str(end),
        "--output", str(output_path),
    ]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        r = subprocess.run(cmd, env=env, timeout=2700)
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def run_model(model_file: str, model_alias: str) -> dict:
    """Bench full 540 contra un modelo, en 6 chunks de 90 (anti-SIGSEGV)."""
    print(f"\n{'#'*70}\n# MODEL: {model_alias} ({model_file})\n{'#'*70}", flush=True)

    chunks = [(i * 90, (i + 1) * 90) for i in range(6)]
    chunk_results: list[Path] = []
    failed_chunks: list[int] = []

    for idx, (s, e) in enumerate(chunks):
        kill_llama()
        proc = spawn_llama(model_file)
        if proc is None:
            print(f"[multi] CHUNK {idx+1} skip — spawn failed", flush=True)
            failed_chunks.append(idx + 1)
            continue
        out_path = RESULTS / f"{model_alias}_chunk{idx+1}_{s:03d}-{e:03d}.json"
        ok = run_chunk(model_alias, s, e, out_path)
        if ok and out_path.exists():
            chunk_results.append(out_path)
            print(f"[multi] CHUNK {idx+1} OK", flush=True)
        else:
            print(f"[multi] CHUNK {idx+1} FAIL", flush=True)
            failed_chunks.append(idx + 1)

    # Re-try failed chunks once
    for idx in list(failed_chunks):
        s, e = chunks[idx - 1]
        print(f"[multi] retry CHUNK {idx}", flush=True)
        kill_llama()
        proc = spawn_llama(model_file)
        if proc is None:
            continue
        out_path = RESULTS / f"{model_alias}_chunk{idx}_{s:03d}-{e:03d}.json"
        if run_chunk(model_alias, s, e, out_path):
            if out_path.exists():
                chunk_results.append(out_path)
                failed_chunks.remove(idx)
                print(f"[multi] CHUNK {idx} retry OK", flush=True)

    # Merge
    merged = []
    by_cat = {}
    pass_total = fail_total = partial_total = 0
    for cp in chunk_results:
        d = json.loads(cp.read_text(encoding="utf-8"))
        for r in d.get("results", []):
            merged.append(r)
            cat = int(r.get("category", 0))
            stats = by_cat.setdefault(cat, {"pass": 0, "partial": 0, "fail": 0})
            st = r.get("status", "FAIL")
            if st == "PASS":
                stats["pass"] += 1; pass_total += 1
            elif st == "PARTIAL":
                stats["partial"] += 1; partial_total += 1
            else:
                stats["fail"] += 1; fail_total += 1

    total = len(merged)
    summary = {
        "model": model_alias,
        "model_file": model_file,
        "total": total,
        "pass": pass_total, "partial": partial_total, "fail": fail_total,
        "pass_rate": round(pass_total / total * 100, 2) if total else 0,
        "chunks_completed": len(chunk_results),
        "chunks_failed": failed_chunks,
        "by_category": by_cat,
    }
    final_path = RESULTS / f"{model_alias}_FINAL.json"
    final_path.write_text(
        json.dumps({"summary": summary, "results": merged},
                    ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n{'='*70}", flush=True)
    print(f"MODEL {model_alias}: {pass_total}/{total} ({summary['pass_rate']}%)", flush=True)
    print(f"  failed chunks: {failed_chunks or 'none'}", flush=True)
    for cat in sorted(by_cat.keys()):
        s = by_cat[cat]
        tot = sum(s.values())
        rate = round(s["pass"] / tot * 100, 1) if tot else 0
        print(f"  C{cat:02d} {s['pass']:>3}/{tot} ({rate}%)", flush=True)
    print(f"  saved: {final_path}", flush=True)
    return summary


def main() -> None:
    # Modelos disponibles ordenados por VRAM (test menor a mayor)
    models = [
        ("gemma-4-E4B-it-UD-IQ2_M.gguf", "E4B-UD-IQ2_M"),
        ("gemma-4-E4B-it-Q4_K_M.gguf", "E4B-Q4_K_M"),
        ("gemma-4-E4B-it-Q5_K_M.gguf", "E4B-Q5_K_M"),
        ("gemma-4-E4B-it-Q6_K.gguf", "E4B-Q6_K"),
        ("gemma-4-E4B-it-Q8_0.gguf", "E4B-Q8_0"),
    ]

    summaries: list[dict] = []
    for fname, alias in models:
        if not (MODELS_DIR / fname).is_file():
            print(f"[multi] SKIP {alias}: archivo no encontrado", flush=True)
            continue
        s = run_model(fname, alias)
        summaries.append(s)
        # Cleanup llama after each model
        kill_llama()

    # Comparative report
    print(f"\n\n{'#'*70}\n# COMPARATIVE REPORT\n{'#'*70}", flush=True)
    print(f"{'MODEL':<25s}  {'PASS':>5s}  {'TOTAL':>5s}  {'%':>6s}", flush=True)
    print("-" * 50, flush=True)
    for s in sorted(summaries, key=lambda x: -x["pass_rate"]):
        print(f"{s['model']:<25s}  {s['pass']:>5d}  {s['total']:>5d}  {s['pass_rate']:>5.2f}%",
              flush=True)
    print("=" * 50, flush=True)

    final = RESULTS / "ALL_MODELS_COMPARATIVE.json"
    final.write_text(json.dumps({"summaries": summaries},
                                  ensure_ascii=False, indent=2),
                      encoding="utf-8")
    print(f"\n[multi] comparative saved to {final}", flush=True)


if __name__ == "__main__":
    main()
