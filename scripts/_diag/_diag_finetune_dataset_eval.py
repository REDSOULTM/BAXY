"""Corre los ejemplos ÚNICOS del dataset de finetuning contra el LLM+agente REAL.

MISIÓN: para cada ejemplo único del dataset curado (dataset_finetune/curated/
curated.jsonl), inyectar el user_text por run_content (LLM real, ejecución física
MOCKEADA = seguro, cero SendInput) y registrar:
  - latencia (s), #pasadas LLM, tools ejecutadas, reply
  - tools ESPERADAS (correct_tools + also_valid del dataset) -> tool_match bool
  - issues (empty/leak/slow/error/tool_mismatch)
Así se diagnostica QUÉ falla, POR QUÉ, y se arregla.

Escribe incremental a _finetune_eval_results.jsonl (resume-friendly por OFFSET).

Uso: python scripts/_diag/_diag_finetune_dataset_eval.py [LIMIT] [OFFSET] [CATEGORY]
  LIMIT    cuántos correr (default todos)
  OFFSET   desde cuál (resume)
  CATEGORY filtrar por categoría del dataset (ej 'mensajeria'); '' = todas
"""
from __future__ import annotations
import json, os, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] else 1000000
OFFSET = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else 0
CATEGORY = sys.argv[3] if len(sys.argv) > 3 else ""
# STRATIFIED=1 -> muestrear proporcionalmente por categoría hasta LIMIT (en vez de
# tomar los primeros LIMIT, que son casi todos 'conversacion'). Cubre TODO el
# espectro de comandos en una corrida acotada por tiempo.
STRATIFIED = os.environ.get("GEMMA4_EVAL_STRATIFIED", "0") == "1"

DATASET = ROOT / "dataset_finetune" / "curated" / "curated.jsonl"
OUT = ROOT / "_finetune_eval_results.jsonl"

# SKIP de ejemplos ya corridos en una pasada previa (GEMMA4_EVAL_SKIP_FILE apunta
# a un JSON con [[user_text_low, prev_low], ...]). Para barrer el RESTO del dataset
# en una 2da corrida sin repetir lo ya medido.
_skip = set()
_skip_path = os.environ.get("GEMMA4_EVAL_SKIP_FILE", "")
if _skip_path and Path(_skip_path).exists():
    try:
        import json as _json
        for _k in _json.loads(Path(_skip_path).read_text(encoding="utf-8")):
            _skip.add((str(_k[0]).strip().lower(), str(_k[1]).strip().lower()))
        print(f"[skip] {len(_skip)} ejemplos ya vistos serán saltados", flush=True)
    except Exception as _e:
        print(f"[skip] no se pudo cargar skip-file: {_e}", flush=True)

# Cargar ejemplos ÚNICOS por (user_text, prev_text). Guardar ground-truth.
rows = []
seen = set()
for line in DATASET.read_text(encoding="utf-8", errors="replace").splitlines():
    if not line.strip():
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    ut = (d.get("user_text") or "").strip()
    if not ut:
        continue
    if CATEGORY and d.get("category") != CATEGORY:
        continue
    key = (ut.lower(), (d.get("prev_text") or "").strip().lower())
    if key in seen:
        continue
    seen.add(key)
    if key in _skip:          # ya medido en una corrida previa -> saltar
        continue
    rows.append({
        "user_text": ut,
        "prev_text": (d.get("prev_text") or "").strip(),
        "lang": d.get("lang", "?"),
        "category": d.get("category", "?"),
        "correct_tools": d.get("correct_tools") or [],
        "also_valid": d.get("also_valid") or [],
        "correct_reply_style": d.get("correct_reply_style") or "",
        "n_steps": d.get("n_steps", 1),
    })

