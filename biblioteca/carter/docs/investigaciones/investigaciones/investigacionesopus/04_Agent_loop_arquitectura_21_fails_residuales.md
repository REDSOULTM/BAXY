# Carter v4 — Arquitectura del Agent Loop: Investigación Técnica para Cerrar 21 Fails Residuales

## TL;DR

**El cuello de botella no es el modelo, es la arquitectura.** Con 96.1% PASS sobre 540 casos y los 21 fails residuales concentrados en C14/C13/C11, las tres palancas con mayor ROI son: (1) **planner-light estructural** disparado por heurística sintáctica multilingüe que rompe ReAct sólo cuando hay misión real, (2) **skill library Voyager-style en SQLite + FTS5/sqlite-vec** con crítico LLM perezoso, y (3) **error classifier mini-LLM** que decide retry/skip/replan/abort en el error path. Estimación combinada: cierra **12–15 de 21 fails** sin tocar runtime, modelo, ni latencia Alexa-tier para casos simples.

- **C14 misiones (5 fails) → cerrables 4/5** con planner-light + verifier orchestrator que declare PARTIAL honesto.
- **C13 GUI (3 fails) → cerrables 2/3** con error classifier que enrute a "replan con estrategia distinta" en `gui_action_failed` + skill library con recipes alternativas.
- **C11 terminal (3 fails) → cerrables 2/3** con planner-light + multi-tool batching paralelo cuando `read-set ∩ write-set = ∅`. Tool-RAG aporta marginal porque 47 tools está bajo el umbral (~30) donde el modelo empieza a confundirse seriamente.

---

## Key Findings

### 1. Heurística estructural multi-step sin keyword lists

Detectar "misión" sin diccionario de verbos por idioma se resuelve con **dependency parsing universal** (spaCy `xx_ent_wiki_sm` o, mejor, **UDPipe / Stanza** con Universal Dependencies que cubre 100+ idiomas con anotación homogénea). La señal que importa **no es el verbo**, es la estructura: dos o más cláusulas imperativas coordinadas (`conj`, `parataxis`) con sujetos elididos y objetos directos distintos. Funciona en es/en/pt/fr/de sin código por idioma.

Combinaciones diagnósticas (todas estructurales):
- `n_root_verbs ≥ 2` con relación `conj` o `parataxis` entre ellos.
- Presencia de marcadores secuenciales detectados como `advmod` adjuntados a verbos distintos (`luego`, `then`, `ensuite`, `dann` se detectan como POS=ADV con dep=advmod, no por matching de string — el parser ya los etiqueta).
- Longitud > 60 chars **y** ≥ 2 sintagmas verbales distintos (VERB con dep=ROOT/conj/xcomp).

Con 2 de 3 condiciones → activar planner. Costo: ~8–15 ms con `xx_sent_ud_sm` + parser. No rompe latencia Alexa.

### 2. Plan-and-Execute vs ReAct: cuándo conviene cada uno

LangChain documenta que plan-and-execute mejora task completion rate al "forzar al planner a pensar todos los pasos". Plan-and-Solve (Wang et al., ACL 2023) muestra mejoras consistentes sobre Zero-shot CoT, y específicamente reduce "missing-step errors" — exactamente el modo de fallo de C14 ("el modelo se rinde después del paso 2-3"). El planner debe devolver **lista de tool stubs** (tool name + intent NL en una línea), no args concretos: cada step resuelve sus args en runtime contra el estado actual del SO. Esto evita que un planner ciego congele variables que aún no existen.

**Híbrido recomendado**: ReAct puro como default; cuando la heurística estructural devuelve `is_mission=True`, se invoca un planner que llama una sola vez al modelo con un prompt fijo y devuelve `[(tool_intent, deps), ...]`. El executor mantiene el ReAct loop por step pero con `max_depth=2` y un summary acumulativo de pasos previos. Esto es lo que LangGraph llama "plan-and-execute" pero compactado a una sola pasada de planning + N pasadas de execute, sin replan iterativo (el replan se dispara sólo si error classifier devuelve `REPLAN`).

### 3. Skill library: aplicabilidad real de Voyager/FRIDAY a OS automation

