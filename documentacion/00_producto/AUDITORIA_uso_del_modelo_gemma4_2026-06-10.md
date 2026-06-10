# Auditoría: ¿usamos Gemma 4 E2B de la mejor forma posible? (2026-06-10)

Contraste de 3 fuentes: (a) docs internos del repo sobre el modelo, (b) fuentes
OFICIALES de Google (model card Gemma 4, ai.google.dev) + investigación citada,
(c) el CÓDIGO real del proyecto. Pregunta: ¿le sacamos todo el potencial?

## Identidad y contrato del modelo (verificado correcto)

- Modelo en prod: **`gemma-4-E2B-it-Q4_K_M`** (Gemma 4 oficial, NO Gemma 3n — el
  caveat de la investigación queda descartado; sí es la familia con thinking
  nativo `<|think|>` y tool-call `<|tool_call|>`).
- Servido con `--jinja` (template embebido del GGUF) + `chat_template_kwargs:
  {enable_thinking}` + `parse_tool_calls` + formato nativo. **Alineado con lo
  oficial.** (model card: thinking vía `<|think|>`, tool-call nativo).
- E2B oficial: 2.3B efectivos, 128K ctx, Per-Layer Embeddings. Usamos ctx 16384
  (suficiente para voz; 128K no cabe en 4GB ni hace falta).

## Tabla de auditoría: recomendación → ¿implementado?

| Recomendación (fuente) | Estado en el código | Veredicto |
|---|---|---|
| **Sampling greedy en acción** (1_toolcalling; oficial dice temp=1 para chat, no tool) | ✅ `GEMMA4_GREEDY_TOOLCALL=1` (temp=0,top_k=1) en turno de acción | **ÓPTIMO** — bajamos la entropía donde importa, dejamos defaults en charla |
| **Thinking gateado por complejidad** (Ares −52% tokens; Punto 4) | ✅ `modes.py`: fast_action/fast_info `enable_thinking=False`; quick/deep/vision condicional con `thinking_budget` | **ÓPTIMO** — exactamente el router de complejidad recomendado |
| **`thinking_budget_tokens` por modo** | ✅ quick=32, deep/research mayores; en el body | **OK** (red de seguridad, no mecanismo principal — correcto) |
| **`--reasoning-budget-message`** (cierre limpio) | ✅ implementado, tag `<channel|>` verificado x2 (GGUF + llama.cpp source) | **OK** (impacto chico y honesto, documentado) |
| **Few-shot positivo para tool-call** (mitigar 2/6) | ✅ `action_fewshot.py` (2026-06-10): few-shot dinámico de la tool ofrecida | **ÓPTIMO** — recién agregado, +14pp medido (71→85%) |
| **Prefill `<|tool_call|>`** (Punto 4 mitigación 1) | ⚠️ NO implementado (el few-shot lo sustituye en parte) | **OK aceptable** — el few-shot da el lift; el prefill es +2/6 adicional incierto |
| **--flash-attn on** (oficial Gemma + SWA) | ❌ OFF por default | **CORRECTO desviarse** — crash CUDA #22527 medido con FA+SWA+prompt grande; OFF es estable (37/37) |
| **--cache-reuse** (prefix-cache) | ❌ REMOVIDO | **CORRECTO desviarse** — dispara CUDA #17109; `--keep -1 + --swa-full` captura el prefix igual |
| **--cache-type-k/v q8_0** (−0.5GB KV, +0-2% decode) | 🔲 NO aplicado | **CANDIDATO REAL** — liberaría ~0.5-1GB VRAM con riesgo ~0 (sin draft). No medido aún |
| **Speculative decoding (n-gram)** | ❌ no usado | **CORRECTO descartar** — benchmarks: −3 a −12% en hardware comparable, prompts diversos |
| **FR-CoT structured brief CoT** (Qi 2026, +45% rel en BFCL) | 🔲 NO implementado como template explícito | **CANDIDATO** — el thinking ya es chico (0-102 tok medido) por el gateo; el ROI marginal puede ser bajo. MEDIR primero |
| **TTS paralelo / speculative tool-call** (enmascara 1-2s percibidos) | 🔲 parcial (`GEMMA4_STREAM_TTS` existe, default OFF) | **CANDIDATO de UX** — alto ROI percibido, no computacional |
| **Q4_K_M (no bajar de Q4)** | ✅ Q4_K_M | **ÓPTIMO** — la investigación (DECISION_MAESTRA_4GB) lo fija como piso seguro |

## Veredicto: SÍ, lo usamos muy bien — con 2-3 mejoras posibles acotadas

**Lo que está ÓPTIMO (la mayoría):** sampling dual greedy, gateo de thinking por
complejidad, few-shot dinámico, reasoning-budget, formato nativo correcto, Q4_K_M.
Las desviaciones de la guía oficial (FA off, sin cache-reuse) son **decisiones
medidas correctas** por bugs reales de CUDA, no descuidos. El proyecto NO trata
mal al modelo: las palancas de mayor ROI de la literatura YA están aplicadas.

