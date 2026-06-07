"""Amplía el corpus del encoder del router con ejemplos 'abrir EN EL NAVEGADOR'
(incl. follow-ups 'abrelo en el navegador') que hoy NO tiene -> el encoder no
rankea browser arriba para esa intención (bug medido 2026-06-07: 've a pivigames'
no instalado -> 'abrelo en el navegador' caía a app). FUENTE: (1) los ejemplos
browser+navegador del dataset del LLM (curated.jsonl, multi-idioma, reales);
(2) follow-ups deícticos generados multi-idioma (abrelo/ábrelo/in browser...).

NO es hardcode de routing: alimenta el ENCODER (embeddings) con datos para que
APRENDA la asociación — universal, cualquier fraseo/idioma cae por similitud.

Salida: append a gemma4_agent/data/tool2vec_queries.jsonl (dedup). Reentrenar el
encoder después con scripts/router_ft_pipeline.py.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LLM_DATA = ROOT / "dataset_finetune" / "curated" / "curated.jsonl"
T2V = ROOT / "gemma4_agent" / "data" / "tool2vec_queries.jsonl"

# (1) extraer del dataset del LLM: comandos browser que mencionan el navegador
def from_llm():
    out = []
    if not LLM_DATA.exists():
        return out
    for line in LLM_DATA.open(encoding="utf-8"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        ut = (r.get("user_text") or "").strip()
        ct = r.get("correct_tools") or []
        low = ut.lower()
        # browser como tool Y señal de navegador en el texto -> ejemplo útil
        if "browser" in ct and any(k in low for k in (
                "navegador", "browser", "navigateur", "navegador", "en opera",
                "en chrome", "en el edge", "en firefox", "no navegador", "im browser")):
            out.append({"tool": "browser", "q": ut})
    return out

# (2) follow-ups deícticos multi-idioma (lo que falta: 'abrelo en el navegador'
# sin destino explícito — el referente lo resuelve el agente, pero el ENCODER
# debe rankear browser). Variedad real de fraseos, NO una plantilla rígida.
FOLLOWUPS = [
    # es (rioplatense + neutro)
    "abrelo en el navegador", "ábrelo en el navegador", "abrilo en el navegador",
    "abrila en el navegador", "ponelo en el navegador", "ponlo en el navegador",
    "mejor abrilo en el navegador", "no, en el navegador", "dale, en el navegador",
    "abrilo en el browser", "metelo en el navegador", "abrí eso en el navegador",
    "abrelo en chrome", "ábrelo en opera", "abrilo en el chrome", "ponelo en opera",
    "abrí eso en chrome", "abrila en firefox",
    # en
    "open it in the browser", "open that in the browser", "open it in chrome",
    "just open it in the browser", "no, in the browser", "put it in the browser",
    # pt
    "abre no navegador", "abra no navegador", "abre isso no navegador",
    "abre no chrome", "põe no navegador",
    # fr
    "ouvre-le dans le navigateur", "ouvre ça dans le navigateur",
    "ouvre dans le navigateur", "ouvre-le dans chrome",
    # de
    "öffne es im browser", "mach es im browser auf", "im browser öffnen",
    # it
    "aprilo nel browser", "aprilo nel navigatore", "apri nel browser",
]

def main():
    existing = set()
    if T2V.exists():
        for line in T2V.open(encoding="utf-8"):
            try:
                r = json.loads(line)
                existing.add((str(r.get("tool")), str(r.get("q")).strip().lower()))
            except Exception:
                pass
    new = []
    for item in from_llm() + [{"tool": "browser", "q": q} for q in FOLLOWUPS]:
        key = (item["tool"], item["q"].strip().lower())
        if key in existing:
            continue
        existing.add(key)
        new.append(item)
    with T2V.open("a", encoding="utf-8") as f:
        for item in new:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"agregados {len(new)} ejemplos browser-navegador al corpus del encoder")
    print(f"  ({len(from_llm())} del dataset LLM + {len(FOLLOWUPS)} follow-ups, dedup)")

if __name__ == "__main__":
    main()
