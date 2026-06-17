# -*- coding: utf-8 -*-
"""Validación EN VIVO del perfil vram4_lean con QAT: (1) el 400 de "abre Steam" con FG
activo (schema-removal -> el prompt entra en ctx 6144), (2) confab de "pantalla" con el
KVA gate puesto (conocimiento -> no_tool, sin alucinar pantalla).

Boota el QAT en :8090 (NO toca el Baxy del usuario en :8080), levanta el agente real
apuntado ahí + FG autoboot en :8082 (CPU), corre los casos, y mata sus servers al salir.
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
QAT_LOG = ROOT / "documentacion" / "_qat_lean_live.log"


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
    # Apuntar el agente al QAT :8090 + FG autoboot :8082, con la config del perfil lean.
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

        def run(msg, reset=True):
            if reset:
                a.clear()
            r = a.run_content(msg)
            rep = (getattr(r, "content", None) or str(r)).replace("\n", " ")
            te = getattr(r, "tool_events", None) or []
            tools = [getattr(x, "name", None) for x in te]
            targs = [getattr(x, "args", None) for x in te]
            return rep, tools, targs

        ctx_err = re.compile(r"exceed|context size|400|problema técnico|problema tecnico", re.I)
        confab = re.compile(r"pantalla|screen|captura|imagen muestra|fondo de color", re.I)

        print("\n========== (0) IDENTIDAD / HONESTIDAD (core lean preserva calidad?) ==========")
        for msg in ["quién sos", "who are you", "gracias"]:
            rep, tools, targs = run(msg)
            print(f"  {msg!r}\n     tools={tools} | {rep[:110]!r}")

        print("\n========== (1) REPRO DEL 400: acción que jala el subset steam/app/window ==========")
        n_400 = 0
        for msg in ["abre Steam", "abrí Steam", "open Steam", "minimizá la ventana"]:
            rep, tools, targs = run(msg)
            bad = bool(ctx_err.search(rep))
            n_400 += bad
            print(f"  [{'400/ERR' if bad else 'OK'}] {msg!r}\n     tools={tools} args={targs} | {rep[:80]!r}")

        print("\n========== (2) CONFAB con KVA gate: conocimiento -> no_tool, sin 'pantalla' ==========")
        total = bad = 0
        for q in ["qué es pytest", "contame de roma", "what is a linked list",
                  "quién fue Einstein", "por qué el cielo es azul", "quién descubrió América"]:
            rep, tools, targs = run(q)
            c = bool(confab.search(rep))
            total += 1
            bad += c
            print(f"  [{'CONFAB' if c else 'ok'}] {q!r}\n     tools={tools} | {rep[:90]!r}")
        print("  -- multi-turno (sin reset) --")
        a.clear()
        for q in ["contame de la torre eiffel", "en qué año se construyó?", "y cuánto mide?"]:
            rep, tools, targs = run(q, reset=False)
            c = bool(confab.search(rep))
            total += 1
            bad += c
            print(f"  [{'CONFAB' if c else 'ok'}] {q!r}\n     tools={tools} | {rep[:90]!r}")

        print("\n========================= RESUMEN =========================")
        print(f"  (1) 400/errores de contexto en acciones: {n_400}/4  (objetivo 0)")
        print(f"  (2) confabs de 'pantalla' en conocimiento: {bad}/{total}  (objetivo 0)")
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
