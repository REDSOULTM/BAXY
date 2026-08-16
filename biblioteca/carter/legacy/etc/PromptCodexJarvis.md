# Prompt para Codex — Carter → Jarvis (root-cause fix)

Copia todo lo que está **bajo esta línea** al chat de Codex.

---

## Misión

Carter es un asistente personal AI para Windows que corre con Qwen3-8B local (llama-cpp-python, n_ctx=8192 + Ollama para pruebas). El esqueleto está hecho (LLM como cerebro, 115 tools, ledger, verificación, approval, recovery), pero falla como Jarvis por causas estructurales, no superficiales.

**Fallas confirmadas por 20 pruebas directas ejecutadas el 2026-04-18 contra Qwen3:8b vía Ollama:**
- "¿Qué hora es?" → intenta `terminal_run_command("time")` → bloqueado por policy → fallo (58s)
- "Lee el archivo X" → 0 tools llamados → guard anti-alucinación → fallo silencioso (52s)
- "Crea archivo en el escritorio" → path `C:\Users\usuario\` (username genérico erróneo) → fallo x5 (262s)
- "Busca en internet X" → Playwright + Google → 0 resultados → fallo sin fallback (66s)
- "Abre el Bloc de Notas" → `app_open` x8 en loop → 322s → fallo total
- "Desinstala paint.net" → `app_uninstall` + 4 tools bloqueados → 381s → fallo total
- "Recuerda que mi color favorito es azul" → 0 tools → respuesta conversacional → no persistió nada
- "¿Cuánto es 2+2?" → correcto pero 91s (thinking mode siempre activo)

Vas a arreglar las causas de raíz.

---

## Reglas no negociables

1. **CERO hardcode de idioma.** Nada de listas tipo `["hora","time","heure","uhrzeit"]`. Carter es universal — debe servir a humanos en cualquier idioma. Las únicas señales aceptables son estructurales: regex de shell destructivo, esquemas JSON, códigos de error de SO, mime types.
2. **El LLM es el cerebro.** No agregues ramas determinísticas que ejecuten antes del LLM. No clasifiques intent por keyword. Si dudas si una heurística es "estructural" o "lingüística", asume lingüística y NO la metas.
3. **No retrocedas sobre BrainRouter.** Solo `_HIGH_RISK_RE` para `rm -rf|Remove-Item|Format-*`. Todo lo demás → `LLM_CHAT / agent_full`.
4. **Tests.** La suite debe seguir en verde (1001/1001). Añade tests nuevos para cada cambio.

---

## Working directory

`C:\Users\usuario\Desktop\ETC\Programacion\Carter OS AI\Carter_v2\`

---

## Tareas (ejecuta en este orden)

### Tarea 1 — Capacidades base atómicas ★ CRÍTICO

**1a. `system_get_time`** — nuevo `capabilities/clock.py` (o añadir a `probe.py`):
- Acción: `get_time`. Sin parámetros.
- Implementar con `datetime.now().astimezone()`.
- Devolver: `{iso, timezone, unix, date, time, weekday, tz_name, tz_offset_hours}`.
- Registrar en `tools.py` como `system_get_time`. Compact description ≤30 palabras.
- Registrar en `_build_registry()` en `main.py`.
- **Por qué:** "¿Qué hora es?" → actualmente intenta `terminal_run_command("time")` → bloqueado → fallo en 58s.

**1b. `filesystem_read_text`** — extender [filesystem.py:13](Carter_v2/src/carter_v2/capabilities/filesystem.py#L13):
- Añadir `"read_text"` a `supports()`.
- Leer con `path.read_text(encoding="utf-8", errors="replace")`.
- Mismo guard `Path.home()` que `write_text`. Cap a 100KB (parámetro `max_bytes=102400`).
- Registrar en `tools.py` como `filesystem_read_text`.
- **Por qué:** "Lee el archivo X" → 0 tools llamados → guard anti-alucinación → nada.

**1c. Fix del username genérico en probe** — `capabilities/probe.py`:
- En donde se genera el context text, usar `os.environ.get("USERNAME") or Path.home().name` para el username real.
- Inyectar en system context: `username: <valor real>` y `home: C:\Users\<username>`.
- **Por qué:** "Crea archivo en escritorio" → escribía en `C:\Users\usuario\Desktop\` (no existe) → fallo x5 en 262s.

**1d. Métricas de sistema vía psutil** — extender `capabilities/system.py`:
- `system_get_ram_info` → `psutil.virtual_memory()` → `{total_gb, used_gb, free_gb, percent}`.
- `system_get_disk_info(drive="C:")` → `psutil.disk_usage(drive)` → `{total_gb, used_gb, free_gb, percent}`.
- `system_get_cpu_info` → `psutil.cpu_percent(interval=0.5)` + `psutil.cpu_count()`.
- Mejorar `system_get_gpu_info` añadiendo `vram_used_mb`, `vram_free_mb` via `nvidia-smi --query-gpu=memory.used,memory.free,memory.total --format=csv,noheader,nounits` (fallback gracioso si nvidia-smi no está).
- Registrar todos en `tools.py` y `_build_registry()`.
- **Por qué:** RAM/disco/CPU actualmente necesitan workaround vía terminal PowerShell (87-291s, frágil). `psutil` ya está instalado en el proyecto.

---

### Tarea 2 — System prompt completo con política de memoria ★ CRÍTICO

Reescribir `_SYSTEM_PROMPT_TEMPLATE` en [agent.py:54-69](Carter_v2/src/carter_v2/turn/agent.py#L54-L69):

```
You are Carter, {user_ref}'s personal AI assistant running on this Windows PC.
Context: username={username}, home={home_dir}

