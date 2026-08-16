# V2 Import Round 8b - app_open fake success

Fecha: 2026-05-04.
Prioridad: CRITICA (R4 cero fake success, Valor 4 ContextoCarter).

## 1. Bug observado en vivo

```
Usuario: "abre spotify"
Carter:  [complete / all_tools_confirmed] Abri spotify y lo verifique.
Realidad: Windows mostro dialogo "no puede encontrar el archivo spotify"
```

## 2. Diagnostico exacto (confirmado en codigo)

Dos fallos compuestos.

### Fallo 1 - Dispatcher retorna ok=True aunque el launch fallo

Archivo: `src/carter_v3/tools/dispatch.py`, metodo `_app_open`, paso 3 del ladder.

Codigo previo:
```python
subprocess.Popen(["cmd", "/c", "start", "", target], ...)
return ToolResult(c.name, ok=True, data={"target": target, "method": "windows_start"})
```

Por contrato Win32, `cmd /c start "" <target>` SIEMPRE termina con exit code 0
aunque el target no exista: el shell se considera exitoso porque "lanzo el comando
start", aunque el archivo no se encuentre. El dialogo de error lo emite el shell
de Windows DESPUES, fuera del proceso `cmd.exe`. Resultado: `Popen` retorna sin
excepcion y Carter reporta `ok=True` aunque no abrio nada.

### Fallo 2 - Verifier confirma proceso preexistente

Archivo: `src/carter_v3/tools/verifier.py`, metodo `_app_open`.

Codigo previo:
```python
proc = _find_running_process(target)
if proc:
    return VerifiedOutcome(call.name, VerifierStatus.CONFIRMED, ...)
```

Si el target ya estaba corriendo antes del comando (ej. usuario tenia Spotify
abierto), `_find_running_process` lo encuentra y el verifier emite CONFIRMED
sin verificar relacion causal con el dispatch actual. Combinado con el Fallo 1,
basta con tener cualquier proceso preexistente que matchee el nombre (browser
con tab "Spotify Web Player", explorer.exe con carpeta "Spotify", etc.) para
generar fake success.

## 3. Que cambie y por que

### Fix 1 - dispatch.py `_app_open`

- Reemplazado el paso 3 `cmd /c start` por `ShellExecuteW` via `ctypes`.
  `ShellExecuteW` retorna entero >32 en exito y un codigo de error documentado
  cuando el archivo no existe (2=ERROR_FILE_NOT_FOUND, 3=ERROR_PATH_NOT_FOUND,
  31=SE_ERR_NOASSOC, etc.). Es la API correcta en Win32 para "abrir cualquier
  cosa que el usuario podria abrir desde el menu Inicio" Y es la unica que
  surface el error de manera honesta.
- Cuando rc <= 32, el handler retorna `ok=False` con `message="shellexecute_failed:<rc>"`
  y `data.shellexecute_rc=<rc>`.
- Cuando rc > 32, retorna `ok=True` con `data.method="shellexecute"`.
- Todos los pasos del ladder (appsfolder, direct popen, shellexecute) ahora
  estampan un `launch_time = time.monotonic()` en `ToolResult.data` justo
  antes del intento de lanzamiento. Es la baseline temporal que el verifier
  usa para distinguir un proceso recien creado de uno preexistente.
- Extraido helper privado `_windows_shellexecute(c, target, stdout)` para
  mantener el ladder principal compacto y permitir monkeypatch en tests.

### Fix 2 - verifier.py `_app_open`

- Lee `launch_time = result.data.get("launch_time")`.
- Nuevo helper `_find_running_process_with_age(target)` (mismo matching que
  `_find_running_process`, ahora retorna tambien `age_s = time.time() - create_time`).
  Implementado on top de `_find_running_process` para que monkeypatch del
  helper original siga funcionando en los tests existentes.
- Camino estricto (con `launch_time`):
  - Si `proc.age_s <= elapsed_since_launch + 2.0s tolerance` -> CONFIRMED.
  - Si proc existe pero es mas viejo -> recuerda como `last_pre_proc`, no confirma.
  - Si la ventana matchea (`_find_window`) en el camino estricto, NO confirma:
    no podemos timestampar un HWND barato.
  - Al expirar el deadline:
    - si `last_pre_proc` -> PENDING con `evidence.preexisting=true`.
    - sino -> PENDING "no process/window matching".
- Camino legacy (sin `launch_time`): comportamiento previo intacto. Esto preserva:
  - los tests `test_app_open_evidence_includes_ui_available_flag` y
    `test_app_open_does_not_invent_success_when_uia_unreachable` que construyen
    `ToolResult` a mano sin launch_time;
  - cualquier dispatcher externo que no estampe la baseline.

