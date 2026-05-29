# Gestión de historial multi-turno en Gemma 4 E4B-it Q4_K_M sobre llama.cpp b9090 (ctx 16K): plan técnico para asistente de voz local

## TL;DR
- **Para asistente de voz, casi todos los turnos son atómicos**: la evidencia (Apple ML Research "Learning to Rank Intents", Amazon Alexa skill routing, Laban et al. 2025) muestra que el contexto previo solo importa cuando el turno actual contiene anáfora/deixis ("súbelo", "ese", "el otro"); detectarlos con regex + un clasificador opcional de <30 ms y **enviar contexto sólo cuando es necesario** es la palanca de mayor impacto: reduce el prompt total de ~7875 a ~1500–2000 tokens en >70% de los turnos.
- **Hay un bug abierto crítico en llama.cpp para Gemma 4 (#21468)**: en build 8660 (commit d006858) y posteriores no fixeados, `--cache-reuse` no funciona con `gemma-4-E4B-it-GGUF` por la arquitectura de *Shared KV Cache* (las últimas `num_kv_shared_layers` reutilizan K/V de la última capa no-shared); el log muestra `cache reuse is not supported - ignoring n_cache_reuse = 256` y fuerza reprocesado completo (~96 s sobre 46K tokens en el caso reportado). Issue abierto, sin PR de fix al 23-may-2026. Mientras no haya solución, la estrategia ganadora es **mantener el prefijo CORE LEAN de ~920 tokens estable byte-a-byte y minimizar el tail variable** (compactación agresiva + summary anclado al boundary del turno, nunca al medio del prefijo).
- **A 16K con un modelo 4B la degradación empieza mucho antes del límite**: Laban et al. 2025 ("LLMs Get Lost in Multi-Turn Conversation", arXiv:2505.06120, Microsoft + Salesforce Research, 200 000+ conversaciones simuladas) mide una caída promedio del **39% single→multi-turn** y específicamente **30–40% en Llama3.1-8B-Instruct y Phi-4**; el mecanismo identificado verbatim es: *"when LLMs take a wrong turn in a conversation, they get lost and do not recover"*. Chroma *Context Rot* (Hong/Troynikov/Huber, jul 2025) confirma degradación **no-uniforme** desde mucho antes del límite en los 18 modelos frontera testeados. **Política recomendada**: presión de contexto en 3 bandas (50% / 70% / 85%) con resumen anclado (nunca recursivo) y reset suave si la conversación lleva > 6 turnos sin referencia anafórica.

## Hallazgos clave

1. **El historial completo casi nunca importa en comandos de voz.** La literatura industrial de NLU (Apple "Learning to Rank Intents", Amazon Alexa skill routing) y la práctica open-source (Home Assistant Assist 2025) coinciden: el dialog manager se apoya en *slots* e *intents* del turno actual; sólo se necesita historial cuando la utterance es deíctica/anafórica. Eckert & Strube (2000), aún el dato cuantitativo de referencia citado por CODI-CRAC 2022, midió **22.6% de anáforas no-NA en diálogo hablado**. Esto justifica una arquitectura *context-as-router-input*: el contexto se inyecta sólo cuando el router detecta dependencia.

2. **El prefijo se invalida ante cualquier cambio byte-a-byte.** `--cache-reuse N` busca un *common prefix* y aplica KV-shifting (`llama_kv_cache_seq_rm` + `seq_add`) en chunks ≥ N; cualquier inserción intermedia invalida el cache desde ese punto. Para modelos SWA (Gemma) sin `--swa-full`, el reuse está limitado al tamaño de la ventana deslizante (1024 tokens en Gemma 3; 512 en las small variants de Gemma 4 según las model cards). **Importante para tu stack**: en Gemma 4 E4B con `--swa-full -fa on --cache-reuse 256`, el cache-reuse específicamente falla (issue #21468, abierto desde 5-abr-2026 sin PR de fix); el match de prefijo común (cache_prompt default true) sigue funcionando pero exige IDs de token idénticos hasta el punto de divergencia.

3. **Los resúmenes recursivos degradan más de lo que ahorran.** El issue público openai/codex #22220 ("Conversation Compaction Telemetry / Context Health") lo documenta verbatim: *"After several compactions, session quality can noticeably degrade due to summarization loss and recursive compression effects, but the user currently has no telemetry to understand that state."* Factory y Anthropic convergen en *Anchored Iterative Summarization*: un único bloque-ancla con campos fijos (intent, changes, decisions, next_steps) que se *extiende* en lugar de regenerarse. La evaluación pública de Factory (factory.ai/news/evaluating-compression, 36 000+ mensajes de producción de debugging, code review e implementación) reporta en el sub-eje *Accuracy*: **Factory 4.04 vs Anthropic 3.74 vs OpenAI 3.43**, con scores globales 3.70 / 3.44 / 3.35 respectivamente; el gap de 0.61 puntos de Accuracy *"reflects how often technical details like file paths and error messages survive compression."*

4. **Observation masking iguala a LLM-summary y es prácticamente gratis.** Lindenbauer et al. 2025 (*The Complexity Trap: Simple Observation Masking Is as Efficient as LLM Summarization for Agent Context Management*, arXiv:2508.21433, JetBrains Research/TUM, NeurIPS DL4C dic 2025) mide que ambas técnicas *"consistently and significantly reduce cost by around 50% without significantly degrading downstream task performance"*; con Qwen3-Coder 480B, observation masking obtiene **54.8% solve rate vs 53.8% de LLM-Summary**, mejor y a coste cero. Es directamente aplicable a tu problema de tool_results acumulados.

5. **Multi-turno en SLMs**: Laban et al. 2025 (arXiv:2505.06120) demostró que la degradación multi-turno es estructural, no de capacidad: ~16% pérdida de aptitud + **112% aumento en *unreliability***. Llama3.1-8B-Instruct y Phi-4 caen 30–40%, igual que frontier. Esperar el mismo orden de magnitud en Gemma 4 E4B.

---

## Detalle por punto

### Punto 1 — Qué preservar entre turnos en un asistente de voz por comandos *(prioritario)*

**Diagnóstico.** Los comandos de voz son mayoritariamente **atómicos**: "enciende la luz", "qué hora es", "agenda reunión mañana 10am". El contexto histórico se vuelve necesario en tres casos detectables baratamente:
- **Anáfora pronominal**: "ábrelo", "muéstrame ese", "eso", "el otro", "súbelo".
- **Continuación implícita** (discourse deixis): "ahora con prioridad alta", "y también para Pedro", "cancélalo".
- **Reformulación**: "no, mejor a las 11", "no, el del lunes".

Eckert & Strube (2000) documentan que **22.6% de las anáforas en diálogo hablado refieren a no-NPs** (eventos, acciones). En comandos de voz, la proporción de turnos con referencia anafórica al turno previo varía 15–30% según el dominio (control de hogar tiende a más alto, búsqueda/dictado a más bajo).

La arquitectura **context-as-router** es la consecuencia natural: un clasificador local (regex + lista cerrada de pronombres/deícticos en español de Chile + embedding ligero opcional) decide en < 5 ms si el turno requiere historial; en caso negativo se inyecta sólo el system prompt CORE LEAN + el turno actual.

**Tabla 1 — Estrategias de inyección de historial**

| Estrategia | Tokens reprocesados/turno | Coherencia | Latencia prefill | Riesgo |
|---|---|---|---|---|
| Historial completo (status quo) | ~3 900 acumulativos | Alta nominal, baja real (context rot) | Crece lineal hasta saturar | Saturación 16K, drift |
| Sólo turno actual + CORE LEAN | ~920 + len(turn) ≈ 950–1 100 | Pierde anáfora | **Mínima y constante** | Falla en "ábrelo" |
| **Context-as-router** (recomendado) | ~1 000 en 70–85% turnos; ~3 000 en turnos con referencia | Alta donde importa | Media-baja | Detector deficiente |
| Inherit-tools (ya implementado) | Bajo | Cubre subcaso "súbelo" tras tool_call previo | Baja | TTL mal sintonizado |

**Fuentes recientes.**
- Apple ML Research, "Learning to Rank Intents in Voice Assistants" — confirma context-aware intent ranking como práctica industrial.
- Laban, Hayashi, Zhou, Neville et al. 2025 (Microsoft + Salesforce Research), arXiv:2505.06120: 39% caída promedio; Llama3.1-8B y Phi-4 en 30–40%; *"when LLMs take a wrong turn in a conversation, they get lost and do not recover"*.
- Eckert & Strube 2000 (clásico, citado en CODI-CRAC 2022): 22.6% anáforas no-nominales en diálogo.
- Home Assistant Assist (2025) — referencia open-source: turn-atomic con fallback a LLM sólo si la intent no resuelve localmente.

**Verdicto VIABLE para 4B+16K+voz.** Implementar **router de contexto** con dos señales:
1. **Lista cerrada de gatillos deícticos** en español de Chile (regex): `\b(eso|esa|ese|esto|esta|este|aquello|aquel|lo|la|los|las|ahí|allá|aquí|tal|otro|otra|así|mismo|misma|también|tampoco|cancélalo|abr[ie]lo|súbe?lo|borr[aá]lo|guárd[ae]lo|ház?lo|mánd[ae]lo|repítelo)\b`, más imperativos enclíticos.
2. **Longitud del turno**: turnos < 5 palabras se tratan como candidatos a continuación.

Si **ninguna** señal dispara → prompt = SYSTEM + USER actual (sin historial). Si dispara → SYSTEM + último resumen-ancla + últimos 2 turnos completos.

**Pseudocódigo.**
```python
DEICTIC_RE = re.compile(r"\b(eso|esa|ese|esto|esta|este|aquello|aquel|"
                        r"lo|la|los|las|ahí|allá|aquí|tal|otro|otra|"
                        r"así|mismo|misma|también|tampoco|"
                        r"(cancél|ábre|súbe|bórra|guárda|ház|mánda|"
                        r"repít|múestra|cierra|abre|borra)(lo|la|los|las|le|me)?)\b",
                        re.IGNORECASE)

def needs_history(user_text: str, last_turn_age_s: float) -> str:
    """Devuelve 'none' | 'light' | 'full'."""
    txt = user_text.strip()
    if last_turn_age_s > 90:           # sesión expirada
        return "none"
    n_words = len(txt.split())
    has_deixis = bool(DEICTIC_RE.search(txt))
    starts_imperative_short = n_words <= 4 and txt.split()[0].endswith(
        ("lo","la","los","las","le","me"))
    if has_deixis or starts_imperative_short:
        return "light"                 # último resumen-ancla + 2 turnos
    if n_words <= 3:                   # "sí", "no", "dale", "vale"
        return "light"
    return "none"                      # turno autocontenido

def build_prompt(state, user_text):
    mode = needs_history(user_text, state.seconds_since_last_turn)
    if mode == "none":
        return CORE_LEAN + microagents_for(user_text) + user_text
    return (CORE_LEAN + microagents_for(user_text)
            + state.anchor_summary       # bloque-ancla estable
            + state.recent_turns[-2:]    # últimos 2 turnos completos
            + user_text)
```

**Qué medir.**
- `pct_turnos_modo_none`: objetivo > 60%.
- `falsos_negativos_deixis` (etiquetado humano sobre 200 turnos): objetivo < 5%.
- `prefill_ms_p50` en modo `none` vs `light`: esperar caída de ~888 ms a < 200 ms.

---

### Punto 2 — Compactación/summarization sin romper el prefix-cache *(prioritario)*

**Diagnóstico.** En llama.cpp el cache reuse funciona así: cada request, el servidor compara los token IDs entrantes con los del slot. `--cache-reuse N` busca un *common prefix* y, si el prefijo difiere por un bloque movido, aplica `llama_kv_cache_seq_rm` + `seq_add` (KV-shifting) con chunks ≥ N. **Cualquier cambio byte-a-byte dentro del prefijo invalida el cache desde el punto del cambio.** Con SWA (Gemma) sin `--swa-full`, el reuse está limitado a la ventana deslizante (Gemma 3: 1024 tok; Gemma 4 small variants: 512 tok). El default `--cache-reuse 0` está desactivado; el flag de tu stack `--cache-reuse 256` exige bloques mínimos de 256 tokens.

**Realidad operativa con Gemma 4 E4B en build b9090**: el issue **#21468 sigue abierto al 23-may-2026** (reportado en llama.cpp build 8660, commit d006858, Clang 19.1.5 Windows, sin PR linkeado y sin assignees). Confirma que con `gemma-4-E4B-it-GGUF` (y E2B) el log muestra textualmente:
```
slot update_slots: cache reuse is not supported - ignoring n_cache_reuse = 256
slot update_slots: n_tokens = 0, memory_seq_rm [0, end)
srv load: - looking for better prompt, base f_keep = -1.000, sim = 0.000
```
La causa raíz reportada: *"Gemma 4 uses a Shared KV Cache architecture where the last num_kv_shared_layers layers reuse K/V tensors from the last non-shared layer"*. Impacto medido en el reporte: *"full prompt re-evaluation on every request (~46K tokens, ~96 seconds on the test hardware)"*. **En la práctica, hoy `--cache-reuse` no funciona para tu modelo**; lo que sí funciona es el match de prefijo común exacto (cache_prompt default true). El reporte no documenta workaround efectivo — el usuario ya probó `-fa on` y `--swa-full` sin éxito.

**Anatomía del prompt** (regla de oro para cache):
```
[SYSTEM CORE LEAN  ~920 tok]      ← estable byte-a-byte → SIEMPRE cacheado
[ANCHOR SUMMARY     ≤300 tok]     ← cambia sólo cada N turnos → cachea entre actualizaciones
[RECENT TURNS       ≤2 turnos]    ← cola variable → SIEMPRE reprocesada
[CURRENT USER       ~50 tok]
```

**El error a evitar**: insertar el resumen *en medio* del system prompt rompe la primera barrera. Solución: **el resumen-ancla forma parte del prefijo "semi-estable"** y se actualiza por reemplazo total cada K turnos, no cada turno.

**Tabla 2 — Variantes de summarization vs cache**

| Estrategia | Tokens reprocesados | Coherencia | Latencia | Riesgo |
|---|---|---|---|---|
| Resumen al final del prompt cada turno | Bajo (sólo tail) | Alta | Baja | Riesgo de "lost in the end" si tail crece |
| Resumen entre system y recent (recomendado) | Bajo si se actualiza cada K=4 turnos | Alta | Baja en turnos sin update; pico cuando se actualiza | Cuando se regenera, invalida todo lo posterior |
| Resumen recursivo (resumen del resumen) | Muy bajo | **Degrada** (openai/codex #22220 verbatim) | Baja | Drift acumulado |
| **Anchored iterative summarization** (Factory) | Muy bajo: sólo se *extiende* el ancla | **Alta** (4.04 Factory vs 3.43 OpenAI en Accuracy) | Baja | Necesita LLM para generar la extensión |
| Observation masking (Lindenbauer 2025, arXiv:2508.21433) | Bajo | 54.8% vs 53.8% LLM-Summary | Mínima (zero-cost) | Pierde detalle si la máscara es ciega |

**Fuentes recientes.**
- ggml-org/llama.cpp Discussion #13606 (*Tutorial: KV cache reuse with llama-server*) y #20574 (*Host-Memory Prompt Caching*, PR #16391 mergeado oct 2025).
- ggml-org/llama.cpp Issue #21468 (abierto, sin fix al 23-may-2026): Gemma 4 cache reuse fails by design.
- ggml-org/llama.cpp PR #22929 (May 2026, en curso): mueve los checkpoints a *natural turn boundaries* extrayendo spans de mensaje de los templates GPT/Gemma 4/ChatML — promete reducir el reprocesado en flujos agénticos.
- Zylos Research, *AI Agent Context Compression Strategies* (feb 2026): trigger compactación al 70% del budget; reportan que *"context drift kills agents before context limits do"* con 65% de fallos enterprise atribuibles a drift.
- Lindenbauer et al. 2025 (arXiv:2508.21433, NeurIPS DL4C dic 2025).
- openai/codex GitHub issue #22220.
- Anthropic Claude Cookbook *Context engineering: memory, compaction, and tool clearing* (2025).

**Verdicto VIABLE.** Dado que `--cache-reuse` está roto para Gemma 4 hoy:
1. **Tratar el prefijo CORE LEAN (~920 tok) como inmutable** (mismo orden de microagents, mismo formato, mismos token IDs en cada turno). No reordenar, no usar campos con timestamps, no inyectar variables condicionales en el system prompt.
2. **Anchor summary entre system y recent**: actualizar cada 4–6 turnos (no cada turno). Política: regenerar el ancla cuando `n_recent_turns > 3` **y** el último turno fue autocontenido (no anafórico), aprovechando el momento natural.
3. **Sólo conservar 2 turnos completos en la cola**; los demás se reemplazan por una línea por turno: `[T{n}] user: <≤12 palabras> | tool: <name> | result: <≤20 palabras o "OK">`.
4. **Observation masking para tool_results antiguos** (Lindenbauer 2025): sustituir el contenido por `<tool_result name="X" turn={n} truncated />`, manteniendo la estructura del mensaje para no romper el tool-calling.
5. **Mientras dure el bug #21468**: priorizar la reducción del tail variable. Cada token extra al final cuesta ~0.1 ms en prefill en tu hardware (extrapolado del 888 ms p50 sobre 7875 tok).
6. **Compatibilidad con context-shift**: en tu config (`--keep -1 --swa-full`) NO debería activarse activamente, pero si se desborda el contexto el shift por defecto descarta la mitad después de `--keep` y rompe coherencia. La política del Punto 5 debe intervenir antes.

**Pseudocódigo del anchor summary.**
```python
ANCHOR_TEMPLATE = """
[CONTEXT_ANCHOR turn={turn}]
intent_actual: {intent}
entidades: {entities}   # JSON corto, máx 6 keys
decisiones: {decisions} # bullet list ≤4 ítems, ≤8 palabras cada uno
herramientas_usadas_recientes: {tools}   # nombre + último arg relevante
ultimo_resultado_util: {last_useful_result}  # 1 línea, descartable
[/CONTEXT_ANCHOR]
"""

def maybe_refresh_anchor(state, llm_local):
    if state.turns_since_anchor < 4: return
    if state.last_turn_was_anaphoric: return   # esperar a turno "limpio"
    # extender en lugar de regenerar (Anchored Iterative, Factory)
    new_anchor = llm_local.extend_anchor(
        old=state.anchor_summary,
        new_turns=state.turns_since_anchor_log,
        max_tokens=300, temperature=0.1)
    state.anchor_summary = new_anchor
    state.turns_since_anchor = 0
```

**Qué medir.**
- `prompt_eval_time_ms` por turno (telemetría llama-server: campo `t_prompt_processing`).
- `tokens_cached` vs `tokens_evaluated` (en la respuesta del server).
- `tail_tokens_p50`: mantener < 2 000.
- `anchor_refresh_per_session`: monitorear que no dispare más de 1 cada 5 turnos.
- Trade-off concreto: 300 tokens de ancla reprocesados al refrescar (≈ 30 ms en tu hw) vs 1 200–2 000 tokens de tail reprocesados cada turno (≈ 100–200 ms).

---

### Punto 3 — Coherencia multi-turno en modelos 4B sin segundo modelo

**Diagnóstico.** Laban et al. 2025 (arXiv:2505.06120, Microsoft Research + Salesforce, 200 000+ conversaciones simuladas, 15 LLMs, 6 tareas) midió 39% de caída promedio single→multi-turn; Llama3.1-8B-Instruct y Phi-4 (ambos < 10B) cayeron 30–40%, **comparable a frontier**. La descomposición fue ~16% pérdida de aptitud + 112% aumento en *unreliability*. El mecanismo, verbatim: *"when LLMs take a wrong turn in a conversation, they get lost and do not recover."* Gemma 4 E4B-it Q4_K_M es razonablemente esperable que se comporte similar.

Suma "lost in the middle" (Liu et al. 2023, sigue válido en 2025): en modelos pequeños el sesgo es de **pura recencia** — el paper midió específicamente que Llama-2-7B muestra sólo recency bias sin U-shape (la curva U recién aparece a 13B+). Para un 4B esto significa que **lo importante debe estar al final** del prompt, no en medio del historial.

Y "context rot" (Chroma 2025, Hong/Troynikov/Huber, trychroma.com/research/context-rot, jul 2025): degradación **no-uniforme** con la longitud del input incluso por debajo del límite, testeada en 18 modelos frontera (GPT-4.1, Claude 4, Gemini 2.5, Qwen3). El reporte concluye *"performance grows increasingly unreliable as input length grows"* en formas *"surprising and non-uniform"*. Aunque Chroma no fija un umbral universal, en SLMs y específicamente en un 4B con 16K cabe esperar deterioro tangible mucho antes del límite — recomiendo medirlo empíricamente, no asumir.

**Patrones SIN segundo modelo:**

1. **State slots estructurados (JSON working set).** El modelo genera/actualiza un bloque:
   ```
   <state>{"intent":"agenda_meeting","entities":{"date":"2026-06-15","time":"15:00","with":"Pedro"},"pending":"confirm_attendees"}</state>
   ```
   El orquestador lo extrae con regex y lo re-inyecta como parte del anchor. Mem0 (oct 2025) documenta que esto vence a la summarization plana porque preserva valores exactos (fechas, IDs, paths).

2. **Scratchpad persistente con campos fijos** (Sopan Deole, Medium sep 2025): cuatro campos estables (`last_goal`, `steps`, `open_questions`, `known_ids`), rotando como ring buffer.

3. **Attention sinks** (StreamingLLM, Xiao et al. ICLR 2024; integrado en HF Transformers, TensorRT-LLM y gpt-oss de OpenAI desde ago 2025): preservar los **primeros 4 tokens** + ventana deslizante. En llama.cpp no está expuesto como flag dedicado, pero la práctica equivalente es **nunca tocar el primer bloque del prompt (BOS + system header)**. Con `--keep -1` ya se cumple en el modo *infinite generation*, pero llama.cpp aplica el shift sólo cuando se desborda, no preventivamente.

4. **Anchored extension** (Factory), descrita en Punto 2.

5. **COMEDY-style** (Chen et al. 2025d, citado en survey arXiv:2504.04717 *Beyond Single-Turn*): un solo modelo genera memoria comprimida. Sin entrenar, en inferencia se aproxima con un system prompt que pide formato estricto:
   ```
   <memo>...</memo>
   <reply>...</reply>
   ```
   El orquestador descarta `<reply>` del historial y conserva sólo `<memo>`.

**Tabla 3 — Coherencia multi-turno**

| Patrón | Tokens reprocesados | Coherencia | Latencia | Riesgo en 4B |
|---|---|---|---|---|
| Historial completo | Alto | Degrada por context rot | Crece | Drift, "lost in the middle" |
| State slots JSON | Bajo | Alta para valores exactos | Baja | Modelo puede romper el formato |
| Scratchpad con campos fijos | Bajo | Alta para tareas | Baja | Modelo puede no actualizarlo |
| Attention sinks (preservar BOS+sys) | Bajo | Estabiliza generación larga | Mínima | No expuesto directamente en llama.cpp |
| Anchored extension | Bajo, picos ocasionales | **+0.61 Accuracy** vs OpenAI (Factory, 36k mensajes) | Picos en refresh | Coste extra de extension |
| COMEDY-style (un solo modelo gen memo) | Muy bajo | Alta | Suma ~30–50 tok output | El 4B no siempre obedece el formato |

**Fuentes recientes.**
- Laban et al. 2025, arXiv:2505.06120 (Microsoft Research + Salesforce).
- Chroma Research, *Context Rot: How Increasing Input Tokens Impacts LLM Performance* (jul 2025).
- COMEDY (Chen et al. 2025d), citado en survey arXiv:2504.04717.
- CogMem (arXiv:2512.14118, dic 2025): tres capas LTM/DA/FoA; útil como arquitectura inspiradora.
- Mem0 blog, *LLM Chat History Summarization* (oct 2025).
- StreamingLLM (Xiao et al. 2024, ICLR), integrado en OpenAI gpt-oss ago 2025.

**Verdicto VIABLE para 4B+voz.** Combinación **state slots + anchored extension + recencia explícita**:
- JSON `<state>` corto (< 200 tok) gestionado por el orquestador, no por el modelo (evita inconsistencia).
- Refrescar anchor cada 4–6 turnos (Punto 2).
- Forzar que la información crítica para el turno actual esté **en los últimos ~500 tokens** del prompt (mitigación lost-in-the-middle).
- Si el orquestador detecta que el JSON state contiene un slot necesario (ej. `last_file_path` cuando el usuario dice "súbelo"), inyectarlo **literalmente en el turno del usuario**: "súbelo [archivo: /tmp/x.png]" — fusión de slot con el turno actual.

**Pseudocódigo.**
```python
@dataclass
class VoiceState:
    intent: str = ""
    entities: dict = field(default_factory=dict)
    last_tool_name: Optional[str] = None
    last_tool_args: dict = field(default_factory=dict)
    last_useful_result: str = ""          # ej. path de archivo
    open_question: Optional[str] = None
    recent_turns: deque = field(default_factory=lambda: deque(maxlen=2))
    turns_since_anchor: int = 0

def inject_slot_in_user_text(user_text, state):
    # Fusión deíctica → slot
    if DEICTIC_RE.search(user_text) and state.last_useful_result:
        return f"{user_text} [referencia: {state.last_useful_result}]"
    return user_text
```

**Qué medir.**
- *Task success rate* en multi-turno sintético (script con 20 conversaciones de 5 turnos cada una, anáfora explícita en turnos 2–5). Objetivo: > 80% con state-slots vs ~50–60% sin ellos (en línea con Laban 2025).
- *State slot consistency*: tasa de slots correctamente actualizados turn-a-turn.

---

### Punto 4 — Manejo de tool_results en el historial

**Diagnóstico.** Tu agent_compaction ya elimina tool_results antiguos. La pregunta es **cuándo un tool_result antiguo importa para el turno actual**. Respuesta empírica:

- **Importa cuando contiene un identificador que el siguiente turno referenciará deícticamente**: paths (`/tmp/foto_2026.png`), IDs (`event_id=42`), URLs, números de cuenta, nombres específicos resultado de búsquedas.
- **No importa cuando es transitorio**: textos de respuesta ya hablados al usuario, listados de opciones cuando el usuario ya eligió, confirmaciones (`{"status":"ok"}`).

Anthropic (Cookbook *automatic context compaction*, 2025) lo formaliza para soporte: *"Keep completion summaries (tickets resolved, categories, outcomes); discard detailed tool results"*. Es el patrón aplicable a voz.

**Heurística de retención** (regla de 3 capas):
1. **Resultados con identificadores extraíbles** (regex `[\w./-]+\.(png|jpg|pdf|mp3)|id=\d+|event_\d+|^/[\w/.-]+|https?://\S+`) → extraer el identificador, descartar el resto, guardarlo en `state.last_useful_result`.
2. **Resultados estructurados (JSON)** → conservar sólo las claves que el orquestador conoce como referenciables (lista blanca por tool: `search_files` retiene `path`; `weather` retiene nada; `calendar` retiene `event_id`).
3. **Resultados verbales** → descartar, ya fueron leídos por TTS al usuario.

**Tabla 4 — Estrategias de tool_results**

| Estrategia | Tokens reprocesados | Coherencia | Latencia | Riesgo |
|---|---|---|---|---|
| Conservar todos (status quo agentes) | Crece sin techo | Alta nominal | Crece | Saturación, drift |
| Eliminar todos los antiguos (status quo tuyo) | Bajo | Falla en "ábrelo" sin inherit-tools | Baja | Pérdida real |
| **Observation masking + slot extraction** (recomendado, Lindenbauer 2025) | Bajo | 54.8% vs 53.8% LLM-Summary | Mínima | Slot extractor con falsos negativos |
| Mantener sólo el último tool_result | Bajo | Limitado a 1 turno atrás | Baja | Falla en cadenas de 3+ pasos |
| `clear_tool_uses` (Claude Code) | Bajo | Alta | Baja | API-específico, no portable a llama.cpp |

**Fuentes recientes.**
- Anthropic Claude Cookbook *automatic context compaction* y *context engineering* (2025).
- Lindenbauer et al. 2025, arXiv:2508.21433 (NeurIPS DL4C dic 2025) — observation masking iguala/supera LLM-summary con ~50% reducción de coste y 54.8% solve rate en Qwen3-Coder 480B.
- ReSum (arXiv:2509.13313, 2025).

**Verdicto VIABLE.** Combinar el `inherit-tools` que ya tienes con **slot extraction explícito**: cada vez que se completa un tool_call, el orquestador corre el extractor de identificadores y guarda los resultados en `state.last_useful_result`, `state.last_file_path`, etc. El tool_message se reemplaza por `<tool_result name="X" status="ok" extracted_to=state />` ocupando ~15 tokens en lugar de 200–500.

**Pseudocódigo.**
```python
IDENT_PATTERNS = {
    "path": re.compile(r"(/[\w./-]+\.(png|jpg|pdf|mp3|txt|md))"),
    "url":  re.compile(r"https?://\S+"),
    "id":   re.compile(r"\b(event|order|user|task)_(\d+)\b"),
}

def compact_tool_result(tool_msg, state):
    raw = tool_msg.content
    extracted = {}
    for kind, pat in IDENT_PATTERNS.items():
        m = pat.search(raw)
        if m:
            extracted[kind] = m.group(0)
            setattr(state, f"last_{kind}", m.group(0))
    state.last_useful_result = next(iter(extracted.values()), "")
    return ToolMessage(
        name=tool_msg.name,
        content=f"<tool_result status=ok extracted={list(extracted.keys())}>",
        token_estimate=15)
```

**Qué medir.**
- `tokens_tool_results_p50` antes vs después: objetivo reducción > 80%.
- `inherit_tools_hit_rate`: fracción de turnos deícticos resueltos correctamente con state.

---

### Punto 5 — Límite de 16K y degradación

**Diagnóstico.** Hechos:
- Chroma *Context Rot* (jul 2025) — la degradación inicia mucho antes del límite, en formas *"surprising and non-uniform"* a través de los 18 modelos frontera testeados; en un 4B con 16K esperar deterioro tangible mucho antes del límite (medirlo empíricamente).
- En llama.cpp con tu config `--keep -1 --swa-full --cache-reuse 256`: si el prompt supera 16K, el comportamiento por defecto es **context shift rotativo** (descarta la mitad de los tokens después de `--keep`). `--keep -1` retiene TODO el prompt inicial, lo que hace el shift más conservador pero **igual rompe coherencia** para asistente porque elimina turnos recientes de manera ciega.
- `--no-context-shift` produce error 500 en lugar de truncar — útil para detección, malo para UX.
- En multimodal Gemma 3/4: `ctx_shift is not supported by multimodal, it will be disabled` (Discussion #14170) — relevante si activas vision.

**Política de presión de contexto en 3 bandas:**

| Banda | Umbral (% de 16384) | Acción | Latencia añadida |
|---|---|---|---|
| Verde | < 50% (< 8K) | Operación normal, anchor refresh natural | 0 |
| **Amarillo** | 50–70% (8–11.5K) | Forzar anchor refresh inmediato; podar tool_results a placeholder | ~30–50 ms (extension del ancla) |
| **Naranja** | 70–85% (11.5–14K) | Compactación dura: dejar sólo CORE LEAN + anchor + 1 turno; descartar `recent_turns[:-1]` | ~50–100 ms en el turno crítico |
| **Rojo** | > 85% (> 14K) | **Reset suave**: conservar sólo CORE LEAN + anchor (no turnos), avisar al usuario "voy a empezar de nuevo manteniendo lo importante" | Reset coste 1 turno |
| Crítico | > 95% (> 15.5K) | Reset duro: nuevo slot/sesión, anchor preservado en estado externo | Sesión nueva |

**Tabla 5 — Estrategias en saturación**

| Estrategia | Tokens reprocesados | Coherencia | Latencia | Riesgo |
|---|---|---|---|---|
| Context shift de llama.cpp (default) | Medio | **Rompe** (descarte ciego) | Pausa significativa | Mal UX en voz |
| `--no-context-shift` + error | 0 | Falla dura | Muy mala | Inaceptable UX |
| Truncar antiguos sin resumir | Bajo | Drift | Baja | Pérdida total de contexto previo |
| **Política 3 bandas con anchor + observation masking** | Variable, controlado | **Alta** | Picos predecibles | Necesita estado externo persistente |

**Tool-calling bajo presión**: NUNCA truncar entre `tool_call` y su `tool_result` correspondiente (rompe el parser de Gemma 4 / chat template). Si la presión obliga a truncar, hacerlo en **boundaries de turno** completos (user → assistant → tool → assistant cerrado).

**Fuentes recientes.**
- Chroma Research *Context Rot* (jul 2025), trychroma.com/research/context-rot.
- llama.cpp Discussion #14170 *Gemma 3 context shift issue* — confirma que context shift no se soporta con multimodal.
- llama.cpp Issue #19977 (mar 2026) — `erased invalidated context checkpoint` con Qwen3.5 large-context: aplicable como advertencia general de que los checkpoints internos no son una defensa única confiable.
- Sourcegraph Amp (2026, tessl.io blog) — abandono de compaction por *Handoff* tras observar deterioro acumulativo.
- openai/codex Issue #22220 — *"After several compactions, session quality can noticeably degrade due to summarization loss and recursive compression effects."*

**Verdicto VIABLE.** Implementar las 3 bandas en el orquestador, no confiar en `--keep -1` para coherencia. **Desactivar context-shift de facto** dejando que la política suave intervenga antes; mantener `--no-context-shift` en false (default actual) sólo como red última.

**Pseudocódigo.**
```python
def pressure_band(n_prompt_tokens, ctx_size=16384):
    p = n_prompt_tokens / ctx_size
    if p < 0.50: return "green"
    if p < 0.70: return "yellow"
    if p < 0.85: return "orange"
    if p < 0.95: return "red"
    return "critical"

def apply_pressure_policy(state, n_prompt):
    band = pressure_band(n_prompt)
    if band == "yellow":
        force_anchor_refresh(state)
        mask_tool_results(state, keep_last=1)
    elif band == "orange":
        force_anchor_refresh(state)
        state.recent_turns = deque(maxlen=1)
        mask_tool_results(state, keep_last=0)
    elif band == "red":
        persist_anchor(state)            # estado externo
        state.recent_turns.clear()
        state.user_warn = "Voy a continuar con lo importante."
    elif band == "critical":
        restart_session(state)           # nuevo slot, anchor recargado
    return band
```

**Qué medir.**
- Histograma de bandas por sesión: objetivo > 80% del tiempo en verde, < 5% en naranja o peor.
- `coherence_at_band` (evaluación humana o LLM-as-judge offline): caída esperada verde→amarillo < 5 pts; verde→naranja < 15.
- `tool_call_integrity`: 100% — nunca truncar entre call y result.

---

## Recomendaciones (orden de implementación)

**Etapa 1 — esta semana (ROI inmediato, sin riesgo):**
1. Implementar el **router de contexto** (Punto 1). Mayor impacto sobre prefill p50. Medir antes/después.
2. **Verificar el log de tu llama-server b9090** buscando `cache reuse is not supported`. Si aparece, no perder tiempo afinando `--cache-reuse 256` y enfocar todo en mantener prefijo idéntico byte-a-byte. Reportar a #21468 con tu build si confirmas.
3. Implementar **observation masking** de tool_results (Punto 4) con slot extraction.

**Etapa 2 — siguientes 2 semanas:**
4. **Anchor summary** entre system y recent (Punto 2), con anchored iterative extension. Refresh cada 4–6 turnos en boundary limpio.
5. **State slots JSON** mantenidos por el orquestador (Punto 3).
6. **Política de 3 bandas** (Punto 5).

**Etapa 3 — cuando haya fix de #21468 o cambio de modelo/build:**
7. Re-activar y afinar `--cache-reuse` con N=128 (más reactivo que 256).
8. Considerar `--cache-ram` (PR #16391, oct 2025) para host-memory caching si el escenario evoluciona a multi-sesión.
9. Seguir el PR #22929 (mayo 2026): mueve los checkpoints a boundaries naturales de turno extrayendo spans de Gemma 4 chat template — cuando se mergee, debería reducir el reprocesado en tu flujo.
10. Evaluar `id_slot` explícito por sesión si emerge patrón multi-usuario.

**Benchmarks que cambian la decisión:**
- Si `prefill_p50 > 1.5 s`: revisar inmediatamente prompt CORE LEAN — está creciendo no-monótonamente.
- Si `tool_call_integrity < 100%`: bug en boundary detection del 3-bandas, prioridad crítica.
- Si `task_success_multi_turn < 70%` en evaluación sintética: considerar fine-tuning ligero del 4B o cambio de modelo a uno con mejor multi-turno (ej. Qwen2.5-7B-Instruct si la latencia lo permite).
- Si `band="red"` aparece más de una vez por sesión típica: el anchor está sub-dimensionado o el router permite demasiado historial — ajustar umbrales.

---

## Caveats

- **#21468 es un bug abierto, no confirmado** (etiqueta `bug-unconfirmed`): el reporte original es del 5-abr-2026 sobre build llama.cpp 8660 (commit d006858). Podría haber fix entre tu build b9090 y la fecha de hoy (23-may-2026) que no esté reflejado en el issue. **Recomiendo verificar empíricamente** con `--debug-slot` o inspeccionar el log por la línea exacta `cache reuse is not supported`.
- Los benchmarks de degradación multi-turno (Laban 2025, Chroma 2025) **no testean Gemma 4 E4B específicamente**: las cifras (30–40% drop para Llama3.1-8B y Phi-4) son la mejor proxy disponible, pero el comportamiento exacto puede variar ±10 puntos.
- **Chroma no fija un umbral universal de "30K"**: el reporte describe degradación no-uniforme dependiente del modelo y la tarea, no un cliff fijo. Cualquier umbral concreto en un 4B con 16K hay que medirlo empíricamente, no asumirlo.
- La detección deíctica por regex tiene falsos negativos (uso elíptico sin pronombre: "manda eso a Pedro" vs "manda a Pedro"). Medir y, si supera 5%, complementar con clasificador embedding ligero (multilingual MiniLM, < 30 ms en CPU).
- `--swa-full` aumenta el consumo de memoria del KV cache (desactiva prácticamente SWA): asegurar que cabe en VRAM/RAM con Q4_K_M.
- *Anchored Iterative Summarization* proviene de blog de Factory (factory.ai/news/evaluating-compression, 36 000+ mensajes de producción) y de Zylos Research (feb 2026), no de paper peer-reviewed. La técnica es ingeniería sólida pero su validación es industrial, no académica.
- StreamingLLM en su forma original requiere modificar el KV cache para preservar los primeros tokens; en llama.cpp no está expuesto como flag directo, sólo aproximado vía `--keep`. El paralelo es conceptual, no implementacional.
- Los resúmenes recursivos producen drift documentado por OpenAI (issue codex #22220): NO encadenar resúmenes de resúmenes.