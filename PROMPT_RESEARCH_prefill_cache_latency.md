# PROMPT RESEARCH — Bajar la latencia de PREFILL en Gemma 4 + llama.cpp (FA-off): prefix-cache reuse y estabilidad de prefijo entre pasadas

## El objetivo (lo importante)

En un asistente de voz LOCAL (Gemma 4 E2B-it Q4_K_M en llama.cpp, **4 GB de VRAM techo**, Windows), cada turno de ACCIÓN hace **2 llamadas al LLM** (pass-1 = decidir + emitir tool-call; pass-2 = confirmar el resultado). **Medí el desglose en vivo** y el costo dominante NO es el decode ni el thinking: es el **PREFILL del prompt** (~2.3 s sumando las 2 llamadas; el decode total es ~0.9 s).

**Quiero que investigues cómo reducir ese prefill** sin sacrificar tool-calling, calidad ni la restricción de 4 GB, en el stack EXACTO que uso (detallado abajo). En particular dos palancas que detecté y necesito que valides/ataques:

1. **Re-habilitar prefix-cache reuse** ahora que `--flash-attn off` eliminó el crash que obligó a removerlo.
2. **Estabilizar el prefijo entre las 2 pasadas** (hoy la pass-2 re-prefilea ~5.3k tokens por un cache-miss auto-inducido).

## Stack exacto (no asumas otra cosa)

