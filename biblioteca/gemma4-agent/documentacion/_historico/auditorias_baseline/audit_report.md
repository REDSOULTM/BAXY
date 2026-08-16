# Carter Agent — Auditoría Integral de Tools

- **Proyecto**: gemma4-agent
- **Fecha**: 2026-05-15
- **Auditor**: claude-opus-4-7 (lectura estática, sin ejecución)
- **Repo commit**: `ca998319f9d7b29c16ce9031601b2c9a4527ad85` (rama `feat/ui-field-react`)
- **Tools en catálogo**: 62 (COMPOUND_TOOL_SCHEMAS en `gemma4_agent/tools.py:3029`)
- **Tools auditadas individualmente**: 57 (algunas entradas del schema son alias del mismo dispatcher; ver criterio abajo)

## Criterio de inclusión

Se consideró “tool” cada entrada con un schema en `COMPOUND_TOOL_SCHEMAS` y un dispatcher en `ToolRegistry._impls`. Las funciones "atómicas" registradas en `_impls` (p.ej. `system_time`, `list_processes`, `gui_click`) están alcanzadas por sus tools compound (`system`, `gui`, etc.) y se auditan dentro de ellas, no como entradas separadas.

## Resumen ejecutivo

- **Por tier**: T1=16, T2=28, T3=18 (total 62 — algunas duplicaciones de alias en el dispatcher quedan cubiertas por su compound).
- **Por severidad**: 11 critical, 14 high, 22 medium, 5 low, 4 info.
- **Por status**: 35 PASS, 22 NEEDS_FIXES, 0 BROKEN.

Hallazgos transversales graves dominan el panorama: la arquitectura de seguridad existe (`state.create_confirmation`, `_DESTRUCTIVE_COMMAND_TOKENS`, `_looks_destructive`, gate de `form_filler.submit`) pero **no se aplica uniformemente**. Por defecto `ToolRegistry(safety_enabled=False)` y muchos tools destructivos saltan la verificación. En paralelo, una familia recurrente de bugs de interpolación f-string en scripts PowerShell expone PowerShell injection en seis tools.

## Dashboard

| Tool | Tier | Status | C | H | M | L |
|---|---|---|---|---|---|---|
| system | T1 | NEEDS_FIXES | 0 | 1 | 1 | 0 |
| filesystem | T2 | NEEDS_FIXES | 0 | 1 | 2 | 0 |
| terminal | T2 | NEEDS_FIXES | 1 | 1 | 1 | 0 |
| gui | T3 | NEEDS_FIXES | 0 | 1 | 2 | 1 |
| uia | T3 | NEEDS_FIXES | 0 | 0 | 0 | 1 |
| web | T2 | NEEDS_FIXES | 0 | 0 | 1 | 0 |
| registry | T2 | NEEDS_FIXES | 0 | 0 | 1 | 0 |
| download | T2 | NEEDS_FIXES | 0 | 1 | 0 | 0 |
| database | T2 | NEEDS_FIXES | 2 | 1 | 1 | 0 |
| backup_sync | T2 | NEEDS_FIXES | 1 | 0 | 1 | 0 |
| notification | T2 | NEEDS_FIXES | 1 | 0 | 1 | 0 |
| maintenance | T2 | NEEDS_FIXES | 1 | 1 | 1 | 0 |
| routine | T3 | NEEDS_FIXES | 1 | 1 | 1 | 0 |
| smart_home | T3 | NEEDS_FIXES | 1 | 0 | 1 | 0 |
| network | T2 | NEEDS_FIXES | 1 | 0 | 1 | 0 |
| data_analysis | T2 | NEEDS_FIXES | 0 | 1 | 0 | 0 |
| developer | T3 | NEEDS_FIXES | 0 | 1 | 1 | 0 |
| browser_real | T3 | NEEDS_FIXES | 0 | 1 | 2 | 1 |
| app | T2 | NEEDS_FIXES | 0 | 0 | 1 | 0 |
| package | T2 | NEEDS_FIXES | 0 | 1 | 0 | 0 |
| media_edit | T2 | NEEDS_FIXES | 0 | 0 | 0 | 1 |
| job_manager | T2 | NEEDS_FIXES | 0 | 0 | 1 | 0 |
| audio_device | T2 | PASS | 0 | 0 | 0 | 0 |
| office | T2 | PASS | 0 | 0 | 0 | 0 |
| photo_library | T2 | PASS | 0 | 0 | 0 | 0 |
| container | T2 | PASS | 0 | 0 | 0 | 0 |
| device_settings | T2 | PASS | 0 | 0 | 0 | 0 |
| media (now_playing/local/vlc) | T3 | PASS | 0 | 0 | 0 | 0 |
| game_launcher | T2 | PASS | 0 | 0 | 0 | 0 |
| watcher | T2 | PASS | 0 | 0 | 0 | 0 |
| printer_scanner | T2 | PASS | 0 | 0 | 0 | 0 |
| desktop_layout | T2 | PASS | 0 | 0 | 0 | 0 |
| document | T2 | PASS | 0 | 0 | 0 | 0 |
| peripheral | T3 | PASS | 0 | 0 | 0 | 0 |
| accessibility | T3 | PASS | 0 | 0 | 0 | 0 |
| creative_local | T3 | PASS | 0 | 0 | 0 | 0 |
| form_filler | T3 | PASS (template) | 0 | 0 | 0 | 0 |
| subagent | T3 | PASS | 0 | 0 | 0 | 0 |
| study | T1 | PASS | 0 | 0 | 0 | 0 |
| fact_check | T1 | PASS | 0 | 0 | 0 | 0 |
| knowledge | T1 | PASS | 0 | 0 | 0 | 0 |
| state | T1 | PASS | 0 | 0 | 0 | 0 |
| safety | T1 | PASS (con caveat) | 0 | 0 | 0 | 0 |
| source_manager | T1 | PASS | 0 | 0 | 0 | 0 |
| contacts | T1 | PASS | 0 | 0 | 0 | 0 |
| notes_tasks | T1 | PASS | 0 | 0 | 0 | 0 |
| local_calendar | T1 | PASS | 0 | 0 | 0 | 0 |
| habit_tracker | T1 | PASS | 0 | 0 | 0 | 0 |
| local_search | T1 | PASS | 0 | 0 | 0 | 0 |
| dependency | T1 | PASS | 0 | 0 | 0 | 0 |
| verify | T1 | PASS | 0 | 0 | 0 | 0 |
| memory | T1 | PASS | 0 | 0 | 0 | 0 |
| input | T2 | PASS | 0 | 0 | 0 | 0 |
| env | T2 | PASS | 0 | 0 | 0 | 0 |
| email | T2 | PASS | 0 | 0 | 0 | 0 |
| reminder | T2 | PASS | 0 | 0 | 0 | 0 |

