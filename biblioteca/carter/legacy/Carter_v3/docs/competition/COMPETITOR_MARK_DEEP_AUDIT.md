# COMPETITOR_MARK_DEEP_AUDIT.md
# Mark XXXIX — Auditoría Profunda
# Generado por: Claude Code (claude-sonnet-4-6) — 2026-05-06
# FUENTE: Código leído directamente desde Extras/Mark-XXXIX-main/Mark-XXXIX-main/

---

## 1. Arquitectura general

Mark XXXIX es un asistente de PC basado **100% en Gemini Live API**. Su arquitectura es una capa delgada sobre la API de Google:

```
Micrófono → sounddevice → PCM 16kHz → Gemini Live WebSocket
                                              ↓
                                    Gemini responde con:
                                    - Text completions
                                    - Audio output 24kHz
                                    - Tool call requests
                                              ↓
                                    JarvisLive._execute_tool()
                                              ↓
                                    Action modules (18 tools)
                                              ↓
                                    Result devuelto a Gemini Live
```

Toda la "inteligencia" vive en el modelo de Google. Mark no tiene lógica de razonamiento propia.

## 2. Loop principal

`main.py` → clase `JarvisLive`:
- Loop async (`asyncio`) con reconnect automático (3s delay on disconnect)
- `client.aio.live.connect()` — WebSocket persistente con Gemini
- `_receive_loop()` procesa respuestas del servidor
- `_send_audio()` envía chunks de micrófono continuamente
- Tools declaradas como JSON schemas en `TOOL_DECLARATIONS` al inicio de la sesión
- LLM elige herramienta → `_execute_tool()` → `loop.run_in_executor(None, lambda: action_fn())`

## 3. Modelo / LLM

| Rol | Modelo |
|---|---|
| Main session (voz + texto + tools) | `models/gemini-2.5-flash-native-audio-preview-12-2025` |
| Planner (plan de pasos) | `gemini-2.5-flash-lite` |
| Replanner (cuando falla) | `gemini-2.5-flash` |
| Error handler | `gemini-2.5-flash-lite` |
| Fix generator | `gemini-2.0-flash` |
| Summarizer | `gemini-2.5-flash-lite` |
| Web search | `gemini-2.5-flash` con google_search grounding |
| Vision session | `models/gemini-2.5-flash-native-audio-preview-12-2025` (instancia separada) |

**Todo cloud. Cero modelo local. Sin Ollama. Sin llama.cpp. Sin privacidad.**

API key: `config/api_keys.json`. Si no hay internet o cuota de Gemini agotada → 100% offline = no funciona.

## 4. Tool calling

18 tools declaradas en `TOOL_DECLARATIONS`:
- `open_app`, `web_search`, `weather_report`, `send_message`, `reminder`, `youtube_video`
- `screen_process`, `computer_settings`, `browser_control`, `file_controller`
- `desktop_control`, `code_helper`, `dev_agent`, `agent_task`
- `computer_control`, `game_updater`, `flight_finder`, `file_processor`
- `save_memory`, `shutdown_jarvis`

Dispatch en `_execute_tool()`: `if name == "open_app": ...` — 18 ramas `elif`.

Sin verificación post-acción. Sin verifier. Sin CONFIRMED vs UNVERIFIED. El LLM asume que la acción fue exitosa si no hubo excepción.

## 5. Transcripción / Voz

- Input: `sounddevice` stream PCM 16-bit 16kHz → Gemini Live. Sin STT local.
- Output: Gemini Live retorna PCM audio 24kHz → `sounddevice.RawOutputStream`. Sin TTS local.
- Voz hardcoded: "Charon" (Gemini voice) en dos lugares (`main.py` y `actions/screen_processor.py`).
- Transcripciones mostradas en log via `input_audio_transcription` / `output_audio_transcription` del server.
- Mute: F4 toggle.

## 6. GUI / Computer control

- `actions/computer_control.py`: pyautogui para mouse/teclado. `pygetwindow` para ventanas.
- `actions/desktop.py`: gestión de ventanas (minimize, maximize, close, list).
- `actions/screen_processor.py`: mss para screenshots, cv2 para webcam, Gemini vision para análisis.
- Sin AttachThreadInput, sin mouse_event Win32, sin acceso a UIA/accessibility tree.
- **Limitación crítica**: Apps CEF (Steam/Discord/Spotify) con chromium embebido no son controlables con pyautogui básico.
- `send_message.py`: pyautogui UI automation con hardcodes de layout para WhatsApp/Telegram/Discord.

## 7. Memoria

