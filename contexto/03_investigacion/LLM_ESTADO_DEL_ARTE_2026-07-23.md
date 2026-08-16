# Auditoría LLM de BAXY — estado del arte y decisión 2026-07-23

## Decisión

Se mantiene **Gemma-4 E2B-it QAT, GGUF Q4_K_XL, llama.cpp CUDA**, no E4B.
Es el punto Pareto vigente para BAXY: es el modelo pequeño actual dirigido a
edge, aporta razonamiento, multilingüe, system prompt y function calling
nativos, y cabe con margen real dentro del límite de **3 GiB de VRAM de la
mente completa**. La mente no usa esa capacidad para ejecutar directamente:
el planner y el core determinista siguen siendo la única autoridad.

No se sustituye Parakeet, VAD, KWS ni SAPI por el audio nativo de Gemma. Aunque
E2B soporta audio, el pipeline actual ya está verificado, corre en CPU y evita
competir por la VRAM que necesita el razonamiento. La integración multimodal se
reabre sólo ante un caso de producto y una medición integral mejores.

## Investigación desde hoy hacia atrás

1. **23-07-2026, Google, documentación vigente.** Gemma 4 declara E2B como
   modelo edge de 2,3B parámetros efectivos (5,1B con PLE), 128K de contexto,
   texto/imagen/audio, multilingüe, system role, thinking configurable y
   function calling nativo. También publica draft MTP para decodificación
   especulativa. Fuentes primarias:
   <https://ai.google.dev/gemma/docs/core/model_card_4>,
   <https://ai.google.dev/gemma/docs/core> y
   <https://ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4>.
2. **23-07-2026, runtime vigente.** llama.cpp mantiene Flash Attention y KV
   cuantizado para CUDA; ambos reducen presión de memoria del contexto sin
   reducir los pesos del modelo. Fuente primaria:
   <https://github.com/ggml-org/llama.cpp/blob/master/tools/completion/README.md>.
3. **Antecedentes internos, 16-07-2026.** El torneo reproducible de BAXY ya
   midió los candidatos bajo el catálogo real y probes ES/EN/spanglish. E2B
   obtuvo el mejor score compuesto (0,846), 92,9 % de abstención negativa,
   87 % de conversación juzgada y cero llamadas mutantes. Qwen 3.5 4B mejoró
   tool+args (84,8 %) pero consumió 3.028 MiB y fabricó una capacidad; modelos
   de 0,8B y 1,2B no superaron la abstención segura. Evidencia:
   `experiments/mind_llm_tournament/results/llm_tournament_scorecard.json` y
   `experiments/mind_llm_tournament/results/convo_judged_review.md`.

## Descartes actuales

| Opción | Motivo |
|---|---|
| Gemma 4 E4B | Q4_K_M publicado ~5 GB: no cumple el límite. |
| Qwen 3.5 4B | Mejor extracción cruda en el torneo, pero 3.028 MiB y fallo de capacidad inventada; no deja margen para el producto. |
| Qwen 3.5 0.8B / LFM2.5 1.2B | Más baratos, pero el torneo BAXY rechazó su precisión/abstención para acciones. LFM sigue siendo candidato futuro de clasificación, no de planner. |
| MTP draft | Es una optimización de velocidad sin pérdida de calidad publicada por Google, pero añade otro modelo y memoria. Bajo 3 GiB se mantiene fuera hasta una medición física que demuestre margen. |

## Aplicación técnica de esta decisión

- Contexto máximo fijo de **4.096 tokens**, no los 128K nominales: BAXY no
  necesita cargar una transcripción ilimitada para un turno de PC y el límite
  preserva VRAM, latencia y privacidad.
- Historial saneado: sólo turnos `user`/`assistant`, como máximo 12 y 6.000
  caracteres. Nunca se admiten `system` ni `tool` inyectados desde el cliente.
- Chat no acepta catálogo ni devuelve tool calls: las acciones pasan sólo por
  `plan` y por el core, que revalida schema, riesgo, confirmación y resultado.
- llama-server se inicia con una sola ranura, Flash Attention y KV Q8 (`-np 1
  -fa on -ctk q8_0 -ctv q8_0`). La configuración fue probada contra el gate
  de comportamiento: 25/25, máximo 0,901 s.

## Medición local más reciente

Con la configuración Q8/Flash Attention y contexto 4K, el proceso de prueba
añadió **1.507 MiB** de VRAM sobre el baseline del equipo (3.700 MiB total con
el proceso; 2.193 MiB sin él). Wake word, VAD, router, STT y TTS no consumen
VRAM en esta arquitectura. El consumo queda aproximadamente a la mitad del
presupuesto de 3.072 MiB; no es una afirmación sobre otros procesos ajenos de
Windows. La compuerta integrada formal sigue siendo
`scripts/measure_mind_budget.py` y debe correrse de nuevo antes de elevar
contexto, slots, modelo o introducir MTP.
