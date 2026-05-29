"""MARATÓN Fase 3 — STRESS del planner: idiomas extra (FR/DE/IT), cadenas multi-paso,
fraseos adversariales/con typos. LLM-direct (no GUI). Busca DÓNDE se rompe el planner
universal (encontrar bugs reales, no confirmar lo que ya anda). JSONL incremental.
"""
import os, sys, json, time, itertools
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMMA4_AGENT_CONTEXT", "16384")

PRIMS = {"focus_app","open_chat","open_url","type","send","keypress","click"}

def gen():
    cases=[]
    # IDIOMAS EXTRA (fr/de/it) — mismas acciones, debe planificar igual
    extra = [
        # (lang, cmd, ops_núcleo)
        ("fr","ouvre la calculatrice et tape 2+2",["focus_app","type"]),
        ("fr","va sur opera et ouvre python.org",["focus_app","open_url"]),
        ("fr","écris bonjour dans le bloc-notes",["focus_app","type"]),
        ("fr","envoie un message à juan sur discord disant salut",["focus_app","open_chat","type","send"]),
        ("de","öffne den Rechner und tippe 5*5",["focus_app","type"]),
        ("de","geh zu opera und öffne github.com",["focus_app","open_url"]),
        ("de","schreibe hallo in den Editor",["focus_app","type"]),
        ("de","schick juan auf discord eine Nachricht hallo",["focus_app","open_chat","type","send"]),
        ("it","apri la calcolatrice e digita 9+1",["focus_app","type"]),
        ("it","vai su opera e apri wikipedia.org",["focus_app","open_url"]),
        ("it","scrivi ciao nel blocco note",["focus_app","type"]),
        ("it","manda a juan su discord il messaggio ciao",["focus_app","open_chat","type","send"]),
    ]
    for lang,cmd,ops in extra:
        for _ in range(3):  # repetir para estabilidad
            cases.append(("multi",lang,cmd,ops))
    # CADENAS multi-paso (2-3 apps/acciones en un comando)
    chains = [
        ("es","abrí la calculadora y calculá 7*8",["focus_app","type"]),
        ("es","en opera entrá a github.com y después a python.org",["focus_app","open_url","open_url"]),
        ("es","abrí el bloc de notas y escribí hola y apretá enter",["focus_app","type","keypress"]),
        ("es","andá a discord al chat de juan y escribile que llego",["focus_app","open_chat","type"]),
        ("en","open calculator type 3+3 and press enter",["focus_app","type","keypress"]),
        ("en","go to opera open reddit.com then youtube.com",["focus_app","open_url","open_url"]),
    ]
    for lang,cmd,ops in chains:
        for _ in range(4):
            cases.append(("chain",lang,cmd,ops))
    # ADVERSARIAL: typos, fraseo raro, abreviado
    adv = [
        ("es","kalkuladora 2+2",["focus_app","type"]),
        ("es","ponme spotify",["focus_app"]),
        ("es","discord chat de juan",["focus_app","open_chat"]),
        ("es","opera python punto org",["focus_app","open_url"]),
        ("es","escribi en el block de notas: prueba",["focus_app","type"]),
        ("en","calc 8x8",["focus_app","type"]),
        ("en","disc msg juan hi",["focus_app","open_chat","type","send"]),
    ]
    for lang,cmd,ops in adv:
        for _ in range(4):
            cases.append(("adversarial",lang,cmd,ops))
    return cases

def is_subseq(small,big):
    it=iter(big); return all(x in it for x in small)

def main():
    from gemma4_agent.agent_core.agent import Gemma4Agent
    from gemma4_agent.infra.config import AgentConfig
    from gemma4_agent.computer_use_pkg.computer_use import plan_for
    ag=Gemma4Agent(AgentConfig.from_env()); ag.run_text("hola")
    cases=gen()
    out=ROOT/"scripts"/"gui_eval"/"_marathon_p3.jsonl"; out.parent.mkdir(parents=True,exist_ok=True)
    done=sum(1 for _ in out.open(encoding="utf-8")) if out.exists() else 0
    print(f"=== Fase 3 STRESS: {len(cases)} casos (idiomas extra/cadenas/adversarial), {done} hechos ===",flush=True)
    n=ok=par=0
    with out.open("a",encoding="utf-8") as f:
        for idx,(kind,lang,cmd,exp) in enumerate(cases):
            if idx<done: continue
            try: plan=plan_for(ag,cmd)
            except Exception: plan=None
            parseable=plan is not None
            ops=[s["op"] for s in plan] if plan else None
            correct=bool(parseable and is_subseq(exp,ops))
            n+=1; ok+=correct; par+=parseable
            f.write(json.dumps({"i":idx,"kind":kind,"lang":lang,"cmd":cmd,"exp":exp,"ops":ops,"parseable":parseable,"correct":correct},ensure_ascii=False)+"\n"); f.flush()
            if n%15==0: print(f"  [{n}] correct {ok}/{n} ({100*ok//n}%) parse {par}/{n} | last {kind}/{lang} {'OK' if correct else 'FAIL'}",flush=True)
    print(f"\n>> Fase 3: correct {ok}/{n} ({100*ok//max(n,1)}%), parseable {par}/{n}",flush=True)
    print("WROTE",out,flush=True)

if __name__=="__main__": main()