Capabilities: control apps, files, windows, terminal, web, vision, system info, memory.

Action policy:
- When asked to do something on the PC, call the right tool immediately.
  No explanation, no asking permission — just call it.
- If a tool fails, try the next logical alternative.
  Never call the same tool with the same arguments more than twice.
  Never say "I can't" without trying at least 2 different tools.
- app_open fails → try terminal_run_command('start <name>') → try terminal_run_powershell('Start-Process <name>').

Memory policy:
- If the user shares a personal fact, preference, or config, call memory_save(key, value) immediately.
- Before answering questions about the user's history or preferences, call memory_recall(key) first.
- Never claim to remember something you haven't stored via memory_save.

Honesty policy:
- Never report success unless a tool returned ok=True.
- If a tool returns an error, quote it exactly. Do not invent a resolution.
- You are Carter. Never claim to be Qwen, ChatGPT, or any other AI.

Format:
- Reply in the language the user used.
- Plain text only. No markdown, no lists, no asterisks.
- After success: 1-2 words. After failure: one honest line.
```

Añadir `{username}` y `{home_dir}` como variables al template. Poblarlos en `_build_system_prompt()`:
```python
username = os.environ.get("USERNAME") or Path.home().name
home_dir = str(Path.home())
```

NO añadir ejemplos en ningún idioma concreto. No poner "abre/open/öffne" en el prompt.

**Por qué:** T14 "¿Quién eres?" tardó 185s porque el modelo no tenía identidad clara. T16 "Recuerda X" no guardó nada porque no había política de memoria.

---

### Tarea 3 — `web_search` con cadena de fallback ★ CRÍTICO

En [web.py:415](Carter_v2/src/carter_v2/capabilities/web.py#L415) (`_web_search`), refactorizar a cadena de 3 backends:

1. **Playwright + Google** (actual) — si `results == []` o error:
2. **requests + DuckDuckGo HTML:**
   ```python
   resp = requests.get("https://html.duckduckgo.com/html/",
                       params={"q": query},
                       headers={"User-Agent": "Mozilla/5.0"},
                       timeout=10)
   # parsear .result__title, .result__url, .result__snippet con BeautifulSoup
   ```
3. **urllib + Bing:**
   ```python
   url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
   # parsear <li class="b_algo"> con regex o BeautifulSoup
   ```

Cada nivel solo se activa si el anterior devuelve `results == []`. Sin keywords. Devolver `data["backend_used"]` para diagnóstico.

**Por qué:** T08 y T09 (en español y alemán) — Playwright carga Google pero devuelve 0 resultados porque Google sirve HTML anti-bot a Chromium headless. Falla en ambos idiomas → sin fallback → Carter inútil para web.

---

### Tarea 4 — Anti-bucle de tools + escalation chain ★ CRÍTICO

**4a. Anti-bucle** — en el loop principal de [agent.py](Carter_v2/src/carter_v2/turn/agent.py) cerca de `MAX_TOOL_ITERATIONS=25`:

Añadir `call_counter: Counter[tuple[str, str]]` donde la key es `(tool_name, stable_hash_of_args)`.
Cuando `call_counter[(tool, hash)] >= 3`, inyectar en el siguiente mensaje al LLM:

```
LOOP_DETECTED: <tool_name>(<args_summary>) called 3 times with the same arguments.
You MUST try a different tool or different arguments. Do not repeat <tool_name> this turn.
```

Este texto va al LLM (no al usuario) — puede ser en inglés, no es hardcode de idioma.

**Por qué:** T10 llamó `app_open` 8 veces seguidas → 322s → fallo total. T12 llamó `terminal_run_command` 3 veces → 381s → fallo total.

**4b. `failure_chain` en metadatos de tool** — en `adapters/tools.py`, añadir campo opcional `failure_chain: list[str] | None = None` a `ToolDefinition`. Definirlo para las tools de acción crítica:

```python
ToolDefinition(name="app_open",
    failure_chain=[
        "try terminal_run_command with command='start <appname>'",
        "try terminal_run_powershell with command='Start-Process <appname>'",
        "try desktop_screenshot then gui_do to click the app icon",
    ])

