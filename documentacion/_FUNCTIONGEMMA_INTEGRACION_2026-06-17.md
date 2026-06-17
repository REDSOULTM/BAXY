# Integración de FunctionGemma run9 como router de tool-calling — 2026-06-17

Estado: **INTEGRADO y VALIDADO EN VIVO**, gated OFF por default (`GEMMA4_FG_ROUTER=1`
para activar). Rama: `Experimentando`. Fuente de verdad del artefacto y contrato:
`FunctionGemma/INTEGRATION_HANDOFF.md`.

## Qué es

FunctionGemma-270M (Gemma-3-270M full-FT, run9) corre como un **segundo modelo** en el
split de Baxy: **SOLO elige tool+args (o `no_tool`)**, no conversa. El E2B sigue
conversando. Arquitectura del split:

```
Parakeet(STT,CPU) → Router(encoder MiniLM-FT,CPU) → FunctionGemma-270M(tools,:8082,CPU ~1.1GB)
                                                   → E2B Q4(habla+visión,:8080,GPU ~1.5GB) → Piper(TTS)
```

Reemplaza/mejora la EMISIÓN de tool-calls del E2B. Motivación medida: el E2B tiene
**sesgo español** — emite tools bien en español pero **pierde acciones en otros idiomas**
("set the volume" en, "quelle heure" fr, "abra a calculadora" pt: todas MISS con el E2B
solo). FunctionGemma las emite bien y multilingüe.

## Piezas (todo versionado)

