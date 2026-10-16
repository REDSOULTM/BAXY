"""VRAM and RAM of the product WITH its window (WebView2), which measure_resources.py cannot see under the conductor.

usage: py -3.12 -X utf8 scripts/renew/measure_window.py <label>
The real product (scripts/run_renew.cmd, no arguments) starts with its window, the heartbeat off
(BAXY_RENEW_HEARTBEAT=0) and no ear (BAXY_RENEW_WAKE_DIR/STT_DIR=none), so it neither acts on the desktop by itself nor
listens to the room. Once the model is loaded and the window drawn, the GPU's growth over the reading before it started
and the USS of every process under Baxy.exe (WebView2 included) are sampled, then the product is closed.
Writes <banks>/runs/<label>-recursos-ventana.json.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bench_e2e import BANKS, ROOT  # noqa: E402
from measure_resources import gpu_used_mib  # noqa: E402


def product_tree() -> list[psutil.Process]:
    roots = [p for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "baxy.exe"]
    found: dict[int, psutil.Process] = {}
    for root in roots:
        for process in [root] + root.children(recursive=True):
            found[process.pid] = process
    return list(found.values())


def main() -> None:
    label = sys.argv[1]
    if product_tree():
        raise SystemExit("Baxy.exe is already running: never two instances")
    env = dict(os.environ, BAXY_RENEW_HEARTBEAT="0", BAXY_RENEW_WAKE_DIR="none", BAXY_RENEW_STT_DIR="none")
    before = gpu_used_mib()
    launcher = subprocess.Popen(["cmd", "/c", str(ROOT / "scripts" / "run_renew.cmd")], cwd=str(ROOT), env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline and not any(
            (p.name() or "").lower() == "llama-server.exe" for p in product_tree()):
        time.sleep(2)
    time.sleep(60)  # the model loads and warms; the window draws
    gpu, peak = before or 0, {}
    for _ in range(10):
        gpu = max(gpu, gpu_used_mib() or 0)
        roles: dict[str, int] = {}
        for process in product_tree():
            try:
                name = process.name().lower()
                roles[name] = roles.get(name, 0) + round(process.memory_full_info().uss / 2**20)
            except psutil.Error:
                pass
        for name, uss in roles.items():
            peak[name] = max(peak.get(name, 0), uss)
        time.sleep(1)
    for process in product_tree():
        try:
            process.kill()
        except psutil.Error:
            pass
    try:
        launcher.wait(30)
    except subprocess.TimeoutExpired:
        launcher.kill()
    result = {"label": label, "ventana": True, "latido": False, "oido_cargado": False,
              "vram_mib": (gpu - before) if before is not None else None, "gpu_before_mib": before,
              "gpu_peak_mib": gpu, "uss_mib": peak, "producto_ram_mib": sum(peak.values())}
    (BANKS / "runs" / f"{label}-recursos-ventana.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                                                    encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
