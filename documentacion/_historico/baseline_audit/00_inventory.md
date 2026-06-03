# Fase 0 — Inventario crudo

> Alcance: solo el paquete `gemma4_agent/`. Excluidos del análisis:
> `__pycache__`, `design_handoff_carter_field/`, `logs/`, `captures/`, `data/`,
> `docs/`, `ui_field/node_modules/`, `ui_field/dist/`, `ui_field/.pytest_cache/`.
> Fuera del paquete (resto del repo raíz: `chat_carter.py`, `harness_carter540/`,
> `PARA_AGENTE_CARTER_PROMPTS_SEPARADOS.md`, etc.) directamente no se analiza —
> es Carter y va a la categoría "deuda Carter".
>
> Fecha del corte: 2026-05-16. Generado con AST walk sobre 135 archivos `.py`.

---

## 1. Agregados de alto nivel

| Métrica | Valor |
|---|---:|
| Archivos `.py` analizados | 135 |
| Archivos de producción (no test, no scripts/) | 82 |
| Archivos de test (`test_*.py`) | 44 |
| Archivos de scripts/probes manuales | 9 |
| LOC totales (incluyendo blancos/comentarios) | 55 633 |
| LOC sólo código | 45 513 |
| Clases top-level | 193 |
| Funciones top-level | 999 |
| Configuración versionada del runtime | **0** (no hay `requirements.txt` ni `pyproject.toml` ni `setup.py` ni `uv.lock` ni `Pipfile` en ningún lado del repo) |
| Persistencia en disco | 4 SQLite + 2 JSON + 1 JSONL |
| Subpaquetes Python | `voice/` (6 archivos), `ui/` (18 archivos), `scripts/` (9 archivos) |
| Subcarpetas no Python | `skills/` (10 skills × `SKILL.md`), `microagents/` (5 .md), `ui_field/` (React+Vite+TS), `data/`, `captures/`, `logs/`, `docs/`, `design_handoff_carter_field/` |

### Top 25 archivos por LOC

| Rank | LOC | #cls | #fn | mtime | Path |
|---:|---:|---:|---:|---|---|
| 1 | **10 539** | 1 | 314 | 2026-05-16 | `domain_tools.py` |
| 2 | **4 825** | 4 | 47 | 2026-05-16 | `tools.py` |
| 3 | **2 968** | 3 | 25 | 2026-05-16 | `agent.py` |
| 4 | 2 666 | 0 | 92 | 2026-05-16 | `test_gx_features.py` |
| 5 | 1 657 | 1 | 43 | 2026-05-16 | `ops_tools.py` |
| 6 | 1 616 | 3 | 1 | 2026-05-15 | `ui/main_window.py` |
| 7 | 1 519 | 2 | 16 | 2026-05-15 | `server.py` |
| 8 | 1 247 | 1 | 5 | 2026-05-15 | `ui/settings.py` |
| 9 | 892 | 2 | 11 | 2026-05-16 | `planner.py` |
| 10 | 863 | 3 | 8 | 2026-05-16 | `voice/stt.py` |
| 11 | 726 | 1 | 4 | 2026-05-15 | `llama_server.py` |
| 12 | 690 | 0 | 19 | 2026-05-15 | `verifiers.py` |
| 13 | 659 | 4 | 6 | 2026-05-15 | `mission_goal.py` |
| 14 | 617 | 8 | 1 | 2026-05-15 | `test_whatsapp.py` |
| 15 | 576 | 1 | 1 | 2026-05-15 | `voice/controller.py` |
| 16 | 552 | 2 | 3 | 2026-05-15 | `agent_runner.py` |
| 17 | 535 | 0 | 46 | 2026-05-16 | `test_verifiers.py` |
| 18 | 532 | 1 | 12 | 2026-05-15 | `profiles.py` |
| 19 | 490 | 1 | 6 | 2026-05-15 | `llm_client.py` |
| 20 | 489 | 1 | 5 | 2026-05-16 | `experience.py` |
| 21 | 489 | 1 | 6 | 2026-05-14 | `chat.py` |
| 22 | 485 | 0 | 17 | 2026-05-15 | `launcher.py` |
| 23 | 482 | 1 | 0 | 2026-05-14 | `ui/hud.py` |
| 24 | 456 | 1 | 15 | 2026-05-15 | `skills_registry.py` |
| 25 | 443 | 1 | 4 | 2026-05-15 | `telemetry.py` |

### Top clases gigantes (`>=200` LOC o `>=15` métodos)

| LOC | #métodos | Archivo::Clase @ línea |
|---:|---:|---|
| **3 157** | **142** | `tools.py::ToolRegistry` @ L1486 |
| **1 852** | 21 | `agent.py::Gemma4Agent` @ L608 |
| 1 430 | 53 | `ui/main_window.py::MainWindow` @ L186 |
| 1 148 | 22 | `ui/settings.py::SettingsDialog` @ L83 |
| 495 | 27 | `voice/controller.py::VoiceController` @ L81 |
| 488 | 11 | `voice/stt.py::StreamingSTT` @ L375 |
| 476 | 11 | `agent_runner.py::AgentRunner` @ L72 |
| 451 | 26 | `ui/hud.py::HudCanvas` @ L31 |
| 371 | 10 | `experience.py::ExperienceMemory` @ L63 |
| 364 | 16 | `tools.py::AppResolver` @ L660 |
| 340 | 15 | `telemetry.py::TelemetryStore` @ L82 |
| 327 | 12 | `llama_server.py::LlamaServerManager` @ L399 |
| 311 | 11 | `ui/triggers.py::TriggersDialog` @ L37 |
| 289 | 8 | `llm_client.py::LLMClient` @ L60 |
| 267 | 12 | `ui/memory_viewer.py::MemoryDialog` @ L18 |
| 236 | 6 | `voice/wake.py::WakeDetector` @ L110 |
| 227 | 17 | `state.py::AgentState` @ L34 |
| 204 | 7 | `voice_runner.py::VoiceRunner` @ L218 |

`tools.py::ToolRegistry` con 3 157 LOC y 142 métodos es el caso más extremo del repo. Lo señalo aquí pero los hallazgos van todos a `08_findings.md`.

---

## 2. Entry points

### 2.1 Reales (módulos invocados como `python -m gemma4_agent.<x>` o equivalentes)

