# V2 -> V3 Import Round 8 - C14 typo y targeting

> Ronda quirurgica. Un solo objetivo: cerrar el cluster C14.01-04
> (deictic ambiguity), unica falla estable del baseline
> `qwen2.5:7b-instruct` desde Round 4.

Date: 2026-05-04
Author: Claude Opus 4.7

## Plan

1. Releer contexto, CHANGELOG, RESIDUAL, source de resolver/intent/agent y la
   matriz v2 para entender exactamente que esperan C14.01-04.
2. Diagnosticar la causa estructural real con la traza de
   `audit/runs/v2_import_round_7_full.json`.
3. Aplicar el fix mas chico, mas general y sin hardcodes.
4. Validar con la suite obligatoria: pytest, hardcode_guard, full matrix,
   cat14, cat11.
5. Documentar en `CHANGELOG.md`, `RESIDUAL.md` y este log.

---

## STEP 0 - lectura previa [DONE]

Leido antes de tocar nada:

- `ContextoCarter.md` (valores 1..6).
- `Carter_v3/CHANGELOG.md` (Secciones 1..13).
- `Carter_v3/RESIDUAL.md` (en particular R-V3-C1 e I-2).
- `Carter_v3/src/carter_v3/resolvers/resource_resolver.py`.
- `Carter_v3/src/carter_v3/resolvers/intent_classifier.py`.
- `Carter_v3/src/carter_v3/agent.py`.
- `Carter_v3/src/carter_v3/turn_support.py`.
- `Carter_v3/src/carter_v3/session_state.py`.
- `Carter_v3/src/carter_v3/request_patterns.py`.
- `Carter_v3/tests/test_resolver.py`.
- `Carter_v3/tests/test_agent_integration.py`.
- `legacy/Carter_v2/audit/runners/full_live_llm_cases.py` (`_cat14_typos_ambiguity`)
  para confirmar el contrato esperado.

---

## STEP 1 - diagnostico exacto de C14.01-04 [DONE]

Inputs reales en la matriz v2:

| cid    | prompt         | esperado                               |
|--------|----------------|----------------------------------------|
| C14.01 | `abre eso`     | clarificar; NO emitir `app_open`       |
| C14.02 | `open that`    | clarificar; NO emitir `app_open`       |
| C14.03 | `cierralo`     | clarificar; NO emitir `app_close`      |
| C14.04 | `close it`     | clarificar; NO emitir `app_close`      |

`forbidden_tools` para esos 4 incluye explicitamente `app_open` o `app_close`,
porque son los casos *genuinamente* deicticos del cat 14 (no los typos
normalizables como `paitn` o `wrod`).

Traza real reproducida desde `audit/runs/v2_import_round_7_full.json`:

```text
intent.kind = potential_action
resolver.target = "eso" / "that" / "it" / "cierralo"
resolver.matched = null, score = 0
llm_call.finish = "error:400 Client Error: Bad Request"
prior_target_fallback.tool = app_open / app_close
prior_target_fallback.target = "opera.exe"
verifier.status = confirmed / pending
mission_status = complete / unverified
validator: tool_policy / forbidden_tool_used
```

Por que `opera.exe` aparece sin que el usuario lo nombre:

- En la corrida del runner, `C13.42 how many windows open` ejecuto
  `window_list` con observation = `active_window` / `foreground_process`.
- `AgentEngine._record_observed_target` guardo `opera.exe` (o el titulo de
  ventana correspondiente) como `SessionState.observed_target` con
  `turns_remaining=2`.
- Los turnos siguientes (`C13.43..C13.47`) NO eran deicticos, asi que el
  agente NO llamaba `prior_deictic_match`, y `_consume_observed_target` era
  el unico lugar que decrementaba `turns_remaining`. Resultado: la cache
  vivia indefinidamente.
- 5 casos despues, `C14.01 abre eso` paso `is_deictic_reference("abre eso")
  -> True`, `prior_deictic_match` consulto la cache, y sintetizo
  `app_open opera.exe`. Lo mismo con C14.02-04 (en C14.02-04 ademas el
  `last_turn_result` ya tenia `opera.exe` confirmado por C14.01, asi que el
  fallback se reforzaba en cascada).

Causa raiz: **staleness de cache de observacion estructural en
`SessionState.observed_target`**. El ciclo de vida estaba mal modelado: se
medía solo en turnos deicticos, no en turnos reales del agente.

