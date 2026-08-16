# V2 Import Round 13C - deuda tecnica del core (agent finish paths + verifier outcome plumbing)

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
- esta ronda no corresponde para bugfix encubierto.

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

- `agent.py` aun repetia el contrato de cierre de una tool en multiples
  branches;
- `tools/verifier.py` aun tenia boilerplate repetido para construir
  `VerifiedOutcome(...)`;
- ambos son hotspots de mantenibilidad real del core.

## 3. Que deuda tecnica reduje exactamente

### `src/carter_v3/agent.py`

Nuevos helpers:

- `_failed_tool_evidence(...)`
- `_finish_policy_block(...)`
- `_finish_single_tool_turn(...)`

Rutas que ahora comparten esos helpers:

1. bloqueo por `unresolved_target`
2. bloqueo por `PolicyEngine`
3. replay de `PendingToolApproval`
4. cierre de `PendingMemoryOffer`
5. turn de una sola tool ya ejecutada/verificada

Complejidad accidental reducida:

- antes, cada branch podia reconstruir a mano `ToolResult`,
  `VerifiedOutcome`, `mission_status` y reply final;
- ahora, esos cierres comparten helpers estructurales y se mantienen
  alineados.

### `src/carter_v3/tools/verifier.py`

Nuevo helper:

- `_outcome(...)`

Complejidad accidental reducida:

- las ramas del verifier dejan de instanciar `VerifiedOutcome(...)`
  repetidamente con pequenas variaciones;
- el contrato de salida queda centralizado en un solo helper interno.

## 4. Que deuda tecnica sigue abierta y por que

- `R-P3-29`
  - sigue abierto porque `agent.py` permanece grande y acoplado; esta
    ronda pago un slice real del armado de cierre, no el hotspot entero.
- `R-P4-04`
  - sigue abierto porque el tamano del paquete sigue alto:
    `src/carter_v3 total = 7692` lineas Python.
- `R-V3-C3`
  - sigue abierto porque `tools/verifier.py` mejora su plumbing, pero no
    se parte en slices mas chicos ni deja de ser hotspot.
- resto de deuda abierta
  - no se toco para no mezclar esta ronda con UX/runtime o con cambios de
    diseño mas amplios.

## 5. Que items no eran deuda tecnica para esta ronda

### Bug real ya cerrado

- `R-P4-10`
  - sigue cerrado desde Round 13A; no se reabre aqui.

### Limite de diseno/runtime

- `R-P4-11`
  - el native ratio sigue dependiendo del modelo/runtime real.
- `R-P4-XX-skipped`
  - subset live-safe por seguridad/scope.
- `R-V3-T4`
  - latencia operativa de cat10 es trabajo del runtime, no de este
    refactor.
- cluster browser/OCR/VLM/read-only (`R-P4-01/02/03`)
  - siguen fuera del baseline de esta ronda.

## 6. Resultados reales de tests y runners

- `python -m pytest -q` -> `316 passed`.
- `python audit/hardcode_guard.py` ->
  `hardcode_guard: clean (54 files scanned)`.
- `python audit/full_matrix_runner.py --mode live-safe --label round_13c_techdebt_core --out audit/runs/round_13c_techdebt_core.json`
  ->
  `global=100.0% P1=100.0% P2=100.0% P3=100.0% cat11=100.0% cat18=100.0% p95=1351.1ms`.
- `python audit/full_matrix_runner.py --mode live-safe --model phi3.5:latest --label round_13c_techdebt_core_cross --out audit/runs/round_13c_techdebt_core_cross.json`
  ->
  `global=100.0% P1=100.0% P2=100.0% P3=100.0% cat11=100.0% cat18=100.0% p95=3250.9ms`.

Impacto real:

- runner principal: no baja; se sostiene en `100.0%`.
- cross-model: no baja; se sostiene en `100.0%`.
- `C14`: sigue `100.0%`.
- `cat11`: sigue `100.0%`.

## 7. Metricas

Medicion actual del tree:

- `src/carter_v3/agent.py`: `692` lineas
- `src/carter_v3/tools/verifier.py`: `594` lineas
- `src/carter_v3 total`: `7692` lineas Python
- tests totales: `316`

Lectura honesta:

- no hubo mejora por conteo bruto;
- la mejora defendible es de acoplamiento/repeticion interna;
- `agent.py` y `tools/verifier.py` siguen siendo hotspots reales.

## 8. Cambios documentales

- `CHANGELOG.md`
  - nueva `Seccion Z - Round 13C`
- `RESIDUAL.md`
  - nueva `Seccion Z - Round 13C`
- `V2_IMPORT_ROUND_13C_LOG.md`
  - este archivo

## 9. Veredicto

`TECHDEBT_ROUND_PARTIAL`

Razon:

- se pago deuda real en el core sin romper baseline, `C14` ni `cat11`;
- no se agregaron features ni hacks;
- pero `R-P3-29`, `R-P4-04` y `R-V3-C3` siguen honestamente abiertos.