---

## Hallazgos por tool

### system  [TIER: T1]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/tools.py:1248`
**Signature**: `t_system(self, args: dict[str, Any]) -> dict[str, Any]`
**Resumen**: Tool agregadora de info de sistema (CPU/disco/batería/brillo) + acciones destructivas no gateadas (shutdown/restart/sleep).

#### Hallazgos
- [HIGH] **shutdown/restart/sleep actions execute without confirmation gate when safety disabled**
  - Ubicación: `gemma4_agent/tools.py:1264-1269`
  - Descripción: las acciones `shutdown`, `restart`, `sleep` despachan directo a `terminal_run` (que usa `shell=True`) sin pasar por el clasificador de seguridad. Con `safety_enabled=False` (default), un solo tool call apaga la máquina del usuario.
  - Fix sugerido: forzar `state.create_confirmation` para estas tres acciones independientemente de `safety_enabled`, mismo patrón que `form_filler.submit`.
- [MEDIUM] **json.loads() on PowerShell stdout without try/except**
  - Ubicación: `gemma4_agent/tools.py:1997-2025`
  - Descripción: `system_cpu_ram_gpu`, `system_disk`, `system_battery`, `system_brightness_get` parsean `proc.stdout` con `json.loads()` directo. Si PS imprime un warning antes del JSON (locale, error CIM), explota con `JSONDecodeError` y el registry sólo surface 'JSONDecodeError:' al LLM.
  - Fix sugerido: reusar `_powershell_json` (`domain_tools.py:7205`) o `_json_or_text` (`ops_tools.py:1102`).

---

### filesystem  [TIER: T2]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/tools.py:1678`
**Signature**: `t_filesystem(self, args: dict[str, Any]) -> dict[str, Any]`
**Resumen**: I/O de archivos con checkpoint/rollback para mutaciones. Diff/archive sin caps de tamaño y overwrite semántica inconsistente.

#### Hallazgos
- [HIGH] **filesystem_copy overwrite flag not honored for files**
  - Ubicación: `gemma4_agent/tools.py:2414-2425`
  - Descripción: `shutil.copy2` no respeta `overwrite=False` en copia de archivo; sólo el path de directorio respeta `dirs_exist_ok`.
  - Impacto: el usuario pide "copia sin sobrescribir" y bar es silenciosamente reemplazado. Hay checkpoint con backup, pero la semántica reportada al LLM es engañosa.
  - Fix sugerido: chequear `dst.exists() and not overwrite` y devolver `needs_user`.
- [MEDIUM] **filesystem_diff loads both files entirely into memory without size guard**
  - Ubicación: `gemma4_agent/tools.py:2465-2473`
  - Fix sugerido: chequear suma de tamaños > 50MB y devolver `needs_user`.
- [MEDIUM] **filesystem_archive walks src.rglob('*') without max entries / max size cap**
  - Ubicación: `gemma4_agent/tools.py:2475-2489`
  - Fix sugerido: agregar `max_files` (50k) y `max_bytes` (5GB); rechazar temprano.

---

### terminal  [TIER: T2]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/tools.py:1729`
**Signature**: `t_terminal(self, args: dict[str, Any]) -> dict[str, Any]`
**Resumen**: Tool universal de ejecución de comandos. `shell=True` por defecto, sin allowlist/denylist; centro de poder del agente.