| Entry point | Comando | Función |
|---|---|---|
| `launcher.py` | `python -m gemma4_agent.launcher {status,start,...}` | CLI orquestador: gestiona `llama-server`, profiles, status del agente. Importa `tools.COMPOUND_TOOL_SCHEMAS`. **No es invocado por nadie del paquete; es entry-point puro.** |
| `chat.py` | `python -m gemma4_agent.chat` | REPL interactivo con paleta ANSI + spinner. Carga `Gemma4Agent` directo. |
| `server.py` | `uvicorn gemma4_agent.server:app` (o similar) | FastAPI: sirve `ui_field/dist/` en `/`, expone `GET /model`, `GET /metrics`, `GET/PUT /settings`, `POST /turn`, `WS /events`. **Es el backend de la UI React.** |
| `ui/__main__.py` → `ui/app.py::main` | `python -m gemma4_agent.ui` | GUI PyQt6 "MARK I" con splash + `MainWindow`. |
| `mcp_server.py` | `python -m gemma4_agent.mcp_server [--port N]` | Expone tools de Gemma4 como servidor MCP (stdio o HTTP). No corre el LLM Gemma. |
| `routine_runner.py` | `python -m gemma4_agent.routine_runner --id res_X` | Invocado por Windows Scheduled Tasks para correr una "routine". |
| `watcher_runner.py` | `python -m gemma4_agent.watcher_runner --id res_X` | Invocado por Scheduled Tasks para evaluar un "watcher". |
| `import_triggercmd.py` | `python -m gemma4_agent.import_triggercmd <commands.json>` | CLI one-shot que importa `TriggerCMD` `commands.json` como `on_phrase` routines. |
| `microagents.py` | `python -m gemma4_agent.microagents` (uso CLI/eval, tiene `__main__`) | Doble rol: módulo importable por `agent.py` y entrypoint con CLI propio. |
| `skills_registry.py` | `python -m gemma4_agent.skills_registry` (tiene `__main__`) | Doble rol idéntico al anterior. |
| `eval_smoke.py` | `python -m gemma4_agent.eval_smoke` | Smoke test rápido. No es un test de pytest. |

**11 entry points para una app sola.** `chat.py` y `ui/app.py` son superficies de usuario competidoras (CLI vs PyQt). `server.py` es una tercera superficie (HTTP+React). Esto cae en categoría "redundancia / superficies múltiples" en Fase 8.

### 2.2 Auxiliares (tienen `__main__` pero son test/probe/utility)

`scripts/probe_*.py` (9 archivos, todos imports `playwright`) — probes manuales de streaming (Netflix, Disney+, HBO).
`scripts/e2e_test_streaming.py` — driver de E2E manual.
`ui/test_bus_bridge_dryrun.py` — test pegado dentro de `ui/`, debería estar en `tests/` si existiera.
44 archivos `test_*.py` con `if __name__ == "__main__":` — patrón típico de scripts pytest invocables sueltos.

---

## 3. Dependencias

### 3.1 Declaración

**No hay archivo de declaración de dependencias en NINGÚN lugar del repo.** Lo verifiqué buscando `requirements*.txt`, `pyproject.toml`, `setup.py`, `setup.cfg`, `Pipfile`, `uv.lock`, `poetry.lock`, `environment.yml`, `conda.yml` en todo el árbol (excluyendo `node_modules` y `.venv`). Cero resultados.

**Implicación:** la lista de dependencias real está implícita en los `import` del código. No es reproducible para terceros (un `pip install -r ...` no existe). Esto es un hallazgo grave para `08_findings.md` (quick win: generar `requirements.txt` desde imports).

### 3.2 Paquetes externos usados (recuento por #archivos que los importan)

| Paquete | #archivos | Notas |
|---|---:|---|
| **PyQt6** | 17 | Todo `ui/` y su test |
| **playwright** | 9 | `ops_tools.py` + 8 probes en `scripts/` (puramente entry-point) |
| **numpy** | 7 | `voice/*` + `semantic_router.py` |
| **psutil** | 5 | `server.py`, `voice/stt.py`, `profile_watcher.py`, `ui/metrics.py`, `tools.py` |
| **sentence_transformers** | 3 | `semantic_router.py`, `knowledge.py`, `test_gx_features.py` |
| **comtypes** | 3 | Win32 audio (volume control) — `voice_runner.py`, `tools.py`, `verifiers.py` |
| **pycaw** | 3 | Win32 audio policy — mismos 3 archivos que comtypes |
| **sounddevice** | 3 | `voice/audio_io.py`, `voice/controller.py`, `voice/tts.py` |
| **uvicorn** | 2 | `server.py`, `launcher.py` |
| **huggingface_hub** | 2 | `voice/stt.py`, `nli_service.py` |
| **win32gui** | 2 | `tools.py`, `verifiers.py` |
| **fastapi** | 1 | `server.py` |
| **pydantic** | 1 | `server.py` |
| **pynvml** | 1 | `server.py` (GPU metrics) |
| **faster_whisper** | 1 | `voice/stt.py` |
| **silero_vad** | 1 | `voice/stt.py` |
| **scipy** | 1 | `voice/stt.py` |
| **torch** | 1 | `voice/stt.py` (transitivo de silero_vad o faster_whisper, pero también importado directo) |
| **vosk** | 1 | `voice/wake.py` |
| **piper** | 1 | `voice/tts.py` |
| **transformers** | 1 | `nli_service.py` |
| **sqlite_vec** | 1 | `experience.py` |
| **webview** | 1 | `launcher.py` (pywebview — desktop window para la UI React?) |
| **PIL** | 1 | `domain_tools.py` |
| **bs4** | 1 | `domain_tools.py` |
| **docx** | 1 | `domain_tools.py` (python-docx) |
| **fitz** | 1 | `domain_tools.py` (PyMuPDF) |
| **matplotlib** | 1 | `domain_tools.py` |
| **mysql** | 1 | `domain_tools.py` |
| **openpyxl** | 1 | `domain_tools.py` |
| **paho** | 1 | `domain_tools.py` (MQTT) |
| **pandas** | 1 | `domain_tools.py` |
| **pdf2image** | 1 | `domain_tools.py` |
| **pdfplumber** | 1 | `domain_tools.py` |
| **pptx** | 1 | `domain_tools.py` (python-pptx) |
| **psycopg** | 1 | `domain_tools.py` |
| **psycopg2** | 1 | `domain_tools.py` |
| **pymysql** | 1 | `domain_tools.py` |
| **pypdf** | 1 | `domain_tools.py` |
| **win32api / win32con / win32process** | 1 c/u | `tools.py` |
| **pythoncom** | 1 | `voice_runner.py` |

### 3.3 Hallazgos directos sobre dependencias