ToolDefinition(name="app_uninstall",
    failure_chain=[
        "try terminal_run_powershell: winget uninstall <name>",
        "try terminal_run_powershell: Get-AppxPackage *<name>* | Remove-AppxPackage",
        "try desktop_screenshot then gui_do to open Settings > Apps and uninstall",
    ])
```

En [agent.py:959-1002](Carter_v2/src/carter_v2/turn/agent.py#L959-L1002), cuando un tool falla y tiene `failure_chain`, añadir al mensaje del LLM:

```
TOOL_FAILED: app_open(target=Bloc de Notas)
ERROR: <mensaje literal del tool>
SUGGESTED_NEXT_STEPS:
  - try terminal_run_command with command='start notepad'
  - try terminal_run_powershell with command='Start-Process notepad'
```

Sin regex de idioma. La cadena es metadata del tool, no clasificación del input del usuario.

---

### Tarea 5 — Memoria real activa ★ CRÍTICO

**5a. Verificar registro de `MemoryCapability`** en [main.py](Carter_v2/src/carter_v2/main.py):
- `MemoryCapability` debe estar en `_build_registry()` y recibir la instancia `memory` de `PersistentMemory`.
- Los tools `memory_save(key, value)` y `memory_recall(key)` deben estar en `tools.py` con compact descriptions.

**5b. System prompt ya incluye la memory policy** — cubierto en Tarea 2. Solo verificar que el tool `memory_save` aparece en el catálogo que recibe el LLM (no está en `FOCUSED_TOOLS` ni excluido por compact).

**5c. `meta_list_capabilities`** — crear `capabilities/meta.py`:
- Acción `list_capabilities`: consulta `CapabilityRegistry`, devuelve `{namespace: [actions]}` reales.
- Acción `describe_tool(name)`: devuelve descripción completa del tool desde `ToolDefinition`.
- Registrar en `tools.py` y `_build_registry()`.
- **Por qué:** T15 "¿Qué puedes hacer?" → lista inventada por el modelo. Con este tool devuelve los datos reales del registry.

---

### Tarea 6 — `thinking=False` para turnos conversacionales

En `OpenAICompatAgentBackend.chat_with_tools()` en [agent.py](Carter_v2/src/carter_v2/turn/agent.py):
- Añadir parámetro `think: bool = True` al método.
- Si `think=False`, añadir `"think": False` al body JSON de la request a Ollama (ignorado por otros backends).
- En `AgentEngine.run()`, cuando `hint_no_tools=True` (turno puramente conversacional sin tools), llamar `chat_with_tools(..., think=False)`.

**Por qué:** T14 "¿Quién eres?" → 185s sin ningún tool. T19 "2+2" → 91s. T18 chiste → 96s. Qwen3 entra en modo `<think>` extenso para TODA respuesta. `think=False` desactiva eso para turnos triviales.

---

### Tarea 7 — Errores accionables en capabilities críticas

En `types.py`, añadir campo opcional `next_step_hint: str | None = None` a `CapabilityResult`.

En las capabilities que más fallan, poblar el hint cuando `ok=False`:
- `app_open` falla → `hint="try terminal_run_command('start <appname>') or terminal_run_powershell"`
- `terminal_run_command` bloqueado por policy → `hint="try terminal_run_powershell instead"`
- `filesystem_write_text` path fuera del home → `hint="use a path inside C:/Users/<username>/"`
- `web_search` sin resultados → `hint="try web_navigate to search directly"`

En `agent.py`, cuando un tool falla y tiene `next_step_hint`, incluirlo en el bloque `TOOL_FAILED` antes de que el LLM decida:

```
TOOL_FAILED: terminal_run_command(command=fsutil)
ERROR: Ejecutable 'fsutil' no está en la lista de comandos permitidos.
HINT: try terminal_run_powershell instead
```

---

### Tarea 8 — Backend null con error visible

En `main.py` al arrancar: si `backend.available is False`, imprimir:

```
[!] Backend LLM no disponible.
    Esperado: <gguf_path o base_url>
    Razón: <exception_message>
    Carter responderá con placeholder hasta que el modelo cargue.
