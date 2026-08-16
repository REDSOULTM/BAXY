# Tools de Baxy — campo de prueba FunctionGemma

Copiado desde el repo de Baxy (gemma4_agent) el 2026-06-14 para probar FunctionGemma
con las tools reales.

## Qué hay acá
- `tool_schemas_full.json` — los **67 tools** (esquema OpenAI/JSON, sin recortar).
- `tool_schemas_lean.json` — los **31 tools** del set lean (Experimentando).
- `tools/tools_pkg/` — código fuente de los tools: `tool_schemas.py` (definición de
  schemas), `tools.py` (dispatcher gigante 426KB), resolvers (app/site/steam),
  `ops_tools.py`, `tool_head.py`, etc.
- `tools/domain_tools/` — handlers por dominio (audio_devices, bluetooth, wifi,
  notifications, whatsapp, media, etc.).

## Para declararle tools a FunctionGemma (uso inmediato)
Usá los JSON directamente — no necesitás importar el Python:
```python
import json
tools = json.load(open("tool_schemas_lean.json", encoding="utf-8"))
# pasalos al server: body["tools"] = tools  (o apply_chat_template(tools=...))
```

## CAVEAT: el código Python NO corre standalone
`tools/tools_pkg/tools.py` y los handlers importan del resto de gemma4_agent
(agent_core, infra, state, etc.). Sirven como REFERENCIA de la lógica de ejecución,
pero para ejecutarlos de verdad necesitás esos módulos o reimplementar los handlers.
Para un campo de prueba de FunctionGemma, lo práctico es: usar los SCHEMAS (JSON) y
stubbear los handlers (que devuelvan un resultado fake) para validar el ROUTING/EMISIÓN.

## GOTCHAS de FunctionGemma (medidos el 2026-06-14 — te ahorran horas)
1. **Rol `developer` obligatorio** (no `system`): el mensaje
   `"You are a model that can do function calling with the following functions"`
   activa el modo function-calling.
2. **Sampling**: temp=1.0, top_k=64, top_p=0.95 (Google). Con temp=0 a veces rechaza.
3. **Context 32K**: con los 31 schemas de Baxy y ctx 8192 da **HTTP 400** (overflow).
   Booteá con `-c 32768`.
4. **Stop token**: agregá `stop=["<end_function_call>"]` o **se va en loop** repitiendo
   el call.
5. **Formato de salida propio** (NO el de Gemma 4): el call sale en `content`, no en
   `tool_calls` — hay que regexear:
   `<start_function_call>call:NOMBRE{param:<escape>valor<escape>}<end_function_call>`
6. **Funciona con tools COMPUESTOS** (enum action) SI: (a) la descripción es **corta y
   limpia** (la verbosa de Baxy lo hace rechazar), (b) los **valores del enum son
   transparentes** (`action=memory` anda; `action=cpu_ram_gpu` NO — no lo mapea).
7. **Sesgo al inglés**: varios fraseos no-EN rechazan (ej. "qué hora es" falla donde
   "what time is it" anda). Para multilingüe necesita fine-tuning.
8. **NO es conversacional**: rechaza conocimiento y smalltalk (0/7 medido). Solo emite
   function-calls. No puede ser un asistente por sí solo.

## GGUF ungated (para correrlo)
`unsloth/functiongemma-270m-it-GGUF` (UD-Q8_K_XL 471MB) — corre con:
```
llama-server -m functiongemma-270m-it-UD-Q8_K_XL.gguf --port 8082 --jinja -ngl 99 -c 32768
```
Para fine-tune: `unsloth/functiongemma-270m-it` (full) o `-unsloth-bnb-4bit` (ambos ungated).

## Veredicto medido (base vs base, sin FT)
| dimensión | Gemma 4 E2B | FunctionGemma 270M |
|---|---|---|
| acción (emitir call) | 5/13 | 6/13 (EN-biased, over-calls) |
| conocimiento | 3/3 | 0/3 (rechaza) |
| smalltalk | 4/4 | 0/4 (rechaza) |

FunctionGemma solo gana marginal en emisión de calls; no conversa ni responde.
Detalle en el repo de Baxy: documentacion/_NIGHT2_APPLY_DISCOVERIES_2026-06-14.md
