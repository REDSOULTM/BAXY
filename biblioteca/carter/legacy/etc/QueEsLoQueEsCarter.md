# Qué es lo que es Carter

> **Documento de visión y alcance.** Esta es la fuente de verdad sobre qué tiene
> que llegar a ser Carter en su fase actual. Antes de cualquier decisión técnica,
> el revisor (Claude o quien sea) debe leer esto primero para no desviarse hacia
> features fuera de scope.
>
> **Fase actual: NÚCLEO + CHAT DE TEXTO.**
> Voz, cámara, transcripción, vision en tiempo real, y todo lo multimodal queda
> explícitamente FUERA de esta fase.

---

## 1. Qué es Carter

Carter es un **asistente personal de IA local para Windows**, controlado por el
usuario. La meta es construir un **"Jarvis de texto"** — un agente que entiende
intención en lenguaje natural y ejecuta acciones reales sobre la PC del usuario,
sin depender de servicios cloud, sin telemetría, sin frontends web.

El usuario habla en español o inglés. Carter responde en el mismo idioma. El
usuario pide algo (abrir una app, leer un archivo, mandar un email, listar
procesos, configurar volumen, ejecutar código, agendar un evento), y Carter
hace exactamente eso, reportando éxito o falla con honestidad.

No es un chatbot. No es Copilot. No es un wrapper de ChatGPT. Es un agente
**local**, **privacy-first**, debe ser un jarvis, capaz de realizar cada tarea que el usuario le pida, que ejecuta tools reales sobre el sistema
operativo.

---

## 2. Lo que Carter SÍ tiene que hacer (alcance de esta fase)

### 2.1 Núcleo del agente
- Recibir texto del usuario en cualquiera de los dos idiomas (ES/EN) (Debe funcionar en todos los idiomas posibles).
- Decidir si hay que llamar tools o responder conversacionalmente.
- Ejecutar tools en orden, con manejo de errores honesto.
- Sintetizar la respuesta final con el resultado de los tools.
- Mantener continuidad de intención dentro de un turno (no cerrar antes de
  completar la meta del usuario).
- Cortar en seco si una acción es de alto riesgo y no fue auto-aprobada.

### 2.2 Chat de texto
- Conversación pura sin tools cuando corresponde (saludos, aritmética simple,
  preguntas conceptuales).
- Routing determinista cuando el LLM se equivoca: invariantes que rescatan
  casos como "mi IP" → memory_recall mal usado.
- Memoria persistente local: hechos del usuario, preferencias, candidatos.
- Catálogo de tools claro, con descripciones que el LLM pueda interpretar.

### 2.3 Tools que YA tienen que funcionar (165 cubiertos por probe_all_tools.py)
- **Sistema**: hora, RAM, disco, CPU, volumen, brillo, dark mode, locale,
  refresh rate, monitores, batería, uptime, audio devices, env vars, registry,
  servicios, clipboard, apps instaladas.
- **Filesystem**: read/write/append text, list, search, move, copy, delete,
  zip/unzip, stat (existencia), get_size.
- **Terminal**: PowerShell, comandos allowlisted, winget search/install.
- **Network**: ping, IP local/pública, DNS, port check, speed test, traceroute,
  Wi-Fi list/connect.
- **Process / Window**: list, focus, close, resize, move, screenshot, get_text,
  pin_on_top.
- **Web**: open URL, search en navegador específico, web_search, click/fill.
- **Apps**: app_open, app_close, app_uninstall.
- **Steam**: list_installed, is_installed, search store, run, stop.
- **Power**: shutdown, restart, lock, sleep, hibernate, signout, screen off.
- **Notifications / Scheduler**: toast, speak, sound, remind, scheduled tasks.
- **Email**: send, read inbox, read message, reply, list folders.
- **Calendar**: list, create, update, delete events.
- **Office / PDF**: pdf_read_text, pdf_merge, pdf_split, pdf_from_docx,
  pdf_to_images, office_pdf_export, find_replace, excel_create_chart.
- **Media**: audio_play, audio_record, audio_transcribe (archivo, no tiempo real),
  video_convert, video_extract_audio, video_trim, image_resize, image_convert.
- **Code/Git**: run_python, run_node, lint, format, git_status/diff/log/clone/
  push/pull.
- **Database**: sqlite query/execute/create, csv query, csv_to_excel.
- **Memory**: save, recall, search, context.
- **GUI básico**: gui_click, gui_type, gui_do, vision OCR como fallback.
- **Meta**: list_capabilities, describe_tool.