```

---

### Tarea 9 — Deduplicar catálogo compact

En `adapters/tools.py`, identificar pares duplicados (`app_open` vs `process_start_app`, `web_open_url` vs `web_navigate`, etc.). Añadir `deprecated=True` al duplicado peor. En `tool_schemas_for_llm(compact=True)`, excluir `deprecated=True`. No borrar — preserva tests.

---

## Validación obligatoria

Tras todos los cambios:

1. `python -m pytest Carter_v2/tests/ -q` → **1001+ passed, 0 failed nuevos.**

2. Correr `python Carter_v2/probe_carter.py` (script ya existe). Verificar que estas pruebas mejoran vs los baselines:

| Test | Input | Baseline (antes) | Target (después) |
|------|-------|-----------------|------------------|
| T01 | "¿Qué hora es?" | error 58s | `system_get_time` <5s |
| T02 | "What time is it?" | error 28s | `system_get_time` <5s |
| T05 | "Lee el archivo X" | 0 tools, 52s | `filesystem_read_text` |
| T06 | "Crea archivo en escritorio" | path erróneo, 262s | path correcto, 1 intento |
| T08 | búsqueda web español | 0 resultados | resultados reales |
| T09 | búsqueda web alemán | 0 resultados | resultados reales |
| T10 | "Abre el Bloc de Notas" | 12 tool calls, 322s | ≤3 tool calls |
| T12 | "Desinstala paint.net" | 5 tools, 381s, fallo | escalation chain correcta |
| T16 | "Recuerda color favorito" | 0 tools | `memory_save` llamado |
| T19 | "¿Cuánto es 2+2?" | 91s | <15s con think=False |

3. **Auditoría anti-hardcode:**
```
grep -ri "hora\|heure\|uhrzeit\|abre\|desinstala\|uninstall\|open app" \
  Carter_v2/src/carter_v2/turn/ \
  Carter_v2/src/carter_v2/capabilities/clock.py \
  Carter_v2/src/carter_v2/capabilities/meta.py
