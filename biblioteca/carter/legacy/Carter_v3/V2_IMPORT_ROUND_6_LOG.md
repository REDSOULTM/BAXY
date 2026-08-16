# V2 -> V3 Import Round 6 - Browser minimo util

> Backend util escondido detras de un surface chico.  Verificacion mas honesta.

Date: 2026-05-03
Author: Claude Opus 4.7

## Mision

Ejecutar `V2 Import Round 6`: redisenar browser/web extrayendo lo justo de
`legacy/Carter_v2/src/carter_v2/capabilities/web.py` para fortalecer
`web_open_url`, `web_search`, `web_extract` y mejorar el readback de
URL / tab / domain.  No reintroducir CDP, tabs/profiles/extension relay
ni cualquier hack por browser.

## 1. Que parte de `web.py` se porto realmente

Solo ayudantes internos.  Cero tools nuevos en el catalog publico.

| v2 source | v3 destino | proposito |
|---|---|---|
| `_parse_duckduckgo_results_regex` (web.py L1003) | `tools/web_helpers.py::parse_duckduckgo_results` | parser regex-only del HTML de DuckDuckGo (sin `bs4`, sin `requests`). |
| `_clean_result_url` (web.py L1063) | `tools/web_helpers.py::_clean_result_url` (privado) | desenvolver `/l/?uddg=` y normalizar URLs absolutas. |
| `_strip_html` (web.py L1057) | `tools/web_helpers.py::_strip_html_tags` (privado) | strip de tags + entities para snippets/titles. |
| logica de `_search_duckduckgo_html` (web.py L703) | `tools/web_helpers.py::fetch_duckduckgo_results` | scrape stdlib-only de duckduckgo HTML, devuelve `{ok, results, status_code, error}`, nunca raise. |

Tambien se anadio en `tools/dispatch.py` un helper privado `_domain_of(url)`
para readback estructurado del dominio (host sin `www.`) que ahora vive
en `ToolResult.data["domain"]` para `web_open_url` / `web_search` y en
`data["final_domain"]` para `web_extract`.

## 2. Que NO se porto y por que

| v2 surface | razon de exclusion |
|---|---|
| `web_navigate` (Playwright) | Playwright no es local-first ni minimo; reintroduce dependencia pesada y un canal automatizado dificil de auditar. |
| `web_download` | requiere browser real; no es necesario para C8.  Si alguna vez se necesita, va detras de `web_extract` o por `terminal_run_command`. |
| `web_click`, `web_fill`, `web_screenshot`, `web_eval` | tabs/clicks/scroll automatizados son surface fragil que no pasa el listado de "no reintroducir" del prompt de la ronda. |
| `web_connect_cdp`, `web_use_tab`, `web_tabs`, `web_profile_*`, `web_extension_relay_*` | explicitamente prohibidos por el handoff (`CLAUDE_V2_IMPORT_HANDOFF.md`).  Reintroducirian CDP/profiles/extensions como tools de core. |
| `_search_google_playwright`, `_search_bing_urllib` | Bing/Google scrape como providers paralelos = mas surface, mas hacks y mas drift sin ROI claro.  DuckDuckGo HTML ya entrega resultados utiles para C8.  Si el usuario los necesita, el LLM puede pedir varios `web_search` con queries distintas. |
| `_resolve_browser_launch`, `_common_browser_paths`, `_find_chromium_exe` | hacks por browser.  El default de `webbrowser.open` ya delega al OS; eso es universal. |

Net: se importo un solo backend (DDG HTML scrape) y dos helpers de
parsing.  El surface publico de `web_*` queda en 3 tools, igual que
antes.

## 3. Que mejoro de C8 con evidencia real

### 3.a Antes vs despues (live-safe matrix, modelo qwen3:8b)

Comparativa C8 entre `audit/runs/v2_import_round_5_full.json` (baseline)
y `audit/runs/v2_import_round_6_full.json` (esta ronda):

| C8 case | tool | before mission_status | after mission_status |
|---|---|---|---|
| C8.01 | web_search "noticias de IA" | unverified | **complete** |
| C8.02 | web_search "AI news" | unverified | **complete** |
| C8.03 | web_open_url google.com | unverified | unverified (honesto: no browser) |
| C8.04 | web_open_url google.com | unverified | unverified (honesto: no browser) |
| C8.05 | web_open_url example.com | unverified | unverified (honesto: no browser) |
| C8.06 | web_open_url es.wikipedia.org | unverified | unverified (honesto: no browser) |
| C8.07 | web_search "python tutorial" | unverified | **complete** |
| C8.08 | web_search "best laptops 2026" | unverified | **complete** |
| C8.11 | web_extract example.com | complete | complete |
| C8.12 | web_extract example.com | complete | complete |

4 cases de `web_search` saltaron de `unverified` -> `complete` con
evidencia real (resultados parseados de DuckDuckGo via stdlib).  Los 4
de `web_open_url` siguen `unverified` porque, sin browser corriendo en
el entorno de auditoria, el verifier reporta honestamente que no puede
ver tab/dominio.  Esto es exactamente "verificacion honesta": cero fake
success.

