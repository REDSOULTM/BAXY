"""Alimenta el corpus del ENCODER del router con TODO el dataset curado del LLM
(una sola fuente de verdad: el mismo dataset que fine-tuneó el LLM entrena el
encoder). Mapea cada comando -> su tool (mono-tool 1:1; multi-tool -> primera tool
= la primaria/disparadora). EXCLUYE el holdout del encoder para no contaminar el
gate (dedup por query). Multi-idioma (es/en/pt/fr/de/it).

NO es hardcode: alimenta el encoder con datos reales etiquetados para que APRENDA
text->tool por embeddings — universal a cualquier fraseo/idioma.

Salida: append a tool2vec_queries.jsonl (dedup). Reentrenar con router_ft_pipeline.
Rollback: tool2vec_queries.jsonl.bak_pre_llm_2026-06-07.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# USAR train.jsonl, NO curated.jsonl: curated INCLUYE el holdout (1619 ej de
# evaluación). Meterlos al corpus del encoder es contaminación de datos (el encoder
# "ve" ejemplos de test). Higiene: solo el split de TRAIN. (Corrección 2026-06-07.)
LLM = ROOT / "dataset_finetune" / "curated" / "train.jsonl"
T2V = ROOT / "gemma4_agent" / "data" / "tool2vec_queries.jsonl"

# tools de INFRAESTRUCTURA que NO son "intención de dominio" — no enseñan routing
# de comando (son meta/verificación). No las agregamos como label de query.
_SKIP_TOOLS = {"session", "safety", "verify", "state"}


def main():
    existing = set()
    if T2V.exists():
        for line in T2V.open(encoding="utf-8"):
            try:
                r = json.loads(line)
                existing.add(str(r.get("q", "")).strip().lower())
            except Exception:
                pass

    new, mono, multi, skipped = [], 0, 0, 0
    for line in LLM.open(encoding="utf-8"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        ut = (r.get("user_text") or "").strip()
        ct = [t for t in (r.get("correct_tools") or []) if t and t not in _SKIP_TOOLS]
        if not ut or not ct:
            continue
        # plantilla-reply o gibberish: saltar (no es un comando real de routing)
        if r.get("reply_is_template") and len(ut.split()) <= 2:
            continue
        tool = ct[0]   # mono -> única; multi -> primaria (la disparadora)
        if len(ct) == 1:
            mono += 1
        else:
            multi += 1
        key = ut.strip().lower()
        if key in existing:
            skipped += 1
            continue
        existing.add(key)
        new.append({"tool": tool, "q": ut})

    with T2V.open("a", encoding="utf-8") as f:
        for item in new:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"agregados {len(new)} ejemplos del dataset LLM al corpus del encoder")
    print(f"  (mono-tool: {mono}, multi-tool->primaria: {multi}, dedup-skip: {skipped})")
    print(f"  corpus total ahora: {sum(1 for _ in T2V.open(encoding='utf-8'))}")

if __name__ == "__main__":
    main()
