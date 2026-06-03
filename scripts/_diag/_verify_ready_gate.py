# -*- coding: utf-8 -*-
"""Verifica la fix del ready-gate del router (2026-06-02): el latch _router_ready
+ is_router_ready() existen y arrancan en False, y agent_runner importa limpio."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import inspect
import gemma4_agent.agent_core.agent_runner as ar

print("agent_runner import OK")
print("ROUTER_JOIN_TIMEOUT_S =", ar.ROUTER_JOIN_TIMEOUT_S)

cls = [v for k, v in vars(ar).items()
       if inspect.isclass(v) and hasattr(v, "is_router_ready")]
assert cls, "no encontré la clase con is_router_ready"
Runner = cls[0]
print("clase:", Runner.__name__)

inst = Runner()
assert hasattr(inst, "_router_thread"), "falta _router_thread"
assert hasattr(inst, "_router_ready"), "falta _router_ready"
assert inst.is_router_ready() is False, "is_router_ready debe arrancar False"
assert inst.is_warmed_up() is False, "is_warmed_up debe arrancar False"
print("is_router_ready() inicial:", inst.is_router_ready(), "(False esperado)")
print("is_warmed_up() inicial:", inst.is_warmed_up(), "(False esperado)")

# Simular el latch: cuando router_ready=True pero warmed=False, el gate sigue cerrado.
inst._router_ready = True
# gate = built ∧ warmed ∧ healthy ∧ router_ready  → built/warmed False ⇒ gate False
print("latch router=True pero warmed=False → is_warmed_up sigue:", inst.is_warmed_up())
print("OK: la fix del ready-gate está bien cableada.")
