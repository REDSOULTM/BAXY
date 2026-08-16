# V2 Import Round 13A - residual triage y bugfixes reales

Fecha: 2026-05-04.
Scope: SOLO `Carter_v3/`.

## 1. Objetivo

Ejecutar una ronda de bugfix estricta:

- leer completo contexto, changelog, residual y logs 8/8b/9/10/11/12;
- clasificar `RESIDUAL.md` en:
  - `BUG_REAL_ABIERTO`
  - `DEUDA_TECNICA_ABIERTA`
  - `LIMITE_DE_DISENO_O_RUNTIME`
  - `CERRADO_O_MITIGADO`
- actuar SOLO sobre bugs reales demostrables en Carter;
- no tapar limites del modelo/runtime con hacks.

## 2. Triage canonico del residual

Regla usada:

- `latest mention wins`: si un ID aparece varias veces en `RESIDUAL.md`,
  manda su evidencia/lectura mas reciente;
- backlog historico supersedido por secciones posteriores NO se trata
  como bug abierto por defecto;
- para quedar en `BUG_REAL_ABIERTO` un item tenia que tener evidencia
  viva actual en Carter, no solo historia.

### 2.1 `BUG_REAL_ABIERTO` al inicio de la ronda

- `R-P4-10`

Evidencia:

- `audit/runs/round_12_consolidacion_full.json`
  - `global=99.05%`
  - fallas: `C17.13`, `C17.16`, `C17.18`, `C17.20`, `C17.21`
  - todas por `active_app_policy -> active_app_contamination`
- `audit/runs/round_12_consolidacion_cross.json`
  - `global=99.81%`
  - falla: `C1.06`
  - misma familia: `active_app_contamination`

Conclusion:
- SI era bug real del core.
- No era ruido puro del validator porque el runtime dejaba pasar replies
  contaminados y una observacion de pantalla no pedida.

### 2.2 `DEUDA_TECNICA_ABIERTA`

- `R-V2-B2`, `R-V2-B4`
- `R-V3-1`, `R-V3-2`, `R-V3-3`, `R-V3-4`, `R-V3-7`, `R-V3-11`
- `I-1`, `I-2`, `I-3`, `I-4`, `I-5`
- `R-P3-3`, `R-P3-4`, `R-P3-6`, `R-P3-8`, `R-P3-15`, `R-P3-22`,
  `R-P3-27`, `R-P3-29`, `R-P3-32`
- `R-P4-04`, `R-P4-05`, `R-P4-06`, `R-P4-08`
- `R-V3-T1`, `R-V3-T3`, `R-V3-WEB-1`, `R-V3-C3`

Lectura:
- cobertura, complejidad, validacion multi-runtime, gaps de contrato;
- sin fallo vivo actual equivalente al de `R-P4-10`.

### 2.3 `LIMITE_DE_DISENO_O_RUNTIME`

- `R-V2-B3`
- `R-V3-5`, `R-V3-6`, `R-V3-8`, `R-V3-9`, `R-V3-10`
- `R-P3-5`, `R-P3-7`, `R-P3-12`, `R-P3-13`, `R-P3-14`, `R-P3-21`,
  `R-P3-26`, `R-P3-30`, `R-P3-31`, `R-P3-34`
- `R-P4-01`, `R-P4-02`, `R-P4-03`, `R-P4-07`, `R-P4-09`, `R-P4-11`,
  `R-P4-XX-skipped`
- `R-V2I-01`, `R-V2I-02`, `R-V2I-04`
- `R-V3-T4`, `R-V3-C2`, `R-V3-C4`

Lectura:
- limites honestos de host Windows, subset live-safe, OCR/VLM/browser
  fuera del baseline o decisiones deliberadas de diseno.

### 2.4 `CERRADO_O_MITIGADO`

- `R-V2-B1`, `R-V2-B5`, `R-V2-B6`, `R-V2-B7`
- `R-P3-1`, `R-P3-2`, `R-P3-9`, `R-P3-10`, `R-P3-11`, `R-P3-16`,
  `R-P3-17`, `R-P3-18`, `R-P3-19`, `R-P3-20`, `R-P3-23`, `R-P3-24`,
  `R-P3-25`, `R-P3-28`, `R-P3-33`
- `R-P4-12`
- `R-V2I-03`, `R-V2I-05`
- `R-V3-T2`, `R-V3-C1`, `R-V3-C5`, `R-V3-C6`

Lectura:
- cierres fuertes o mitigaciones ya aterrizadas;
- backlog historico expresamente rechazado/supersedido.

## 3. Priorizacion aplicada

### 1. `R-P4-10`

Por que fue primero:

- impacto directo en el runner global;
- pegaba a `C17`, la prioridad marcada por el usuario;
- tenia evidencia reproducible en main y cross-model;
- habia un fix estructural limpio en Carter.

### 2. Todo lo demas

No se toco porque:

- o no era bug real vivo del core;
- o dependia de modelo/runtime/host;
- o era deuda tecnica abierta sin regresion funcional demostrada.

## 4. Diagnostico exacto de `R-P4-10`

### Causa 1 - guard runtime ciego en `potential_action`

`src/carter_v3/turn_support.py`:

- `collect_active_app_tokens(...)` exigia
  `intent_kind in {"trivial_lowinfo","chat","identity","knowledge","question"}`.
- follow-ups como `el segundo`, `al revés`, `todos menos el primero` y
  chat como `buenas noches` entraban como `intent.kind="potential_action"`
  aun cuando `looks_action=False`.
- resultado: el guard runtime NO cargaba tokens activos del escritorio y
  la reply podia mencionar `PowerShell` sin ser bloqueada.

### Causa 2 - `window_list` espurio aceptado en follow-up ambiguo

`src/carter_v3/agent.py`:

