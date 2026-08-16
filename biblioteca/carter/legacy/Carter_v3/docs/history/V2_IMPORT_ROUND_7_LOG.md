# V2 -> V3 Import Round 7 - Live Log

> Ronda de consolidacion final. No agrega features nuevas.
> Su trabajo es revalidar, medir, cerrar documentalmente y decidir que NO vale
> la pena seguir portando desde v2.

Date: 2026-05-03
Author: GPT-5 Codex

## Plan

1. Releer contexto, handoff, auditoria y logs previos para fijar verdad vigente.
2. Ejecutar validacion obligatoria completa sobre el baseline actual.
3. Repetir live-safe con un segundo modelo local y comparar.
4. Consolidar ROI por ronda, detectar complejidad accidental y cerrar docs.

---

## Steps

### STEP 0 - contexto y trazabilidad releidos [DONE]

Leido antes de editar:
- `ContextoCarter.md`
- `Carter_v3/CLAUDE_V2_IMPORT_HANDOFF.md`
- `Carter_v3/V2_TO_V3_IMPORT_AUDIT.md`
- `Carter_v3/CHANGELOG.md`
- `Carter_v3/RESIDUAL.md`
- `Carter_v3/V2_IMPORT_ROUND_1_LOG.md`
- `Carter_v3/V2_IMPORT_ROUND_2_LOG.md`
- `Carter_v3/V2_IMPORT_ROUND_3_LOG.md`
- `Carter_v3/V2_IMPORT_ROUND_4_LOG.md`
- `Carter_v3/V2_IMPORT_ROUND_5_LOG.md`
- `Carter_v3/V2_IMPORT_ROUND_6_LOG.md`
- `Carter_v3/audit/runs/v2_import_round_*`

### STEP 1 - validacion obligatoria baseline [DONE]

Comandos ejecutados en `Carter_v3/`:
- `python -m pytest -q`
- `python audit/hardcode_guard.py`
- `python audit/full_matrix_runner.py --mode live-safe --label v2_import_round_7_full --out audit/runs/v2_import_round_7_full.json`

Resultados:
- `pytest`: PASS (`304` tests).
- `hardcode_guard`: `clean (47 files scanned)`.
- Live-safe qwen:
  - `executed=526`, `passed=522`, `failed=4`, `skipped=128`
  - `global=99.24%`
  - `P1/P2/P3=100.0%/98.55%/100.0%`
  - `cat11=100.0%`, `cat18=100.0%`
  - `p95=1876.7ms`, `pre_llm_p95=31.0ms`
  - `validator_failures={"tool_policy": 4}`

Fallas observadas:
- `C14.01`
- `C14.02`
- `C14.03`
- `C14.04`

Todas siguen siendo el cluster de typos/targeting ya heredado de rondas previas.

### STEP 2 - cross-model obligatorio [DONE]

Deteccion:
- `ollama list` mostro multiples modelos locales disponibles.

Comando ejecutado:
- `python audit/full_matrix_runner.py --mode live-safe --model phi3.5:latest --label v2_import_round_7_cross_phi35 --out audit/runs/v2_import_round_7_cross_phi35.json`

Resultado:
- `executed=526`, `passed=520`, `failed=6`, `skipped=128`
- `global=98.86%`
- `P1/P2/P3=99.64%/98.07%/100.0%`
- `cat11=100.0%`, `cat18=100.0%`
- `p95=3445.6ms`, `pre_llm_p95=31.0ms`
- `heartbeat_turns=60`
- `validator_failures={"active_app_policy": 2, "tool_policy": 4}`

Lectura:
- `phi3.5:latest` sigue aterrizando baseline live-safe.
- Pero es peor que `qwen2.5:7b-instruct` en latencia y robustez cross-model.
- Las 4 fallas de tool-policy siguen en C14.01-04.
- Ademas aparecen 2 contaminaciones de ventana activa:
  - `C3.24`
  - `C5.33`