```
No debe matchear ninguna lista de clasificación de input. Solo descripciones de tools, mensajes de output, o código de tests.

---

## Reporte esperado

Al terminar, entrega:
- Lista de archivos tocados con +/- de líneas.
- Tests añadidos (nombres y qué verifican).
- Output completo del `pytest` final.
- Confirmación explícita: **"cero keywords de idioma añadidas a ningún clasificador"**.
- Resultados de al menos 5 pruebas del `probe_carter.py` mostrando mejora vs baseline.

---

## Si encuentras conflicto entre estas instrucciones y "lo que sería más fácil"

Sigue estas instrucciones. La facilidad no es el objetivo — Carter como Jarvis universal sí lo es.

---
---

# CONTINUACIÓN — Sesión 6 (post-Sesión 5)

Sesión 5 completó Tareas 1-9. Las pruebas reales y la auditoría estructural revelaron **gaps más profundos**: memoria no se inyecta, heartbeat ciego, app resolver hardcodeado, faltan filesystem/sistema/notificaciones, sin watchdog, sin verification, etc.

**Las reglas no negociables siguen vigentes:**
1. CERO hardcode de idioma. Carter es para todos los humanos en cualquier idioma.
2. El LLM es el cerebro. Sin ramas determinísticas que ejecuten antes del LLM.
3. No retroceder sobre BrainRouter — solo `_HIGH_RISK_RE` para shell destructivo.
4. Suite de tests debe seguir verde. Tests nuevos por cada cambio.

---

## Tarea 10 — Inyectar memoria en cada turno ★ CRÍTICO

**Problema:** `memory_recall` existe pero el LLM olvida llamarlo. Resultado: T17 ("¿cuál es mi color favorito?") no recuerda nada aunque T16 lo guardó.

**Fix de raíz** en [agent.py:_build_system_prompt](Carter_v2/src/carter_v2/turn/agent.py):

1. Cambiar la firma a `_build_system_prompt(user_name=None, memory=None, recent_alerts=None)`.
2. Si `memory is not None`, leer `facts = memory.list_facts(limit=20)` y formatearlos:
   ```
   KNOWN FACTS ABOUT USER (auto-injected from persistent memory):
   - favorite_color: blue
   - city: Santiago
   - gpu: RTX 4060 Ti
   ```
3. Añadir el bloque al system prompt SOLO si `len(facts) > 0`. Cap a 600 chars total.
4. En `AgentEngine.run()`, pasar `memory=self.memory` a `_build_system_prompt`.
5. Invalidar el cache `_SYSTEM_PROMPT_CACHE` cuando se llama `memory_save` (o cachear con hash de facts).

**Test obligatorio:** `tests/test_memory_injection.py` — guardar fact, ejecutar nuevo turno, verificar que el system prompt enviado al backend contiene el fact.

**Por qué:** Sin esto Carter es amnésico funcionalmente aunque la base de datos esté llena.

---

## Tarea 11 — Heartbeat alerts → contexto del LLM ★ CRÍTICO

**Problema:** [main.py:684-686](Carter_v2/src/carter_v2/main.py#L684-L686) drena los alerts del `AlertQueue` y los imprime al CLI. El LLM nunca los ve.

**Fix de raíz:**

1. En [session/proactive.py](Carter_v2/src/carter_v2/session/proactive.py), añadir `AlertQueue.peek(n)` que devuelve últimos N sin consumir.
2. En `AgentEngine.__init__`, recibir `alert_queue: AlertQueue | None = None`.
3. En `AgentEngine.run()`, leer `recent = alert_queue.peek(5)` (si existe) y pasar a `_build_system_prompt(..., recent_alerts=recent)`.
4. En el system prompt, si `recent_alerts` no vacío, añadir bloque opcional:
   ```
   RECENT SYSTEM EVENTS (last 5):
   - 2 min ago: GPU usage at 95%
   - 5 min ago: Disk C: at 90% (45 GB free)
   ```
5. En `main.py`, pasar `alert_queue` al `build_engine()` y NO drenarlo en el loop CLI (solo peek para mostrar).

**Test:** `tests/test_proactive_injection.py` — crear alert, ejecutar turno, verificar bloque en system prompt.

**Por qué:** Jarvis es proactivo. Sin esto Carter ignora el contexto del PC.

---

## Tarea 12 — App resolver dinámico (sin hardcode de idioma) ★ CRÍTICO universalidad

**Problema:** [app_resolver.py:30-41](Carter_v2/src/carter_v2/capabilities/app_resolver.py#L30-L41) tiene 10 nombres ingleses hardcodeados. "Bloc de Notas", "Editor", "Notepad" en alemán → fallan.

**Fix de raíz (cero diccionarios de traducción):**

1. Reemplazar `_REGISTRY` estático por resolver dinámico que use:
   - **Fuente 1 (preferente):** `Get-StartApps` vía PowerShell — devuelve apps del SO con su nombre LOCALIZADO + AppUserModelID (AppId) + ejecutable. Caché 5 minutos.
   - **Fuente 2:** `probe.snapshot().apps` — apps instaladas detectadas por el probe.
   - **Fuente 3 (último recurso):** intentar `Start-Process <raw>` directamente.

2. Algoritmo de resolución (`AppResolver.resolve_launch(raw)`):
   ```python
   raw_norm = raw.lower().strip()
   candidates = self._cached_start_apps()  # list[(name, exe, aumid)]
   # Match exacto por name lowercased
   exact = next((c for c in candidates if c.name.lower() == raw_norm), None)
   if exact: return exact.aumid_or_exe
   # Match contiene raw o raw contiene name
   sub = next((c for c in candidates if raw_norm in c.name.lower() or c.name.lower() in raw_norm), None)
   if sub: return sub.aumid_or_exe
   # Fuzzy match con difflib
   names = [c.name.lower() for c in candidates]
   best = difflib.get_close_matches(raw_norm, names, n=1, cutoff=0.6)
   if best:
       return next(c for c in candidates if c.name.lower() == best[0]).aumid_or_exe
   # Fallback: devolver raw para que Start-Process intente
   return raw
   ```

3. Lanzamiento: `Start-Process -FilePath "shell:appsfolder\<aumid>"` para apps Modern, o `os.startfile(exe)` para Win32. Detección automática.

4. **Cero entradas hardcodeadas en inglés.** El cache se construye del SO en runtime.

**Test:** `tests/test_app_resolver_dynamic.py` con `Get-StartApps` mockeado devolviendo "Bloc de notas", "Editor", "Calculator" — todos deben resolver sin hardcode.

**Por qué:** Universalidad. Funciona en cualquier SO Windows en cualquier idioma sin tocar código.

---

## Tarea 13 — Filesystem extendido

**En [filesystem.py](Carter_v2/src/carter_v2/capabilities/filesystem.py)** añadir acciones (todas con guard `Path.home()`):

- `list_directory(path, max_entries=100, include_hidden=False)` → entries con `{name, size, is_dir, modified_iso}`.
- `search_files(root, pattern, max_results=50)` → glob con `Path.rglob`. Pattern es glob simple (`*.txt`, `**/*.py`).
- `move(src, dst)` → `shutil.move`. Guard ambos paths.
- `copy(src, dst)` → `shutil.copy2` para archivos, `shutil.copytree` para dirs. Guard.
- `delete(path)` → marcado como **high-risk** (requiere approval). `Path.unlink` o `shutil.rmtree`.
- `get_stat(path)` → size, mtime, ctime, mime guess.

Registrar los 6 tools nuevos en `adapters/tools.py` con compact descriptions.

**Test:** `tests/test_filesystem_extended.py` cubriendo cada acción con tmpdir.

---

## Tarea 14 — System control (volume, brightness, dark mode, wifi)

**Crear `capabilities/media.py`** con tools (todos cross-checked con `next_step_hint` si la dep falta):

- `system_set_volume(level: int)` → `pycaw` (`AudioUtilities.GetSpeakers()`). 0-100.
- `system_get_volume()` → mismo.
- `system_mute(toggle: bool)` → idem.
- `system_set_brightness(level: int)` → WMI `WmiMonitorBrightnessMethods`.
- `system_get_brightness()` → idem.
- `system_set_dark_mode(enabled: bool)` → registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize\AppsUseLightTheme`.
- `system_get_dark_mode()` → idem.

**Crear `capabilities/network.py`:**

- `network_wifi_list()` → `netsh wlan show networks mode=Bssid` parsed.
- `network_wifi_connect(ssid)` → `netsh wlan connect name="<ssid>"` (asume perfil ya guardado).
- `network_wifi_disconnect()` → `netsh wlan disconnect`.
- `network_get_ip()` → `socket.gethostbyname(socket.gethostname())` + interface IPs.

Registrar tools en `tools.py`. Si falta `pycaw` o WMI, devolver `CapabilityResult(False, ..., next_step_hint="install pycaw: pip install pycaw")`. **Cero hardcode de idioma** en mensajes; el `next_step_hint` es metadata para el LLM.

**Test:** mocks de WMI/registry/netsh.

---

## Tarea 15 — Notificaciones (toast, TTS, sound)

**Crear `capabilities/notifications.py`:**

- `notify_toast(title: str, message: str, duration_seconds: int = 5)` → `win10toast` (añadir a deps si no está) o `winrt.Windows.UI.Notifications`.
- `notify_speak(text: str, voice: str | None = None, rate: int = 0)` → `pyttsx3` (ya en deps según el repo). Voz neutra del SO si no se especifica. **No detectar idioma del texto** — pyttsx3 elige automáticamente según las voces instaladas.
- `notify_sound(sound_name: str = "default")` → `winsound.PlaySound` con mapeo a constantes (`default`→`SystemDefault`, `error`→`SystemHand`, `asterisk`→`SystemAsterisk`).

Registrar 3 tools en `tools.py`. Compact descriptions ≤30 palabras cada una.

**Por qué:** Carter actualmente es invisible cuando el usuario no está mirando la terminal. Toast + TTS = Jarvis presencial.

---

## Tarea 16 — Watchdog/timeout por tool call ★ CRÍTICO

**En [agent.py loop principal](Carter_v2/src/carter_v2/turn/agent.py):**

1. Añadir campo `timeout_seconds: int = 30` a `ToolDefinition` en `adapters/tools.py`.
2. Tools lentos declaran timeout mayor:
   - `web_search`, `web_navigate`, `web_get_text`: 60s
   - `vision_describe`, `vision_find_element`: 45s
   - `download_url`: 120s
   - `terminal_run_command`: 30s
3. En el loop, ejecutar tool con `concurrent.futures.ThreadPoolExecutor`:
   ```python
   with ThreadPoolExecutor(max_workers=1) as ex:
       future = ex.submit(tool.execute, request)
       try:
           result = future.result(timeout=tool_def.timeout_seconds)
       except FuturesTimeout:
           future.cancel()
           result = CapabilityResult(
               False,
               f"Tool {tool_name} exceeded {tool_def.timeout_seconds}s timeout",
               next_step_hint="try a faster alternative tool or smaller scope",
           )
   ```
4. El timeout se incluye como evento en el ledger.

**Test:** `tests/test_tool_timeout.py` con un tool fake que duerme N+1 segundos.

---

## Tarea 17 — Verification post-acción ★ CRÍTICO confiabilidad

**Activar [verification/](Carter_v2/src/carter_v2/verification/):**

1. Definir `VerificationManager` (si no existe ya) con método `verify(tool_name, args, before_snapshot, after_snapshot) → VerificationResult(verified: bool, evidence: dict, hint: str | None)`.
2. Reglas estructurales por tool (sin keywords de idioma):
   - `app_open(target)` → verificar que después hay un proceso/ventana cuyo nombre matchea fuzzy con `target`.
   - `filesystem_write_text(path)` → verificar `Path(path).exists()` y `read_text()[:200]` matchea content esperado.
   - `process_stop_app(target)` → verificar que el proceso ya NO está en `psutil.process_iter()`.
   - `app_uninstall(name)` → verificar que el name desapareció de `probe.snapshot().apps`.
3. En el loop de agent.py, tras cada tool con `ok=True` que sea mutativo, llamar `verifier.verify(...)`. Si `verified=False`, marcar el ledger con `success_unverified` y añadir al hint del LLM:
   ```
   TOOL_REPORTED_OK_BUT_NOT_VERIFIED: app_open(Notepad) returned ok=True but no notepad.exe process appeared after 1s. The tool may have failed silently.
   ```
4. Tools NO mutativos (queries) saltan verificación.

**Test:** `tests/test_verification_post_action.py` con escenarios verified=True y verified=False.

**Por qué:** Sin verification, Carter cree todo lo que dice cualquier tool. Jarvis confirma con sus propios sentidos.

---

## Tarea 18 — Auto-identity de os.environ

**En [agent.py:_build_system_prompt](Carter_v2/src/carter_v2/turn/agent.py:98):**

Cambiar el fallback de `user_name`:
```python
user_ref = (
    user_name
    or (memory.get_user_name() if memory else None)
    or os.environ.get("USERNAME")
    or Path.home().name
    or "the user"
)
```

Así el primer turno con memoria vacía YA conoce al usuario por su username Windows.

**Test:** `tests/test_identity_autoload.py` con `USERNAME=usuario` y memoria vacía.

---

## Tarea 19 — Web cookies persistence

**En [web.py](Carter_v2/src/carter_v2/capabilities/web.py):**

1. Reemplazar `playwright.chromium.launch()` ad-hoc por contexto persistente:
   ```python
   state_path = Path.home() / ".carter" / "web_state.json"
   state_path.parent.mkdir(parents=True, exist_ok=True)
   context = browser.new_context(storage_state=str(state_path) if state_path.exists() else None)
   # ... navegación ...
   context.storage_state(path=str(state_path))
   ```
2. User-Agent realista (no "HeadlessChrome"): `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36`.
3. Caché de browser instance entre llamadas (evitar relanzar Chromium cada vez).

**Test:** `tests/test_web_cookies.py` con dos llamadas consecutivas verificando que `state.json` se persiste.

---

## Tarea 20 — `process_list` real

**En [process.py](Carter_v2/src/carter_v2/capabilities/process.py)** añadir acción `list`:

- `process_list(filter: str = "", max_results: int = 50)` → usar `psutil.process_iter(["pid","name","memory_info","cpu_percent"])`.
- Filtrar por substring case-insensitive en `name` si `filter` se pasa.
- Devolver `[{pid, name, memory_mb, cpu_percent}]` ordenado por `memory_mb` descendente.

Registrar como `process_list` en `tools.py`. Compact description.

**Por qué:** T11 funcionó pero vía workaround `terminal_run_powershell`. Tool nativo es más rápido y confiable.

---

## Tarea 21 — Allowlist de terminal

**En [terminal.py](Carter_v2/src/carter_v2/capabilities/terminal.py)** añadir a la allowlist de comandos read-only:

```
tasklist, wmic, where, whoami, hostname, ver, ipconfig, systeminfo, getmac, query
```

Estos comandos no mutan nada (son queries). Sin razón para bloquearlos en `terminal_run_command` cuando PowerShell ya permite todo.

**Test:** `tests/test_terminal_allowlist.py` verificando que `tasklist` no devuelve "no está en la lista".

---

## Tarea 22 — Validación de dependencias al arranque

**En [main.py](Carter_v2/src/carter_v2/main.py)** después del banner añadir health check no-bloqueante:

```python
def _runtime_health_check() -> dict[str, str]:
    checks = {}
    try:
        import playwright; checks["playwright"] = "ok"
    except ImportError:
        checks["playwright"] = "missing — web_search/web_navigate degradados"
    try:
        import pytesseract; pytesseract.get_tesseract_version(); checks["tesseract"] = "ok"
    except Exception as e:
        checks["tesseract"] = f"missing — vision_read_text degradado ({e})"
    try:
        import pycaw; checks["pycaw"] = "ok"
    except ImportError:
        checks["pycaw"] = "missing — system_set_volume degradado"
    # nvidia-smi
    import subprocess
    try:
        subprocess.run(["nvidia-smi", "--version"], capture_output=True, check=True, timeout=2)
        checks["nvidia-smi"] = "ok"
    except Exception:
        checks["nvidia-smi"] = "missing — system_get_gpu_info VRAM no disponible"
    return checks

# Imprimir en banner
checks = _runtime_health_check()
for name, status in checks.items():
    icon = "[OK]" if status == "ok" else "[!]"
    print(f"  {icon} {name}: {status}", file=out)
```

Inyectar este resultado al system prompt como `RUNTIME_DEPS:` (cap 200 chars) para que el LLM sepa qué tools están degradados.

---

## Tarea 23 — Skills accesibles vía tool

**En [capabilities/skills.py](Carter_v2/src/carter_v2/capabilities/skills.py)** o nuevo, exponer 3 acciones:

- `skill_list()` → `[{name, description}]` desde `SkillLibrary.list_file_skills(50)`.
- `skill_load(name)` → cuerpo completo del skill (cap 6000 chars).
- `skill_run(name, args="")` → ejecuta el skill como sub-prompt (igual que el dispatcher `/<name>` actual).

Registrar 3 tools en `tools.py`.

**Por qué:** SKILL.md inyecta ~50 chars al system prompt actualmente. Inútil. Con `skill_load(name)` el LLM puede consultar el skill completo bajo demanda.

---

## Validación obligatoria — Sesión 6

1. **Suite completa:** `python -m pytest Carter_v2/tests/ -q` → ≥1080 passed (suma tests nuevos), 0 failed nuevos.

2. **Probe extendido:** Re-correr `python Carter_v2/probe_carter.py` y verificar mejoras vs baseline Sesión 5:

| Test | Input | Baseline Sesión 5 | Target Sesión 6 |
|------|-------|-------------------|-----------------|
| T16+T17 | guardar+recordar color | memory_save llamado pero T17 no recordaba | T17 recuerda sin llamar memory_recall (auto-injection) |
| T10 | "Abre el Bloc de Notas" | aún fallaba en español por hardcode inglés | resuelve vía Get-StartApps localizado |
| T05 | "Lista archivos de Documentos" | no soportado | `filesystem_list_directory` <2s |
| nuevo | "Baja el volumen al 30%" | imposible | `system_set_volume(30)` |
| nuevo | "Notifícame cuando termine" | imposible | `notify_toast` o `notify_speak` |
| nuevo | tool cuelga | cuelga indefinido | timeout 30s + hint |
| nuevo | abre app inexistente | reporta ok=True | verification detecta no se abrió |

3. **Auditoría anti-hardcode (estricta):**
```
grep -rni "notepad\|chrome\|firefox\|spotify\|discord\|steam" \
  Carter_v2/src/carter_v2/capabilities/app_resolver.py \
  Carter_v2/src/carter_v2/capabilities/media.py \
  Carter_v2/src/carter_v2/capabilities/notifications.py \
  Carter_v2/src/carter_v2/capabilities/network.py
```
Solo debe matchear en docstrings de ejemplo, NUNCA como dato funcional para decisiones.

```
grep -rni "español\|english\|deutsch\|français\|hora\|time\|zeit\|heure" \
  Carter_v2/src/carter_v2/turn/ \
  Carter_v2/src/carter_v2/capabilities/
```
Solo en mensajes de output o tests, NUNCA como clasificador de input.

4. **Confirmación explícita en el reporte:**
   - "cero keywords de idioma añadidas a ningún clasificador en Sesión 6"
   - "AppResolver no contiene NINGÚN nombre de app hardcodeado — todo viene del SO"

---

## Reporte esperado Sesión 6

Al terminar, entrega:
- Lista de archivos tocados con +/- de líneas (esperado: ~25 archivos, +2000/-500 aproximado).
- Tests añadidos con nombre y qué verifican (≥10 tests nuevos).
- Output completo del `pytest` final.
- Resultados de las nuevas pruebas en probe_carter.py mostrando T10 resuelto sin hardcode.
- Confirmación explícita de las 2 reglas de auditoría.
- Lista de capabilities nuevas creadas (`media.py`, `network.py`, `notifications.py`).

---

## Recordatorio final — qué NO hacer en Sesión 6

- ❌ NO añadir listas de keywords de idiomas a ningún clasificador, planner, intent detector
- ❌ NO añadir nombres de apps hardcodeados ("notepad", "chrome", "bloc de notas", "editor"...) en app_resolver
- ❌ NO añadir ramas if/else basadas en idioma del input ("if 'hora' in text or 'time' in text...")
- ❌ NO retroceder sobre BrainRouter
- ❌ NO romper tests de Sesión 5
- ❌ NO inventar fixes — si algo no está claro en este prompt, inspecciona el código y pregunta al usuario antes de codificar

✅ Sí: el LLM decide. Las herramientas son universales. Los datos del SO están localizados nativamente. Carter es para todos los humanos.
