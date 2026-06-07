"""Prepara el input para el workflow de análisis de dataset-FT: consolida los modos
de falla de las 6 tandas re-run + el juez de 4000, organizados por los 4 focos
(idioma, identidad, routing, honestidad), para que los agentes propongan correcciones
al dataset de fine-tuning.

Salida: scripts/_diag/_ftfail/_failmode_<foco>.json (casos crudos por foco) +
        _ftfail/_judge_bugs.json (los 992 bugs del juez).
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DIAG = ROOT / "scripts" / "_diag"
OUT = DIAG / "_ftfail"
OUT.mkdir(parents=True, exist_ok=True)

# 1) cargar las 6 tandas re-run
recs = []
for o in (0, 1000, 2000, 3000, 4000, 5000):
    f = DIAG / f"_rerun_tanda_{o}.jsonl"
    if f.exists():
        for l in f.read_text(encoding="utf-8").splitlines():
            if l.strip():
                recs.append(json.loads(l))
print(f"re-run: {len(recs)} casos", file=sys.stderr)

def compact(r):
    return {
        "i": r.get("i"), "lang": r.get("lang"), "cat": r.get("cat"),
        "user": (r.get("user_text") or "")[:160],
        "reply": (r.get("reply") or "")[:300],
        "tools": [{"n": t.get("name"), "a": t.get("action")} for t in (r.get("tools") or [])][:8],
        "gt": r.get("correct_tools") or [],
    }

# --- FOCO 1: IDIOMA (user no-ES, reply en español) ---
es_lead = re.compile(r"^(listo|abr[íi]|abrir|claro|son las|reproduc|busqu)", re.I)
lang_fails = []
for r in recs:
    lang = (r.get("lang") or "").lower()
    if lang and lang[:2] in ("en", "pt", "fr", "de", "it", "ru", "ja", "zh"):
        rep = (r.get("reply") or "").strip()
        if es_lead.match(rep):
            lang_fails.append(compact(r))

# --- FOCO 2: IDENTIDAD ("soy gemma", "me llamo gemma", o cómo-me-llamo mal) ---
ident = re.compile(r"\bsoy gemma\b|\bme llamo gemma\b|gemma 4\b", re.I)
ident_fails = []
for r in recs:
    rep = (r.get("reply") or "")
    if ident.search(rep):
        ident_fails.append(compact(r))

# --- FOCO 3: ROUTING (estado-vs-acción, how-to, conocimiento->web) ---
state_q = re.compile(r"\b(est[áa]\s+(abiert|cerrad|instalad)|tienes?|hay\s+|chequea|revisa|verifica|"
                     r"is\s+\w+\s+(open|running|installed)|check if)\b", re.I)
howto_q = re.compile(r"\b(c[óo]mo\s+(cierro|borro|elimino|abro|hago)|how\s+(do|to|can)\s+i)\b", re.I)
know_q = re.compile(r"^\s*(qu[ée]\s+es|qu[ée]\s+son|de qu[ée] trata|what\s+is|what\s+are|expli)", re.I)
routing_fails = []
for r in recs:
    ut = r.get("user_text") or ""
    tools = [(t.get("name") or "") for t in (r.get("tools") or [])]
    acted = any(t in ("app", "steam", "filesystem", "system", "browser", "gui", "window",
                      "computer_use", "media") for t in tools)
    if acted and (state_q.search(ut) or howto_q.search(ut) or know_q.search(ut)):
        routing_fails.append(compact(r))

# --- FOCO 4: HONESTIDAD (auto-confirm, claim sin evidencia, fabricación) ---
# confirmed:true auto-emitido + claims de envío/click/borrado sin tool real
honesty_fails = []
for r in recs:
    flagged = False
    for t in (r.get("tools") or []):
        if str((t.get("args") or {}).get("confirmed", "")).lower() in ("true", "1", "yes"):
            flagged = True
    rep = (r.get("reply") or "").lower()
    if re.search(r"\b(le mand[ée]|le envi[ée]|cliqu[ée]|borr[ée]|elimin[ée]|sent|clicked)\b", rep):
        # solo si el reply afirma algo fuerte (luego el agente decide si es real)
        flagged = True
    if flagged:
        honesty_fails.append(compact(r))

# guardar (cap a 200 por foco para que el lote sea manejable; el agente ve la muestra)
for name, data in [("idioma", lang_fails), ("identidad", ident_fails),
                   ("routing", routing_fails), ("honestidad", honesty_fails)]:
    (OUT / f"_failmode_{name}.json").write_text(
        json.dumps(data[:200], ensure_ascii=False), encoding="utf-8")
    print(f"{name}: {len(data)} casos (guardo {min(len(data),200)})", file=sys.stderr)

# 2) los 992 bugs del juez (si está el output)
judge_out = ROOT / ".." / ".." / "AppData"  # no portable; se pasa por separado
print("listo", file=sys.stderr)