### STEP 3 - consolidacion ROI + complejidad accidental [DONE]

ROI real por ronda:
- Round 1: audio real + resolver/appsfolder opt-in.
- Round 2: cierre cooperativo + focus real + inventario window/process.
- Round 3: UIA interna determinista.
- Round 4: filesystem universal con backup delete.
- Round 5: terminal seguro/verificable.
- Round 6: browser minimo util con DDG backend.

Metricas de categoria ya consolidadas:
- `v2_import_round_2_cat7.json` -> `100%`
- `v2_import_round_2_cat13.json` -> `100%`
- `v2_import_round_3_cat13.json` -> `100%`
- `v2_import_round_4_cat9.json` -> `100%`
- `v2_import_round_5_cat10.json` -> `100%`
- `v2_import_round_5_cat11.json` -> `100%`
- `v2_import_round_6_cat8.json` -> `100%`

Complejidad accidental detectada:
- cap de tools preservado: `32`
- `src/carter_v3` actual: `7277` lineas Python
- archivo mas grande: `src/carter_v3/tools/dispatch.py` = `822` lineas
- `tests/` actual: `2639` lineas Python

Conclusion:
- el porting selectivo rindio;
- pero seguir metiendo piezas v2 sin refactor previo ya no tiene ROI limpio.

### STEP 4 - cierre documental final [DONE]

Archivos actualizados:
- `Carter_v3/CHANGELOG.md`
- `Carter_v3/RESIDUAL.md`
- `Carter_v3/V2_IMPORT_ROUND_7_LOG.md`

---

## Entrega final

### 1. Que rondas quedaron realmente cerradas

- Round 1: cerrada en su scope; baseline actual revalidado.
- Round 2: cerrada en su scope.
- Round 3: cerrada en su scope.
- Round 4: cerrada en su scope.
- Round 5: cerrada en su scope.
- Round 6: cerrada en su scope.
- Round 7: cierre documental/canonico completado.

Ninguna de esas clausuras significa "portar todo v2". Significa que cada ronda
cumplio su corte selectivo y verificable.

### 2. Que ROI real dejo cada ronda

- Round 1 -> controles de audio reales + base de resolucion de apps.
- Round 2 -> control real de procesos/ventanas.
- Round 3 -> evidencia UIA barata antes de vision.
- Round 4 -> filesystem honesto y con rollback parcial.
- Round 5 -> terminal util sin romper safety.
- Round 6 -> browser minimo util con evidencia real.

### 3. Que importaciones futuras NO valen la pena

- `steam_*`
- `office_*`
- `gui_do`
- `web_connect_cdp`
- `web_tabs`
- `web_use_tab`
- `web_profile_*`
- `web_extension_relay_*`
- `meta_*`
- `skills_*`
- cualquier surface cuyo verifier fuerte no exista de verdad

### 4. Resultados reales

- baseline principal (`qwen2.5:7b-instruct`): `99.24%`, `522/526`, p95 `1876.7ms`
- cross-model (`phi3.5:latest`): `98.86%`, `520/526`, p95 `3445.6ms`
- `pytest`: `304` tests PASS
- `hardcode_guard`: clean

### 5. Veredicto canonico de la campana v2 -> v3

- baseline: `V3_BASELINE_LANDED_LIVE_VERIFIED`
- campana: `V2_TO_V3_IMPORT_CAMPAIGN_CLOSED_SELECTIVE_SUCCESS`

Interpretacion:
- el objetivo correcto NO era restaurar el catalogo v2;
- el objetivo correcto SI era extraer primitivas universales de alto ROI;
- ese objetivo ya quedo cumplido.

### 6. Updates documentales finales

- `CHANGELOG.md` actualizado con validacion round 7, cross-model, ROI y veredicto.
- `RESIDUAL.md` actualizado con cierre honesto del backlog de campana.
