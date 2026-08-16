# Round 15 - REPL follow-ups ambiguos y launches reales de Windows

Fecha: 2026-05-04.

## Objetivo

Atacar dos frentes del runtime real sin meter hacks por app/modelo:

1. endurecer el REPL frente a follow-ups ambiguos;
2. mejorar discovery / launch / verificación de apps externas en Windows.

Referencia obligatoria aplicada durante la ronda:

- `ContextoCarter.md`
  - honestidad y no fake success;
  - verificación real;
  - no hardcodes por app;
  - diseño por intención / capacidades declarativas.

## Cambios principales

### 1. Follow-ups ambiguos / fuertes

- `src/carter_v3/session_state.py`
  - `prior_reopen_match(...)` ya acepta follow-up fuerte de reapertura
    (`ábrelo`) además del patrón explícito `abre lo que acabas de cerrar`.
  - `prior_deictic_match(...)` puede reutilizar el último `app_open`
    reciente cuando el follow-up es fuerte (`ahora ciérralo`) aunque el
    `open` previo haya quedado `PENDING` / `UNVERIFIABLE`.
  - `cierra eso` sigue tratado como ambiguo y no reutiliza target.

- `src/carter_v3/request_patterns.py`
  - robustez Unicode para:
    - deícticos como `ciérralo`;
    - compuestos tipo `Abre Calculadora y minimízala`.

### 2. Launch / verify de apps reales en Windows

- `src/carter_v3/perception/app_resolver.py`
  - el inventario ya no depende solo de `Get-StartApps`;
  - ahora agrega:
    - `App Paths`;
    - shortcuts `.lnk` del menú Inicio;
  - `find_launch_entry(...)` elige targets de launch de forma conservadora:
    - `.exe` / `.lnk` solo por match fuerte;
    - `AppsFolder` puede usar el match más amplio del inventario.

- `src/carter_v3/agent.py`
  - la traducción de `app_open` ahora adjunta:
    - `display_name`
    - `expected_process`
  - la traducción de launch se limita a `app_discovery=True`, para no
    contaminar tests / engines deterministas.

- `src/carter_v3/tools/dispatch_app.py`
  - captura baseline pre-launch de procesos y ventanas;
  - usa `startfile` para `.lnk` en Windows;
  - prioriza match exacto de proceso sobre substring.

- `src/carter_v3/tools/verifier.py`
  - `app_open` verifica con múltiples needles:
    - `display_name`
    - `expected_process`
    - `target`
  - puede confirmar por ventana nueva respecto de la baseline pre-launch;
  - evita preferir helpers tipo `steamwebhelper.exe` cuando existe un
    proceso exacto esperado.

- `src/carter_v3/response_composer.py`
  - las replies públicas de `app_open` / `app_close` usan `display_name`
    cuando existe, en vez de exponer URIs internas `shell:appsfolder`.

- `audit/full_matrix_runner.py`
  - el builder en `live` / `live-safe` crea el engine con
    `app_discovery=True`, alineando runner y launcher real.

## Tests agregados / ajustados

- `tests/test_agent_integration.py`
  - reapertura fuerte con `ábrelo`;
  - `cierra eso` sigue ambiguo;
  - follow-up fuerte puede cerrar un `app_open` previo no confirmado;
  - traducción exacta de launch directo para `Steam`;
  - no traducción de `notepad` -> `Notepad++`.

- `tests/test_app_resolver.py`
  - cobertura del nuevo `find_launch_entry(...)`;
  - cache del inventory loader.

- `tests/test_app_open_verifier.py`
  - confirma por ventana nueva vs baseline pre-launch;
  - adapta el helper de `ShellExecuteW` al baseline nuevo.

- `tests/test_request_patterns_routing.py`
  - `Ahora ciérralo` con acento;
  - `Abre Calculadora y minimízala`.

## Evidencia real del host

Inspección del inventario local:

- `steam` -> `Steam.lnk`
- `spotify` -> `Spotify.lnk`
- `whatsapp` -> `shell:appsfolder\\5319275A.WhatsAppDesktop...`
- `marvel rivals` -> sin entry encontrada

Chequeos reales con launcher:

- `Run_Carterv3.py --once "abre spotify"` ->
  `COMPLETE / all_tools_confirmed`
- `Run_Carterv3.py --once "abre whatsapp"` ->
  `COMPLETE / all_tools_confirmed`
- `Run_Carterv3.py --once "abre steam"` ->
  `UNVERIFIED / verification_inconclusive`
  - detalle: `steam.exe` preexistía y no se pudo atribuir causalmente al
    comando actual.

Lectura honesta:

- `spotify` y `whatsapp` quedan demostrablemente mejorados en runtime real;
- `steam` sigue abierto como límite causal del host, no como fake success.

## Validación final

- `python -m pytest -q` -> PASS
- `python audit/hardcode_guard.py` ->
  `hardcode_guard: clean (54 files scanned)`
- `python audit/minimum_testing_runner.py --mode live-safe --label round_15_repl_launch_hardening_release --out audit/runs/round_15_repl_launch_hardening_release.json`
  - `global=100.0%`
  - `required100=True`
  - `p95=8038.4ms`
  - `verdict=MINIMUM_TESTING_PASS_WITH_WARNINGS`

## Residual honesto

- `steam`
  - sigue pudiendo quedar `UNVERIFIED` si el proceso ya existía y no aparece
    evidencia causal nueva.
  - estado: `LIMITE_DE_DISENO_O_RUNTIME`

- `marvel rivals`
  - no apareció entrada estructural en el inventario local de este host.
  - estado: `LIMITE_DE_DISENO_O_RUNTIME`

- PowerPoint / authoring
  - sigue fuera del catálogo actual.
  - estado: `LIMITE_DE_DISENO_O_RUNTIME`
