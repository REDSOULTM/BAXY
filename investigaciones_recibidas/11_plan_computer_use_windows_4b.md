# Plan técnico para un agente de voz local que controla Windows con un LLM 4B (Gemma 4 E4B)

**TL;DR**

- El stack que describís se llama oficialmente **Gemma 4 E4B-it** (familia "E" = edge, no Gemma 3n; Google la liberó el 2 de abril de 2026, Apache 2.0). En llama.cpp tiene soporte multimodal day-one con `--mmproj` y el archivo `mmproj-gemma-4-E4B-it-bf16.gguf` (~992 MB BF16 en el repo oficial `ggml-org/gemma-4-E4B-it-GGUF`; el "F16 ~946 MB" del usuario corresponde a una medición de BF16 redondeada). **Veredicto:** con 6 GB de VRAM y el LLM ya cargado, mantener la visión residente es marginal — usala bajo demanda como ya planeás, pero asumí que cada llamada VLM cuesta ~1.5–2 s solo por el image-encode y rompe el budget tier-Alexa si se hace por paso.
- **Arquitectura ganadora:** macros deterministas parametrizadas (`click_button(label)`, `fill_field(label, value)`) que internamente ejecutan **observe→act→verify** con UIA primero, OCR como fallback y visión como último recurso. El 4B SOLO decide objetivo, descomposición y ramificación ambigua. Esto es exactamente la receta de UFO² (Microsoft, arXiv:2504.14603, abril 2025): "hybrid control detection pipeline fuses Windows UI Automation (UIA) with vision-based parsing" + "speculative multi-action execution… lowering inference cost by up to 51.5%". Con un VLM de 7B+ como UI-TARS-1.5 (24.6 % OSWorld) o Operator/Claude (≤22 %), la SOTA Windows real es 27.9–30.5 % SR en WindowsAgentArena con GPT-4o/o1 en UFO² — un 4B local sin grounding entrenado va a estar muy por debajo. **Honestidad:** "controlar la PC de forma confiable para misiones arbitrarias" NO es alcanzable con Gemma 4 E4B local hoy. SÍ es alcanzable un subset acotado: apps con UIA rico (Notepad, Explorer, Office, Settings, navegadores con `--force-renderer-accessibility=complete`), tareas ≤5 pasos, con verificación estructural por paso.
- **Loop crítico:** cada acción GUI tiene que pasar por un `verify_post_action()` que combine (1) hash perceptual de la región de interés (no de toda la pantalla) con dHash 8×8 + Hamming ≤6 como umbral, (2) delta del subárbol UIA enfocado, y (3) `GetForegroundWindow`. La visión Gemma se enciende solo cuando UIA viene vacío Y el OCR no localizó el label. Para vram4 esto es viable; activarla por paso no lo es.

**Key Findings**

