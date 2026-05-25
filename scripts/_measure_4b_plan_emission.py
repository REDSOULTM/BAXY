"""¿El 4B emite un PLAN estructurado de primitivas de forma fiable?

Decide el diseño de la capa de grounding universal: si el 4B sabe LISTAR los pasos
(aunque no los ENCADENE como acciones), la capa es un simple ejecutor de planes
(opción A, lo más universal). Si no, queda clasificar por embeddings (opción B).

Llama al server vram4 (:8080) DIRECTO con un prompt que pide un plan JSON con un
vocabulario CERRADO de primitivas. Mide parseable + correcto contra lo esperado.

GATE (definido ANTES): >=7/10 planes correctos y parseables -> opción A (ejecutor).
<7/10 -> opción B (clasificar verbo->primitiva por embeddings).
"""
import json, sys, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PRIMS = ["focus_app", "open_chat", "type", "send", "keypress", "click", "open_url"]

SYS = (
    "Sos un planificador de acciones de computer-use. Te doy un objetivo del usuario "
    "y devolvés SOLO un JSON: una lista de pasos. Cada paso es un objeto con \"op\" "
    "(una de: " + ", ".join(PRIMS) + ") y \"arg\" (string, o \"\" si no aplica).\n"
    "Primitivas:\n"
    "- focus_app: traer al frente la app. arg = nombre de app.\n"
    "- open_chat: abrir el chat/conversación de un contacto en una app de chat. arg = contacto.\n"
    "- type: teclear texto. arg = texto.\n"
    "- send: enviar (Enter). arg = \"\".\n"
    "- keypress: una tecla/combo. arg = la tecla (ej enter, ctrl+k).\n"
    "- click: clickear un control por nombre. arg = nombre.\n"
    "- open_url: navegar a una URL en el navegador. arg = url.\n"
    "Devolvé EXACTAMENTE el JSON, sin texto extra, sin markdown.\n"
    "Ejemplo objetivo: 'mandale hola a juan en discord' -> "
    '[{"op":"focus_app","arg":"discord"},{"op":"open_chat","arg":"juan"},'
    '{"op":"type","arg":"hola"},{"op":"send","arg":""}]'
)

# (objetivo, secuencia de ops esperada — ORDEN importa; args se chequean laxo)
CASES = [
    ("andá a discord al chat de cbayeah",
     ["focus_app", "open_chat"]),
    ("escribe a cbayeah en discord y dile que haces",
     ["focus_app", "open_chat", "type", "send"]),
    ("mandale a juan en discord nos vemos manana",
     ["focus_app", "open_chat", "type", "send"]),
    ("entrá a opera y andá a python.org",
     ["focus_app", "open_url"]),
    ("en opera entrá a github.com",
     ["focus_app", "open_url"]),
    ("abrí la calculadora y escribí 2+2 y apretá igual",
     ["focus_app", "type", "keypress"]),
    ("decile a GordoFriki que llego tarde",
     ["focus_app", "open_chat", "type", "send"]),
    ("entrá a discord al canal general",
     ["focus_app", "open_chat"]),
    ("escribí hola mundo en el bloc de notas",
     ["focus_app", "type"]),
    ("mandale buenas noches a pierosky por discord",
     ["focus_app", "open_chat", "type", "send"]),
]

def ask(goal):
    body = json.dumps({
        "model": "vram4-text",
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": goal}],
        "temperature": 0.0, "max_tokens": 256,
    }).encode()
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
                                 data=body, headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=60)
    data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]

def parse_plan(text):
    t = text.strip()
    # quitar fences markdown si los hay
    if "```" in t:
        t = t.split("```")[1] if t.count("```") >= 2 else t
        t = t.replace("json", "", 1).strip() if t.lstrip().lower().startswith("json") else t
    # tomar desde el primer [ hasta el último ]
    i, j = t.find("["), t.rfind("]")
    if i < 0 or j < 0:
        return None
    try:
        plan = json.loads(t[i:j+1])
        if isinstance(plan, list) and all(isinstance(s, dict) and "op" in s for s in plan):
            return plan
    except Exception:
        return None
    return None

print(f"=== ¿El 4B emite PLAN de primitivas? x{len(CASES)} ===", flush=True)
results = []
for goal, exp_ops in CASES:
    try:
        raw = ask(goal)
    except Exception as e:
        raw = f"ERR {e}"
    plan = parse_plan(raw)
    ops = [s.get("op") for s in plan] if plan else None
    parseable = plan is not None
    valid_ops = parseable and all(o in PRIMS for o in ops)
    # correcto = parseable + ops válidos + la SECUENCIA esperada es subsecuencia
    # ordenada del plan (toleramos pasos extra razonables, exigimos el orden núcleo).
    def is_subseq(small, big):
        it = iter(big)
        return all(x in it for x in small)
    correct = bool(valid_ops and is_subseq(exp_ops, ops))
    results.append({"goal": goal, "parseable": parseable, "valid_ops": valid_ops,
                    "ops": ops, "exp": exp_ops, "correct": correct,
                    "raw": raw.encode("ascii", "replace").decode()[:80]})
    print(f"  {'OK ' if correct else 'FAIL'} | ops={ops} | exp={exp_ops} | {goal[:38]!r}", flush=True)

n = sum(1 for r in results if r["correct"])
npars = sum(1 for r in results if r["parseable"])
out = ROOT / "scripts" / "gui_eval" / "_measure_4b_plan_results.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
verdict = "OPCIÓN A (ejecutor de planes)" if n >= 7 else "OPCIÓN B (embeddings verbo->primitiva)"
print(f"\n>> planes correctos: {n}/{len(CASES)} (parseables {npars}/{len(CASES)})  GATE>=7 -> {verdict}", flush=True)
print("WROTE", out, flush=True)
