"""Mide los 4 focos del re-fine-tuning EN VIVO contra el modelo cargado (run_content,
seguro). Para correr DESPUÉS de cuantizar+reemplazar el GGUF. Ejecución física
mockeada (read-only) para medir routing/idioma/identidad sin tocar nada.

Mide: IDENTIDAD (se nombra Baxy, no Gemma), IDIOMA (reply espeja idioma del user),
ROUTING (estado/how-to/conocimiento no ejecutan), y anti-regresión (acciones siguen).

Uso: python scripts/_diag/_verify_focos_postft.py
"""
from __future__ import annotations
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import os
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")  # no contaminar la DB de Jarvis en pruebas
os.environ.setdefault("GEMMA4_AGENT_SAFETY", "0")  # medir routing sin fricción de gate

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)

from gemma4_agent.tools_pkg.tools import ToolRegistry
ToolRegistry.execute = lambda self, n, a: {"ok": True, "status": "ok", "verified": True, "_eval_mock": True}

from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent()
agent.run_content("hola")


def run(msg, prev=None):
    try:
        agent.history.clear()
    except Exception:
        pass
    if prev:
        agent.run_content(prev)
    r = agent.run_content(msg)
    return (getattr(r, "content", "") or "")


# ---- IDENTIDAD ----
print("\n=== IDENTIDAD (debe decir Baxy, no Gemma 4) ===", flush=True)
id_ok = 0
for msg in ["quién sos?", "who are you?", "wer bist du?", "cómo te llamás?", "preséntate"]:
    rep = run(msg)
    says_baxy = "baxy" in rep.lower()
    says_gemma_self = bool(re.search(r"\b(soy|i'?m|i am|ich bin)\s+gemma", rep, re.I))
    ok = says_baxy and not says_gemma_self
    id_ok += ok
    print(f"  [{'OK' if ok else 'XX'}] {msg!r} -> {rep[:60]!r}", flush=True)
# anti-regresión: qué modelo usás -> Gemma 4 (el modelo)
rep = run("qué modelo de IA usás por dentro?")
model_ok = "gemma" in rep.lower()
print(f"  [{'OK' if model_ok else 'XX'}] modelo -> {rep[:60]!r}", flush=True)

# ---- IDIOMA ----
print("\n=== IDIOMA (reply espeja idioma del user) ===", flush=True)
lang_ok = 0
LANG = [("en", "open notepad", ["opened", "opening", "done", "notepad"]),
        ("pt", "abre o bloco de notas", ["abri", "bloco", "pronto", "feito"]),
        ("fr", "ouvre le bloc-notes", ["ouvert", "j'ai", "fait", "voilà"]),
        ("de", "öffne den editor", ["geöffnet", "ich habe", "fertig", "erledigt"]),
        ("it", "apri la calcolatrice", ["aperto", "ho ", "fatto"])]
for lang, msg, good in LANG:
    rep = run(msg)
    rl = rep.lower()
    es_lead = rl.strip().startswith(("listo", "abrí", "abrir"))
    ok = not es_lead
    lang_ok += ok
    print(f"  [{'OK' if ok else 'ES?'}] {lang}: {msg!r} -> {rep[:55]!r}", flush=True)

# ---- ROUTING (consulta no ejecuta) ----
print("\n=== ROUTING (estado/how-to/conocimiento NO ejecutan) ===", flush=True)
rout_ok = 0
ROUT = [("está Steam abierto?", "estado"), ("cómo cierro Spotify?", "howto"),
        ("qué es Python?", "conocimiento"), ("puedes escucharme?", "capacidad")]
for msg, kind in ROUT:
    rep = run(msg)
    # heurística: el reply responde/explica (no es solo "Listo")
    answers = len(rep) > 25 and not rep.lower().strip().startswith(("listo, abrí", "listo, cerré"))
    rout_ok += answers
    print(f"  [{'OK' if answers else 'XX'}] {kind}: {msg!r} -> {rep[:55]!r}", flush=True)

# ---- ESPAÑOL COHERENTE (el gate que falló en v1: input ES -> reply ES coherente) ----
print("\n=== ESPAÑOL COHERENTE (input ES -> reply en ES, no inglés/mezcla) ===", flush=True)
es_ok = 0
ES_MSGS = ["quién sos", "cómo estás", "contame un chiste", "qué hora es",
           "gracias", "cuánto es 2 más 2", "abrí Spotify", "buscá el clima"]
_en_lead = re.compile(r"\b(i'?m|i am|the|done|here|your|opening|i |great|yes|sure|okay)\b", re.I)
for msg in ES_MSGS:
    rep = run(msg)
    # responde en español si NO arranca con marcador inglés fuerte
    en = bool(_en_lead.search(rep[:25]))
    ok = not en
    es_ok += ok
    print(f"  [{'ES' if ok else 'EN!'}] {msg!r} -> {rep[:55]!r}", flush=True)

# ---- ANTI-REGRESIÓN (acciones siguen ejecutando) ----
print("\n=== ANTI-REGRESIÓN (imperativos siguen actuando) ===", flush=True)
anti_ok = 0
for msg in ["abrí Spotify", "subí el volumen a 30", "cerrá Chrome"]:
    rep = run(msg)
    acted = bool(re.search(r"listo|abrí|cerré|subí|abr[íi]|spotify|volumen|chrome", rep, re.I))
    anti_ok += acted
    print(f"  [{'OK' if acted else 'XX'}] {msg!r} -> {rep[:50]!r}", flush=True)

print(f"\n=== RESUMEN ===", flush=True)
print(f"  ESPAÑOL COHERENTE (gate decisivo v2): {es_ok}/{len(ES_MSGS)} "
      f"{'(OK >=7)' if es_ok >= 7 else '(REGRESIÓN — rollback)'}", flush=True)
print(f"  identidad: {id_ok}/5 + modelo {'OK' if model_ok else 'XX'}", flush=True)
print(f"  idioma noES: {lang_ok}/5", flush=True)
print(f"  routing: {rout_ok}/4", flush=True)
print(f"  anti-regresión: {anti_ok}/3", flush=True)