#### Hallazgos
- [CRITICAL] **terminal_run defaults to shell=True and passes the joined command unchanged**
  - Ubicación: `gemma4_agent/tools.py:2610-2632`
  - Evidencia:
    ```
    shell = bool(args.get("shell", True))
    argv = [command] + [str(x) for x in cmd_args]
    run_arg = subprocess.list2cmdline(argv) if shell else argv
    proc = subprocess.run(run_arg, cwd=cwd, shell=shell, capture_output=True, text=True, timeout=timeout)
    ```
  - Impacto: prompt-injection en página web/documento puede convencer al LLM de llamar `terminal(command='cmd', args=['/c','rd /S /Q %USERPROFILE%'])`. No hay rollback para terminal.
  - Fix sugerido: shell=False por defecto; con `safety_enabled` o si el comando matchea `_DESTRUCTIVE_COMMAND_TOKENS`, forzar confirmación. Mantener una denylist de patrones catastróficos (`rd /s`, `shutdown`, `format`, `diskpart`, `bcdedit`, `cipher /w`).
- [HIGH] **terminal_run accepts arbitrary cwd without checking existence**
  - Ubicación: `gemma4_agent/tools.py:2611-2623`
  - Fix sugerido: si `cwd` se pasa, validar `Path(cwd).is_dir()` y retornar `needs_user` con el path si falla.
- [MEDIUM] **terminal_run hides stdout/stderr beyond 6000/3000 chars without flag**
  - Ubicación: `gemma4_agent/tools.py:2625-2632`
  - Fix sugerido: exponer `max_stdout_chars`/`max_stderr_chars` en schema o volcar a logfile bajo `captures_dir`.

---

### gui  [TIER: T3]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/tools.py:1411`
**Signature**: `t_gui(self, args: dict[str, Any]) -> dict[str, Any]`
**Resumen**: Mouse/teclado/screenshot/OCR. Interpolación insegura en SendKeys + caveats de coordenadas multi-monitor.

#### Hallazgos
- [HIGH] **gui_keypress interpolates raw `keys` into PowerShell SendKeys script**
  - Ubicación: `gemma4_agent/tools.py:2967-2984`
  - Evidencia: `script = f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{sendkeys}')"`
  - Impacto: si `keys` contiene `'`, escapa el literal PS y permite injection. Aunque `keys` viene del LLM, esto sucede sin sanitización.
  - Fix sugerido: usar el patrón env-var indirection (ya usado en `window_control`, `_env_ps`, `_file_hash`, `_authenticode_signature`, `_scanner_scan`). Set `$env:GEMMA4_KEYS = keys` y leer `$env:GEMMA4_KEYS` adentro.
- [MEDIUM] **gui_type pipes text via stdin to SendKeys without escaping control chars**
  - Ubicación: `gemma4_agent/tools.py:2961-2965`
  - Descripción: SendKeys interpreta `+^%~(){}` como modificadores; tipear `C:/Users/Foo (1)/file` falla.
  - Fix sugerido: envolver cada control char en `{}` antes de pasar (`+` → `{+}`).
- [MEDIUM] **gui_screenshot uses VirtualScreen which combines all monitors**
  - Ubicación: `gemma4_agent/tools.py:2843-2865`
  - Fix sugerido: añadir param `monitor=primary|all|<index>` con crop al monitor solicitado.
- [LOW] **click_text adds shot.left/top to OCR coords without documenting it**
  - Ubicación: `gemma4_agent/tools.py:1437-1443`
  - Fix sugerido: añadir `screen_x`/`screen_y` (pre-traducidos) en el match output y documentar `center_x`/`center_y` como image-local.

---

### uia  [TIER: T3]  [STATUS: NEEDS_FIXES (perf)]
**File**: `gemma4_agent/tools.py:1534`
**Resumen**: PowerShell + UIAutomationClient por cada acción; sin afinidad de thread COM ni caching.

#### Hallazgos
- [LOW] **UIA traversal launches a new PowerShell per call (slow + no caching)**
  - Ubicación: `gemma4_agent/tools.py:2644-2826`
  - Fix sugerido: host PowerShell long-lived (Start-Process + named pipe) que amortice la inicialización; o pasar bounds desde `find` a `click` sin re-find.

---

### web  [TIER: T2]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/tools.py:1522`
**Resumen**: HTTP fetch básico para `web.read/research`; no hay SSRF guard.

#### Hallazgos
- [MEDIUM] **_http_get_text follows redirects without cap; no SSRF guard**
  - Ubicación: `gemma4_agent/tools.py:991-1014`
  - Descripción: una URL pública puede redirigir a `127.0.0.1:11434/api/show` (Ollama, sin auth) o `169.254.169.254` (metadatos cloud). El contenido se devuelve al LLM como "texto de página".
  - Fix sugerido: rechazar hosts RFC1918 / loopback / link-local tras resolución DNS; cap explícito de redirects con custom HTTPRedirectHandler.

---

