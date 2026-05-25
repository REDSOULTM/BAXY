"""MARATÓN Fase 1 — LLM-direct: calidad del PLAN de primitivas que emite el 4B.

Genera cientos de comandos (apps × acciones × fraseos × idiomas) y mide si el plan
es PARSEABLE y CORRECTO (la secuencia núcleo de ops esperada es subsecuencia ordenada
del plan). NO toca la GUI -> corre en background sin robar foco. Resultados JSONL
incrementales (reanudable, observable). Verifica la capa de PLANIFICACIÓN universal,
que es la base del computer-use.

Uso: python scripts/_marathon_llm_plans.py [--max N] [--out PATH]
"""
import os, sys, json, time, argparse, itertools
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_AGENT_CONTEXT", "16384")

ap = argparse.ArgumentParser()
ap.add_argument("--max", type=int, default=100000)
ap.add_argument("--out", type=str, default=str(ROOT/"scripts"/"gui_eval"/"_marathon_llm.jsonl"))
args = ap.parse_args()

PRIMS = {"focus_app", "open_chat", "open_url", "type", "send", "keypress", "click"}

# ---- generador de comandos: (app, kind, comando, ops_núcleo_esperadas) ----
# Plantillas multi-idioma por TIPO de acción. {app}/{x}/{url}/{contact} se rellenan.
def gen_cases():
    cases = []
    # apps de chat (open_chat / mensaje)
    chats = ["discord", "whatsapp", "telegram"]
    contacts = ["juan", "maria", "cbayeah", "pierosky", "el grupo de la familia", "soporte"]
    # navegadores (open_url)
    browsers = ["opera", "chrome", "edge", "el navegador"]
    urls = ["python.org", "github.com", "wikipedia.org", "youtube.com", "gmail.com", "reddit.com"]
    # apps de texto (type / type+keypress)
    text_apps = ["la calculadora", "el bloc de notas", "word", "notepad"]
    exprs = ["2+2", "15*3", "100-58", "9*9", "hola mundo", "informe final", "reunion a las 5"]
    # apps a abrir/operar genérico
    apps_any = ["spotify", "steam", "paint", "explorador de archivos", "configuracion",
                "la calculadora", "el bloc de notas", "vlc", "obs"]

    # NAV a chat — fraseos ES/EN/PT
    nav_templates = [
        ("es", "andá a {app} al chat de {c}"),
        ("es", "entrá a {app} y abrí el chat de {c}"),
        ("es", "en {app} abrí la conversación con {c}"),
        ("es", "ponte en el chat de {c} en {app}"),
        ("en", "go to {app} and open the chat with {c}"),
        ("en", "in {app} open the conversation with {c}"),
        ("pt", "vá ao {app} e abra a conversa com {c}"),
    ]
    for app, c, (lang, tmpl) in itertools.product(chats, contacts, nav_templates):
        cmd = tmpl.format(app=app, c=c)
        cases.append((app, "open_chat", lang, cmd, ["focus_app", "open_chat"]))

    # MENSAJE — fraseos ES/EN/PT (focus, open_chat, type, send)
    msgs = ["hola que tal", "llego tarde", "nos vemos manana", "feliz cumple"]
    msg_templates = [
        ("es", "mandale a {c} en {app} que {m}"),
        ("es", "escribile a {c} por {app}: {m}"),
        ("es", "decile a {c} en {app} {m}"),
        ("en", "message {c} on {app} saying {m}"),
        ("pt", "manda pro {c} no {app} dizendo {m}"),
    ]
    for app, c, m, (lang, tmpl) in itertools.product(chats[:2], contacts[:3], msgs[:2], msg_templates):
        cmd = tmpl.format(app=app, c=c, m=m)
        cases.append((app, "message", lang, cmd, ["focus_app", "open_chat", "type", "send"]))

    # URL — fraseos ES/EN/PT (focus, open_url)
    url_templates = [
        ("es", "andá a {app} y entrá a {url}"),
        ("es", "en {app} entrá a {url}"),
        ("es", "abrí {url} en {app}"),
        ("es", "navegá a {url} en {app}"),
        ("en", "in {app} go to {url}"),
        ("en", "open {url} in {app}"),
        ("pt", "no {app} entra em {url}"),
    ]
    for app, url, (lang, tmpl) in itertools.product(browsers, urls, url_templates):
        cmd = tmpl.format(app=app, url=url)
        cases.append((app, "open_url", lang, cmd, ["focus_app", "open_url"]))

    # TEXTO en app (focus, type[, keypress])
    txt_templates = [
        ("es", "escribí {x} en {app}", ["focus_app", "type"]),
        ("es", "en {app} escribí {x}", ["focus_app", "type"]),
        ("es", "calculá {x} en {app}", ["focus_app", "type"]),
        ("es", "en {app} escribí {x} y apretá enter", ["focus_app", "type", "keypress"]),
        ("en", "type {x} in {app}", ["focus_app", "type"]),
        ("en", "in {app} write {x} and press enter", ["focus_app", "type", "keypress"]),
    ]
    for app, x, (lang, tmpl, ops) in itertools.product(text_apps, exprs, txt_templates):
        cmd = tmpl.format(app=app, x=x)
        cases.append((app, "type", lang, cmd, ops))

    # ABRIR/operar app (focus_app al menos)
    open_templates = [
        ("es", "abrí {app}"), ("es", "abrime {app}"), ("es", "andá a {app}"),
        ("en", "open {app}"), ("pt", "abre {app}"),
    ]
    for app, (lang, tmpl) in itertools.product(apps_any, open_templates):
        cmd = tmpl.format(app=app)
        cases.append((app, "focus_app", lang, cmd, ["focus_app"]))

    return cases