Voyager (Wang et al., 2023, NVIDIA) demostró que skill library + retrieval por embedding del prompt actual permite reutilizar competencias y outperformar ReAct/Reflexion/AutoGPT en open-ended tasks. OS-Copilot/FRIDAY (Wu et al., ICLR 2024) demuestra que el patrón transfiere a tareas OS reales: +35% sobre métodos previos en GAIA, generalización a apps no vistas vía skills acumuladas. **La transferencia a Carter es directa**: una "skill" es un trazado `(prompt_normalizado, plan_steps_json, evidence_hash, score)` cuya retrieval ahorra el planning entero en repeticiones cercanas y ayuda al modelo en variantes.

El crítico LLM perezoso es clave: tras `COMPLETED` real (verifier dice `success=True`), se invoca un único call al mismo `qwen3:4b` con prompt: *"Score 0–10 cómo de generalizable es esta receta. Devuelve JSON: {score, reason}"*. Costo: 1 LLM call extra ~400ms **sólo en éxitos**, no en el path crítico de fail. Sólo recipes con `score≥7` se persisten.

Retrieval: **híbrido FTS5 + cosine** con Reciprocal Rank Fusion. Para una librería que crecerá a 500–5k recipes en producción doméstica, sqlite-vec con vectores de 384 dims (`paraphrase-multilingual-MiniLM-L12-v2`, multilingüe out-of-the-box) cabe en <50MB y consulta en <5ms. Inyectar como **few-shot en system prompt** (top-2, NO top-K grande) reduce confusión; el modelo Qwen3 trata mejor 2 ejemplos concretos que 5 abstractos.

### 4. Tool retrieval RAG: ROI real con 47 tools

RAG-MCP (arXiv 2505.03275) reporta el dato citable más concreto: tool selection accuracy **13.62% → 43.13%** y prompts -50% tokens. **Pero** el experimento clave es el "stress test" donde la degradación severa empieza alrededor de las **30 tools** y entra en colapso pasadas las 100. Con 47 tools Carter está en zona intermedia: se gana algo, pero no es el ROI dominante. Vale la pena implementarlo porque es barato (un embedding del prompt + top-15 tools) y ayuda específicamente a C11/C13 donde el modelo a veces "se olvida" de que existe `terminal_run` mientras está en GUI mode. **No es la palanca principal para los 21 fails**.

Berkeley Function Calling Leaderboard V3/V4 confirma que en multi-turn tool calling, modelos pequeños (<7B) caen sustancialmente cuando el catálogo crece y cuando hay irrelevance detection requerida. Qwen3-4B-Instruct-2507 está específicamente entrenado para tool use no-thinking; sus modos de fallo conocidos son: (a) language mixing con presence_penalty alto, (b) endless repetition cuando contexto se llena (recomendación oficial: `presence_penalty=1.5`, `temp=0.7`).

### 5. Loop detection: estado del arte vs el detector existente

Los 4 detectores actuales (`generic_repeat`, `unknown_tool_repeat`, `ping_pong`, `global_circuit_breaker`) cubren los modos clásicos. Lo que falta y la literatura reciente añade:

