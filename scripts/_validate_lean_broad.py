# -*- coding: utf-8 -*-
"""Validación AMPLIA en vivo de vram4_lean (QAT + FG-CPU + encoder-ONNX + schema-removal).
Persona, acciones multi-idioma, chitchat/no_tool, conocimiento, grounding + un multi-turno.
Apunta al stack lean (E2B QAT :8080 + FG :8082). Proceso efímero."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["GEMMA4_ENCODER_ONNX"] = "1"
os.environ["GEMMA4_FG_ROUTER"] = "1"
os.environ["GEMMA4_LEAN_TOOLS"] = "0"
os.environ["GEMMA4_FG_AUTOBOOT"] = "0"
os.environ["GEMMA4_AGENT_SERVER"] = "http://127.0.0.1:8080"
os.environ["GEMMA4_FG_SERVER"] = "http://127.0.0.1:8082/v1/chat/completions"
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4_lean")
os.environ.setdefault("GEMMA4_DIAG", "1")

from gemma4_agent.agent_core.agent import Gemma4Agent  # noqa: E402

a = Gemma4Agent()


def t(msg, label, reset=True):
    if reset:
        a.clear()
    r = a.run_content(msg)
    rep = (getattr(r, "content", None) or str(r)).replace("\n", " ")
    te = getattr(r, "tool_events", None) or []
    tools = [getattr(x, "name", None) for x in te]
    print(f"[{label}] {msg!r}\n   tools={tools} | {rep[:110]!r}")


print("===== PERSONA / META =====")
t("quién sos", "persona-es")
t("who are you", "persona-en")
print("===== ACCIONES MULTI-IDIOMA =====")
t("subí el volumen a 40", "vol-es")
t("set the volume to 25", "vol-en")
t("qué hora es", "hora-es")
t("what time is it", "hora-en")
t("quelle heure est-il", "hora-fr")
t("que horas são", "hora-pt")
t("che ore sono", "hora-it")
t("abrí la calculadora", "app-es")
t("aumentá el brillo", "brillo-es")
print("===== CHITCHAT / NO_TOOL =====")
t("gracias", "gracias")
t("hola, cómo estás", "saludo")
t("thanks a lot", "thanks-en")
t("contame un chiste", "chiste")
print("===== CONOCIMIENTO =====")
t("qué es pytest", "know-es")
t("who was Napoleon", "know-en")
t("quién descubrió América", "know-es2")
print("===== MULTI-TURNO (sin reset, coherencia) =====")
a.clear()
t("contame de la torre eiffel", "mt-1", reset=False)
t("en qué año se construyó?", "mt-2", reset=False)
t("y cuánto mide?", "mt-3", reset=False)
print("===== GROUNDING (acción real → narración) =====")
t("subí el volumen a 55", "ground", reset=True)