def is_subseq(small, big):
    it = iter(big)
    return all(x in it for x in small)


def main():
    from gemma4_agent.agent import Gemma4Agent
    from gemma4_agent.config import AgentConfig
    from gemma4_agent.computer_use import plan_for
    ag = Gemma4Agent(AgentConfig.from_env())
    ag.run_text("hola")  # warm

    cases = gen_cases()
    print(f"=== MARATÓN Fase 1 (LLM plan emission): {len(cases)} casos generados ===", flush=True)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # reanudable: contar cuántos ya hay
    done = 0
    if out.exists():
        done = sum(1 for _ in out.open(encoding="utf-8"))
        print(f"  reanudando: {done} ya hechos", flush=True)
    n_ok = n_parse = n = 0
    t0 = time.time()
    with out.open("a", encoding="utf-8") as f:
        for idx, (app, kind, lang, cmd, exp_ops) in enumerate(cases):
            if idx < done:
                continue
            if idx - done >= args.max:
                break
            t = time.time()
            try:
                plan = plan_for(ag, cmd)
            except Exception as exc:
                plan = None
            dt = time.time() - t
            parseable = plan is not None
            ops = [s["op"] for s in plan] if plan else None
            correct = bool(parseable and is_subseq(exp_ops, ops))
            n += 1; n_parse += parseable; n_ok += correct
            rec = {"i": idx, "app": app, "kind": kind, "lang": lang, "cmd": cmd,
                   "exp": exp_ops, "ops": ops, "parseable": parseable,
                   "correct": correct, "lat": round(dt, 2)}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
            if n % 20 == 0:
                el = time.time() - t0
                print(f"  [{n}] correct {n_ok}/{n} ({100*n_ok//n}%) parse {n_parse}/{n} "
                      f"| {el/n:.1f}s/caso | last: {kind} {lang} {'OK' if correct else 'FAIL'}", flush=True)
    print(f"\n>> Fase 1: correct {n_ok}/{n} ({100*n_ok//max(n,1)}%), parseable {n_parse}/{n}", flush=True)
    print("WROTE", out, flush=True)


if __name__ == "__main__":
    main()
