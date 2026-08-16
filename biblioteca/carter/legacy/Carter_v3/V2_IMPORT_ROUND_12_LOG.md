# V2 Import Round 12 - Consolidacion post-fixes

Fecha: 2026-05-04.
Scope: SOLO `Carter_v3/`.
Modelo principal revalidado: `qwen2.5:7b-instruct`.
Cross-check adicional: `phi3.5:latest`.

Nota: este archivo reemplaza el borrador previo de "Round 12 native push".
El cierre canonico de la segunda campana 8-11 es esta consolidacion.

## 1. Objetivo

No agregar features. Revalidar y documentar honestamente el estado real
despues de los fixes de Round 8 a Round 11:

- Round 8: cierre de C14.
- Round 9: refactor de dispatch sin regresion estructural.
- Round 10: mejora medible del protocolo de tools.
- Round 11 / 11b: fix de validator y hardening de provenance
  `user_approved`.

## 2. Evidencia leida antes de validar

- `ContextoCarter.md`
- `CHANGELOG.md`
- `RESIDUAL.md`
- `V2_IMPORT_ROUND_8_LOG.md`
- `V2_IMPORT_ROUND_8B_LOG.md`
- `V2_IMPORT_ROUND_9_LOG.md`
- `V2_IMPORT_ROUND_10_LOG.md`
- `V2_IMPORT_ROUND_11_LOG.md`
- `audit/runs/round_8_*`
- `audit/runs/round_9_*`
- `audit/runs/round_10_*`
- `audit/runs/round_11_*`

## 3. Revalidacion por ronda

### 3.1 Round 8 - C14

- Baseline Round 7: `global=99.24%`, `cat14=91.30%`, C14.01-04 = `0/4`.
- Round 8 fijo la causa raiz estructural:
  `SessionState.observed_target` ya no sobrevive turnos no deicticos.
- Evidencia historica:
  - `audit/runs/round_8_c14_fix_full.json` -> `526/526`, `global=100.0%`.
  - `audit/runs/round_8_c14_fix_cat14.json` -> C14.01-04 `4/4 PASS`.
  - `audit/runs/round_8_c14_fix_cat11.json` -> `cat11=100.0%`.
- Revalidacion actual:
  - `audit/runs/round_12_consolidacion_full.json` -> cat14 `46/46`,
    `100.0%`.
  - `audit/runs/round_12_consolidacion_cross.json` -> cat14 `46/46`,
    `100.0%`.

Conclusion: Round 8 sigue cerrado. C14 no se reabrio.

### 3.2 Round 9 - refactor dispatch

- Evidencia historica:
  - `src/carter_v3/tools/dispatch.py`: `768 -> 75` lineas.
  - `src/carter_v3` total: `6353 -> 6350`.
  - `audit/runs/round_9_refactor_full.json` ->
    `global=99.81%`, `cat11=100.0%`, `cat14=100.0%`, `cat18=100.0%`.
- Estado actual de tamano:
  - `src/carter_v3/tools/dispatch.py`: `90` lineas.
  - `src/carter_v3` total actual: `7602` lineas Python (`54` archivos).
  - Hotspots actuales: `agent.py` `617`, `tools/verifier.py` `607`.

Lectura honesta:
- El monolito `dispatch.py` no reaparecio; el refactor estructural se
  mantiene.
- La complejidad total SI crecio despues de Round 9 (`6350 -> 7602`,
  `+1252` lineas, `+19.7%`). La deuda ya no esta concentrada en
  dispatch; migro sobre todo a `agent.py` y `verifier.py`.

Conclusion: Round 9 se conserva como mejora estructural real, pero dejo
complejidad nueva aguas abajo que debe vigilarse.

### 3.3 Round 10 - protocolo de tools

- Evidencia historica de mejora medible:
  - Round 9: `0/35` native tool-calls, `35/35` fallback estructural.
  - Round 10: `32/38` native tool-calls, `6/38` fallback estructural.
  - `endpoint 400 errors`: `104 -> 0`.
  - `audit/runs/round_10_tool_protocol_cat7.json` -> `100.0%`.
  - `audit/runs/round_10_tool_protocol_cat9.json` -> `100.0%`.
- Gap que seguia abierto desde Round 10:
  - falta validar el mismo fix en runtimes OpenAI-compat / otros modos
    de tool-calling.

Conclusion: Round 10 si mejoro el protocolo de tools de forma medible.
Ese cierre es mitigacion fuerte, no cierre universal multi-runtime.

### 3.4 Round 11 y 11b - validator + provenance

- Evidencia historica:
  - `audit/runs/round_11_validator_fix.json` -> `526/526`,
    `global=100.0%`.
  - `audit/runs/round_11_provenance_full.json` -> `526/526`,
    `global=100.0%`, cat11 `100.0%`.
  - `audit/runs/round_11_provenance_cat11.json` -> cat11 `49/49`,
    `100.0%`.
