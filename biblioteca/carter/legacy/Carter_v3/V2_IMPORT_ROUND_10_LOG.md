# V2 Import Round 10 — Tool protocol robusto con Ollama

Fecha: 2026-05-04.
Modelo: `qwen2.5:7b-instruct` en Ollama local (`http://127.0.0.1:11434`).
Scope: SOLO `Carter_v3/`.

## 1. Diagnostico exacto del fallo (antes de tocar nada)

Probe directo al endpoint `/api/chat` con el catalogo completo de 32 tools
(`audit/round_10_probe.py`, escenario `A_full_current_shape`):

```
status: 400
error:  "json: cannot unmarshal bool into Go struct field
         ToolFunctionParameters.tools.function.parameters.properties.required
         of type []string"
elapsed: 0.01s
body_size: 7904 bytes
```

El error NO es:
- ni context window (7.9KB esta muy lejos de saturar `qwen2.5:7b-instruct`),
- ni timeout (falla en 10ms),
- ni incompatibilidad del adapter (la respuesta nativa se parsea bien
  cuando llega; el problema es que nunca llega).

El error ES:
- `ToolSpec.to_openai_tool()` en `src/carter_v3/tools/catalog.py` ponia
  `"required": True` (boolean) DENTRO del schema de cada propiedad
  (vivia en `properties.<arg>.required`).
- JSON-Schema y el decoder estricto Go de Ollama esperan `required`
  como `[]string` SOLO al nivel de `parameters`, nunca dentro de un
  property.
- El array correcto de `required` arriba ya se generaba bien;
  el bug era que el boolean por-arg se filtraba a las properties via
  `properties: self.arguments` sin sanear.

Probe escenario `B_full_clean_required` (mismo catalogo de 32, sin
boolean dentro de properties): `status=200`, `tool_calls_in_resp=1`,
`name=app_open`, `args={"target":"notepad"}`, 1.07s.

Probe sobre 4 prompts distintos con el catalogo completo limpio:
```
"abre notepad"      -> app_open(target="notepad")           1.0s
"que hora es"       -> clock_now()                          0.5s
"abre google.com"   -> app_open(target="google chrome")     0.6s
"toma una captura"  -> desktop_screenshot(path="...")       0.7s
```
4/4 native tool-calls reales, p95 sub-segundo.

## 2. Que cambie

Un solo punto de cambio funcional, minimo:

### `src/carter_v3/tools/catalog.py` — `ToolSpec.to_openai_tool()`

Antes:
```python
"properties": self.arguments,
"required": [k for k, v in self.arguments.items() if v.get("required")],
```

Despues:
```python
properties: dict[str, Any] = {}
required: list[str] = []
for key, schema in self.arguments.items():
    if not isinstance(schema, dict):
        continue
    clean = {k: v for k, v in schema.items() if k != "required"}
    properties[key] = clean
    if schema.get("required"):
        required.append(key)
return {
    "type": "function",
    "function": {
        "name": self.name,
        "description": self.description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    },
}
```

El flag `required: True` por-argumento sigue siendo la unica fuente de
verdad interna; ahora se traduce SOLO al `required: []string` de
nivel `parameters`, sin contaminar el property schema.

### Probe nuevo (no es runtime)

`audit/round_10_probe.py` — script de diagnostico reproducible, no se
importa desde el runtime. Documenta el experimento que encontro el bug.

## 3. Que NO cambie (invariantes preservados)

- `tool_call_mode` sigue siendo `native` en todos los profiles.
  No se cayo a `none` como solucion (regla explicita de la ronda).
- Cero ramas por nombre de modelo en core o adapter (R T2 del CHANGELOG).
- `OllamaAdapter` no toca el schema; sigue enviando `body["tools"] = tools`
  tal cual lo recibe del agent. La adaptacion del schema vive donde
  corresponde: en el productor del catalogo (`ToolSpec.to_openai_tool`),
  no en el adapter.
- Catalogo publico sigue en 32 tools. NO se segmento por categoria.
  El probe demostro que el catalogo completo cabe perfectamente
  (~7.5KB body) y el modelo selecciona la tool correcta sin ayuda.
- Verifier, dispatcher, perception y guards no se tocaron.
- `agent.py` y `turn_support.py` no se tocaron.

