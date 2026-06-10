"""Misión: probar a Baxy/Carter EN VIVO con todo levantado para cazar fallas de
CALIDAD, LATENCIA y otros, a partir del dataset de finetuning.

Reusa la maquinaria probada de _diag_finetune_dataset_eval.py (boot del LLM real,
mock SEGURO de ejecución física, run_content = la UI, wrap del chat para contar
pases), pero con dos diferencias clave para esta misión:

  1. MUESTREO GARANTIZADO: >=N_CATS categorías (default 18) x >=PER_CAT prompts
     (default 10) cada una. Si una categoría tiene menos de PER_CAT ejemplos, se
     toman todos los que tenga y se completa con otra categoría — pero se exige el
     mínimo de categorías distintas.
  2. DETECTORES DE CALIDAD AMPLIADOS + REPORTE POR CATEGORÍA al final (qué
     categoría concentra las fallas), para priorizar las causas raíz.

Seguro: NO ejecuta efectos físicos (execute/t_computer_use mockeados); el LLM SÍ
corre real, así la LATENCIA medida es la real del turno. No toca el workstream de
gestos/cámara.

Uso:
    python scripts/_diag/_mission_eval.py   (con el venv del proyecto activo)
Env:
    GEMMA4_MISSION_CATS=18      # mínimo de categorías
    GEMMA4_MISSION_PER_CAT=10   # mínimo de prompts por categoría
    GEMMA4_MISSION_SLOW_S=6.0   # umbral de latencia "lenta"
    GEMMA4_MISSION_MAXLEN=600   # umbral de reply "demasiado largo" (chars)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import OrderedDict, Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DATASET = ROOT / "dataset_finetune" / "curated" / "curated.jsonl"
OUT = ROOT / "_mission_eval_results.jsonl"
REPORT = ROOT / "documentacion" / "_MISSION_EVAL_REPORT.md"

N_CATS = int(os.environ.get("GEMMA4_MISSION_CATS", "18"))
PER_CAT = int(os.environ.get("GEMMA4_MISSION_PER_CAT", "10"))
SLOW_S = float(os.environ.get("GEMMA4_MISSION_SLOW_S", "6.0"))
MAXLEN = int(os.environ.get("GEMMA4_MISSION_MAXLEN", "600"))

# ---------------------------------------------------------------------------
# 1. Cargar y agrupar por categoría
# ---------------------------------------------------------------------------
by_cat: "OrderedDict[str, list]" = OrderedDict()
seen = set()
for line in DATASET.read_text(encoding="utf-8", errors="replace").splitlines():
    if not line.strip():
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    ut = (d.get("user_text") or "").strip()
    cat = d.get("category") or "(sin)"
    if not ut or cat == "(sin)":
        continue
    key = (ut.lower(), (d.get("prev_text") or "").strip().lower())
    if key in seen:
        continue
    seen.add(key)
    by_cat.setdefault(cat, []).append({
        "user_text": ut,
        "prev_text": (d.get("prev_text") or "").strip(),
        "lang": d.get("lang", "?"),
        "category": cat,
        "correct_tools": d.get("correct_tools") or [],
        "also_valid": d.get("also_valid") or [],
        "correct_reply_style": d.get("correct_reply_style") or "",
        "n_steps": d.get("n_steps", 1),
    })

# Ordenar categorías por tamaño DESC y elegir las que tengan >= PER_CAT, hasta
# cubrir al menos N_CATS. Si no hay suficientes con PER_CAT, bajamos el mínimo
# por-categoría para esas pero garantizamos N_CATS distintas.
cats_sorted = sorted(by_cat.items(), key=lambda kv: -len(kv[1]))
chosen_cats = [c for c, items in cats_sorted if len(items) >= PER_CAT]
if len(chosen_cats) < N_CATS:
    # completar con las siguientes más grandes aunque tengan < PER_CAT
    for c, items in cats_sorted:
        if c not in chosen_cats:
            chosen_cats.append(c)
        if len(chosen_cats) >= N_CATS:
            break
chosen_cats = chosen_cats[:max(N_CATS, len(chosen_cats))]
# limitar a un número manejable de categorías (las N_CATS más pobladas + variedad):
chosen_cats = chosen_cats[:max(N_CATS, 22)]

rows = []
for c in chosen_cats:
    items = by_cat[c]
    take = min(max(PER_CAT, 0), len(items)) if len(items) >= PER_CAT else len(items)
    take = max(take, min(PER_CAT, len(items)))
    # tomar espaciado uniforme para cubrir el rango de la categoría (determinista)
    step = max(1, len(items) // take)
    rows.extend(items[::step][:take])

print(f"[mission-eval] {len(rows)} prompts de {len(chosen_cats)} categorías "
      f"(>= {PER_CAT} c/u, objetivo {N_CATS} cats)", flush=True)
_cc = Counter(r["category"] for r in rows)
for c, n in _cc.most_common():
    print(f"    {n:3}  {c}", flush=True)
assert len(chosen_cats) >= N_CATS, f"solo {len(chosen_cats)} categorías (<{N_CATS})"
assert all(_cc[c] >= min(PER_CAT, len(by_cat[c])) for c in chosen_cats), "alguna cat por debajo del mínimo"

# ---------------------------------------------------------------------------
# 2. Boot del LLM real + mock seguro de ejecución física
# ---------------------------------------------------------------------------
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
mgr = get_shared_manager()
print("[boot] arrancando llama-server...", flush=True)
mgr.start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)

from gemma4_agent.tools_pkg.tools import ToolRegistry, COMPOUND_TOOL_SCHEMAS
from gemma4_agent.infra import llm_client
from gemma4_agent.support.reasoning import detect_leaked_tool_call

KNOWN = {s["function"]["name"] for s in COMPOUND_TOOL_SCHEMAS
         if isinstance(s, dict) and isinstance(s.get("function"), dict)}

executed: list = []
# Acciones IRREVERSIBLES que el tool REAL nunca completa solo: devuelve
# needs_confirmation y espera el OK del usuario (apagar/reiniciar/bloquear PC,
# enviar mensaje, borrar). Si el mock las da por "hechas" ({ok:True}), el 4B
# reintenta sin saber qué hacer -> LOOP FALSO en el eval (medido 2026-06-10:
# spegni/bloqueia/shutdown daban loop_genuine(8) en el mock plano pero en vivo
# con needs_confirmation responden en 1 turno pidiendo confirmación). El mock
# debe replicar ese contrato para no inflar loops.
_DESTRUCTIVE_ACTIONS = (
    "shutdown", "restart", "reboot", "lock", "sleep", "hibernate",
    "log_off", "logoff", "power_off", "poweroff", "sign_out",
)
def _is_destructive(n, a):
    if n not in ("system", "safety"):
        return False
    blob = str(a).lower()
    return any(d in blob for d in _DESTRUCTIVE_ACTIONS)
def _mock_execute(self, n, a):
    executed.append(n)
    if _is_destructive(n, a):
        return {"ok": False, "status": "needs_confirmation", "verified": False,
                "message": "Acción irreversible: requiere confirmación del usuario.",
                "_eval_mock": True}
    return {"ok": True, "status": "ok", "verified": True, "_eval_mock": True}
ToolRegistry.execute = _mock_execute
if hasattr(ToolRegistry, "t_computer_use"):
    def _mock_cu(self, a):
        executed.append("computer_use")
        return {"ok": True, "status": "ok", "verified": True,
                "completion_status": "simulated", "_eval_mock": True}
    ToolRegistry.t_computer_use = _mock_cu
for _m in ["gui_type", "gui_keypress", "gui_click", "gui_type_into", "gui_click_button",
           "gui_hotkey", "gui_scroll", "gui_drag", "_send_text_via_sendinput"]:
    if hasattr(ToolRegistry, _m):
        setattr(ToolRegistry, _m, lambda *a, **k: {"ok": True})

ncalls = [0]
_real_chat = llm_client.LLMClient.chat
def _wrap_chat(self, m, **kw):
    ncalls[0] += 1
    return _real_chat(self, m, **kw)
llm_client.LLMClient.chat = _wrap_chat

from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent()
agent.run_content("hola")  # warm-up (no contar)

# ---------------------------------------------------------------------------
# 3. Detectores de fallas (calidad + latencia)
# ---------------------------------------------------------------------------
_LEAK_TOKENS = re.compile(r"<intent>|</intent>|<unused\d+>|<\|tool_call|INTENT:")
_OLD_NAME = re.compile(r"\bsoy gemma\b|\bgemma 4\b|\bme llamo gemma\b", re.IGNORECASE)
_FOOTER = re.compile(r"\b(status|completion_status|verified|tool_call|ok:true|ok=true)\b", re.IGNORECASE)
_OCR_ECHO = re.compile(r"<<<|>>>")


def tool_match(executed_tools, correct, also_valid):
    exe = [t for t in executed_tools if t not in ("session", "safety", "state")]
    valid_sets = [set(correct)] + [{t} for t in also_valid] + [set(also_valid)]
    if not correct and not also_valid:
        return len(exe) == 0
    exe_set = set(exe)
    if exe_set in valid_sets:
        return True
    if correct and set(correct).issubset(exe_set):
        return True
    if any(t in exe_set for t in correct):
        return True
    return False


def find_issues(reply, passes, exe, dt, err, row):
    issues = []
    if err:
        return ["ERROR:" + err[:60]]
    r = (reply or "").strip()
    if not r:
        issues.append("empty_reply")
    if _LEAK_TOKENS.search(reply or ""):
        issues.append("special_token_leak")
    if _OLD_NAME.search(reply or ""):
        issues.append("old_name_gemma")
    if _FOOTER.search(reply or ""):
        issues.append("footer_or_meta_leak")
    if _OCR_ECHO.search(reply or ""):
        issues.append("ocr_echo")
    try:
        if detect_leaked_tool_call(reply or "", known_tool_names=KNOWN) is not None:
            issues.append("tool_call_leaked")
    except Exception:
        pass
    if not tool_match(exe, row["correct_tools"], row["also_valid"]):
        issues.append(f"tool_mismatch(exp={row['correct_tools']},got={exe})")
    # idioma: si el dataset marca un lang != es y el reply parece español, posible drift
    if row["lang"] in ("en", "pt", "fr", "de", "it") and r:
        # heurística mínima: marcadores de español fuertes en reply de turno no-es
        if re.search(r"\b(listo|abrí|cerré|qué|está|sí|también)\b", r, re.IGNORECASE):
            issues.append(f"lang_drift(exp={row['lang']})")
    if len(r) > MAXLEN:
        issues.append(f"reply_too_long({len(r)})")
    # LOOP GENUINO vs multi-tool inflado por el mock: el mock de execute devuelve
    # siempre {ok:True simulated}, lo que hace que el 4B reintente acciones que en
    # PRODUCCIÓN (tool real con resultado concreto) completaría en 1 pase. Verificado
    # en vivo: "génère une image", "mach leiser", "Baisse le son" loopeaban en el
    # eval pero NO en producción. Solo es loop REAL si el anti-loop guard tuvo que
    # cortar (el reply lo dice). El resto de many_passes/slow se marca como inflado
    # por el mock para no contarlo como bug.
    _genuine_loop = ("limite de turnos" in r.lower()
                     or "límite de turnos" in r.lower()
                     or "repitiendo la misma" in r.lower()
                     or "sin avanzar" in r.lower())
    if passes >= 4:
        issues.append(f"loop_genuine({passes})" if _genuine_loop
                      else f"many_passes_mock({passes})")
    if dt > SLOW_S:
        # un slow que viene de un multi-tool/loop NO es latencia genuina del turno
        issues.append(f"slow({dt:.1f}s)" if passes < 4
                      else f"slow_from_passes({dt:.1f}s)")
    return issues


# ---------------------------------------------------------------------------
# 4. Correr la evaluación
# ---------------------------------------------------------------------------
if OUT.exists():
    OUT.unlink()
t_start = time.time()
n_issues = 0
lat = []
issues_by_cat: "defaultdict[str, int]" = defaultdict(int)
issue_kinds: Counter = Counter()
total_by_cat: "defaultdict[str, int]" = defaultdict(int)

with OUT.open("a", encoding="utf-8") as out:
    for i, row in enumerate(rows):
        total_by_cat[row["category"]] += 1
        try:
            agent.history.clear()
        except Exception:
            pass
        if row["prev_text"]:
            try:
                agent.run_content(row["prev_text"])
            except Exception:
                pass
        executed.clear(); ncalls[0] = 0
        err = None
        t0 = time.perf_counter()
        try:
            reply = agent.run_content(row["user_text"])
            content = getattr(reply, "content", "") or ""
        except Exception as e:
            content = ""; err = f"{type(e).__name__}: {e}"
        dt = time.perf_counter() - t0
        lat.append(dt)
        issues = find_issues(content, ncalls[0], list(executed), dt, err, row)
        if issues:
            n_issues += 1
            issues_by_cat[row["category"]] += 1
            for it in issues:
                issue_kinds[it.split("(")[0]] += 1
        rec = {
            "i": i, "cat": row["category"], "lang": row["lang"],
            "user_text": row["user_text"], "prev_text": row["prev_text"],
            "dt": round(dt, 2), "passes": ncalls[0],
            "tools_exec": list(executed), "tools_expected": row["correct_tools"],
            "also_valid": row["also_valid"],
            "reply": content[:240], "issues": issues,
        }
        out.write(json.dumps(rec, ensure_ascii=False) + "\n"); out.flush()
        if (i + 1) % 20 == 0:
            el = time.time() - t_start
            eta = el / (i + 1) * (len(rows) - i - 1) / 60
            print(f"  {i+1}/{len(rows)}  issues={n_issues}  {el/(i+1):.1f}s/ej  ETA {eta:.0f}min", flush=True)

# ---------------------------------------------------------------------------
# 5. Reporte agregado (markdown + stdout)
# ---------------------------------------------------------------------------
el = time.time() - t_start
slat = sorted(lat)
p50 = slat[len(slat) // 2] if slat else 0
p90 = slat[int(len(slat) * 0.9)] if slat else 0
pmax = slat[-1] if slat else 0

lines = []
lines.append(f"# Mission eval — Baxy en vivo ({len(rows)} prompts, {len(chosen_cats)} categorías)\n")
lines.append(f"- Corridos: {len(rows)}  |  con issues: {n_issues} ({100*n_issues/max(1,len(rows)):.0f}%)")
lines.append(f"- Latencia: p50={p50:.2f}s  p90={p90:.2f}s  max={pmax:.2f}s  (umbral lento={SLOW_S}s)")
lines.append(f"- Tiempo total: {el/60:.1f} min\n")
lines.append("## Fallas por TIPO")
for k, n in issue_kinds.most_common():
    lines.append(f"- {n:4}  {k}")
lines.append("\n## Fallas por CATEGORÍA (priorizar las de arriba)")
for c in sorted(total_by_cat, key=lambda c: -issues_by_cat[c]):
    tot = total_by_cat[c]; bad = issues_by_cat[c]
    lines.append(f"- {bad:3}/{tot:<3} ({100*bad/max(1,tot):3.0f}%)  {c}")
lines.append(f"\nResultados crudos por prompt: `_mission_eval_results.jsonl`")
report = "\n".join(lines)
REPORT.write_text(report, encoding="utf-8")
print("\n" + report, flush=True)
print(f"\n[done] reporte -> {REPORT}", flush=True)