**Candidatos REALES no explotados (rankeados, todos a MEDIR antes — regla #3.5):**

1. **`--cache-type-k q8_0 --cache-type-v q8_0`** (afinación segura). Libera
   ~0.5-1 GB de VRAM en ctx 16384 con riesgo ~0 (no usamos draft model, donde
   estaba el bug #10552). Ese margen permite o más ctx, o más holgura con visión
   residente. **Mayor ROI/riesgo de lo que queda.** Verificar que no reintroduce
   el crash CUDA con SWA en el build b9090.

2. **TTS paralelo / confirm filler** (UX). El `GEMMA4_STREAM_TTS` existe pero
   está OFF. Un "confirm filler intent-aware" ("Abriendo Steam…") mientras el LLM
   piensa enmascara 1-2s percibidos. No baja latencia real, sí la percibida.
   Complejidad media (orquestación TTS).

3. **FR-CoT brief template** (calidad de tool-call). Solo si se mide que el
   thinking de quick/deep_action genera outliers >100 tok en uso real. Hoy el
   thinking ya es chico por el gateo, así que el lift puede ser marginal. NO
   asumir el +45% de Qwen2.5 — es otro modelo. Medir distribución de tokens en
   n≥100 turnos reales ANTES de implementar.

**Lo que NO vale tocar:** speculative decoding (descartado con datos), bajar de
Q4 (degrada), forzar FA on (crash), prefill agresivo (el few-shot ya da el lift).

## Lo único oficial que NO aprovechamos (y por qué está bien)

- **128K de contexto:** usamos 16384. No cabe en 4GB ni se necesita para voz
  (turnos cortos). Correcto.
- **temp=1.0/top_k=64 oficial:** lo usamos SOLO en charla; en acción bajamos a
  greedy. La guía oficial es para generación general, no tool-calling — la
  investigación (1_toolcalling) lo respalda y Google no da guía específica de
  tool-call. Correcto.
- **Visión/audio nativos:** visión SÍ (mmproj residente); audio nativo NO se usa
  (Whisper/Parakeet en CPU es mejor WER + 0 VRAM — DECISION_MAESTRA lo midió).

## Implementación de los candidatos (2026-06-10)

**#1 KV-cache K q8_0 — APLICADO (con caveat de medición).**
`--cache-type-k q8_0` en `llama_server.py`, GPU-only, kill-switch
`GEMMA4_KV_CACHE_K`. CLAVE descubierta investigando: **solo se cuantiza K, NO V**
— el V cache cuantizado EXIGE flash-attn ("V cache quantization requires
flash_attn", llama.cpp #21450/#19036) y tenemos FA OFF por el crash #22527.
Cuantizar V rompería el arranque; cuantizar solo K es seguro sin FA. Verificado:
el cmd arma `--cache-type-k q8_0` y NO `--cache-type-v`. Suite server/config/
profile 141/141. CAVEAT HONESTO: no se pudo medir el ahorro de VRAM en vivo (el
sandbox no deja arrancar un server de prueba con el binario); el ahorro (~la
mitad del KV de la capa K) se confirmará al reiniciar el server. Bajo riesgo y
reversible.

**#3 FR-CoT brief template — DESCARTADO por medición.** Medí la latencia por
turno: el thinking CALIENTE ya es 1.4-3.0s (chico, por el gateo de modos). El
outlier observado ("qué hora es" 18-20s en la 1ª corrida, 1.4-3s en las
siguientes) NO es overthinking — es **cold-start del prefix-cache** (re-prefill
del prompt en la 1ª llamada). FR-CoT NO arregla cold-start (es ortogonal). El
lift sería marginal y solo en quick/deep_action, que ya tienen thinking acotado.
No vale la complejidad. Confirma la sospecha de la auditoría.

**#2 TTS paralelo / confirm filler — PENDIENTE (válido, UX).** No tocado aún.
Sigue siendo el candidato de UX (enmascara latencia percibida, incluido el
cold-start de prefill que SÍ existe). El flag `GEMMA4_STREAM_TTS` existe (OFF).
Es trabajo de orquestación TTS, sesión dedicada.

## Fuentes

- [Gemma 4 model card (oficial Google)](https://ai.google.dev/gemma/docs/core/model_card_4)
- [Gemma 4 overview (oficial)](https://ai.google.dev/gemma/docs/core)
- Docs internos: `1_toolcalling.md`, `reducir_latencia_thinking_gemma4.md`,
  `DECISION_MAESTRA_4GB.md`, `GEMMA4_modelo_finetune_idioma_2026-06-06.md`,
  `Gemma4_estado_y_limites_2026_05_29.md`.
- Código: `infra/llama_server.py`, `infra/llm_client.py`, `support/modes.py`,
  `routing/action_fewshot.py`.