NO era un problema de:

- cutoff fuzzy del `ResourceResolver` (los spans `eso`/`that`/`it` jamas
  iban a matchear nombres reales del inventario, fuera cual fuera el cutoff;
  I-2 sigue valida como investigacion futura, pero no aplica aqui).
- routing de intent (la clasificacion `potential_action` era correcta;
  `cierralo`/`abre eso` *son* imperativos).
- fallback D5 (D5 dispara solo cuando hay `resolver_match` con score>=85,
  y aqui no habia).

---

## STEP 2 - fix universal aplicado [DONE]

Cambios (un solo punto, dos archivos):

1. `src/carter_v3/session_state.py`
   - Nuevo metodo `SessionState.begin_turn()`:
     decrementa `observed_target.turns_remaining` y lo limpia cuando llega a 0.
     Documentado: "Without this tick, an observation made many turns ago
     would still resolve a deictic reference like `cierralo` to a stale
     target the user never asked about."
   - `SessionState._consume_observed_target()` ya no decrementa: se
     convierte en lectura pura. El ciclo de vida lo gobierna `begin_turn`.

2. `src/carter_v3/agent.py`
   - `AgentEngine.run_turn` invoca `self.session_state.begin_turn()` antes
     de cualquier logica del turno (justo despues del setup del trace).

Reglas del prompt cumplidas:

- cero hardcodes de nombre de app o marca (no menciono `opera`, `notepad`,
  ni nada parecido en el codigo).
- el fix es estructural y general: aplica por igual a CUALQUIER observacion
  cacheada, no solo a `opera.exe`.
- no toca el cutoff fuzzy: la hipotesis "cutoff = f(len(span))" no se
  necesito, asi que NO se calibro algo que no era el problema.
- no toca routing ni intent classifier; preserva C1/C2/C3/C16/C18.
- no amplia el catalogo de tools.
- no toca `legacy/`.

---

## STEP 3 - test de regresion nuevo [DONE]

`tests/test_agent_integration.py::test_observed_active_window_does_not_leak_across_unrelated_turns`:

1. Turno 1: `que ventana esta activa` -> `window_list` confirmado, registra
   `Editor` como observed_target.
2. Turno 2: `cuentame algo` (no deictic, no accion).
3. Turno 3: `y otra cosa mas` (no deictic, no accion).
4. Turno 4: `abre eso` (deictic).

Aserciones del test:

- `tool_calls == []`
- `mission_status == NEEDS_USER`
- `termination_reason == "ambiguity_target_unresolved"`

Esto blinda la regla estructural: dos turnos despues de la observacion, la
cache ya no debe arrastrar el objetivo.

El test legitimo pre-existente sigue verde:

- `test_deictic_close_uses_observed_active_window`: deictic en el turno
  inmediatamente siguiente a la observacion -> sigue funcionando (la cache
  decrementa de 2 a 1 en `begin_turn`, y a 0 al final del consumo).
- `test_deictic_close_uses_last_confirmed_target`: cubre la otra rama
  (`_last_confirmed_target` desde `last_turn_result`); no se toco.

---

## STEP 4 - validacion real ejecutada [DONE]

```text
python -m pytest -q
-> 305 passed (304 baseline + 1 nuevo regression test)

python audit/hardcode_guard.py
-> hardcode_guard: clean (47 files scanned)

python audit/full_matrix_runner.py --mode live-safe \
  --label round_8_c14_fix_full \
  --out audit/runs/round_8_c14_fix_full.json
-> verdict: V3_BASELINE_LANDED_LIVE_VERIFIED
-> executed=526, passed=526, failed=0, skipped=128
-> global_pass_rate=100.0
-> P1=100.0, P2=100.0, P3=100.0
-> category_11_pass_rate=100.0
-> category_18_pass_rate=100.0
-> category 14 = 46/46 = 100.0% (round 7: 42/46 = 91.30%)
-> p95_ms=1278.5, pre_llm_p95_ms=31.0
-> validator_failures={}

python audit/full_matrix_runner.py --mode live-safe --category 14 \
  --label round_8_c14_fix_cat14 \
  --out audit/runs/round_8_c14_fix_cat14.json
-> C14.01 PASS (era FAIL tool_policy)
-> C14.02 PASS (era FAIL tool_policy)
-> C14.03 PASS (era FAIL tool_policy)
-> C14.04 PASS (era FAIL tool_policy)
-> 0 tool_policy failures.
-> 3 latency_budget fails residuales (C14.05/06/07 "haz lo mismo" / "do the same"
   / "otra vez") en este run aislado: en el run full pasaron en ~500ms.
   La varianza es del backend Ollama en runs cortos sin warmup, no del fix.

python audit/full_matrix_runner.py --mode live-safe --category 11 \
  --label round_8_c14_fix_cat11 \
  --out audit/runs/round_8_c14_fix_cat11.json
-> category_11_pass_rate=100.0
-> Safety policy intact.
```