### registry  [TIER: T2]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/ops_tools.py:183`
**Resumen**: Wrapper de `reg.exe` con backup/rollback. Falla parcial del backup puede romper el rollback.

#### Hallazgos
- [MEDIUM] **Rollback assumes the .reg backup succeeded; falls back to delete on failure**
  - Ubicación: `gemma4_agent/ops_tools.py:207-230`
  - Fix sugerido: si el backup falló transitoriamente con un valor que existía antes, refusar la op; o verificar con `reg query` que la clave/valor no existía antes de fallback-to-delete.

---

### download  [TIER: T2]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/ops_tools.py:234`
**Resumen**: Descarga via Invoke-WebRequest + SHA256 + Authenticode. Falsa confianza en firmas.

#### Hallazgos
- [HIGH] **verified=True when Authenticode signature is Valid, regardless of publisher**
  - Ubicación: `gemma4_agent/ops_tools.py:270-293`
  - Evidencia:
    ```
    verified = hash_verified or signature_verified
    ```
  - Impacto: malware firmado con cert robado/comprado pasa la verificación y el LLM puede confiar y ejecutar.
  - Fix sugerido: promover sólo `hash_verified` a `verified=True`. `Authenticode-Valid` → `verified=False, signature_present=True, signer_subject=...`. El agente entonces presenta la firma al usuario en vez de tratarla como prueba.

---

### database  [TIER: T2]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/domain_tools.py:1645`
**Resumen**: SQLite/Postgres/MySQL. Heurística de read-only frágil, identifier injection en `schema`, mutaciones sin gate.

#### Hallazgos
- [CRITICAL] **_database_schema interpolates table name into SQL via f-string**
  - Ubicación: `gemma4_agent/domain_tools.py:1772-1786`
  - Evidencia:
    ```
    if driver == "sqlite":
        cur.execute(f"PRAGMA table_info({table})")
    ...
    else:
        cur.execute(f"DESCRIBE {table}")
    ```
  - Impacto: SQL injection en SQLite y MySQL via `table` arg (PRAGMA/DESCRIBE no aceptan placeholders).
  - Fix sugerido: validar `table` contra allowlist `[A-Za-z_][A-Za-z0-9_]*` y/o exigir que aparezca en `list_tables`.
- [CRITICAL] **_is_read_only_sql heuristic only checks the first keyword; CTE+DML bypasses it**
  - Ubicación: `gemma4_agent/domain_tools.py:1860-1869`
  - Evidencia: `return s.startswith(("select","with","explain","pragma","show","describe"))`
  - Impacto: `WITH x AS (SELECT 1) DELETE FROM y WHERE 1=1` empieza con `with` y pasa; muta la BD vía la action `query` "read-only".
  - Fix sugerido: parsear con sqlglot y rechazar nodos DML/DDL en el árbol; o setear `PRAGMA query_only=1` (SQLite) / `SET TRANSACTION READ ONLY` (PG) durante la `query`.
- [HIGH] **execute mutates without a checkpoint or transaction snapshot**
  - Ubicación: `gemma4_agent/domain_tools.py:1816-1829`
  - Fix sugerido: requerir `confirmed=true`; sin él, retornar `needs_confirmation` con preview de affected rows.
- [MEDIUM] **Postgres/MySQL password passes through args and may be echoed in traces**
  - Ubicación: `gemma4_agent/domain_tools.py:1697-1748`
  - Fix sugerido: redactar `password`/`token`/`key` antes de tracking; o sólo aceptar `password_env=<VARNAME>`.

---

### backup_sync  [TIER: T2]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/domain_tools.py:6302`
**Resumen**: ZIP backup/restore con conflict policy. Zip-slip en restore + sin checkpoint del dst.

#### Hallazgos
- [CRITICAL] **_backup_restore does not sanitize zip entry paths (zip-slip)**
  - Ubicación: `gemma4_agent/domain_tools.py:6386-6403`
  - Evidencia: `final_target = dst / entry.filename` con `entry.filename` arbitrario del ZIP. Permite `../../evil.txt`.
  - Impacto: path traversal — un ZIP malicioso puede escribir cualquier path donde el usuario del agente tenga write.
  - Fix sugerido: tras computar `final_target.resolve()`, verificar que `dst.resolve()` esté en `final_target.resolve().parents` (o sean iguales). Rechazar el entry si no.
- [MEDIUM] **restore does not snapshot the dst tree before overwriting**
  - Ubicación: `gemma4_agent/domain_tools.py:6354-6413`
  - Fix sugerido: copiar el dst tree a backup directory antes del primer overwrite y registrar checkpoint con rollback.

---

### notification  [TIER: T2]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/domain_tools.py:218`
**Resumen**: MessageBox + Scheduled Tasks. Inyección anidada de PS en `_schedule_notification`.

