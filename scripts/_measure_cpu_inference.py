"""Experimento mínimo: mide la velocidad de inferencia en CPU del perfil `cpu`
(-ngl 0, E2B-Q4) — el fallback para cuando la GPU está ocupada (juego/app pesada).

Arranca un llama-server CPU en un puerto SECUNDARIO (no toca el 8080 del agente),
mide con los `timings` reales de llama.cpp:
  - prefill tok/s (costo del primer turno: procesar el prompt)
  - decode tok/s (velocidad a la que se genera la respuesta — la métrica de UX)
y lo apaga.

SEGURO: CPU puro (sin GPU), sin input sintético, server propio del agente.
NOTA: corre en el box de dev (CPU desktop) → es un TECHO; una laptop 4GB será más lenta.

Uso:  python scripts/_measure_cpu_inference.py
"""
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.infra.config import AgentConfig
from gemma4_agent.infra.profiles import PROFILES, _profile_with_overrides
from gemma4_agent.infra.llama_server import llama_command

PORT = 8092  # secundario: no interfiere con el server gestionado (8080)
cfg = AgentConfig.from_env()
prof = _profile_with_overrides(PROFILES["cpu"])
cmd = llama_command(cfg, prof)
for i, a in enumerate(cmd):
    if a == "--port":
        cmd[i + 1] = str(PORT)

print(f"[boot] llama-server CPU (-ngl 0) en :{PORT} — carga del modelo en RAM (~10-40s)...", flush=True)
t0 = time.time()
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _health() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


deadline = time.time() + 240
while time.time() < deadline:
    if _health():
        break
    if proc.poll() is not None:
        print(f"[ERROR] el server CPU murió al arrancar (exit {proc.returncode})", flush=True)
        sys.exit(1)
    time.sleep(1)
else:
    print("[ERROR] timeout esperando /health", flush=True)
    proc.terminate()
    sys.exit(1)
print(f"[boot] server CPU listo en {time.time() - t0:.1f}s", flush=True)


def measure(prompt: str, n_predict: int, label: str) -> dict:
    body = json.dumps({
        # ignore_eos: generar SIEMPRE n_predict tokens (sin cortar en EOS), para
        # medir throughput de decode puro — sin esto el modelo corta a 1 token con
        # el prompt crudo de /completion y la medición de decode sale inválida.
        "prompt": prompt, "n_predict": n_predict, "stream": False,
        "cache_prompt": True, "ignore_eos": True,
    }).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}/completion", data=body,
        headers={"Content-Type": "application/json"},
    )
    t = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        data = json.loads(r.read())
    wall = time.time() - t
    tm = data.get("timings", {}) or {}
    print(f"\n[{label}]", flush=True)
    print(f"  prefill: {tm.get('prompt_n', '?')} tok en {tm.get('prompt_ms', 0):.0f}ms "
          f"→ {tm.get('prompt_per_second', 0):.1f} tok/s", flush=True)
    print(f"  decode:  {tm.get('predicted_n', '?')} tok en {tm.get('predicted_ms', 0):.0f}ms "
          f"→ {tm.get('predicted_per_second', 0):.1f} tok/s", flush=True)
    print(f"  wall total: {wall:.1f}s", flush=True)
    return tm


print("=" * 72, flush=True)
measure("Hola", 8, "warmup (descartado)")
measure("Explicá en una frase qué es la fotosíntesis.", 80,
        "DECODE — prompt corto (~12 tok), genera 80 tok (≈ velocidad de respuesta)")
big = "El asistente de voz local procesa el pedido del usuario y responde. " * 200
measure(big + "\nResumí en una frase.", 24,
        "PREFILL — prompt grande (~2.4k tok), genera 24 tok (≈ costo del 1er turno)")
print("=" * 72, flush=True)
print("[interpretación] decode tok/s = qué tan rápido streamea la respuesta.", flush=True)
print("                 prefill tok/s = costo de procesar el prompt (1er turno; luego cachea).", flush=True)
print("                 OJO: medido en CPU de DESKTOP → una laptop 4GB será MÁS lenta.", flush=True)

print("\n[fin] apagando server CPU :%d" % PORT, flush=True)
proc.terminate()
try:
    proc.wait(timeout=10)
except Exception:
    proc.kill()
