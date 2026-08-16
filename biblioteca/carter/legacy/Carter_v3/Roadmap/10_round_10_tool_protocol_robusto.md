# Round 10 - Tool protocol robusto con Ollama

Modelo recomendado:

- Mejor: `Claude Opus 4.7`
- Razonamiento: `High`
- Fallback: `GPT-5.4`

Prompt:

```text
Vivimos en:

c:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI

Tu trabajo ocurre SOLO dentro de:
`Carter_v3/`

OBJETIVO DE ESTA RONDA
Cerrar R-P4-05 y R-P3-33: el protocolo de tool-calling con Ollama
sigue siendo fragil cuando se expone el catalogo completo. Carter
resuelve muchos casos por fallback estructural acotado, no por
tool-calling real.

ANTES DE TOCAR NADA, LEE:
- `ContextoCarter.md`
- `Carter_v3/CHANGELOG.md`
- `Carter_v3/RESIDUAL.md` (especialmente R-P4-05, R-P3-33, R-P3-20)
- `Carter_v3/src/carter_v3/adapters/ollama_adapter.py`
- `Carter_v3/src/carter_v3/adapters/llm_protocol.py`
- `Carter_v3/src/carter_v3/tools/catalog.py`
- `Carter_v3/src/carter_v3/agent.py`
- `Carter_v3/src/carter_v3/turn_support.py`
- `Carter_v3/audit/full_matrix_runner.py`

TRAZABILIDAD
Crea:
- `Carter_v3/V2_IMPORT_ROUND_10_LOG.md`

DIAGNOSTICO REQUERIDO ANTES DE TOCAR NADA
1. Lanza Ollama localmente con `qwen2.5:7b-instruct`.
2. Ejecuta una llamada directa al endpoint `/api/chat` con el catalogo
   completo de 32 tools en formato JSON y un prompt de accion simple
   (ej. "abre notepad").
3. Identifica exactamente por que falla: formato de schema, tamano del
   payload, incompatibilidad de tipos, timeout, o algo del adapter.
4. Documenta el error real antes de proponer ningun fix.

HIPOTESIS A INVESTIGAR
- El schema de algunas tools tiene campos que Ollama/qwen no acepta
  en su formato de functions.
- El catalogo completo de 32 tools supera el context window del modelo
  para tool definitions, causando truncation o error 400.
- El adapter no maneja correctamente el formato de tool_call en la
  respuesta del modelo.

MISION
Lograr que tool-calling nativo (`tool_call_mode=native`) funcione de
forma estable con `qwen2.5:7b-instruct` para al menos los 10 casos
mas comunes de la matriz live-safe que actualmente dependen de
fallback estructural.

REGLAS
- No cambiar `tool_call_mode` a `none` como solucion.
- No meter branches por nombre de modelo en el core (R T2 del CHANGELOG).
- El adapter puede adaptar el schema; el core no sabe que adapter hay debajo.
- Si el catalogo completo es el problema, evaluar si se puede segmentar:
  enviar solo las tools relevantes para la ruta clasificada. Esto debe
  ser una decision estructural (por familia de intent), no un hack por caso.
- No reducir el catalogo publico a menos de 32 tools.

VALIDACION
- `python -m pytest -q`
- `python audit/hardcode_guard.py`
- `python audit/full_matrix_runner.py --mode live-safe --label round_10_tool_protocol_full --out audit/runs/round_10_tool_protocol_full.json`
- `python audit/full_matrix_runner.py --mode live-safe --category 7 --label round_10_tool_protocol_cat7 --out audit/runs/round_10_tool_protocol_cat7.json`
- `python audit/full_matrix_runner.py --mode live-safe --category 9 --label round_10_tool_protocol_cat9 --out audit/runs/round_10_tool_protocol_cat9.json`

El global del runner no debe bajar. El objetivo es reducir los casos
que llegaban a fallback estructural y ahora pasan por tool-calling real.

METRICAS A REPORTAR
- Cuantos turnos usaban fallback estructural antes vs despues (medible
  con log de tool_call_source si se agrega o con manual sampling).
- Error rate del endpoint antes vs despues.
- p95 antes/despues (el tool-calling real puede ser mas lento).

ENTREGA
1. Diagnostico exacto del fallo del protocolo (error real observado)
2. Que cambiaste en el adapter o en el schema de tools
3. Que NO cambiaste (invariantes preservados)
4. Resultados reales de runners y metricas comparativas
5. Residual que sigue abierto
6. Updates en `CHANGELOG.md`, `RESIDUAL.md`, `V2_IMPORT_ROUND_10_LOG.md`
```
