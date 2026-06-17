# -*- coding: utf-8 -*-
"""Recheck del prompt-fix anti vision-confab, vía el AGENTE (camino real) contra el QAT.
Corre las queries que confabulaban (conocimiento + multi-turno) 2 veces cada una (temp>0
-> chequear que el fix sea estable). Proceso efímero."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["GEMMA4_ENCODER_ONNX"] = "1"
os.environ["GEMMA4_FG_ROUTER"] = "1"
os.environ["GEMMA4_LEAN_TOOLS"] = "0"
os.environ["GEMMA4_FG_AUTOBOOT"] = "0"
os.environ.setdefault("GEMMA4_AGENT_SERVER", "http://127.0.0.1:8080")
os.environ["GEMMA4_FG_SERVER"] = "http://127.0.0.1:8082/v1/chat/completions"
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4_lean")
os.environ.setdefault("GEMMA4_DIAG", "1")

from gemma4_agent.agent_core.agent import Gemma4Agent  # noqa: E402

a = Gemma4Agent()


def confab(txt: str) -> bool:
    t = txt.lower()[:55]
    return any(k in t for k in ("pantalla", "screen", "captura", "imagen muestra", "fondo de color"))


def run(msg, reset=True):
    if reset:
        a.clear()
    r = a.run_content(msg)
    rep = (getattr(r, "content", None) or str(r)).replace("\n", " ")
    return rep


print("=== knowledge (2 pasadas c/u) ===")
total = bad = 0
for q in ["qué es pytest", "quién descubrió América", "what is a linked list", "contame de roma"]:
    for _ in range(2):
        rep = run(q)
        c = confab(rep)
        total += 1
        bad += c
        print(f"  [{'CONFAB' if c else 'ok'}] {q!r} -> {rep[:80]!r}")
print("=== multi-turno (sin reset) ===")
a.clear()
for q in ["contame de la torre eiffel", "en qué año se construyó?", "y cuánto mide?"]:
    rep = run(q, reset=False)
    c = confab(rep)
    total += 1
    bad += c
    print(f"  [{'CONFAB' if c else 'ok'}] {q!r} -> {rep[:80]!r}")
print(f"\nRESULTADO: {bad}/{total} confabs de pantalla (objetivo: 0)")