#### Hallazgos
- [CRITICAL] **_schedule_notification embeds a quoted PS sub-command into another quoted PS argument**
  - Ubicación: `gemma4_agent/domain_tools.py:6914-6925`
  - Evidencia:
    ```
    display_script = f"Add-Type ...::Show('{_ps_quote(text)}','{_ps_quote(title)}')"
    ps = f"""
    $Action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -WindowStyle Hidden -Command "{display_script}"'
    ...
    ```
  - Impacto: `_ps_quote` sólo escapa `'`. Si `text` o `title` contienen `"`, escapan el `-Argument` envolvente y todo lo demás corre como PS al disparar el task.
  - Fix sugerido: registrar el Action como `New-ScheduledTaskAction -Execute powershell.exe -Argument '-NoProfile -File <fixed_runner.ps1>'`, y pasar text/title por env-var o por id-de-estado para que el runner las lea.
- [MEDIUM] **_notification_due falls back to now+5min if parsing fails — silent UX bug**
  - Ubicación: `gemma4_agent/domain_tools.py:7056-7069`
  - Fix sugerido: error de validación explícito si el formato no parsea; aceptar `HH:MM` como atajo a hoy/mañana.

---

### maintenance  [TIER: T2]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/domain_tools.py:3180`
**Resumen**: Defender/eventos/servicios/restore points. PowerShell injection en event_logs, Defender scan bloquea.

#### Hallazgos
- [CRITICAL] **_maintenance_event_logs interpolates `log` arg into the PS FilterHashtable literal**
  - Ubicación: `gemma4_agent/domain_tools.py:3313-3343`
  - Evidencia: `f"$f = @{{ LogName='{log}'; ... }}"`
  - Impacto: PS injection via `maintenance(action='event_logs_query', log="System' ; Stop-Computer ; #")`.
  - Fix sugerido: env-var indirection (`$env:GEMMA4_LOG_NAME`) o validar `log` contra regex `^[A-Za-z][A-Za-z0-9/_\-]*$`.
- [HIGH] **defender_quick_scan blocks the agent thread up to 15 minutes**
  - Ubicación: `gemma4_agent/domain_tools.py:3280-3293`
  - Fix sugerido: lanzar via `job_manager.start` y devolver `job_id` para polling.
- [MEDIUM] **disk_cleanup_describe returns command_describe=['cleanmgr','/sageset:1'] but says 'we do not run this'**
  - Ubicación: `gemma4_agent/domain_tools.py:3219-3225`
  - Fix sugerido: no devolver arrays de comando listos-para-ejecutar; sólo prosa. O exponer un `maintenance.disk_cleanup_run` separado con confirmation.

---

### routine  [TIER: T3]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/domain_tools.py:450`
**Resumen**: Scheduled Tasks + watchers + on_phrase. PS injection en cron triggers, `state._load/_save` privado en uso.

#### Hallazgos
- [CRITICAL] **_build_routine_trigger_ps interpolates trigger.at / days_of_week into PowerShell**
  - Ubicación: `gemma4_agent/domain_tools.py:5032-5057`
  - Evidencia: `f"New-ScheduledTaskTrigger -Daily -At '{at}'"`, `f"... -DaysOfWeek {days_str} -At '{at}'"`
  - Impacto: PS injection via `trigger.at` o `trigger.days_of_week` controlados por LLM.
  - Fix sugerido: validar `at` regex `^[0-2]\d:[0-5]\d$` (o ISO para `once`); `days_of_week` contra el set literal de nombres en inglés.
- [HIGH] **routine_tool reaches into state._load() / state._save() throughout**
  - Ubicación: `gemma4_agent/domain_tools.py:575-581` (también `notification`, `watcher`, `developer`, `job_manager`).
  - Fix sugerido: añadir `state.update_resource_metadata(resource_id, patch)` y refactorizar todos los call sites.
- [MEDIUM] **_looks_destructive contains a redundant/buggy boolean chain**
  - Ubicación: `gemma4_agent/domain_tools.py:278-291`
  - Descripción: la línea 284 (`if needle in low or low.find(" " + needle.split()[0]) >= 0 and needle in low`) simplifica a `needle in low`; la lógica real está en `boundary_hits` debajo.
  - Fix sugerido: borrar el primer loop, dejar sólo el regex word-boundary.

---

### smart_home  [TIER: T3]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/domain_tools.py:650`
**Resumen**: Home Assistant REST + MQTT. `_hass_alive` siempre devuelve True y rollback semicompleto.

#### Hallazgos
- [CRITICAL] **_hass_alive returns True even when HA is unreachable**
  - Ubicación: `gemma4_agent/domain_tools.py:711-723`
  - Evidencia:
    ```
    except Exception:
        try:
            import urllib.error  # noqa: F401
            return True
        except Exception:
            return False
    ```
  - Impacto: `smart_home.status` reporta `home_assistant=True` aunque HA esté caído; downstream calls fallan con HTTPError críptico.
  - Fix sugerido: distinguir `HTTPError` (200/401/403 = alive) de `URLError`/timeout (= False). Quitar el `import urllib.error` no-op.
- [MEDIUM] **_hass_call_service rollback only handles binary on/off; brightness/color not snapshotted**
  - Ubicación: `gemma4_agent/domain_tools.py:783-814`
  - Fix sugerido: snapshot del state completo (atributos incluidos) y reconstruir el rollback con ellos.

