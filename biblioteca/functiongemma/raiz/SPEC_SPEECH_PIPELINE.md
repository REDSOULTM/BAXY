# SPEC — Pipeline del modelo de HABLA de Baxy (listo para FunctionGemma)

Todo preparado para enchufar FunctionGemma cuando vuelvas. El lado de HABLA está
resuelto y probado en vivo. Archivos:
- `baxy_speech.py` — orquestador (system prompt + ensamblado de contexto + prefill + speak()). PROBADO.
- `sim_split.py` — simulación del flujo completo (1-5 mock, 6 real).
- `README_SPEECH_MODEL.md` — modelo Q4 QAT + config de servidor + por qué Q4>Q2.
- `speech_model/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf` — el modelo.

## 1. El system prompt FINAL (en `baxy_speech.py::BAXY_SYSTEM_PROMPT`)
```
Te llamás Baxy, un asistente de voz personal, cercano y claro.
- Respondé en el mismo idioma en que te habla el usuario.
- Sé breve y natural, como en una conversación hablada (1 a 3 frases).
- Cuando se ejecuta una acción, te paso su resultado: usalo para responder con
  naturalidad, sin nombrar herramientas ni detalles técnicos.
- Si no sabés algo, o una acción falló, decilo con honestidad. No inventes.
```
Corto (mejor para un modelo chico), afirmativo. Probado: persona "Soy Baxy" pega en Q4 sin FT.

## 2. CÓMO RECIBE TODO (el contrato)
```python
speak(history, user_text, tool=None, args=None, result=None)
```
El runtime arma este contexto y se lo pasa al modelo de habla:
```
[system]    BAXY_SYSTEM_PROMPT
[...history...]                                  # turnos previos
[user]      user_text                            # lo que dijo ahora el usuario
[assistant] tool_calls=[tool(args)]              # SI hubo acción: la llamada de FunctionGemma
[tool]      result                               # SI hubo acción: lo que devolvió la tool
[assistant] "<semilla de idioma>"   <-- PREFILL  # fuerza el idioma; el modelo CONTINÚA acá
```
- Smalltalk (sin acción): tool/args/result = None → no se inyectan los 2 mensajes de tool.
- El modelo **lee** el result del contexto y redacta; **nunca emite tool-calls**.

## 3. El fix de IDIOMA: prefill por idioma (lo que el prompt NO lograba)
`detect_language(user_text)` → `LANG_STARTERS[lang]` → se prefilla la respuesta con esa
semilla → el modelo continúa en ese idioma. Medido: arregla FR/EN/PT/DE/IT donde el
system prompt y la temperatura fallaban.
```
es→"Claro, "  en→"Sure, "  fr→"D'accord, "  pt→"Claro, "  de→"Okay, "  it→"Va bene, "
```
Es steering ESTRUCTURAL de idioma (1 palabra; el LLM escribe el resto), no respuesta enlatada.

## 4. DÓNDE ENCHUFA FUNCTIONGEMMA (el único hueco que falta)
En el runtime, antes de `speak()`:
```python
subset       = router.suggest(user_text)              # encoder (ya lo tenés, route.py)
tool, args   = functiongemma_emit(user_text, subset)  # <-- TU MODELO DE TOOLS (a validar)
result       = execute_tool(tool, args)               # ejecución real
reply        = speak(history, user_text, tool, args, result)   # modelo de habla (listo)
```

## 5. Config de servidor (modelo de habla)
```
llama-server -m speech_model/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf \
  --jinja -ngl 99 -c 4096 --reasoning off --port 8086
```
Sampling (en baxy_speech.py): temp 0.5, top_k 40, top_p 0.9, min_p 0.05, DRY(0.8/1.75/3).
NO KV-quant. Flash-attn OFF. (Todo medido.)

## 6. Caveats honestos (medidos)
- **Detector de idioma**: el prefill es tan bueno como la detección. La heurística del
  módulo confunde **pt↔es** (cercanos) → reemplazar por el detector real de Baxy. Para
  pt, una semilla más distintiva ("Tens "/"Você ") ayuda a desambiguar de es.
- **Semilla gramatical**: encaja casi siempre; en algún fraseo raro puede quedar forzada.
- **Grounding numérico fino**: un 2B puede errar conversiones (15:42→"la una"); el FT o
  formatear el result explícito ("3:42 PM") lo evita.
- Estos NO bloquean la arquitectura; son afinables.

## Estado: lado HABLA = LISTO ✅. Falta: validar FunctionGemma (gate ≥94% tools multiling.).
