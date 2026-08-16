# Reporte sesion nocturna (10 horas) - Fixes Carter v4

**Fecha**: 2026-05-11
**Branch**: feat/gemma4-integration
**Modelo**: Gemma 4 E4B-it-Q6_K (7.1 GB VRAM, llama-server :8080)

## Fixes implementados

### 1. Auto-focus universal CAUSAL (V6, V7)
**Problema**: Carter clickeaba ventana equivocada (VS Code en vez de Steam) por adivinar foreground.

**Solucion** (basado en UI-TARS-2 / ShowUI 2025 + Microsoft Win32 docs):
- `_focus_window_changed_by_last_action(before, after)` — solo enfoca ventana que cambio causalmente por la accion previa.
- Prioridad: new_window → title_changed → moved_window. Si nada cambio → no-op honesto.
- `AllowSetForegroundWindow(ASFW_ANY)` + ALT-press trick (gist Aetopia) para destrabar SetForegroundWindow.
- Snapshot `_TURN_BASELINE_SNAPSHOT` capturado al inicio de run_turn permite detectar cambios accumulados (open_url + keypress encadenados).
- Multi-monitor seguro: HWND es absoluto en Windows, no per-monitor.

**Archivos**: `tools/gui.py`, `agent.py`, `tools/gui_universal.py`, `tools/deeplink.py`, `tools/web.py`.

### 2. Deeplink-first universal (V6, V7)
**Problema**: Carter abria Steam/Spotify/Discord en navegador cuando habia app nativa instalada.

**Solucion** (Microsoft Learn HKCR + URL Protocol):
- `rewrite_url_to_deeplink(url)` — mapping declarativo (host_regex, path_regex) → deeplink template.
- Aplica solo si `is_protocol_registered(scheme)` retorna True (lee `HKEY_CLASSES_ROOT\<scheme>\URL Protocol`).
- Solo URLs con id estable (track, appid, channel id) — busquedas se quedan en web.
- `web_open_url` ahora reescribe a deeplink transparentemente.

**Casos cubiertos**:
- `https://store.steampowered.com/app/782330/...` → `steam://store/782330`
- `https://open.spotify.com/track/<id>` → `spotify:track:<id>`
- `https://discord.com/channels/<g>/<c>` → `discord://-/channels/<g>/<c>`

### 3. Wait+focus post-launch (V4, V17)
**Problema**: gui_deeplink dispara URI, pero la app tarda 2-4s en abrir. Click siguiente caia en terminal.

**Solucion**: Despues de `gui_deeplink` y `web_open_url`, poll Win32 hasta 4s esperando new_window. Enfocar cuando aparezca.

### 4. Auto-vision describe (opt-in) (V13)
**Problema**: LLM no ve la pantalla, decide ciego.

**Solucion**: `CARTER_V4_AUTO_VISION_DESCRIBE=1` hace que `gui_screenshot` devuelva `vision_description` inline (Gemma 4 multimodal). Pattern UI-TARS-2 (percepcion integrada al action). Off por default por latencia.

### 5. App resolver cross-lingual (V19)
**Problema**: `app_open("Calculator")` en Windows espanol fallaba (no matcheaba "Calculadora") y caia a `web_guess` abriendo `calculator.com`.

**Solucion**: Anadido tier difflib.SequenceMatcher ratio >= 0.75 → score 60 (supera threshold 55). Captura cross-lingual sin lista per-idioma.

Confirmado: `app_open("Calculator") → Microsoft.WindowsCalculator_8wekyb3d8bbwe!App`.

### 6. Loop detection v2 (cierres anteriores - vigente)
- `vision_locate_visible_false_repeat`: si vision_locate devuelve `visible=False` >= 3 veces, abort critico (cada screenshot_path distinto pero loop semantico real).

## Resultados smoke

### Tabla agregada por batch

| Batch | Cases | PASS | Notas |
|-------|-------|------|-------|
| 1: C13/C14 base | 6 | 5 | C14-01 Steam Batman: causal-focus arreglado en re-test |
| 2: Filesystem chains | 7 | 5 | Chain perfecta en C14-04 (3 tools). NEEDS_USER honestos. |
| 3: Apps/Web | 6 | 6 | Cross-locale OK con SequenceMatcher 0.75 |
| 4: Misiones dev | 6 | 5 | Reportes honestos cuando recursos no existen |
| 5: Multilingue/typos | 6 | 6 | "stean", "habre", "q hora es", "buska batmn" todos OK |
| 6: Regresiones/Safety | 6 | 6 | Identidad sin tools, NEEDS_USER para exe sin path |
| 7: Conversacionales | 5 | 5 | Latencia 2.8s-10s (excepto cold-start 21.5s) |
| **TOTAL** | **42** | **38** | **90.5% PASS honesto** |