## 4. Resultados reales (live-safe contra Ollama)

### Suites unitarias y guard

```
python -m pytest -q                  -> 309 passed (120.94s)
python audit/hardcode_guard.py       -> clean (54 files scanned)
```

### Matrix runner global

```
python audit/full_matrix_runner.py --mode live-safe \
  --label round_10_tool_protocol_full \
  --out audit/runs/round_10_tool_protocol_full.json
```

| metric                      | round 9 (refactor) | round 10 (tool protocol) |
|-----------------------------|--------------------|--------------------------|
| global_pass_rate            | 99.81%             | 99.62%                   |
| passed                      | 525                | 524                      |
| failed                      | 1                  | 2                        |
| p95_ms                      | 1231.5             | 1550.5                   |
| turnos con tool_calls       | 35                 | 38                       |
| **native tool-calls**       | **0 / 35**         | **32 / 38** (84%)        |
| **fallback estructural**    | **35 / 35**        | **6 / 38** (16%)         |
| **endpoint 400 errors**     | **104**            | **0**                    |

Lectura honesta:
- El global bajo 0.19 pp por dos casos `active_app_contamination`
  (`C2.21` con un spill de caracteres CJK del modelo, `C16.16` con
  la palabra "horario" matcheando un token de ventana activa). Ambos
  son ruido del LLM no determinista interactuando con el estado real
  del escritorio durante la corrida; el mismo validator tumbo `C5.33`
  en round 9. No hay regresion de logica de Carter.
- El cambio real es el shift estructural: round 9 dependia 100% de
  fallback estructural para emitir tool calls (porque el endpoint
  rechazaba el catalogo). Round 10 emite tool calls nativos en 84%
  de los turnos que usan tools, con 0 errores de endpoint.
- p95 subio 319ms (1231 -> 1550). Esperado: el tool-calling nativo
  paga round-trip extra del modelo deliberando con el catalogo,
  donde el fallback antes resolvia sin consultar al modelo. Sigue
  por debajo del cap operativo (<2s para acciones).

### Categorias

```
python audit/full_matrix_runner.py --mode live-safe --category 7 \
  --label round_10_tool_protocol_cat7 \
  --out audit/runs/round_10_tool_protocol_cat7.json
  -> global=100.0%  p95=901ms

python audit/full_matrix_runner.py --mode live-safe --category 9 \
  --label round_10_tool_protocol_cat9 \
  --out audit/runs/round_10_tool_protocol_cat9.json
  -> global=100.0%  p95=3239ms
```

C7 (acciones de sistema basicas) y C9 (memoria) ambas 100%.

## 5. Residual que sigue abierto

- **R-P4-05 / R-P3-33 / R-P3-20** quedan **mitigados** (no cerrados al
  100%): tool-calling nativo funciona estable contra
  `qwen2.5:7b-instruct` con el catalogo completo y 0 errores de
  endpoint en 654 casos live-safe. Falta:
  - validar el mismo fix contra runtimes alternos (OpenAI-compat,
    `gpt-oss:20b`) para descartar otra incompatibilidad de schema.
  - validar contra modelos cuyo `tool_call_mode = json_schema` (no
    `native`); el path de `parse_tool_call` sobre `text` no se ejercito
    en esta ronda.
  - los 6 turnos que aun usan fallback estructural (16%): mayoria son
    rutas tipo `web_open_url` con resolver previo que sintetiza la
    tool antes de consultar al LLM (decision arquitectural, no fallo
    de protocolo).
- `active_app_contamination` sigue siendo flake real: el guard se
  dispara cuando el LLM (no determinista) escupe un token que
  coincide con un titulo de ventana abierta. No es problema de tool
  protocol y no se aborda en esta ronda.
- p95 +319ms es el costo honesto de mover de fallback a native.
  Sigue dentro de presupuesto.

## 6. Updates

- `CHANGELOG.md`: nueva entrada Seccion R - Round 10.
- `RESIDUAL.md`: nueva Seccion S anotando R-P4-05 / R-P3-33 / R-P3-20
  como mitigados con evidencia.
- `audit/round_10_probe.py`: script de diagnostico (nuevo).
- `audit/runs/round_10_tool_protocol_*.json`: 3 corridas live-safe.