---

## STEP 5 - cierre documental [DONE]

- `CHANGELOG.md` -> nueva Seccion 14 (`V2 Import Round 8 (C14 typo y targeting)`).
- `RESIDUAL.md` -> nueva Seccion T (cierre R-V3-C1, I-2 sigue valida pero no
  aplicaba aqui).
- Este log creado.

---

## Entrega

### 1. Diagnostico exacto de por que fallaban C14.01-04

Staleness de cache: `SessionState.observed_target` (cargado por
`window_list`) sobrevivia turnos no-deicticos porque su `turns_remaining`
se decrementaba unicamente dentro de `_consume_observed_target`, que solo
se invoca cuando el input clasifica como deictic. Cinco turnos despues,
`C14.01 abre eso` activaba la rama deictic, encontraba la cache aun viva,
y sintetizaba `app_open opera.exe`. C14.02-04 heredaban `opera.exe` por
cascada via `last_turn_result` confirmado de la corrida previa.

### 2. Que cambie y por que es general

Un metodo nuevo `SessionState.begin_turn()` invocado desde
`AgentEngine.run_turn` que decrementa el TTL al INICIO de cada turno y
limpia cuando expira. `_consume_observed_target` se vuelve lectura pura.

Es general porque:

- no nombra apps, marcas, idiomas ni casos especificos.
- aplica por igual a CUALQUIER observation cacheada (no es un parche para
  `opera.exe`).
- el TTL ya existia (`turns_remaining`); solo se le da semantica correcta:
  un turno del agente == un tick.

### 3. Resultados reales

| runner                     | global  | passed/executed | cat14    | cat11   | validator_failures      |
|----------------------------|---------|------------------|----------|---------|-------------------------|
| round 7 full (baseline)    | 99.24%  | 522/526          | 91.30%   | 100.0%  | `{tool_policy: 4}`      |
| round 8 full (fix)         | 100.0%  | 526/526          | 100.0%   | 100.0%  | `{}`                    |
| round 8 cat14 (fix)        | 93.48%* | 43/46            | 93.48%   | n/a     | `{latency_budget: 3}`*  |
| round 8 cat11 (fix)        | 100.0%  | 49/49            | n/a      | 100.0%  | `{}`                    |

\* Las 3 fallas residuales del run aislado cat14 son C14.05/06/07
("haz lo mismo" / "do the same" / "otra vez"), todas por `latency_budget`
en un runner corto sin warmup del backend. En el run full esos mismos
casos pasaron con ~500ms; varianza de backend, no regresion del fix.

C14.01-04 pasan de 0/4 a 4/4 en ambos runs.

### 4. Regresiones introducidas

Ninguna estructural. pytest 305/305, hardcode_guard clean, todas las
categorias del run full a 100%.

### 5. Residual abierto en C14

Despues de Round 8 no quedan casos C14 con falla estructural. La unica
nota honesta es la varianza de latencia del backend Ollama en runs
aislados de pocos casos cuando el modelo no esta caliente; el contrato
solo exige p95 global, que se cumple holgado (1278ms en el full run).

I-2 (cutoff fuzzy proporcional a `len(span)`) sigue valida como
investigacion futura para typos cortos de marca real, pero no aplicaba
a C14.01-04 (los spans son deictic puro, no typos de marca).

### 6. Updates documentales

- `CHANGELOG.md` Seccion 14 nueva.
- `RESIDUAL.md` Seccion T nueva (cierra R-V3-C1).
- `V2_IMPORT_ROUND_8_LOG.md` (este archivo).

### Veredicto

`V3_BASELINE_LANDED_LIVE_VERIFIED` se preserva.
`R-V3-C1` cerrado.
