# Round 8b - app_open fake success (BLOQUEANTE - hacer antes que Round 8)

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

PRIORIDAD: CRITICA. Este bug viola directamente R4 (cero fake success)
y el Valor 4 de ContextoCarter.md.

OBJETIVO DE ESTA RONDA
Corregir el bug de fake success en `app_open` observado en vivo:

  Usuario: "abre spotify"
  Carter:  [complete / all_tools_confirmed] Abri spotify y lo verifique.
  Realidad: Windows mostro dialogo "no puede encontrar el archivo spotify"

ANTES DE TOCAR NADA, LEE:
- `ContextoCarter.md`
- `Carter_v3/CHANGELOG.md`
- `Carter_v3/RESIDUAL.md`
- `Carter_v3/src/carter_v3/tools/dispatch.py`  (metodo _app_open, linea ~245)
- `Carter_v3/src/carter_v3/tools/verifier.py`  (metodo _app_open, linea ~121)
- `Carter_v3/src/carter_v3/perception/app_resolver.py`
- `Carter_v3/tests/test_agent_integration.py`

TRAZABILIDAD
Crea:
- `Carter_v3/V2_IMPORT_ROUND_8B_LOG.md`

DIAGNOSTICO EXACTO DEL BUG
Hay dos fallos compuestos que producen el fake success:

FALLO 1 — Dispatcher retorna ok=True aunque el launch fallo:
- El ladder de `_app_open` en dispatch.py llega al paso 3:
  `subprocess.Popen(["cmd", "/c", "start", "", "spotify"], ...)`.
- `cmd /c start "" spotify` siempre retorna exit code 0 aunque el
  archivo no exista. Windows muestra el dialogo de error al usuario,
  pero el proceso `cmd.exe` termino exitosamente desde la perspectiva
  de Popen.
- Resultado: dispatch retorna `ToolResult(ok=True, method="windows_start")`.

FALLO 2 — Verifier confirma un proceso que ya estaba corriendo antes:
- `_app_open` en verifier.py busca un proceso que matchee "spotify".
- Si Spotify ya estaba corriendo antes del comando (proceso vivo), el
  verifier encuentra ese proceso y retorna CONFIRMED aunque Carter no
  lo abrio ahora.
- Resultado: `all_tools_confirmed` aunque el launch fallara.

MISION
Cerrar ambos fallos. El contrato final debe ser:
- Si `cmd /c start` falla (el archivo no existe), Carter debe retornar
  `ok=False` o `mission_status=unverified/failed`, nunca `complete`.
- El verifier de `app_open` solo confirma CONFIRMED si el proceso/ventana
  aparecio DESPUES del dispatch, o si hay evidencia causal directa.
  Un proceso preexistente no es evidencia de exito del launch actual.

DISENO DEL FIX

Fix 1 — Dispatcher (dispatch.py _app_open):
Para el paso `cmd /c start`, no se puede confiar en el exit code.
Alternativas ordenadas por preferencia:
  (a) Usar `ShellExecuteEx` via `ctypes` o `win32api` que retorna
      error real cuando el archivo no existe. Es la API correcta para
      esto en Windows.
  (b) Registrar el timestamp justo antes del launch y pasarlo en
      `ToolResult.data` para que el verifier lo use como baseline
      temporal (el proceso debe haber aparecido DESPUES de ese timestamp).
  (c) Si el target no tiene extension y no se encuentra en PATH,
      retornar ok=False antes de intentar `cmd /c start` para targets
      que claramente no son ejecutables ni URIs.
Elige el enfoque mas defensible. Puede ser una combinacion.

Fix 2 — Verifier (verifier.py _app_open):
- El verifier debe recibir un `launch_time` del ToolResult.data
  (timestamp monotonic puesto por el dispatcher justo antes del Popen).
- Solo cuenta como CONFIRMED si el proceso aparecio con
  `create_time >= launch_time - tolerancia_s`.
- Si el proceso existia antes del launch, el resultado es PENDING
  (no se puede atribuir causalmente a este comando).
- Fallback cuando no hay `launch_time`: comportamiento actual (PENDING,
  no CONFIRMED).

REGLAS
- No cambiar los contratos publicos (mission_status, VerifiedOutcome, etc.).
- No agregar tools al catalogo.
- No hardcodes de nombre de app.
- El fix debe funcionar para steam, spotify, discord y cualquier app
  sin necesidad de entrada especifica por app.
- Si en un caso el fix introduce regresiones en apps que si funcionaban
  (ej. steam.exe en PATH), el fix debe ser mas quirurgico, no mas agresivo.

CASOS DE PRUEBA OBLIGATORIOS
Agrega tests en `tests/test_agent_integration.py` o en un nuevo
`tests/test_app_open_verifier.py` que cubran:
1. App que no existe: dispatch retorna ok=False o verifier retorna PENDING/FAILED.
2. App preexistente (proceso ya corria): verifier retorna PENDING, no CONFIRMED.
3. App que si se lanza con exito: verifier retorna CONFIRMED (proceso nuevo
   aparece despues del launch_time).

VALIDACION
- `python -m pytest -q`
- `python audit/hardcode_guard.py`
- `python audit/full_matrix_runner.py --mode live-safe --label round_8b_app_open_fix_full --out audit/runs/round_8b_app_open_fix_full.json`
- `python audit/full_matrix_runner.py --mode live-safe --category 7 --label round_8b_app_open_fix_cat7 --out audit/runs/round_8b_app_open_fix_cat7.json`

Despues de los tests, prueba manualmente:
- `python -m carter_v3.cli.launcher --once "abre spotify"` cuando
  spotify NO esta en PATH -> debe retornar unverified o failed, no complete.
- `python -m carter_v3.cli.launcher --once "abre steam"` cuando
  steam.exe SI existe -> debe retornar complete con CONFIRMED real.

ENTREGA
1. Diagnostico exacto de los dos fallos (confirmado en codigo)
2. Que cambiaste en dispatch.py y por que
3. Que cambiaste en verifier.py y por que
4. Tests nuevos que prueban los contratos correctos
5. Resultados reales de runners y prueba manual
6. Si hubo regresiones, cuales y como las resolviste
7. Updates en `CHANGELOG.md`, `RESIDUAL.md`, `V2_IMPORT_ROUND_8B_LOG.md`
```