1. **`domain_tools.py` es el agujero negro de dependencias pesadas.** Importa MQTT (paho), múltiples drivers SQL (mysql, psycopg, psycopg2, pymysql), tres parsers PDF (fitz, pdf2image, pdfplumber, pypdf — sí, **cuatro**), `matplotlib`, `pandas`, `openpyxl`, `pptx`, `docx`, `PIL`. **314 funciones top-level en un solo archivo**. Es el "Tool Universal" — y carga toda esa pila incluso si el usuario no invoca ninguna de esas tools. Esto rompe el budget de latencia (memoria UP/AUTO).
2. **Drivers SQL duplicados:** `psycopg` y `psycopg2` (PostgreSQL); `mysql` y `pymysql` (MySQL). Hay dos clientes para la misma base.
3. **Parsers PDF redundantes:** `fitz` (PyMuPDF), `pdfplumber`, `pdf2image`, `pypdf`. Cuatro maneras de leer PDF.
4. **`webview` (pywebview)** sólo aparece en `launcher.py`. Si la UI React se sirve vía `server.py` + FastAPI, `webview` podría ser un wrapper "desktop window" — confirmar en Fase 1.
5. **No hay dependencias "declaradas pero no importadas"** porque no hay declaración. El cruce inverso (importadas pero no en el venv) lo veremos cuando exista `requirements.txt`.
6. **Stack ML de voz concentrado:** `faster_whisper`, `silero_vad`, `vosk`, `piper`, `torch`, `scipy`, `transformers`, `huggingface_hub`, `sentence_transformers` — todos en `voice/` salvo `transformers`/`huggingface_hub` (que están en `nli_service.py`) y `sentence_transformers` (en `semantic_router.py` y `knowledge.py`). Dos modelos NLI/embedding diferentes en juego.

---

## 4. Archivos de configuración y persistencia

### 4.1 Configuración declarativa (YAML/JSON/TOML)

**No hay archivos de configuración declarativa cargados por el agente.** La configuración 100 % vive en:

| Mecanismo | Detalle |
|---|---|
| **Env vars** | 20+ variables `GEMMA4_AGENT_*` (server URL, modelo, temperatura, top-p/k, min-p, context_size, max-tokens, max-turns, parse-tool-calls, tracing, safety, paths...) leídas en `config.AgentConfig.from_env` |
| **Perfil persistido** | Archivo de texto plano `~/.gemma4/active_profile.txt` (un nombre de perfil). Lo lee `profiles.get_active_profile()` y aplica un set de env vars vía `apply_profile_to_env()` |
| **Settings GUI** | `~/.gemma4/gui.json` — escrito/leído por `server.py` (`GET/PUT /settings`) y por `ui/app.py::apply_persisted_on_startup` |
| **Profiles definidos en código** | Los perfiles ("Performance", etc.) están definidos en `profiles.py` (532 LOC, 1 clase, 12 funciones top-level) — no en YAML |

### 4.2 Estado persistido por la app

| Path | Formato | Tamaño | Escrito por | Leído por |
|---|---|---:|---|---|
| `data/memory.json` | JSON dict (`items` con `auto:<key>`) | tiny | `memory.MemoryStore` | mismo |
| `data/state.json` | JSON dict (`resources`: routines, watchers, sessions) | mediano (visto: ~K entries) | `state.AgentState` | `tools.ToolRegistry`, `routine_runner`, `watcher_runner` |
| `data/traces.jsonl` | JSON-lines (1 evento/línea) | crece | `tracing.py` | grep manual |
| `data/experience.sqlite` | SQLite | crece | `experience.ExperienceMemory` (usa `sqlite_vec` para vector search) | mismo |
| `data/knowledge.sqlite` | SQLite | crece | `knowledge.py` (`sentence_transformers` embedding) | mismo |
| `data/study.sqlite` | SQLite | ? | (a investigar; no hay módulo `study.py`) | (a investigar) |
| `data/jobs/*.log` | texto | per-job | desconocido (probable scheduler) | manual |
| `data/backups/*.zip` | zip | per-backup | probable tool `backup` | manual |
| `data/generated/*` | pptx/xlsx/png | per-output | probable tools `make_pptx`/`make_xlsx`/`plot` | (no leído) |
| `data/data_analysis/*.png` | imagen | per-output | tool de plotting | (no leído) |
| `data/small_tool_smoke/*` | varios | tiny | smoke testing | (no leído) |
| `~/.gemma4/active_profile.txt` | texto plano | 1 línea | `profiles.set_active_profile` | `config._apply_persisted_profile_if_unset` |
| `~/.gemma4/gui.json` | JSON | ? | `server.py` `PUT /settings` | `ui/app.py` y `server.py` |

> **Hallazgo:** `study.sqlite` está en disco pero no hay módulo `study.py` ni `study_*.py` en el paquete. Posible artefacto huérfano de una iteración anterior. A confirmar en Fase 5 con `grep "study"` y `grep "study.sqlite"`.

### 4.3 Configuración por archivo del lado UI

| Path | Propósito |
|---|---|
| `ui_field/package.json` | React 19 + Vite 8 + TS 6 (versiones aspiracionales). 0 deps runtime salvo react+react-dom; 11 devDeps |
| `ui_field/pnpm-lock.yaml` | lockfile |
| `ui_field/tsconfig*.json` (3 archivos) | tsconfig roots para app/node/test |
| `ui_field/eslint.config.js` | lint |
| `ui_field/vite.config.ts` | bundler |
| `ui_field/README.md` | **boilerplate de Vite sin tocar**, no documenta nada específico del proyecto |

### 4.4 Outputs de probes JSON (en `docs/`)

`docs/all_platforms_flow.json`, `docs/disney_*_*.json`, `docs/netflix_*.json`, `docs/streaming_probe_*.json`, `docs/e2e_streaming_results.json` — 8 dumps de runs de probes manuales. **No los lee ningún módulo**; son outputs leídos por humanos. Candidatos a mover fuera del repo o agregar a `.gitignore`.

---

## 5. Estructura del paquete

