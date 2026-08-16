# Carter ≠ Jarvis aún — Análisis de raíz

Auditoría profunda del proyecto. Cada gap está respaldado por evidencia en el código **y confirmado por pruebas directas contra Carter con Qwen3:8b vía Ollama** (20 pruebas reales, 2026-04-18).

Reglas no negociables:
1. **Cero hardcode de idioma** — Carter es para todos los humanos. Nada de keyword lists en español/inglés/etc.
2. **Universal** — solo señales estructurales (regex de shell destructivo, formato de archivo, códigos HTTP) o decisiones del LLM.

---

## Resultados de las 20 pruebas directas

| ID | Categoría | Input | Tools llamados | Resultado | Veredicto |
|----|-----------|-------|---------------|-----------|-----------|
| T01 | Sistema/Hora | "¿Qué hora es?" | `terminal_run_command` x2 | "Ejecutable 'time' no está en la lista de comandos permitidos" | **GAP CRITICO** |
| T02 | Sistema/Hora | "What time is it right now?" | `terminal_run_command` | Reply: `'%time%'` — imprimió la variable literal | **GAP CRITICO** |
| T03 | Sistema/GPU | "¿Cuánta VRAM libre tengo?" | `system_get_gpu_info` | Respuesta parcial: detectó GPU pero no VRAM usada | **GAP PARCIAL** |
| T04 | Sistema/RAM | "¿Cuánta RAM usa el sistema?" | `terminal_run_command` | Funcionó vía PowerShell (workaround, 55s) | **WORKAROUND LENTO** |
| T05 | Archivos/Leer | "Lee el archivo JarvisGaps.md" | ninguno | "No tool was executed, so I cannot confirm a PC action." | **GAP CRITICO** |
| T06 | Archivos/Escribir | "Crea test_carter.txt" | `filesystem_write_text` x3 + terminal x2 | Falló: path hardcodeado a `C:\Users\usuario\` (username genérico) | **BUG CRITICO** |
| T07 | Portapapeles | "¿Qué tengo en el portapapeles?" | `desktop_clipboard_get` | Funcionó — tool existe en DesktopCapability | **OK (gap era falso)** |
| T08 | Web/Búsqueda | "Temperatura en Santiago de Chile" | `web_search` x5 + `web_open_url` | "No encontré resultados" — Google retorna 0 resultados con Playwright | **GAP REAL** |
| T09 | Web/Alemán | "Suche nach Bitcoin-Kurs" | `web_search` x3 + `web_open_url` | Mismo fallo que T08. Routing multilenguaje OK, búsqueda falla | **GAP REAL** |
| T10 | Apps/Abrir | "Abre el Bloc de Notas" | `app_open` x8 + `terminal_run_command` x3 | 322 segundos, 11 tools llamados, fallo total | **GAP CRITICO** |
| T11 | Apps/Estado | "¿Qué apps tengo abiertas?" | `terminal_run_powershell` | Funcionó vía PowerShell, lista correcta (99s) — workaround sin tool nativo | **WORKAROUND** |
| T12 | Apps/Desinstalar | "Desinstala paint.net" | `app_uninstall` + `terminal_run_command` x2 + `terminal_run_powershell` x2 | winget falló + `msiexec` bloqueado → **381s**, 5 tools, sin resultado | **GAP CRITICO** |
| T13 | Terminal | "Ejecuta echo hola mundo" | `terminal_run_command` | "Done." — funcionó correctamente | **OK** |
| T14 | Identidad | "¿Quién eres?" | ninguno | Respondió "Soy Carter" sin revelar Qwen — **185 segundos** | **OK pero MUY LENTO** |
| T15 | Capacidades | "¿Qué puedes hacer?" | ninguno | Lista genérica memorizada, no datos reales del registry | **GAP** |
| T16 | Memoria | "Recuerda que mi color fav es azul" | ninguno | "Mi color favorito también es el azul" — **no guardó nada** | **GAP CRITICO** |
| T17 | Memoria | "¿Cuál es mi color favorito?" | ninguno | "Mi color favorito es… un misterio. ¿Y el tuyo?" — no recordó nada de T16 | **GAP CRITICO** |
| T18 | Conversación | "Cuéntame un chiste" | ninguno | Funcionó — chiste correcto (96s) | **OK pero lento** |
| T19 | Conversación | "¿Cuánto es 2+2?" | ninguno | "2 + 2 es 4." — correcto, **91s** para un cálculo trivial | **OK pero 91s** |
| T20 | Sistema/Disco | "¿Cuánto espacio libre en C?" | `terminal_run_command` + `terminal_run_powershell` x4 | `fsutil` bloqueado → 4 intentos PowerShell → **291s** sin resultado claro | **GAP CRITICO** |

### Observaciones críticas de las pruebas

**Velocidad:** Las respuestas tardan entre 14s (portapapeles) y 322s (abrir notepad). Incluso cálculos triviales tardan 91s (T19: "2+2"), conversación pura 96-104s, y disco libre 291s. Qwen3:8b entra en modo `<think>` extenso antes de *cada* respuesta. El parámetro `think=False` de Ollama no está activado para ningún turno, incluyendo los puramente conversacionales.

**Looping de tools:** T10 llamó `app_open` 8 veces seguidas con el mismo argumento antes de escalar. El MAX_TOOL_ITERATIONS=25 no protege contra bucles del mismo tool.

**Username hardcodeado en filesystem:** T06 falló porque `filesystem_write_text` intentó escribir en `C:\Users\usuario\Desktop\` — el probe devuelve "usuario" como nombre genérico en lugar del nombre real del usuario Windows.

---

## Resumen ejecutivo

Carter tiene el esqueleto de un Jarvis (LLM como cerebro, 115 tools, ledger, verificación, approval, recovery). Las pruebas reales revelan **9 gaps** — 4 críticos, 3 parciales, 2 arquitecturales:

| # | Área | Confirmado por prueba |
|---|------|-----------------------|
| 1 | Capacidades base ausentes (hora, leer archivo) | T01, T02, T05 |
| 2 | `web_search` no devuelve resultados reales | T08, T09 |
| 3 | `app_open` loopea sin escalar (322s, 12 calls) | T10 |
| 4 | Memoria no persiste — el LLM no llama tools de memoria | T16 |
| 5 | Username genérico en probe → paths rotos | T06 |
| 6 | Latencia excesiva (15-185s por turno) | T04, T14 |
| 7 | `system_get_gpu_info` no devuelve VRAM usada | T03 |
| 8 | Auto-introspección recita, no consulta | T15 |
| 9 | Recovery sin anti-bucle por tool | T10 |

---

## GAP 1 — Faltan capacidades atómicas críticas

### 1a. No hay tool de fecha/hora ★ CONFIRMADO POR T01+T02
**Evidencia código:** `adapters/tools.py` — 0 entradas con `time`, `date`, `datetime`. `SystemProbe` no expone `get_time`.

**Evidencia prueba:**
- T01: "¿Qué hora es?" → intentó `terminal_run_command("time")` → bloqueado por policy (58s)
- T02: "What time is it right now?" → devolvió la variable `%time%` literal sin expandir (28s)

**Comportamiento real:** El LLM improvisa usando `terminal_run_command` porque no tiene otro recurso. La policy de comandos bloquea `time.exe`. Resultado: error o string literal inútil.

**Fix de raíz (sin hardcode):** Añadir `system_get_time` en `capabilities/probe.py` o nuevo `capabilities/clock.py` usando `datetime.now().astimezone()`. Devuelve `{iso, timezone, unix, date, time, weekday, tz_offset}`. El LLM decide cuándo llamarla — no hay keyword classifier.

### 1b. No hay `filesystem_read_text` ★ CONFIRMADO POR T05
**Evidencia código:** [filesystem.py:13](Carter_v2/src/carter_v2/capabilities/filesystem.py#L13) — `supports()` solo `{create_folder, write_text, exists}`.

**Evidencia prueba:**
- T05: "Lee el archivo JarvisGaps.md" → 0 tools llamados → "No tool was executed, so I cannot confirm a PC action." (52s)

**Comportamiento real:** El LLM no tiene ningún tool que pueda leer un archivo. Devuelve el mensaje del guard anti-alucinación (correcto) pero no puede intentar nada porque la herramienta no existe.

**Fix:** Añadir acción `read_text` a `FileSystemCapability` con el mismo guard de `Path.home()`. Cap a 100KB, parámetro `max_bytes`. Registrar como `filesystem_read_text`.

### 1c. Username genérico en probe rompe paths de escritura ★ CONFIRMADO POR T06
**Evidencia código:** `capabilities/probe.py` — `snapshot()` devuelve username genérico "usuario" en vez del nombre Windows real.

**Evidencia prueba:**
- T06: "Crea test_carter.txt en el escritorio" → intentó escribir en `C:\Users\usuario\Desktop\` (path inexistente) → falló 3 veces + 2 intentos PowerShell → 262s total

**Comportamiento real:** `Path.home()` en Python sí devuelve el path correcto, pero el probe/context inyecta "usuario" como username, y el LLM construye el path manualmente con ese string erróneo.

**Fix:** En `probe.py`, usar `os.environ.get("USERNAME") or Path.home().name` para el username real. Inyectarlo en el system context como `username: usuario` y `home: C:\Users\usuario`.

### 1d. `system_get_gpu_info` no devuelve VRAM usada ★ CONFIRMADO POR T03
**Evidencia prueba:**
- T03: "¿Cuánta VRAM libre tengo?" → llamó `system_get_gpu_info` → "RTX 4060 Ti detectada pero no se mostró uso de memoria"

**Fix:** Añadir campos `vram_used_mb`, `vram_free_mb`, `vram_total_mb` al resultado de `system_get_gpu_info` usando `nvidia-smi --query-gpu=memory.used,memory.free,memory.total --format=csv,noheader,nounits` vía `subprocess`.

### 1e. No hay tools de sistema básicos: RAM, disco, CPU
**Evidencia prueba:**
- T04: "¿Cuánta RAM usa el sistema?" → workaround vía `terminal_run_command` PowerShell (87s, frágil)
- T20: "¿Cuánto espacio libre en C?" → `fsutil` bloqueado por policy → 4 intentos `terminal_run_powershell` → 291s sin respuesta útil

**Fix:** Añadir `system_get_ram_info`, `system_get_disk_info(drive)`, `system_get_cpu_info` en `SystemCapability` usando `psutil` (ya instalado en el proyecto). Devuelven datos directos en <100ms, sin terminal, sin policy de comandos.

---

## GAP 2 — `web_search` no funciona con Google + Playwright

### 2a. Google bloquea Playwright headless ★ CONFIRMADO POR T08+T09
**Evidencia código:** [web.py:415-455](Carter_v2/src/carter_v2/capabilities/web.py#L415-L455) — busca selectores `div.g`, `h3`, `div.VwiC3b`. Google sirve HTML diferente a bots.

**Evidencia prueba:**
- T08: "Temperatura en Santiago de Chile" → 5 llamadas a `web_search` + `web_open_url` → "No encontré resultados" en todos los intentos (66s)
- T09: misma prueba en alemán — mismo fallo (29s)

**Comportamiento real:** Playwright sí carga Google, pero los selectores CSS no coinciden con el HTML anti-bot que Google sirve. El parser devuelve 0 resultados en vez de error claro.

**Fix de raíz (cadena de fallback, sin keywords):**
1. Playwright + Google (actual) — si 0 resultados:
2. `requests` a `https://html.duckduckgo.com/html/?q=<query>` con User-Agent real
3. `urllib` a `https://www.bing.com/search?q=<query>` con headers normales
Cada nivel solo se activa si el anterior devuelve `results=[]`. Sin clasificación de idioma. Devolver `data["backend_used"]` para diagnóstico.