- Suites:
  - baseline pre-campana: `304` tests.
  - estado actual: `313` tests.
- Contrato de provenance:
  - `user_approved=True` del LLM ya no destraba `HIGH-risk`.
  - Solo destraba una provenance estructural generada por el loop.
  - `CRITICAL` sigue bloqueado.

Conclusion: Round 11 y 11b siguen cerrados en safety/policy.

## 4. Validacion real de esta ronda

### 4.1 Test suite y guard

```text
python -m pytest -q
-> PASS, exit 0, 313 tests recolectados
```

Observacion operativa:
- Tras completar `[100%]`, el host emitio ruido post-run de
  `pywinauto` / COM (`Windows fatal exception: code 0x80040155`).
- El comando termino con exit code `0`, asi que no fue un fallo de
  suite, pero queda documentado como ruido del entorno Windows.

```text
python audit/hardcode_guard.py
-> hardcode_guard: clean (54 files scanned)
```

### 4.2 Runner full live-safe principal

```text
python audit/full_matrix_runner.py --mode live-safe \
  --label round_12_consolidacion_full \
  --out audit/runs/round_12_consolidacion_full.json
```

Resultado:
- `executed=526`, `passed=521`, `failed=5`
- `global=99.05%`
- `P1=100.0%`, `P2=97.31%`, `P3=100.0%`
- cat11 `100.0%`
- cat14 `100.0%`
- cat17 `83.87%`
- cat18 `100.0%`
- `p95=1416.5ms`

Fallas reales:
- `C17.13`
- `C17.16`
- `C17.18`
- `C17.20`
- `C17.21`

Todas por la misma familia:
- validator `active_app_policy`
- razon `active_app_contamination`
- contaminacion concreta: titulos reales del host con `PowerShell` /
  `Developer PowerShell for VS 2019`

### 4.3 Runner full live-safe cross-model

```text
python audit/full_matrix_runner.py --mode live-safe --model phi3.5:latest \
  --label round_12_consolidacion_cross \
  --out audit/runs/round_12_consolidacion_cross.json
```

Resultado:
- `executed=526`, `passed=525`, `failed=1`
- `global=99.81%`
- `P1=99.72%`, `P2=100.0%`, `P3=100.0%`
- cat11 `100.0%`
- cat14 `100.0%`
- cat17 `100.0%`
- cat18 `100.0%`
- `p95=3022.5ms`

Falla real:
- `C1.06`, otra vez por `active_app_contamination`, porque el saludo
  menciono `PowerShell`.

## 5. Metricas canonicas de consolidacion

| metrica | antes | despues |
|---|---:|---:|
| tests totales | `304` | `313` |
| lineas `src/carter_v3` en refactor R9 | `6353` | `6350` |
| lineas `src/carter_v3` actuales | `6350` | `7602` |
| global runner baseline | `99.24%` | `99.05%` (`qwen`) |
| global runner cross-model | n/a | `99.81%` (`phi3.5`) |
| C14.01-04 | `0/4` | `4/4` |
| cat14 actual | `91.30%` | `100.0%` |
| cat11 | `100.0%` | `100.0%` |

## 6. Que quedo realmente cerrado

- Round 8: cerrado y revalidado. C14 sigue en `100%`.
- Round 9: cerrado como refactor estructural; no revirtio a monolito.
- Round 10: cerrado como mejora medible del protocolo en Ollama local;
  no cerrado universalmente multi-runtime.
- Round 11: cerrado. Validator y provenance siguen defendiendo cat11.

## 7. Que sigue abierto

- `R-P4-10` debe reabrirse honestamente:
  `active_app_contamination` reaparecio en el runner principal, ahora
  concentrado en follow-ups de cat17.
- Los gaps multi-runtime de Round 10 siguen mitigados, no cerrados.
- La complejidad total del runtime crecio `+1252` lineas desde el
  post-refactor de Round 9; no es monolito de nuevo, pero si deuda
  estructural real.
- El cluster terminal/policy de `RESIDUAL` sigue con:
  `R-V3-T1`, `R-V3-T3`, `R-V3-T4`.

## 8. Veredicto canonico

`V3_SECOND_CAMPAIGN_PARTIAL`

Justificacion:
- No corresponde `CLOSED` porque el runner principal quedo por debajo
  del baseline de Round 7 (`99.05% < 99.24%`).
- No corresponde `BLOCKED` porque los fixes de Round 8-11 si aterrizaron
  y siguen visibles: C14 permanece cerrado, cat11 permanece en 100%, y
  el protocolo de tools mejoro de forma medible.
- La salida honesta es `PARTIAL`: segunda campana util y mayormente
  aterrizada, con residual reabierto y documentado en `active_app_policy`.
