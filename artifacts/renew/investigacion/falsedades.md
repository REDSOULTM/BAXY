# Falsedades: por qué el modelo cuenta lo que no pasó (investigación, 2026-10-15)

Diagnóstico de los hechos en `../PROGRESO-nb.md`. Aquí van la evidencia externa y lo que se recomienda, dentro de
las reglas del goal (sólo presentación, protocolo e inferencia).

## Qué hace la plantilla de Qwen3.5 con las herramientas de turnos anteriores

La plantilla del GGUF local es idéntica a la oficial
([Qwen/Qwen3.5-4B chat_template.jinja](https://huggingface.co/Qwen/Qwen3.5-4B/raw/main/chat_template.jinja)).

- Las llamadas de los turnos anteriores se conservan completas (`<tool_call><function=…><parameter=…>`). Los
  parámetros sólo se ven si `arguments` llega como objeto; si llega como cadena JSON, la llamada sale sin parámetros.
  Hay que comprobar con `/apply-template` de llama-server qué ve el modelo.
- Los resultados van dentro de un mensaje de usuario, entre `<tool_response>…</tool_response>`, sin el nombre de la
  herramienta ni su id. El modelo sólo puede emparejar resultado y llamada por posición.
- El razonamiento de los turnos anteriores se borra; el model card pide que el historial lleve sólo la salida final.

**Conclusión:** la plantilla está hecha para repetir el historial de herramientas entre turnos. Que BAXY lo
descarte es una elección del arnés, no una exigencia del formato.

## Recomendaciones, de más a menos impacto

1. **Conservar en el historial los `tool_calls` y los mensajes `role:"tool"` de los turnos recientes.** Ataca las
   falsedades 1 y 2.
   - Hoy el modelo ve su propio «Listo, abrí Steam» sin la prueba al lado, y la negación de la persona. Los modelos
     tienden a darle la razón: en [FlipFlop](https://arxiv.org/abs/2311.08596) cambian la respuesta cerca del
     46 % de las veces ante «¿estás seguro?». [A-CC](https://arxiv.org/abs/2512.00332) muestra que los agentes con
     herramientas son muy vulnerables a afirmaciones falsas del usuario.
   - Las guías oficiales repiten la cadena completa:
     [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling) («preserve model
     output for the next turn») y [Qwen function calling](https://qwen.readthedocs.io/en/latest/framework/function_call.html).
   - Si falta contexto, se resume un resultado viejo en una línea verificada en vez de borrarlo
     ([context editing](https://platform.claude.com/docs/en/agents-and-tools/tool-use/manage-tool-context.md)).
2. **Cada resultado dice exactamente qué se verificó.** Ataca las falsedades 2 y 3.
   - JSON compacto con el resultado primero y el nombre de la herramienta repetido, porque la plantilla no lo
     muestra.
   - Los campos dicen el límite de la verificación (por ejemplo, la URL de la barra de direcciones, no el contenido
     de la página). Así el modelo no estira «URL verificada» a «te llevé a la página de Doom».
   - [Halluci-action](https://neurips.cc/virtual/2026/173318) atribuye las falsas afirmaciones de acción a huecos en
     la verificación y en lo que se le muestra al agente.
   - Anthropic recomienda campos de alta señal y nombres legibles
     ([writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)).
3. **La biblioteca de juegos en el esquema, no en la prosa de otra herramienta.** Ataca la falsedad 3.
   - Un `enum` con los juegos o appIds en el parámetro que los usa. OpenAI: «use enums… don't make the model fill
     arguments you already know».
4. **Reglas cortas de anclaje en el prompt, en positivo.**
   - Lo que digas que hiciste sale de un resultado de herramienta de esta conversación.
   - Si te dicen que no lo hiciste, mira los resultados anteriores y di lo verificado.
   - No anuncies acciones futuras: haz la llamada o no la menciones.
   - Fuentes: [guía de prompting de GPT-4.1](https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide)
     («ACTUALLY make the tool call») y [ToolBeHonest](https://arxiv.org/abs/2406.20015).
5. **El relleno («¡Listo!», «¿Quieres algo más?»).** Con el historial conservado, las respuestas pasadas del modelo
   funcionan como ejemplos que copia. Se arregla con dos o tres ejemplos variados de respuesta final que dan el dato
   observado y terminan, más la regla de no ofrecer más ayuda ni disculparse.
6. **Inferencia.** Para el modo sin razonamiento, el model card de Qwen3.5-4B recomienda temperatura 0,7, top_p 0,8,
   top_k 20, min_p 0 y presence_penalty 1,5. Hay que medirlo; hoy se decide a 0,2.

## Salvedades

- No hay un estudio controlado de conservar contra descartar el historial de herramientas. El apoyo viene de los
  protocolos oficiales, del diseño de la plantilla y de los estudios de complacencia.
- La evidencia de JSON contra prosa ([NLT](https://arxiv.org/abs/2510.14453),
  [modelos pequeños](https://arxiv.org/abs/2504.19277)) trata de cómo el modelo escribe llamadas, no de cómo lee
  resultados. Se mide con el banco.

Otras fuentes: [encuesta de alucinación en agentes, 2025](https://arxiv.org/abs/2509.18970) y
[LLMs Get Lost in Multi-Turn](https://arxiv.org/abs/2505.06120).