### 2.4 Calidad operativa
- pytest verde sin tests order-dependent.
- probe_all_tools.py ≥ 100% (excluyendo lo que el entorno no tenga, como Office).
- probe_text_hardening.py ≥ 80%.
- Ningún hook global persistente entre tests.
- Ningún `setx`, ningún `taskkill /F` sobre procesos del usuario.
- Configuración centralizada en `config.py` + `.env`.
- Errores reportados con honestidad — nunca mentir sobre éxito.

### 2.5 Backends LLM soportados
- llama-cpp-python in-process (preferido por velocidad y privacidad).
- llama-server localhost:8080 (con GBNF para output estructurado).
- LM Studio localhost:1234.
- Ollama localhost:11434 (con qwen3:8b o qwen3:14b por defecto).
- Cloud API solo si el usuario lo configura explícitamente vía `.env`.

---

## 3. Lo que Carter NO va a hacer en esta fase

**Estas features están explícitamente fuera de scope. No agregar, no preparar
infraestructura para, no "adelantar trabajo" sobre estas líneas.**

### 3.1 Multimodalidad en tiempo real (FUERA)

Carter es un Jarvis: **tiene que ver la pantalla** para poder operar la PC del
usuario. Lo que está fuera de scope es el modo *streaming continuo*, no la
visión puntual.

**FUERA de esta fase:**
- Voz en tiempo real (STT en streaming, TTS en streaming).
- Cámara / webcam / video en vivo del usuario.
- Transcripción de audio en tiempo real.
- **Loop continuo de análisis de pantalla** (vigilar el escritorio frame a frame
  sin que el usuario lo pida).
- Wake word, activación por voz.
- Modelos multimodales **como backend principal del agente** (llava, qwen-vl
  reemplazando al planificador de texto). El planificador es siempre un LLM de
  texto con tool-calling.

**DENTRO de esta fase (visión puntual permitida y necesaria):**
- `desktop_screenshot` y captura de ventana específica bajo demanda.
- OCR sobre captura para leer texto en pantalla cuando el usuario pregunta
  qué está viendo.
- Vision router como **fallback** cuando GUI nativa falla (`gui_click` no
  encuentra el botón → vision OCR para localizarlo).
- `window_inspect_active`, `window_list`, `window_get_text` y similares.
- Modelo de visión invocado como **tool puntual**, no como loop ni como
  backend principal. Una llamada por intención del usuario, no una cada
  N segundos.

Regla práctica: si el usuario tiene que pedirlo (explícito o vía intención de
turno), está dentro. Si Carter lo haría solo en un loop sin pedirlo, está
fuera.

### 3.2 Frontends que no sean texto plano (FUERA)
- GUI propia con botones/ventanas para Carter.
- Web app, dashboard.
- Mobile app.
- Notificaciones interactivas con UI rica.

### 3.3 Cloud y servicios externos (FUERA salvo que el usuario lo pida explícito)
- Telemetría, analytics, crash reporting hacia servidores externos.
- SaaS integrations no pedidas (Slack, Linear, Notion, Jira, Stripe, etc.).
- Auto-update desde internet.
- Sync entre dispositivos.

### 3.4 Comportamiento agresivo sobre el SO (PROHIBIDO)
- `setx` (mutación permanente del registro de Windows).
- `taskkill /F /IM` sobre procesos que no inició Carter.
- Modificación silenciosa de variables permanentes del usuario.
- Auto-instalación de paquetes sin confirmación.

### 3.5 Refactors fuera de scope (FUERA)
- Reescribir agent.py para soportar features futuras.
- Migrar a otro framework de tools.
- Cambiar la arquitectura de capabilities.
- Adelantar abstracciones para multimodal "por las dudas".

---

## 4. Principios de diseño no negociables

### 4.1 Privacy-first, local-first
Todo corre en la máquina del usuario. Si el usuario no configuró un backend
cloud, **nada sale de su PC**. Memoria en SQLite local. Modelos en disco local.

### 4.2 El LLM es el planificador, los invariants son el cinturón de seguridad
El modelo decide qué tool llamar. Los invariantes (reglas deterministas) solo
corrigen errores históricamente observados, sin reemplazar al LLM.

**No agregar invariantes nuevos por capricho.** Cada invariante debe responder
a un fallo real, reproducible, con test de regresión.

### 4.3 Honestidad sobre falla
Si una tool falla, el reply lo dice claro: "no encontré X", "permission denied",
"el archivo no existe". **Nunca afirmar éxito si `result.ok` es False.**

