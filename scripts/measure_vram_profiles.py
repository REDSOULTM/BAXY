"""Measure REAL loaded VRAM for each Gemma 4 GGUF quant (+ optional vision).

Purpose (2026-05-20): the profiles.py VRAM numbers were stale (E2B-Q4 was
commented "4.46 GB" but the file on disk is 2.9 GB). Before designing a full
set of VRAM-named profiles we measure the truth on this machine with
nvidia-smi, loading each quant via the real llama-server and reading the
used-memory delta over idle.

Each measurement:
  1. record nvidia-smi memory.used (idle baseline)
  2. start llama-server -m <quant> -c <ctx> -ngl 99 --flash-attn on
     (+ --mmproj <mmproj> when vision=on)
  3. wait until /health is ok (or timeout)
  4. record peak memory.used; delta = peak - idle
  5. stop the server, wait for VRAM to drain

NOT a runtime module — a one-shot benchmark. Run from repo root:
    python scripts/measure_vram_profiles.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LLAMA = Path("C:/llamacpp-cuda/bin/llama-server.exe")
HOST, PORT = "127.0.0.1", 8090  # 8090 to avoid colliding with the real server
E2B = ROOT / "models" / "E2B"
E4B = ROOT / "models" / "E4B"

# (label, gguf path, ctx, vision mmproj or None)
CASES = [
    ("E2B-UD-Q2_K_XL  ctx2k  novis", E2B / "gemma-4-E2B-it-UD-Q2_K_XL.gguf", 2048, None),
    ("E2B-Q3_K_M      ctx2k  novis", E2B / "gemma-4-E2B-it-Q3_K_M.gguf",      2048, None),
    ("E2B-Q4_K_M      ctx4k  novis", E2B / "gemma-4-E2B-it-Q4_K_M.gguf",      4096, None),
    ("E2B-Q4_K_M      ctx4k  +VIS",  E2B / "gemma-4-E2B-it-Q4_K_M.gguf",      4096, E2B / "mmproj-F16.gguf"),
    ("E2B-Q5_K_M      ctx8k  novis", E2B / "gemma-4-E2B-it-Q5_K_M.gguf",      8192, None),
    ("E2B-UD-Q2_K_XL  ctx2k  +VIS",  E2B / "gemma-4-E2B-it-UD-Q2_K_XL.gguf",  2048, E2B / "mmproj-F16.gguf"),
    ("E4B-UD-Q4_K_XL  ctx16k novis", E4B / "gemma-4-E4B-it-UD-Q4_K_XL.gguf",  16384, None),
    ("E4B-Q4_K_M      ctx8k  +VIS",  E4B / "gemma-4-E4B-it-Q4_K_M.gguf",      8192, E4B / "mmproj-F16.gguf"),
]


def vram_used_mb() -> int:
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=5,
    ).stdout.strip().splitlines()[0]
    return int(out)


def health_ok() -> bool:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{PORT}/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def measure(label: str, model: Path, ctx: int, mmproj: Path | None) -> dict:
    if not model.is_file():
        return {"label": label, "error": "model missing"}
    idle = vram_used_mb()
    cmd = [
        str(LLAMA), "-m", str(model), "-c", str(ctx), "-ngl", "99",
        "--flash-attn", "on", "--host", HOST, "--port", str(PORT),
        "--no-webui",
    ]
    if mmproj and mmproj.is_file():
        cmd += ["--mmproj", str(mmproj)]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    peak = idle
    ok = False
    try:
        for _ in range(90):  # up to ~90s to load
            time.sleep(1)
            try:
                peak = max(peak, vram_used_mb())
            except Exception:
                pass
            if health_ok():
                ok = True
                # sample a couple more times after ready to catch compute buffers
                for _ in range(3):
                    time.sleep(1)
                    peak = max(peak, vram_used_mb())
                break
            if proc.poll() is not None:
                break
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        # wait for VRAM to drain back near idle
        for _ in range(20):
            time.sleep(1)
            if vram_used_mb() <= idle + 200:
                break
    return {
        "label": label, "ok": ok, "idle_mb": idle, "peak_mb": peak,
        "delta_mb": peak - idle, "disk_mb": model.stat().st_size // (1024 * 1024),
    }


def main() -> int:
    if not LLAMA.is_file():
        print(f"llama-server not found: {LLAMA}")
        return 1
    results = []
    for label, model, ctx, mmproj in CASES:
        print(f"measuring {label} ...", flush=True)
        r = measure(label, model, ctx, mmproj)
        results.append(r)
        print(f"  -> {json.dumps(r)}", flush=True)
    print("\n==== SUMMARY (delta = real VRAM the app added over Windows idle) ====")
    print(f"{'profile case':32s} {'disk':>7s} {'loaded':>8s} {'ok':>4s}")
    for r in results:
        if "error" in r:
            print(f"{r['label']:32s}  {r['error']}")
            continue
        print(f"{r['label']:32s} {r['disk_mb']:5d}MB {r['delta_mb']:6d}MB {'Y' if r['ok'] else 'N':>4s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
