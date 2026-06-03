# Mapa de descomposición — archivos-dios (2026-06-01)

Continúa la auditoría arquitectural (commit a18dc63) y la serie R1–R8. Las extracciones
**seguras** ya se hicieron (R2 dejó 38 módulos hermanos en `domain_tools/`). Lo que queda
en los archivos-dios es lo **mock-acoplado / disperso / de clase**, que exige extracción
**supervisada** (no se hace de noche a ciegas: romper audio/whatsapp no se atrapa con los
tests actuales y no se puede probar físicamente sin cerrar VS Code).

## Estado (LOC producción)

| archivo | LOC | naturaleza | riesgo de partir |
|---|---|---|---|
| `tools_pkg/tools.py` | 7.6k | **clase** `ToolRegistry` con métodos `t_*` + workers PowerShell | ALTO (métodos de clase, no funciones-módulo → mixin/delegación) |
| `agent_core/agent.py` | 6.4k | el agente (run_content ya partido en 3 fases R1) | ALTO (núcleo; cada fase cruza estado) |
| `domain_tools/__init__.py` | 4.5k | media/streaming + whatsapp + audio-devices | MEDIO (patrón sibling+shim ya existe) |
| `tools_pkg/ops_tools.py` | 2.2k | OCR + screenshot + helpers | MEDIO |

## Áreas extraíbles de `domain_tools/__init__.py` (con el patrón R2)

Patrón R2: crear `domain_tools/<area>.py`, mover las funcs, en `__init__.py` dejar
`from .<area> import *` (shim de back-compat), lazy-import de helpers cross-area
(`_ok/_err/_text/_load/_find_soundvolumeview` viven en `helpers.py`/R3).

1. **audio_devices** (~300 LOC, líneas ~86-230 + ~4192-4488): `audio_device_tool`,
   `_set_default_audio_device`, `_restore_audio_default`, `_svv_*` (SoundVolumeView),
   `_audio_endpoints`, `_audio_rollback_steps`, `_audio_verify_default`,
   `_run_detached_powershell`. **NO mock-acoplado** (verificado: ningún test patchea sus
   internos). Riesgo: está **disperso** (86-230 y 4192-4488) y usa helpers cross-area →
   mover junto + lazy-import de helpers. **Mejor candidato siguiente**, pero requiere
   prueba de audio real (física) que solo corre el usuario.
2. **media/streaming** (~1900 LOC, ~628-2918): VLC/Spotify/CDP/`media_tool`.
   **Mock-acoplado** (`test_spotify_*` patchea `_launch_streaming`, `_spotify_auto_play`,
   `_verify_visible_whatsapp_text_status`…) → actualizar los `mock.patch` targets al
   nuevo módulo. R2 lo saltó por costo > beneficio.
3. **whatsapp** (~1300 LOC, ~2919-4191): `whatsapp_tool` + verificadores de header GUI.
   **Mock-acoplado** (`test_whatsapp` patchea `_find_whatsapp_app`, `_verify_chat_header_status`…).

## Regla (enforced por `test_god_object_size_ceiling.py`)

Los 4 archivos-dios **no deben crecer**: para agregar funcionalidad, extraé un hermano
(R2), no engrosá el dios. El guard pone un techo con buffer chico de mantenimiento; si lo
superás, la respuesta es **partir**, no subir el techo. Quitar de un dios es la dirección
correcta (R-series); el techo solo evita la regresión.

## NO hacer de noche / sin supervisión
- Mover media/whatsapp sin actualizar los `mock.patch` targets (rompe la suite).
- Mover audio sin que el usuario pruebe el switch de dispositivo real.
- Cualquier `git checkout/restore/stash` (el harness los bloquea — incidente R2). Usar
  Write/Edit + `git add` + commit; para revertir, `git show HEAD:<file>` + Write.
