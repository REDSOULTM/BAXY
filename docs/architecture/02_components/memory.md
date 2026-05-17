# 02.06 — Memory & Knowledge + Skills/Microagents/Personas

> **Containers:** Memory & Knowledge + Skills/Microagents/Personas.
> **Archivos:** `memory.py`, `experience.py`, `knowledge.py`,
> `skills_registry.py`, `microagents.py`, `personas.py`.
> **Total LOC:** 1 862.
> **Responsabilidad:** todo lo que enriquece el system prompt o sirve datos
> al agente sin ser una tool: memoria explícita, experience replay, RAG
> documental, skills declarativas, microagents-por-trigger, personas.

## Componentes

| # | Archivo | Símbolo principal | LOC | Storage | Modelo externo | Propósito |
|--:|---|---|--:|---|---|---|
| 1 | `memory.py` | `MemoryStore` (1 clase + 2 helpers sanitize) | 187 | `data/memory.json` | — | Facts user-facing: "user_name=emma", "platform=disney". Tool `memory` lo expone |
| 2 | `experience.py` | `ExperienceMemory` (5 funciones top-level + clase 371 LOC) | 489 | `data/experience.sqlite` con `experiences` + `experience_vec` virtual table | MiniLM 384d (reusa el del semantic_router) | Replay tipo Voyager: turn pasados embeddeados + buscables por similitud |
| 3 | `knowledge.py` | `KnowledgeStore` (1 clase) + `_rerank_rows()` + `_load_reranker()` | 253 | `data/knowledge.sqlite` con `documents` + `chunks` FTS5 virtual table | (opcional) cross-encoder ms-marco-MiniLM-L-6-v2 (~80 MB) | Ingesta de docs del usuario + RAG con BM25 + opcional rerank |
| 4 | `skills_registry.py` | `SkillMeta` + `scan_skills()` + `build_menu()` + `build_critical_block()` + `load_skill_content()` + parser YAML "simple" | 456 | filesystem `skills/<name>/SKILL.md` (10 carpetas) | — | Lazy "recetas" enchufables. Spec Anthropic Agent Skills + extensiones (priority, requires) |
| 5 | `microagents.py` | `Microagent` + `build_microagents_section()` + parser frontmatter | 351 | filesystem `microagents/*.md` (5 archivos) | — | Eager-por-trigger. Inyecta knowledge cuando el user_text matchea substrings |
| 6 | `personas.py` | `Persona` dataclass + `PERSONAS` dict (6 personas) | 126 | hardcoded en código | — | Tono + preferred_tools nudges. Seleccionable por env `GEMMA4_AGENT_PERSONA` o `/persona` CLI |

## Las 3 memorias en una sola foto

```mermaid
%% Fig 2.11 — Tres memorias paralelas con propósitos distintos
graph LR
    subgraph mem["MemoryStore — JSON explícito"]
        MJ[MemoryStore<br/>memory.py 187 LOC]
        MJfile[(data/memory.json<br/>items dict)]
        MJtool[tool memory<br/>save/recall/list/delete]
    end

    subgraph exp["ExperienceMemory — semantic replay"]
        EM[ExperienceMemory<br/>experience.py 489 LOC]
        EMdb[(data/experience.sqlite<br/>experiences + experience_vec)]
        EMembed[reusa MiniLM<br/>de semantic_router]
        EMfmt[format_recall_for_prompt]
    end

    subgraph kn["KnowledgeStore — RAG documental"]
        KS[KnowledgeStore<br/>knowledge.py 253 LOC]
        KSdb[(data/knowledge.sqlite<br/>documents + chunks FTS5)]
        KSrerank[cross-encoder reranker<br/>ms-marco-MiniLM]
        KStool[tool knowledge<br/>ingest/search]
    end

    Agent[Gemma4Agent]
    UT[user_text]

    Agent -- "save/recall via tool" --> MJ
    MJ --> MJfile
    Agent -- "_recent_recalls in system_prompt" --> MJ

    Agent -- "record turn (post)" --> EM
    Agent -- "search topK by similarity (pre)" --> EM
    EM --> EMdb
    EM --> EMembed
    EM --> EMfmt
    EMfmt -- "format_recall_for_prompt(_recent_recalls)" --> Agent

    Agent -- "tool knowledge → ingest/search" --> KS
    KS --> KSdb
    KS -. "opt rerank" .-> KSrerank
```

### Tabla comparativa