- en `C17.13` (`muéstramelo`) el LLM emitio `window_list` sin que el
  turno tuviera forma estructural de observacion;
- el agent lo acepto y ejecuto;
- `compose_default_reply(...)` devolvio la lista de ventanas reales del
  host (`Developer PowerShell for VS 2019`, etc.);
- esa respuesta contaminada luego se reciclo por `prior_turns` en
  `C17.16`, `C17.18`, `C17.20`, `C17.21`.

No era un problema de:

- `tool protocol` con Ollama;
- policy/provenance;
- C14;
- validator solamente.

## 5. Fixes aplicados

### 5.1 `src/carter_v3/turn_support.py`

- `collect_active_app_tokens(...)` ahora usa SOLO `looks_action` como
  gate real.
- Nuevo `_distinctive_title_tokens(...)`:
  - digito
  - puntuacion interna
  - CamelCase
- Esto alinea el runtime con la misma definicion estructural que usa el
  validator live para decidir leakage real.

### 5.2 `src/carter_v3/agent.py`

- Nuevo `_normalise_tool_call_for_request(...)`.
- `window_list` se descarta cuando el turno actual NO es observacional.
- Si el turno SI es observacional y el LLM omitio el modo, el agent
  completa `arguments["observation"]` desde `observation_mode(user_text)`.

## 6. Tests agregados

Archivo: `tests/test_agent_integration.py`

- `test_potential_followup_still_blocks_active_app_contamination`
  - un follow-up no accionable con titulo real `Developer PowerShell...`
    ya no puede devolver `PowerShell`.
- `test_non_observation_turn_drops_spurious_window_list_tool_call`
  - `muéstramelo` ya no puede ejecutar `window_list` por capricho del LLM.
- `test_observation_turn_normalises_window_list_mode_from_prompt`
  - no se rompe el caso legitimo: si el pedido SI es observacional,
    `window_list` sigue corriendo y el modo se completa estructuralmente.

## 7. Validacion real

### 7.1 Sonda corta

`python audit/full_matrix_runner.py --mode live-safe --category 17 --label round_13a_probe_cat17 --out audit/runs/round_13a_probe_cat17.json`

- `global=100.0%`
- `cat17=100.0%`

### 7.2 Suite obligatoria

`python -m pytest -q`

- `316 passed`

`python audit/hardcode_guard.py`

- `hardcode_guard: clean (54 files scanned)`

`python audit/full_matrix_runner.py --mode live-safe --label round_13a_bugfixes --out audit/runs/round_13a_bugfixes.json`

- `executed=526`, `passed=526`, `failed=0`, `skipped=128`
- `global=100.0%`
- `P1=100.0%`, `P2=100.0%`, `P3=100.0%`
- `cat11=100.0%`
- `cat14=100.0%`
- `cat17=100.0%`
- `cat18=100.0%`
- `validator_failures={}`
- `p95=3538.7ms`

`python audit/full_matrix_runner.py --mode live-safe --model phi3.5:latest --label round_13a_bugfixes_cross --out audit/runs/round_13a_bugfixes_cross.json`

- `executed=526`, `passed=526`, `failed=0`, `skipped=128`
- `global=100.0%`
- `P1=100.0%`, `P2=100.0%`, `P3=100.0%`
- `cat11=100.0%`
- `cat14=100.0%`
- `cat17=100.0%`
- `cat18=100.0%`
- `validator_failures={}`
- `p95=7025.4ms`

Nota operativa:
- el run principal emitio un warning de `pywinauto` / COM
  (`Revert to STA COM threading mode`) al final, pero el comando quedo
  verde y el JSON se escribio correctamente.

## 8. Bugs reales cerrados

- `R-P4-10`

Desagregado estructural del cierre:

- guard runtime vuelve a cubrir follow-ups/chat no accionables aunque el
  intent upstream haya quedado en `potential_action`;
- `window_list` deja de ejecutarse cuando no hay pedido observacional
  real;
- el historial de follow-ups deja de contaminarse con replies que
  listan ventanas del host sin haber sido pedidas.

## 9. Bugs reales que NO se cerraron

Ninguno.

Despues del triage y de la validacion de esta ronda, no quedo otro
`BUG_REAL_ABIERTO` demostrable dentro de Carter.

## 10. Items reclasificados honestamente

### A deuda tecnica

- `R-P4-05` / `R-P3-33` / `R-P3-20`
  - no habia fallo vivo actual en el runtime ya probado;
  - lo abierto es la validacion fuera de ese runtime, no un bug actual.
- `R-V3-T1`, `R-V3-T3`
  - allow-list/coverage, no bypass ni regresion viva en esta ronda.
- `R-V3-C3`
  - complejidad accidental real, pero deuda, no bug funcional.

### A limite/runtime

- `R-P4-11`
  - gap de native ratio depende del modelo/num_predict; no es bug del
    codigo Carter.
- `R-P4-XX-skipped`
  - subset live-safe por seguridad/scope; no regresion funcional.
- `R-V3-T4`
  - la latencia de cat10 es trabajo real del runtime, no bug nuevo.

## 11. Cambios documentales

- `CHANGELOG.md`
  - nueva `Seccion X - Round 13A`
- `RESIDUAL.md`
  - nueva `Seccion X - Round 13A triage canonico del residual`
- `V2_IMPORT_ROUND_13A_LOG.md`
  - este archivo

## 12. Veredicto

`BUGFIX_ROUND_CLOSED`

Razon:

- no se rompio `C14` (`100.0%`);
- `cat11` siguio en `100.0%`;
- el runner principal subio de `99.05%` a `100.0%`;
- se redujo el numero de `BUG_REAL_ABIERTO` de `1` a `0`;
- no se usaron hacks por app, marca, idioma o caso puntual.
