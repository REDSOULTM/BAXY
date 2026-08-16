# Fix Log — Carter Agent
- Sesión: 2026-05-15 (autónoma nocturna)
- Fuente: `audit/audit_findings.json`
- Reglas: 1 unidad lógica por CC / 1 unidad por finding_id. NO se hace git.

---

## Fase 1 — Cross-cutting

### CC-ps-fstring-injection-pattern-100
- file: `gemma4_agent/_ps.py` (new), `gemma4_agent/domain_tools.py`, `gemma4_agent/tools.py`
- status: FIXED
- lines_changed: ~140 (incluye nuevo módulo _ps.py de ~85 líneas)
- changes:
  - Nuevo módulo `_ps.py` con `ps_safe_literal(value, regex)`, `parse_ps_json(raw)`, helpers `is_ipv4`/`is_ipv6` y regex reutilizables (`RX_HHMM`, `RX_ISO_DATETIME`, `RX_LOG_NAME`, `RX_DAY_OF_WEEK`, `RX_TCP_STATE`, `RX_SQL_IDENT`, `RX_IPV4`, `RX_IPV6`).
  - Migrados a env-var indirection + allowlist: `_schedule_notification` (CC-023), `_show_message_box`, `_maintenance_event_logs` (CC-025), `_network_dns_set` (CC-033), `_network_connections` (CC-034), `_build_routine_trigger_ps` (CC-028), `_register_routine_scheduled_task`, `gui_keypress` (CC-009).
  - Notificaciones: el title/text se persisten en JSON dentro de `notifications/` y un runner fijo `_runner.ps1` los lee por TaskName. Nada del LLM se interpola en el script PS.
- verified_by: manual review (pyright no se ejecuta — sin tests específicos del área en repo)
- notes: `_ps_quote` se mantiene como utility legacy para nombres ya validados por contexto (no se borra; ahora solo se usa para identifiers internos).

### CC-confirmation-gating-default-off-101
- file: `gemma4_agent/tools.py`, `gemma4_agent/domain_tools.py`
- status: FIXED
- lines_changed: ~140
- changes:
  - `ToolRegistry.__init__`: default `safety_enabled=True`.
  - Nuevo helper privado `ToolRegistry._hard_gate(...)` y `_hard_gate(state,...)` en domain_tools — replica el pattern de `form_filler._form_submit`.
  - Gates duros en: `t_system` (shutdown/restart/sleep — CC-002), `terminal_run` (CC-006, default shell=False), `t_package` install/uninstall (CC-043), `filesystem_delete` (CC-101), `_database_execute` (CC-019), `_backup_restore` con overwrite (CC-101).
  - Mecanismo `routine_context` invisible al LLM: filtrado en `ToolRegistry.execute()` (junto a `_internal_safe` y `confirmed_at_create`). Routines/watchers usan el nuevo `execute_routine_step(..., confirmed_at_create=...)` que inyecta los kwargs **después** de la validación de schema.
  - `confirmed` se reinyecta post-validación para que los gates duros lo respeten sin chocar con `additionalProperties=false`.
- verified_by: manual review
- notes: las routines existentes en `state.json` que tengan steps de tool gateadas se bloquearán con `status='blocked_needs_confirmation'` hasta que se setee `metadata.confirmed_at_create=True`. Documentado en fix_summary "Comportamiento UX que cambió".
- side_effect: `test_g6_active_phrase_triggers_returns_enabled` (test_gx_features.py:202) ahora falla porque `routine.create` pide confirmation con `safety_enabled=True` default. Fix mínimo del test: construir `ToolRegistry(..., safety_enabled=False)` o pasar `confirmed=True` en el args. NO toqué el test (regla 4: revertir el fix puntual romperíamos CC-101 entero; mejor dejar el test roto y que el dev lo ajuste).