---

### network  [TIER: T2]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/domain_tools.py:2640`
**Resumen**: ping/dns/port/conn. PS injection en dns_set, validación insuficiente en connections-state.

#### Hallazgos
- [CRITICAL] **_network_dns_set joins addresses into a PowerShell expression without escaping**
  - Ubicación: `gemma4_agent/domain_tools.py:2740-2745`
  - Evidencia: `addr_list = ",".join(f"'{a}'" for a in addresses)` ; embebido en `-ServerAddresses ({addr_list})`.
  - Impacto: PS injection si una address contiene `'`.
  - Fix sugerido: validar cada address contra regex IPv4/IPv6 antes de embeber.
- [MEDIUM] **_network_connections passes `state` arg straight into Get-NetTCPConnection -State**
  - Ubicación: `gemma4_agent/domain_tools.py:2790-2807`
  - Fix sugerido: enum allowlist (`Established`, `Listen`, etc.); rechazar lo demás.

---

### data_analysis  [TIER: T2]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/domain_tools.py:2460`
**Resumen**: pandas + matplotlib. `csv_query` expone `.query()` con eval-like semantics.

#### Hallazgos
- [HIGH] **csv_query passes user string to pandas .query() without engine restriction**
  - Ubicación: `gemma4_agent/domain_tools.py:2546-2562`
  - Descripción: pandas `.query()` cae a `engine='python'` si numexpr falta; soporta `@` y backticks para acceder locals. Documentado en pandas como inseguro contra input adversarial.
  - Fix sugerido: forzar `engine='numexpr'` si está, rechazar queries con `@` o backticks; o usar AST validado.

---

### developer  [TIER: T3]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/domain_tools.py:4270`
**Resumen**: project_detect/tests/lint/format + dev_server lifecycle. Dev server detach insuficiente.

#### Hallazgos
- [HIGH] **stop_dev_server kills the stored PID without checking it is still owned by the dev server**
  - Ubicación: `gemma4_agent/domain_tools.py:4543-4573`
  - Impacto: PID recycling en Windows → taskkill puede matar un proceso ajeno.
  - Fix sugerido: antes de taskkill, `Get-Process -Id <pid>` y comparar nombre con `metadata.cmd[0]`.
- [MEDIUM] **start_dev_server uses Popen but does not detach from agent process group**
  - Ubicación: `gemma4_agent/domain_tools.py:4514-4519`
  - Fix sugerido: añadir `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS` para que el dev server sobreviva al cierre del agente.

---

### browser_real  [TIER: T3]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/ops_tools.py:373`
**Resumen**: Playwright headless + CDP attach. Evaluate arbitrario, session state global, headless inconsistente.

#### Hallazgos
- [HIGH] **browser_real(action='evaluate') accepts arbitrary JavaScript from the LLM**
  - Ubicación: `gemma4_agent/ops_tools.py:511-516`
  - Descripción: en CDP-attached visible session, ese JS corre en contexto de usuario con cookies. Permite exfiltración de sesiones.
  - Fix sugerido: gate de confirmación cuando session.cdp=True; pass-through en sessions headless propias del agente.
- [MEDIUM] **_BROWSER_SESSIONS is module-global and not lifecycle-managed by AgentState**
  - Ubicación: `gemma4_agent/ops_tools.py:23-24`
  - Fix sugerido: al startup, marcar como stale las browser_real resources con `metadata.process_uptime` distinto del actual.
- [MEDIUM] **_get_browser_session ignores headless flag after first call**
  - Ubicación: `gemma4_agent/ops_tools.py:769-786`
  - Fix sugerido: si `session.headless != requested`, retornar `needs_user` ("close first").
- [LOW] **wait_for_download returns needs_implementation for CDP sessions**
  - Ubicación: `gemma4_agent/ops_tools.py:678-683`
  - Fix sugerido: documentar el gap en el schema description y plan-de-acción para CDP raw `Browser.downloadProgress`.

---

### app  [TIER: T2]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/tools.py:1288`
**Resumen**: AppResolver + open/close/search. Errores de startfile no estructurados.

#### Hallazgos
- [MEDIUM] **AppResolver.open swallows os.startfile errors silently**
  - Ubicación: `gemma4_agent/tools.py:724-728`
  - Fix sugerido: try/except OSError + retornar error estructurado con candidate y reason.

---

### package  [TIER: T2]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/tools.py:1708`
**Resumen**: winget wrapper sin confirmación.

#### Hallazgos
- [HIGH] **package install/uninstall runs winget with no user confirmation gate**
  - Ubicación: `gemma4_agent/tools.py:1708-1719`
  - Evidencia: `winget install --accept-source-agreements --accept-package-agreements <name>`
  - Fix sugerido: confirmación obligatoria en install/uninstall, fuera del flag `safety_enabled`.

---

### media_edit  [TIER: T2]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/domain_tools.py:3431`
**Resumen**: ffmpeg wrapper. Concat list no escapa apóstrofos.