```
gemma4_agent/
├── __init__.py                         (5 LOC: solo __version__ = "0.1.0")
├── agent.py                            (2 968 LOC — clase Gemma4Agent)
├── agent_runner.py                     (552 LOC — clase AgentRunner)
├── chat.py                             (489 LOC — entry CLI)
├── launcher.py                         (485 LOC — entry CLI orquestador)
├── server.py                           (1 519 LOC — FastAPI backend de ui_field)
├── mcp_server.py                       (332 LOC — entry MCP server)
├── voice_runner.py                     (425 LOC — entry voice loop)
├── routine_runner.py                   (54 LOC — entry Scheduled Tasks)
├── watcher_runner.py                   (43 LOC — entry Scheduled Tasks)
├── import_triggercmd.py                (131 LOC — entry CLI utility)
├── eval_smoke.py                       (97 LOC — smoke)
│
│   ── núcleo agente ──
├── config.py                           (141 LOC — AgentConfig + env)
├── state.py                            (261 LOC — AgentState + resources)
├── sessions.py                         (237 LOC — Session, SessionStore)
├── llama_server.py                     (726 LOC — LlamaServerManager)
├── llm_client.py                       (490 LOC — LLMClient)
├── model_info.py                       (153 LOC — ModelInfo + GGUF parse)
├── multimodal.py                       (134 LOC — handling de imágenes)
├── prewarm.py                          (140 LOC — warmup del modelo)
├── boot_progress.py                    (145 LOC — eventos de boot)
├── events_bus.py                       (99 LOC — BUS in-process)
├── log_recorder.py                     (220 LOC — capturador BUS→archivo)
├── telemetry.py                        (443 LOC — TelemetryStore — HUÉRFANO)
├── tracing.py                          (67 LOC — escribe traces.jsonl)
│
│   ── tools/registro ──
├── tools.py                            (4 825 LOC — ToolRegistry: 142 métodos)
├── domain_tools.py                     (10 539 LOC — 314 funciones; PDF/SQL/Excel/MQTT/…)
├── ops_tools.py                        (1 657 LOC — playwright/browser tools)
├── safety.py                           (67 LOC — chequeos pre-tool)
├── verify_core.py                      (191 LOC — verificadores comunes)
├── verifiers.py                        (690 LOC, 0 clases — HUÉRFANO; 19 verificadores)
│
│   ── memoria/conocimiento ──
├── memory.py                           (187 LOC — MemoryStore JSON)
├── experience.py                       (489 LOC — ExperienceMemory + sqlite_vec)
├── knowledge.py                        (253 LOC — knowledge.sqlite + embeddings)
│
│   ── router/planner/reasoning ──
├── semantic_router.py                  (279 LOC — embedding-based intent)
├── capability_classifier.py            (303 LOC — usa nli_service)
├── nli_service.py                      (246 LOC — modelo NLI HuggingFace)
├── grounding_gate.py                   (255 LOC — anti-alucinación; usa nli_service)
├── intent_validator.py                 (141 LOC)
├── planner.py                          (892 LOC)
├── reasoning.py                        (234 LOC, 0 clases)
├── explicit_plan.py                    (150 LOC, 0 clases)
├── mission_goal.py                     (659 LOC — adaptado de Carter v5)
├── mission_outcome.py                  (260 LOC — adaptado de Carter v5)
├── loop_detection.py                   (316 LOC)
├── modes.py                            (199 LOC)
├── personas.py                         (126 LOC)
├── microagents.py                      (351 LOC — entry doble)
├── skills_registry.py                  (456 LOC — entry doble; "extensiones de Carter")
├── subagent.py                         (99 LOC)
├── evaluator.py                        (96 LOC, 0 clases)
├── timeline.py                         (137 LOC)
├── project_context.py                  (91 LOC, 0 clases)
├── profiles.py                         (532 LOC — perfiles Performance/etc.)
├── profile_watcher.py                  (398 LOC)
├── _ml_import_lock.py                  (49 LOC — utility de import lock para ML)
├── _ps.py                              (82 LOC — utility process)
│
├── voice/        (6 archivos, 2 340 LOC)
│   ├── __init__.py    (8 LOC)
│   ├── audio_io.py    (245 LOC)
│   ├── controller.py  (576 LOC — VoiceController, orquesta wake→stt→…)
│   ├── stt.py         (863 LOC — StreamingSTT + Faster-Whisper + Silero-VAD)
│   ├── tts.py         (302 LOC — Piper)
│   └── wake.py        (346 LOC — WakeDetector + Vosk)
│
├── ui/           (18 archivos PyQt6, 5 587 LOC)
│   ├── __init__.py    (17 LOC)
│   ├── __main__.py    (10 LOC)
│   ├── app.py         (145 LOC — main + splash)
│   ├── main_window.py (1 616 LOC — MainWindow: 53 métodos)
│   ├── settings.py    (1 247 LOC — SettingsDialog: 22 métodos)
│   ├── hud.py         (482 LOC — HudCanvas)
│   ├── panels.py      (390 LOC — HUÉRFANO: nadie importa este módulo)
│   ├── triggers.py    (348 LOC — TriggersDialog)
│   ├── memory_viewer.py (285 LOC)
│   ├── theme.py       (227 LOC)
│   ├── agent_thread.py (220 LOC — QThread del agente)
│   ├── sessions_panel.py (212 LOC)
│   ├── tool_explorer.py (188 LOC)
│   ├── metrics.py     (179 LOC — HUÉRFANO)
│   ├── bus_bridge.py  (122 LOC — BUS → Qt signals)
│   ├── log_widget.py  (101 LOC)
│   ├── metric_bar.py  (75 LOC)
│   ├── async_tool.py  (70 LOC)
│   └── test_bus_bridge_dryrun.py (123 LOC — test mal ubicado)
│
├── scripts/      (9 archivos, todos huérfanos por definición — entry-points manuales)
│   └── probe_*.py, e2e_test_streaming.py
│
├── ui_field/     (React + Vite + TS; UI alternativa servida por server.py)
│   └── package.json, src/, dist/, node_modules/, ...
│
├── microagents/  (5 .md, NO contiene .py — son prompts/docs)
├── skills/       (10 carpetas con un SKILL.md cada una; spec de Anthropic Agent Skills)
├── data/         (estado persistente — ver §4.2)
├── captures/     (capturas en tiempo de ejecución; no analizado)
├── logs/         (logs en tiempo de ejecución; no analizado)
├── docs/         (markdown + JSONs de probes; no analizado)
└── design_handoff_carter_field/   (deuda Carter — ver §7)
```

---

## 6. Tabla detallada por archivo

Ver `_inventory_tables.md` (generado por `_inventory_md.py`) — incluida íntegra a continuación.

### 6.1 Archivos de producción (raíz del paquete)

