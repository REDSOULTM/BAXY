# Round 8 - C14 typo y targeting

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
Cerrar el cluster C14.01-04: la unica falla estable del baseline
`qwen2.5:7b-instruct` desde Round 4.

ANTES DE TOCAR NADA, LEE:
- `ContextoCarter.md`
- `Carter_v3/CHANGELOG.md`
- `Carter_v3/RESIDUAL.md` (especialmente R-V3-C1 y I-2)
- `Carter_v3/src/carter_v3/resolvers/resource_resolver.py`
- `Carter_v3/src/carter_v3/resolvers/intent_classifier.py`
- `Carter_v3/src/carter_v3/agent.py`
- `Carter_v3/src/carter_v3/turn_support.py`
- `Carter_v3/tests/test_resolver.py`
- `Carter_v3/tests/test_agent_integration.py`
- `legacy/Carter_v2/audit/runners/full_live_llm_cases.py`
  (solo para entender que esperan C14.01-04)

TRAZABILIDAD
Crea:
- `Carter_v3/V2_IMPORT_ROUND_8_LOG.md`

DIAGNOSTICO
Lee el run `audit/runs/v2_import_round_7_full.json` y los anteriores
donde aparecen C14.01, C14.02, C14.03, C14.04 con
`validator_failures={"tool_policy": 4}`.

Entiende EXACTAMENTE que pasa en esos 4 casos antes de tocar nada:
- Que input recibe Carter.
- Que ruta toma (trivial / action / resolver).
- Que tool call emite o no emite.
- Por que el validator lo marca como `tool_policy` failure.

MISION
Cerrar C14.01-04 sin romper nada del baseline actual.

HIPOTESIS A INVESTIGAR
- El resolver fuzzy tiene score_cutoff=85 calibrado en C7, pero para
  typos de nombres cortos (<= 4 chars) puede fallar por cutoff fijo
  vs longitud del span (ver I-2 en RESIDUAL.md).
- La ruta de intent puede estar clasificando como `question` o `trivial`
  inputs que deberian ser accion con target ambiguo y pedir clarificacion.
- El fallback D5 puede no sintetizar la tool correcta para estos casos.

REGLAS
- cero hardcodes de nombre de app o marca para "ayudar" al resolver
- si el fix es en el cutoff, debe ser una formula general (funcion del
  largo del span), no un caso especial para C14
- si el fix es en el routing, no debe romper C1/C2/C3/C16/C18
- no ampliar el catalogo de tools
- no tocar legacy/

VALIDACION
- `python -m pytest -q`
- `python audit/hardcode_guard.py`
- `python audit/full_matrix_runner.py --mode live-safe --label round_8_c14_fix_full --out audit/runs/round_8_c14_fix_full.json`
- `python audit/full_matrix_runner.py --mode live-safe --category 14 --label round_8_c14_fix_cat14 --out audit/runs/round_8_c14_fix_cat14.json`
- `python audit/full_matrix_runner.py --mode live-safe --category 11 --label round_8_c14_fix_cat11 --out audit/runs/round_8_c14_fix_cat11.json`

El full runner debe pasar de 4 fails a 0 en C14.01-04.
C11 debe mantenerse en 100%.

ENTREGA
1. Diagnostico exacto de por que fallaban C14.01-04
2. Que cambiaste y por que es general (no hardcode)
3. Resultados reales de todos los runners
4. Regresiones introducidas (si las hay, honestamente)
5. Residual que sigue abierto en C14 (casos que no se pueden cerrar sin hardcode)
6. Updates en `CHANGELOG.md`, `RESIDUAL.md`, `V2_IMPORT_ROUND_8_LOG.md`
```
