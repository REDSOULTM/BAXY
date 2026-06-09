# Baxy Agent

**Asistente de voz local para Windows — privado, OSS y corriendo en 4 GB de VRAM.**
*A local-first voice assistant for Windows, powered by Gemma 4 — 100% offline, no paid APIs.*

> **Nota:** el proyecto se renombró a **Baxy** (antes **Gemma 4 Agent**, brevemente **Carter**) — ese es el nombre del asistente. El modelo de lenguaje sigue siendo **Gemma 4** (de Google); solo cambió el nombre del producto y la palabra de activación.

[![Python](https://img.shields.io/badge/Python-3.10-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6.svg)](#-requisitos)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](#-licencia)
[![LLM](https://img.shields.io/badge/LLM-Gemma%204%20E2B-orange.svg)](https://ai.google.dev/gemma)

---

## ¿Qué es?

**Baxy** es un asistente de voz y texto que corre **100% en tu máquina**. Hablás (o escribís), el agente decide qué herramienta usar, opera tu PC y te responde por voz. No hay nube, no hay APIs de pago, no se envían tus datos a ningún lado: el modelo de lenguaje (Gemma 4 en formato GGUF) se sirve localmente con `llama.cpp` y todo el razonamiento, la transcripción y la síntesis de voz ocurren offline.

Está diseñado para **hardware modesto**: el target real es una laptop Windows con una GPU NVIDIA de **4 GB de VRAM** (o incluso sin GPU dedicada, cayendo a un perfil de CPU). El LLM, su visión multimodal y el cache de contexto entran completos en ese presupuesto; la transcripción y la voz corren en CPU para no robarle VRAM al modelo.

Pensado para ser **universal**: multi-idioma y multi-acento (el routing de intención usa embeddings multilingües, no listas de keywords por idioma), con **modos de accesibilidad** de primera clase (control 100% por voz para movilidad reducida, narración de cada acción para personas no videntes). El agente expone **67 herramientas compuestas** que cubren desde controlar el sistema operativo, navegadores, juegos y mensajería, hasta operar *cualquier* aplicación abierta mediante accesibilidad (UIA → OCR → visión nativa de Gemma).

---

## 🧭 Principios del proyecto

Los valores de diseño que definen a Baxy. No son aspiracionales: están cableados en el código y en los *gates* de aceptación, y se revisan en cada cambio.

- **El asistente no miente.** Nunca afirma haber hecho algo que no pudo verificar. Si una acción no se confirmó, la respuesta lo dice — no hay "éxitos" fabricados ni respuestas enlatadas. Cada acción se valida contra el estado real del sistema.
- **Inteligencia, no árboles de `if`.** Las decisiones (qué herramienta usar, qué responder) las toma el modelo, no tablas de respuestas fijas ni listas de keywords por idioma. Lo determinista se limita a clasificación por **embeddings multilingües**, **guardas estructurales** (que miden la forma, no el contenido) y **lectura del estado del SO**.
- **Universal por diseño.** Multi-idioma y multi-acento: funciona igual para cualquier persona, no se ajusta a una sola voz o idioma. La calidad se mide contra conjuntos diversos (por ejemplo, la *wake-word* se evalúa sobre un *held-out* de 25 voces en 13 idiomas).
- **Privado y local.** Todo corre en tu máquina: sin nube, sin APIs de pago obligatorias, sin enviar tus datos a ningún lado. Construido sobre software abierto y gratuito.
- **Medible y reproducible.** Nada se da por "funcionando" sin un número contra un criterio definido de antemano, y todo dataset o artefacto se puede regenerar desde scripts versionados.
- **Cuidadoso con lo irreversible.** Las operaciones destructivas (borrar, sobrescribir, cerrar lo que estás usando) piden confirmación antes de proceder.

---

## ✨ Características

### 🎙️ Voz
- **Pipeline de voz local de punta a punta**: `audio → VAD → wake-word → STT → corrector → LLM → TTS`.
- **Wake-word** **"Baxy"** (variantes reconocidas: *baxy* / *baxi* / *hey baxy*) (LiveKit conv-attention sobre ONNX; fallbacks openWakeWord), entrenada multi-idioma/multi-acento, con *throttle* de inferencia para no clavar la CPU en reposo.
- **VAD** con Silero + gate de silencio anti-alucinación.
- **STT** intercambiable: Whisper-small en CPU/int8 (faster-whisper, default) o Parakeet-TDT via sherpa-onnx (más rápido, no alucina en silencio). Corrector fuzzy (RapidFuzz + fonético) para nombres propios mal transcriptos.
- **TTS** Piper en streaming (voz default `es_MX-claude-high`): corta por oración y reproduce mientras el LLM sigue generando, con ventana anti-self-hearing.
- Multi-idioma / multi-acento, *ducking* de audio y *earcons*.

### 👁️ Visión
- **Visión nativa de Gemma 4** (mmproj): los screenshots se re-inyectan al modelo para razonamiento visual multimodal.
- **OCR** local con Tesseract (`locate_text` / `click_text`).
- **Screenshot** por monitor (primary / all / índice).
- **Entrada por cámara/gestos** (`vision_input/`, opcional, MediaPipe): gestos de mano, puntero por cabeza, *gaze* por iris. **Estado: POC de medición** — todavía no controla la GUI en producción.

### 🖥️ Computer-use / Accesibilidad
- **Operá cualquier app abierta** sin necesidad de una herramienta dedicada: dictás el objetivo en lenguaje natural y el agente lo descompone en pasos, verificando por estado del SO. Cascada **UIA → OCR → visión nativa**.
- **Control de bajo nivel** de mouse/teclado (screenshot, click, type, hotkey, scroll, drag, click por nombre de control vía UIA con verificación).
- **Modos de accesibilidad** respaldados por WCAG 2.1/2.2, activados por voz (clasificación por embeddings, no por keywords):
  - 🦮 **No vidente** — narra cada acción, lee la pantalla a demanda, describe errores y diálogos.
  - ♿ **Movilidad / manos libres** — control total por voz, nunca asume teclado/mouse, confirma por voz lo irreversible.

### 🧰 Herramientas (67 tools compuestas)
- **Sistema y hardware** — procesos, CPU/RAM/GPU, batería, brillo, energía; WiFi/Bluetooth/monitores; Windows Update, Defender, firewall, servicios, restore points; registro de Windows (con backup y rollback); variables de entorno; red (ping, traceroute, DNS, IP pública); periféricos/controles; impresoras y escáner (WIA); winget; Docker.
- **Audio y multimedia** — volumen/mute/media-keys; ruteo de audio por app; reproducción multi-provider (YouTube, Spotify, Netflix, Disney+, HBO Max, Prime Video, VLC, archivo local) con *now playing* vía SMTC; edición con ffmpeg (trim, concat, subtítulos, normalize EBU R128).
- **Apps, juegos y ventanas** — abrir/cerrar/desinstalar apps y juegos; **Steam** (resuelve AppID, lanza, instala y auto-confirma el diálogo); Epic/GOG/Xbox/Riot; gestión y *layout* de ventanas.
- **Navegador y web** — control del navegador visible; **automatización real con Playwright/CDP** (se adjunta a tu Chrome/Edge/Opera/Brave); investigación web (search/read/research); llenado de formularios (envío gateado); descargas con verificación SHA256 + Authenticode.
- **Mensajería** — **WhatsApp** (envío con verificación de foco, slot-filling multilingüe del destinatario/cuerpo, fallback wa.me); email (envío real solo con token de Microsoft Graph, si no devuelve `needs_user`); contactos (vCard RFC 6350).
- **Archivos y datos** — filesystem con checkpoints/rollback; búsqueda local por nombre/contenido; backups ZIP con dedupe SHA256; extracción de PDF/DOCX/XLSX/PPTX/HTML (texto, tablas, OCR); análisis de datos (pandas + matplotlib); SQLite/Postgres/MySQL; portapapeles.
- **Productividad** — notas y tareas; calendario offline (ICS RFC 5545); recordatorios/alarmas persistentes vía Task Scheduler; hábitos; *flashcards* con repetición espaciada (SM-2); Office (PowerPoint/Word/Excel, export PDF); rutinas con triggers; *watchers* de archivos/URLs.
- **Desarrollo** — detección de stack, tests/lint/format (pytest/ruff/npm/cargo/go), git status/diff/log, dev servers; terminal (gateado); *job manager*; bridge a ComfyUI.

### 🧠 Memoria, conocimiento y personalización
- **Knowledge / RAG local** — base de conocimiento sobre tus documentos (BM25 sobre SQLite FTS5 + rerank semántico opcional). *On por default.*
- **Memoria multicapa** — hechos explícitos, memoria semántica de turnos pasados (experience replay) y la capa **"Jarvis"** que aprende tus gustos observando *metadata* (app en foco, música que suena) — nunca contenido.
- **Skills** (spec Anthropic Agent Skills) — recetas en disco cargadas *lazy* por el LLM (selección semántica, sin keywords).
- **Microagents** (patrón OpenHands) — conocimiento de dominio inyectado por trigger.
- **Personas y perfiles de VRAM** — tono del asistente + perfiles que escalan los *caps* por turno.

> El detalle a fondo de cada subsistema (modelo, fine-tuning, RAG, memoria, skills y routing) está en **[🧬 El LLM y sus capas inteligentes](#-el-llm-y-sus-capas-inteligentes)**.

### 🧭 Routing inteligente
Decide qué subconjunto de tools ofrecer al LLM por turno — una **cascada semántica, no un árbol de if/else**:
- **Encoder fine-tuneado** (`paraphrase-multilingual-MiniLM-L12-v2`) re-entrenado en queries de tools multilingües.
- **Abstain head** calibrado: decide cuándo *no* ofrecer ninguna tool (charla, preguntas), con forward pass sub-milisegundo.
- **Tool2Vec + capa de keywords + confident-peak escape + reorden anti-primacy**, con cap de 5 tools por turno.

---

## 🧬 El LLM y sus capas inteligentes

El corazón de Baxy es **Gemma 4** (de Google) servido localmente, rodeado de varias capas que lo hacen *conocer* tu PC, tus documentos y tu historial — todas locales, sin nube. Esta sección documenta cada una en detalle, marcando lo que está **ON por default**, lo **opt-in** y lo **POC/experimental**.

### 🤖 El modelo y su contrato

- **Modelo:** **Gemma 4 E2B** en formato GGUF (`Q4_K_M`), servido por `llama.cpp` / `llama-server` con API OpenAI-compatible en loopback. El perfil `vram4` (default) lo corre con visión residente + KV cache en ~3.36 GB; el perfil `cpu` corre el mismo E2B-Q4 enteramente en CPU (visión off). Configurado en `infra/config.py` (`AgentConfig`, default `models/E2B/gemma-4-E2B-it-Q4_K_M.gguf`).
- **Contexto y sampling:** ventana de contexto **12288** tokens en el perfil activo `vram4` (bajada de 16384 para ahorrar ~168 MB de KV cache sin perder la compactación de historial; `context_size` por env la puede subir); sampling con `temperature=1.0`, `top_p=0.95`, `top_k=64`, `seed=-1` (aleatorio por request). Todo override-able por env `GEMMA4_AGENT_*` (ver tabla de Configuración). `max_tokens` por respuesta = 1280; hasta `max_agent_turns=8` de tool-calling encadenado por pedido.
- **Tool-calling:** el agente pasa los schemas de las tools al server y parsea las `tool_calls` que Gemma emite (`parse_tool_calls=True`); las llamadas son **secuenciales** por default (`parallel_tool_calls=False`). El cliente normaliza las respuestas y tiene rescues estructurales para cuando el modelo "leakea" una llamada como texto (`infra/llm_client.py`).
- **Thinking:** el modo *thinking* (razonamiento explícito) está **OFF por default** (`enable_thinking=False`) — togglearlo bustea el prefix-cache de `llama-server`, así que se mantiene apagado salvo cuando el flujo lo activa puntualmente.
- **Visión multimodal:** vía el **mmproj** de Gemma 4 (proyector F16). Los screenshots se re-inyectan al modelo para razonamiento visual. *On por default en el perfil `vram4`; off en el perfil `cpu`* y desactivable con `GEMMA4_MMPROJ_PATH=""`. El mmproj queda **RESIDENTE** por default (`GEMMA4_VISION_ALWAYS=1`, toggle en settings): medido que no penaliza el cache de texto (llama.cpp #21133) y evita la carga on-demand de la imagen (~2-5 s del modo lazy/router anterior).

#### Fine-tuning del LLM (QLoRA — *honestidad de tool-calling*)

El modelo base de Gemma 4 tiende a **inventar tools** que no existen cuando se le ofrece un catálogo grande. Se hizo un **fine-tune QLoRA** sobre Gemma 4 (familia E2B) cuyo objetivo medido es **0% de tools inventadas en producción** (con el array de tools provisto en el prompt). El gate se pasó: 0% de tools alucinadas en prod. Aprendizajes clave del proceso (auditar el 100% del dataset antes de entrenar, serializar bien los argumentos de tools) quedaron documentados en `dataset_finetune/`. Es una mejora de **fiabilidad del tool-calling**, no de conocimiento general: Gemma sigue siendo Gemma, solo deja de inventar herramientas.

> **Nota de honestidad:** el GGUF que corre en producción por default es el E2B-Q4 (ver `infra/config.py`). El pipeline de fine-tuning entrena en formato HF aparte; el binario GGUF activo se elige por el perfil de VRAM. Si no tenés el artefacto FT, el sistema corre igual con el modelo base.

### 📚 RAG / Knowledge base local

Baxy tiene una base de conocimiento **local** sobre *tus* documentos. **No es un RAG vectorial**: el retrieval base es **léxico (BM25) sobre SQLite FTS5** (un solo archivo `knowledge.sqlite`), con un **re-rank semántico opcional** que solo reordena los candidatos que BM25 ya trajo. El LLM redacta la respuesta a partir de los snippets recuperados — el tool *no* llama al modelo.

- **Tool `knowledge`** (compuesto: `status` / `ingest` / `search` / `list` / `delete`). **Registrado y ON por default** (lo ofrece el router; no está gated).
- **Ingesta:** parte el texto en chunks de ~2200 chars con 250 de solape, dedup por `sha256` del contenido, y lo guarda en una tabla virtual FTS5. Ingiere **directamente** solo texto plano: `.txt .md .json .csv .log .py .ps1 .yaml .yml`.
- **PDF / DOCX / XLSX / PPTX / HTML:** soporte **real pero indirecto** — pasan por un tool **separado** `document` (`domain_tools/document.py`, action `ingest_to_knowledge`), que extrae el texto con el backend correspondiente (pypdf/pdfplumber/python-docx/openpyxl/python-pptx/beautifulsoup4) y recién entonces lo entrega al knowledge store. Cada backend es **opt-in por dependencia** (reporta `needs_dependency` si falta).
- **Búsqueda + rerank:** BM25 trae los candidatos; si el rerank está activo, un **cross-encoder** (`cross-encoder/ms-marco-MiniLM-L-6-v2`, ~80 MB, vía `sentence-transformers`) re-puntúa los pares *(query, snippet)* para subir precisión. **ON por default**, degradable: `GEMMA4_KNOWLEDGE_RERANK=false` → BM25 puro; `GEMMA4_RERANK_MODEL` cambia el modelo; el llamador puede pasar `rerank=true/false` por tool-call. Si `sentence-transformers` o el modelo no están, **cae limpio a BM25** (no falla).
- **Honestidad:** si la búsqueda no encuentra coincidencias **no** marca el resultado como "falso" (eso hacía que el modelo dijera "no lo encontré"); setea `search_complete_no_matches` y guía al LLM a responder con su propio conocimiento si es pregunta general.

> **Alcance honesto:** es RAG **léxico** (BM25) con rerank semántico opcional sobre *tus notas y documentos personales* — no un RAG vectorial/semántico de gran escala sobre el contenido. Es funcional y testeado, no POC.
>
> *Fuente: `memory_pkg/knowledge.py`, `domain_tools/document.py`, `tools_pkg/tools.py`.*

### 🧠 Memoria multicapa

Baxy tiene **cuatro** sistemas de memoria distintos, todos **locales** (`~/.gemma4/` y el `state_dir`), sin nube, dimensionados para hardware modesto:

1. **Hechos explícitos** (`memory_pkg/memory.py`) — store JSON clave/valor de hechos sobre vos ("mi ciudad es…"). Lo escribe el LLM con la tool `memory.save`, o se auto-extrae del chat si activás la extracción (**OFF por default**). Tope 500 hechos con evicción por *salience*: un hecho explícito pesa más que uno auto-extraído, y recordarlo lo refuerza. Se inyecta entero al prompt si es chico, o por relevancia semántica si crece.
2. **Memoria semántica de experiencias** (`memory_pkg/experience.py`) — el *experience replay* del producto, **ON por default** (`GEMMA4_EXPERIENCE_MEMORY=false` lo apaga). Cada turno completado se embedea (384-dim, el mismo MiniLM multilingüe del router) y se guarda en SQLite con `sqlite-vec`. En el turno siguiente recupera los top-K (k=3) turnos pasados más parecidos y le inyecta **lecciones de tool-selection** ("para este tipo de pedido, estas tools funcionaron / **EVITAR**: esto falló"). **Clave de honestidad:** *no* le pasa al modelo el **texto** de la respuesta pasada (para que un modelo chico no lo copie como plantilla), solo qué-tools-con-qué-args-y-qué-resultado. Auto-prune por antigüedad/tamaño y recuperación ante corrupción de la DB.
3. **Capa "Jarvis" proactiva** (`ambient_observer.py`, `behavior_log.py`, `taste_profile.py`, `pattern_miner.py`) — observa qué hacés *realmente* para conocerte. Un observador de ambiente mira **qué app tenés en foco** y **qué música suena** (vía Windows SMTC), registrando **solo METADATA**: nombre de proceso y `"artista - título"` + franja horaria — **nunca** títulos de ventana, teclado, clipboard, pantalla ni navegación (por diseño, ver docstring de `ambient_observer.py`). De ahí arma un **perfil de gustos determinista** (sin LLM: cuenta dwell por app, artista dominante, franjas; con umbrales anti-ruido y dedup de sesión) que se rinde como **párrafo en lenguaje natural** (técnica *Guided Profile Generation*, arXiv:2409.13093) y se inyecta al prompt como contexto de fondo, cacheado con TTL para no romper el budget de latencia. Un **minero de patrones** detecta rutinas repetidas y, con cooldowns anti-molestia, te **ofrece** automatizarlas.
4. **Reflexión de gustos por LLM** (`taste_reflection.py`) — capa **OPT-IN** (default-OFF, corre en *background*, no por turno) que pasa el perfil observado por el propio Gemma local para inferir gustos de más alto nivel ("preferís rock latino de los 90"), con un **guard anti-alucinación** que descarta toda inferencia que no cite un dato observado real.

**Privacidad:** todo es local, **inspectable** ("¿qué sabés de mí?"), **borrable** ("olvidá lo que sabés de mí", con confirmación porque es irreversible) y **pausable por flags**. Además están las **sesiones** y el **estado** (`sessions.py`, `state.py`) para mantener contexto e identidad del turno.

### 🧩 Skills + Microagents

Dos mecanismos ortogonales para darle conocimiento/recetas al LLM **sin keywords**:

- **Skills** (`tools_pkg/skills_registry.py`, spec **Anthropic Agent Skills**) — cada skill es una carpeta con `SKILL.md` (frontmatter YAML: `name`, `description`, `priority`, `requires`). Al boot se escanean y se inyecta un **menú** (name + description, ~50 tokens c/u) al system prompt; el LLM decide **semánticamente** cuál cargar full vía `skill_load()` — carga **lazy on-demand**. Las skills `priority: critical` se eager-loadean (reservado para guardas de seguridad/honestidad). `requires` filtra por elegibilidad (exes en PATH, env vars, OS). Cap de `skill_load()` por turno según el perfil de VRAM. Opt-out: `GEMMA4_SKILLS_OFF=1`.
- **Microagents** (`memory_pkg/microagents.py`, patrón **OpenHands**) — markdown con frontmatter (`name`, `triggers`, `priority`). Cuando un trigger matchea el turno, el body se **appendea al system prompt** como conocimiento de dominio (qué significa "HKCR", "mmproj", etc.). Selección **semántica con word-boundary** (no substring crudo, que confundía "RAG" ⊂ "Dragon"). Cache por sesión para preservar el KV-cache, cap defensivo de 3 por selección. Opt-out: `GEMMA4_MICROAGENTS_OFF=1`.

### 🧭 Routing semántico (qué tools se le ofrecen al LLM)

El router (`routing/`) decide **qué subconjunto de tools ofrecer** al LLM en cada turno. Es una **cascada semántica**, no un árbol de if/else, y su norte es la **precisión** (ofrecer solo lo necesario), porque el recall ya está saturado (holdout 0.9964):

- **Encoder fine-tuneado** — `paraphrase-multilingual-MiniLM-L12-v2` (384-dim) re-entrenado en queries de tools multilingües sintéticas + el split de dev. Sube el recall de holdout 0.835 → 0.878 y el *NO-TOOL keep* 0.512 → 0.628, con la **misma latencia CPU**. Si el artefacto FT no está (checkout fresco), **cae al modelo base** automáticamente (`routing/semantic_router.py`). Regenerable con `scripts/train_router_encoder.py` + `scripts/router_ft_pipeline.py`.
- **Abstain head** calibrado — decide cuándo **no** ofrecer ninguna tool (charla, preguntas), con forward pass sub-milisegundo, más un *confident-peak escape*: una tool cuyo coseno domina claramente y le gana al runner-up por un gap escapa del gate de abstención (p.ej. "mutea" → `audio`).
- **Tool2Vec + capa de keywords** — embeddings por tool alineados al catálogo + señales léxicas, con bar propio para tools MCP (que viven en un rango de coseno más bajo que las nativas).
- **Reorden anti-primacy** (**ON por default**, `GEMMA4_ANTIPRIMACY=0` lo apaga) — pone la tool de dominio de mayor confianza **primera** en el subset (los LLMs atienden más a lo que aparece primero, *Lost in the Middle*, arXiv:2307.03172). No cambia el **conjunto**, solo el **orden**: las tools de infraestructura quedan al final y se respetan los invariantes del `pending_intent`.
- **Cap de 5 tools por turno** (`MAX_SELECTED_TOOLS`, override `GEMMA4_MAX_SELECTED_TOOLS`) — un subset grande infla el prefill y empuja al modo thinking sin beneficio; medido, el recall de holdout es idéntico con 10 vs 16 tools, así que el cap recorta la cola de bajo valor.

---

## 🛠️ Tecnologías

### Núcleo LLM / inferencia
| Tecnología | Rol |
|---|---|
| **Gemma 4 E2B** (GGUF, `Q4_K_M`) | LLM principal (~3.36 GB con visión residente + KV) |
| **mmproj F16** | Proyector multimodal (visión) de Gemma |
| **llama.cpp / llama-server** (build CUDA) | Servidor de inferencia GGUF; API OpenAI-compatible en loopback |

### Runtime, servidor y UI
| Tecnología | Versión | Rol |
|---|---|---|
| **CPython** | 3.10 | Intérprete de runtime del agente |
| **FastAPI** | 0.119.1 | API HTTP del agente |
| **Uvicorn** | 0.38.0 | ASGI server |
| **Pydantic** | 2.12.5 | Validación de la API |
| **pywebview** | 6.2.1 | Ventana nativa de escritorio que embebe la UI web |
| **React** | 19 | UI web (`ui_field/`) |
| **Vite** + **TypeScript** | 8 / ~6 | Bundler + lenguaje de la UI |

### Voz
| Tecnología | Versión | Rol |
|---|---|---|
| **faster-whisper** (CTranslate2) | 1.2.1 | STT por defecto (Whisper-small, int8/CPU) |
| **sherpa-onnx** + Parakeet-TDT | 1.13.2 | STT alternativo (más rápido, CPU int8) |
| **Piper TTS** | 1.4.2 | TTS por defecto (streaming por oración) |
| **silero-vad** | 6.2.1 | Voice Activity Detection |
| **openWakeWord** / LiveKit ONNX | >=0.6 | Wake-word ("Baxy"; variantes: baxy / baxi / hey baxy) |
| **onnxruntime** | 1.23.2 | Backend ONNX (wake-word, VAD) |
| **sounddevice** | 0.5.5 | I/O de audio (PortAudio) |
| **rapidfuzz** / **jellyfish** | 3.14.5 / 1.2.1 | Corrección fuzzy + fonética |

### Embeddings / routing
| Tecnología | Versión | Rol |
|---|---|---|
| **sentence-transformers** | 5.3.0 | Embeddings multilingües (routing, deícticos, rerank) |
| `paraphrase-multilingual-MiniLM-L12-v2` | 384-dim | Clasificación de intención por embeddings |
| **torch** | 2.10.0 | Backend de embeddings + silero-vad |

### Automatización / computer-use (Windows)
| Tecnología | Versión | Rol |
|---|---|---|
| **Playwright** | 1.55.0 | Automatización de navegador (CDP) |
| **uiautomation** (UIA) | 2.0.29 | Lectura del árbol de accesibilidad + foco de ventanas |
| **mss** | 10.2.0 | Capturas de pantalla rápidas |
| **pywin32** | 311 | Control de ventanas / SO |
| **comtypes** / **pycaw** | 1.4.16 / 20251023 | COM + control de audio por estado del SO |
| **psutil** | 6.1.1 | Procesos / threads |
| **winsdk** | 1.0.0b10 | SMTC ("now playing") para el observador de ambiente |
| **MediaPipe** + **OpenCV** (opt-in) | 0.10.x / 4.11 | Control por cámara/gestos (opcional) |

### Datos / documentos / integraciones (opcionales)
sqlite-vec, pandas, openpyxl · Pillow, python-docx, python-pptx, pypdf, PyMuPDF, pdfplumber, matplotlib, beautifulsoup4 · clientes DB (mysql/postgres) · paho-mqtt · **mcp** 1.27.1 (cliente MCP, default-OFF) · dateparser.

---

## 📋 Requisitos

### Hardware
- **Windows** (el agente usa APIs nativas de Windows: UIA, SMTC, pywin32).
- **GPU NVIDIA con 4 GB de VRAM** (perfil `vram4`, recomendado) — el modelo + visión + KV cache entran completos en ese presupuesto (medido ~3.36 GB con visión).
- **Sin GPU dedicada / GPU ocupada por un juego**: perfil `cpu` (`-ngl 0`) que corre el mismo E2B-Q4 enteramente en CPU (0 VRAM, visión OFF, más lento pero usable). Auto-fallback si no se detecta NVIDIA.
- **RAM**: laptop ~8 GB (Whisper-small añade ~900 MB de RAM de inferencia). *Mínimo no especificado formalmente.*
- **Disco**: el GGUF E2B-Q4 + mmproj rondan ~2–3 GB; el stack de voz añade ~300 MB de deps + ~490 MB de modelos.
- **Voz y STT no consumen VRAM**: corren en CPU (int8) por diseño.
- **Latencia objetivo**: tier-Alexa, 4–5 s por turno de voz.

### Software
- **Python 3.10** (runtime verificado: 3.10.11).
- **llama.cpp / llama-server con CUDA** (binario externo, **no incluido**). Build mínimo recomendado con soporte de tool-calling de Gemma 4 (PRs de parser/tokenizer). Esperado por default en `C:\llamacpp-cuda\bin\llama-server.exe`.
- **Runtime CUDA 12** para faster-whisper GPU (wheels `nvidia-cublas-cu12` / `nvidia-cudnn-cu12`; `scripts/setup_cuda_runtime.py` reubica las DLLs en Windows).
- **Node + pnpm** para buildear la UI web (React 19 + Vite 8 + TS).
- **Modelos GGUF** — el fine-tune de Baxy (texto + visión) está publicado en
  **[huggingface.co/REDSOULTM/baxy-gemma4-E2B-GGUF](https://huggingface.co/REDSOULTM/baxy-gemma4-E2B-GGUF)**
  (~4.4 GB, descarga aparte; no van en git por tamaño). El CLI `hf` viene con
  `huggingface_hub`, que se instala con `requirements.txt` (dependencia de
  `sentence-transformers`); si hiciera falta: `pip install -U huggingface_hub`.
- **Deps de sistema gratis** (el agente puede instalarlas): **ffmpeg** (audio), **espeak-ng** (fonemizador de Piper), **VLC** (media).

---

## 🚀 Instalación

```powershell
# 1. Clonar el repo
git clone https://github.com/REDSOULTM/Baxy.git
cd Baxy

# 2. venv Python 3.10 + deps de runtime
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
# -c constraints.txt fija numpy==1.26.4 (TOPE DURO): py3langid pide numpy>=2 pero
# numpy 2.x rompe pandas y, con él, el encoder del router. El constraint gana siempre.
pip install -r requirements.txt -c constraints.txt
# (opcional) voz y cámara — el mismo constraint protege el stack:
pip install -r requirements-voice.txt -c constraints.txt
pip install -r requirements-camera.txt -c constraints.txt

# 3. CUDA runtime para faster-whisper (stage de las DLLs cuBLAS; idempotente)
python scripts\setup_cuda_runtime.py

# 4. llama.cpp con CUDA — colocá llama-server.exe en:
#    C:\llamacpp-cuda\bin\llama-server.exe
#    (o configurá GEMMA4_LLAMA_SERVER_EXE con otra ruta)

# 5. Descargar el modelo GGUF — el FINE-TUNEADO de Baxy (texto + visión)
#    (es el que corre en producción: 0% tools inventadas + replies multi-idioma)
hf download REDSOULTM/baxy-gemma4-E2B-GGUF gemma-4-E2B-it-Q4_K_M.gguf --local-dir models\E2B
hf download REDSOULTM/baxy-gemma4-E2B-GGUF mmproj-F16.gguf            --local-dir models\E2B
#    Alternativa (Gemma 4 BASE de Unsloth, SIN el fine-tune de Baxy): reemplazá
#    el repo por `unsloth/gemma-4-E2B-it-GGUF`. Baxy corre igual, pero el modelo
#    base puede inventar tools y responder siempre en español tras una acción.

# 6. Build de la UI web (React/Vite)
cd gemma4_agent\ui_field
pnpm install
pnpm run build          # tsc -b && vite build  ->  ui_field/dist/
cd ..\..

# 7. Verificar y correr
python -m gemma4_agent.launcher status   # model / mmproj / llama-server = OK
python -m gemma4_agent.launcher ui
```

> **Gotchas conocidos** (ver `CLAUDE.md` para el detalle): ONNX Runtime puede congelar la PC en loops pesados (importar `scripts/_ort_throttle.py` antes de cargar modelos ONNX); `espeak-ng` en Windows escupe UTF-8 (default cp1252, hay un patch en el venv); usar comillas simples para paths Windows en YAML; `torchvision` está intencionalmente fuera de `requirements.txt`.

---

## ▶️ Uso

```powershell
# UI web en ventana nativa pywebview (default)
python -m gemma4_agent.launcher ui
python -m gemma4_agent.launcher ui --browser     # abre en el navegador del sistema
python -m gemma4_agent.launcher ui --no-window   # headless (solo server)

# Chat por consola
python -m gemma4_agent.launcher chat
python -m gemma4_agent.launcher chat --no-start-server

# Solo el llama-server (según el perfil activo)
python -m gemma4_agent.launcher server

# Diagnóstico (paths del modelo/exe, server online?, ctx, nº de tools)
python -m gemma4_agent.launcher status

# Otros: smoke (tests sin LLM), open <carpeta>, shortcut (.cmd de escritorio),
#        mcp (expone las tools como servidor MCP), sin args -> menú interactivo
```

Entry points equivalentes (de `pyproject.toml`): `gemma4-launcher`, `gemma4-chat`, `gemma4-server`.

**Ejemplos de lo que le podés pedir** (por voz o texto, en cualquier idioma):
- *"Subí el volumen al 30 y poné rock en Spotify."*
- *"Mandale a Mamá un WhatsApp diciendo que llego en 20 minutos."*
- *"Instalame Terraria de Steam."*
- *"Abrí Discord, andá al canal general y escribí 'hola'."*
- *"Conectame al WiFi de casa."*
- *"Resumime este PDF y guardalo como conocimiento."*
- *"¿Cuánta RAM tengo libre?"*
- *"Sacá una captura y describime qué hay en pantalla."*

---

## 🏗️ Arquitectura

```
Probando Gemma 4/
├── pyproject.toml              entry points: gemma4-launcher / gemma4-chat / gemma4-server
├── requirements*.txt           deps de runtime / voz / cámara
├── CLAUDE.md                   reglas operativas del repo (gotchas, restricciones)
├── models/E2B/                 GGUF activos (gitignored): E2B-Q4_K_M + mmproj-F16
├── scripts/                    download, setup CUDA, evals, diagnóstico
└── gemma4_agent/
    ├── agent_core/             el agente: run_content en 3 fases (decide → execute → finalize)
    ├── tools_pkg/              registro de tools compuestas, schemas, dispatch, MCP
    ├── domain_tools/           ~40 áreas de capacidad (calendar, contacts, whatsapp, office, ...)
    ├── routing/                decide qué tools ofrecer (planner híbrido, cap 5)
    ├── voice/                  pipeline de voz (VAD, wake, STT, TTS, corrector)
    ├── computer_use_pkg/       control de Windows (UIA, verificación visual, accesibilidad)
    ├── memory_pkg/             memoria, conocimiento, sesiones, estado, capa Jarvis
    ├── safety_pkg/             guardas: verifiers, grounding, anti-loop, confirmaciones, SSRF
    ├── infra/                  plomería: launcher, config, perfiles VRAM, llama_server, server
    ├── ui_field/               UI web (React + Vite); se buildea a ui_field/dist/
    ├── vision_input/           control por cámara/gestos (MediaPipe) — opcional, POC
    └── mission/                misiones multi-paso (goal, checkpoint, outcome)
```

**Flujo de un turno**: la UI manda el input al `AgentRunner` → el **routing** decide qué tools ofrecer → el **LLM** (servido por `llama-server`) elige y encadena tools → cada acción pasa por las **guardas de safety** (verificación post-acción, confirmación de lo irreversible) → se valida el reply y se devuelve a la UI (con TTS si es voz). Al arrancar (`launcher ui`), se levanta un server FastAPI en un puerto bindeable, se construye el agente en background y se gestiona el proceso de `llama-server` según el **perfil de VRAM activo**; la ventana pywebview muestra la UI web servida desde `ui_field/dist/`.

---

## ⚙️ Configuración

Config central en `gemma4_agent/infra/config.py` (`AgentConfig`); perfiles de VRAM en `gemma4_agent/infra/profiles.py`. El estado del usuario se persiste en `~/.gemma4/` (`active_profile.txt`, `profiles.json`, `gui.json`, `logs/`).

**Perfiles**: `vram4` (GPU, default — todo en ≤4 GB, ctx 12288) · `cpu` (sin GPU, 0 VRAM, visión off) · `standby` (server apagado, UI en solo-lectura).

Variables de entorno `GEMMA4_*` más relevantes:

| Variable | Qué controla |
|---|---|
| `GEMMA4_MODEL_PATH` | Ruta al GGUF del modelo |
| `GEMMA4_MMPROJ_PATH` | Ruta al mmproj (visión); `""` lo desactiva |
| `GEMMA4_LLAMA_SERVER_EXE` | Ruta a `llama-server.exe` |
| `GEMMA4_AGENT_SERVER` | URL del llama-server (default `http://127.0.0.1:8080`) |
| `GEMMA4_AGENT_CONTEXT` | Tamaño de contexto (`-c`) |
| `GEMMA4_AGENT_MODE` | Modo del agente (`auto`, `fast_action`, `deep_action`, `research`, ...) |
| `GEMMA4_AGENT_MAX_TOKENS` / `_TEMPERATURE` / `_TOP_P` / `_TOP_K` / `_SEED` | Sampling |
| `GEMMA4_AGENT_SAFETY` | Activa el safety classifier (default off) |
| `GEMMA4_DEFAULT_PROFILE` | Perfil del primer arranque |
| `GEMMA4_LLAMA_GPU_VENDOR` | Fuerza `cuda` / `cpu` / `vulkan` (salta detección de hardware) |
| `GEMMA4_NO_GPU_AUTOCPU` | `0` desactiva el auto-fallback a perfil `cpu` sin NVIDIA |
| `GEMMA4_FLASH_ATTN` | `on`/`off` flash-attn (default `off`) |
| `GEMMA4_LLAMA_API_KEY` | Si se setea, el server exige `Authorization: Bearer` |
| `GEMMA4_UI_HOST` / `GEMMA4_UI_PORT` | Bind de la UI web |
| `GEMMA4_AGENT_MEMORY` / `_STATE` / `_TRACE_PATH` / `_CAPTURES` | Paths de memoria/estado/traza |

---

## 📄 Licencia

El código de este proyecto se distribuye bajo licencia **MIT** (ver `LICENSE`).

> **Nota sobre dependencias y modelos de terceros**: este agente combina paquetes con licencias mixtas. La mayoría son permisivas (MIT/BSD/Apache/PSF). Tené en cuenta al redistribuir:
> - **El modelo Gemma** se licencia bajo los **[Gemma Terms of Use](https://ai.google.dev/gemma/terms)** de Google (con su *Prohibited Use Policy*), **no** bajo una licencia OSI. Revisá los términos antes de cualquier uso comercial.
> - **Parakeet-TDT** (STT opcional) es **CC-BY-4.0** → exige atribución.
> - Las **voces de Piper** tienen licencia por voz — revisá la de la voz que uses.
> - Los **clientes de DB** (mysql-connector, etc.) pueden tener restricciones de redistribución.

---

## 🙏 Créditos

Este proyecto se apoya en el trabajo de muchos proyectos OSS:

- **[Gemma](https://ai.google.dev/gemma)** — Google DeepMind (modelo de lenguaje).
- **[llama.cpp](https://github.com/ggml-org/llama.cpp)** — inferencia GGUF local.
- **[Unsloth](https://github.com/unslothai/unsloth)** — GGUFs de Gemma 4 y pipeline de fine-tuning.
- **[faster-whisper](https://github.com/SYSTRAN/faster-whisper)** / **[Whisper](https://github.com/openai/whisper)** (OpenAI) — STT.
- **[Parakeet](https://huggingface.co/nvidia)** (NVIDIA) + **[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)** — STT alternativo.
- **[Piper](https://github.com/rhasspy/piper)** (rhasspy) — TTS.
- **[Silero VAD](https://github.com/snakers4/silero-vad)** — detección de actividad de voz.
- **[openWakeWord](https://github.com/dscripka/openWakeWord)** / **[LiveKit](https://github.com/livekit)** — wake-word.
- **[sentence-transformers](https://www.sbert.net/)** — embeddings multilingües para el routing.
- **[Playwright](https://playwright.dev/)**, **[uiautomation](https://github.com/yinkaisheng/Python-UIAutomation-for-Windows)**, **[MediaPipe](https://developers.google.com/mediapipe)** — automatización y visión.
- **[FastAPI](https://fastapi.tiangolo.com/)**, **[React](https://react.dev/)**, **[Vite](https://vite.dev/)**, **[pywebview](https://pywebview.flowrl.com/)** — server y UI.

Patrones de diseño inspirados en **[Anthropic Agent Skills](https://www.anthropic.com/)** (skills) y **[OpenHands](https://github.com/All-Hands-AI/OpenHands)** (microagents).

---

<sub>Asistente local, privado y OSS. Sin nube, sin APIs de pago, sin enviar tus datos a ningún lado.</sub>
