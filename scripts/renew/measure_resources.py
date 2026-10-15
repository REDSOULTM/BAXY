"""Resources of the running product, with everything loaded, as the goal counts them.

usage: py -3.12 -X utf8 scripts/renew/measure_resources.py <label>
Two runs of the real product through the conductor, each with a few spoken turns:
- «arnés»: llama-server, the mind and Piper, without the wake word k4 and Parakeet Ultra (outside the measurement by
  the owner's decision): BAXY_RENEW_WAKE_DIR and BAXY_RENEW_STT_DIR point nowhere.
- «total con la voz»: the same with k4 and Ultra loaded.
RAM is each process's USS (memory it alone holds: llama-server's working set counts the mapped GGUF and its private
bytes count the VRAM WDDM commits). VRAM is the GPU's growth over the reading before the product started (WDDM reports
no per-process VRAM). Writes <banks>/runs/<label>-recursos.json.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bench_e2e import BANKS, Conductor, run_turn, wait_silence  # noqa: E402

TURNS = ["hola, ¿cómo estás?", "¿qué hora es?", "dime una frase corta para empezar bien el día"]


def gpu_used_mib() -> int | None:
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, timeout=20).stdout.strip().splitlines()
    return int(out[0]) if out and out[0].strip().isdigit() else None


def product_processes() -> dict[str, list[psutil.Process]]:
    found: dict[str, list[psutil.Process]] = {}
    for process in psutil.process_iter(["name", "cmdline"]):
        name = (process.info["name"] or "").lower()
        cmdline = " ".join(process.info["cmdline"] or [])
        role = ("llama-server" if name == "llama-server.exe" and "BAXYeval" in cmdline
                else "mente" if name.startswith("python") and "baxy_mind" in cmdline
                else "piper" if name == "piper.exe"
                else "app" if name == "baxy.exe"
                else "core" if name == "baxy-core.exe"
                else None)
        if role:
            found.setdefault(role, []).append(process)
    return found


def measure(label: str, ear: bool) -> dict:
    run_dir = BANKS / "runs" / f"{label}-recursos-{'con-oido' if ear else 'arnes'}"
    run_dir.mkdir(parents=True, exist_ok=True)
    if ear:
        os.environ.pop("BAXY_RENEW_WAKE_DIR", None)
        os.environ.pop("BAXY_RENEW_STT_DIR", None)
    else:
        os.environ["BAXY_RENEW_WAKE_DIR"] = os.environ["BAXY_RENEW_STT_DIR"] = "none"
    before = gpu_used_mib()
    conductor = Conductor(run_dir, Path(os.environ["LOCALAPPDATA"]) / "BAXY" / f"bench-{run_dir.name}")
    ready = conductor.events.wait(lambda e: e["type"] in {"runtime", "terminal"}, 300)
    if not ready or not ready.get("mindReady"):
        conductor.close()
        raise SystemExit(f"conductor not ready: {ready}")
    time.sleep(20)  # the voice runtime finishes loading beside the model
    for text in TURNS:
        run_turn(conductor, {"text": text}, 120)
        wait_silence(conductor, 30)
    peak: dict[str, int] = {}
    gpu = before
    for _ in range(5):
        gpu = max(gpu or 0, gpu_used_mib() or 0)
        for role, processes in product_processes().items():
            uss = 0
            for process in processes:
                try:
                    uss += process.memory_full_info().uss
                except psutil.Error:
                    pass
            peak[role] = max(peak.get(role, 0), round(uss / 2**20))
        time.sleep(1)
    conductor.close()
    harness = sum(peak.get(role, 0) for role in ("llama-server", "mente", "piper"))
    return {"oido_cargado": ear, "vram_mib": (gpu - before) if gpu is not None and before is not None else None,
            "uss_mib": peak, "arnes_ram_mib": harness, "gpu_before_mib": before, "gpu_peak_mib": gpu}


def main() -> None:
    label = sys.argv[1]
    result = {"label": label, "arnes": measure(label, ear=False), "total_con_voz": measure(label, ear=True)}
    (BANKS / "runs" / f"{label}-recursos.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                                           encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
