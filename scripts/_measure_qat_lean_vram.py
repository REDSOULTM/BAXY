# -*- coding: utf-8 -*-
"""Mide la VRAM REAL del perfil vram4_lean (QAT + ubatch 320 + mmproj-CPU + ctx 6144).

Replica el comando EXACTO que arma el perfil (llama_command), lo levanta en un puerto
APARTE (:8090, no toca el Baxy que corre en :8080), y reporta:
  - los buffers auto-reportados por llama.cpp en GPU (model + KV + compute) = footprint real
  - el delta de nvidia-smi total (incluye overhead del contexto CUDA)
Se mata solo al terminar. NO necesita el agente ni FG: el compute buffer del ubatch se
reserva al cargar el contexto (sched_reserve), así que basta bootear el server.
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gemma4_agent.infra.config import AgentConfig
from gemma4_agent.infra.llama_server import llama_command
from gemma4_agent.infra.profiles import PROFILES

PORT = "8090"
LOG = Path(__file__).resolve().parent.parent / "documentacion" / "_qat_lean_vram_measure.log"


def nvidia_used_mib() -> int | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        return int(out.stdout.strip().splitlines()[0])
    except Exception as e:
        print(f"  (nvidia-smi falló: {e})")
        return None


def health_ok(port: str) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def main() -> int:
    profile = PROFILES["vram4_lean"]
    cmd = llama_command(AgentConfig(), profile)
    # swap el puerto 8080 -> 8090 (no tocar el Baxy del usuario)
    cmd = [PORT if c == "8080" else c for c in cmd]
    print("=== comando (idéntico al perfil, puerto 8090) ===")
    print(" ".join(f'"{c}"' if " " in c else c for c in cmd))
    print(f"\nmodelo: {Path(profile.model_path).name}")
    print(f"ctx={profile.context_size} ubatch={profile.n_ubatch} batch={profile.n_batch} "
          f"mmproj_cpu={profile.mmproj_on_cpu} ngl={profile.n_gpu_layers}\n")

    base = nvidia_used_mib()
    print(f"VRAM total ANTES (con tu Baxy en :8080): {base} MiB\n")

    LOG.parent.mkdir(exist_ok=True)
    logf = open(LOG, "w", encoding="utf-8", errors="replace")
    print("booteando server de medición en :8090 ...")
    proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
    try:
        t0 = time.time()
        while time.time() - t0 < 90:
            if health_ok(PORT):
                break
            if proc.poll() is not None:
                print(f"!! el server murió (exit {proc.returncode}); ver {LOG.name}")
                return 1
            time.sleep(1.0)
        else:
            print(f"!! no quedó healthy en 90s; ver {LOG.name}")
            return 1

        time.sleep(2.0)  # dejar que sched_reserve termine de reservar
        after = nvidia_used_mib()
        load_s = time.time() - t0
        print(f"server healthy en {load_s:.1f}s")
        print(f"VRAM total DESPUÉS: {after} MiB")
        if base is not None and after is not None:
            print(f"\n>>> DELTA nvidia-smi (= VRAM del QAT lean, incl. overhead CUDA): {after - base} MiB ({(after-base)/1024:.2f} GB)\n")

        # buffers auto-reportados por llama.cpp en GPU (el footprint "puro" del modelo)
        txt = LOG.read_text(encoding="utf-8", errors="replace")
        print("=== buffers que reporta llama.cpp (CUDA0 = en GPU) ===")
        for pat, label in [
            (r"CUDA0 model buffer size\s*=\s*([\d.]+)", "model (pesos)"),
            (r"CUDA0 KV buffer size\s*=\s*([\d.]+)", "KV cache"),
            (r"CUDA0 compute buffer size\s*=\s*([\d.]+)", "compute buffer"),
        ]:
            vals = re.findall(pat, txt)
            if vals:
                tot = sum(float(v) for v in vals)
                print(f"  {label:16s}: {tot:8.1f} MiB" + (f"  (suma de {len(vals)})" if len(vals) > 1 else ""))
        m = re.search(r"projected to use (\d+) MiB", txt)
        if m:
            print(f"  llama.cpp 'projected to use': {m.group(1)} MiB")
    finally:
        print("\nmatando server de medición ...")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        logf.close()
        print("listo (tu Baxy en :8080 quedó intacto).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
