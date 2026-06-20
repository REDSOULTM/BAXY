# -*- coding: utf-8 -*-
"""Validación EN VIVO: las tools de estado que devuelven LISTA (procesos, monitores)
ahora exponen un CONTEO explícito (count / monitor_count) para que el LLM narre
"cuántos X" sin dar un no-answer. Boota QAT en :8090 (no toca el Baxy del user en
:8080) + FG :8082, corre la batería con historia aislada por turno, y mata sus servers.
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.infra.config import AgentConfig
from gemma4_agent.infra.llama_server import llama_command
from gemma4_agent.infra.profiles import PROFILES

QAT_PORT = "8090"
QAT_LOG = ROOT / "documentacion" / "_count_narration_live.log"


def health(port: str) -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def boot_qat() -> subprocess.Popen:
    cmd = llama_command(AgentConfig(), PROFILES["vram4_lean"])
    cmd = [QAT_PORT if c == "8080" else c for c in cmd]
    QAT_LOG.parent.mkdir(exist_ok=True)
    logf = open(QAT_LOG, "w", encoding="utf-8", errors="replace")
    print(f"booteando QAT en :{QAT_PORT} ...")
    proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
    t0 = time.time()
    while time.time() - t0 < 90:
        if health(QAT_PORT):
            print(f"  QAT healthy en {time.time()-t0:.1f}s")
            return proc
        if proc.poll() is not None:
            raise RuntimeError(f"QAT murió (exit {proc.returncode}); ver {QAT_LOG}")
        time.sleep(1.0)
    raise RuntimeError("QAT no quedó healthy en 90s")


def main() -> int:
    qat = boot_qat()
    os.environ["GEMMA4_AGENT_SERVER"] = f"http://127.0.0.1:{QAT_PORT}"
    os.environ["GEMMA4_FG_ROUTER"] = "1"
    os.environ["GEMMA4_ENCODER_ONNX"] = "1"
    os.environ["GEMMA4_LEAN_TOOLS"] = "0"
    os.environ["GEMMA4_FG_AUTOBOOT"] = "1"
    os.environ["GEMMA4_FG_SERVER"] = "http://127.0.0.1:8082/v1/chat/completions"
    os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4_lean")
    os.environ.setdefault("GEMMA4_DIAG", "1")

    try:
        from gemma4_agent.agent_core.agent import Gemma4Agent
        a = Gemma4Agent()

        def run(msg):
            a.clear()
            r = a.run_content(msg)
            rep = (getattr(r, "content", None) or str(r)).replace("\n", " ")
            te = getattr(r, "tool_events", None) or []
            tools = [getattr(x, "name", None) for x in te]
            return rep, tools

        # casos: la pregunta "cuántos" sobre tools de lista (antes daban no-answer)
        # + regresión de los que ya narraban bien (RAM/hora), que no deben romperse.
        cases = [
            "cuántos procesos hay corriendo",
            "how many processes are running",
            "cuántos monitores tengo",
            "how many monitors do i have",
            "cuánta RAM tengo",
            "qué hora es",
        ]
        nonanswer = re.compile(
            r"no se ha proporcionado|ninguna tarea|listo, lo dejo|no tengo (la|esa) "
            r"(función|funcion|informaci)|no puedo", re.I)

        print("\n========== BATERÍA cuántos-X (narración de conteo) ==========")
        n_bad = 0
        n_total = 0
        leak = re.compile(r"noted the|tool rules|reglas", re.I)
        for msg in cases:
            reps = 3 if "monitor" in msg or "monitores" in msg or "proces" in msg else 1
            for _ in range(reps):
                rep, tools = run(msg)
                na = bool(nonanswer.search(rep)) or bool(leak.search(rep))
                n_bad += na
                n_total += 1
                tag = "NO-ANSWER" if na else "ok"
                print(f"  [{tag:9}] {msg!r}\n     tools={tools}\n     -> {rep[:160]!r}")

        print("\n========================= RESUMEN =========================")
        print(f"  no-answers/leaks: {n_bad}/{n_total}  (objetivo 0)")
    finally:
        print("\nmatando QAT :8090 (FG :8082 lo mata el atexit del agente) ...")
        qat.terminate()
        try:
            qat.wait(timeout=10)
        except subprocess.TimeoutExpired:
            qat.kill()
        print("listo (tu Baxy en :8080 quedó intacto).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