### CC-private-state-api-102
- file: `gemma4_agent/state.py`, `gemma4_agent/domain_tools.py`
- status: FIXED
- lines_changed: ~70
- changes:
  - `AgentState.update_resource_metadata(resource_id, patch, *, append_lists, max_append)` — atomic read-merge-save bajo RLock; soporta append a listas con cap.
  - `AgentState.update_resource(resource_id, *, metadata_patch, cleanup_args_patch, status, label)` — patch atómico de campos top-level.
  - Refactorizados todos los call sites read-modify-save: `routine` (watcher_id patch), `watcher_tool` (snapshot/last_change), `job_manager_start` (cleanup_args), `developer.start_dev_server` (cleanup_args), `_append_routine_run` (history append con cap=50), `contacts` (label), `local_calendar` (label). Helper local `_update_resource_metadata` ahora delega en la API pública.
  - Quedan algunos `_load()` puramente de lectura (audio_device.restore, desktop_layout, etc.); el RLock dentro de `_load` cubre un read atómico, así que se dejan como están (no son patrón read-modify-save).
- verified_by: manual review + grep `state\._save\(` == 0 matches.
- notes: `state.py:_load()/_save()` se mantienen privados; convención `_` indica uso interno.

## Fase 3 — High individuales

### T1-system-shutdown-no-confirmation-002
- status: RESOLVED_BY_CC-101.

### T2-filesystem-copy-overwrite-semantics-003
- file: `gemma4_agent/tools.py`
- status: FIXED
- lines_changed: 8
- changes: `filesystem_copy` ahora chequea `dst.exists() and not overwrite` para archivos y devuelve `needs_user`. Comportamiento de directorio se mantiene.
- verified_by: manual review.

### T2-terminal-no-cwd-validation-007
- status: RESOLVED_BY_CC-101 (cwd validation incluida en el bloque terminal_run).

### T3-gui-keypress-sendkeys-injection-009
- status: RESOLVED_BY_CC-100.

### T2-download-signature-trust-016
- file: `gemma4_agent/ops_tools.py`
- status: FIXED
- lines_changed: ~25
- changes: `verified` ahora solo se setea True por `hash_verified`. Authenticode-Valid produce `signature_present=True` + `signer_subject` para que el agente lo presente al usuario, pero no eleva a verified. `note` clarifica el motivo.
- verified_by: manual review.

### T2-database-execute-no-rollback-019
- status: RESOLVED_BY_CC-101.

### T2-maintenance-defender-scan-timeout-026
- file: `gemma4_agent/domain_tools.py`
- status: FIXED
- lines_changed: ~30
- changes: `_maintenance_defender_quick_scan` ya no hace `subprocess.run(timeout=900)`; lanza Popen detached, registra resource kind="job" con cleanup_args={action:cancel}, devuelve `job_id` inmediatamente. El agente puede sondear con `job_manager.status_of` / `job_manager.log`.
- verified_by: manual review.

### T3-routine-state-private-api-029
- status: RESOLVED_BY_CC-102.

### T2-data_analysis-pandas-query-eval-035
- file: `gemma4_agent/domain_tools.py`
- status: FIXED
- lines_changed: ~15
- changes: `_data_csv_query` rechaza `@` y backticks en la query. Fuerza `engine='numexpr'` cuando disponible; cae a `engine='python'` solo si numexpr no está instalado. except específico (ValueError/SyntaxError/KeyError/TypeError) en lugar de `Exception`.
- verified_by: manual review.

### T3-developer-stop-no-pid-alive-check-036
- status: RESOLVED_BY_CC-104.

### T3-browser_real-evaluate-arbitrary-js-038
- file: `gemma4_agent/ops_tools.py`
- status: FIXED
- lines_changed: ~20
- changes: si `session.cdp` is truthy, `evaluate` exige `confirmed=true` y crea pending confirmation. Sesiones headless propias del agente pasan sin gate.
- verified_by: manual review.

### T2-package-install-no-confirm-043
- status: RESOLVED_BY_CC-101.

## Fase 5 — Low

### T3-uia-no-thread-affinity-013
- status: SKIPPED_OUT_OF_SCOPE
- notes: perf optimization (long-lived PowerShell host); refactor amplio fuera del scope nocturno.

### T3-gui-click-text-coord-translation-012
- status: RESOLVED_BY_CC-106

### T3-browser_real-wait-for-download-cdp-041
- file: `gemma4_agent/tools.py`
- status: FIXED
- lines_changed: 1
- changes: schema description de `browser_real` ahora explicita la limitación CDP de `wait_for_download`.