### 3.b Metricas globales

`audit/runs/v2_import_round_6_full.json`:

```
verdict           V3_BASELINE_LANDED_LIVE_VERIFIED
executed          526
passed            522   (baseline 520)  -> +2
failed            4     (baseline 6)    -> -2
global_pass_rate  99.24% (baseline 98.86%)
C8 p95            1775 ms (baseline 1320 ms)  -> dentro de target
```

Las 4 fallas restantes son `C14.01..C14.04` (typos `opera.exe`),
heredadas y NO tocadas por esta ronda.

### 3.c C8 dedicada

`audit/runs/v2_import_round_6_cat8.json`:

```
executed       10/36  (26 skipped por mode_not_allowed)
passed         10
fail           0
pass_rate      100.0%
p50_ms         142.7
p95_ms         1257.5
```

### 3.d Pytest + hardcode guard

```
pytest:           304 passed  (baseline 294, +10 tests nuevos para round 6)
hardcode_guard:   clean (47 files scanned)
```

Tests nuevos:
- `tests/test_web_helpers.py` (5 tests para parsing/fetch DDG).
- `tests/test_web_dispatch.py` (4 tests para `_web_search` backend
  fallback, `_web_open_url` domain readback, rechazo de URLs no http).
- `tests/test_verifier.py` +1 test (`backend_results_count` como
  evidencia independiente de browser).

## 4. Que sigue pendiente

Honesto y acotado:

1. **Tab readback real.** Hoy el verifier `_web_open` se basa en
   `WindowProbe.active_title()` y polling 0..3s.  Cuando el browser
   tarda mas de 3s en aparecer, el outcome es `unverified` (correcto
   pero conservador).  Subir el limite tendria costo de latencia en
   cada turno.  Una mejora futura es desacoplar el polling a una
   verificacion diferida (post-turn), pero eso requiere repensar el
   contrato `VerifiedOutcome` y NO se hizo en esta ronda.
2. **Resultados de busqueda no se inyectan al system prompt.**  Hoy
   viven en `ToolResult.data["results"]`; el prompt composer aun no
   los formatea como evidencia para que el LLM los cite.  Es una
   mejora de prompt-shape, no de browser; queda fuera de scope.
3. **`web_extract` no soporta paginacion ni JS-rendered pages.**
   Por diseno: portar Playwright reintroducia el surface pesado.  Si
   en una ronda futura se necesita JS, se hara como provider interno
   gateado por flag, NO como tool publico.
4. **Multi-search providers.**  Solo DuckDuckGo HTML por ahora.
   Bing/Google quedaron explicitamente fuera (ver seccion 2).

## 5. Resultados reales

| validacion | resultado |
|---|---|
| `python -m pytest -q` | **304 passed in 123.56s** |
| `python audit/hardcode_guard.py` | **clean (47 files scanned)** |
| `python audit/full_matrix_runner.py --mode live-safe --label v2_import_round_6_full ...` | **522/526 pass, 99.24% global, V3_BASELINE_LANDED_LIVE_VERIFIED** |
| `python audit/full_matrix_runner.py --mode live-safe --category 8 --label v2_import_round_6_cat8 ...` | **10/10 cat8 executable pass, p95 1257ms** |

Artefactos:
- `audit/runs/v2_import_round_6_full.json`
- `audit/runs/v2_import_round_6_cat8.json`

## 6. Updates documentales

- `Carter_v3/V2_IMPORT_ROUND_6_LOG.md` (este archivo) creado.
- `Carter_v3/CHANGELOG.md` -> nueva entrada en seccion "V2 import" (round 6).
- `Carter_v3/RESIDUAL.md` -> nuevo item `R-V3-WEB-1` documentando los 2
  pendientes honestos (tab readback diferido + multi-provider opcional).

## Files touched

- `src/carter_v3/tools/web_helpers.py` (NEW, ~110 lineas; backend DDG + parsers).
- `src/carter_v3/tools/dispatch.py` (`_web_open_url`, `_web_search`, `_web_extract`, helper `_domain_of`).
- `src/carter_v3/tools/verifier.py` (`_web_open` con polling y backend-results-as-evidence).
- `tests/test_web_helpers.py` (NEW, 5 tests).
- `tests/test_web_dispatch.py` (NEW, 4 tests).
- `tests/test_verifier.py` (+1 test para backend results path).
- `CHANGELOG.md`, `RESIDUAL.md`, `V2_IMPORT_ROUND_6_LOG.md` (docs).

## Cumplimiento de invariantes

- [x] No CDP surface publica.
- [x] No tabs/profiles/extensiones como tools de core.
- [x] No hacks por browser (no `_resolve_browser_launch`, no listas de
      paths por marca).
- [x] Backend mas fuerte (DDG scrape) escondido detras del surface chico
      `web_search`.
- [x] No se toco vision.
- [x] Verifier mantiene honestidad: el browser no verificable sigue
      reportandose como `pending` / `unverified`, no como falso
      `confirmed`.
- [x] Surface publico sigue en 3 tools (`web_open_url`, `web_search`,
      `web_extract`); cap de 32 tools del catalog respetado.