| | MemoryStore | ExperienceMemory | KnowledgeStore |
|---|---|---|---|
| **Qué guarda** | facts explícitos (key/value strings) | turns pasados con embedding | docs del usuario chunked |
| **Cómo se crea** | LLM llama tool `memory(action="save")` | escritura automática post-turn | LLM llama tool `knowledge(action="ingest")` |
| **Cómo se lee** | LLM llama tool `memory(action="recall")` o `prompt_summary()` directo en system_prompt | top-K búsqueda por similitud, inyectado en system_prompt | LLM llama tool `knowledge(action="search")` |
| **Storage** | 1 archivo JSON (~tiny) | 1 SQLite + virtual table sqlite-vec (crece) | 1 SQLite + FTS5 virtual table (crece) |
| **Modelo ML** | — | MiniLM (compartido con router) | (opcional) cross-encoder ms-marco |
| **Opt-out** | `GEMMA4_AGENT_MEMORY` (path override) | `GEMMA4_EXPERIENCE_MEMORY=false` | `GEMMA4_KNOWLEDGE_RERANK=false` (solo el reranker) |
| **Limpieza** | `MAX_TOTAL_ITEMS=500` cap; sin TTL | `prune()` por `_AUTO_PRUNE_EVERY=50` + `_DEFAULT_MAX_RECORDS=5000` + `_DEFAULT_MAX_AGE_DAYS=180` | manual via `delete(doc_id)` |

**No son redundantes.** Cada una tiene un propósito ortogonal:
- `MemoryStore` = "lo que el usuario dijo de sí mismo o quiere que recuerde".
- `ExperienceMemory` = "qué hizo el agente en turns parecidos antes".
- `KnowledgeStore` = "qué dicen los documentos del usuario".

Pero las **3 SQLite + 1 JSON + 1 archivo de profile + 1 archivo de gui.json = 6 stores** distribuidos en `data/` y `~/.gemma4/`. Para Fase 5 dejo el inventario completo.

## Skills + Microagents + Personas — 3 capas declarativas de system_prompt enrichment

```mermaid
%% Fig 2.12 — Skills + Microagents + Personas
graph TB
    subgraph user["entrada"]
        UT[user_text]
    end

    subgraph sk["skills_registry.py — LAZY, 456 LOC"]
        SC[scan_skills<br/>scan skills/*/SKILL.md]
        SF[(skills/<br/>10 carpetas)]
        SP[_parse_yaml_simple<br/>parser propio]
        BM[build_menu<br/>1 línea por skill]
        BC[build_critical_block<br/>body completo<br/>solo priority=critical]
        SL[load_skill_content<br/>tool skill_load]
    end

    subgraph mc["microagents.py — EAGER por trigger, 351 LOC"]
        MS[scan_microagents<br/>microagents/*.md]
        MF[(microagents/<br/>5 archivos)]
        BMA[build_microagents_section<br/>match triggers vs user_text<br/>cap 3 por turn]
    end

    subgraph pe["personas.py — hardcoded, 126 LOC"]
        PE[PERSONAS dict<br/>6 personas: default/coder/researcher/<br/>creative/planner/casual]
        FE[from_env<br/>GEMMA4_AGENT_PERSONA]
    end

    Agent[Gemma4Agent._system_message]
    SysP[system_prompt final]

    SC --> SF
    SC --> SP
    SC --> BM
    SC --> BC
    Agent -- "cache instancia" --> SC
    BM -- "skill menu (compact)" --> SysP
    BC -- "critical skills (full body)" --> SysP
    Agent -- "tool skill_load" --> SL

    MS --> MF
    MS --> BMA
    UT --> BMA
    BMA -- "matched bodies" --> SysP
    Agent -- "cache instancia _cached_microagents" --> BMA

    Agent --> FE --> PE
    PE -- "persona.system_hint" --> SysP
```

### Tabla comparativa

| | Skills | Microagents | Personas |
|---|---|---|---|
| **Carga al system_prompt** | lazy (menu small + load explícito por tool) + critical eager | eager por trigger (substring match en user_text) | eager (1 por sesión) |
| **Selector** | LLM decide qué cargar | substring matching de keywords | env var o `/persona` CLI |
| **Storage** | `skills/<name>/SKILL.md` con frontmatter YAML | `microagents/*.md` con frontmatter YAML | dict hardcoded en `personas.py` |
| **Cantidad actual** | 10 skills | 5 microagents | 6 personas |
| **Opt-out** | `GEMMA4_SKILLS_OFF=1` | `GEMMA4_MICROAGENTS_OFF=1` | n/a (default persona = identity) |
| **Cap defensivo** | por profile (1/2/3/5) | `max_microagents=3` | no aplica |
| **Modifica preferred_tools del subset** | no | no | sí (`persona.preferred_tools` se mergea en planner) |