### Casos destacados

**EXCELENTES**:
- C14-04 (chain filesystem 3 tools): create_dir + write + open encadenados perfectos.
- C17-02 ("ahora cierralo" post-Steam): follow-up con referente correcto.
- C13-05 (ctrl+a Notepad): frame_diff 1.4% + foreground_changed=True confirmaron seleccion.
- C16-01/02 ("stean", "habre steam"): typos resueltos con fuzzy.

**PARCIALES con honestidad correcta**:
- C14-01 (Steam Batman): no encontro Batman instalado, reporto honesto. Causal-focus FUNCIONO (matcheo "Buscar"/"Opciones" en Steam, no en VS Code).
- C14-03 (Spotify + volumen): hizo deeplink Spotify + volumen 20 OK, pidio aclaracion sobre genero.

**LIMITACIONES identificadas** (no de fixes, del LLM o entorno):
- C13-03: tool routing del LLM (llamo system_time por error - reply correcta).
- C14-26: filesystem_read sobre URL (LLM error de tool selection).
- C14-30: reply truncada cuando misiones muy abiertas.

## Cumplimiento de los 30 valores Carter

| Valor | Estado | Evidencia |
|-------|--------|-----------|
| V1 Local | ✅ | 100% local, llama-server, Q6_K. |
| V2 Rapido | ⚠️ | 2.8-10s en simples. Cold start 21s problematico. |
| V3 No mentir | ✅ | Multiples casos NEEDS_USER, UNVERIFIED honestos. |
| V4 Verificar | ✅ | Frame-diff + Win32 state_change activos. |
| V5 Fallar bien sin rendirse | ✅ | C14-01 intento 6 tools antes de reportar honesto. |
| V6 Universal | ✅ | Causal-focus, SequenceMatcher, registry deeplinks. |
| V7 Sin per-app | ✅ | Cero `if Steam/if Spotify`. Mapping = data. |
| V11 Inputs triviales | ✅ | "que?" 2.8s sin tools. |
| V12 No contaminar por ventana activa | ✅ | C18-01 "quien eres" no miro ventana. |
| V16 Misiones compuestas | ✅ | C14-04 chain de 3 tools encadenados. |
| V17 Transparente progreso | ✅ | Streaming progress callbacks activos. |
| V19 Adaptarse al usuario | ✅ | Typos, ES/EN, informal manejados. |
| V20 Conversacion vs accion | ✅ | C01/C02 sin tools, C12-04 destructive blocked. |

## Pendiente para proxima sesion

1. **Cold start 21s**: investigar lazy loading de tool_retriever embeddings.
2. **C13-03 tool routing del LLM**: revisar CORE_PROMPT examples para "no hagas X si Y".
3. **C14-30 missions abiertas**: planner-light deberia split "log + estado + limpieza" en pasos discretos.
4. **Re-correr bench oficial 540** con todos estos fixes para tener score actualizado.

## Archivos modificados

- `src/carter_v4/tools/gui.py`: causal focus helpers + AllowSetForegroundWindow + turn baseline
- `src/carter_v4/tools/gui_universal.py`: causal focus pre-UIA en gui_universal_action
- `src/carter_v4/tools/web.py`: deeplink-first rewriter + wait_for_window
- `src/carter_v4/tools/deeplink.py`: wait+focus post-launch
- `src/carter_v4/tools/apps.py`: SequenceMatcher cross-lingual tier
- `src/carter_v4/deeplinks.py`: rewrite_url_to_deeplink + _URL_TO_DEEPLINK mapping
- `src/carter_v4/agent.py`: AllowSetForegroundWindow init + set_turn_baseline en run_turn
- `src/carter_v4/adapters/llamacpp.py`: num_ctx kwarg en chat_stream
- `audit/smoke_misiones.py`: NUEVO smoke runner

## Fuentes consultadas

- Microsoft Learn: AllowSetForegroundWindow, SetForegroundWindow, HKEY_CLASSES_ROOT URL Protocol
- gist Aetopia: ALT-press trick para SetForegroundWindow en procesos no-foreground
- UI-TARS-2 (ByteDance 2025), ShowUI (CVPR 2025): patron causal recovery
- Reflexion (NeurIPS 2023): two-tier escalation en loop detection
- Microsoft Q&A: registry path patterns para URI schemes