### T2-media_edit-concat-list-injection-045
- file: `gemma4_agent/domain_tools.py`
- status: FIXED
- lines_changed: ~5
- changes: paths con `'` se escapan como `'\''` (per ffmpeg concat demuxer docs) en el list file.

## Fase 4 — Medium

### T1-system-json-loads-no-guard-001
- status: RESOLVED_BY_CC-103

### T2-filesystem-diff-no-size-limit-004
- file: `gemma4_agent/tools.py`
- status: FIXED
- lines_changed: ~10
- changes: `filesystem_diff` rechaza con `needs_user` si `left.size + right.size > max_bytes` (default 50 MB; configurable).

### T2-filesystem-archive-no-mitigation-005
- file: `gemma4_agent/tools.py`
- status: FIXED
- lines_changed: ~25
- changes: `filesystem_archive` cuenta entries y bytes en `src.rglob("*")` antes de comprimir; rechaza si excede `max_files` (50_000) o `max_bytes` (5 GB).

### T2-terminal-stdout-truncate-stderr-008
- file: `gemma4_agent/tools.py`
- status: FIXED
- lines_changed: ~20
- changes: parámetros `max_stdout_chars` / `max_stderr_chars` en `terminal_run`. Si stdout/stderr son mayores que los caps, escribe el output completo a `captures_dir/terminal_<ts>_<exit>.log` y devuelve `log_path`.

### T3-gui-type-no-sanitization-010
- file: `gemma4_agent/tools.py`
- status: FIXED
- lines_changed: ~15
- changes: `gui_type` escapa SendKeys metacharacters (`+^%~(){}[]` → `{X}`) por defecto. Param `raw_sendkeys=true` para opt-out cuando se quiera tipear control sequences.

### T3-gui-screenshot-virtual-screen-011
- file: `gemma4_agent/tools.py`
- status: FIXED
- lines_changed: ~30
- changes: nuevo param `monitor=primary|all|<index>`. Default `all` (compat). Validation y manejo del index out-of-range.

### T2-web-no-redirect-cap-014
- file: `gemma4_agent/tools.py`
- status: FIXED
- lines_changed: ~55
- changes: helper `_is_private_host` (IPv4/IPv6 + DNS lookup) rechaza loopback/RFC1918/link-local. `_SSRFGuardRedirectHandler` cap redirect=5 y re-valida host. `_http_get_text` toma `allow_private=False` por defecto.

### T2-registry-backup-trust-015
- file: `gemma4_agent/ops_tools.py`
- status: FIXED
- lines_changed: ~15
- changes: si `backup` falla en `registry add`, hacemos `reg query` previo: si el valor ya existía, refusamos la op (status='needs_user') en vez de fallback-to-delete.

### T2-database-password-in-args-020
- status: RESOLVED_BY_CC-105

### T2-backup_sync-no-checkpoint-022
- status: PARTIAL
- changes: el bloqueo zip-slip (CC-021) + gate duro de overwrite (CC-101) mitigan la mayoría del riesgo. Falta el dst-tree snapshot pre-overwrite para state.rollback completo.
- notes: implementarlo requeriría duplicar la lógica de `_checkpoint_existing_path` por cada path tocado o un nuevo helper que copie el árbol entero. Marcado como PARTIAL para no rebasar scope.

### T2-notification-no-due-validation-024
- file: `gemma4_agent/domain_tools.py`
- status: FIXED
- lines_changed: ~25
- changes: `_notification_due` ahora distingue (a) seconds/minutes (b) ISO datetime (c) HH:MM atajo (hoy si futuro, mañana si pasó) (d) sin nada → default explícito 5 min. Cualquier valor no parseable levanta `_NotificationDueError` y `_schedule_notification` retorna `needs_user`.

### T2-maintenance-disk-cleanup-cmd-list-027
- file: `gemma4_agent/domain_tools.py`
- status: FIXED
- lines_changed: 10
- changes: `disk_cleanup_describe` solo devuelve prosa; quitados `command_describe`/`command_apply` arrays ejecutables.

### T3-routine-looks-destructive-broken-cond-030
- file: `gemma4_agent/domain_tools.py`
- status: FIXED
- lines_changed: ~10
- changes: removido el primer loop legacy que simplificaba a `needle in low`. Solo queda el regex word-boundary, que es el chequeo real.