if STRATIFIED and LIMIT < len(rows):
    # Muestreo estratificado proporcional por categoría, determinista (sin random:
    # tomamos cada k-ésimo de cada categoría para cubrir el rango). Round-robin
    # entre categorías para que ninguna domine la corrida acotada.
    from collections import defaultdict, OrderedDict
    by_cat = OrderedDict()
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    # cuántos por categoría, proporcional al tamaño, mínimo razonable.
    total = len(rows)
    picked = []
    quotas = {}
    for cat, items in by_cat.items():
        q = max(8, round(LIMIT * len(items) / total))
        quotas[cat] = min(q, len(items))
    # tomar cada k-ésimo de cada categoría (espaciado uniforme).
    for cat, items in by_cat.items():
        q = quotas[cat]
        step = max(1, len(items) // q)
        picked.extend(items[::step][:q])
    rows = picked[:LIMIT]
    print(f"[finetune-eval] ESTRATIFICADO: {len(rows)} ejemplos de {len(by_cat)} categorías", flush=True)
    from collections import Counter as _C
    for c, n in _C(r["category"] for r in rows).most_common():
        print(f"    {n:4} {c}", flush=True)
else:
    rows = rows[OFFSET:OFFSET + LIMIT]
print(f"[finetune-eval] {len(rows)} ejemplos únicos (offset={OFFSET}, cat={CATEGORY or 'ALL'})", flush=True)

# --- Boot del server real ---
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
mgr = get_shared_manager(); print("[boot]...", flush=True)
mgr.start(prof, wait_health=True, timeout_s=120); print("[boot] OK", flush=True)

from gemma4_agent.tools_pkg.tools import ToolRegistry, COMPOUND_TOOL_SCHEMAS
from gemma4_agent.infra import llm_client
from gemma4_agent.support.reasoning import detect_leaked_tool_call

KNOWN = {s["function"]["name"] for s in COMPOUND_TOOL_SCHEMAS
         if isinstance(s, dict) and isinstance(s.get("function"), dict)}

# MOCK de ejecución: registra el NOMBRE de la tool y NO ejecuta efectos físicos.
executed: list = []
_real_execute = ToolRegistry.execute
def _mock_execute(self, n, a):
    executed.append(n)
    return {"ok": True, "status": "ok", "verified": True, "_eval_mock": True}
ToolRegistry.execute = _mock_execute
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

_LEAK_TOKENS = re.compile(r"<intent>|</intent>|<unused\d+>|<\|tool_call|INTENT:")
# El nombre viejo "Gemma" como identidad del asistente es un fallo de marca (Baxy).
_OLD_NAME = re.compile(r"\bsoy gemma\b|\bgemma 4\b|\bme llamo gemma\b", re.IGNORECASE)


def tool_match(executed_tools, correct, also_valid):
    """¿Las tools ejecutadas concuerdan con el ground-truth? correct=[] significa
    'sin tool' (conversacional) -> match si no se ejecutó ninguna domain-tool.
    Si correct tiene tools, match si el SET ejecutado ⊇ las correctas (o iguala
    alguna combinación válida). Conservador: medimos el primer/principal tool."""
    exe = [t for t in executed_tools if t not in ("session", "safety", "state")]
    valid_sets = [set(correct)] + [{t} for t in also_valid] + [set(also_valid)]
    if not correct and not also_valid:
        return len(exe) == 0  # conversacional: no debía ejecutar tools
    exe_set = set(exe)
    # match exacto, o el principal correcto está entre los ejecutados
    if exe_set in valid_sets:
        return True
    if correct and set(correct).issubset(exe_set):
        return True
    if any(t in exe_set for t in correct):  # al menos la tool principal
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
    try:
        if detect_leaked_tool_call(reply or "", known_tool_names=KNOWN) is not None:
            issues.append("tool_call_leaked")
    except Exception:
        pass
    if not tool_match(exe, row["correct_tools"], row["also_valid"]):
        issues.append(f"tool_mismatch(exp={row['correct_tools']},got={exe})")
    if passes >= 4:
        issues.append(f"many_passes({passes})")
    if dt > 6.0:
        issues.append(f"slow({dt:.1f}s)")
    return issues


if OUT.exists() and OFFSET == 0:
    OUT.unlink()
t_start = time.time()
n_issues = 0
lat = []
with OUT.open("a", encoding="utf-8") as out:
    for i, row in enumerate(rows):
        try:
            agent.history.clear()
        except Exception:
            pass
        # prev_text: simular contexto previo si lo hay (follow-ups)
        if row["prev_text"]:
            try:
                agent.run_content(row["prev_text"])
                agent.history  # keep
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
        rec = {
            "i": i + OFFSET, "cat": row["category"], "lang": row["lang"],
            "user_text": row["user_text"], "prev_text": row["prev_text"],
            "dt": round(dt, 2), "passes": ncalls[0],
            "tools_exec": list(executed), "tools_expected": row["correct_tools"],
            "also_valid": row["also_valid"],
            "reply": content[:200], "issues": issues,
        }
        out.write(json.dumps(rec, ensure_ascii=False) + "\n"); out.flush()
        if (i + 1) % 25 == 0:
            el = time.time() - t_start
            eta = el / (i + 1) * (len(rows) - i - 1) / 60
            print(f"  {i+1}/{len(rows)}  issues={n_issues}  {el/(i+1):.1f}s/ej  ETA {eta:.0f}min", flush=True)

el = time.time() - t_start
p50 = sorted(lat)[len(lat)//2] if lat else 0
print(f"[done] {len(rows)} corridos, {n_issues} con issues, {el/60:.1f}min, p50={p50:.2f}s", flush=True)
