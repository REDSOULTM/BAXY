# Prompt de investigación — Control GUI tipo humano (computer-use) para un agente local con Gemma 4 E4B en vram4

> Pegá TODO lo de abajo (desde "===") en claude.ai. Está escrito para que la
> respuesta sea APLICABLE a nuestro stack real, no genérica. Pedí fuentes.

---

===

# Rol y objetivo

Sos un arquitecto de agentes de automatización GUI en Windows. Necesito un plan
técnico **accionable, medido y con fuentes** para que mi asistente de voz local
pueda **controlar el PC como un humano** (mouse + teclado + leer la pantalla) y
completar "misiones imposibles" que los tools genéricos no cubren —
navegar UIs arbitrarias, clickear botones, llenar formularios, encadenar pasos—
**manteniendo calidad alta y latencia mínima** bajo restricciones duras de hardware.

No quiero un ensayo genérico sobre "computer use agents". Quiero decisiones
concretas para MI stack, con números, trade-offs medibles, y código/pseudocódigo
donde aplique. Si algo no es viable bajo mis restricciones, decílo explícitamente.

# Mi stack EXACTO (confirmado, no asumas otra cosa)

- **Modelo:** Gemma 4 E4B-it, Q4_K_M (GGUF), ~4B efectivos. Servido por
  **llama.cpp `llama-server` build b9090** con flags reales:
  `--jinja --flash-attn on --swa-full --cache-reuse 256 --keep -1 -c 16384 --parallel 1 --n-gpu-layers 99 --no-mmap`. Monoslot.
- **Visión:** Gemma 4 multimodal vía `mmproj-F16` (~946 MB de VRAM extra). Se
  carga BAJO DEMANDA (lazy) por un router por-turno; un turno de texto NO paga
  el costo de visión. Activar visión por cada paso GUI es CARO.
- **Hardware target:** laptop modesto, **GPU de 6 GB de VRAM** (perfil "vram4").
  El LLM ya consume ~4–5 GB. La RAM/VRAM es escasa. (El dev tiene una RTX 4060 Ti
  16GB SOLO para entrenar; NO es el target de runtime.)
- **OS:** Windows 11. Python 3.10 en runtime.
- **Librerías GUI ya instaladas y disponibles:** `pyautogui`, `mss` (screenshot
  rápido multi-monitor), `Pillow`, `opencv (cv2)`, `paddleocr`, `uiautomation`
  (yinkaisheng), `pywinauto`, `pywin32` (win32api/win32gui). NO tengo Tesseract.
- **Latencia objetivo (tier-Alexa):** 4–5 s por turno de voz es el tope; 8 s es
  UX catastrófica. Un click ciego es instantáneo; el problema es el costo de
  PERCIBIR la pantalla y razonar sobre ella por cada paso.

# Lo que YA tengo (no me lo propongas como nuevo — construí ENCIMA de esto)

- **Primitivos de input REALES** (control humano del PC, ya funcionan):
  - Mouse vía Win32 `SetCursorPos` + `mouse_event` (click, double, right, scroll,
    drag), con validación de bounds del virtual-screen (multi-monitor).
  - Teclado vía SendKeys/Win32 (type, keypress, hotkey).
  - Screenshot vía `mss` (virtual screen completo).
  - OCR vía PaddleOCR (`locate_text`, `click_text`).
  - `locate_image` (template matching).
- **Árbol UIA** (tool `uia`): tree / find / click / focus / set_value, leyendo
  Name/ControlType/AutomationId/BoundingRect vía `uiautomation`. Sirve la mayoría
  de apps nativas; en CEF/Chromium (Discord/Spotify/Slack) el árbol puede venir
  vacío sin el flag `--force-renderer-accessibility=complete`.
- **Foco de ventana "golden"**: AllowSetForegroundWindow + ALT-trick +
  AttachThreadInput + ShowWindow restore/maximize.