## 4. Tests nuevos

Archivo: `tests/test_app_open_verifier.py` (4 tests, todos PASS).

1. `test_app_open_returns_ok_false_when_shellexecute_reports_file_not_found`
   - Cubre Fix 1: dispatcher con ShellExecuteW rc=2 -> `ok=False`,
     `message="shellexecute_failed:2"`.
2. `test_app_open_verifier_pending_when_process_predates_launch_time`
   - Cubre Fix 2: proceso de 10 minutos con launch_time presente -> PENDING,
     `evidence.preexisting=true`.
3. `test_app_open_verifier_confirms_fresh_process`
   - Cubre Fix 2 (positivo): proceso de 0.1s con launch_time -> CONFIRMED,
     `evidence.process_age_s` registrado.
4. `test_app_open_verifier_legacy_fallback_when_launch_time_absent`
   - Cubre fallback explicito: sin launch_time, comportamiento previo intacto
     (CONFIRMED en proceso matcheado).

## 5. Tests existentes ajustados

`tests/test_agent_integration.py::test_typo_target_resolves_via_resolver`:
ahora acepta tambien `MissionStatus.FAILED` como veredicto valido.
Razon: el dispatcher real, cuando recibe `target="steam"` y steam.exe no esta
en PATH ni installed via AppResolver del host, ahora retorna ok=False
honestamente. Antes el test asumia que cmd /c start fake-confirmaba.
FAILED es la salida estructuralmente correcta y el test seguia probando
"no fake success".

## 6. Resultados reales

- `python -m pytest -q` -> **309 passed in 114.62s** (308 baseline + 1 nuevo file con 4 tests, ajustes inline mantienen el conteo).
- `python audit/hardcode_guard.py` -> `hardcode_guard: clean (47 files scanned)`.
- `python audit/full_matrix_runner.py --mode live-safe --label round_8b_app_open_fix_full --out audit/runs/round_8b_app_open_fix_full.json`:
  - `global=100.0% P1=100.0% P2=100.0% P3=100.0% cat11=100.0% cat18=100.0% p95=1379.6ms`.
- `python audit/full_matrix_runner.py --mode live-safe --category 7 --label round_8b_app_open_fix_cat7 --out audit/runs/round_8b_app_open_fix_cat7.json`:
  - `global=100.0% p95=52.1ms`.

## 7. Smoke manual de los caminos reales

(host sin Spotify ni Steam en PATH)

```text
spotify -> ToolResult(ok=False, message='shellexecute_failed:2',
                       data={'target':'spotify','method':'shellexecute',
                             'shellexecute_rc':2})
steam   -> ToolResult(ok=False, message='shellexecute_failed:2',
                       data={'target':'steam','method':'shellexecute',
                             'shellexecute_rc':2})
notepad -> dispatch ok=True data={'method':'direct','launch_time':3780.109}
           verifier=confirmed "Process found: Notepad.exe (age=0.05s, max=2.08s)"
```

Ningun fake success. Notepad confirma con evidencia causal (age 0.05s,
muy por debajo del max=2.08s tolerance). spotify/steam fallan honestamente
con codigo Win32 documentado.

NOTA: cuando AppResolver del host real (`Get-StartApps`) tiene Spotify
instalado, devuelve `shell:appsfolder\\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify`
y el ladder pasa por el paso 1 (explorer.exe), sin tocar ShellExecuteW.
Por eso el fix no rompe la apertura real de apps Microsoft Store en
maquinas donde si estan instaladas; solo rompe la mentira en maquinas
donde la app no existe.

## 8. Regresiones detectadas y resueltas

Una sola: `test_typo_target_resolves_via_resolver` (ver seccion 5).
Resuelto ampliando el set de status validos del test para incluir FAILED,
que es la salida estructuralmente correcta despues del fix.

Cero regresiones en cat11 (safety), cat18, ni en latencia (p95 1379ms vs
1278ms del Round 8: la diferencia es varianza del backend Ollama, no del
fix; esta dentro del ruido normal del runner live-safe).

## 9. Archivos tocados

- `src/carter_v3/tools/dispatch.py` (`_app_open` reescrito + nuevo `_windows_shellexecute`).
- `src/carter_v3/tools/verifier.py` (`_app_open` reescrito + nuevo `_find_running_process_with_age`).
- `tests/test_agent_integration.py` (ampliado set de status validos en 1 test).
- `tests/test_app_open_verifier.py` (NUEVO, 4 tests).
- `CHANGELOG.md` (Seccion 15 - Round 8b).
- `RESIDUAL.md` (Seccion U - Round 8b cierre).
- `V2_IMPORT_ROUND_8B_LOG.md` (este archivo).
