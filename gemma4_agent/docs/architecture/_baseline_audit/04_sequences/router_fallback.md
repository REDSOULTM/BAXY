# 04.05 — Router fallback: regex no encuentra tool

> Cuándo: el usuario pide algo cuyo vocabulario no está en los buckets regex
> multilingües de `planner._suggest_tools`.
> **Fuente:** `planner.py:select_tool_names` + `semantic_router.suggest_tools_semantic` + `capability_classifier.augment_subset`.

## Cadena de fallbacks (4 niveles + último recurso)

```mermaid
sequenceDiagram
    autonumber
    participant AG as Gemma4Agent
    participant Sel as select_tool_names
    participant Sg as _suggest_tools (regex)
    participant CH as continuation hint (last_assistant)
    participant Sem as semantic_router
    participant ST as SentenceTransformer
    participant Cap as capability_classifier (async)
    participant NLI as nli_service (BG)

    AG->>Sel: select_tool_names(content, plan, ..., last_assistant_text)
    Sel->>Sg: _suggest_tools(text)
    Note over Sg: ~30 buckets regex multilingüe ES/EN/PT/FR/IT<br/>(media, audio, browser, filesystem, system, ...)

    alt regex matchea
        Sg-->>Sel: ["media", "browser"]
    else regex NO matchea
        Sg-->>Sel: []

        Sel->>CH: chequear continuation hint
        alt last_assistant pidió "perfil" + plataforma streaming<br/>AND text es corto (<=6 palabras o no acción)
            CH-->>Sel: insert "media" at front
        end

        alt aún vacío AND text >3 palabras AND no casual greeting
            Sel->>Sem: suggest_tools_semantic(text, k=12)
            Sem->>Sem: is_enabled()? (GEMMA4_SEMANTIC_FALLBACK)
            Sem->>Sem: _ensure_loaded()?
            alt model loaded
                Sem->>ST: encode(text) → 384d vec
                ST-->>Sem: query_emb
                Sem->>Sem: cosine vs tool_embeddings (62 tools)
                Sem->>Sem: filtrar score >= min_score=0.25
                Sem-->>Sel: top-k tools (or [] si nada >threshold)
            else model not loaded
                Sem-->>Sel: []
            end
        end

        alt aún vacío
            Note over Sel: ultimo recurso
            Sel-->>AG: ["session"] (+ "safety" si enabled)
        end
    end

    par paralelo SIEMPRE
        AG->>Cap: classify_capability_async(text)
        Cap->>NLI: classify_async(text, CAPABILITY_LABELS, callback)
        NLI->>NLI: BG thread carga mDeBERTa si no está
        NLI->>NLI: zero-shot classification (~1200ms primera vez)
        NLI-->>Cap: scores dict
        Cap->>Cap: cache_put(text, verdict)
        Note over Cap: lo de este turn NO afecta subset actual<br/>se usa en próximo turn similar (cache hit)
    end

    alt continuation tools heredados (gap < 300s)
        Sel->>Sel: si subset vacío + short input + has prev_tools<br/>→ heredar tools del turn anterior<br/>(filtra DANGEROUS_TOOLS_NEVER_INHERIT)
    end

    Sel-->>AG: subset final (cap MAX_SELECTED_TOOLS=16)
    Note over AG: session.cancel_turn siempre presente al final<br/>(después del cap, no se descarta)
```

## Negative anchor: drop "email" en caso ambiguo

`planner.py:160-163` tiene un caso especial: si el subset contiene `email` AND
el texto menciona "perfil/profile" pero NO menciona keywords de correo
(`mail|email|correo|courriel|posta|messaggio`), **se descarta email** porque
el semantic fallback a veces lo trae erróneamente por similitud léxica.

Es un parche reactivo a un bug observado.

## Hallazgos a `_findings_seed.md`

- **4 niveles de fallback + último recurso + paralelo NLI** = mucha lógica para una decisión que regresa "qué tools van al prompt".
- **`_suggest_tools` regex multilingüe ya marcada como HIGH** — esto reafirma. Las 30 buckets regex son la "primera línea". Si fallan, hay 3 capas más detrás que pagan latencia (especialmente NLI primera vez).
- **`semantic_router.min_score=0.25` hardcoded.** Si los embeddings cambian (modelo distinto, deps nuevas), el threshold puede ser óptimo o no.
- **`capability_classifier` lo único que hace en este turn es "cachear para el próximo"**. Para que aporte valor, el mismo input (o muy similar) tiene que repetirse. ¿Pasa eso seguido en producción? Verificar telemetry del cache hit rate (si Telemetry está activado).
- **Negative anchor "email + perfil sin mail keywords → drop email"** es un parche puntual. Si se acumulan más parches así, vale generalizar a un mecanismo de "anti-patterns" declarativo.
- **`MAX_SELECTED_TOOLS=16` cap + session siempre al final** — diseño defensivo OK.
