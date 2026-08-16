# Instrucciones — redactar ejemplos de function-calling (FunctionGemma / asistente Baxy)

Sos un redactor experto de datos de entrenamiento. Redactás ejemplos INDIVIDUALES de altísima
calidad, NUNCA plantillas. El usuario rechaza datos sintéticos repetitivos.

## Entrada
Te paso un número de lote NNN. Leé `curated/specs/batch_NNN.json` (rutas relativas a
`c:/Users/usuario/Desktop/ETC/Programacion/FunctionGemma/finetune_llm/`). Es una lista de tools,
cada una con: `name`, `description`, `params` (nombres y tipo/enum), `family`, `target_new`.

## Salida
Escribí `curated/hc/batch_NNN.jsonl`: una línea JSON por ejemplo, SIN texto extra, UTF-8.
Formato de cada línea:
{"q": "<frase natural del usuario>", "lang": "<es|en|pt|fr|de|it>", "tool": "<name exacto>", "args": {<args>}}

Para CADA tool del spec, escribí `target_new` ejemplos (tope 50).

## Reglas de calidad (lo más importante)
- Cada `q` es una frase REAL y natural que alguien le diría a su asistente de voz/PC. Variá:
  registro (formal/informal, jerga rioplatense, española, mexicana), longitud, orden de
  palabras, sinónimos, formas implícitas y explícitas. NADA de rellenar huecos de plantilla.
- La frase debe implicar CLARAMENTE la acción específica de ESA tool (mirá su `description`),
  distinguible de tools hermanas (ej. start vs stop vs status; create vs list vs delete).
- Idiomas por tool (aprox): es 45%, en 25%, resto pt/fr/de/it. Frases NATIVAS, no traducciones.
- `args`: usá EXACTAMENTE los nombres de params del spec. Valores realistas y variados. Enums:
  solo valores del enum. Si la acción no necesita valores, `{}`.
- Cero duplicados ni casi-duplicados.

## Cuidado técnico
- Escribí con la herramienta Write (no heredoc), para no romper el escape de `\` en rutas Windows.
- Antes de terminar: releé el archivo, parseá cada línea como JSON, confirmá que cada `tool`
  está en el spec y que los args usan params del spec. Corregí lo que falle. Reportá conteo por tool.

## Gold standard (ejemplos de referencia, tool wifi_connect, params name/password)
{"q": "enganchate a la red HUAWEI-3F2A, la clave es 12345678", "lang": "es", "tool": "wifi_connect", "args": {"name": "HUAWEI-3F2A", "password": "12345678"}}
{"q": "connect to MyWiFi, the password is hunter2", "lang": "en", "tool": "wifi_connect", "args": {"name": "MyWiFi", "password": "hunter2"}}
{"q": "rejoins le réseau Freebox_5G", "lang": "fr", "tool": "wifi_connect", "args": {"name": "Freebox_5G"}}
{"q": "collegati al wifi TIM-12345", "lang": "it", "tool": "wifi_connect", "args": {"name": "TIM-12345"}}
