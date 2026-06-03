# Carter Agent

**Asistente de voz local para Windows — privado, OSS y corriendo en 4 GB de VRAM.**
*A local-first voice assistant for Windows, powered by Gemma 4 — 100% offline, no paid APIs.*

> **Nota:** el proyecto se llamaba **Gemma 4 Agent** y se renombró a **Carter** (el nombre del asistente). El modelo de lenguaje sigue siendo **Gemma 4** (de Google); solo cambió el nombre del producto y la palabra de activación.

[![Python](https://img.shields.io/badge/Python-3.10-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6.svg)](#-requisitos)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](#-licencia)
[![LLM](https://img.shields.io/badge/LLM-Gemma%204%20E2B-orange.svg)](https://ai.google.dev/gemma)

---

## ¿Qué es?

**Carter** es un asistente de voz y texto que corre **100% en tu máquina**. Hablás (o escribís), el agente decide qué herramienta usar, opera tu PC y te responde por voz. No hay nube, no hay APIs de pago, no se envían tus datos a ningún lado: el modelo de lenguaje (Gemma 4 en formato GGUF) se sirve localmente con `llama.cpp` y todo el razonamiento, la transcripción y la síntesis de voz ocurren offline.

Está diseñado para **hardware modesto**: el target real es una laptop Windows con una GPU NVIDIA de **4 GB de VRAM** (o incluso sin GPU dedicada, cayendo a un perfil de CPU). El LLM, su visión multimodal y el cache de contexto entran completos en ese presupuesto; la transcripción y la voz corren en CPU para no robarle VRAM al modelo.

Pensado para ser **universal**: multi-idioma y multi-acento (el routing de intención usa embeddings multilingües, no listas de keywords por idioma), con **modos de accesibilidad** de primera clase (control 100% por voz para movilidad reducida, narración de cada acción para personas no videntes). El agente expone **67 herramientas compuestas** que cubren desde controlar el sistema operativo, navegadores, juegos y mensajería, hasta operar *cualquier* aplicación abierta mediante accesibilidad (UIA → OCR → visión nativa de Gemma).

---

## ✨ Características

### 🎙️ Voz
- **Pipeline de voz local de punta a punta**: `audio → VAD → wake-word → STT → corrector → LLM → TTS`.
- **Wake-word** "hey gemma" (LiveKit conv-attention sobre ONNX; fallbacks openWakeWord), con *throttle* de inferencia para no clavar la CPU en reposo.
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

### 🧠 Memoria y personalización
- **Capa "Jarvis"** — observador de ambiente (artista/título que suena vía SMTC, app en foco, franja horaria — **metadata, no contenido**) que arma un perfil de gustos inyectado al prompt. Inferencia de gustos finos opcional con el propio Gemma local (default-OFF, en background, con guard anti-alucinación). Local, inspectable y borrable.
- **Skills** (spec Anthropic Agent Skills) — recetas en disco cargadas *lazy* por el LLM (selección semántica, sin keywords).
- **Microagents** (patrón OpenHands) — conocimiento de dominio inyectado por trigger.
- **Knowledge / RAG local** — SQLite FTS5 + rerank cross-encoder opcional.
- **Personas y perfiles de VRAM** — tono del asistente + perfiles que escalan los *caps* por turno.

### 🧭 Routing inteligente
Decide qué subconjunto de tools ofrecer al LLM por turno — una **cascada semántica, no un árbol de if/else**:
- **Encoder fine-tuneado** (`paraphrase-multilingual-MiniLM-L12-v2`) re-entrenado en queries de tools multilingües.
- **Abstain head** calibrado: decide cuándo *no* ofrecer ninguna tool (charla, preguntas), con forward pass sub-milisegundo.
- **Tool2Vec + capa de keywords + confident-peak escape**, con cap de 5 tools por turno.

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
| **openWakeWord** / LiveKit ONNX | >=0.6 | Wake-word ("hey gemma") |
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
- **Modelos GGUF** E2B-Q4_K_M + mmproj-F16 (descarga aparte, no versionados).
- **Deps de sistema gratis** (el agente puede instalarlas): **ffmpeg** (audio), **espeak-ng** (fonemizador de Piper), **VLC** (media).

---

## 🚀 Instalación

```powershell
# 1. Clonar el repo
git clone <repo>
cd "Probando Gemma 4"

# 2. venv Python 3.10 + deps de runtime
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
# (opcional) voz y cámara:
pip install -r requirements-voice.txt
pip install -r requirements-camera.txt

# 3. CUDA runtime para faster-whisper (stage de las DLLs cuBLAS; idempotente)
python scripts\setup_cuda_runtime.py

# 4. llama.cpp con CUDA — colocá llama-server.exe en:
#    C:\llamacpp-cuda\bin\llama-server.exe
#    (o configurá GEMMA4_LLAMA_SERVER_EXE con otra ruta)

# 5. Descargar el modelo GGUF (Hugging Face / Unsloth)
hf download unsloth/gemma-4-E2B-it-GGUF gemma-4-E2B-it-Q4_K_M.gguf --local-dir models\E2B
hf download unsloth/gemma-4-E2B-it-GGUF mmproj-F16.gguf            --local-dir models\E2B

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