### 2b. `vision_*` requiere OmniParser (sin fallback)
**Evidencia código:** [vision.py:82-130](Carter_v2/src/carter_v2/capabilities/vision.py#L82-L130). Si OmniParser local + HTTP fallan, no hay OCR alternativo.

**Fix:** Añadir Windows.Media.Ocr o pytesseract como fallback final.

### 2c. `terminal_run_command` bloqueado — LLM no conoce alternativas
**Evidencia prueba:** T01/T02 — `terminal_run_command("time")` bloqueado. El LLM reintentó el mismo comando varias veces sin escalar a `terminal_run_powershell`.

**Fix:** En el mensaje de error de `terminal_run_command` cuando está bloqueado por policy, incluir hint: `"try terminal_run_powershell instead"`. Así el LLM sabe escalar sin que le hardcodeen nada.

---

## GAP 3 — Recovery: looping sin anti-bucle + sin escalation chain

### 3a. Looping del mismo tool ★ CONFIRMADO POR T10
**Evidencia código:** [agent.py:959-1002](Carter_v2/src/carter_v2/turn/agent.py#L959-L1002). `RetryBudget(remaining=1)` solo aplica al recovery explícito. El loop principal (`MAX_TOOL_ITERATIONS=25`) no detecta `(tool_name, args_hash)` repetidos.

**Evidencia prueba:**
- T10: "Abre el Bloc de Notas" → `app_open` llamado 8 veces seguidas con el mismo o casi mismo argumento → 322 segundos, fallo total

**Dato adicional (batch 3):** T06 "Crea archivo en escritorio" → `filesystem_write_text` x7 → 359s → el sistema actual SÍ tiene detección de bucle ("Bucle detectado" en reply), pero solo actúa a las 7 iteraciones. Para entonces ya han pasado 360s. El umbral debe ser 3, no 7.

**Fix de raíz:** En el loop principal de `agent.py`, mantener `Counter[(tool_name, frozenset(args.items()))]`. Si el mismo `(tool, args)` se llama ≥3 veces, inyectar en el mensaje al LLM: `"LOOP_DETECTED: app_open('Bloc de Notas') has been called 3 times. Try a different tool or different arguments."` Sin clasificar idioma — solo contar llamadas idénticas.

### 3b. Sin escalation chain — alucinación de plan
**Evidencia previa:** "desinstala fall guys" → `app_uninstall` falla → LLM eligió `terminal_run_command("start Fall Guys")` — abrir el juego en vez de desinstalarlo.

**Evidencia T12:** "Desinstala paint.net" → `app_uninstall` (winget falla) → `terminal_run_command("msiexec")` (bloqueado) × 2 → `terminal_run_powershell` × 2 → **381s, 5 tools, 0 resultados**. Nunca intentó la chain visual (Settings → Apps).

**Fix de raíz:** Añadir `failure_chain: list[str] | None` a `ToolDefinition` como hint textual de qué intentar si falla. El LLM lee el hint y decide. Sin keywords, sin regex de idioma.

```python
# En tools.py:
ToolDefinition(
  name="app_open",
  failure_chain=["try terminal_run_command with 'start <app>'",
                 "try terminal_run_powershell with 'Start-Process <app>'"],
)
```

---

## GAP 4 — Memoria no funciona + Carter no se conoce a sí mismo

### 4a. Memoria no persiste nada ★ CONFIRMADO POR T16
**Evidencia código:** `MemoryCapability` existe pero no está en el registro de prueba básico. Cuando está disponible, el LLM no la invoca espontáneamente para guardar datos del usuario.

**Evidencia prueba:**
- T16: "Recuerda que mi color favorito es el azul" → 0 tools → "Mi color favorito también es el azul" (no guardó nada)
- T17 (turno siguiente): "¿Cuál es mi color favorito?" → 0 tools → "Mi color favorito es… un misterio. ¿Y el tuyo?" (no recordó nada de T16)

**Comportamiento real:** El LLM no tiene instrucción explícita en el system prompt de cuándo llamar `memory_save`. Sin esa instrucción, Qwen3 responde conversacionalmente. En el turno siguiente tampoco consultó memoria — el ciclo completo de guardar/recuperar está roto.

**Fix de raíz (dos partes):**
1. System prompt: añadir regla explícita — "If the user shares a personal fact or preference (name, favorite X, their PC config, etc.), call `memory_save` with key and value immediately."
2. Asegurar que `MemoryCapability` esté en el registry con tools `memory_save` y `memory_recall`.

### 4b. Auto-introspección recita en vez de consultar ★ CONFIRMADO POR T15
**Evidencia prueba:**
- T15: "¿Qué puedes hacer?" → 0 tools → lista genérica memorizada durante entrenamiento, no datos del registry real

**Fix de raíz:** Tool `meta_list_capabilities` que consulta `CapabilityRegistry` en tiempo real y devuelve lista real de namespaces y acciones. Sin keywords; el LLM lo llama cuando el usuario pregunta sobre capacidades.

### 4c. System prompt superficial — personalidad colapsa
**Evidencia código:** [agent.py:54-69](Carter_v2/src/carter_v2/turn/agent.py#L54-L69) — 6 líneas de reglas de output, sin identidad ni política de memoria.

**Evidencia prueba:** T14 ("¿Quién eres?") tardó 185 segundos — Qwen3 entró en modo razonamiento extenso porque el prompt no da una identidad clara que suprima esa incertidumbre.

**Fix:** Reescribir con secciones: identidad, capacidades de alto nivel, política de memoria, política de fallo, política de honestidad, formato. Neutral en idioma — solo la regla "responde en el idioma del usuario".

---

## GAP 5 — Observabilidad y skills muertos

### 5a. Heartbeat no llega al LLM
HEARTBEAT.md y el monitor proactivo corren, pero sus alertas no se inyectan en el contexto del próximo turno. El LLM no se entera que la GPU está al 95%.

**Fix:** Inyectar `recent_alerts` como bloque opcional del system prompt (cap 200 chars), igual que ya se hace con `system_probe`.

### 5b. Skills sistema dead
SKILL.md inyecta ~50 chars al prompt — efectivamente nada. Ningún tool lee la skill completa cuando se necesita.

**Fix:** Tool `skills_load(name)` que devuelve el contenido completo bajo demanda. El LLM lo llama cuando ve que el skill es relevante.

### 5c. Backend null sin warning visible
Si `LlamaCppBackend` no carga el modelo, `available=False` y Carter responde con el placeholder de NullAgentBackend sin que el usuario sepa por qué.

**Fix:** En `main.py`, si `backend.available is False` al arranque, imprimir línea roja explícita con la causa exacta y el path del GGUF esperado.

---

## GAP 6 — Catálogo de 115 tools ambiguo

**Evidencia:** Coexisten `app_open` y `process_start_app`, `desktop_screenshot` y `vision_*`, `web_open` y `web_navigate`. El LLM con n_ctx=8192 ya está al límite y debe *elegir* entre dos opciones casi idénticas.

**Impacto:** Selección errática observada en sesión real.

**Fix de raíz:** Auditar tools, marcar duplicados como `deprecated=True` y excluirlos del catálogo `compact`. No borrar para mantener tests pasando.

---

## GAP 7 — Errores no accionables

Muchos `CapabilityResult(False, ...)` devuelven `"error"` o `"Error en X: <traceback>"`. El LLM no sabe qué hacer con eso.

**Fix:** Cada error debe tener un campo `next_step_hint` (string libre) que el tool genera describiendo qué intentar. El LLM lo lee como hint, no como orden.

---

## Lo que NO vamos a hacer

- ❌ Añadir listas de keywords ("hora|time|heure|uhrzeit") a ningún clasificador
- ❌ Añadir ramas determinísticas que ejecuten antes del LLM
- ❌ Cualquier regla específica de un idioma o cultura
- ❌ Retroceder sobre la limpieza ya hecha en BrainRouter

Las únicas señales aceptables son **estructurales** (regex de shell destructivo, esquemas JSON, códigos de error de SO).

---

## GAP 8 — Latencia: Qwen3:8b + Ollama es demasiado lento

**Evidencia prueba (resumen de latencias):**

| Prueba | Input | Tiempo | Tools |
|--------|-------|--------|-------|
| T01 | "¿Qué hora es?" | 58s | 2 (fallidos) |
| T04 | "¿Cuánta RAM usa el sistema?" | 87s | 1 (workaround) |
| T07 | "¿Qué tengo en el portapapeles?" | 14s | 1 (exitoso) |
| T09 | búsqueda en alemán | 29s | 4 (todos fallidos) |
| T13 | "Ejecuta echo hola mundo" | 63s | 1 (exitoso) |
| T14 | "¿Quién eres?" | 185s | 0 (pura conversación) |
| T16 | "Recuerda color favorito" | 104s | 0 (pura conversación) |
| T19 | "¿Cuánto es 2+2?" | 91s | 0 (cálculo trivial) |
| T10 | "Abre el Bloc de Notas" | 322s | 12 (loop) |
| T12 | "Desinstala paint.net" | 381s | 5 (todos fallidos) |
| T20 | "¿Cuánto espacio en C?" | 291s | 5 (todos fallidos) |

**Causa raíz identificada:** Qwen3:8b con Ollama usa `think=True` por defecto — genera un bloque `<think>` completo antes del primer token útil en TODOS los turnos, incluyendo los triviales. Un "2+2" tarda 91s porque el modelo razona extensamente sobre cómo responder.

**Causa raíz:** Qwen3:8b vía Ollama no usa las capacidades de GPU correctamente, o el modelo entra en modo `<think>` extenso antes de cada respuesta. El modo `thinking=False` no está siendo forzado para turnos simples.

**Fix:**
1. Para conversación pura (`hint_no_tools=True`): forzar `think=False` en la llamada al backend Ollama.
2. Para tool calls simples: detectar si el reply incluye bloque `<think>` y truncarlo antes de procesar. [agent.py:89-108](Carter_v2/src/carter_v2/turn/agent.py#L89-L108) ya tiene `_strip_thinking_text` pero el bloqueo de 185s sugiere que el thinking ocurre en el backend antes del primer token.
3. Evaluar usar `qwen3:1.7b` o `qwen3:4b` para turnos de baja complejidad como `hint_no_tools`.

---

## Orden de prioridad para Codex (por impacto en experiencia Jarvis)

| Prioridad | Gap | Impacto |
|-----------|-----|---------|
| 🔴 1 | GAP 1a — `system_get_time` | Cualquier usuario pregunta la hora. Falla vergonzosa. |
| 🔴 2 | GAP 1b — `filesystem_read_text` | No puede leer ningún archivo. |
| 🔴 3 | GAP 1c — username genérico → paths rotos | Escritura de archivos falla con usuario real. |
| 🔴 4 | GAP 4a — memoria no persiste | "Recuérdame X" no hace nada. |
| 🔴 5 | GAP 2a — `web_search` sin resultados | Búsqueda web completamente rota con Google. |
| 🟠 6 | GAP 3a — anti-bucle de tools | `app_open` x8 en 322s es inaceptable. |
| 🟠 7 | GAP 4c — system prompt superficial | Memoria, identidad, política de fallo en un lugar. |
| 🟠 8 | GAP 1d+1e — GPU/RAM/disco vía psutil | Eliminar workarounds lentos con terminal. |
| 🟡 9 | GAP 8 — latencia thinking mode | Conversación en 185s es insoportable. |
| 🟡 10 | GAP 2c — hint en errores de terminal | LLM escala a PowerShell automáticamente. |
| 🟡 11 | GAP 3b — `failure_chain` en tool metadata | Recovery con plan correcto, no alucinado. |
| 🟢 12 | GAP 4b — `meta_list_capabilities` | "¿Qué puedes hacer?" con datos reales. |
| 🟢 13 | GAP 5 — heartbeat/skills al LLM | Proactividad real. |
| 🟢 14 | GAP 6 — deduplicar tools | Limpieza del catálogo. |

---

# AUDITORÍA ESTRUCTURAL PROFUNDA — cada detalle de Carter

Sesión 5 (Codex) cerró 9 de 14 gaps superficiales. Quedan **gaps estructurales más graves** detectados por inspección exhaustiva del código `Carter_v2/src/carter_v2/`. Este es el mapa completo.

## Resumen del estado tras Sesión 5

| Subsistema | Estado | Línea base |
|------------|--------|-----------|
| Capabilities atómicas (clock, RAM/disco/GPU, read_text) | ✅ Implementado | Codex Sesión 5 |
| System prompt con identidad/memoria/honestidad | ✅ Implementado | [agent.py:54-92](Carter_v2/src/carter_v2/turn/agent.py#L54-L92) |
| `think=False` para conversación | ✅ Implementado | Codex Sesión 5 |
| Anti-bucle por (tool, args) | ✅ Implementado | Codex Sesión 5 |
| `failure_chain` en metadata de tools | ✅ Implementado | Codex Sesión 5 |
| `web_search` con cadena DDG/Bing | ✅ Implementado | Codex Sesión 5 |
| `meta_list_capabilities` | ✅ Implementado | [meta.py](Carter_v2/src/carter_v2/capabilities/meta.py) |
| **Memoria inyectada en cada turno** | ❌ Roto — solo vía `memory_recall` que el LLM olvida llamar | [agent.py:765-768](Carter_v2/src/carter_v2/turn/agent.py#L765-L768) |
| **Heartbeat alerts → LLM** | ❌ Drain a CLI, nunca al contexto del LLM | [main.py:684-686](Carter_v2/src/carter_v2/main.py#L684-L686) |
| **App resolver dinámico** | ❌ Hardcode 10 nombres en inglés | [app_resolver.py:30-41](Carter_v2/src/carter_v2/capabilities/app_resolver.py#L30-L41) |
| **Filesystem list/search/move/copy/delete** | ❌ Solo create_folder/write_text/read_text/exists | [filesystem.py:13](Carter_v2/src/carter_v2/capabilities/filesystem.py#L13) |
| **System control (volume/brightness/wifi/dark)** | ❌ No existen | — |
| **Notificaciones (toast/TTS/sound)** | ❌ No existen | — |
| **Watchdog/timeout por tool call** | ❌ El LLM puede colgar indefinido | [agent.py loop](Carter_v2/src/carter_v2/turn/agent.py) |
| **Verification post-acción** | ❌ Existe `verification/` dir pero sin VerificationManager activo | [verification/](Carter_v2/src/carter_v2/verification/) |
| **process_list real** | ❌ Solo window_list workaround | [process.py](Carter_v2/src/carter_v2/capabilities/process.py) |
| **tasklist en allowlist** | ❌ Bloqueado por terminal policy | [terminal.py allowlist](Carter_v2/src/carter_v2/capabilities/terminal.py) |
| **Validación de deps al arranque** (Playwright, OmniParser, pytesseract) | ❌ Falla silenciosa | — |
| **Skills en catálogo de tools** | ❌ SKILL.md inyecta ~50 chars al prompt, dead | [main.py:760-792](Carter_v2/src/carter_v2/main.py#L760-L792) |
| **Identidad auto-cargada de os.environ + memoria** | ⚠️ Parcial — username sí, pero no carga `user_name` de memoria al primer turno | [agent.py:756](Carter_v2/src/carter_v2/turn/agent.py#L756) |
| **Web cookies persistencia + captcha** | ❌ Cada `web_search` crea un context nuevo | [web.py](Carter_v2/src/carter_v2/capabilities/web.py) |

---

## Estructura completa de Carter — qué hay, qué falta

### `capabilities/` — 22 capabilities registradas

| Capability | Estado | Tools expuestos | Gap estructural |
|-----------|--------|-----------------|-----------------|
| `clock.py` | ✅ Nuevo | `system_get_time` | — |
| `meta.py` | ✅ Nuevo | `meta_list_capabilities`, `meta_describe_tool` | — |
| `memory.py` | ⚠️ Parcial | `memory_save`, `memory_recall` | LLM rara vez los llama; no auto-inyecta |
| `system.py` | ⚠️ Parcial | `system_get_ram_info`, `system_get_disk_info`, `system_get_gpu_info`, `system_get_cpu_info` | Falta `set_volume`, `set_brightness`, `set_dark_mode`, `wifi_*`, `bluetooth_*` |
| `filesystem.py` | ⚠️ Mínimo | `create_folder`, `write_text`, `read_text`, `exists` | Falta `list_directory`, `search_files`, `move`, `copy`, `delete`, `stat`, `get_size` |
| `process.py` | ⚠️ Workaround | `process_start_app`, `process_stop_app`, `process_get_app_status` | Falta `process_list` real (con CPU/RAM/PID por proceso) |
| `terminal.py` | ⚠️ Restrictivo | `terminal_run_command`, `terminal_run_powershell` | Allowlist no incluye `tasklist`, `wmic`, `where`, `whoami`. PowerShell sin restricción → desbalance |
| `web.py` | ⚠️ Frágil | `web_search`, `web_navigate`, `web_open_url`, `web_get_text`, `web_close_tabs` | Sin cookie persistence, sin captcha handling, Playwright se reinicia cada call |
| `vision.py` | ⚠️ Opcional | `vision_describe`, `vision_read_text`, `vision_find_element` | OmniParser silencioso si falla. pytesseract no validado al arranque |
| `desktop.py` | ✅ OK | `desktop_screenshot`, `desktop_clipboard_get`, `desktop_clipboard_set` | — |
| `window.py` | ✅ OK | `window_list`, `window_focus`, `window_minimize`, `window_close` | — |
| `ui.py` | ⚠️ Parcial | UIA queries | UIA falla en CEF (Steam/Discord/Spotify) — requiere fallback chromium |
| `gui_agent.py` | ⚠️ Parcial | `gui_do` | Click no funciona en CEF sin AttachThreadInput+mouse_event |
| `input.py` | ✅ OK | `input_type`, `input_press_key` | — |
| `download.py` | ✅ OK | `download_url` | — |
| `office.py` | ✅ OK | COM Word/Excel/PowerPoint | — |
| `steam.py` | ⚠️ Específico | `steam_open_game`, `steam_close` | Lista de juegos hardcodeada; no descubre Steam library dinámicamente |
| `taskman.py` | ✅ OK | `task_list`, `task_cancel` | — |
| `heartbeat.py` | ❌ Inerte | — | Existe pero nada lo lee |
| `skills.py` | ❌ Inerte | — | SkillsCapability registrada pero no expone tools |
| `probe.py` | ✅ OK | (snapshot via context) | — |
| `screen_cache.py` | ✅ OK | (cache interno) | — |

**Faltan capabilities completas:**
- `notifications.py` — toast (Windows.UI.Notifications), TTS (pyttsx3 ya en deps), sound (winsound)
- `network.py` — wifi list/connect/disconnect, bluetooth toggle, ping, DNS lookup
- `media.py` — system volume, mute, brightness, dark mode toggle
- `calendar.py` — Outlook/Google Calendar (con OAuth)
- `email.py` — Outlook/Gmail send/read
- `screenshot_diff.py` — comparar antes/después de cada acción para verificación visual

### `turn/` — Lógica del agente

| Archivo | Estado | Gap |
|---------|--------|-----|
| `agent.py` | ⚠️ Funcional | Sin watchdog por tool. Sin retry exponencial. Memoria larga no inyectada |
| `engine.py` | ✅ OK | — |
| `brain_router.py` | ✅ OK | Solo `_HIGH_RISK_RE` (correcto) |
| `perception.py` | ⚠️ Existe | No claro qué consume su output |
| `llama_backend.py` | ✅ OK | — |
| `ledger.py` | ✅ OK | ActionLedger anti-alucinación funcional |
| `cloud_fallback.py` | ✅ OK | — |

### `session/`

| Archivo | Estado | Gap |
|---------|--------|-----|
| `memory.py` (PersistentMemory) | ⚠️ | `long_term_context()` existe pero **no se inyecta en cada turno** del LLM |
| `proactive.py` (ProactiveMonitor) | ⚠️ | Genera `AlertQueue` pero el agent.py no la lee |
| `context_window.py` | ✅ OK | — |
| `observer.py` | ✅ OK | — |
| `policy.py` (approval) | ✅ OK | — |
| `skills.py` (SkillLibrary) | ⚠️ | Skills viven en disco pero no aparecen en tool catalog |
| `lessons.py` | ⚠️ | Se guardan errores pero no se inyectan en futuros prompts |
| `critic.py` | ⚠️ | LLM-as-judge para skills, pero no se ve uso real en run |

### `verification/`
Directorio existe pero VerificationManager nunca se invoca tras una acción. Sin diff de estado pre/post → Carter no sabe si una acción tuvo efecto real más allá del `ok=True` del tool. **Crítico para Jarvis confiable.**

### `recovery/`
Existe pero solo se invoca con `RetryBudget(remaining=1)` en el loop principal. Sin estrategia adaptativa por tipo de error.

### `interfaces/`
Discord, Slack, Telegram, HTTP gateway: implementados pero opt-in vía env vars. Sin documentación visible al usuario sobre cómo activarlos.

### `plugins/`
Sistema de carga existe pero ningún plugin de ejemplo. Sin docs.

---

## GAP 9 — Memoria larga no se inyecta en cada turno (CRÍTICO)

**Evidencia código:** [agent.py:765-768](Carter_v2/src/carter_v2/turn/agent.py#L765-L768) — el agent solo añade al system prompt el string `"Memory store available: use memory_recall before answering stored user facts."`. No inyecta los datos reales.

**Comportamiento esperado:** En cada turno, leer `memory.long_term_context(max_chars=600)` y añadirlo como bloque `<user_known_facts>` al system prompt. Así el LLM YA tiene la información sin necesidad de llamar `memory_recall`.

**Por qué importa:** El LLM olvida llamar `memory_recall`. Con la inyección automática nunca falla en consultas como "¿cuál es mi color favorito?" porque el dato YA está en el prompt.

**Fix de raíz:** En `_build_system_prompt(user_name, memory)`, después del bloque base añadir si `memory` no es None y `len(facts) > 0`:
```
KNOWN FACTS ABOUT USER:
- favorite_color: blue
- gpu: RTX 4060 Ti
- prefers_language: spanish
```

---

## GAP 10 — Heartbeat/proactividad muerta para el LLM (CRÍTICO)

**Evidencia código:** [main.py:684-686](Carter_v2/src/carter_v2/main.py#L684-L686) — `for alert in alert_queue.drain(): print(...)`. El alert se imprime al CLI y se descarta. **El LLM nunca se entera.**

**Comportamiento esperado:** Los alerts del ProactiveMonitor (GPU 95%, disco 90%, batería 5%, app crasheada) deben inyectarse al system prompt del próximo turno como bloque `<recent_system_events>`.

**Fix de raíz:**
1. `AlertQueue` debe persistir últimos N alerts (no descartarlos al drain).
2. `_build_system_prompt(..., recent_alerts=alert_queue.peek(5))` añade bloque opcional.
3. El LLM puede mencionarlos proactivamente o ignorarlos según relevancia al input del usuario.

---

## GAP 11 — App resolver hardcodeado en inglés (CRÍTICO universalidad)

**Evidencia código:** [app_resolver.py:30-41](Carter_v2/src/carter_v2/capabilities/app_resolver.py#L30-L41) — `_REGISTRY` con 10 entradas en inglés (`"notepad"`, `"chrome"`, `"firefox"`...).

**Comportamiento real:** "Abre el Bloc de Notas" → app_resolver no encuentra "bloc de notas" → falla. "Öffne den Editor" → mismo problema en alemán.

**Fix de raíz (sin hardcode de idioma):**
1. Resolver dinámico que use `probe.snapshot().apps` (lista REAL de apps instaladas) más fuzzy match (`difflib.get_close_matches`).
2. Para nombres ejecutables nativos del SO: usar `Get-StartApps` (PowerShell) que devuelve nombre localizado + AppUserModelID. Estos nombres ya vienen en el idioma del SO del usuario.
3. Si fuzzy match no encuentra, intentar `Start-Process <raw>` directamente (Windows resuelve por si solo en muchos casos).
4. **Cero diccionarios de traducción.** Los nombres vienen del SO o del fuzzy match contra apps reales.

---

## GAP 12 — Sin tools de filesystem básicos

**Tools que faltan en `filesystem.py`:**
- `filesystem_list_directory(path, max_entries=100)` → entries con name/size/is_dir/modified
- `filesystem_search_files(root, pattern, max_results=50)` → glob con `Path.rglob`
- `filesystem_move(src, dst)` → `shutil.move` con guard de `Path.home()`
- `filesystem_copy(src, dst)` → `shutil.copy2` con guard
- `filesystem_delete(path, confirm=True)` → `Path.unlink` o `shutil.rmtree`, requiere approval
- `filesystem_get_stat(path)` → size, mtime, ctime, owner

**Por qué:** Sin estos, "lista los archivos de Documentos" o "borra ese .tmp" obliga al LLM a ir a `terminal_run_command` (lento, frágil, policy-restricted).

---

## GAP 13 — Sin tools de control del sistema operativo

**Tools que faltan (capability nueva `media.py` o `system.py` extendida):**
- `system_set_volume(level: 0-100)` → `pycaw` (ya disponible) o COM
- `system_mute(toggle: bool)` → idem
- `system_set_brightness(level: 0-100)` → WMI `WmiMonitorBrightnessMethods`
- `system_set_dark_mode(enabled: bool)` → registry `HKCU\...\AppsUseLightTheme`
- `system_wifi_list_networks()` → `netsh wlan show networks`
- `system_wifi_connect(ssid, password)` → `netsh wlan connect`
- `system_bluetooth_toggle(enabled)` → COM Windows.Devices.Radios

**Por qué:** Jarvis controla el ambiente. Sin esto, Carter no puede "baja el volumen", "modo oscuro", "conéctate al wifi de la oficina".

---

## GAP 14 — Sin notificaciones salientes

**Tools que faltan (capability nueva `notifications.py`):**
- `notify_toast(title, message, icon=None)` → `winrt.Windows.UI.Notifications` o `win10toast`
- `notify_speak(text, voice=None)` → `pyttsx3` (ya en deps) o Windows.Media.SpeechSynthesis
- `notify_sound(sound_name)` → `winsound.PlaySound` con SystemDefault, etc.

**Por qué:** Jarvis habla, alerta, notifica. Carter solo escribe en CLI. Sin TTS/toast Carter es invisible cuando el usuario no está mirando la terminal.

---

## GAP 15 — Sin watchdog por tool call

**Evidencia:** El loop principal de agent.py llama `tool.execute(request)` sin timeout. Si `web_search` cuelga 5 minutos en Playwright, Carter cuelga 5 minutos.

**Fix de raíz:**
1. Cada `ToolDefinition` declara `timeout_seconds: int = 30` por defecto. Tools lentos (vision, web_search) declaran timeouts mayores.
2. En el loop, ejecutar tool con `concurrent.futures.ThreadPoolExecutor` y `.result(timeout=tool.timeout_seconds)`.
3. Si timeout: cancelar future, devolver `CapabilityResult(False, "Timeout exceeded", next_step_hint="try a faster alternative tool")`.

---

## GAP 16 — Sin verification post-acción

**Evidencia:** Carpeta [verification/](Carter_v2/src/carter_v2/verification/) existe pero ninguna llamada en agent.py la usa.

**Comportamiento esperado:** Tras cualquier acción mutativa (`app_open`, `filesystem_write_text`, `process_stop_app`), el VerificationManager debería:
1. Tomar `snapshot_before` (subset relevante: ventanas, archivos, procesos según el tool).
2. Esperar 500ms.
3. Tomar `snapshot_after`.
4. Calcular diff y devolver `verified: bool` + `evidence`.
5. Si `verified=False`, marcar el ledger como `success_unverified` para que el LLM lo sepa.

---

## GAP 17 — Errores de runtime sin contexto suficiente

Cuando un tool lanza excepción no capturada, el LLM recibe un `Error: <traceback>` poco accionable. Falta:
1. Sanitización de tracebacks (sin paths absolutos del sistema, sin info sensible).
2. `error_category: enum` (`PERMISSION_DENIED`, `NOT_FOUND`, `TIMEOUT`, `NETWORK`, `INVALID_ARG`).
3. Hints específicos por categoría inyectados al `next_step_hint`.

---

## GAP 18 — Identity auto-load incompleto

**Evidencia código:** [agent.py:756](Carter_v2/src/carter_v2/turn/agent.py#L756) — `user_name` se pasa a `_build_system_prompt`. Pero su origen es el `memory.get_user_name()` que solo retorna algo si el usuario dijo "me llamo X" antes (regex en main.py).

**Gap:** En el primer turno con memoria vacía, Carter no sabe el nombre del usuario aunque exista en `os.environ.get("USERNAME")`.

**Fix:** En `_build_system_prompt`, fallback chain: `memory.get_user_name() or os.environ.get("USERNAME") or Path.home().name`.

---

## GAP 19 — Skills disconnected del catálogo

SkillLibrary y SkillsCapability existen. SKILL.md inyecta ~50 chars al prompt. Pero **ningún tool del catálogo permite al LLM listar/cargar/ejecutar skills**.

**Fix:**
- `skill_list()` → lista nombres y descripciones cortas.
- `skill_load(name)` → devuelve cuerpo completo del skill bajo demanda.
- `skill_run(name, args)` → ejecuta el skill como sub-turno.

---

## GAP 20 — Web sin cookies persistence

**Evidencia código:** Cada llamada a `web_search` crea un nuevo Playwright context. No hay `storage_state.json` persistente. Resultado: cada búsqueda parte de cero, los servicios la marcan como bot, captchas más frecuentes.

**Fix:** Persistir context state en `~/.carter/web_state.json`, reutilizar entre llamadas. Cookies, localStorage, sesiones.

---

## GAP 21 — `tasklist`, `wmic`, `where` bloqueados por terminal allowlist

**Evidencia:** T11 usó `terminal_run_powershell` (no restricted) en vez de `terminal_run_command` con `tasklist` (restringido). Esto es asimétrico — PowerShell permite todo, CMD restringe.

**Fix:** Añadir a allowlist de `terminal.py`: `tasklist, wmic, where, whoami, hostname, ver, ipconfig` (read-only commands).

---

## GAP 22 — Sin validación de dependencias al arranque

**Evidencia:** Si Playwright no está instalado, primer `web_search` falla con error críptico. Si OmniParser no carga, primer `vision_describe` falla. Si pytesseract falta, OCR falla. Sin validación previa.

**Fix:** En `main.py` antes del REPL, ejecutar health check ligero:
- `import playwright; playwright.sync_api.sync_playwright().start().chromium.executable_path` → ok/missing
- `import pytesseract; pytesseract.get_tesseract_version()` → ok/missing
- OmniParser: HEAD a localhost:9001 si configurado
- nvidia-smi presence
- Imprimir tabla "Subsistema | Estado" al banner.