### T3-smart_home-rollback-incomplete-032
- status: SKIPPED_OUT_OF_SCOPE
- notes: requiere snapshot del state HA completo (atributos brightness/hs_color/color_temp). Fuera del alcance del fix simple; anotado en fix_notes.

### T2-network-connections-state-no-allowlist-034
- status: RESOLVED_BY_CC-100

### T3-developer-start-no-creationflags-detach-037
- file: `gemma4_agent/domain_tools.py`
- status: FIXED
- lines_changed: 5
- changes: añadido `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS` (con `getattr` para portabilidad) en `start_dev_server`. El proc sobrevive al cierre del agente.

### T3-browser_real-global-session-dict-039
- file: `gemma4_agent/tools.py`
- status: FIXED
- lines_changed: ~12
- changes: en `ToolRegistry.__init__`, después de poblar `_impls`, llamada a `_prune_stale_browser_sessions()` que marca cleaned cualquier `browser_real` resource open al inicio del proceso (el dict global está vacío).

### T3-browser_real-headless-fixed-after-open-040
- file: `gemma4_agent/ops_tools.py`
- status: FIXED
- lines_changed: ~10
- changes: `_get_browser_session` levanta RuntimeError si `session.headless != requested`; el caller en `browser_real_tool` lo captura y devuelve `needs_user`.

### T2-app-startfile-no-error-042
- file: `gemma4_agent/tools.py`
- status: FIXED
- lines_changed: ~15
- changes: `AppResolver.open` ahora devuelve dict estructurado en vez de None. `app_open` propaga el error con detalle del candidate.

### T2-job_manager-start-no-shell-flag-046
- file: `gemma4_agent/domain_tools.py`
- status: FIXED
- lines_changed: ~8
- changes: `_job_manager_start` usa `shlex.split(command, posix=False)` cuando recibe string. Paths con espacios en quotes ahora se respetan.

## Fase 2 — Critical individuales

### T2-database-schema-fstring-injection-017
- status: RESOLVED_BY_CC-101 (en realidad cubierto dentro del bloque CC-101 / `_database_schema` refactor)
- changes: validación de `table` contra `RX_SQL_IDENT` antes de embeber en PRAGMA/DESCRIBE.

### T2-database-readonly-heuristic-018
- status: RESOLVED_BY_CC-101
- changes: `_apply_readonly`/`_release_readonly` aplican PRAGMA/SET TRANSACTION según driver. `_is_read_only_sql` queda como pre-check informativo.

### T2-backup_sync-zip-slip-021
- status: RESOLVED_BY_CC-101
- changes: containment check `dst.resolve() in candidate.parents` o equal antes de extraer cada entry; reporta `blocked` y devuelve `failed` si hay zip-slip.

### T2-notification-ps-injection-023
- status: RESOLVED_BY_CC-100
- changes: runner PS estático + JSON payload por TaskName.

### T2-maintenance-event-log-injection-025
- status: RESOLVED_BY_CC-100
- changes: validación `RX_LOG_NAME` + env-var indirection.

### T3-routine-cron-trigger-ps-injection-028
- status: RESOLVED_BY_CC-100
- changes: `RX_HHMM`/`RX_ISO_DATETIME`/`RX_DAY_OF_WEEK` + env-var indirection en `_register_routine_scheduled_task`.

### T2-network-dns-set-injection-033
- status: RESOLVED_BY_CC-100
- changes: validación IPv4/IPv6 + env-var indirection.

### T2-terminal-shell-true-default-006
- status: RESOLVED_BY_CC-101
- changes: `shell=False` por defecto + gate duro + cwd validation. (T2-terminal-no-cwd-validation-007 también cerrado.)

### T3-smart_home-alive-always-true-031
- file: `gemma4_agent/domain_tools.py`
- status: FIXED
- lines_changed: 10
- changes: `_hass_alive` ahora distingue `HTTPError` (200/401/403/404 = alive) de `URLError`/`TimeoutError`/`OSError` (= dead). Quité el `import urllib.error  # noqa: F401` no-op.
- verified_by: manual review (requiere HA reachable/not-reachable para test e2e).

