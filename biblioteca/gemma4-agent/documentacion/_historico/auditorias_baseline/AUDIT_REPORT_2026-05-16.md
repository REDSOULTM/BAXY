# Auditoría Carter Agent — 2026-05-16

Auditor: Claude Opus 4.7 (read-only). Sin edits. Pytest corrido en local.

## Resumen ejecutivo

- **N findings totales: 13** — 5 ALTO, 5 MEDIO, 3 BAJO
- **Top 3 a arreglar ya:**
  1. `player_started=True` promovido global cuando no hay confirmación de playback ([F-001](#f-001-player_startedtrue-mentiroso-en-detail_page_reached)).
  2. "Hecho/Listo …" se emite con `tool_events=0` en 17 de 25 casos en últimos 1000 traces (mentira sistemática) — el promise guard NO los agarra ([F-002](#f-002-promise-guard-incompleto-y-no-dispara-retry)).
  3. `_ensure_cdp_browser` mata TODOS los procesos de Opera con `Stop-Process -Force` sin cierre suave ni respeto por múltiples perfiles, y solo detecta pytest ([F-003](#f-003-kill-opera-no-graceful-y-detecta-solo-pytest)).
- **Cobertura:** áreas 1–12 chequeadas (selectores DOM, player_started, promise guard, mode selection, inherit-tools, _BROWSER_SESSIONS, _ensure_cdp_browser, rescue parser, locales, system prompt size, tests, traces). Pendientes: probe en vivo de selectores (requeriría arrancar browser — fuera de read-only); revisión del executor real de `browser_real` (action=`fill/click`) y de `verifiers.py` semántico (sólo se vio uso indirecto).

---

## Findings de riesgo ALTO

### F-001: `player_started=True` mentiroso en `detail_page_reached`

- **Archivo:** [gemma4_agent/domain_tools.py:6627-6646](gemma4_agent/domain_tools.py#L6627-L6646)
- **Snippet:**
```python
    # 7. Click play button.
    play_res = _try_selectors("click", selectors_play, timeout_sec=10)
    if play_res["ok"]:
        ...
    # Llegamos al detail page pero no encontramos un Play button explicito.
    # En la mayoria de plataformas el detail page YA auto-reproduce (Prime),
    # o el titulo abre directo al player (Netflix /watch/). Marcamos como
    # exito best-effort — el user lo ve en pantalla.
    return {
        "player_started": True,  # promovido: detail page reached via CDP
        "attempted_play": True,
        "steps": steps + ["detail_page_reached_no_explicit_play_button"],
        "abort_reason": None, "via_cache": False,
        "detail_url": detail_url,
    }
```
- **Por qué es riesgo alto:** este return es global — corre para Netflix, Disney+, HBO Max, Prime Video. La justificación ("Prime ya auto-reproduce, Netflix click va directo a /watch/") solo es cierta para los providers con `click_card_starts_playback=True` (Prime). Pero el código llega aquí justamente cuando ese flag es `False` y el play button click falló. En Disney+/HBO Max/Netflix detail-page-without-play-button NO equivale a reproducción.
- **Cómo se manifiesta para el user:** dice "Disney+: playing — title clicked, Play pressed" (línea 6942) cuando el video NO sonó. El user oye la confirmación, mira la pantalla, ve un poster estático. Romperse: el caller `_launch_streaming` consume `played` directamente (línea 6898), por lo que `played=True` se propaga al footer del agente y a `mission_goal`. En el log audit 7/21 finals tienen `mission_status=FAILED` reason "mission expected tool actions but no tool ran" — patrón compatible con esto.
- **Test que lo confirma:** path manual: en Disney+, intentar play de un título cuya página detalle aún esté cargando. `selectors_play` falla por timeout, función retorna `player_started=True`, `media_tool` reporta éxito. No hay test automatizado que cubra este path (los tests de streaming mockean `executor` y no ejercitan la rama "selectors_play todos fallaron").

### F-002: Promise guard incompleto y no dispara retry

- **Archivo:** [gemma4_agent/agent.py:1992-2041](gemma4_agent/agent.py#L1992-L2041), patrones en [agent.py:2010-2020](gemma4_agent/agent.py#L2010-L2020)
- **Snippet:**
```python
promise_patterns = (
    "buscare", "buscaré", "voy a buscar", "voy a investigar",
    "voy a consultar", "voy a revisar", "voy a chequear",
    "te proporcionare", "te proporcionaré", "te dire", "te diré",
    "te respondere", "te responderé", "te informare", "te informaré",
    "te traere", "te traeré", "te dare", "te daré la informacion",
    "permiteme buscar", "permíteme buscar",
    "dame un momento", "un momento por favor",
    "i'll search", "i'll look", "let me search", "let me check",
    "i will find", "i'll find", "i'll get",
)
...
replacement = (
    "Necesito un segundo intento para traer la info. Repetí la "
    "pregunta una vez más por favor."
)
if len(content.strip()) <= 100:
    return replacement
# Reply tenia mas contenido — solo strippear la promesa.
return content   # ← NO se strippea; se devuelve igual
```
- **Por qué es riesgo alto:**
  1. **El guard solo reemplaza texto, NO dispara retry/tool execution.** El comentario menciona "The next user turn will inherit prev tools…" — pero eso requiere que el user HABLE OTRA VEZ. Mientras tanto el user ya recibió "Necesito un segundo intento, repetí la pregunta" en vez del dato. UX degradado igual.
  2. **Patrones faltantes:** "te aviso", "te confirmo", "te paso", "te mando", "te muestro", "lo reviso", "lo verifico", "déjame ver", "ahora te traigo", "ya te digo", "te explico en un momento", "ya mismo".
  3. **El branch del `else` (línea 2041) hace `return content` sin strippear la promesa.** El comentario dice "solo strippear" pero el código no hace nada — devuelve el original. Es código muerto que confunde + bug de implementación.
  4. **Pattern más grave que NO está cubierto:** "Hecho: …" / "Listo, …" / "Registré tu rutina y la ejecuté" — confirmaciones FALSAS con `tool_events=0`. En traces últimos 1000 hay 17/25 (68%) "Hecho/Listo" que son mentiras (tool_events=0). El guard actual no toca este tipo de claim.
- **Cómo se manifiesta para el user:** user pregunta algo que requiere búsqueda. El LLM dice "te informaré" (no agarrado), o "Hecho: agendé tu evento" (no agarrado, mentira). Agente se cierra el turn sin ejecutar nada. User en voz: "¿y entonces?". 0 `promise_without_action_caught` en últimos 200 traces pese a 7 mission FAILED — el guard es prácticamente inerte.
- **Test que lo confirma:** `gemma4_agent/test_promise_guard.py` existe; no lo ejecuté en aislado pero pytest pasó. Trace pattern:
  - `tool_events=0` + reply "Hecho: registre tu rutina y la ejecute" (3 ocurrencias en window de 200)
  - `tool_events=0` + reply "Gemma 4 es un modelo de lenguaje grande desarrollado por Google DeepMind" (deber haber sido web research)

### F-003: Kill Opera no graceful y detecta solo pytest

- **Archivo:** [gemma4_agent/domain_tools.py:6300-6391](gemma4_agent/domain_tools.py#L6300-L6391)
- **Snippet:**
```python
    if (os.environ.get("GEMMA4_DISABLE_AUTO_CDP_LAUNCH") == "1"
            or "PYTEST_CURRENT_TEST" in os.environ):
        return {"cdp_ok": False, "action": "disabled", ...}
    ...
    try:
        running = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
              f"Get-Process {proc_name} -ErrorAction SilentlyContinue | "
              "Select-Object -ExpandProperty Id"], ...)
        pids = [p.strip() for p in (running.stdout or "").splitlines() if p.strip()]
        if pids:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                  f"Get-Process {proc_name} -ErrorAction SilentlyContinue | "
                  "Stop-Process -Force"], ...)
            relaunched = True
            _time.sleep(1.5)  # let OS clean up handles
    except Exception:
        pass
```
- **Por qué es riesgo alto:**
  1. **`Stop-Process -Force` es kill duro** — no envía WM_CLOSE, no espera shutdown gracefull. Opera/Chrome pierden datos de forms parcialmente llenados, downloads sin terminar, pestañas con audio que no quedan en session restore.
  2. **Mata TODAS las instancias del browser.** Si user tiene 2 perfiles abiertos (perfil personal + perfil work), o un PWA empaquetado con Opera GX, se cae todo de una.
  3. **Pytest detection es solo `PYTEST_CURRENT_TEST`.** unittest puro, nose, runs interactivos (REPL/jupyter), Quokka, smoke scripts — ninguno setea esa env var. Cualquier script que importe `domain_tools` y dispare playback durante dev mata el browser del dev. El comentario explícitamente reconoce este riesgo: "Para no matar Opera del dev cada vez que corren tests" — el fix está incompleto.
  4. **Errores del Stop-Process se silencian** (`except Exception: pass`). Si el Stop falla porque hay un handle abierto (download en curso), `relaunched=True` queda mintiendo, y el siguiente `Popen` lanza una segunda instancia que peleará por el puerto 9222.
- **Cómo se manifiesta para el user:** user pide "ponme Loki en Disney+". Si CDP no está activo, el agente cierra todas las pestañas que tenía el user abiertas con Stop-Force (puede perder docs, mails sin enviar, código en CodeSandbox). Adicional: si tenía 2 perfiles, se le cae el del trabajo también. Documentado parcialmente en feedback [no_user_setup_burden](memory/feedback_no_user_setup_burden.md) pero la implementación elegida es destructiva.
- **Test que lo confirma:** no hay test que ejercite esta función con Opera viva (pytest la cortocircuita por env). Path manual: ejecutar `python -c "from gemma4_agent.domain_tools import _ensure_cdp_browser; print(_ensure_cdp_browser())"` con Opera GX abierto sin CDP — el browser muere.

### F-004: Mode selection trunca explicaciones/comparaciones/listas a 384 tokens

- **Archivo:** [gemma4_agent/modes.py:86-99](gemma4_agent/modes.py#L86-L99) (fast_action), [modes.py:131-158](gemma4_agent/modes.py#L131-L158) (`_infer_mode` markers)
- **Snippet:**
```python
sequencing_markers = (" luego ", " despues ", " entonces ", " primero ", ...)
action_markers = (" abre ", " ve a ", " busca ", " pon ", " escribe ", ...)
sequence_score = sum(1 for marker in sequencing_markers if marker in low)
action_score = sum(1 for marker in action_markers if marker in low)
if sequence_score or action_score >= 2 or len(text) > 180:
    return "deep_action"
return "fast_action"  # 384 tokens max
```
- **Por qué es riesgo alto:** simulación mental (sin LLM, solo el código):
  - "orden cronológico de la saga Batman Arkham" → 0 markers, len=44 → **fast_action 384 tok**. Una lista cronológica de 6 juegos necesita >384 tok para incluir nombres + año + plataforma.
  - "comparame Disney+ y Netflix" → 0 markers, len=28 → **fast_action 384 tok**. Comparación tabla mental se trunca.
  - "explicame cómo funciona CDP" → 0 markers, len=27 → **fast_action 384 tok**. Una explicación técnica de 2-3 párrafos se corta.
  - "qué hora es" → fast_action 384 tok → OK (respuesta corta).
  - "cuándo salió GTA 5" → fast_action 384 tok → OK (fecha).
  - "ponme Loki" → fast_action → OK acción rápida (aunque debería ser action; pero hay path orto que detecta el verbo "pon"/"play" en planner).
- **Cómo se manifiesta para el user:** user pide cronología/comparación/explicación → reply se corta mid-sentence porque max_tokens=384 (~7-8s a 50tok/s). Worse: el system_hint del modo dice "1-2 sentences MAX, plain text" — el LLM además **no intenta** dar la lista completa porque tiene la instrucción de ser corto.
- **Test que lo confirma:** no hay test que cubra estos prompts contra el classifier. `_infer_mode("orden cronológico de la saga Batman Arkham")` retorna "fast_action" (verificable trivialmente).

### F-005: Inherit-tools sin TTL ni blacklist de tools peligrosos

- **Archivo:** [gemma4_agent/agent.py:1049-1092](gemma4_agent/agent.py#L1049-L1092)
- **Snippet:**
```python
if not selected_tool_names:
    raw_text = ""
    ...
    is_short_continuation = (
        raw_text and len(raw_text.split()) <= 6
    )
    if is_short_continuation:
        prev_tools: list[str] = []
        for msg in reversed(self.history):
            ...
            elif msg.get("role") == "assistant":
                tcs = msg.get("tool_calls") or []
                for tc in tcs:
                    fn = (tc or {}).get("function") or {}
                    name = fn.get("name")
                    if isinstance(name, str) and name and name not in prev_tools:
                        prev_tools.append(name)
                ...
        if prev_tools:
            selected_tool_names = prev_tools[:6]
```
- **Por qué es riesgo alto:**
  - **0 TTL**: si pasaron 30 minutos entre turns (user fue a almorzar, dejó la sesión abierta), un "ok" hereda los tools del turno previo. Si esos tools eran `whatsapp_send` o `file_delete` o `system_shutdown`, una respuesta corta ambigua del user puede gatillar acción peligrosa.
  - **0 blacklist** de tools destructivos. No hay filtro tipo `DANGEROUS_TOOLS_NEVER_INHERIT = {"whatsapp_send","file_delete","system_shutdown","system_logoff"}`.
  - **Heurística `≤6 words AND no action verb`** está mal redactada: el comentario menciona "no action verb" pero el código `is_short_continuation = raw_text and len(raw_text.split()) <= 6` NO chequea verbos. La intención no está implementada.
- **Cómo se manifiesta para el user:** scenario: user "mandale por whatsapp a Juan que llegue temprano" → agent ejecuta whatsapp. Pasan 25 min. User dice "ok". Agente hereda `whatsapp_send` y manda algo basado en el contenido del turno (el LLM puede confundirse y re-enviar o enviar derivado). Más sutil: scenario donde inherit-tools sirve para responder a tool resultados ("¿cuál prefieres?" → "el primero") es legítimo, pero el alcance debe ser de <5 min.
- **Test que lo confirma:** `test_planner_continuation.py` cubre el caso happy-path. No vi test que cubra (a) gap temporal grande, (b) inherit de tool destructivo. Inspección directa del código confirma ausencia de `last_assistant_ts` o similar.

---

## Findings de riesgo MEDIO

### F-006: `_BROWSER_SESSIONS` sin cleanup global / sin TTL / sin cap

- **Archivo:** [gemma4_agent/ops_tools.py:25](gemma4_agent/ops_tools.py#L25), [ops_tools.py:1189-1247](gemma4_agent/ops_tools.py#L1189-L1247)
- **Snippet:**
```python
_BROWSER_SESSIONS: dict[str, dict[str, Any]] = {}
...
def _get_browser_session(session_id: str, state: AgentState, *, headless: bool) -> dict[str, Any]:
    session = _BROWSER_SESSIONS.get(session_id)
    if session:
        ...
        return session
    pw = _playwright()
    browser = pw.chromium.launch(headless=headless)
    context = browser.new_context()
    session = {"browser": browser, "context": context, ...}
    _BROWSER_SESSIONS[session_id] = session
    return session
```
- **Por qué es riesgo:** no hay `atexit.register`, no hay límite máximo, no hay TTL. Si en un run largo el LLM inventa diferentes `session_id` (rescue parser puede generar IDs nuevos), las sesiones se acumulan. Cada sesión es un Chromium completo en memoria.
- **Cómo se manifiesta para el user:** UI lenta, RAM hinchada, eventualmente OOM en runs >2h. Probable también: pages dejan handles a recursos del sistema (DevTools, sockets) que no se liberan hasta proceso exit.
- **Test que lo confirma:** `grep -n "atexit" gemma4_agent/ops_tools.py` → 0 hits. `grep -n "atexit" gemma4_agent/` → solo en archivos no-ops.

### F-007: Rescue parser pierde tool calls múltiples y formatos no-Python

- **Archivo:** [gemma4_agent/reasoning.py:173-228](gemma4_agent/reasoning.py#L173-L228)
- **Snippet:**
```python
    if not m:
        # Maybe there's narration first ("Voy a llamar web(...)"). Try to
        # find the LAST tool-call-shaped substring.
        last_call = None
        for cand in re.finditer(
            r"\b([a-z][a-z0-9_]{1,40})\s*\(",
            stripped,
        ):
            open_idx = cand.end() - 1
            close_idx = _find_matching_paren(stripped, open_idx)
            if close_idx > open_idx:
                last_call = (cand.group(1), stripped[open_idx + 1: close_idx])
```
- **Por qué es riesgo:**
  - Si el LLM emite **dos** tool calls leak en un mismo mensaje (`web(query="X"). Luego whatsapp(to="Y", text="...")`), el rescue captura solo el último y pierde el primero.
  - El cap de **40 chars** en tool name es ajustado a tools actuales (max ~28), pero futuro MCP nesting o namespacing más largo lo rompe silencioso.
  - El parser usa `ast.parse` que es Python-strict. Si el LLM emite JS-like (`web(query: "X")` con `:` en vez de `=`), no parsea.
  - El regex `_LEAKED_CALL_RE` requiere `^...$` con DOTALL — texto prefijado con narración cae al fallback "last call substring" que descarta el contexto.
- **Cómo se manifiesta para el user:** ya hay evidencia en traces: línea con reply `'web(action="search", query="de que trata GTA 5")'` mostrado AL USER como reply final (mission FAILED). 3 `tool_call_rescued` exitosos pero al menos 1 fallido en ventana de 200 — ~25% miss rate cuando el rescue debería disparar.
- **Test que lo confirma:** `gemma4_agent/test_tool_call_rescue.py` existe (recién creado, untracked). Sin haberlo ejecutado en detalle, presencia del leak literal en traces indica gap real.

### F-008: System prompt full = 25.6K chars / ~6400 tokens

- **Archivo:** [gemma4_agent/agent.py:527-575](gemma4_agent/agent.py#L527-L575)
- **Snippet (calculado en vivo):**
```
CORE_PROMPT: 8682 chars / ~2170 tokens
build_system_prompt(None) full: 25626 chars / ~6400 tokens
TOOL_RULES distinct: 26 (35 keys con dedupe)
```
- **Por qué es riesgo medio:** el subset path (subset != None) lo reduce — bueno. Pero algunas rutas usan `None` (legacy) y el endpoint `/agent/system_prompt` lo expone full. Más relevante: **6400 tokens son el techo conservativo de Gemma3 (8K-32K context según size)**. Combinado con tool schemas (~46K chars per comments) + history + recall + project context + persona + phrase_section + explicit_block, el budget de history queda apretado. La política de `_compact_completed_history` debe estar comprimiendo agresivo.
- **Cómo se manifiesta para el user:** primer turn lento (~5-10s pre-fill) si el modelo es 3n. Latencia bloat — choca con cap de [latency_budget](memory/feedback_latency_budget.md) (4-5s). Ningún ratio claro de "instrucciones útiles vs ruido" — TOOL_RULES probablemente repite reglas de "use only what's needed" + "verify_before_claim" en varios bloques.
- **Test que lo confirma:** medición arriba. Sin probar timings reales del modelo.

### F-009: Hardcode `es-419` en Disney+ URL

- **Archivo:** [gemma4_agent/domain_tools.py:5805](gemma4_agent/domain_tools.py#L5805)
- **Snippet:**
```python
"web_url": "https://www.disneyplus.com/es-419/browse/search",
```
- **Por qué es riesgo:** locale LATAM hardcoded. Si user viaja a Europa, su account redirige a `/es-es/` o `/en-gb/` y la URL exacta 404. No hay detección de locale del browser, del account, ni fallback en cascada. Selectors específicos referencian `/es-419/video/`, `/es-419/movies/`, etc en probe scripts — esos son scripts de research, no de runtime, pero confirma la dependencia conceptual.
- **Cómo se manifiesta para el user:** si user cambia región del Disney+ account o usa VPN, "ponme Loki" da 404 / search page rota.
- **Test que lo confirma:** [test_streaming_urls.py:46-53](gemma4_agent/test_streaming_urls.py#L46-L53) explícitamente asserta `es-419` (lo cementa). No hay test que cubra otros locales.

### F-010: Spotify auto-play presiona Enter en ventana "Spotify" sin checar workspace/profile

- **Archivo:** [gemma4_agent/domain_tools.py:6732-6799](gemma4_agent/domain_tools.py#L6732-L6799)
- **Snippet:**
```python
if "spotify" not in active_title.lower():
    return {... "abort_reason": "active window is X, not Spotify"...}
try:
    keypress_result = executor("gui", {"action": "keypress", "keys": "enter"})
```
- **Por qué es riesgo medio:** el check de "spotify" en title es laxo — cualquier ventana que tenga "spotify" en el título matchea (browser tab "Spotify - Wikipedia", VSCode con archivo "spotify.py"). Después del check pasan 300ms hasta el `keypress`. Si el user clickea otra cosa en ese intervalo, Enter va al lugar equivocado.
- **Cómo se manifiesta para el user:** poco frecuente, pero envío de form en browser, abrir archivo en VS Code, etc. Latencia + race condition.
- **Test que lo confirma:** lectura directa, sin test que cubra el race window.

---

## Findings de riesgo BAJO

### F-011: Tests con `return <bool>` en vez de `assert` (warnings ruidosos)

- **Archivo:** [gemma4_agent/test_verifiers.py](gemma4_agent/test_verifiers.py) (varios)
- **Por qué:** 16+ tests con `PytestReturnNotNoneWarning`. Funcional pero rotuto si pytest 8+ se vuelve strict. Distrae la salida de tests reales.

### F-012: `_streaming_cdp_play` usa `_time.sleep` fijo (5.5s+8s+5s+4s)

- **Archivo:** [gemma4_agent/domain_tools.py:6535,6572,6591,6594,6605](gemma4_agent/domain_tools.py#L6535)
- **Por qué:** suma >20s wall clock en flow de búsqueda+click. Para una red rápida y SPA cacheada, espera de más. Para red lenta, puede ser corto. Mejor un `wait_for_selector` con polling.

### F-013: `_BROWSER_SESSIONS` y `_PW` son globals de módulo

- **Archivo:** [gemma4_agent/ops_tools.py:25](gemma4_agent/ops_tools.py#L25)
- **Por qué:** estado global compartido entre tests. Si pytest paraleliza (xdist) o algún test importa y muta el dict sin teardown, contagia state. Visualmente menor mientras los tests usen `@patch`.

---

## Sospechas sin evidencia clara

- **`select_tool_names` semantic_fallback** podría estar inyectando tools de más en queries ambiguas (`select_tool_names._last_fallback_used` se chequea pero no se inspeccionó la lógica). Recomendado revisar `gemma4_agent/planner.py` y `gemma4_agent/semantic_router.py` en una segunda pasada.
- **`mission_goal.from_user_text`** infiere "expected tool actions" — los 7 FAILED en últimos 200 son todos `tool_events=0` con replies tipo confirmation. Sospecha: el classifier de mission_goal es demasiado optimista marcando "needs tools" para queries informativas ("qué es Gemma 4" → es web research opcional, pero el agente respondió por knowledge sin web tool, y se marca FAILED).
- **`_compact_completed_history`** no leído en detalle — si comprime de manera agresiva, puede estar borrando context que el promise guard necesitaba.
- **Streaming flow de Prime Video** marca `click_card_starts_playback=True` ([domain_tools.py:5907](gemma4_agent/domain_tools.py#L5907)) con comentario "best-effort". Probable falso positivo si el detail page no tiene mini-player auto-running (Prime tiene a/b testing del preview player — no garantía).

---

## Propuestas de fix (NO APLICAR — solo propuesta)

### Para F-001 (player_started global mentiroso)
- **Cambio:** en `_streaming_cdp_play:6640-6646`, retornar `player_started=False, attempted_play=True` cuando no hubo click de play y NO es Prime (i.e., cuando `click_starts_playback==False`). Solo para Prime puede mantenerse el `True` con un comentario explícito.
- **Tests a agregar:** mockear `executor("browser_real", {"action":"click", ...})` para que `selectors_play` falle, llamar `_streaming_cdp_play` con `canonical="disney"` y `click_starts_playback=False`, assertar `result["player_started"] is False`.
- **Riesgo de regresión:** bajo — la rama solo se ejecuta cuando el play_button selector falla, que ya es un caso degradado. La caller `_launch_streaming` ya maneja `attempted_play` vs `played` (línea 6945) — el footer cambia a "playback_attempted_unverified" honesto.

### Para F-002 (promise guard + Hecho-mentiroso)
- **Cambio:**
  1. Ampliar `promise_patterns` con: "te aviso", "te confirmo", "te paso", "te mando", "te muestro", "lo reviso", "lo verifico", "déjame ver", "ahora te traigo", "ya te digo", "te explico", "ya mismo".
  2. Agregar `false_confirmation_patterns` separados: `("hecho:", "hecho,", "listo,", "listo:", "ejecut", "registr", "agend", "envi", "mand")` — y si el reply empieza con alguno + `tool_events=0`, override con honest "Intenté pero no se completó la acción. ¿Repetimos?".
  3. En vez de solo retornar texto, **dispararar un retry interno** del turn con instrucción "el turno anterior prometió X sin ejecutar; ejecutá X ahora" — esto sí cierra el loop. Limitar a 1 retry para no infinitar.
- **Tests a agregar:** `test_promise_guard.py` con casos "Hecho: te agendé" + events=[] y assertar reply transformado / retry disparado.
- **Riesgo:** medio — un retry interno cambia el flow del turn (más latencia). Mitigación: solo disparar si el reply es corto (<150 chars) y los tools subset del turn previo incluyen el tool implícito (web/calendar/whatsapp).

### Para F-003 (kill Opera no graceful)
- **Cambio:**
  1. Reemplazar `Stop-Process -Force` por: primero `(Get-Process opera).CloseMainWindow()` (envía WM_CLOSE), luego `Wait-Process -Timeout 5`, solo si sigue vivo aplicar `Stop-Process`.
  2. Expandir detección "running in test": chequear también `sys.modules.get("pytest")`, `sys.modules.get("unittest")` y `os.environ.get("CI")` además de la env var actual.
  3. Antes de matar, contar instancias y, si >1, pedir confirmación o abrir mensaje al user vía notification — o intentar atacharse a una de las instancias existentes que YA tengan `--remote-debugging-port=9222` (los args están en `Get-Process | Get-CimInstance Win32_Process | Select CommandLine`).
- **Tests a agregar:** mock subprocess.run para verificar que primero se llama CloseMainWindow y solo después Stop-Process. Test que setea sys.modules['unittest'] y assertea action='disabled'.
- **Riesgo:** medio — el flow de CloseMainWindow agrega ~3-5s al peor caso. Pero respeta data del user.

### Para F-004 (mode truncamiento)
- **Cambio:** en `_infer_mode` agregar markers de "needs longer reply":
  - `info_markers = (" explica ", " explicame ", " explicame ", " explicar ", " describ ", " describí ", " describime ", " compara ", " comparar ", " comparame ", " orden ", " lista ", " cronolog ", " diferencia ", " porque ", " por que ", " razon ", " resumi ", " resumen ")`.
  - Si matchea → retornar nuevo modo `"answer"` (o reusar `research` sin hint de "use web") con `max_tokens >= 1024`.
- **Tests a agregar:** parametrizar los 6 inputs del enunciado + assertar mode esperado.
- **Riesgo:** bajo — solo agrega un branch antes de fast_action.

### Para F-005 (inherit-tools TTL + blacklist)
- **Cambio:**
  1. En `Gemma4Agent.__init__` agregar `self._last_turn_ts: float | None = None`. Setear al inicio de cada turn.
  2. En el inherit-tools block, si `time.time() - self._last_turn_ts > 300` (5 min), no heredar.
  3. Definir constante `DANGEROUS_TOOLS_NEVER_INHERIT = {"whatsapp_send", "whatsapp", "file_delete", "system_shutdown", "system_logoff", "system_restart"}` y filtrar `prev_tools = [t for t in prev_tools if t not in DANGEROUS]`.
- **Tests a agregar:** test que setea history con tool whatsapp + simula `_last_turn_ts` hace 25 min, assertar `selected_tool_names==[]`. Test con whatsapp + 1 min, assertar whatsapp NO está en inherit.
- **Riesgo:** bajo — el inherit ya es un fallback; un TTL extra no rompe casos legítimos (continuation post-tool es <30s típicamente).

### Para F-006 (_BROWSER_SESSIONS cleanup)
- **Cambio:** agregar `atexit.register(_cleanup_all_browser_sessions)` al final de `ops_tools.py`. Implementación: iterar `_BROWSER_SESSIONS.copy().items()`, llamar `_close_browser_session(sid)` para cada uno, tragar excepciones.
- **Tests:** difícil sin process exit real. Smoke: importar ops_tools, crear sesión mock, invocar `atexit._run_exitfuncs()`, verificar dict vacío.
- **Riesgo:** bajo.

### Para F-007 (rescue parser multi-call + non-python)
- **Cambio:**
  1. En `detect_leaked_tool_call`, cambiar la fallback de "última llamada" por **lista** de llamadas y retornar la primera que matcheé `known_tool_names`. Si el caller quiere multi-call, exponer una variante `detect_all_leaked_tool_calls`.
  2. Aceptar `:` además de `=` en kwargs (JS-style): regex pre-normalize `r'(\w+)\s*:\s*'` → `r'\1='` antes de ast.parse, solo dentro del body. Riesgo: rompe casos donde `:` es legítimo en strings — chequear que no esté dentro de comillas (state machine simple).
- **Tests:** ya hay `test_tool_call_rescue.py` — agregar casos multi-call y JS-style.
- **Riesgo:** bajo.

### Para F-008 (system prompt size)
- **Cambio:** dejar el legacy `build_system_prompt(None)` solo para el endpoint GET /agent/system_prompt y forzar a todos los callsites runtime a pasar subset explícito. Auditar `SYSTEM_PROMPT = build_system_prompt()` y reemplazar usos directos por el path con subset.
- **Tests:** test que cuenta usos de `SYSTEM_PROMPT` (módulo-level import) y assertea que solo está en el server endpoint.
- **Riesgo:** medio si hay imports indirectos.

### Para F-009 (locale hardcoded)
- **Cambio:** detectar locale del state del user (`state.user_locale` con default "es-419") y formatear la URL: `f"https://www.disneyplus.com/{locale}/browse/search"`. Mantener fallback con HEAD request para 404 → probar `es-419` → `es` → `en-us`.
- **Tests:** parametrizar test con varios locales.
- **Riesgo:** bajo.

### Para F-010 (Spotify race)
- **Cambio:** después del `focus + active check`, agregar segundo check inmediatamente antes del keypress (recheck window-foreground). Y exigir que el `class_name` sea `Chrome_WidgetWin_1` o el wndclass de Spotify, no solo title contains "spotify".
- **Tests:** mock executor para retornar title diferente entre primer y segundo check.
- **Riesgo:** bajo.

---

## Datos cuantitativos

- **Tests:** 493 passed / 0 failed, 30.16s wall total, 211 warnings (la mayoría `PytestReturnNotNoneWarning`).
- **Tests más lentos:**
  | test | duración |
  |---|---|
  | test_g1_experience_record_and_recall | 11.87s |
  | test_hit_rate_meets_threshold | 4.65s |
  | test_spotify_deeplink_when_desktop_installed | 2.10s |
  | test_status_exposes_streaming_platforms | 1.06s |
  | test_reset_health_never_returns_raises | 0.99s |
  | test_h1_1_chat_timeout_param_accepted | 0.50s |
  | test_h1_2_run_with_timeout_returns_on_hang | 0.50s |
  | test_voice_state_machine_listening_timeout_5s | 0.50s |
  | test_disney_plus_alias_resolves | 0.38s |
  | test_first_call_with_profile_saves_it | 0.37s |
  Solo 1 test (`test_g1_experience_record_and_recall`) cruza el umbral de 2s — probable I/O real contra SQLite. Candidato a refactor con tempdir + factory.

- **Tamaño system prompt:** CORE 8682 chars / 2170 tok; full 25626 chars / ~6400 tok; subset depende de tools (típicamente 3-6 tools → ~3000 tok).

- **Selectores DOM sin fecha de verificación:** 0 sin fecha — todos los specs en `_STREAMING_PLATFORMS` traen comentario "Verified via CDP probe 2026-05-16". Buena higiene. Pero: **no hay job/script periódico** que re-verifique y avise rotos antes que el user los pise. Los scripts en `scripts/probe_*.py` requieren disparo manual.

- **Patterns problemáticos en logs últimos 200 turnos (21 finals):**
  | pattern | conteo en ventana | ventana 1000 |
  |---|---|---|
  | finals con `mission_status=FAILED` (tool_events=0 pero mission esperaba tool) | 7 / 21 (33%) | n/a |
  | "Hecho/Listo …" + `tool_events=0` (mentiras de confirmación) | 5+ en 200 | **17 / 25** Hecho-Listo en 1000 son mentiras |
  | `tool_call_rescued` (rescue parser disparó) | 3 | n/a |
  | `web(action=...)` literal leaked al user reply | ≥1 visible en 200 | n/a |
  | `promise_without_action_caught` (guard disparó) | 0 | n/a |
  | `plan_status_surfaced` (planner failed/error) | 4 | n/a |
  | markdown leak (**, #, - bullets) | 0 | n/a |

  Headline: el guard de promise no agarró ningún caso en 200 turnos, pero hay evidencia clara (Hecho-mentiroso + leak literal) de que mintió varias veces. El guard actual es ciego al patrón dominante.

---

## Esperando tu input

Estos son los 13 findings. Listo para que decidas:

1. ¿Qué fix aplicamos primero? Mi recomendación: **F-002 (Hecho-mentiroso) > F-001 (player_started) > F-005 (inherit TTL) > F-003 (kill Opera)**. F-002 y F-001 atacan directamente el problema "el agente miente". F-005 y F-003 son safety-net antes de que rompan algo grande.
2. ¿Algún finding parece falso positivo o ya estaba previsto y queda como wontfix?
3. ¿Querés que en la siguiente pasada revise `planner.py`, `semantic_router.py`, `verifiers.py`, o el flow `_compact_completed_history`?