#### Hallazgos
- [LOW] **_media_edit_concat writes paths to a concat list file without escaping apostrophes**
  - Ubicación: `gemma4_agent/domain_tools.py:3543-3564`
  - Fix sugerido: escapar `'` como `'\\''` en el list file (per ffmpeg concat docs).

---

### job_manager  [TIER: T2]  [STATUS: NEEDS_FIXES]
**File**: `gemma4_agent/domain_tools.py:3057`
**Resumen**: Popen detached + log + cancel via taskkill. Split por whitespace pierde quoting.

#### Hallazgos
- [MEDIUM] **_job_manager_start string-splits commands by whitespace, losing quoting**
  - Ubicación: `gemma4_agent/domain_tools.py:3095-3104`
  - Fix sugerido: `shlex.split(command, posix=False)` o requerir list-form para paths con espacios.

---

### safety  [TIER: T1]  [STATUS: PASS (con caveat)]
**File**: `gemma4_agent/tools.py:1933`
**Resumen**: Tool de confirmación; correcto. El caveat es a nivel de constructor.

#### Hallazgos
- [INFO] **safety_enabled defaults to False on ToolRegistry**
  - Ubicación: `gemma4_agent/tools.py:1093-1101`
  - Impacto: combinado con terminal/package/system findings, por default el agente puede ejecutar acciones destructivas sin gate.
  - Fix sugerido: default a True; flag explícito para deshabilitar en tests.

---

### routine.import (TriggerCMD)  [TIER: T2]  [STATUS: PASS]
**File**: `gemma4_agent/domain_tools.py:294`
**Resumen**: import con `_looks_destructive` + `enabled=false` por default. Buen patrón.

#### Hallazgos
- [INFO] **import_triggercmd_entries gates destructive commands behind enabled=false on import**
  - Fix sugerido (replicación): aplicar el mismo check de `_looks_destructive` a `routine.create` directo cuando los `steps` invoquen `terminal` con `shell=True`.

---

### Tools sin hallazgos (PASS)

Las siguientes tools recibieron `status: PASS` tras revisión estática: `audio_device`, `office`, `photo_library`, `container`, `device_settings`, `media` (now_playing/local/vlc), `game_launcher`, `watcher`, `printer_scanner`, `desktop_layout`, `document`, `peripheral`, `accessibility`, `creative_local`, `form_filler` (template a replicar), `subagent`, `study`, `fact_check`, `knowledge`, `state`, `source_manager`, `contacts`, `notes_tasks`, `local_calendar`, `habit_tracker`, `local_search`, `dependency`, `verify`, `memory`, `input`, `env`, `email`, `reminder`.

Nota: PASS aquí significa "no se identificó un defecto bloqueante en revisión estática"; algunas de ellas comparten los hallazgos transversales del próximo bloque (especialmente `CC-confirmation-gating-default-off-101` y `CC-private-state-api-102`).

---

## Hallazgos transversales

### CC-ps-fstring-injection-pattern-100  [CRITICAL]
**Tools afectadas**: `notification`, `maintenance`, `network`, `routine`, `gui` (más casos sospechosos en `_register_routine_scheduled_task`).

Múltiples tools construyen scripts PowerShell por interpolación f-string con datos controlados por el LLM. `_ps_quote` solo dobla `'`; no escapa `"`, backticks, `$`, ni ningún carácter que rompa el parsing cuando el valor está fuera de un literal single-quoted. El patrón correcto **ya existe** en el código (env-var indirection en `window_control`, `_env_ps`, `_file_hash`, `_authenticode_signature`, `_scanner_scan`). Faltó aplicarlo uniformemente.

**Fix global**: introducir un helper `_ps_safe_literal(value, regex)` y, donde no aplique, mover los datos a `$env:GEMMA4_*` antes de invocar PowerShell. Auditar también `_register_routine_scheduled_task` (ya cuenta con `_ps_quote`, pero el `arg_line` con doble comilla embebida amerita misma migración).

### CC-confirmation-gating-default-off-101  [CRITICAL]
**Tools afectadas**: `system` (shutdown/restart/sleep), `terminal`, `package`, `database` (execute), `backup_sync` (restore overwrite), `filesystem` (delete).

`ToolRegistry.safety_enabled` default es `False`. La pieza correcta (`state.create_confirmation` + `form_filler` pattern) está implementada pero opt-in. El default actual permite que el modelo ejecute acciones destructivas con un solo tool call.

**Fix global**: 1) cambiar default a `True`. 2) Para los tools listados, añadir un gate `needs_confirmation` independiente de `safety_enabled`. 3) Incluir en la confirmación un resumen breve y la posibilidad de rollback.

### CC-private-state-api-102  [HIGH]
**Tools afectadas**: `routine`, `watcher`, `job_manager`, `developer`, `notification`.

Varios call sites llaman `state._load()`/`state._save(data)` directamente. Esto puentea cualquier locking que la API pública aplique. El commit reciente `3f77637` agregó RLock pero los `_load/_save` directos sortean la operación atómica read-modify-write.