| Path | LOC | #cls | #fn | Imports externos (sin stdlib) | Imports internos | mtime |
|---|---:|---:|---:|---|---|---|
| domain_tools.py | 10 539 | 1 | 314 | PIL, bs4, docx, fitz, matplotlib, mysql (+10) | _ps, state | 2026-05-16 |
| tools.py | 4 825 | 4 | 47 | comtypes, psutil, pycaw, win32api, win32con, win32gui (+1) | _ps, domain_tools, knowledge, memory, ops_tools, safety (+3) | 2026-05-16 |
| agent.py | 2 968 | 3 | 25 | — | (relativos), capability_classifier, config, domain_tools, evaluator, experience (+21) | 2026-05-16 |
| ops_tools.py | 1 657 | 1 | 43 | playwright | state | 2026-05-16 |
| server.py | 1 519 | 2 | 16 | fastapi, psutil, pydantic, pynvml, uvicorn | agent, agent_runner, config, domain_tools, events_bus, llama_server (+10) | 2026-05-15 |
| planner.py | 892 | 2 | 11 | — | semantic_router | 2026-05-16 |
| llama_server.py | 726 | 1 | 4 | — | config, events_bus, llm_client, model_info, multimodal, profiles | 2026-05-15 |
| verifiers.py | 690 | 0 | 19 | comtypes, pycaw, win32gui | tools, verify_core | 2026-05-15 |
| mission_goal.py | 659 | 4 | 6 | — | — | 2026-05-15 |
| agent_runner.py | 552 | 2 | 3 | — | (rel), agent, boot_progress, config, events_bus, llama_server (+4) | 2026-05-15 |
| profiles.py | 532 | 1 | 12 | — | state | 2026-05-15 |
| llm_client.py | 490 | 1 | 6 | — | config | 2026-05-15 |
| chat.py | 489 | 1 | 6 | — | agent, config, gemma4_agent, llama_server, personas, profiles (+2) | 2026-05-14 |
| experience.py | 489 | 1 | 5 | sqlite_vec | — | 2026-05-16 |
| launcher.py | 485 | 0 | 17 | uvicorn, webview | (rel), config, llama_server, llm_client, mcp_server, profiles (+2) | 2026-05-15 |
| skills_registry.py | 456 | 1 | 15 | — | — | 2026-05-15 |
| telemetry.py | 443 | 1 | 4 | — | config, events_bus | 2026-05-15 |
| voice_runner.py | 425 | 2 | 1 | comtypes, pycaw, pythoncom | agent_runner, boot_progress, events_bus, voice.controller | 2026-05-15 |
| profile_watcher.py | 398 | 3 | 5 | psutil | profiles | 2026-05-15 |
| microagents.py | 351 | 1 | 12 | — | — | 2026-05-15 |
| mcp_server.py | 332 | 0 | 9 | — | config, memory, state, tools | 2026-05-15 |
| loop_detection.py | 316 | 2 | 3 | — | — | 2026-05-15 |
| capability_classifier.py | 303 | 1 | 10 | — | nli_service | 2026-05-16 |
| semantic_router.py | 279 | 1 | 8 | numpy, sentence_transformers | — | 2026-05-15 |
| state.py | 261 | 1 | 2 | — | — | 2026-05-15 |
| mission_outcome.py | 260 | 1 | 4 | — | mission_goal, verify_core | 2026-05-15 |
| grounding_gate.py | 255 | 1 | 6 | — | nli_service | 2026-05-16 |
| knowledge.py | 253 | 1 | 6 | sentence_transformers | — | 2026-05-14 |
| nli_service.py | 246 | 1 | 1 | huggingface_hub, transformers | _ml_import_lock | 2026-05-16 |
| sessions.py | 237 | 3 | 6 | — | state | 2026-05-14 |
| reasoning.py | 234 | 0 | 5 | — | — | 2026-05-16 |
| log_recorder.py | 220 | 1 | 3 | — | events_bus | 2026-05-15 |
| modes.py | 199 | 1 | 4 | — | — | 2026-05-16 |
| verify_core.py | 191 | 1 | 7 | — | — | 2026-05-15 |
| memory.py | 187 | 1 | 2 | — | state | 2026-05-15 |
| model_info.py | 153 | 1 | 4 | — | — | 2026-05-15 |
| explicit_plan.py | 150 | 0 | 6 | — | reasoning | 2026-05-13 |
| boot_progress.py | 145 | 1 | 2 | — | — | 2026-05-15 |
| config.py | 141 | 1 | 2 | — | profiles | 2026-05-15 |
| intent_validator.py | 141 | 2 | 5 | — | — | 2026-05-16 |
| prewarm.py | 140 | 0 | 2 | — | events_bus | 2026-05-15 |
| timeline.py | 137 | 1 | 3 | — | — | 2026-05-14 |
| multimodal.py | 134 | 0 | 8 | — | events_bus | 2026-05-15 |
| import_triggercmd.py | 131 | 0 | 2 | — | config, domain_tools, state | 2026-05-14 |
| personas.py | 126 | 1 | 3 | — | — | 2026-05-14 |
| events_bus.py | 99 | 1 | 0 | — | — | 2026-05-15 |
| subagent.py | 99 | 0 | 1 | — | agent | 2026-05-13 |
| eval_smoke.py | 97 | 0 | 1 | — | config, memory, modes, planner, reasoning, state (+1) | 2026-05-12 |
| evaluator.py | 96 | 0 | 4 | — | — | 2026-05-12 |
| project_context.py | 91 | 0 | 4 | — | — | 2026-05-14 |
| _ps.py | 82 | 1 | 4 | — | — | 2026-05-15 |
| safety.py | 67 | 1 | 2 | — | — | 2026-05-12 |
| tracing.py | 67 | 1 | 2 | — | — | 2026-05-12 |
| routine_runner.py | 54 | 0 | 1 | — | config, memory, state, tools | 2026-05-15 |
| _ml_import_lock.py | 49 | 0 | 1 | — | — | 2026-05-16 |
| watcher_runner.py | 43 | 0 | 1 | — | config, memory, state, tools | 2026-05-13 |
| __init__.py | 5 | 0 | 0 | — | — | 2026-05-11 |

### 6.2 Subpaquete `ui/`

