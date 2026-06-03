# Prompt de investigación — Arquitectura del LLM en Carter Agent (refinamiento)

Copiá esto a Claude (research/web). El objetivo es mejorar cómo el LLM interactúa
con TODO el programa. CRÍTICO: abajo está lo que YA tenemos implementado y medido
— NO recomiendes cosas que ya existen; enfocate en las 5 tensiones abiertas al
final. Distinguí lo confirmado de lo hipotético, citá fuentes recientes, y dame
recomendaciones VIABLES para este stack con código/pseudocódigo donde aplique.

---

## 0. Stack (confirmado en código)
- **Modelo:** Gemma 4 **E4B-it Q4_K_M** GGUF (familia Gemma 4, ~4B efectivos,
  Per-Layer Embeddings, atención híbrida SWA+global, function-calling nativo
  `<|tool_call|>`, thinking nativo).
- **Runtime:** llama.cpp `llama-server` build b9090, monoslot, GPU 6 GB target
  (dev en RTX 4060 Ti 16 GB). Flags: `--jinja --flash-attn on --swa-full
  --cache-reuse 256 --keep -1 -c 16384 --parallel 1`.
- **Producto:** asistente de VOZ local Windows, 100% OSS/offline, latencia
  tier-Alexa (4-5 s/turno). STT=Parakeet-TDT-v3 (sherpa CPU). 65 tools.

## 1. Sampling actual (posible punto fino)
`temperature=1.0, top_p=0.95, top_k=64, repeat_penalty=1.0, min_p=None`
(defaults de Gemma). Para tool-calling esto es ALTO. ¿Conviene greedy/baja-temp
para el tool-calling y dejar temp alta solo para chat libre? Medir el trade-off
fiabilidad-vs-diversidad.

## 2. LO QUE YA EXISTE (no recomendar de nuevo — esto es el punto)
Esta arquitectura NO es un "LLM + tools" ingenuo. Ya implementado y medido:
- **Loop agéntico multi-paso** (`max_agent_turns=8`). Thinking ON solo en el
  PRIMER paso; tras la 1ª tool se apaga (resumir el resultado no necesita
  reasoning; dejarlo prendido duplica latencia — medido).
- **Router en capas para el subset de tools** (no se pasan los 65 al LLM):
  semantic_router (encoder `paraphrase-multilingual-MiniLM-L12-v2` fine-tuneado
  + Tool2Vec + RRF) → intent_router (info/acción por anclas multilingües +
  gate interrogativo léxico zero-ML como fallback) → abstain_head (gate no-tool
  calibrado) → planner. recall holdout 0.881. Devuelve 4-6 tools/turno.
- **Forced-retry con `tool_choice="required"`**: si el modelo "promete" la acción
  en texto sin llamar la tool (fallo clásico de SLM), se reintenta UNA vez
  forzando el tool-call vía la gramática interna de llama.cpp.
- **Guards de respuesta** (corren sobre el texto del reply): honestidad
  (no decir "listo" si la tool no verificó), grounding (claim de acción debe
  tener evidencia), promesa-sin-acción, leaked-tool-call (rescata un tool-call
  emitido como texto), reply_validator.
- **Recuperación de errores:** context-overflow retry (compacta historial +
  recorta el subset a la mitad), server-reload recovery (Connection reset →
  poll /health → 1 retry), unsupported-option retry, per-mode timeout.
- **Summary-pass slimming:** tras una tool en modo single-action, el 2º pass
  quita el catálogo de tool-schemas del prompt y capa max_tokens a 160 (el
  resultado es una sola frase) → menos prefill+decode.
- **thinking_budget por modo** (quick_action=256, deep=1024, research=2048),
  cache-reuse + swa-full para prefix-reuse, modos por intención (fast_action,
  fast_info, quick_action, deep_action, vision_action, audio_mode, research).
- **Compaction de historial** proporcional al context_size; inherit-tools en
  continuaciones cortas ("subelo") con TTL; microagents inyectados por trigger.