- **Result-aware detection**: hash incluye `(tool, args, result_signature)`, no sólo `(tool, args)`. Polling legítimo cambia output; loops no. Issue tracking del ecosistema (zeroclaw #2152) muestra que esto reduce dramáticamente falsos positivos.
- **Hidden cycle detection** (arXiv 2511.10650): detección de ciclos *semánticos* — secuencias de tool calls cuya unión semántica equivale a un ciclo previo aunque los args difieran. Reportan F1=0.72 combinando análisis estructural (call stack) + semántico (embedding del trace). Implementación: embedding de `tool_seq_signature` cada 3 calls, cosine vs ventana anterior; >0.92 → cycle.
- **Two-tier escalation**: en el primer match no abortar, **inyectar self-correction prompt** ("estás repitiendo X, prueba Y"); abortar sólo en el segundo match. Esto se alinea con Reflexion (Shinn et al., NeurIPS 2023): self-reflection verbal añade ~8% absoluto sobre memoria episódica sola.

### 6. Error classifier: vale los 300–500ms

SHIELDA (arXiv 2508.07935) y REIN (arXiv 2602.17022) ambos formalizan el patrón Mark-XXXIX: clasificador externo del error en categorías {RETRYABLE, SKIPPABLE, REPLAN_NEEDED, ABORT}. REIN reporta mejoras consistentes en task success y generalización a error types no vistos sin tocar el agente principal. **Coste real con qwen3:4b-q4_K_M en error path**: ~350–500ms. **Beneficio**: en C13 específicamente, un click GUI fallido hoy gatilla retry idéntico (porque ReAct no tiene contexto de que ya falló). Con classifier explícito, `gui_click_failed (target_not_found)` → REPLAN con estrategia "buscar coordenadas via screenshot + OCR", que es exactamente lo que falta. **Importante**: el classifier debe ser idempotente y no llamarse a sí mismo (no clasifica errores del classifier; si falla, cae a heurística determinística por error code).

### 7. Streaming + early termination con Ollama: NO es viable hoy

**Caveat empírico crítico**: el ecosistema Ollama tiene un bug documentado y abierto (issues #5796 y #12557, último confirmado octubre 2025) donde streaming + tool_calls **no emite chunks parciales del tool_call**: la respuesta llega entera con `done:true` o se pierde el tool_call. La recomendación canónica del proyecto es `stream:false` cuando hay tools. Esto invalida la idea de "detectar pre-emisión de tool_call y cortar". Solución alternativa para reducir TTFB: **paralelizar el primer token de no-tools con embedding del prompt + lookup en skill library**, y *si* skill library hit con score≥0.85, ejecutar plan cacheado sin esperar al modelo. Esto es lo que más reduce p50 latencia para casos repetidos.

### 8. Multi-tool batching seguro

Detección de independencia entre tool_calls del mismo turn vía **read/write set analysis**:
- Cada tool declara `reads={"fs:/path", "win:steam", "screen:"}` y `writes={...}` en el manifest.
- Dos tool_calls son paralelizables sii `(A.writes ∩ B.reads) ∪ (A.writes ∩ B.writes) ∪ (B.writes ∩ A.reads) = ∅`.
- GUI siempre se considera write a `screen:` y `win:focus`, lo que serializa GUI con todo lo que también lea/escriba pantalla — correcto y conservador.
- Filesystem reads paralelos OK; write+read sobre misma ruta → serial.

LangGraph implementa esto como Pregel/BSP: writes de un superstep visibles al siguiente. Para Carter basta un planificador greedy O(n²) sobre los tool_calls del turn (n≤5 en práctica).

### 9. Compaction strategies para qwen3:4b

MemGPT (arXiv 2310.08560) introduce el patrón OS-paging: main context (prompt) + external context (SQLite) con functions explícitas para mover info. Para un asistente local de turnos cortos, el patrón completo es overkill. **Recomendado**: hierarchical summary de 2 niveles, sweet spot **al 60%** (no 70%) del num_ctx para Qwen3-4B, ya que las recommendations de Qwen-team mencionan degradación de tool calling cerca del 80%. LLMLingua-2 puede aplicarse al working memory pero su small-LM compressor (~270M) suma latencia que no compensa para turnos de <8s. **A-MEM** (NeurIPS 2025) — Zettelkasten dinámico con linkage automático — es elegante pero su valor está en horizontes de días/semanas; para Carter es overengineering hoy.

### 10. Verifier orchestrator y honest-by-construction

El paper "The Art of Building Verifiers for CUA" (arXiv 2604.06240) formaliza 4 principios aplicables: rúbricas no solapantes, separar process reward de outcome reward, **cascading-error-free scoring** (un fail temprano no penaliza downstream), y atender screenshot evidence completo. Para Carter: verifier orchestrator recibe la cadena entera + estado SO inicial/final, declara `{COMPLETED, PARTIAL, FAILED}` con `evidence_steps` (qué pasos tienen prueba objetiva: file diff, window title change, exit code 0). PARTIAL es honesto cuando ≥1 step verifica pero no todos.

---

## Details — Código Python concreto

### A. Detector estructural de misión (sin keywords)

```python
# carter/agent/mission_detector.py
import spacy
from functools import lru_cache

# Modelo multilingüe UD-based; ~50MB, parsing ~10ms en CPU
_NLP = spacy.load("xx_sent_ud_sm")  # fallback: stanza con UD

def _imperative_like(token) -> bool:
    """Verbo en posición de raíz/conj que probablemente es imperativo.
    Heurística estructural: verbo finito, sujeto elidido o 2nd person."""
    if token.pos_ != "VERB":
        return False
    has_subject = any(c.dep_ in ("nsubj", "nsubj:pass") for c in token.children)
    morph = token.morph.to_dict()
    is_imp = morph.get("Mood") == "Imp"
    is_fin = morph.get("VerbForm") == "Fin"
    # imperativo explícito O verbo finito sin sujeto explícito (es/en/pt típico)
    return is_imp or (is_fin and not has_subject)

def detect_mission(prompt: str) -> dict:
    """Devuelve {is_mission: bool, score: float, signals: dict}.
    Sin listas de keywords. Estructural y multilingüe."""
    doc = _NLP(prompt.strip())
    roots = [t for t in doc if t.dep_ == "ROOT"]
    imperatives = [t for t in doc if _imperative_like(t)]
    coords = [t for t in doc
              if t.dep_ in ("conj", "parataxis") and t.pos_ == "VERB"]
    distinct_dobjs = {
        c.lemma_.lower()
        for v in imperatives + coords
        for c in v.children if c.dep_ in ("obj", "dobj", "obl")
    }
    seq_markers = sum(
        1 for t in doc
        if t.pos_ == "ADV" and t.dep_ == "advmod" and t.head.pos_ == "VERB"
    )
    signals = {
        "n_imperatives": len(imperatives),
        "n_coord_verbs": len(coords),
        "n_distinct_objects": len(distinct_dobjs),
        "n_seq_markers": seq_markers,
        "len_chars": len(prompt),
    }
    score = (
        (1.0 if len(imperatives) + len(coords) >= 2 else 0.0)
        + (0.6 if len(distinct_dobjs) >= 2 else 0.0)
        + (0.4 if seq_markers >= 1 else 0.0)
        + (0.3 if len(prompt) > 60 and len(roots) >= 1 else 0.0)
    )
    return {"is_mission": score >= 1.0, "score": score, "signals": signals}
```

Calibración inicial: umbral 1.0 produce ~10–15% de prompts marcados como misión sobre tráfico real esperado. Ajustar con audit matrix.

### B. Planner-light (single LLM call, devuelve stubs)

```python
# carter/agent/planner.py
import json
from carter.llm import chat_once  # wrap de ollama.chat con stream=False

PLANNER_SYS = """Eres un planner. Recibes una misión del usuario y devuelves
una lista mínima de pasos. Cada paso tiene:
- intent: descripción NL de qué hacer (no args concretos)
- tool_hint: nombre de tool del catálogo o "any"
- depends_on: índices de pasos previos cuyo resultado se necesita
Devuelve JSON: {"steps":[{"intent":"...", "tool_hint":"...", "depends_on":[]}]}
Máximo 6 pasos. Si la tarea es simple, devuelve 1 paso."""

def plan(user_prompt: str, tool_catalog_brief: str) -> list[dict]:
    raw = chat_once(
        model="qwen3:4b-instruct-2507-q4_K_M",
        messages=[
            {"role": "system",
             "content": PLANNER_SYS + "\n\nTOOLS:\n" + tool_catalog_brief},
            {"role": "user", "content": user_prompt},
        ],
        format="json",         # Ollama JSON mode
        options={"temperature": 0.2, "num_predict": 512},
    )
    try:
        steps = json.loads(raw)["steps"]
    except (json.JSONDecodeError, KeyError):
        return [{"intent": user_prompt, "tool_hint": "any", "depends_on": []}]
    return steps[:6]
```

### C. Skill library SQLite + retrieval híbrido

```python
# carter/memory/skills.py
import json, sqlite3, hashlib, time
import numpy as np
from sentence_transformers import SentenceTransformer

_EMB = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")  # 384d, ml

SCHEMA = """
CREATE TABLE IF NOT EXISTS skills(
  id INTEGER PRIMARY KEY,
  prompt TEXT NOT NULL,
  recipe_json TEXT NOT NULL,
  evidence_hash TEXT NOT NULL,
  score REAL NOT NULL,
  uses INTEGER DEFAULT 0,
  created_at REAL NOT NULL,
  embedding BLOB NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
  prompt, content='skills', content_rowid='id', tokenize='unicode61'
);
CREATE TRIGGER IF NOT EXISTS skills_ai AFTER INSERT ON skills BEGIN
  INSERT INTO skills_fts(rowid, prompt) VALUES (new.id, new.prompt);
END;
"""

class SkillStore:
    def __init__(self, path="carter.db"):
        self.con = sqlite3.connect(path)
        self.con.executescript(SCHEMA)

    def add(self, prompt, recipe, evidence_hash, score):
        if score < 7.0:
            return None
        emb = _EMB.encode(prompt, normalize_embeddings=True).astype(np.float32)
        self.con.execute(
            "INSERT INTO skills(prompt,recipe_json,evidence_hash,score,"
            "created_at,embedding) VALUES (?,?,?,?,?,?)",
            (prompt, json.dumps(recipe), evidence_hash, score,
             time.time(), emb.tobytes()),
        )
        self.con.commit()

    def retrieve(self, prompt, k=2, alpha=0.6):
        """Híbrido: cosine + FTS5 con RRF. alpha = peso vectorial."""
        q_emb = _EMB.encode(prompt, normalize_embeddings=True).astype(np.float32)
        rows = list(self.con.execute(
            "SELECT id, prompt, recipe_json, score, embedding FROM skills"))
        if not rows:
            return []
        # cosine (linear scan; OK hasta ~50k recipes)
        sims = []
        for rid, p, rj, sc, eb in rows:
            v = np.frombuffer(eb, dtype=np.float32)
            sims.append((rid, float(np.dot(v, q_emb)), p, rj, sc))
        sims.sort(key=lambda x: -x[1])
        vec_rank = {rid: i+1 for i, (rid, *_ ) in enumerate(sims)}
        # FTS5
        fts = list(self.con.execute(
            "SELECT rowid FROM skills_fts WHERE skills_fts MATCH ? LIMIT 50",
            (" OR ".join(prompt.split()[:8]),)))
        fts_rank = {rid: i+1 for i, (rid,) in enumerate(fts)}
        # RRF
        rrf_k = 60
        all_ids = set(vec_rank) | set(fts_rank)
        scored = []
        for rid in all_ids:
            r = (alpha * (1.0/(rrf_k + vec_rank.get(rid, 1e9)))
                 + (1-alpha) * (1.0/(rrf_k + fts_rank.get(rid, 1e9))))
            scored.append((r, rid))
        scored.sort(reverse=True)
        out = []
        by_id = {rid: (p, rj, sc) for rid, _, p, rj, sc in sims}
        for r, rid in scored[:k]:
            if rid in by_id:
                p, rj, sc = by_id[rid]
                out.append({"prompt": p, "recipe": json.loads(rj),
                            "score": sc, "rrf": r})
        return out
```

### D. Error classifier mini-LLM

```python
# carter/agent/error_classifier.py
import json
from carter.llm import chat_once

CLS_SYS = """Clasifica un error de tool execution en exactamente UNA categoría:
- RETRY: error transitorio, reintentar igual probablemente funciona
- SKIP: paso opcional, continuar con el siguiente
- REPLAN: hay que cambiar de estrategia (otra tool, otro approach)
- ABORT: error irrecuperable, detener la misión
Devuelve SOLO JSON: {"action":"RETRY|SKIP|REPLAN|ABORT","reason":"..."}"""

_DETERMINISTIC = {
    "TimeoutError": "RETRY",
    "ConnectionResetError": "RETRY",
    "PermissionError": "ABORT",
    "FileNotFoundError": "REPLAN",
}

def classify(tool_name, args, error_type, error_msg, attempt_idx):
    if attempt_idx >= 2 and error_type in _DETERMINISTIC:
        return {"action": _DETERMINISTIC[error_type], "reason": "deterministic"}
    if attempt_idx >= 3:
        return {"action": "ABORT", "reason": "max_attempts"}
    user = (f"tool={tool_name} args={json.dumps(args)[:200]} "
            f"err_type={error_type} err_msg={error_msg[:300]} "
            f"attempt={attempt_idx}")
    raw = chat_once(
        model="qwen3:4b-instruct-2507-q4_K_M",
        messages=[{"role":"system","content":CLS_SYS},
                  {"role":"user","content":user}],
        format="json",
        options={"temperature":0.0, "num_predict":80},
    )
    try:
        out = json.loads(raw)
        if out["action"] in {"RETRY","SKIP","REPLAN","ABORT"}:
            return out
    except Exception:
        pass
    return {"action":"REPLAN", "reason":"classifier_fallback"}
```

### E. Verifier orchestrator (PARTIAL honesto)

```python
# carter/agent/verifier_orchestrator.py
def declare_outcome(plan_steps, executed, evidence):
    """
    plan_steps: list[dict] del planner
    executed: list[dict] {step_idx, tool, ok, evidence_keys: set}
    evidence: dict[str, Any] - state diffs verificados (file_diff, window, etc.)
    Returns: {status, completed_steps, partial_steps, failed_steps, summary}
    """
    n = len(plan_steps)
    by_idx = {e["step_idx"]: e for e in executed}
    completed, partial, failed = [], [], []
    for i, step in enumerate(plan_steps):
        e = by_idx.get(i)
        if not e:
            failed.append(i); continue
        # criterio: step verificado sii tiene al menos una evidence_key con valor
        verified = any(k in evidence and evidence[k] for k in e["evidence_keys"])
        if e["ok"] and verified:
            completed.append(i)
        elif e["ok"] and not verified:
            partial.append(i)  # tool dice ok pero no hay evidencia objetiva
        else:
            failed.append(i)
    if len(completed) == n:
        status = "COMPLETED"
    elif len(failed) == n:
        status = "FAILED"
    else:
        status = "PARTIAL"  # honest by construction
    return {"status": status, "completed_steps": completed,
            "partial_steps": partial, "failed_steps": failed,
            "summary": f"{len(completed)}/{n} verified"}
```

---

## Tabla comparativa — Approaches

| Aspecto | ReAct puro (actual) | Plan-and-Execute puro | **Híbrido recomendado** |
|---|---|---|---|
| Latencia caso simple | 3–5s ✅ | 5–9s ❌ (planner siempre) | **3–5s ✅** (planner sólo si misión) |
| Tasa éxito multi-step | ~83% (C14) | ~92% est. | **~92%** est. |
| Coste tokens promedio | bajo | +30% | +5–8% (sólo en misiones) |
| Recuperación de errores | débil (loop o abort) | media (replan global) | **alta** (classifier + replan local) |
| Honest PARTIAL | no | parcial | **sí** (verifier orchestrator) |
| Compatibilidad SQLite/Ollama | sí | sí | **sí** |
| Esfuerzo implementación | — | alto (refactor loop) | **medio** (gate + planner + classifier) |

---

## Roadmap

**Fase 1 (1–2 semanas) — palancas baratas, alto ROI**
1. Implementar `mission_detector.py` + gate en `run_turn`. Mantener ReAct intacto en path "no misión".
2. `error_classifier.py` integrado entre tool execution y siguiente followup. Sólo activo en error path. Métrica: tasa de retry inútil (mismo tool+args+error 2 veces consecutivas) → debe caer >70%.
3. Extender `loop_detection.py` con result-aware hashing y two-tier escalation (inyectar self-correction prompt antes de abortar). Métrica: false-positive rate sobre logs históricos.

**Fase 2 (2–3 semanas) — capacidades nuevas**
4. `planner.py` + executor con stubs. Activar sólo si `mission_detector` dice sí. Verifier orchestrator declarando PARTIAL/COMPLETED. Métrica primaria: pass rate C14 (objetivo 28/30) y honest-PARTIAL rate (PARTIAL con evidence ≥1 step ≥ 95%).
5. Skill library SQLite + crítico LLM. Inyección top-2 como few-shot en system prompt sólo en path planner. Métrica: hit-rate de skill (% turnos con retrieval score>0.85) y delta de latencia en hits.

**Fase 3 (opcional, 2 semanas) — tuning**
6. Multi-tool batching con read/write sets en manifest de tools. Empezar con read-only batches (filesystem + window enumeration paralelos).
7. Tool-RAG top-15 sólo si experimentos muestran que el modelo confunde tools en C13/C11. ROI esperado modesto a 47 tools; revisitar cuando el catálogo cruce 80.
8. Compaction al 60% en lugar de 70%, con hierarchical summary de 2 niveles. Métrica: tool-calling accuracy en turnos largos (>8 tool calls).

**Métricas concretas a instrumentar desde día 1**
- `mission_detected_rate` (% turns marcados como misión).
- `mission_detected_to_completion_rate` (precisión del detector: de los marcados como misión, cuántos eran realmente >1 step).
- `verifier_status_distribution` (COMPLETED/PARTIAL/FAILED per categoría).
- `classifier_decisions` count por acción.
- `skill_hit_rate` y `skill_hit_pass_rate` (hits que terminan en COMPLETED).
- `p50/p95 latency` por tipo de turno (simple vs misión).
- Re-ejecutar audit matrix 540 al final de cada fase.

---

## Caveats — qué se afirma pero no se sostiene

1. **Streaming + tool_calls en Ollama es inestable hoy.** Issues #5796 y #12557 (último confirmado oct-2025) documentan que `stream:true` con `tools` rompe la emisión de `tool_calls` o entrega la respuesta entera con `done:true`. **No** se puede construir "early termination" de tool_call sobre streaming chunks con Ollama hoy. La técnica funciona en vLLM/SGLang pero está fuera del scope. Mantener `stream:false` durante turnos con tools y usar streaming sólo para la respuesta final user-facing.

2. **El "+35% sobre métodos previos" de FRIDAY/OS-Copilot** se mide en GAIA con GPT-4-turbo. La transferencia *quantitativa* a Qwen3-4B es un acto de fe; la transferencia *cualitativa* (skill library funciona en agentes OS) sí está bien soportada. No prometer números absolutos al stakeholder; prometer la dirección.

3. **RAG-MCP 13.62% → 43.13% se mide a 11.100 tool positions** (escala MCP), no con catálogos pequeños. A 47 tools la mejora esperable es del orden de 5–10 puntos absolutos en tool selection accuracy, **no** triplicación. La reducción de tokens del prompt sí es real y proporcional al recorte.

4. **Voyager** corre con GPT-4 y sintetiza skills como código JavaScript ejecutable. Para Carter las "skills" son recipes-as-data (lista de tool_intents), no código generado. Es un downgrade deliberado y necesario: ejecutar código sintetizado por un 4B local es una superficie de ataque y bug-surface inaceptable.

5. **Plan-and-Solve mejora reasoning, no necesariamente tool-use multi-step.** El paper original (ACL 2023) mide GSM8K, AQuA, SVAMP — tareas de razonamiento aritmético. La inferencia de que mejora tool-use multi-step es razonable y consistente con resultados de LangGraph plan-and-execute, pero no hay benchmark equivalente publicado para asistentes OS locales con modelos 4B. Validar empíricamente con C14 antes de generalizar.

6. **`xx_sent_ud_sm` de spaCy** tiene cobertura uneven: imperative-mood marking es excelente en es/en/fr/pt/de/it pero más ruidoso en idiomas con escritura no latina. Si el tráfico real incluye japonés/árabe/chino conviene usar **Stanza** con su modelo UD por idioma, ~3× más lento (~30ms) pero más preciso morfológicamente.

7. **Crítico LLM al final de turnos exitosos**: hay un riesgo no trivial de score-inflation (Qwen3-4B tiende a ser optimista). Mitigación: pedir evidence concreta en el prompt del crítico ("cita 2 razones por las que esta receta generaliza") y descartar si la justificación es genérica. Threshold 7.0 es conservador.

8. **Hierarchical summary al 60%**: el número es una recomendación basada en el comportamiento documentado de Qwen3-Instruct-2507 con tool calling en contexts largos. Validar con tu carga real; si num_ctx efectivo es 32k y los turnos típicos rondan 8–10k, el threshold actual 70% probablemente ya está bien y compactar antes desperdicia compute.

9. **El detector estructural no detectará** misiones expresadas como pregunta indirecta ("¿podrías abrir Steam y luego buscar Batman?"). En español la subordinación al condicional educado destruye la señal de imperativo. Esto **es aceptable**: caen al fallback ReAct, que ya las maneja en C14 con 25/30 — el detector no necesita ser perfecto, solo precisar bien sobre los casos que ReAct está fallando hoy.

10. **Hardware**: sentence-transformers `paraphrase-multilingual-MiniLM-L12-v2` corre en CPU a ~5ms/encode con batch=1 sobre x86 moderno; en ARM (RPi 5) sube a 30–40ms. Si Carter target incluye Raspberry Pi/NUC, considerar **`static-retrieval-mrl-en-v1`** (CPU-friendly, sin attention) o cachear embeddings de prompts vistos.