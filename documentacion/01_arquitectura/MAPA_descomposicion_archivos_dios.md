# Mapa de descomposición — archivos-dios (2026-06-01, **act. 2026-06-09**)

Continúa la auditoría arquitectural (commit a18dc63) y la serie R1–R8. Las extracciones
**seguras** ya se hicieron (R2 dejó 38 módulos hermanos en `domain_tools/`). Lo que queda
en los archivos-dios es lo **mock-acoplado / disperso / de clase**, que exige extracción
**supervisada** (no se hace de noche a ciegas: romper audio/whatsapp no se atrapa con los
tests actuales y no se puede probar físicamente sin cerrar VS Code).

## Extracciones nuevas (2026-06-07 → 2026-06-09) — ✅ HECHAS

Cada feature reciente que habría engrosado un dios se extrajo a un hermano (el ratchet lo
fuerza). Módulos NUEVOS:

| Módulo hermano | Extraído de | Qué | Commit |
|----------------|-------------|-----|--------|
| `agent_core/agent_helpers.py` | `agent.py` | helpers libres del agente | `e2b7c79` |
| `tools_pkg/site_resolver.py` | `tools.py` | resolución de sitios "ve a X" | `1cae3b1` |
| `tools_pkg/vision_describe.py` | `tools.py` | describe_screen con ancla OCR | tanda visión |
| `tools_pkg/web_search.py` | `tools.py` | scrapers DDG/Bing + selector de proveedor | `808df2a` |
| `tools_pkg/web_source_quality.py` | `tools.py` | calidad de fuentes (foro vs estándar) | `808df2a` |
| `tools_pkg/visual_click_redirect.py` | `tools.py` | redirección click-visual → gui | `808df2a` |
| `agent_core/reply_repair.py` | `agent.py` | reparación de idioma + info-followup + observación de media | `808df2a` |
| `domain_tools/media_current.py` | `domain_tools/__init__.py` | resume del video/media actual | `808df2a` |
| `tools_pkg/steam_store.py` | `tools.py` | helpers de Steam (AppID/URIs/store search) | 2026-06-10 |
| `domain_tools/audio_devices.py` | `domain_tools/__init__.py` | dispositivos de audio (endpoints, set/restore default, SoundVolumeView) | 2026-06-10 |

**Consolidación 2026-06-10:** dos extracciones limpias (contiguas, sin ciclo, con
tests verdes) bajaron los techos de verdad: `tools.py` 8060→8023 (-42, Steam) y
`domain_tools/__init__.py` 3370→3070 (-300, audio). Ambas con el patrón sibling+shim;
audio importa `_ok/_err` de `_shared` y `_find_soundvolumeview/_powershell_json` de
`helpers` (no de `__init__`), evitando el ciclo. El alias back-compat
`gemma4_agent.domain_tools_audio_devices` se registró en `__init__._alias_domain_tools_shims`.

**Caveat honesto (deuda registrada):** `agent.py` subió su techo +296 LOC (en el comentario
de `CEILINGS` de `test_god_object_size_ceiling.py`) por un bloque INLINE **irreducible**: el
prefetch de info-followup (~94 LOC que muta los locales del loop del turno — `events`,
`verifier_outcomes`, `mission_goal`, `selected_*`, `mode` — sin frontera de función limpia).
Lo extraíble se extrajo a `reply_repair.py`; ese bloque queda cableado al hot-path. Mismo
patrón que los bumps previos documentados en el comentario del techo.

## Estado (LOC producción, **medido 2026-06-09**)

| archivo | LOC | naturaleza | riesgo de partir |
|---|---|---|---|
| `tools_pkg/tools.py` | ~8.0k | **clase** `ToolRegistry` con métodos `t_*` + workers PowerShell | ALTO (métodos de clase, no funciones-módulo → mixin/delegación) |
| `agent_core/agent.py` | ~7.3k | el agente (run_content ya partido en 3 fases R1) | ALTO (núcleo; cada fase cruza estado) |
| `domain_tools/__init__.py` | ~3.3k | media/streaming + whatsapp + audio-devices (bajó tras extraer `media_current.py`) | MEDIO (patrón sibling+shim ya existe) |
| `tools_pkg/ops_tools.py` | ~2.3k | OCR + screenshot + helpers | MEDIO |

> Nota: las cifras crecen y bajan con cada feature/extracción; el número exacto que
> importa es el **techo** en `test_god_object_size_ceiling.py` (la verdad enforced).
> `domain_tools` bajó (3.3k) tras extraer `media_current.py`; `tools.py` se mantuvo
> bajo techo extrayendo `web_search`/`web_source_quality`/`visual_click_redirect`.

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