| Pieza | Ruta | Qué hace |
|---|---|---|
| Módulo router | `gemma4_agent/routing/fg_router.py` | router jerárquico + cliente :8082 + bridge + auto-boot |
| Wiring | `gemma4_agent/agent_core/agent.py` | override gated de la decisión de tool (≈línea 3240) |
| Schemas slim | `gemma4_agent/data/fg/tool_schemas_slim.json` | 525 tools (con `no_tool`). **El FT se entrenó con SLIM** |
| Categorías | `gemma4_agent/data/fg/tool_categories.json` | familia→hijos para el stage-2 |
| Bridge map | `gemma4_agent/data/fg/tool_action_map.json` | `{compuesto::action: individual}` (reverse para dispatch) |
| Alias | `gemma4_agent/data/fg/baxy_alias_map.json` | sinónimos de args (handlers tolerantes) |
| GGUF | `models/FunctionGemma/functiongemma-ft-270m-it-Q8_0.gguf` | 278MB Q8_0, md5 b4ac42db86c75eeddff559515039bdac (Git LFS) |
| Validación | `scripts/_live_validate_fg_router.py`, `scripts/_measure_e2b_gate.py` | harness en vivo (regla #3.5) |

## Flujo por turno

1. El E2B corre como siempre (genera el reply conversacional + su propia decisión de tool).
2. `fg_emit(query, e2b_emitted=bool(raw_tool_calls))` decide el tool-call autoritativo:
   - **Gate acción-vs-conversación** (ver abajo). Si NO es accionable → `no_tool` → responde el E2B.
   - Si es accionable: router jerárquico (familias→hijos→top-K + `no_tool` siempre) → FunctionGemma elige.
   - **Bridge** individual→compuesto: `set_volume{level:40}` → `execute("audio",{action:"set_volume",level:40})`.
3. El agente ejecuta el tool elegido por FunctionGemma (o conserva el del E2B si FG no resolvió).

## EL FIX CRÍTICO — gate acción-vs-conversación (cazado en vivo, regla #3.5)

**Síntoma:** la 1ª integración rompía la abstención: "gracias"→memory_save, "hola"→notes,
"qué es pytest"→knowledge_search. En el handoff la abstención medía 93%; en Baxy 0/3.

**Causa raíz (medida):** el probe del handoff usa subsets de **4-5 tools diversos** y
FunctionGemma abstiene 93%. El router de Baxy genera subsets de **~11 tools dominados por
UNA familia** (para "gracias": 11 tools memory/reminder/notes). FunctionGemma (270M) es un
**mal abstenedor**: con un subset dominado por una familia se "deja arrastrar" y elige una
tool aunque el turno sea chitchat (eager invocation; SimpleToolHalluBench arXiv 2510.22977,
When2Call arXiv 2504.18851). El `no_tool` inyectado en el subset es necesario pero **no
suficiente** con subsets así. Bajar `tool_k` arregla la abstención pero pierde acciones
(tensión irreductible del eager-invocation).

**Solución (MEDIDA, batería 24 casos es/en/fr/pt):** NO se llama a FunctionGemma salvo que
el turno sea accionable, decidido por **DOS señales independientes en OR**:
- **(a) pico del encoder FT**: top-1 de familia ≥ `FG_ACT_PEAK` (0.52). Separación medida:
  chitchat top-1 ≤ 0.485, acción ≥ 0.565 (es/en/fr/pt) → 0.52 con margen a ambos lados.
- **(b) el E2B emitió un tool-call**: el E2B es abstenedor **perfecto** en chitchat (7/7
  medido) pero PIERDE acciones no-españolas; el pico (a) las rescata.

Chitchat requiere que fallen **ambas** (encoder<0.52 Y E2B abstuvo) → no pasa. Es
clasificación por embeddings multilingües con fallback seguro (permitido por CLAUDE.md), no
keywords ni listas. Cada modelo hace lo que sabe: **E2B = gate de conversación (es el LLM),
FunctionGemma = selector de tool+args**. Tunable con `GEMMA4_FG_PEAK`.

## Resultados medidos EN VIVO (regla #3.5)

Harness `scripts/_live_validate_fg_router.py` contra E2B :8080 (vram4) + FG :8082:

- **Abstención `no_tool`: 3/3** (era 0/3 sin el gate). Gate 8-13ms, ni llama a FunctionGemma.
- **Acciones: 9/9 ruteadas** correctamente, incluyendo el **rescate multilingüe** que el E2B
  solo perdía: "set the volume to 30"(en)→set_volume{30}, "what time is it"(en)/"quelle heure
  est-il"(fr)→system{time} con reply en el idioma correcto.
- Replies coherentes ("abrí la calculadora"→"Listo, estoy abriendo la calculadora").
- `fg_emit` standalone sobre 22 casos: no_tool 9/9, acción 12/13 (solo encoder, sin la señal E2B).
- Latencia FunctionGemma: 100-535ms/decisión tras warm-up (greedy temp 0).

**Sin regresión:** los cambios están gated tras `GEMMA4_FG_ROUTER` (default OFF). Suite de
routing/abstain sin regresión (la única falla, `test_ip_query_offers_network`, es
pre-existente de la poda de tools de Experimentando — verificado con y sin estos cambios).

## Infra — server FunctionGemma :8082

`ensure_fg_server()` en fg_router.py garantiza el server (CLAUDE.md regla #5):
- Idempotente: si :8082 ya está vivo (externo o ya booteado) reusa (medido 4ms).
- Si no, lo botea con el contrato handoff §2 (`--jinja -ngl 99 -c 4096 --no-webui`) y espera
  `/health`==200 (modelo listo, no solo puerto abierto). Cold-boot medido ~1-2s (270M).
- `atexit` mata el child al salir (en Windows el Popen NO muere con el padre → orphan; medido).
- Prewarm en **background** al startup del agente (gated): listo antes del turno 1, sin bloquear.
- Desactivable con `GEMMA4_FG_AUTOBOOT=0` (si se gestiona el server por fuera).

## VRAM / recursos (MEDIDO en RTX 4060 Ti, config prod vram4)

Medición por diferencia controlada desde baseline limpia (1859 MiB = solo escritorio).

| Config | VRAM de Baxy |
|---|---|
| E2B Q4_K_M + mmproj Q8 (habla+visión, GPU) | ~2907 MiB ≈ 2.84 GB |
| + FunctionGemma en GPU (`-ngl 99`) | +960 MiB → **3.78 GB total** |
| + FunctionGemma en **CPU** (default) | +0 MiB → **2.84 GB total** |

FunctionGemma corre **CPU-only por default** (`CUDA_VISIBLE_DEVICES=-1`): en CPU el 270M
decide en ~70-150ms (medido, sobra para el budget de voz) y libera la GPU para el E2B.
**GOTCHA medido:** con el build CUDA de llama-server, `-ngl 0` NO da 0 VRAM — igual reserva
~0.9 GB de compute buffer en la GPU; hay que OCULTAR la GPU. `GEMMA4_FG_GPU=1` lo pone en GPU.

No se usa la iGPU (Intel UHD) porque: el build de llama.cpp es CUDA-only (sin Vulkan/SYCL),
la iGPU usa la misma RAM del sistema (no ahorra nada extra), y el CPU (i9-12900HX) le gana a
esa iGPU para un 270M. Desglose por buffer en el cuerpo del doc / logs de llama.cpp.

## Cómo activar

```
GEMMA4_FG_ROUTER=1 GEMMA4_LEAN_TOOLS=0   # requiere las 67 familias para tool_categories
```
El server :8082 se autoboot-ea (o levantarlo manual con el comando del handoff §2).

## Residuales conocidos (NO bloqueantes — del handoff §6)

- **Confusión de tools hermanas** (long-tail del 270M): "guardá que me gusta X" → reminder en
  vez de memory; "abra a calculadora"(pt) → computer_use en vez de app. Los args se extraen
  bien; solo el ruteo cae a la hermana. Palanca futura: datos contrastivos hand-crafted.
- **web_search a veces sin query completa** ("buscá el clima"→web{search} con query parcial).
- **Confabulación del E2B con guards OFF** (neto): "gracias"→reply confabulado. Es el issue
  del `GEMMA4_GUARDS=0`, NO del router (FunctionGemma abstuvo bien). Re-agregar honesty-guards
  gated lo cubre. Ver `_BAXY_NETO_2026-06-17.md`.