## 3. Métricas medidas (sesión 2026-05-23)
- Latencia: prefill mediana ~888 ms (el router ya lo controla). THINKING es el
  cuello: p90=268 tok, max 841, **23% de turnos generan >100 tok = hasta 4.3 s**.
- Tool-calling: con reasoning ON 6/6 en comandos crisp; con OFF 2/6 (el reasoning
  es lo que hace fiable el tool-call en este 4B).
- agent.py = **3249 líneas** (orquestación del LLM muy concentrada).

## 4. LAS 5 TENSIONES ABIERTAS (acá quiero la investigación)

### T1 — Encadenamiento multi-paso en 4B (search→open/play/read)
El 4B ejecuta `filesystem.search` pero NO emite de forma fiable la 2ª tool-call
(office.open) — termina el turno en prosa. Ya probamos: nudge inyectado tras el
search (ayuda parcial), auto-repair del path, y un fallback "preguntar cuál
abrir". ¿Cuál es el patrón MÁS fiable para encadenamiento dependiente en un 4B
local SIN un planner LLM caro y SIN auto-ejecutar a ciegas? ¿Fine-tune ligero
(QLoRA) en pares de encadenamiento vale el ROI vs prompting? Evidencia en <10B.

### T2 — Reducir el costo del THINKING sin perder fiabilidad de tool-call
Reasoning ON = 6/6 pero p90 4.3 s; OFF = 2/6. Probamos FR-CoT (thinking
estructurado ≤4 líneas INTENT/TOOL/ARGS/GO): mejoró apps/audio (audio 5.2→2.4 s)
PERO regresionó media (6/6→3/6) porque Gemma E4B a veces emite el formato como
TEXTO de salida (no en el canal de pensamiento), rompiendo el tool-call. ¿Cómo
forzar reasoning breve SIN que el formato se filtre al output en Gemma 4? ¿GBNF/
grammar para separar canal-thinking de canal-respuesta? ¿Un router de complejidad
que mande crisp a "sin thinking" + grammar que garantice el tool-call (cura el
2/6)? Queremos rescatar la ganancia de FR-CoT sin romper media.

### T3 — Subset dinámico de tools vs estabilidad del prefijo (cache)
El router da 4-6 tools/turno (bueno para tool-calling: el 4B se confunde con 65).
PERO el system prompt se filtra al subset → cambia turno-a-turno → rompe el
prefix-cache. Probamos un core-set FIJO de 15 tools (prefijo estable): aislado
10× mejor prefill, pero E2E real 2× PEOR (prompt más grande no compensa). ¿Existe
un punto óptimo? ¿Layout que ponga lo estable (core) adelante y el subset variable
al FINAL del prompt para preservar el cache, sin inflar el total? Dame el cálculo.

### T4 — Sampling para tool-calling
temp=1.0/top_k=64 (Gemma defaults) en TODOS los modos. ¿Conviene greedy/low-temp
para los modos de acción (tool-calling determinista) y temp alta solo para chat?
¿Riesgo de degradar la calidad del tool-call o del lenguaje? Evidencia.

### T5 — Deuda arquitectónica de la orquestación
agent.py concentra 3249 líneas: el loop, los passes, los guards, el forced-retry,
la recuperación. ¿Hay un patrón de arquitectura (state machine explícita,
pipeline de fases, separación orquestador/política) que reduzca el riesgo de
regresión sin reescribir todo? ¿O la concentración es aceptable y el ROI de
refactor es bajo? Sé honesto: si no rinde, decílo.

## 5. Formato del informe
Para cada tensión (T1-T5): diagnóstico, opciones con tabla comparativa (criterios
medibles: fiabilidad tool-call %, latencia ms, riesgo de regresión, esfuerzo),
fuentes oficiales/papers/benchmarks RECIENTES (2025-2026, modelos <10B y
llama.cpp donde aplique), y veredicto VIABLE para ESTE stack. Snippets de código/
flags listos para integrar. Marcá lo que hay que MEDIR en nuestro dataset/smoke.
Prioridad: T1 y T2 (impacto UX directo). NO repitas lo de la sección 2 (ya existe).
```
```