## Hallazgos

| Sev | Hallazgo | Ubicación |
|---|---|---|
| **HIGH** | **Skills + Microagents = dos sistemas declarativos paralelos para enriquecer el system_prompt** (807 LOC combinados). El docstring del propio `skills_registry.py:16-20` dice "Diferencia vs microagents". Esta auto-justificación es señal de que la separación es delicada. Si en producción un skill termina sirviendo lo que un microagent serviría, hay duplicación de propósito (no de código). | `skills_registry.py` + `microagents.py` |
| **HIGH** | `skills_registry._parse_yaml_simple` (74 LOC) es un **YAML parser artesanal** que cubre "scalars + inline lists + block sub-dict/sub-lists indentados con 2 espacios + booleans". Repo NO tiene `pyyaml` como dependencia. Pero el comentario del propio docstring dice "NO soporta block scalar `\|`, anchors, ni tipos complejos". Si los SKILL.md siempre son simples, esto está bien; si un autor escribe un `description:` multi-línea, parsea silenciosamente mal. Considerar `pyyaml` (1 dep, 0 LOC propias). | `skills_registry.py:107-180` |
| **HIGH** | `microagents.py` también parsea frontmatter YAML por su cuenta (otro parser distinto, `_FRONTMATTER_RE` regex). **Dos parsers caseros de YAML en el repo.** | `microagents.py:78` |
| **MED** | `personas.py` con 6 personas hardcoded. ¿Cuántas se usan en producción? Si el dueño usa solo `default` y `coder`, las otras 4 son código. | `personas.py:33-112` |
| **MED** | `personas.py:53` `preferred_tools=("developer", "filesystem", "terminal", "document", "fact_check", "knowledge")` — 6 tools "preferidas". El comentario dice que se mergean al planner subset. Verificar en `Gemma4Agent._select_subset` si la lista efectivamente entra antes del cap MAX_SELECTED_TOOLS=16 o si se descarta. | `personas.py` |
| **MED** | `experience.py:106-120` define **5 columnas ALTER TABLE wrapped en try/except** (provenance fields: `outcome_code`, `failure_reason_code`, `args_signature`, `capability_label`, `grounding_flagged`). Patrón de migración honesto pero `except sqlite3.OperationalError: pass` traga errores genuinos (disk full, etc). | `experience.py:110-120` |
| **MED** | `experience.flag_grounding` y `flag_grounding_by_turn` son **dos métodos casi idénticos** que difieren solo en si el lookup es por `id` o `turn_id`. Las dos hacen el mismo UPDATE. Colapsable a un solo método con un selector. | `experience.py:202-248` |
| **LOW** | `knowledge._chunk_text` con `max_chars=2200, overlap=250` hardcoded en kwargs default. No expuesto al usuario ni configurable por documento. | `knowledge.py:233` |
| **LOW** | `knowledge._fts_query` arma `"term1" OR "term2" OR ...` hasta `[:12]` términos. Si el query tiene 13+ palabras (raro pero posible), se silenciosamente truncado. | `knowledge.py:249-253` |
| **LOW** | `MemoryStore.MAX_TOTAL_ITEMS=500` cap pero no hay TTL ni LRU; el primero en llegar al cap bloquea writes. | `memory.py:18` |
| **NIL** | `state.atomic_write_json` reusado por `sessions.py` y `profiles.py`. Buena reutilización. | `state.py:19-30` |

## DOT backup

```dot
digraph Memory {
    rankdir=TB; node [shape=box, style=rounded];
    Agent; UT [shape=ellipse];
    MJ [label="MemoryStore"]; MJfile [shape=cylinder, label="memory.json"];
    EM [label="ExperienceMemory"]; EMdb [shape=cylinder, label="experience.sqlite"];
    KS [label="KnowledgeStore"]; KSdb [shape=cylinder, label="knowledge.sqlite"];
    SC [label="skills_registry"]; SF [shape=cylinder, label="skills/"];
    MS [label="microagents"]; MF [shape=cylinder, label="microagents/"];
    PE [label="personas (hardcoded)"];
    SysP [label="system_prompt"];

    Agent -> MJ -> MJfile; Agent -> EM -> EMdb; Agent -> KS -> KSdb;
    SC -> SF; MS -> MF; UT -> MS;
    SC -> SysP; MS -> SysP; PE -> SysP;
}
```
