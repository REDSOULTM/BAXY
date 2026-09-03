# Comando C01 — conductor sin ventana

No es un ejemplo pendiente: `ProductConductorHost` arranca `MainWindowViewModel`
sin `MainWindow`/`WebView2` y habla con `FieldProductChannel`, el mismo
controlador que `FieldUiBridge` usa tras la política de origen.

## Arranque

Desde la raíz del repositorio, con el runtime registrado:

```powershell
py main.py --conductor --turns-file artifacts\comprobaciones\C01\launch.turns.jsonl --capture artifacts\comprobaciones\C01\launch-1 --timeout-ms 180000
```

Equivalente directo:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_baxy_conductor.ps1 `
  -TurnsFile artifacts\comprobaciones\C01\launch.turns.jsonl `
  -Capture artifacts\comprobaciones\C01\launch-1 `
  -TimeoutMs 180000
```

R01–R06 (una sesión persistente, sin limpiar pendientes entre turnos):

```powershell
py main.py --conductor --turns-file artifacts\comprobaciones\C01\r01-r06.turns.jsonl --capture artifacts\comprobaciones\C01\r01-r06 --timeout-ms 180000
```

## Qué hace

1. Compila si hace falta (`py main.py`) y cierra una ventana de desarrollo previa.
2. Configura el perfil persistente `%LOCALAPPDATA%\BAXY\comprobaciones-c01` al
   arrancar. No lo vacía entre turnos.
3. Lanza `Baxy.exe --conductor` sin crear la ventana de producto y **espera**
   a que el proceso WinExe termine (`WaitForExit`). `& Baxy.exe` no espera.
4. Adjunta manifiesto `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json`, commit y
   variables de runtime en el evento `meta`.
5. Envía el texto público (o `session.new` / `upload` / `cancelar`) por el canal
   compartido. BAXY no recibe operación esperada ni veredicto.
6. Emite JSONL: `meta`, `admission`, `event` (proyección pública), `terminal`,
   `posterior`. `status=accepted` no se cuenta como respuesta final.

## Terminales honestos

| `terminal.kind` | Significado |
|---|---|
| `published_final` | Hubo actividad BAXY pública y el turno se asentó |
| `filtered` | Descarte de publicación o composición rechazada sin texto visible |
| `accepted_without_final` | Admisión sin respuesta final publicada |
| `silence` | Timeout sin final visible; no se inventa salida |
| `rejected` | Admisión rechazada (vacío, no listo, adjunto, etc.) |
| `blocked_environment` | Runtime no listo u otra instancia ya posee el escritorio |

El conductor no repara la sesión ni borra planes pendientes.
