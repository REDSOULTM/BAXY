# Prompt de investigación — Latencia del THINKING (no del prefill) en Gemma 4

Copiá esto a claude.ai (con research/web). Es la SEGUNDA iteración del problema
de latencia: la primera atacó el prefill (prefix-cache) y MEDIMOS que el router
ya lo controla y que estabilizar el prefijo NO rinde en E2E real. El cuello real
es el **thinking** (reasoning antes del tool-call). Quiero informe técnico
accionable con código/flags, distinguiendo confirmado de hipotético, fuentes
recientes. NO repitas lo del prefix-cache (ya descartado).

---

## 0. Stack (confirmado en código)

- Modelo **Gemma 4 E4B-it Q4_K_M** (GGUF), llama.cpp `llama-server` **b9090+**,
  monoslot, 6 GB VRAM, Windows. Asistente de VOZ: budget tier-Alexa 4-5 s/turno.
- Flags: `--jinja --flash-attn on --swa-full --cache-reuse 256 --keep -1 -c 16384
  --parallel 1`. Gemma 4 = atención híbrida SWA(512)+global, function-calling
  nativo vía `<|tool_call|>`/`--jinja`. Soporta `thinking_budget_tokens` en el
  body (verificado en b9090).

## 1. Diagnóstico MEDIDO (logs de llama-server, sesión real)

- **La latencia tiene DOS fuentes; la primera investigación atacó la menor:**
  - **Prefill: mediana ~888 ms** (reprocesar prompt). El router ya da subsets
    chicos cacheables; estabilizar el prefijo con un core-set fijo se PROBÓ y dio
    ~2x PEOR en E2E real (prompt más grande no compensa el cache). DESCARTADO.
  - **THINKING/generación: el cuello real.** Distribución de tokens generados
    por turno (n=355): mediana 23 tok (rápido), **p75=98, p90=268, max=841**.
    A 62 tok/s. **El 23% de los turnos genera >100 tok (thinking largo) y cuesta
    4.3 s mediana** — son los outliers que rompen el budget de 4-5 s.
- **Por qué hay thinking**: MEDIDO (E4B-Q4) que Gemma 4 con reasoning OFF emite
  el tool-call solo ~2/6 veces (promete la acción en texto sin llamar la tool);
  con reasoning ON, 6/6. **El thinking es lo que hace FIABLE el tool-calling en
  este modelo chico.** Por eso NO se puede simplemente apagar.
- Ya hay `thinking_budget` por modo (quick_action=256, deep_action/vision=1024,
  research=2048). El modelo normalmente auto-termina el reasoning bajo el budget,
  pero a veces se dispara (los casos de 268-841 tok / >4 s).

## 2. La tensión central

Reasoning ON = tool-calling fiable (6/6) pero latencia variable (a veces 4 s+ de
puro thinking). Reasoning OFF = rápido (0.4-2 s) pero tool-calling no fiable
(2/6). Buscamos **bajar el costo del thinking SIN perder la fiabilidad** del
tool-calling en un modelo de 4B local.

## 3. Lo que necesito investigado (con código/flags y fuentes)

1. **Reducir tokens de thinking sin perder fiabilidad de tool-call** en LLMs
   chicos: ¿prompting que fuerce reasoning BREVE y dirigido a la decisión de
   tool ("piensa en ≤1 frase qué tool y argumentos, luego llama")? ¿budgets más
   agresivos por tipo de comando? ¿"reasoning estructurado/templated" que evite
   el divague? Evidencia de qué recorta el reasoning sin bajar la tasa de
   tool-call correcto en modelos <10B.

2. **Speculative / draft decoding para acelerar la GENERACIÓN** (que es donde
   está el costo, 62 tok/s × cientos de tok): la 1ª investigación lo marcó
   arriesgado en 6 GB (target E4B-Q4 + drafter MTP no carga en mainline
   llama.cpp, issue #22337; VRAM justa). RE-EVALUAR específicamente para el
   thinking: ¿n-gram self-speculation (`--draft-min/--draft-max` sin draft model,
   0 VRAM) acelera el reasoning repetitivo/estructurado? ¿Cuánto, con qué riesgo
   de regresión? ¿Vale para los turnos de 268-841 tok?

3. **¿El thinking se puede hacer en paralelo / pipeline con algo?** Ej. empezar
   a hablar (TTS) la confirmación mientras razona, o pre-emitir feedback. ¿O un
   modo "responde la confirmación corta primero, ejecuta la tool después"?

4. **Detección temprana de cuándo NO hace falta thinking**: hay comandos triviales
   ("abre steam") donde el tool es obvio. ¿Un clasificador barato (o el propio
   router) puede marcar "tool-call directo sin reasoning" para los crisp, dejando
   el thinking solo para los ambiguos? ¿Cómo decidir esto de forma fiable sin
   reintroducir el fallo 2/6?

5. **`thinking_budget_tokens` de llama.cpp/Gemma 4**: ¿cómo funciona exactamente
   (corta el reasoning duro? degrada la salida si corta a media frase?)? ¿Valor
   óptimo para tool-calling fiable pero acotado? ¿Interactúa con `--jinja`?

6. **Quant/decoding tricks que aceleren generación sin tocar fiabilidad**: ¿flags
   de sampling (greedy vs temp), `--cache-type-k/v q8_0`, batch de generación?
   Qué da ROI real en E4B-Q4 / 6 GB para la fase de DECODE (no prefill).

## 4. Formato

Por cada punto: diagnóstico, opciones con tabla (criterios medibles: ms de
generación, % tool-call correcto, VRAM, riesgo), fuentes oficiales/papers/PRs
recientes, veredicto VIABLE para ESTE stack (E4B-Q4, llama.cpp b9090+, 6 GB, voz
tier-Alexa). Snippets de código Python y/o flags listos para pegar. Priorizá los
puntos 1 y 4 (recortar/evitar thinking sin perder fiabilidad) — son el mayor ROI
según la medición. Sé honesto si algo no aplica a 6 GB.