| Path | LOC | #cls | #fn | Imports externos | Imports internos | mtime |
|---|---:|---:|---:|---|---|---|
| ui/main_window.py | 1 616 | 3 | 1 | PyQt6 | (rel), agent, agent_thread, bus_bridge, config, events_bus (+15) | 2026-05-15 |
| ui/settings.py | 1 247 | 1 | 5 | PyQt6 | (rel), agent, profiles, state, theme, voice.audio_io (+1) | 2026-05-15 |
| ui/hud.py | 482 | 1 | 0 | PyQt6 | theme | 2026-05-14 |
| ui/panels.py | 390 | 0 | 4 | PyQt6 | (rel), metric_bar, theme | 2026-05-15 |
| ui/triggers.py | 348 | 1 | 0 | PyQt6 | async_tool, theme | 2026-05-14 |
| ui/memory_viewer.py | 285 | 1 | 0 | PyQt6 | async_tool, semantic_router, theme | 2026-05-14 |
| ui/theme.py | 227 | 1 | 10 | PyQt6 | — | 2026-05-15 |
| ui/agent_thread.py | 220 | 2 | 0 | PyQt6 | agent, config | 2026-05-15 |
| ui/sessions_panel.py | 212 | 1 | 0 | PyQt6 | theme | 2026-05-14 |
| ui/tool_explorer.py | 188 | 1 | 0 | PyQt6 | async_tool, theme | 2026-05-14 |
| ui/metrics.py | 179 | 1 | 3 | psutil | — | 2026-05-15 |
| ui/app.py | 145 | 1 | 2 | PyQt6 | main_window, settings, theme | 2026-05-15 |
| ui/bus_bridge.py | 122 | 1 | 0 | PyQt6 | events_bus | 2026-05-15 |
| ui/log_widget.py | 101 | 1 | 0 | PyQt6 | theme | 2026-05-14 |
| ui/metric_bar.py | 75 | 1 | 0 | PyQt6 | theme | 2026-05-14 |
| ui/async_tool.py | 70 | 2 | 1 | PyQt6 | — | 2026-05-14 |
| ui/__init__.py | 17 | 0 | 1 | — | app | 2026-05-14 |
| ui/__main__.py | 10 | 0 | 0 | — | app | 2026-05-14 |

### 6.3 Subpaquete `voice/`

| Path | LOC | #cls | #fn | Imports externos | Imports internos | mtime |
|---|---:|---:|---:|---|---|---|
| voice/stt.py | 863 | 3 | 8 | faster_whisper, huggingface_hub, numpy, psutil, scipy, silero_vad (+1) | _ml_import_lock | 2026-05-16 |
| voice/controller.py | 576 | 1 | 1 | numpy, sounddevice | audio_io, stt, tts, wake | 2026-05-15 |
| voice/wake.py | 346 | 1 | 2 | numpy, vosk | audio_io | 2026-05-15 |
| voice/tts.py | 302 | 1 | 4 | numpy, piper, sounddevice | — | 2026-05-15 |
| voice/audio_io.py | 245 | 1 | 1 | numpy, sounddevice | — | 2026-05-14 |
| voice/__init__.py | 8 | 0 | 0 | — | — | 2026-05-14 |

### 6.4 Tests (44 archivos)

| Path | LOC | #cls | #fn |
|---|---:|---:|---:|
| test_gx_features.py | 2 666 | 0 | 92 |
| test_whatsapp.py | 617 | 8 | 1 |
| test_verifiers.py | 535 | 0 | 46 |
| test_skills.py | 418 | 0 | 29 |
| test_mission_goal.py | 397 | 7 | 0 |
| test_microagents.py | 368 | 0 | 31 |
| test_loop_detection.py | 310 | 0 | 21 |
| test_log_audit_fixes.py | 300 | 4 | 0 |
| test_streaming_urls.py | 290 | 5 | 1 |
| test_dispatch_status.py | 263 | 4 | 0 |
| test_streaming_profile.py | 263 | 5 | 2 |
| test_experience_provenance.py | 262 | 4 | 1 |
| test_capability_classifier.py | 247 | 7 | 1 |
| test_grounding_gate.py | 207 | 5 | 0 |
| test_mcp_server.py | 177 | 5 | 0 |
| test_tool_call_rescue.py | 176 | 4 | 0 |
| test_promise_guard.py | 163 | 2 | 0 |
| test_daredevil_e2e.py | 162 | 1 | 0 |
| test_router_corpus.py | 152 | 3 | 1 |
| test_nli_service.py | 143 | 6 | 0 |
| test_router.py | 140 | 1 | 1 |
| test_state_safety.py | 138 | 3 | 1 |
| test_llm_client_retry.py | 129 | 2 | 0 |
| test_streaming_player_started.py | 123 | 1 | 1 |
| ui/test_bus_bridge_dryrun.py | 123 | 0 | 1 |
| test_tool_dispatch_contract.py | 119 | 2 | 1 |
| test_keys_translator.py | 112 | 2 | 0 |
| test_context_overflow.py | 108 | 3 | 0 |
| test_cdp_browser_graceful.py | 98 | 2 | 0 |
| test_browser_real_tabs_perf.py | 95 | 1 | 0 |
| test_inherit_tools_safety.py | 94 | 2 | 0 |
| test_ml_import_lock.py | 86 | 3 | 0 |
| test_tool_watchdog.py | 83 | 3 | 0 |
| test_browser_sessions_atexit.py | 80 | 1 | 0 |
| test_system_prompt_scope.py | 80 | 1 | 0 |
| test_planner_continuation.py | 78 | 1 | 0 |
| test_spotify_recheck.py | 75 | 1 | 0 |
| test_phrase_trigger_guards.py | 74 | 3 | 0 |
| test_profiles_restart.py | 74 | 1 | 0 |
| test_modes_info_routing.py | 72 | 1 | 0 |
| test_session_registry.py | 54 | 1 | 0 |
| test_thread_affine_tools.py | 53 | 2 | 0 |
| test_streaming_locale.py | 49 | 1 | 0 |
| test_model_info.py | 37 | 0 | 4 |

### 6.5 Scripts/probes (huérfanos por definición — son entry-points manuales)

| Path | LOC | #fn | Imports externos |
|---|---:|---:|---|
| scripts/probe_streaming_cdp.py | 228 | 2 | playwright |
| scripts/probe_streaming_urls.py | 184 | 3 | playwright |
| scripts/probe_all_platforms.py | 183 | 1 | playwright |
| scripts/probe_disney_search2.py | 162 | 1 | playwright |
| scripts/e2e_test_streaming.py | 145 | 4 | — |
| scripts/probe_netflix_full.py | 123 | 1 | playwright |
| scripts/probe_disney_search.py | 119 | 1 | playwright |
| scripts/probe_netflix_hbo.py | 118 | 2 | playwright |
| scripts/probe_disney_full.py | 110 | 1 | playwright |

---

## 7. Restos del proyecto Carter

### 7.1 Carpetas/archivos enteros que son Carter

| Path | Naturaleza | Acción sugerida |
|---|---|---|
| `gemma4_agent/design_handoff_carter_field/` (carpeta entera) | Prototipo de UI handoff (jsx). README explícito de Carter. | **Eliminar / mover fuera del paquete.** No es importado por nada. |

(Recordá que `chat_carter.py`, `harness_carter540/`, `PARA_AGENTE_CARTER_PROMPTS_SEPARADOS.md` en el raíz del repo también son Carter, pero están fuera de `gemma4_agent/` y por scope acordado no se documentan.)

### 7.2 Referencias residuales dentro de archivos `.py` de Gemma4