- Archivo: `memory/long_term.json`
- Estructura: 6 categorías (`identity`, `preferences`, `projects`, `relationships`, `wishes`, `notes`)
- Guardado: LLM llama `save_memory(category, key, value)` → merge + trim a 2200 chars
- Contexto: inyectado como texto plano al system prompt al conectar
- Sin secret filter. Sin dedup sofisticado. Sin SQLite.
- No persiste historial de conversaciones, solo hechos.

## 8. Manejo de errores

1. Per-tool exception → `speak_error(name, e)` → log + TTS del error
2. AgentExecutor step errors → `analyze_error()` llama a Gemini para clasificar: `retry/skip/replan/abort`
3. `generate_fix()` → Gemini genera un script Python para arreglar el problema
4. Reconnect loop en JarvisLive (3s delay)
5. Vision session: exponential backoff 2s→30s max

**Sin policy pre-LLM. Sin guards post-reply. Todo el error handling es reactivo, no preventivo.**

## 9. Logging

- `LogWidget` en UI muestra mensajes con typewriter effect, codificados por color por tipo
- Transcripciones input/output visibles en el log
- Archivo de log no visible en el código revisado (no hay logging.FileHandler)

## 10. Seguridad

**Seguridad muy débil:**
- Sin policy engine pre-LLM
- Sin regex de dangerous patterns
- Sin guards post-reply para fake success
- Sin secret filter en memoria
- Sin verificación de acciones destructivas
- Sin autoaprobar/negar risk levels
- La única protección es Gemini rechazando solicitudes peligrosas (cloud, no controlable por el usuario)
- `shutdown_jarvis` tool solo apaga la app, pero no bloquea comandos destructivos del sistema

## 11. UX

- PyQt6 HUD animado con esferas, partículas, waveform, crosshair — 60fps custom paint
- Estados claros: LISTENING/THINKING/PROCESSING/SPEAKING/MUTED
- Métricas en tiempo real: CPU/MEM/NET/GPU/TEMP (psutil + nvidia-smi)
- Drag-and-drop de archivos
- Primera vez: overlay de setup para API key
- **La UX visual es la mayor fortaleza de Mark frente a Carter**

## 12. Cosas que Mark hace MEJOR que Carter

1. **UX visual** — HUD animado, estados claros, waveform en tiempo real
2. **Voz nativa integrada** — Gemini Live audio nativo, sin pipeline separado
3. **Cámara funcional** — mss + cv2 + Gemini vision en producción
4. **Agent task planner** — Gemini genera plan JSON con hasta 5 pasos, 3 reintentos, 2 replanes
5. **Progress visible** — estados de UI claros durante ejecución
6. **Browser con Playwright** — automatización real de navegador (tabs, forms, clicks, smart_click)
7. **Memoria categorizada** — 6 categorías semánticas, más estructurado que texto plano
8. **Multi-OS** — Windows + macOS + Linux (aunque con limitaciones)
9. **Error recovery LLM-driven** — Gemini analiza el error y decide retry/replan/abort

## 13. Cosas que Mark hace PEOR que Carter

1. **100% cloud** — sin Gemini, no funciona. Sin internet, inútil.
2. **Sin verificación de acciones** — asume éxito si no hay excepción. Fake success por diseño.
3. **Sin policy engine** — cualquier comando peligroso llega al ejecutor.
4. **Sin fake success guard** — puede decir "hecho" sin evidencia.
5. **Sin fuzzy resolver de recursos** — la lista de 64 app aliases es exacta o falla.
6. **Hardcodes masivos** — 64 app aliases, layout de WhatsApp/Telegram, voz "Charon", prefijo "JARVISReminder_".
7. **Sin tests** — cero test suite visible.
8. **Identidad robada** — "JARVIS", "Tony Stark's AI" — violación de trademark, proyecto no publicable como producto.
9. **Sin memory secret filter** — puede guardar contraseñas en la memoria.
10. **Sin step budget** — AgentExecutor puede loopear indefinidamente si el planner manda más de 5 pasos.
11. **Sin causal baseline para acciones** — si el proceso ya estaba abierto, Mark reporta éxito igual.

## 14. Partes que NO se deben copiar de Mark

- El nombre "JARVIS" / "Tony Stark" (trademark de Marvel/Disney)
- La `_APP_ALIASES` dict de 64 entradas (hardcode por app, anti-Carter)
- La dependencia a Gemini como único backend
- El fake success implícito (sin verifier)
- El pyautogui para send_message (frágil, hardcodea layout de apps)
- La voz "Charon" hardcoded
- El prefijo "JARVISReminder_" hardcoded
- El error handler que pide a Gemini "escribir un script Python fix" (superficie de ataque)

