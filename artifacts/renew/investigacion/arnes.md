# Arnés para un 4B: exposición de herramientas, latido y falsedades — investigación (2026-10-15, subagente del PC)

Fuentes leídas el 2026-10-15. **[inferencia]** = razonamiento propio, no de la fuente.

## OpenClaw

- **Skills:** carpeta con `SKILL.md` (frontmatter YAML). En el prompt sólo va un índice `<available_skills>` (nombre,
  descripción, ubicación, ~24 tokens por skill); el modelo lee la skill entera con su herramienta `read` cuando aplica.
  (docs.openclaw.ai/skills, /concepts/system-prompt)
- **Tool Search** por defecto: `tool_search`, `tool_describe`, `dispatch_action` y un directorio; el resto diferido.
  Avisos de la propia doc: con catálogos chicos los turnos extra se comen el ahorro; los modelos locales aplanan los
  argumentos de `dispatch_action`. (docs.openclaw.ai/tools/tool-search, /gateway/local-models). Sin cifras publicadas
  con modelos chicos.
- **Latido** (openclaw@2026.6.6 docs/gateway/heartbeat.md): cada 30 min por defecto; mensaje «Read HEARTBEAT.md if it
  exists… Follow it strictly. Do not infer or repeat old tasks from prior chats. If nothing needs attention, reply
  HEARTBEAT_OK»; `HEARTBEAT_OK` al inicio o final y respuesta ≤ 300 caracteres → se descarta; `isolatedSession`
  (sin historial, 2–5k tokens) y `lightContext`; eventos con `system event --mode now`; se salta si el carril principal
  está ocupado. El riesgo se controla fuera del prompt (aprobación de exec en runtime).
- **Memoria:** `MEMORY.md`, `USER.md`, notas diarias; `memory_search` y `memory_get`; «memory flush» antes de compactar.

## Muchas herramientas y modelos chicos

| Fuente | Resultado |
|---|---|
| Less is More (arXiv 2411.15399, 2024), 1,5–8B Q4 | menos herramientas a la vista sube BFCL y baja 48–80 % el tiempo; Llama3.1-8B falla con 46 y pasa con 19 |
| TinyAgent (arXiv 2409.00608) | Tool RAG ~4 herramientas: 80–85 %, pero con un recuperador DeBERTa entrenado; embeddings planos van mal |
| ToolRet (arXiv 2503.01763) | los recuperadores estándar encuentran mal herramientas (nDCG@10 34–47) |
| RAG-MCP (arXiv 2505.03275), MCP-Zero (arXiv 2506.01056) | grandes ahorros de tokens con modelos grandes; a veces inyectar todo gana |
| Anthropic Advanced Tool Use (nov 2025) | Tool Search Tool 49→74 % (Opus); «deja 3–5 herramientas siempre cargadas» |
| Qwen3.5-4B model card | BFCL-V4 50,3; TAU2 79,9 |

**[inferencia]** BAXY ya está en 85/90 con todo en caché: poco margen. El protocolo de dos pasos compone errores, suma
latencia, abre falsedades nuevas (cargar la skill y narrar), choca con la gramática de llama.cpp (sólo se pueden llamar
las herramientas declaradas) e invalida la caché si cambia el array de tools (va dentro del mensaje de sistema).

**Brazos a medir, en orden:** A hoy; **B todas, compactas** (descripciones de una línea, ~10–15k tokens); C híbrido
(5–15 fijas + `cargar_habilidad` con las tools añadidas al final); D índice puro. C o D sólo si ganan a B en acierto,
falsedades y latencia por acción completa.

## Qwen3.5 y llama.cpp

- Muestreo oficial sin pensar: temperature 0,7, top_p 0,8, top_k 20, min_p 0, presence_penalty 1,5 (a probar 1,5 vs 0:
  penaliza tokens que se repiten dentro de una llamada). Pensar apagado con `chat_template_kwargs.enable_thinking=false`.
- Unsloth arregló un bug del template de tool calling que afectaba a todos los cuantizadores: comprobar el GGUF y el
  template (unsloth.ai/docs/models/qwen3.5).
- «The Reasoning Trap» (arXiv 2510.22977): más razonamiento, más alucinación de herramientas → pensar apagado.
- **Modelo híbrido** (Gated DeltaNet:atención 3:1): sólo ¼ de las capas tienen KV; el estado recurrente no se desplaza,
  `--cache-reuse` no ayuda; la reutilización va por checkpoints (`--ctx-checkpoints`, 32 por slot) y se invalida si
  cambia el medio del prompt (issue #24587). **Sólo añadir al final; nunca editar el medio.**
- La doc de function calling de llama.cpp avisa que cuantizar la KV puede degradar las llamadas: A/B q8_0 vs f16 (en
  este híbrido la KV f16 cuesta poco).
- `--slot-save-path` + `POST /slots/{id}?action=save|restore`; `--cache-ram`; MTP (`--spec-type draft-mtp`) ayuda poco
  con salidas cortas **[inferencia]**.

## Falsedades

- Advani, «From Confident Closing to Silent Failure» (arXiv 2606.09863, 2026): el falso éxito es 45–76 % de los fallos;
  los arreglos de prompt o razonamiento apenas ayudan; anclar el mensaje final a los resultados no se probó.
- «Beyond Task Completion» (arXiv 2603.03116), ToolBeHonest (EMNLP 2024), Relign (ICML 2025: acciones de diferir o
  preguntar bajan la alucinación de herramientas).
- Guía de prompting de GPT-4.1: herramientas en el campo `tools` mejor que descritas en el prompt; ejemplos en una
  sección `# Examples` del sistema.
- **Mitigaciones dentro de las reglas [inferencia]:** (1) llamadas y resultados en el historial (si el historial guarda
  «¡Listo! Ya abrí X» sin la llamada, el modelo copia la afirmación); (2) `tool_choice: required` en la primera
  decisión con una herramienta `responder(texto)` para la charla, así una falsedad es elegir mal la herramienta;
  (3) ejemplos trabajados llamada → resultado → frase; (4) un detector de «afirma sin llamar» sólo como métrica del
  banco, nunca como veto.