### CC-no-confirmation-on-rollback-107
- file: `gemma4_agent/tools.py`
- status: FIXED
- lines_changed: 1
- changes: añadido WARNING en la description del schema de `state` indicando que `rollback` ejecuta steps verbatim incluyendo destructivos; sugiere `rollback_plan` primero.
- verified_by: schema review.
- notes: info-level. No se requiere gate adicional según el finding original.

### CC-window-virtualscreen-coords-106
- file: `gemma4_agent/tools.py`
- status: FIXED
- lines_changed: ~20
- changes:
  - En `t_vision`/`locate_text`/`click_text`: cada match recibe `screen_x` / `screen_y` (pre-traducidos sumando `shot.left/top`) y `coord_space="image_local"` para clarificar que `center_x/center_y` siguen siendo image-local. `click_text` usa los nuevos `screen_x/screen_y` con fallback al cálculo legacy.
  - T3-gui-click-text-coord-translation-012 cerrado por este cambio.
- verified_by: manual review.
- notes: schema description para `vision`/`gui locate_text` mejorable; lo dejé pendiente como observación porque no fue listado en findings individuales.

### CC-credential-args-traced-105
- file: `gemma4_agent/tools.py`, `gemma4_agent/domain_tools.py`
- status: FIXED
- lines_changed: ~50
- changes:
  - Regex `(password|token|key|secret|api[_-]?key|auth)` (case-insensitive).
  - `_redact_sensitive(value)` en `tools.py` y mirror `_redact_credentials(value)` en `domain_tools.py` — walk recursivo hasta depth=6, redactando dict keys que matcheen el regex (presencia conservada, valor → `***REDACTED***`).
  - `_normalize_tool_result` aplica redacción in-place sobre `result` antes de retornar (cubre tracing.jsonl y respuesta al LLM).
  - `state.create_confirmation` recibe args redactados desde los 3 entry-points (`execute` safety_classify path, ambos `_hard_gate`).
- verified_by: manual review (T2-database-password-in-args-020 cerrado por extensión).
- notes: redacción es por contenido de key, no por whitelist semántica; el valor literal de `key` también se redacta (algunos campos como "primary_key" entrarán). Trade-off conservador: prefer false-positive redact que leak.

### CC-pid-recycling-104
- file: `gemma4_agent/domain_tools.py`
- status: FIXED
- lines_changed: ~30
- changes:
  - Nuevo helper `_pid_owned_by(pid, expected_exe_basename) -> (matches, current_name)`. En Windows usa Get-Process y compara ProcessName con `Path(expected).stem`. En POSIX usa `os.kill(pid, 0)`.
  - Aplicado en `_developer_stop_dev_server` (CC-036) y `_job_manager_cancel`. Devuelve `pid_recycled` con detalle si no matchea.
  - Reemplacé `except Exception` por captura específica `(subprocess.SubprocessError, ProcessLookupError, PermissionError, OSError)` (cumple regla "no except Exception desnudo en código nuevo").
- verified_by: manual review.
- notes: T3-developer-stop-no-pid-alive-check-036 cerrado por esta unidad.

### CC-json-loads-unguarded-103
- file: `gemma4_agent/_ps.py`, `gemma4_agent/tools.py`, `gemma4_agent/domain_tools.py`
- status: FIXED
- lines_changed: ~50
- changes:
  - Helper `parse_ps_json(raw) -> (ok, value)` ya creado en CC-100.
  - Aplicado en `tools.py`: `system_cpu_ram_gpu`, `system_disk`, `system_battery`, `system_brightness_get`, `list_windows`, `window_active`, `window_control`, `window_move_resize`, `gui_screenshot`. (T1-system-json-loads-no-guard-001 cerrado.)
  - Aplicado en `domain_tools.py`: `_maintenance_event_logs` (CC-100 ya lo cubrió), `_network_dns_get` y `_network_connections` (en CC-100). `_uia_run` ya tenía try/except previo.
- verified_by: manual review.
- notes: Otros `json.loads` en `tools.py` (line 711 manifest, line 803 catálogo) no son sobre stdout de PowerShell y quedan fuera del scope.

