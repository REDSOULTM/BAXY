# V2 Import Round 13B - deuda tecnica estructural del agent loop

Fecha: 2026-05-04.
Scope: SOLO `Carter_v3/`.

## 1. Triage completo de `RESIDUAL.md`

Regla usada:

- `latest mention wins`;
- la Seccion X de `RESIDUAL.md` sigue siendo el triage canonico vigente;
- esta ronda NO reabre bugs ya cerrados ni reclasifica limites como
  deuda de codigo.

### `BUG_REAL_ABIERTO`

- ninguno.

Lectura:
- despues de Round 13A no quedo bug vivo demostrado en Carter;
- no corresponda usar esta ronda para bugfix encubierto.

### `DEUDA_TECNICA_ABIERTA`

- `R-V2-B2`, `R-V2-B4`
- `R-V3-1`, `R-V3-2`, `R-V3-3`, `R-V3-4`, `R-V3-7`, `R-V3-11`
- `I-1`, `I-2`, `I-3`, `I-4`, `I-5`
- `R-P3-3`, `R-P3-4`, `R-P3-6`, `R-P3-8`, `R-P3-15`, `R-P3-22`,
  `R-P3-27`, `R-P3-29`, `R-P3-32`
- `R-P4-04`, `R-P4-05`, `R-P4-06`, `R-P4-08`
- `R-V3-T1`, `R-V3-T3`, `R-V3-WEB-1`, `R-V3-C3`

### `LIMITE_DE_DISENO_O_RUNTIME`

- `R-V2-B3`
- `R-V3-5`, `R-V3-6`, `R-V3-8`, `R-V3-9`, `R-V3-10`
- `R-P3-5`, `R-P3-7`, `R-P3-12`, `R-P3-13`, `R-P3-14`, `R-P3-21`,
  `R-P3-26`, `R-P3-30`, `R-P3-31`, `R-P3-34`
- `R-P4-01`, `R-P4-02`, `R-P4-03`, `R-P4-07`, `R-P4-09`, `R-P4-11`,
  `R-P4-XX-skipped`
- `R-V2I-01`, `R-V2I-02`, `R-V2I-04`
- `R-V3-T4`, `R-V3-C2`, `R-V3-C4`

### `CERRADO_O_MITIGADO`

- `R-V2-B1`, `R-V2-B5`, `R-V2-B6`, `R-V2-B7`
- `R-P3-1`, `R-P3-2`, `R-P3-9`, `R-P3-10`, `R-P3-11`, `R-P3-16`,
  `R-P3-17`, `R-P3-18`, `R-P3-19`, `R-P3-20`, `R-P3-23`, `R-P3-24`,
  `R-P3-25`, `R-P3-28`, `R-P3-33`
- `R-P4-10`, `R-P4-12`
- `R-V2I-03`, `R-V2I-05`
- `R-V3-T2`, `R-V3-C1`, `R-V3-C5`, `R-V3-C6`

## 2. Priorizacion aplicada

Deuda elegida:

- `R-P3-29`
- `R-P4-04`
- `R-V3-C3`

Razon:

- `agent.py` seguia como hotspot estructural del core;
- el pipeline de ejecucion/verificacion estaba duplicado;
- consolidarlo reduce fragilidad y hace mas defendibles futuros fixes sin
  tocar contratos publicos.

## 3. Que deuda tecnica reduje exactamente

Archivo tocado:

- `src/carter_v3/agent.py`

Cambio:

- nuevo helper `_execute_tool_call(...)`.
- concentra:
  - `_translate_target_to_launch(...)`
  - `_trusted_dispatch_call(...)`
  - dispatch
  - verify
  - `maybe_retry_app_open(...)`
  - trazas `tool:*` y `verify:*`

Duplicacion eliminada del flujo:

1. loop principal de steps
2. action-route fallback
3. prior-target fallback
4. replay de `PendingToolApproval`
5. guardado de `PendingMemoryOffer`

Complejidad accidental reducida exactamente donde estaba:

- antes, una regla de ejecucion/verificacion podia requerir tocar 5
  caminos;
- despues, esos caminos comparten una sola ruta estructural;
- esto baja acoplamiento entre policy, approval provenance, dispatch,
  verify y retry.

## 4. Que deuda tecnica sigue abierta y por que

- `R-P3-29`
  - sigue abierto porque `agent.py` aun es grande (`589` lineas) y el
    refactor pago acoplamiento, no tamano.
- `R-P4-04`
  - sigue abierto porque `src/carter_v3 total=6633` sigue por encima del
    cap documental.
- `R-V3-C3`
  - sigue abierto porque `tools/verifier.py` permanece como hotspot
    separado (`536` lineas) y no se refactorizo en esta ronda.
- resto de deuda abierta
  - no se toco para no abrir surface ni mezclar esta ronda con cambios de
    diseno o runtime.

## 5. Que items no eran deuda tecnica sino bug o limite externo

### Bug real ya cerrado

- `R-P4-10`
  - bugfix real de Round 13A; no se reabrió aquí.

### Limite de diseno/runtime

- `R-P4-11`
  - native ratio depende del modelo y del runtime, no del core.
- `R-P4-XX-skipped`
  - subset live-safe por seguridad/scope.
- `R-V3-T4`
  - latencia de cat10 es trabajo real del runtime.
- `R-P4-01`, `R-P4-02`, `R-P4-03`
  - browser/OCR/VLM/observacion read-only siguen fuera del baseline o con
    rigor deliberadamente parcial.

## 6. Resultados reales de tests y runners

- `python -m pytest -q` -> `316 passed`.
- `python audit/hardcode_guard.py` ->
  `hardcode_guard: clean (54 files scanned)`.
- `python audit/full_matrix_runner.py --mode live-safe --label round_13b_techdebt --out audit/runs/round_13b_techdebt.json`
  ->
  `global=100.0% P1=100.0% P2=100.0% P3=100.0% cat11=100.0% cat18=100.0% p95=1407.9ms`.
- `python audit/full_matrix_runner.py --mode live-safe --model phi3.5:latest --label round_13b_techdebt_cross --out audit/runs/round_13b_techdebt_cross.json`
  ->
  `global=100.0% P1=100.0% P2=100.0% P3=100.0% cat11=100.0% cat18=100.0% p95=2777.7ms`.

Impacto real:

- runner principal: no baja; se sostiene en `100.0%`.
- cross-model: no baja; se sostiene en `100.0%`.
- `C14`: sigue `100.0%`.
- `cat11`: sigue `100.0%`.

## 7. Metricas

### Lineas antes/despues de archivos refactorizados

- `src/carter_v3/agent.py`: `578 -> 589`

### Tests totales antes/despues

- `316 -> 316`

### Lectura honesta de metricas

- el tamano local sube `+11` lineas;
- la mejora defendible NO es el conteo bruto sino la eliminacion de
  duplicacion de pipeline en 5 rutas del loop;
- no hay cambio de contrato ni degradacion live.

## 8. Cambios documentales

- `CHANGELOG.md`
  - nueva `Seccion Y - Round 13B`
- `RESIDUAL.md`
  - nueva `Seccion Y - Round 13B`
- `V2_IMPORT_ROUND_13B_LOG.md`
  - este archivo

## 9. Veredicto

`TECHDEBT_ROUND_PARTIAL`

Razon:

- se redujo deuda tecnica real del hotspot principal;
- no hubo regresion funcional;
- `C14` y `cat11` se mantienen en `100.0%`;
- pero la deuda estructural mayor no queda cerrada:
  `agent.py` sigue grande, `verifier.py` sigue intacto como hotspot y la
  deuda total de lineas del paquete sigue abierta.