- **Deeplinks** vía registry HKCR (steam://, spotify:, ms-settings:, etc.).
- **Resolución de apps universal** (Get-StartApps en idioma del usuario +
  difflib SequenceMatcher ≥0.75 cross-lingual, sin hardcodes por app).
- **Verificadores estructurales** por-tool: pycaw (volumen), EnumWindows (foco),
  Path/stat (filesystem) — devuelven confirmed True/False/None (None=no verificable).
- **mission_goal** (verifier por-misión estilo Voyager) + **loop detector**
  (5 patrones result-aware + no_progress) + **honesty guard** (nunca decir "hecho"
  sin evidencia).
- **GAP CONFIRMADO en mi código:** el tool `gui` hace **"click es dispatch ciego
  sin verify post"** — disparo clicks pero NO verifico que cambien algo. No hay
  loop observe→act→verify. El LLM coordina clicks sueltos, y un 4B lo hace mal en
  misiones multi-paso (deriva, alucina estado, loopea).

# Restricciones de producto (LEY, no negociables)

1. **100% local y gratis.** Nada de cloud APIs de pago, nada de Picovoice.
2. **Universal / multi-idioma / multi-app.** PROHIBIDO hardcodear: nada de
   `if "spotify" in user_text`, nada de listas de keywords por idioma, nada de
   tablas por-app (URLs/nombres). Nada de respuestas enlatadas. La clasificación
   de intención se hace por **embeddings multilingües** (ya tengo un encoder
   paraphrase-multilingual-MiniLM-L12-v2) con fallback seguro, o por **estructura
   del SO** (registry/UIA/pycaw), nunca por listas léxicas. Lo determinista
   permitido: estructural (mide forma, no contenido) o semántico (embeddings).
3. **Un 4B local NO es un VLM de 7B+ nativo.** No le pidas razonamiento que no
   tiene. El código determinista resuelve lo que pueda; el LLM solo decide
   intención ambigua + descomposición + explicación.
4. **vram4 manda.** Si una solución necesita un modelo más grande, otro VLM
   residente, o cargar mmproj por cada paso, marcala como NO-VIABLE o como
   "solo último recurso, raro".

# Preguntas concretas que necesito respondidas (con fuentes y números)

## P1 — Arquitectura del loop observe→act→verify→recover (PRIORIDAD MÁXIMA)
- ¿Cuál es la mejor arquitectura para un loop de control GUI confiable con un
  **4B local** (no VLM nativo)? Compará: (a) el LLM emite primitivos sueltos
  (status quo, falla), (b) macros deterministas parametrizadas
  (`click_button(label)`, `fill_field(label, value)`) que internamente
  observan→actúan→verifican, (c) un agente VLM-style que ve screenshots cada paso.
- ¿Cómo separar responsabilidades para que el 4B solo decida el OBJETIVO
  ("mandá 'hola' a Pedro en Discord") y el código determinista resuelva los pasos?
- Fuentes recientes: UFO² (Microsoft), OS-Copilot/FRIDAY, Agent-S2, UI-TARS,
  computer-use de Anthropic/OpenAI — ¿qué transfiere a un 4B local y qué NO?

## P2 — Verificación post-acción SIN VLM (cabe en vram4)
- Quiero verificar que un click/type "hizo algo" sin gastar un VLM-call por paso.
  Compará por latencia/fiabilidad en Windows: **frame-diff** (hash de pixeles
  antes/después con `mss`, ¿qué threshold por canal evita falsos por cursor/
  blinking?), **UIA delta** (re-leer el árbol y comparar Name/estado),
  **Win32 events** (SetWinEventHook EVENT_SYSTEM_FOREGROUND/EVENT_OBJECT_*),
  **GetForegroundWindow/título**. ¿Cuál combinación da mejor señal con <50ms?
- ¿Cómo distinguir "cambió la pantalla por mi acción" de "cambió por animación/
  notificación/reloj"? (frame-diff ingenuo da falsos).
- ¿Cuándo es INEVITABLE caer a visión (Gemma 4 mmproj) y cómo minimizar su uso
  (gate por UIA-vacío + OCR-falló, cropping, resolución reducida)?

## P3 — Cascading de percepción (UIA → OCR → visión) bajo presupuesto
- Diseñá la cascada: ¿en qué orden y con qué criterios de "fall-through"?
  Para apps nativas (UIA rico), CEF/Chromium (¿el flag
  `--force-renderer-accessibility=complete` es la respuesta? ¿efectos
  secundarios? ¿cómo relanzar la app con el flag sin romper la sesión del user?),
  apps custom-render/juegos (solo pixeles).
- ¿Cómo representar la pantalla como TEXTO para que el 4B la consuma
  (lista de elementos `[id] tipo "label" @bbox`), con qué cap de elementos y
  caracteres para no inflar el prompt (recordá: ctx 16K, latencia)?
- ¿Conviene cachear la observación UIA por turno y reusarla? ¿RuntimeId para
  re-bindear elementos sin re-escanear?

## P4 — Recuperación de errores en GUI (pre-retry actions)
- Cuando un paso GUI falla (target_not_found, stale element, foco perdido),
  ¿qué acción determinista conviene ANTES de reintentar? (refocus window,
  reinspect UIA, reobserve, wait-short). Dame la tabla
  `(tipo_de_fallo) → (acción_pre_retry, presupuesto_de_reintentos)`.
- ¿Cómo evitar loops infinitos de clicks (ya tengo loop-detector result-aware;
  cómo integrarlo con el loop GUI)?

## P5 — Riesgo y seguridad de un agente que controla mouse/teclado
- Un agente que mueve el mouse y teclea puede hacer daño (cerrar cosas, mandar
  mensajes equivocados, tocar UIs sensibles). ¿Qué política de riesgo estructural
  recomendás (clasificar la acción GUI por riesgo, gates de confirmación para
  irreversibles/comunicación, detección de campos de password/secretos para NO
  teclear/loguear)? ¿Cómo manejar el "secret handoff" (el agente necesita que el
  user escriba una contraseña) sin que el secreto entre al historial/checkpoint?
- ¿Cómo no pelear con el usuario por el control del mouse (si el user está usando
  la PC)? ¿Detección de actividad de input del user para ceder/pausar?

## P6 — Latencia: presupuesto por paso GUI
- Dame un presupuesto realista por paso (observar + decidir + actuar + verificar)
  en mi hardware (Gemma 4 E4B Q4 en GPU 6GB, ~40–60 tok/s). ¿Cuántos pasos GUI
  caben en una misión antes de violar UX? ¿Cómo paralelizar/anticipar (speculative
  multi-action de UFO²: predecir N acciones en 1 LLM call)? ¿Vale para un 4B o es
  riesgoso?
- ¿Conviene "modo misión" (presupuesto de latencia relajado, el user sabe que es
  una tarea larga) vs "modo voz" (tier-Alexa, atómico)?

## P7 — Durable execution / checkpoint de misiones largas
- Para misiones de muchos pasos, ¿vale checkpoint/resume (persistir el plan +
  pasos completados, reanudar tras crash/interrupción)? ¿O es over-engineering
  para un asistente de turnos cortos? Si vale, ¿el diseño mínimo?

## P8 — Plan de implementación por fases, medible
- Proponé un roadmap por fases con un **gate medible por fase** (qué número
  define éxito), empezando por lo de menor riesgo/mayor ROI. Para CADA fase:
  qué construir, cómo medirlo, y el umbral que decide si sigo o reviero.
- ¿Cómo armo un **eval-set de misiones GUI reales** representativo y reproducible
  (no un bench que mida "estructura" y dé falsos PASS)? ¿Qué métricas
  (task success real verificado por estado del SO, no por "el tool dijo ok";
  pasos por misión; latencia p50/p95; tasa de clicks-sin-efecto; falsos PASS)?

# Formato de la respuesta que quiero

1. **TL;DR** con las 3–5 decisiones de mayor impacto.
2. Respuesta por pregunta (P1–P8) con **tablas comparativas con criterios
   medibles**, no prosa vaga.
3. **Código/pseudocódigo** concreto donde aplique (frame-diff verifier, cascada,
   tabla de recovery, política de riesgo), en Python para Windows con las libs
   que YA tengo.
4. **Qué es VIABLE en vram4 vs NO-VIABLE**, explícito.
5. **Fuentes citadas** (papers 2024–2026, docs oficiales de Windows UIA/Win32,
   issues de llama.cpp, repos de computer-use agents). Preferí fuentes recientes
   y verificables; marcá lo que sea hipótesis tuya vs hecho con fuente.
6. **Caveats**: qué afirmás con evidencia vs qué asumís; qué medir en mi hardware
   antes de confiar en un número.

Sé escéptico y honesto: si "controlar el PC como humano de forma confiable" no es
alcanzable con un 4B local hoy para misiones arbitrarias, decílo y dame el subset
que SÍ es alcanzable (ej. apps con buen UIA) y dónde está el techo real.