## 15. Ideas adaptables de Mark a Carter

1. **Agent task planner con pasos JSON** — separar planner del executor, con max_steps y retry_count
2. **Progress reporting de estados** — "Ejecutando paso 1/3: Abriendo..." (no la animación, el concepto)
3. **Error classification** — categorizar error en retry/skip/abort de forma estructural (sin LLM, con reglas)
4. **Browser Playwright** — Carter no tiene automatización real de browser; Mark sí
5. **Vision session separada** — cuando se necesita visión, instancia separada del modelo, no contaminar el turn loop
6. **Categorías de memoria** — considerar 3-5 categorías semánticas en la memory store de Carter
7. **Webcam snapshot** — cv2 para capturar foto de la cámara física cuando corresponda
8. **Primera ejecución UX** — wizard de configuración para Ollama/modelo/API key

---

## Tabla comparativa Mark vs Carter

| Área | Mark XXXIX | Carter v3 | Ganador | Qué tomar de Mark | Qué evitar de Mark |
|---|---|---|---|---|---|
| LLM backend | Gemini solo (cloud) | Configurable (local+cloud) | **Carter** | Nada | Dependencia cloud obligatoria |
| Verificación de acciones | Sin verifier (fake success implícito) | 14 verifiers con causal baseline | **Carter** | Nada | Sin verifier |
| Seguridad | Sin policy pre-LLM, sin guards | PolicyEngine + 8 guards | **Carter** | Error classification pattern | Sin policy |
| Voz | Gemini Live nativo, en producción | No implementado aún | **Mark** | Pipeline separado para voice session | Voz hardcoded a Gemini |
| Cámara | mss + cv2 + Gemini vision, funcional | No implementado aún | **Mark** | Webcam snapshot concept | Gemini como única vision |
| UX / Progreso | HUD PyQt6, estados visuales, progress | Sin progress reporting aún | **Mark** | Progress reporting concept | UI de 1500 líneas monolítica |
| Planner | Gemini genera JSON plan | Agent loop con step_budget | **Carter** (más robusto) | Max_steps + retry_count explícitos | LLM-generated plan frágil |
| Browser | Playwright real (tabs, forms, smart_click) | Sin browser automation real | **Mark** | Playwright integration idea | Nada específico |
| Memoria | JSON categorizado, 6 categorías | SQLite con secret filter, dedup | **Carter** | Categorías semánticas | Sin secret filter, sin dedup |
| Hardcodes | 64 app aliases, muchos strings fijos | Clean (hardcode_guard verifica) | **Carter** | Nada | Toda la lista de aliases |
| Tests | Sin test suite | 490 tests, hardcode_guard | **Carter** | Nada | Sin tests es inaceptable |
| Privacy | 100% cloud, sin control del usuario | Local-first, configurable | **Carter** | Nada | Cloud obligatorio |
| Identity | "JARVIS", trademark violation | "Carter", nombre propio | **Carter** | Nada | Nombre de marca ajena |
| Recovery | LLM analiza y replana | 1 retry para app_open | **Mark (parcialmente)** | Replan concept estructural | LLM para fix generation |
| App control CEF | pyautogui básico, falla en CEF | AttachThreadInput + mouse_event | **Carter** | Nada | pyautogui sin CEF support |

---

## Respuestas a preguntas clave

- ¿Mark tiene mejor transcripción? **SÍ** — Gemini nativo. Pero es cloud obligatorio.
- ¿Mark tiene mejor loop de estados? **Parcialmente** — estados UI claros, pero sin policy.
- ¿Mark muestra progreso mejor? **SÍ** — estados UI visibles. Carter no tiene esto aún.
- ¿Mark maneja contexto de pantalla mejor? **NO** — Gemini vision, pero sin UIA ni OCR local.
- ¿Mark tiene mejor UX conversacional? **SÍ visualmente** — pero sin honestidad sobre acciones.
- ¿Mark usa cloud de forma obligatoria? **SÍ, absolutamente.**
- ¿Mark tiene hardcodes? **SÍ, masivos.**
- ¿Mark inventa éxitos? **SÍ, por diseño** — sin verifier, asume éxito.
- ¿Mark es más simple que Carter? **SÍ** — es una capa delgada sobre Gemini. Carter tiene arquitectura propia.
- ¿Qué puede aprender Carter? **Progress reporting, browser Playwright, vision session separada, error classification estructural.**