Las menciones a "carter" en código Python son **todas comentarios de procedencia** (de qué archivo de Carter se portó la idea). NO hay imports de Carter ni código vivo de Carter ejecutándose en Gemma4. Lista exhaustiva:

| Archivo | Línea | Tipo | Texto |
|---|---:|---|---|
| `mcp_server.py` | 28 | comentario docstring | "Carter v5 mcp_server.py — reference implementation porteada aca" |
| `mission_goal.py` | 13 | comentario docstring | "Adaptado de carter_v5/mission/goal.py a las compound tools de Gemma 4:" |
| `mission_goal.py` | 39 | comentario | "Outcome contracts (mirror Carter v5 types — local to avoid import cycles)" |
| `mission_goal.py` | 44 | docstring | "Estado final del turn — 9 valores explicitos (Carter v4 inheritance)." |
| `mission_outcome.py` | 15 | comentario docstring | "Carter v5 mission/verifier.py — 9 outcome states." |
| `mission_outcome.py` | 16 | comentario docstring | "ContextoCarter V3/V4: honestidad por construccion." |
| `llama_server.py` | 309 | comentario inline | "...leave unset (F16 default) until benchmarked on Carter 540." |
| `llama_server.py` | 322 | comentario | "Acceptance rate estimado 40-60% en Carter (sin medir). VRAM: solo viable" |
| `skills_registry.py` | 1 | docstring | "Skills registry — Anthropic Agent Skills spec con extensiones de Carter." |
| `skills_registry.py` | 48 | docstring | "Inspirado en carter_v5/skills/registry.py (extension priority + requires)" |
| `verify_core.py` | 3 | docstring | "Filosofia (heredada de ContextoCarter V3/V4): una tool retornando ok=True NO" |

**Veredicto:** la deuda Carter dentro del paquete es **estrictamente documental**. No hay riesgo runtime. La acción es cosmética (limpiar referencias a un proyecto deprecado para no confundir lectores futuros).

### 7.3 Referencias Carter en docs/markdown

| Archivo | Tipo |
|---|---|
| `gemma4_agent/microagents/glossary.md` | menciona "carter" |
| `gemma4_agent/ROADMAP.md` | menciona "carter" |
| `gemma4_agent/tests_540.md` | nombre del archivo (540 = ContextoCarter 5.4.0) |
| `gemma4_agent/skills/README.md` | menciona "carter" |
| `gemma4_agent/docs/Gemma 4 Agent — Informe de Optimización (auditoría externa).md` | menciona "carter" |
| `gemma4_agent/ui_field/src/components/SettingsPanel.tsx` | menciona "carter" |
| `gemma4_agent/ui_field/src/components/TopBar.tsx` | menciona "carter" |
| `gemma4_agent/ui_field/src/styles/prototype.css` | menciona "carter" |
| `gemma4_agent/ui_field/index.html` | menciona "carter" |
| `gemma4_agent/ui_field/dist/index.html` | menciona "carter" |
| `gemma4_agent/ui_field/dist/assets/index-*.js` | bundle compilado con strings "carter" |

**Atención: `ui_field/` tiene strings "carter" en su código fuente y en su bundle compilado.** No es solo doc — está en la UI visible. Hay que decidir si limpiar o re-brand.

---

## 8. Módulos huérfanos (no importados por ningún otro `.py`)

Excluyendo tests, `__main__/__init__`, scripts/probes (que son huérfanos por diseño) y los archivos que generé yo:

| LOC | Path | Notas |
|---:|---|---|
| 489 | `chat.py` | Entry-point CLI — OK que sea huérfano |
| 485 | `launcher.py` | Entry-point CLI — OK que sea huérfano |
| **690** | **`verifiers.py`** | 19 funciones de verificación, importa `tools`+`verify_core`. **Nadie lo importa.** Posiblemente cargado dinámicamente por nombre desde `ToolRegistry`, a confirmar. |
| **443** | **`telemetry.py`** | `TelemetryStore` (340 LOC, 15 métodos). **Nadie lo importa.** Sospechoso. |
| **390** | **`ui/panels.py`** | Define `panels` y widgets para PyQt. **Nadie lo importa.** Probable código muerto o pegado por error. |
| **179** | **`ui/metrics.py`** | Define MetricsWidget? **Nadie lo importa.** ¿Reemplazado por `metric_bar.py`? |
| 131 | `import_triggercmd.py` | Entry-point CLI — OK |
| 145 | `(ui)/test_bus_bridge_dryrun.py` | Test ubicado en `ui/` — OK como test |
| 97 | `eval_smoke.py` | Entry-point smoke — OK |
| 54 | `routine_runner.py` | Entry-point Scheduled Tasks — OK |
| 43 | `watcher_runner.py` | Entry-point Scheduled Tasks — OK |

**Top sospechosos a investigar antes de borrar (Fase 6 con grafo + grep dinámico):** `verifiers.py`, `telemetry.py`, `ui/panels.py`, `ui/metrics.py`.

Posibles falsos positivos:
- `verifiers.py` puede ser cargado por `verify_core.py` vía `importlib` o por `tools.py::ToolRegistry` por nombre de string. Hay que grepear `"verifiers"` como string.
- `telemetry.py` puede engancharse al `events_bus` por side-effect de import en algún entry-point. Hay que grepear `"telemetry"` como string y como import en los runners.

---

## 9. Top "god modules" por dependencia entrante

Conteo aproximado (subestima los relativos `from .X import`; el grafo limpio va en Fase 6).

| #importers | Módulo |
|---:|---|
| 27 | `gemma4_agent` (es decir, `import gemma4_agent` o `from gemma4_agent.X`) |
| 20 | `config` |
| 18 | `state` |
| 11 | `domain_tools` |
| 11 | `agent` |
| 11 | `theme` (ui) |
| 10 | `tools` |
| 10 | `events_bus` |
| 10 | `profiles` |
| 7 | `memory` |
| 6 | `llama_server` |
| 5 | `planner`, `reasoning`, `verify_core` |
| 4 | `llm_client`, `multimodal`, `semantic_router` |

`config`/`state`/`events_bus` son god modules **esperables** (config global, estado global, bus pub/sub). `domain_tools` y `tools` siendo importados por 10–11 módulos cada uno **no es esperable** — son catálogos de tools enormes y cualquier importador trae toda la pila.

---

## 10. Las dos UIs (resolución de la duda inicial)

Tras leer `server.py`, `ui/app.py` y `ui_field/package.json`/`README.md`:

| | `ui/` (PyQt6) | `ui_field/` (React + Vite + TS) |
|---|---|---|
| **Cómo arranca** | `python -m gemma4_agent.ui` → `app.py::main` | `server.py` (FastAPI) sirve `ui_field/dist/` en `/`, presumiblemente abierto por `launcher.py` (que importa `webview`) |
| **Stack** | PyQt6 con tema custom "MARK I" estilo HUD | React 19 + Vite 8 + TS 6, lockfile pnpm |
| **Tamaño Python** | 5 587 LOC en 18 archivos | 1 519 LOC (`server.py`) |
| **Estado** | 16 widgets activos, `main_window.py` 1 616 LOC; `panels.py` y `metrics.py` huérfanos | `README.md` es el **boilerplate de Vite intacto**; el proyecto no documenta para qué existe |
| **Acoplamiento al core** | Directo: `agent`, `agent_thread`, `bus_bridge`, `config`, `events_bus`, ... | Indirecto vía HTTP+WS (limpio); el backend `server.py` sí está fuertemente acoplado al core |
| **Strings "carter"** | No en código fuente | **Sí** — `SettingsPanel.tsx`, `TopBar.tsx`, `prototype.css`, `index.html` y `dist/` |
| **Tests** | `ui/test_bus_bridge_dryrun.py` (1 archivo) | ninguno |
| **Activa hoy** | Sí (tiene `__main__`, splash, etc.) | Sí (`server.py` lo sirve y depende `webview` de pywebview en `launcher.py`) |

**Veredicto inicial:** **ambas conviven y ambas están vivas**. La PyQt es la legacy "JARVIS desktop"; la React + FastAPI es la nueva "Field UI" — pero está a medio terminar (boilerplate README, strings "carter" sin migrar, sin tests). Para Fase 1 las trato como dos containers de UI separados pero marco a `ui_field/` como **incompleta / dual** y a `ui/` como **estable pero potencialmente legacy**. La decisión "cuál se queda" la toma el dueño humano, no este análisis.

---

## 11. Conclusiones rápidas de Fase 0 (para confirmar antes de Fase 1)

Estos son los hallazgos más fuertes que ya emergieron y que cambian cosas materiales:

1. **No existe declaración de dependencias.** El proyecto no se puede reproducir desde cero sin reconstruir manualmente el `requirements.txt`. Quick win obligatorio.
2. **3 god modules concentran 18 332 LOC** (33 % del total):
   - `domain_tools.py` 10 539 LOC, 314 funciones, +20 deps externas
   - `tools.py` 4 825 LOC, `ToolRegistry` con 142 métodos
   - `agent.py` 2 968 LOC, `Gemma4Agent` con 1 852 LOC y 21 métodos
3. **Hay 3 superficies de usuario** (CLI `chat.py`, PyQt `ui/`, React+FastAPI `ui_field/`+`server.py`) y 11 entry-points distintos. La pregunta "¿cuál es la app principal?" no tiene una respuesta inequívoca en el código.
4. **4 candidatos a código muerto plausible**: `verifiers.py` (690 LOC), `telemetry.py` (443 LOC), `ui/panels.py` (390 LOC), `ui/metrics.py` (179 LOC). Total ~1 700 LOC. Hay que descartar carga dinámica antes de marcar definitivamente.
5. **Dependencias redundantes en `domain_tools.py`:** dos drivers PostgreSQL (`psycopg`+`psycopg2`), dos drivers MySQL (`mysql`+`pymysql`), **cuatro** librerías PDF (`fitz`+`pdfplumber`+`pdf2image`+`pypdf`).
6. **`ui_field/` es un proyecto a medio terminar.** README boilerplate, strings "carter" hardcodeadas en TSX y en el bundle. No está claro si está pensado para reemplazar `ui/` o convivir.
7. **Carter dentro del paquete es solo documental** (11 menciones, todas en docstrings y comentarios de procedencia). Cero imports vivos. La deuda real (carpeta `design_handoff_carter_field/` y strings en `ui_field/`) es **cosmética**, no funcional.
8. **`study.sqlite` existe en disco pero no hay módulo `study.py`.** Posible artefacto huérfano de iteración previa. A verificar en Fase 5.
9. **Hipótesis de containers para Fase 1 — observaciones que la afectan:**
   - Mi hipótesis original mencionaba "wake-word/VAD" como container — **confirmado**: `voice/wake.py` (Vosk) + `voice/stt.py` usa Silero-VAD.
   - Mencionaba "intent router" — **confirmado**: `semantic_router.py` + `capability_classifier.py` + `intent_validator.py` + `grounding_gate.py` (4 piezas, posiblemente solapadas).
   - Mencionaba "tool dispatcher" — **confirmado y enorme**: es `tools.ToolRegistry` (3 157 LOC).
   - Mencionaba "session manager" — **confirmado**: `sessions.py`.
   - Mencionaba "memory/RAG" — **confirmado y triple**: `memory.py` (JSON), `experience.py` (SQLite+vec), `knowledge.py` (SQLite+ST). Tres memorias separadas.
   - Mencionaba "telemetría local" — `telemetry.py` existe pero es huérfano. Hay además `tracing.py`, `log_recorder.py`, `boot_progress.py`, `events_bus.py`. **Lo que existe es un bus de eventos del que múltiples sinks consumen, no una "telemetry" tradicional**.
   - Mencionaba "sandbox de ejecución" — **no encontré nada parecido**. `safety.py` son 67 LOC de chequeos pre-tool, no un sandbox.
   - **Falta en tu hipótesis original:** `mission_goal`/`mission_outcome` (sistema de verificación de cumplimiento del turn — 919 LOC heredados de Carter); `microagents` + `skills_registry` (dos sistemas de "habilidades" paralelos, 807 LOC combinados); `personas`; `loop_detection`; `profile_watcher`; un container "LLM lifecycle" propio (`llama_server` + `llm_client` + `model_info` + `prewarm` + `multimodal`); planner/reasoning como pieza aparte (`planner` 892 LOC, `reasoning` 234 LOC, `explicit_plan` 150 LOC).

---

## Anexo: artefactos generados

- `gemma4_agent/_inventory_scan.py` — scanner AST (de un solo uso, borrable).
- `gemma4_agent/_inventory.json` — dump JSON crudo del scan (5 448 líneas, borrable).
- `gemma4_agent/_inventory_report.py` — generador de los resúmenes que usé arriba (borrable).
- `gemma4_agent/_inventory_md.py` — generador de las tablas markdown de la §6 (borrable).
- `gemma4_agent/_inventory_tables.md` — tablas crudas embebidas en §6 (borrable).

Los 5 archivos `_inventory_*` son scratch y se eliminan cuando termine Fase 0. No tocan código existente.