**Fix global**: añadir `state.update_resource_metadata(resource_id, patch)` (atómico bajo RLock) y refactorizar los call sites. Bloquear `_load`/`_save` con `_` prefix-respetando-convención en code review.

### CC-json-loads-unguarded-103  [MEDIUM]
**Tools afectadas**: `system`, `app`, `uia` (y partes de domain_tools.py).

Varios call sites usan `json.loads(proc.stdout)` directo en lugar de los helpers existentes `_powershell_json` y `_json_or_text`. Cuando PowerShell imprime un warning antes del JSON, el agente surface un genérico `JSONDecodeError:` que no ayuda al verifier.

**Fix global**: consolidar a un solo helper (sugerido: `gemma4_agent/_ps.py`) y replace-all.

### CC-pid-recycling-104  [HIGH]
**Tools afectadas**: `developer.stop_dev_server`, `job_manager.cancel`.

Ambos hacen `taskkill /F /PID <pid> /T` sobre PID almacenado. Windows recicla PIDs; el mismo PID puede pertenecer a otro proceso post-restart del agente.

**Fix global**: helper `_pid_owned_by(pid, expected_exe_basename)` que confirme `Get-Process -Id <pid>.ProcessName` matchea antes de matar.

### CC-credential-args-traced-105  [MEDIUM]
**Tools afectadas**: `database`, `smart_home`, `email`.

Credenciales pasadas via args terminan en `traces.jsonl`.

**Fix global**: pass de redacción a nivel de `_normalize_tool_result` para keys que matcheen `password|token|key|secret`. O exigir `password_env=<VARNAME>`.

### CC-window-virtualscreen-coords-106  [LOW]
**Tools afectadas**: `gui`, `vision`.

Coordenadas OCR son image-local (VirtualScreen-local) pero el screenshot abarca todos los monitores. `click_text` ya hace la traducción internamente; otros call sites que extraen `center_x`/`center_y` de un OCR result pueden mis-clickear.

**Fix global**: añadir `screen_x`/`screen_y` (pre-traducidos) en los OCR matches y documentar.

### CC-no-confirmation-on-rollback-107  [INFO]
**Tools afectadas**: `state`.

`state(action='rollback')` ejecuta verbatim los rollback steps almacenados. Algunos son destructivos (filesystem.delete para deshacer copy). No es defecto, pero merece documentación en el schema y, opcionalmente, requerir un `state.rollback_plan` previo antes del apply.

---

## Cierre

- **Path de artefactos**: `audit/audit_report.md` y `audit/audit_findings.json`.
- **Conteo final**: 11 critical, 14 high, 22 medium, 5 low, 4 info. 35 PASS, 22 NEEDS_FIXES.

### Top 5 hallazgos críticos

1. **terminal_run defaults to shell=True without allowlist or confirmation** (`T2-terminal-shell-true-default-006`) — el agente puede ejecutar cualquier comando del LLM.
2. **_is_read_only_sql heuristic bypassed by CTE+DML** (`T2-database-readonly-heuristic-018`) — la "read-only" `database.query` permite mutaciones.
3. **_backup_restore zip-slip** (`T2-backup_sync-zip-slip-021`) — ZIPs maliciosos escriben fuera del destino.
4. **_schedule_notification PowerShell injection vía title/text** (`T2-notification-ps-injection-023`) — payload disparado en el momento programado.
5. **_hass_alive always-true bug** (`T3-smart_home-alive-always-true-031`) — smart_home reporta HA vivo aun caído, downstream calls confunden al verifier.

### No verificables estáticamente

Los siguientes ítems requirieron criterio o serían más sólidos con ejecución real:

- **Ejecución real del flujo de confirmación**: `state.create_confirmation` está en código; queda comprobar end-to-end que `safety(action='confirm', id=...)` re-invoca correctamente con `confirmed=True` (`form_filler.submit` lo hace; no se ejecutó).
- **Compatibilidad del clasificador `safety.classify_tool_call`**: el archivo `safety.py` (líneas no leídas en esta auditoría) define qué calls quedan flagged. No se cuantificó qué proporción de los tools NEEDS_FIXES ya están parcialmente cubiertos por ese clasificador.
- **Comportamiento RLock real de `AgentState._load/_save`**: el commit `3f77637` agregó RLock; no se verificó que la primitiva cubra el patrón read-modify-write usado por tools que llaman `_load()` luego `_save(data)`.
- **Recorrido completo de pandas `.query()` engines**: dependiendo de versión de pandas/numexpr la superficie de eval cambia.
- **Carga real de `SoundVolumeView` y `WIA.DeviceManager`**: tools que dependen de COM/binarios externos sólo se verificaron contractualmente.
- **Race conditions concurrentes**: el repo es de un agente single-thread mayoritariamente; no se exploró si `subagent` paraleliza calls que tocaran tools mutables.
- **Encoding cp1252 en outputs de PowerShell**: varios stdouts contienen caracteres `?` (líneas 4089, 4092 etc.) — el código de origen ya tiene replacement chars; señal de que el encoding cp1252→utf-8 está siendo lossy en algún punto upstream. No verificado con ejecución.
