"""Resources of the running product, with everything loaded, as the goal counts them.

usage: py -3.12 -X utf8 scripts/renew/measure_resources.py <label>
Two runs of the real product through the conductor, each with a few spoken turns:
- «arnés»: llama-server and the mind (BAXY's voice, Supertonic, runs inside it), without the wake word k4 and Parakeet Ultra (outside the measurement by
  the owner's decision): BAXY_RENEW_WAKE_DIR and BAXY_RENEW_STT_DIR point nowhere.
- «total con la voz»: the same with k4 and Ultra loaded.
RAM is each process's USS (memory it alone holds: llama-server's working set counts the mapped GGUF and its private
bytes count the VRAM WDDM commits). VRAM is the GPU's growth over the reading before the product started (WDDM reports
no per-process VRAM). Both are sampled every second from the product ready to 5 s after its turns, and each keeps its
peak. Qwen's llama-server and Laya's (System One, told apart by the GGUF of its command line) are separate roles.
Writes <banks>/runs/<label>-recursos.json.
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bench_e2e import BANKS, Conductor, run_turn, wait_silence  # noqa: E402

TURNS = ["hola, ¿cómo estás?", "¿qué hora es?", "dime una frase corta para empezar bien el día"]
SAMPLE_S = 1.0


def gpu_used_mib() -> int | None:
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, timeout=20).stdout.strip().splitlines()
    return int(out[0]) if out and out[0].strip().isdigit() else None


def gguf_of(arguments: list[str]) -> str:
    """The model a llama-server was started with (its -m)."""
    for flag in ("-m", "--model"):
        if flag in arguments[:-1]:
            return arguments[arguments.index(flag) + 1]
    return ""


def llama_role(arguments: list[str]) -> str | None:
    """R12.7: Laya's server (System One, layam-*.gguf, wherever it lies) is «laya»; Qwen's stays «llama-server»."""
    if Path(gguf_of(arguments)).name.lower().startswith("laya"):
        return "laya"
    return "llama-server" if "BAXYeval" in " ".join(arguments) else None


def product_processes() -> dict[str, list[psutil.Process]]:
    found: dict[str, list[psutil.Process]] = {}
    for process in psutil.process_iter(["name", "cmdline"]):
        name = (process.info["name"] or "").lower()
        cmdline = " ".join(process.info["cmdline"] or [])
        role = (llama_role(process.info["cmdline"] or []) if name == "llama-server.exe"
                else "mente" if name.startswith("python") and "baxy_mind" in cmdline
                else "app" if name == "baxy.exe"
                else "core" if name == "baxy-core.exe"
                # Ronda final: the persistent UIA worker the core prewarms (UiaWorkerHost) is the product's too.
                else "worker-uia" if name.startswith("powershell") and "DesktopUiaWorker" in cmdline
                else None)
        if role:
            found.setdefault(role, []).append(process)
    return found


class Sampler(threading.Thread):
    """Every SAMPLE_S, the USS of each role and the GPU's memory, keeping each one's peak (R12.7: five samples after
    the turns missed the inference; a long session read llama-server's USS at 3.1 GB against 2.3 GB)."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.done = threading.Event()
        self.peak: dict[str, int] = {}
        # Auditoría final: the peak is only of the samples nvidia-smi answered; none answered leaves the VRAM unmeasured.
        self.gpu: int | None = None
        self.total = 0  # the product's RAM in one sample, at its highest
        self.samples = 0

    def sample(self) -> None:
        try:
            reading = gpu_used_mib()
        except (OSError, subprocess.SubprocessError):
            reading = None
        if reading is not None:
            self.gpu = max(self.gpu or 0, reading)
        now = {}
        for role, processes in product_processes().items():
            uss = 0
            for process in processes:
                try:
                    uss += process.memory_full_info().uss
                except psutil.Error:
                    pass
            now[role] = round(uss / 2**20)
            self.peak[role] = max(self.peak.get(role, 0), now[role])
        self.total = max(self.total, sum(now.values()))
        self.samples += 1

    def run(self) -> None:
        while not self.done.is_set():
            self.sample()
            self.done.wait(SAMPLE_S)

    def stop(self) -> None:
        self.done.set()
        self.join()


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
    sampler = Sampler()
    sampler.start()
    try:
        time.sleep(20)  # the voice runtime finishes loading beside the model
        for text in TURNS:
            run_turn(conductor, {"text": text}, 120)
            wait_silence(conductor, 30)
        time.sleep(5)  # the five seconds after the turns that were the whole measurement before
    finally:
        sampler.stop()
        conductor.close()
    peak, gpu = sampler.peak, sampler.gpu
    # Laya's server is the mind's as well (it counted inside «llama-server» on the notebook before R12.7).
    harness = sum(peak.get(role, 0) for role in ("llama-server", "laya", "mente"))
    # Ronda final: the product as the conductor runs it as well (App, Core and the UIA worker beside the harness); the
    # window's WebView2 and the browser's own UIA worker do not run under the conductor and are not measured.
    return {"oido_cargado": ear, "vram_mib": (gpu - before) if gpu is not None and before is not None else None,
            "uss_mib": peak, "arnes_ram_mib": harness, "producto_ram_mib": sum(peak.values()),
            "gpu_before_mib": before, "gpu_peak_mib": gpu,
            # R12.7: the product's RAM in the sample where it was highest (the roles' peaks above may not coincide),
            # and how many samples there were.
            "producto_ram_pico_conjunto_mib": sampler.total, "muestras": sampler.samples}


def main() -> None:
    label = sys.argv[1]
    result = {"label": label, "arnes": measure(label, ear=False), "total_con_voz": measure(label, ear=True)}
    (BANKS / "runs" / f"{label}-recursos.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                                           encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