- Modelo: `gemma-4-E2B-it-Q4_K_M.gguf`, contexto 16384, visión mmproj lazy.
- llama.cpp build **b9384** (router mode: un `llama-server` proxy en :8080 enruta a un server hijo por perfil). Antes b9090.
- Hardware del dev: RTX 4060 Ti 16 GB (mide acá), pero el **TARGET REAL es 4 GB** (ej. RTX 1650) — toda recomendación debe entrar en 4 GB.
- **`--flash-attn off` es DEFAULT ahora** (eliminó el crash CUDA #22527 del kernel FA+SWA de Gemma 4; medido 37/37 turnos OK vs 6/37 con FA on). Costo: prefill ~2× más lento.
- Gemma 4 = arquitectura híbrida con **SWA (sliding window attention)** + full attention, **head sizes mixtos** (no-SWA 512 / SWA 256), **shared KV cache**. Flag `--swa-full` está activo.
- System prompt + tools ≈ **5k tokens** (ya optimizado: lean mode bajó de 9.4k→5k; Plan A2 redujo reglas always-on 15→6).
- Sampling acción: greedy (temp 0). Thinking: quick_action con `thinking_budget=32` (cap bajo). **Medí que el thinking es load-bearing**: sin él el tool-calling cae 4/6 → 0/6.

## Lo que MEDÍ en vivo (datos reales, 2026-05-28)

Turno de acción limpio ("subí el volumen al 40 por ciento", el modelo emite tool-call `audio`):

| pasada | PREFILL (tokens / ms) | DECODE (tokens / ms) | wall |
|---|---|---|---|
| **pass-1 (decidir)** | 5854 tok / **1222 ms** | 55 tok / 732 ms | 2.00 s |
| **pass-2 (confirmar)** | 5363 tok / **1083 ms** | 13 tok / 167 ms | 1.28 s |

- **El prefill domina** (~2.3 s de ~3.3 s de tiempo-LLM). El decode es chico.
- **Observación CLAVE**: la pass-2 re-prefilea **5363 tokens** aunque comparte casi todo el system prompt con la pass-1. Esto pasa porque la pass-2 **DROPEA las tool-schemas del prompt** (optimización "summary slimming" para ahorrar ~1.5k tokens) → cambia el PREFIJO → **cache-miss** → re-prefill casi completo. Sospecho que el ahorro de tokens (1.5k) se lo come el cache-miss (re-prefilar 5.3k).
- En otro turno ("minimizá la ventana") la pass-1 prefileó solo **1656 tokens** → o sea **el prefix-cache SÍ funciona parcialmente** entre turnos cuando el prefijo se mantiene.

## Preguntas concretas (lo que necesito que respondas, con fuentes)

### A. Prefix-cache reuse con Gemma 4 + FA-off + SWA
1. El `cache-reuse` / KV-cache reuse se **removió a propósito** porque disparaba el crash #22527 (con FA on). Ahora con **FA off**: ¿se puede re-habilitar `--cache-reuse N` (o el mecanismo equivalente del build b9384) **sin que vuelva a crashear**? ¿El crash era del kernel FA (entonces FA-off lo cura para cache-reuse también) o del path de `create_checkpoint`/`llama_state_seq_get_data_ext` (que sería independiente de FA)?
2. ¿Cuál es la **config óptima de prefix-cache para Gemma 4 con SWA + FA-off** en llama.cpp b9384? Flags exactos (`--cache-reuse`, `--swa-full`, `--keep`, `-c`, ctx-checkpoints, etc.), su interacción, y los **defaults peligrosos**. ¿`--swa-full` es necesario/suficiente para que el reuse funcione con SWA, o el sliding window invalida el cache de los tokens fuera de la ventana?
3. ¿Hay issues conocidos de prefix-cache + Gemma 4 SWA en builds recientes (≥b9090)? (ej. #21468 cache-reuse Gemma 4). ¿Estado actual?

### B. Estabilidad del prefijo entre las 2 pasadas (el cache-bust auto-inducido)
4. **RESULTADO QUE NECESITO QUE EXPLIQUES (medido 2026-05-28):** probé mantener las tools en la pass-2 para que el prefijo == pass-1, esperando un cache-hit. **NO funcionó**: la pass-2 re-prefileó **5919 tokens** (con tools) vs **5243** (sin tools) — o sea **re-prefila TODO igual, NO hubo cache-hit aunque el prefijo coincidía**. Conclusión: el prefix-cache **NO está reusando within-turn** (entre pass-1 y pass-2 del MISMO turno, requests secuenciales al mismo server), independientemente de si el prefijo matchea. **¿POR QUÉ?** Candidatas a confirmar/refutar: (a) SWA invalida el KV de tokens fuera de la ventana deslizante → el reuse no aplica al prefijo largo; (b) el slot se evicta/reasigna entre requests; (c) `--keep -1 + --swa-full` SIN `--cache-reuse` solo hace LCP desde el token 0 y algo del prefijo difiere temprano (¿el render del chat-template mete algo antes de las tools?); (d) hace falta `--cache-reuse N` explícito (que removí por el crash) para que reuse el prefijo. Esta es **la pregunta central**: ¿qué hace falta para que la pass-2 reuse el KV de la pass-1 (mismo prefijo) en lugar de re-prefilar 5k+?
5. Asumiendo que se resuelva (4): trade-off de **mantener tools** (prefijo estable, +1.5k tokens pero cache-hit → prefilar ~50 nuevos) **vs dropearlas** (−1.5k tokens pero re-prefill completo). ¿Best-practice para turnos multi-pasada con KV reuse (prefijo byte-idéntico)?
5. ¿Qué rompe el prefix-cache en llama.cpp además de cambiar el set de tools? (orden de mensajes, timestamps en el system, IDs de tool_call, `chat_template_kwargs` que varían, etc.) — quiero una checklist de "qué mantener byte-estable" para maximizar cache-hit en un agente multi-turno.

### C. Otras palancas de prefill (4 GB / Gemma 4 / OSS)
6. ¿Otras formas de bajar los ~1.2 s de prefill de un prompt de 5-6k tokens con FA-off en 4 GB? (ej. KV cache quantization `-ctk/-ctv q8_0`, `--no-context-shift`, batch/ubatch tuning para prefill, etc.) — con su impacto en VRAM y el riesgo de re-disparar el crash.
7. ¿Conviene `tool_choice="required"` + un tool sintético `respond_in_natural_language` para eliminar la rama de prosa (lo vi sugerido), y eso cómo afecta el prefill/cache?

## Restricciones DURAS (descartá lo que las viole)
- **Gemma 4 sí o sí** (no Llama/Qwen/otro). **OSS/gratis** (no cloud, no APIs pagas).
- **4 GB de VRAM** techo (el dev mide en 16 GB pero el target es 4 GB).
- **0 crashes CUDA** en 50 turnos variados (el crash #22527 fue el dolor #1; cualquier reuse debe probarse contra él).
- Multi-usuario / multi-idioma (sin hardcodes por idioma).
- Latencia objetivo: turno de acción ≤ 5 s (hoy ~3.5 s LLM + tool + TTS).

## Ya medido / descartado (no repitas, citalo si lo desafiás)
- Lean prompt (9.4k→5k) + Plan A2 (15→6 reglas always-on): YA aplicado, fue el gran win de prefill.
- Bajar/sacar thinking: el thinking es load-bearing (sin él tool-calling 4/6→0/6). Greedy ya está aplicado.
- Prefill del token `<|tool_call|>` (assistant-prefix continuation): NO parece soportado limpio bajo `--jinja`+tools, y el techo de win (~0.4-0.9s del decode) es chico vs el prefill. (Confírmalo o refútalo.)
- Streaming token→TTS de la confirmación: medido, ~0 win (la confirmación es corta; el costo es prefill, no decode).
- FA on: crashea (#22527). NO es opción.

## Formato de respuesta esperado
Por cada palanca: (1) qué hacer concreto (flags/código/config), (2) por qué (con fuente — issue de llama.cpp, PR, doc, paper, fecha), (3) impacto esperado en latencia de prefill + VRAM, (4) riesgo (sobre todo de re-disparar el crash) y cómo medirlo. Priorizá por impacto×seguridad. Sé escéptico con lo no verificado y marcá hipótesis vs hecho. Cerrá con un orden recomendado de experimentos.