- **El nombre del modelo:** "Gemma 4 E4B" existe oficialmente y es lo que el usuario tiene. Google blog (2 abril 2026): *"We are releasing Gemma 4 in four versatile sizes: Effective 2B (E2B), Effective 4B (E4B), 26B Mixture of Experts (MoE) and 31B Dense"*; *"the E2B and E4B models feature native audio input for speech recognition and understanding"*. La "E" es Edge (PLE / Per-Layer Embeddings), no Experts. **No es Gemma 3n** — Gemma 3n E4B existió pero su soporte multimodal en llama.cpp todavía estaba bloqueado en agosto 2025 (Discussion #15194). Gemma 4 sí tiene mmproj oficial.
- **llama.cpp + mmproj:** el repo oficial `ggml-org/gemma-4-E4B-it-GGUF` publica `mmproj-gemma-4-E4B-it-bf16.gguf` (992 MB) y un Q8_0 (560 MB). `docs/multimodal.md` lista Gemma 4 explícitamente: *"Use -m model.gguf option with --mmproj file.gguf to specify text and multimodal projector respectively. By default, multimodal projector will be offloaded to GPU. To disable this, add --no-mmproj-offload"*. **Bug conocido (#21402):** crash CUDA `SIGABRT` en `clip_model_loader::load_tensors` al cargar mmproj de Gemma 4 31B/26B-A4B en Blackwell; E4B no está flagged ahí pero hay que probar antes. **Audio NO está cableado en llama-server** todavía (discussion #21334: *"audio input is not supported - hint: if this is unexpected, you may need to provide the mmproj"*), o sea no contar con audio nativo del modelo: hay que poner Whisper/Vosk aparte.
- **Techo real con 4B local:** UI-TARS-1.5 (7B nativo, RL extenso) hace 24.6 % en OSWorld; UI-TARS-2 (sept 2025) llega a 47.5 % OSWorld / 50.6 % WindowsAgentArena; UFO² con o1 hace 30.5 % WAA / 32.7 % OSWorld-W; Holo3-35B-A3B (H Company, lanzado 31 marzo 2026) lidera el OSWorld-Verified leaderboard con 82.6 % per BenchLM.ai (último update 29 abril 2026), aunque el propio model card de H Company en Hugging Face reporta 77.8 % para el 35B y 78.85 % para el flagship Holo3-122B-A10B. **Sin RL de grounding y sin VLM nativo de 7B+, un 4B vía mmproj genérico está estructuralmente por debajo del 20 % en tareas arbitrarias**. El plan tiene que apuntar a que el código determinista absorba el 80–90 % del trabajo y el LLM solo intervenga en decisiones ambiguas — exactamente lo que dice Agent-S2 (Simular Research, arXiv:2504.00906): *"Mixture of Grounding… reasons about subgoals and routes actions to specialized grounding experts"*.
- **GAP del tool "gui" del usuario está bien diagnosticado:** "dispatch ciego sin verify post" es la falla estructural #1 de todas las CUAs early. UFO² confirma: *"each automation step is executed in isolation, requiring a full LLM inference for every single GUI action. This step-wise inference loop introduces excessive latency, inflates system resource usage, and increases cumulative error rates"*. La solución no es un LLM mejor: es un loop observe→act→verify a nivel de macro determinista.

**Details**

## P1 — Arquitectura del loop observe→act→verify→recover

**Conclusión: opción (b), macros parametrizadas deterministas, es la única viable en vram4 + 4B local.** (a) es el status quo roto y (c) requiere VLM residente que no cabe.

| Opción | Latencia/paso | Confiabilidad | VRAM | Aplicable a 4B local | Veredicto |
|---|---|---|---|---|---|
| (a) LLM emite primitivos sueltos (click_xy, type_text) | 1–2 s LLM + 0 verify | Baja: deriva tras 3 pasos | ~5 GB | Sí pero falla | Status quo, **DESCARTAR** |
| (b) Macros deterministas `click_button(label)` con observe→act→verify | 50–300 ms (sin LLM en pasos triviales) | Alta para UIA rico | ~5 GB | **Sí** | **ELEGIR** |
| (c) VLM-style (Gemma mmproj cada paso) | 1.5–3 s solo image-encode + LLM | Media (sin grounding RL) | ~6.5 GB (sobre presupuesto) | No | **NO-VIABLE en vram4** |

**Cómo transfiere la literatura al stack del usuario:**

- **UFO² (Microsoft, arXiv:2504.14603):** transfiere directo — HostAgent (decide objetivo) + AppAgent (ejecuta con UIA+API). En tu caso, el HostAgent ES el 4B + tu `mission_goal` verifier; los AppAgent SON tus macros. *"UFO2 achieves a 27.9% SR on WAA, exceeding Operator by a substantial 7.1%… Utilizing the stronger o1 model further improves UFO2's performance to 30.5% (WAA) and 32.7% (OSWorld-W)"*. **Lo que NO transfiere:** ellos asumen GPT-4o/o1 cloud. Adaptación: el 4B no descompone bien tareas largas → restringí a 1 sola "AppTask" por turno de voz.
- **Agent-S2 (arXiv:2504.00906, Simular Research):** "Mixture of Grounding" — para vos, eso significa: cuando UIA falla, NO le pidas al 4B que estime coordenadas; usá especialistas deterministas (OCR PaddleOCR localiza el label exacto, template matching opencv para íconos). *"Agent S2 achieves 18.9% and 32.7% relative improvements over leading baseline agents such as Claude Computer Use and UI-TARS on the OSWorld 15-step and 50-step evaluation"*.
- **OS-Copilot/FRIDAY (arXiv:2402.07456):** transfiere la idea de **skill library** — guardá macros exitosas verificadas por misión como tools reutilizables. *"FRIDAY learns to control and self-improve on Excel and Powerpoint with minimal supervision"*. Tu `mission_goal` verifier es justo el gate para incorporar una skill nueva.
- **UI-TARS-1.5/2 (ByteDance, arXiv:2501.12326 y 2509.02544):** NO transfiere directo — son VLMs end-to-end 7B/72B con RL de grounding, no son tu arquitectura. UI-TARS-2 reporta *"47.5% on OSWorld, 50.6% on WindowsAgentArena"*; sirve como techo aspiracional para ver qué pierde uno por no tener grounding entrenado.
- **Anthropic/OpenAI computer-use:** cloud-only, no transfiere stack pero sí filosofía. Anthropic, en la página oficial de producto de Claude Sonnet 4.6 (anthropic.com/claude/sonnet), reporta: *"Claude Sonnet 4.6 produced zero hallucinated links in our computer use evals. Previously, we saw about one in three hallucinated links. That kind of reliability is what actually makes browser automation deployable at scale."* Anthropic, "Introducing Claude Opus 4.7" (anthropic.com/news/claude-opus-4-7, 16 abril 2026): Opus 4.7 alcanza 78.0 % en OSWorld-Verified, up from Opus 4.6's 72.7 %, con mejora parcialmente atribuida a resolución de imagen 3× (de 1.15 MP a 3.75 MP). Implica que la confiabilidad sube con tamaño y RL — un 4B no llega.

**Separación de responsabilidades (regla dura):**

```
USER VOICE
    │
    ▼
[Intent Router]  ←  embeddings paraphrase-multilingual-MiniLM-L12-v2
    │             (NUNCA listas léxicas; clasifica goal_type por similitud)
    ▼
[4B LLM: SOLO descomposición]  ←  JSON Schema grammar via llama.cpp
    │             prompt: "Dado el goal X y la observación estructural Y,
    │             ¿qué macro debo invocar? ¿con qué argumentos?"
    ▼
[Macro Determinista]  ←  observe (UIA cached) → act → verify_post_action()
    │                     → si falla: recovery_table → retry (presupuesto 2)
    │                     → si recovery agota: pedir al 4B re-plan
    ▼
[mission_goal verifier]  ←  estructural por SO (pycaw, Path.stat, EnumWindows)
    │
    ▼
RESPUESTA AL USER (honesty guard: solo "hecho" si confirmed==True)
```

## P2 — Verificación post-acción SIN VLM

**El verifier es lo más importante del sistema.** Tabla comparativa por señal:

| Señal | Latencia | False-positive | False-negative | Distingue "yo lo cambié" vs ruido | Veredicto |
|---|---|---|---|---|---|
| Frame-diff full-screen pHash | 20–40 ms | Alto (cursor, reloj, blink) | Medio | No | **Solo con cropping** |
| Frame-diff de ROI (bbox del target) con dHash 8×8 | 5–10 ms | Bajo si ROI bien acotado | Bajo | Sí (ROI excluye reloj/notif) | **PRIMARIO** |
| Re-lectura UIA del subárbol enfocado, delta Name/Value/State | 30–150 ms (depende de prefetch) | Bajo | Bajo (si UIA responde) | Sí | **PRIMARIO** |
| `SetWinEventHook` (`EVENT_SYSTEM_FOREGROUND`, `EVENT_OBJECT_INVOKED`, `EVENT_OBJECT_VALUECHANGE`) | <5 ms (async push) | Muy bajo | Solo si la app emite eventos | Sí (event_thread_id correlaciona con tu PID) | **SECUNDARIO async** |
| `GetForegroundWindow` + título | <2 ms | Bajo | Alto (no detecta cambios intra-ventana) | Sí | **Solo para verify de "abrió la app correcta"** |
| Visión Gemma mmproj (recorte 256×256) | ~1.5–2.5 s (encode+decode) | Bajo | Bajo | Sí | **Último recurso, gateado** |

**Combinación recomendada (<50 ms en el camino feliz):**

```python
def verify_post_action(action, target_element, screenshot_before, t_before_ms):
    # 1) Esperar settling corto (UI necesita refrescar)
    time.sleep(0.08)  # 80 ms; ajustar por app
    
    # 2) UIA delta del subárbol del target (con RuntimeId si lo tenemos)
    try:
        new_el = uia_refind_by_runtime_id(target_element.runtime_id, timeout_ms=120)
        if new_el is None:
            uia_signal = "stale"  # el elemento desapareció: a veces es éxito (botón cerrar)
        else:
            uia_signal = "changed" if (new_el.value != target_element.value or
                                       new_el.toggle_state != target_element.toggle_state or
                                       new_el.has_focus != target_element.has_focus) else "unchanged"
    except COMError:
        uia_signal = "uia_failed"
    
    # 3) Frame-diff ROI (NO full-screen) con dHash 8×8
    bbox = expand_bbox(target_element.bbox, margin=40)  # contexto cercano
    crop_after = mss_capture(bbox)
    h_before = dhash8(crop_before)  # precomputed before action
    h_after = dhash8(crop_after)
    hamming = bin(h_before ^ h_after).count('1')
    pixel_signal = "changed" if hamming >= 6 else "unchanged"  # umbral empírico para ROI ~200x60 px
    
    # 4) Foreground check (cheap)
    fg_ok = (win32gui.GetForegroundWindow() == expected_hwnd)
    
    # 5) Event hook (async, leído del buffer)
    fired_events = drain_winevent_buffer(since_ms=t_before_ms,
                                         match=[EVENT_OBJECT_INVOKED, EVENT_OBJECT_VALUECHANGE,
                                                EVENT_OBJECT_STATECHANGE])
    event_signal = "fired" if fired_events else "silent"
    
    # 6) Fusión: cualquier 2 de las 3 señales positivas = confirmed True
    positives = sum([uia_signal == "changed", pixel_signal == "changed", event_signal == "fired"])
    if positives >= 2:
        return ("confirmed_true", {"uia": uia_signal, "px": pixel_signal, "ev": event_signal})
    if uia_signal == "stale" and action.kind in {"close", "submit", "navigate"}:
        return ("confirmed_true_stale", {"reason": "target_dismissed_as_expected"})
    if positives == 0 and not fg_ok:
        return ("confirmed_false", {"reason": "no_change_and_focus_lost"})
    return ("inconclusive", {...})  # → gatea visión SI el paso es crítico
```

**Umbrales (medirlos en TU hardware):**

- dHash 8×8 → Hamming ≥6 sobre 64 bits para ROI ~200×60 px funciona en la práctica para distinguir "cambió por click" vs "blink de cursor"; subí a ≥10 si el ROI es ≥500×300. Justificación: pHash/dHash con hashsize=8 produce hashes 64-bit; *"You may want to adjust the hashsize or require some manhattan distance"* — JohannesBuchner/imagehash. Para detectar cursor blink vs cambio real, **excluí la zona del cursor** del crop (`win32gui.GetCursorPos`) o usá doble-muestreo (dos screenshots con 40 ms de gap, hash idéntico = baseline; cualquier hash distinto post-acción = cambio).
- UIA refresh: usá un `IUIAutomationCacheRequest` con `AddProperty(Name, Value, ToggleState, HasKeyboardFocus, BoundingRectangle)` para hacer un round-trip único en vez de 5; reduce de ~150 ms a ~30 ms en árboles medianos.
- `SetWinEventHook` con `WINEVENT_OUTOFCONTEXT` async — los eventos `EVENT_OBJECT_INVOKED`, `EVENT_OBJECT_VALUECHANGE`, `EVENT_SYSTEM_FOREGROUND` llegan en <5 ms a un buffer thread-safe; correlacioná por `event_thread_id == GetWindowThreadProcessId(target_hwnd)` para descartar ruido de notificaciones de Teams/Outlook.

**Cuándo es INEVITABLE caer a Gemma mmproj (gate estricto):**

- `uia_signal == "uia_failed"` (árbol vacío, app custom-render, juego), Y
- OCR PaddleOCR no localizó el label esperado dentro de un margen razonable, Y
- la acción es **mission-critical** (no es un click exploratorio), Y
- el sistema tiene budget de visión disponible (≤2 calls por misión).

Cropping: pasar a Gemma un recorte de la región esperada (256×256 px o 384×384 — la resolución variable de Gemma 4 lo permite), no la pantalla entera (~1920×1080 sería 8–12 image tokens más → +1 s). Token budget de imagen: 280 tokens es el default hardcodeado en `max_soft_tokens` de Gemma 4 (per ollama issue #15626: *"hardcoded to 280 in model/models/gemma4/process_image.go"*); el blog Datature ("Gemma 4: What Computer Vision Engineers Actually Need to Know") lo describe como el midpoint de 5 opciones (70 / 140 / 280 / 560 / 1120), y la doc oficial de Google (ai.google.dev/gemma/docs/capabilities/vision/image) documenta el rango completo, no una recomendación única para edge. **No-Viable:** mmproj cada paso. **Viable raro:** 1–2 calls por misión, gateadas.

## P3 — Cascada UIA → OCR → visión

**Orden y criterios:**

```python
def perceive(target_spec, app_context):
    # Tier 0: cache de observación por turno (NO re-escanear si <2 s pasaron)
    if cache.fresh(app_context.hwnd, ttl_ms=2000):
        return cache.get()
    
    # Tier 1: UIA con prefetch (cacheRequest bulk) — apps nativas, ~30-150 ms
    tree = uia_scan(app_context.hwnd, max_depth=8, max_elements=400,
                    cache_props=[Name, ControlType, AutomationId, BoundingRect,
                                 IsKeyboardFocusable, IsEnabled, IsPassword,
                                 RuntimeId, Value])
    if tree.is_rich():  # heurística: >=10 elementos con Name no vacío
        cache.put(app_context.hwnd, tree, ttl_ms=2000)
        return tree.as_textual_list(cap_elements=80, cap_chars_per_label=60)
    
    # Tier 2: relaunch CEF/Chromium con --force-renderer-accessibility=complete
    if is_chromium_app(app_context) and not app_context.has_a11y_flag:
        if user_allows_relaunch():  # CONFIRMACIÓN del user, no automático
            relaunch_with_a11y_flag(app_context)
            return perceive(target_spec, app_context)  # reintentar UIA
    
    # Tier 3: OCR PaddleOCR sobre screenshot mss — apps custom-render, ~200-500 ms
    screenshot = mss_capture(app_context.bounds)
    ocr_elements = paddleocr.locate_text_with_bbox(screenshot)
    if ocr_elements:
        return ocr_elements.as_textual_list()  # sin tipo de control, solo text+bbox
    
    # Tier 4: Visión Gemma mmproj — último recurso, SOLO si el step es crítico
    if step_is_critical and vision_budget_remaining > 0:
        return gemma_vision_describe(screenshot, prompt=target_spec)
    return None  # forzar fallback al recovery handler
```

**`--force-renderer-accessibility=complete` (P3 sub-pregunta):**

- Es la respuesta para Discord/Spotify/Slack/Electron/Chrome cuando el árbol UIA viene vacío. Doc Chromium: *"`--force-renderer-accessibility=[basic|form-controls|complete]`: Force accessibility to be enabled, with optional parameter to force the AXMode to one of the predefined bundles during the entire execution. If the optional parameter is invalid, then the default AXMode will be complete."*
- **Efectos secundarios documentados:** consumo de CPU/RAM extra del renderer porque mantiene el árbol de accesibilidad serializado; en Chromium docs: *"a representation of the entire accessibility tree is cached in the main process… Great care needs to be taken to ensure that this representation is as concise as possible"*. Para Discord/Slack hay reports de +5–15 % CPU sostenido. Aceptable para el assistant; no prendas sin avisar.
- **Cómo relanzar sin romper la sesión del user:** **NO lo hagas automático.** Política:
  1. Detectar app via process_name (`Discord.exe`, `Slack.exe`, `Spotify.exe`).
  2. Pedirle al user confirmación verbal una vez por sesión: *"Para controlar Discord necesito reiniciarlo con accesibilidad. ¿Lo hago?"*
  3. Si acepta, persistir un shortcut/launcher modificado (`%LOCALAPPDATA%\Discord\app-*\Discord.exe --force-renderer-accessibility=complete`) o lanzar una nueva instancia con el flag. **Nunca matar procesos del user sin confirmación explícita.**
  4. Para apps Electron que ya intercepan args (VSCode issue #84833), no funciona y hay que caer a OCR.

**Representación textual para el 4B (cap de tokens):**

```
[01] button "Send" @1620,980,80,32 enabled focused
[02] edit "Message"  @20,950,1580,60 value="" focusable
[03] text "John Doe — online" @20,80,200,24
...
```

- **Cap recomendado:** 60 elementos visibles, 50 chars por Name. Con ctx 16K y prompt sys/user fijo ~1500 tokens, te quedan ~13 K para historia + observación. 60 elementos × ~25 tokens cada uno = 1500 tokens → cabe holgado y deja room a 5 turnos de historia.
- **Filtrar agresivamente:** `IsOffscreen=False`, `IsControlElement=True`, área visible >0, Name no vacío O AutomationId no vacío. Eso suele bajar de 400 elementos crudos a 50–80.
- **RuntimeId para re-bindear sin re-escanear:** sí, **siempre cachealos**. `IUIAutomationElement.GetRuntimeId()` devuelve un array que es estable mientras el elemento existe; *"Identifiers can be reused over time. The format of run-time identifiers might change in the future. The returned identifier should be treated as an opaque value and used only for comparison"*. Usalos como key del cache por turno; si la macro hace 3 acciones en el mismo dialog, re-bind por RuntimeId vale ~5 ms vs re-scan que vale 80 ms.

## P4 — Recuperación de errores (pre-retry actions)

**Tabla determinista:**

| Tipo de fallo | Acción pre-retry | Budget retries | Si agota |
|---|---|---|---|
| `target_not_found` (UIA scan no encontró label esperado) | `wait(300ms)` + `re-scan UIA` + difflib fuzzy con threshold 0.75 | 2 | escalar a OCR; si OCR falla → re-plan LLM |
| `stale_element` (RuntimeId ya no resuelve) | invalidar cache, `re-scan UIA` desde root del HWND | 1 | mismo handling que target_not_found |
| `focus_lost` (`GetForegroundWindow() != expected_hwnd`) | tu "golden focus" (AllowSetForegroundWindow + ALT-trick + AttachThreadInput) | 2 | abortar misión con mensaje al user |
| `click_no_effect` (verify devolvió `confirmed_false`) | `wait(200ms)` (animación) + verify de nuevo; si sigue → `re-scan UIA` y verificar que el elemento sigue en mismo bbox | 1 | reintentar con coordenada del **center** vs `ClickablePoint` UIA |
| `uia_empty_tree` (CEF/Chromium sin flag) | gate de relanzar con `--force-renderer-accessibility=complete` (con consentimiento del user) | 1 | caer a OCR; si OCR falla → último recurso visión |
| `disambiguation_needed` (≥2 elementos matchean el label fuzzy ≥0.75) | NO retry mecánico; preguntarle al user *"¿Cuál: 'Enviar' (botón principal) o 'Enviar a contactos'?"* | N/A | el user decide |
| `password_field_detected` (UIA `IsPassword=True`) | NO teclear; gatillar **secret handoff** (ver P5) | 0 | mensaje al user pidiendo que escriba |
| `app_not_responding` (UIA timeout 2 s) | `wait(1 s)` + ping con `SendMessageTimeout(WM_NULL, SMTO_ABORTIFHUNG, 500ms)` | 1 | abortar |
| `loop_detected` (tu detector existente: 5 patrones result-aware) | `abort_macro` y re-plan con LLM, incluyendo en prompt los pasos fallidos | 0 | si re-plan también loopea → abandonar misión, honesty guard |

**Integración con tu loop-detector existente:**

- Tu loop-detector ya tiene 5 patrones result-aware + `no_progress`. **Reglas de integración:**
  1. Cada macro emite un `step_signature = hash(action_kind, target_label, verify_outcome)`. Si dos steps consecutivos comparten signature Y ambos son `confirmed_false`/`inconclusive` → trigger `no_progress`.
  2. El budget de retries por macro NO cuenta como "loop" mientras el verify devuelva `confirmed_true` al menos una vez en la cadena.
  3. Si el detector se dispara, la macro hace `abort` (no espera al LLM) y devuelve el contexto al planner para re-plan.

## P5 — Riesgo y seguridad

**Clasificación estructural de riesgo por acción (no por keyword):**

| Clase | Detección estructural | Política |
|---|---|---|
| **R0 read-only** | scroll, hover, screenshot, UIA read | Auto-ejecutar sin confirmación |
| **R1 reversible** | click en toggle/checkbox, type en edit no-password | Auto-ejecutar; loguear |
| **R2 navegacional** | abrir app, cambiar tab, navegar URL | Auto-ejecutar si el goal lo cubre |
| **R3 comunicación** | enviar mensaje, enviar email, postear | **Confirmación obligatoria**: detectar via UIA `Name` con clase "send/submit/post" semánticamente (embedding similarity contra prototipos multilingües), no via lista de keywords |
| **R4 destructivo** | delete, format, uninstall, drop | **Confirmación verbal del user, repitiendo target**: *"Borrar archivo X.docx, ¿confirmás?"* |
| **R5 financiero / autenticación** | UIA `IsPassword=True`, OAuth dialogs, dialogs con texto que matchee embeddings de "pay/transfer/buy/sign-in" | **Secret handoff** (abajo) o pausar y pedir intervención humana |

**Detección de campos de contraseña — la clave es UIA:**

- Microsoft docs: *"Must be set to TRUE on edit controls that contain passwords. If an edit control does contain Password contents then this property can be used by a screen reader to determine whether keystrokes should be read out as the user types them."* (UIA `IsPasswordPropertyId`, ID 30019).
- Política dura: si `element.GetCurrentPropertyValue(UIA_IsPasswordPropertyId) == True`:
  1. NUNCA escribir desde `SendKeys`/`mouse_event`.
  2. NUNCA loguear el valor objetivo en el checkpoint/history.
  3. Trigger `secret_handoff()`.

**Secret handoff (sin que el secreto entre al historial):**

```python
def secret_handoff(field_element, prompt_msg):
    # 1) Mostrar overlay al user (TTS + Toast): "Por favor escribí la contraseña, te cedo el control 30 s"
    speak(prompt_msg)
    toast_notify(prompt_msg)
    
    # 2) Asegurar foco al campo
    field_element.SetFocus()
    
    # 3) Ceder control: deshabilitar el agent input
    agent_input_lock.acquire()  # globally pause SetCursorPos/SendKeys
    
    # 4) Monitorear UIA Value (sin leer el contenido — solo length>=min y focus_lost)
    deadline = time.time() + 30
    while time.time() < deadline:
        if not field_element.HasKeyboardFocus:  # user tabbed out
            break
        if uia_get_value_length(field_element) >= 4:  # heuristic; NO ver el valor
            break
        time.sleep(0.1)
    
    # 5) Resumir control, registrar en history SOLO "user_typed_secret_into:<AutomationId>"
    agent_input_lock.release()
    history.append({"action": "secret_handoff", "field_id": field_element.AutomationId,
                    "field_name_redacted": "***", "duration_s": ...})
    return "handed_off"
```

**Reglas no negociables:**
- El historial/checkpoint **NUNCA** persiste valores tecleados en campos `IsPassword=True`.
- Para clipboard: si la macro va a leer clipboard tras un secret_handoff, abortar (puede contener el secreto).
- Si el campo NO es `IsPassword` pero su Name/Label tiene similitud embeddings ≥0.75 con "password/contraseña/PIN/codice/clave" en cualquiera de los 140+ idiomas que Gemma 4 soporta → tratar como password (paraphrase-multilingual-MiniLM-L12-v2 maneja esto).

**No pelear con el user por el mouse:**

```python
def user_activity_monitor():
    # Pollear estado del input cada 50 ms
    last_user_pos = win32api.GetCursorPos()
    last_user_keys = get_last_input_info_tick()  # GetLastInputInfo de Win32
    
    while True:
        time.sleep(0.05)
        current_keys_tick = get_last_input_info_tick()
        current_pos = win32api.GetCursorPos()
        
        # Si hubo input del user EN LOS ÚLTIMOS 200 ms y NO fue del agente
        if (current_keys_tick != last_user_keys) and not agent_just_acted_within(200):
            agent_input_lock.acquire()
            speak("Te cedo el control")
            # Pause por 5 s; reanudar si el user no vuelve a tocar
            wait_for_user_idle(threshold_ms=3000, timeout=30)
            agent_input_lock.release()
        
        last_user_keys = current_keys_tick
        last_user_pos = current_pos
```

Usa `GetLastInputInfo` (Win32) para distinguir input humano (mouse movement no generado por `SetCursorPos`, teclas no enviadas por `SendInput`). El agente marca `agent_just_acted` cuando emite input.

## P6 — Latencia: presupuesto por paso GUI

**Mediciones esperadas para Gemma 4 E4B Q4_K_M en GPU 6 GB a 40–60 tok/s:**

| Componente | Tiempo esperado | Notas |
|---|---|---|
| Prompt processing (con `--cache-reuse 256` activo, prefix estable) | 50–300 ms para 1500 tokens nuevos | Gerganov: *"Enable context reuse of the server by adding --cache-reuse 256. It will improve your prompt processing performance noticeably"*. **Ojo:** issue #15082 reporta regresión en algunas builds; medir con `tokens_cached` en la respuesta |
| LLM decode 1 acción JSON (~80 tokens) | 1.3–2.0 s a 40–60 tok/s | Tu cuello de botella si llamás al LLM por paso |
| UIA scan + cache prefetch (50 elementos) | 30–150 ms | Con `IUIAutomationCacheRequest` |
| OCR PaddleOCR full-screen (CPU) | 200–500 ms | GPU OCR baja a 80–150 ms pero compite con LLM por VRAM — **NO instalar paddle-gpu**, mantener CPU |
| OCR PaddleOCR crop 600×200 | 60–120 ms | Preferí crops siempre que sepas dónde mirar |
| Screenshot mss full-screen | 5–15 ms | Multi-monitor cuesta más |
| dHash 8×8 sobre ROI 400×200 | 2–5 ms | Numpy puro |
| Mouse move + click + delay | 80–150 ms | Tu primitivo Win32 actual |
| Verify (UIA delta + frame-diff ROI + event drain) | 30–80 ms | Con prefetch |
| **Gemma mmproj vision call (recorte 384×384)** | **1.5–2.5 s** | Image encode ~700 ms + decode ~1 s; **rompe budget si se usa por paso** |

**Cuánto cabe en un turno de voz tier-Alexa (≤5 s):**

- Camino feliz, **sin** LLM call por paso (macro determinista pura): `screenshot 10 + UIA 80 + decide_target 5 + click 100 + verify 60 = 255 ms/paso`. **5 s = ~19 pasos.** No realista por complejidad, pero el techo está alto.
- **Con** 1 LLM call al inicio del turno (descomposición): `LLM 1.8 s + 3 pasos × 280 ms = 2.64 s`. **OK tier-Alexa.**
- **Con** LLM call por paso (mal diseño): `(LLM 1.8 + step 280) × 3 = 6.2 s`. **Rompe.**
- **Con** 1 vision call por misión: `+1.8 s adicional → ~4.4 s para 3 pasos`. **Borderline; OK si la misión justifica.**
- **Con** vision por paso: **rompe siempre, no-viable.**

**Speculative multi-action (UFO² style) en un 4B:**

- UFO² reporta: *"speculative multi-action execution… lowering inference cost by up to 51.5%"* y *"GPT-4o achieves a 6.5% step reduction, while o1 demonstrates a remarkable 58.5% reduction in steps for identical tasks"*.
- **Para un 4B local:** **Riesgoso pero RECOMENDADO con guardrails.** El 4B predice peor secuencias largas → limitar a N=2 acciones speculativas por call, y **validar cada una antes de ejecutar la siguiente** (no batch-execute). Si la validación de la acción k falla → descartar k+1..N y re-planear. Esto es lo que UFO² llama "online validation": *"speculatively generates a batch of likely next steps using a single inference pass and validates their applicability at runtime through tight OS integration"*.
- **Métrica de gate:** activar speculative N=2 solo si en las últimas 20 misiones el 4B tuvo ≥80 % de aciertos en el "next action prediction". Si baja, volver a N=1.

**"Modo misión" vs "modo voz":**

- **Modo voz (atómico):** turno = 1 sola macro, ≤5 s p95, sin pedir clarifications excepto disambiguation. Si el goal requiere más → responder *"Hago A primero; querés que siga con B?"*.
- **Modo misión (relajado):** turno largo (hasta 30–60 s), permite vision calls, permite checkpoint, permite preguntarle al user. Disparado explícitamente por el user *"hacé una misión: …"* o por embedding-similarity del intent con prototipos "long-task".

## P7 — Durable execution / checkpoint

**Veredicto: vale, pero MINIMAL, no LangGraph/Temporal.**

| Opción | Costo dev | Beneficio | ¿Cabe en vram4? |
|---|---|---|---|
| Sin checkpoint (status quo) | 0 | Si crashea, perdés todo | Sí |
| Checkpoint JSON sencillo en `%LOCALAPPDATA%` | 1 día | Resume tras crash o cierre | Sí — **ELEGIR** |
| LangGraph con SQLite checkpointer | 3–5 días | Replay determinístico | Sí pero overkill |
| Temporal | 1–2 semanas | Producción serio | Overkill |

**Diseño mínimo:**

```python
@dataclass
class MissionCheckpoint:
    mission_id: str            # uuid
    user_intent: str            # texto original del user
    goal: dict                  # mission_goal verifier spec
    plan_steps: list[dict]      # macros a ejecutar
    completed_steps: list[dict] # con verify outcomes
    pending_step_idx: int
    started_at: float
    last_update_at: float
    # NUNCA: passwords, clipboard contents, screenshots
    
def save_checkpoint(cp: MissionCheckpoint):
    # Atomic write: tmp file + os.replace
    path = LOCALAPPDATA / "agent" / f"mission_{cp.mission_id}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(cp), default=str))
    os.replace(tmp, path)

def resume_on_startup():
    for cp_file in (LOCALAPPDATA / "agent").glob("mission_*.json"):
        cp = load(cp_file)
        if cp.last_update_at < time.time() - 3600:  # >1h stale
            cp_file.unlink()
            continue
        # Preguntarle al user: "Quedó pendiente: <goal>. ¿Reanudo?"
        if user_confirms():
            resume_mission(cp)
        else:
            cp_file.unlink()
```

**Cuándo NO sirve:** turnos de voz atómicos (modo Alexa). Solo activá checkpoint para misiones largas (`>3 macros` o `>15 s` de runtime estimado).

## P8 — Plan de implementación por fases

| Fase | Construir | Métrica de éxito (gate) | Umbral | Tiempo estimado |
|---|---|---|---|---|
| **0. Eval-set** | 30 misiones reales reproducibles cubriendo: 10 Notepad/Settings/Explorer (UIA rico), 10 Chrome/Edge con flag (CEF), 5 Discord/Spotify (custom), 5 multi-app | Reproducibilidad: 2 runs sin agente, mismo estado final por verifier estructural | 100 % reproducible | 2 días |
| **1. Verify post-action** | `verify_post_action()` con UIA delta + dHash ROI + WinEvent hook; integración con tools `gui`, `uia`, `paste_typing` | Tasa de **false PASS** (verify dice OK pero el SO no cambió) en eval-set | <5 % | 3 días |
| **2. Macros parametrizadas** | `click_button(label)`, `fill_field(label, value)`, `select_menu(path)`, `toggle(label)`, `wait_for(label)`. Cada una con observe→act→verify→recover | Task SR por verifier estructural en eval-set Fase 0 | ≥40 % vs status quo (~15 %) | 5 días |
| **3. Cascada UIA→OCR→visión** | Tier router con cache de turno, RuntimeId rebind, flag CEF con consentimiento | SR sobre Discord/Spotify subset | 0 → ≥30 % | 3 días |
| **4. Recovery table** | Tabla P4 implementada + integración con loop-detector existente | Tasa clicks-sin-efecto **post-retry** | <10 % | 2 días |
| **5. Seguridad R0–R5** | Clasificador estructural + secret handoff + user-activity monitor + IsPassword gate | 0 leaks de password en logs/checkpoint en 100 runs sintéticos | 0 leaks | 3 días |
| **6. Speculative N=2** | Multi-action prediction validada step-by-step | Latencia p50 misiones 3-step | -25 % vs Fase 2 | 3 días |
| **7. Checkpoint mínimo** | Persistencia JSON + resume con confirmación | 100 % de misiones interrumpidas reanudan correctamente | 100 % | 1 día |
| **8. Visión gateada** | mmproj lazy + crops 384×384 + budget ≤2 calls/misión | SR en subset custom-render | +10 puntos sobre Fase 3 | 2 días |

**Métricas obligatorias por fase (loguear siempre):**

1. **Task Success Rate (real):** verificado por `mission_goal` estructural (pycaw, Path.stat, EnumWindows, registry diff), NUNCA por "el tool dijo ok".
2. **Steps per mission:** mediana y p95.
3. **Latencia p50 / p95** por turno de voz.
4. **Tasa de clicks-sin-efecto** (verify devolvió `confirmed_false`).
5. **Falsos PASS** (verify=ok, mission_goal=fail).
6. **LLM calls por misión** (gate de speculative).
7. **Vision calls por misión** (debe ser ≤1 promedio).
8. **Tasa de secret_handoff disparado correctamente** vs missed (campo password tecleado por error → SEV-1).

**Eval-set, reglas para evitar falsos PASS:**

- Cada misión define `goal_verifier()` que lee estado del SO, no del agente. Ejemplos:
  - "Subí volumen al 60%" → `pycaw.GetMasterVolumeLevelScalar() ∈ [0.58, 0.62]`.
  - "Abrí Notepad y escribí 'hola'" → `EnumWindows` encuentra Notepad Y UIA del Document = "hola\r\n".
  - "Enviá un mensaje en Discord" → leer la última row de UIA del chat (no del Send button) Y matchear el texto.
- **No usar "el tool devolvió True"** como evidencia (eso es lo que ya tiene el sistema actual y es justo el origen del falso PASS).
- Reproducibilidad: snapshot del estado pre-test (apps abiertas, foco, volumen) + reset script que lo restaura.

**Recommendations**

**Hacé esto antes del lunes (Fase 0–1, 5 días):**

1. **Armá el eval-set de 30 misiones reproducibles** con verifier estructural por misión. Sin esto, todo lo demás es opinión. Tirá el bench actual si está midiendo "estructura" en lugar de estado del SO.
2. **Implementá `verify_post_action()` con las tres señales (UIA delta + dHash ROI + WinEvent hook).** Es el GAP confirmado más crítico y arregla la mayor causa de deriva. Gate de éxito: <5 % falsos PASS en eval-set.
3. **Mediciones en TU hardware ANTES de confiar en mis números:** tok/s de Gemma 4 E4B Q4_K_M con tu flag set actual (sospechar si <30 o >80); latencia de UIA scan con/sin cacheRequest; tiempo de Gemma mmproj con un crop 384×384. Sin estos, el budget de latencia es hipótesis.

**Después (Fase 2–4, 10 días):**

4. **Refactorizá `gui` a macros parametrizadas.** No más `click_xy`; reemplazá por `click_button(label, app_context)` que internamente hace UIA-find → click → verify. El LLM no toca coordenadas.
5. **Aplicá la tabla de recovery P4 tal cual.** Integrala con tu loop-detector existente sin reescribirlo.
6. **Activá el flag CEF (`--force-renderer-accessibility=complete`) con consentimiento explícito del user por app, una sola vez.** No hagas relaunch silencioso.

**Después (Fase 5–8, 9 días):**

7. **Política de riesgo estructural + secret handoff.** No empieces a manejar passwords sin esto.
8. **Speculative N=2 con validación step-by-step** solo si las métricas justifican (acierto >80 % en next-action).
9. **Checkpoint JSON mínimo** SOLO para modo misión.
10. **Visión Gemma mmproj lazy y gateada,** crops ≤384×384, budget ≤2/misión.

**Umbrales que cambian las decisiones (si no se cumplen, revertí):**

- Si Fase 1 deja falsos PASS >10 % → arquitectura del verifier mala, NO seguir a Fase 2; revisar señales.
- Si Fase 2 deja Task SR <30 % en eval-set Tier-1 (UIA rico) → problema de macros o de UIA scan; no escalar a Fase 3.
- Si latencia p95 >7 s en Fase 2 → el 4B no está sirviendo para descomposición; reducir contexto o cambiar prompt.
- Si Vision calls/misión >2 en steady-state → la cascada está rota, no abusar del último recurso.
- Si tu hardware mide <30 tok/s en Gemma 4 E4B Q4 → o el flash-attn no está activo, o swa-full está rompiendo cache; revisar build y env vars LLAMA_*.

**Lo que NO recomiendo (riesgos):**

- **No reemplazar Gemma 4 E4B por un VLM nativo más chico (TinyClick 0.27B, Ferret-UI Lite 3B).** TinyClick solo hace grounding single-turn; según Apple Machine Learning Research (arXiv:2509.26539, sept 2025), Ferret-UI Lite *"achieves success rates of 28.0% on AndroidWorld and 19.8% on OSWorld"* y el paper concluye explícitamente que *"navigation in extended or more complex settings remains challenging for models under 3B parameters."* Ninguno reemplaza al 4B para descomposición + lenguaje + razonamiento.
- **No buscar paridad con UI-TARS-2/Holo3 o con OSWorld scores SOTA.** Esos modelos son 7B–35B con RL extensivo y datasets de GUI screenshots. Con tu stack, el techo realista es **40–60 % SR en Tier-1 (UIA rico) y 15–25 % SR en Tier-3 (custom-render)** — eso ya es enormemente útil para asistente de voz acotado.
- **No usar LangGraph/Temporal para checkpointing.** Over-engineering para turnos cortos. JSON atómico alcanza.

**Caveats**

- **Hipótesis vs hecho:** Los números de **latencia por componente en tu hardware son hipótesis**; basados en lo que llama.cpp reporta para Gemma 4 E4B en hardware comparable (Adrian Lee reporta *"~99 tokens/sec on an A10G GPU"* en Q4; en una GPU 6 GB Ampere/Ada el rango realista es 40–60 tok/s pero hay que medir). **Hechos verificables:** los SR de UFO² (27.9 % WAA con GPT-4o; 30.5 % con o1), los SR de UI-TARS-1.5/2, la existencia del mmproj oficial y la doc de `--mmproj`, la doc de `--force-renderer-accessibility=complete`, el comportamiento de `IsPasswordPropertyId`.
- **Conflicto de datos:** el usuario reporta "mmproj-F16 ~946 MB"; el repo oficial publica `mmproj-gemma-4-E4B-it-bf16.gguf` a **992 MB BF16** y `mmproj-gemma-4-E4B-it-Q8_0.gguf` a 560 MB. Hay variantes F16 third-party. Verificá el archivo exacto que tiene cargado (`sha256sum` vs el del repo `ggml-org/gemma-4-E4B-it-GGUF`).
- **Bug abierto a watcher:** llama.cpp issue #21402 reporta crash CUDA al cargar mmproj de Gemma 4 31B/26B-A4B en Blackwell. **E4B no está flaggeado**, pero conviene probar la combinación exacta antes de comprometer fases. Pin tu build de llama.cpp en algo verificado (b9090 es razonable; si crashea, downgrade).
- **Lo que ASUMO sin evidencia directa para tu setup:** que `--swa-full` + `--cache-reuse 256` se llevan bien con el cambio de prompt entre turnos (issues #15082 y #18497 reportan regresiones); medir `tokens_cached` en cada response es OBLIGATORIO para confirmar el reuse de prefix. Si está bajo, perdés gran parte del budget.
- **Lo que NO afirmo:** que un 4B local sin RL específico de GUI vaya a llegar a >40 % SR en eval-sets como WindowsAgentArena. La evidencia (UI-TARS papers) sugiere que el grounding entrenado es lo que mueve la aguja, y Gemma 4 E4B no fue entrenado específicamente para grounding GUI. Lo que SÍ afirmo es que en el subset de UIA rico, con macros deterministas + verify + recovery, el SR sube enormemente respecto al status quo de "click ciego".
- **Sobre `--force-renderer-accessibility=complete`:** funciona en Chrome 117+ con la variante `=complete` explícita; sin la variante el flag puede no activar AXMode completo (Blue Prism community thread). Probá con `inspect.exe` el árbol antes y después.
- **Sobre Gemma 4 audio nativo:** Google dice E4B soporta audio (30 s cap), pero **llama.cpp todavía no expone audio en llama-server** (discussion #21334). Mantené Whisper.cpp / Vosk como ASR aparte, no esperés a que esté.
- **Medir antes de confiar:** p50/p95 de cada componente en tu RTX/laptop con el LLM ya cargado y aplicaciones reales abiertas. Lab numbers + hardware vacío ≠ producción.