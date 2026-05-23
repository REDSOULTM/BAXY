# Prompt de investigación 1/8 — Fiabilidad de tool-calling y structured output en Gemma 4 E4B (4B local)

Copiá esto a Claude (research/web). Tema ESPECÍFICO: hacer que el modelo de 4B
emita tool-calls válidos de forma fiable, sin depender del reasoning largo.
Distinguí confirmado de hipotético, citá fuentes 2025-2026 sobre SLMs <10B y
llama.cpp. Dame código/flags. NO repitas lo que ya tenemos (sección 2).

## 0. Stack
Gemma 4 E4B-it Q4_K_M GGUF, llama.cpp b9090, `--jinja`, monoslot, 6 GB, voz
local. Function-calling nativo (`<|tool_call|>`). 65 tools; router da 4-6/turno.


## RESTRICCIÓN DURA (innegociable): TODO debe correr en vram4 = E4B-Q4
El perfil DEFAULT es vram4 (Gemma 4 E4B-it Q4_K_M, ~4B cuantizado, GPU
modesta ~4-6 GB, latencia tier-Alexa 4-5 s). RED quiere que vram4 sea capaz
de TODO esto — NO asumir un modelo más grande ni subir de perfil. Ninguna
solución puede inflar VRAM/latencia fuera del budget de vram4 ni meter un 2º
modelo pesado. Lo que necesite 'inteligencia' extra: preferí CÓDIGO
DETERMINISTA + el LLM solo para lo conversacional. Cualquier recomendación
que requiera >4B o más VRAM debe marcarse NO-VIABLE-EN-VRAM4 con una
alternativa que sí entre.

## 1. El problema medido
- Con reasoning ON: tool-call correcto 6/6 en comandos crisp. Con reasoning OFF:
  **2/6** — el modelo "promete" la acción en texto sin emitir el tool-call.
- Por eso hoy dependemos del thinking (cuesta p90 268 tok / hasta 4.3 s). Quitar
  el thinking para ganar latencia rompe la fiabilidad. Queremos romper ese
  acoplamiento: tool-call fiable SIN reasoning caro.
- Sampling actual: temp=1.0, top_p=0.95, top_k=64 (defaults Gemma) en TODOS los
  modos — alto para una decisión determinista como elegir tool+args.

## 2. Lo que YA tenemos (no recomendar)
- `tool_choice="required"` como forced-retry (1 vez/turno) cuando el modelo no
  emite tool-call. Funciona pero gasta una 2ª llamada.
- leaked-tool-call rescue (parsea un tool-call emitido como texto).
- Router que limita a 4-6 tools (el 4B se confunde con 65).
- thinking_budget por modo.

## 3. Lo que quiero investigado
1. **GBNF / grammar-constrained decoding en llama.cpp para tool-calls**: ¿se puede
   GARANTIZAR un tool-call válido (JSON conforme al schema) con grammar, SIN
   reasoning, en Gemma 4 + `--jinja`? ¿Cómo interactúa la grammar custom con la
   gramática interna que `--jinja` ya genera para function-calling? ¿`response_
   format: json_schema` es mejor que grammar raw acá? ¿Acelera o frena el TTFT?
   ¿Sirve para curar el 2/6 sin el costo del thinking?
2. **Sampling óptimo para tool-calling**: ¿greedy/low-temp para modos de acción
   mejora la tasa de tool-call correcto vs temp=1.0? ¿Degrada el lenguaje del
   reply? Evidencia en SLMs. Dame valores concretos a probar (temp/top_k/min_p).
3. **El acoplamiento reasoning↔tool-call en modelos 4B**: ¿por qué el reasoning
   sube el tool-call de 2/6 a 6/6? ¿Es atención/formato/confianza? ¿Hay un
   sustituto barato del reasoning (few-shot de tool-calls, system prompt
   estructurado, prefill del canal de tool) que dé la misma fiabilidad sin el
   costo de generar 268 tokens? Evidencia (BFCL, ToolBench, papers SLM 2025-26).
4. **Few-shot / prompt para tool-calling en 4B**: ¿2-4 ejemplos `usuario→<|tool_
   call|>` en el system prompt re-condicionan la cabeza de salida hacia el tool
   token y curan el 2/6? ¿Cuántos ejemplos, qué formato, costo en prefill?
5. **Fine-tune ligero (QLoRA)** como último recurso: ¿vale el ROI sobre prompting
   para subir la fiabilidad de tool-call en este 4B? (ej. FunctionGemma 58→85%).

## 4. Formato
Por punto: diagnóstico, tabla comparativa (tasa tool-call %, latencia, riesgo),
fuentes recientes, veredicto VIABLE para este stack, código/flags. Marcá lo que
medimos nosotros (smoke E2E). Priorizá 1 y 2 (bajo riesgo, alto impacto).
