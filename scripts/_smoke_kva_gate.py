# -*- coding: utf-8 -*-
"""Smoke del KVA gate con el encoder REAL de Baxy (sr.embed). Verifica que las TRAMPAS de
conocimiento den is_knowledge=True (→no_tool) y las ACCIONES den False (→FG). Corré con
GEMMA4_ENCODER_ONNX=1 (lean, el deployment) y =0 (torch, el del training del gate) para ver
si transfiere. No necesita servers (solo el encoder + el gate)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gemma4_agent.routing import semantic_router as sr
from gemma4_agent.routing import fg_router as fg

sr.embed("warmup")
gate = fg._KVAGate(fg._KVA_GATE)

# Trampas de CONOCIMIENTO (handoff: deben dar is_knowledge=True → no_tool)
TRAPS = ["contame de roma", "what is a linked list", "y cuánto mide?", "quién fue Einstein",
         "por qué el cielo es azul", "parle-moi de Rome", "cos'è una lista", "contame de la torre eiffel",
         "qué es pytest", "who was Napoleon"]
# Canarios de ACCIÓN (deben dar is_knowledge=False → FG, NO bloquear)
ACTIONS = ["subi el volumen a 40", "mandale 'te amo' a Ana por whatsapp", "abrí Chrome",
           "recordá comprar café", "conectate al wifi Casa_5G", "poné música", "qué hora es",
           "set the volume to 30", "abrí la calculadora", "aumentá el brillo"]

enc = "ONNX" if (os.environ.get("GEMMA4_ENCODER_ONNX", "0").lower() in {"1", "true", "yes", "on"}) else "torch"
print(f"=== KVA gate smoke | encoder={enc} (backend real: {type(sr._STATE.model).__name__}) | thr={gate.thr} ===")


def emb(q):
    return fg._norm(np.asarray(sr.embed(q), dtype=np.float32))


ok_traps = sum(gate.is_knowledge(emb(q)) for q in TRAPS)
ok_acts = sum(not gate.is_knowledge(emb(q)) for q in ACTIONS)
print("-- TRAMPAS conocimiento (queremos is_knowledge=True → no_tool):")
for q in TRAPS:
    p = gate.p_knowledge(emb(q))
    print(f"   P(conoc)={p:.2f} {'no_tool' if p >= gate.thr else 'FG(MISS)'}  {q!r}")
print("-- ACCIONES (queremos is_knowledge=False → FG):")
for q in ACTIONS:
    p = gate.p_knowledge(emb(q))
    print(f"   P(conoc)={p:.2f} {'FG' if p < gate.thr else 'BLOCK(MISS)'}  {q!r}")
print(f"\nRESUMEN: trampas→no_tool {ok_traps}/{len(TRAPS)} | acciones→FG {ok_acts}/{len(ACTIONS)}")