### 4.4 Una cosa por commit
Sin "refactor de paso". Sin "ya que estoy". Cada commit hace exactamente lo que
dice su mensaje.

### 4.5 Tests son la verdad
Si pytest falla, todo se detiene hasta entender por qué. No hay "el test está
mal, lo borramos". Los tests existen para evitar regresiones reales.

### 4.6 No agregar tools sin razón
El catálogo ya tiene 80+ tools. Agregar uno nuevo requiere:
- caso de uso real del usuario,
- compact description sin ambigüedad,
- test de routing en `probe_all_tools.py` o `probe_text_hardening.py`,
- entrada en el system prompt si es ambiguo con otra tool.

### 4.7 Compatibilidad con Windows como prioridad
Comandos PowerShell-friendly. No `&&`. No bash-isms. Paths con `\` o forward
slash, no mezclas. Manejar correctamente `C:\Users\...`.

---

## 5. Estado actual conocido (snapshot 2026-04-29)

- **pytest**: 815 passed, 0 failed.
- **probe_all_tools.py**: ~96–100% según corrida (algunos fallos de entorno por
  Office no instalado, file locks, no son regresiones lógicas).
- **probe_text_hardening.py**: pendiente de validar tras los commits de Gemini.
- **Branch**: `rebuild/v2-from-scratch`.
- **Bug crítico abierto** (a corregir esta sesión): `invariants.py` referencia
  tools inexistentes (`desktop_screenshot_analyze`, `window_get_active`).
- **Pendiente de revisión profunda**: `_dialogs.py` (538 líneas nuevas de
  Gemini, usadas por `steam.py`).

---

## 6. Cómo usar este documento

**Antes de cualquier sesión nueva con un agente (Claude, Opus, lo que sea):**
1. El agente lee este archivo PRIMERO.
2. Si el agente propone algo que cae en sección 3 (FUERA), se rechaza sin
   discutir. No es "flexible", está explícitamente fuera de scope.
3. Si el agente propone algo que viola sección 4 (principios), se rechaza.
4. Si el agente propone algo que está en sección 2 (alcance), se evalúa según
   su mérito técnico y prioridad.

**El responsable de mantener este documento al día es el usuario** (no los
agentes). Si el alcance cambia (por ejemplo, se aprueba empezar voz), el
usuario edita la sección 2 y mueve lo correspondiente fuera de la sección 3.

---

## 7. Definición de "listo" para esta fase

Carter v2 fase texto se considera **cerrada** cuando:

1. pytest = 815+ passed, 0 failed, suite completa, sin orden dependiente.
2. probe_all_tools.py = 100% sobre lo que el entorno permite probar.
3. probe_text_hardening.py = 100% (o ≥ 90% con justificación clara de fallos).
4. Cero `setx` / `taskkill /F` en código de runtime.
5. Cero hooks globales persistentes entre sesiones de tests.
6. Configuración centralizada — no hay `os.getenv` hardcoded por todo el repo.
7. Documentación coherente (`CLAUDE.md`, `TEXT_AGENT_CLOSURE.md`, `.env.example`,
   este archivo) sin contradicciones.
8. Carter responde con honestidad a fallos de tools (validado en categoría G
   de probe_text_hardening).
9. Carter no toca el SO de forma irreversible sin confirmación explícita.

Cuando esos 9 criterios se cumplan, **se cierra la fase de texto** y recién
ahí se discute la siguiente (probablemente: voz local con whisper.cpp + TTS
local, sin streaming en tiempo real al inicio).

---

## 8. Reglas para los agentes que trabajan en este repo

1. **No tomes decisiones de scope.** Si dudás si algo entra o no, preguntá al
   usuario. No "preparás infraestructura para más adelante".
2. **No optimices prematuramente.** Si funciona y está testeado, no lo toques.
3. **No inventes tool names.** Si vas a referenciar una tool, primero verificá
   en `tools.py` que existe con ese nombre exacto.
4. **No mientas en commits.** Si el commit fixea X, el mensaje dice "fix X",
   no "improvements". Si no validaste, no escribas "validated".
5. **No corras Carter interactivo en una sesión de auditoría.** No levantes
   Ollama, no inicies LLMs locales, salvo que el usuario lo pida explícito.
6. **Una cosa por commit.** Si encontrás dos bugs, dos commits.
7. **PowerShell-friendly.** No uses `&&`, no uses bash-isms.

---

*Última actualización: 2026-04-29 — fase texto en curso, núcleo + chat con
visión puntual permitida (sin streaming, sin loops continuos, sin wake word).*
