# REBUILD_DECISIONS.md — Carter OS v2

Fecha: 2026-04-06
Contexto: Rebuild completo de Carter desde cero con filosofia zero predefined tools.

---

## A) CONSERVAR E INTEGRAR

Estas piezas aumentan autonomia, verificacion, robustez o seguridad real:

### Del proyecto nuevo (Carter v1)

| Pieza | Justificacion |
|---|---|
| **Sandbox aislado con kill tree** | Fundamento de la ejecucion segura. Timeout, env sanitizado, cwd aislado. Sin esto no hay autonomia segura. |
| **Parser JSON tolerante con _try_fix_json** | Los LLMs locales producen JSON roto. El parser de 3 capas (json.loads -> fix_json -> regex) es critico. |
| **Strip de tags <think> de qwen3** | Necesario para el modelo default. Sin esto, el parser falla. |
| **Anti-loop con deteccion de propositos repetidos** | Evita quemar 15 ciclos repitiendo la misma estrategia. Probado en produccion. |
| **Anti-mentira: rechazo de TASK_COMPLETE sin evidencia** | El modelo mentia declarando exito sin verificar. El sistema de task_successes por tarea lo resolvio. |
| **Anti-fabricacion: buscar antes de inventar** | El modelo inventaba App IDs. La regla de "busca primero con codigo" funciona. |
| **Deteccion de software instalado** | Evita que el modelo pierda ciclos buscando Steam, Git, etc. Va en runtime_context. |
| **System prompt con JSON estricto + reglas de conducta** | El prompt es el "cerebro" del agente. Todo lo aprendido se queda. |
| **Feedback de ejecucion con is_success** | El LLM necesita saber si el codigo funciono para decidir si verificar y cerrar. |

### Del proyecto viejo (Agente De Mastering)

| Pieza | Como se integra | Justificacion |
|---|---|---|
| **VRAM Manager (HOT/WARM/COLD)** | Modulo propio minimo | Protege FPS del usuario. Si juega, el modelo se descarga de VRAM. Unico y valioso. |
| **Memoria local SQLite** | memory.py nuevo, sin ChromaDB | Continuidad entre sesiones. Hash embedding ligero en vez de vectores pesados. |
| **Telemetria local ligera** | telemetry.py con metricas basicas | Deteccion de anomalias simple (proceso se come RAM). Sin pandas/sklearn. |
| **Sanitizacion de entorno** | Ya esta en sandbox, se refuerza | Blacklist de API keys, tokens, passwords del env heredado. |
| **Logs estructurados legibles** | Se rehace limpio | Que, penso, ejecuto, resultado, por que exito/fallo. Local, rotativo, util. |

---

## B) REINTERPRETAR

Ideas buenas que NO vuelven como antes, pero si como concepto ligero:

| Idea original | Era | Ahora sera | Por que cambia |
|---|---|---|---|
| **App Discovery (59 tools, registry, manifests)** | Sistema de tools con registry, resolvers, estado | `runtime_context.py` — snapshot del sistema real | Las tools eran rigidas y pesadas. Carter genera su propio codigo, no necesita wrappers. Solo necesita SABER que hay instalado. |
| **System Catalog** | Catalogo estatico de apps con rutas hardcodeadas | Deteccion dinamica en runtime_context | Hardcodear rutas no escala. Mejor detectar en runtime. |
| **Sandbox AppContainer** | Requeria admin, complejo, raramente usado | Sandbox por subproceso con env sanitizado + opcion futura AppContainer | AppContainer real requiere elevacion. El sandbox actual es suficiente. Se deja via de evolucion documentada. |
| **Visual Grounding (5168 LOC, observe-plan-act-verify)** | Modulo monolitico con OCR, UIA, pyautogui, LLM planner | Carter lo genera bajo demanda: el LLM escribe codigo con PIL/pyautogui/screenshot cuando lo necesita | El patron observe-plan-act-verify es bueno, pero Carter lo hace GENERANDO codigo, no con un modulo preconstruido. El prompt le ensena a tomar screenshots y verificar. |
| **Pre-LLM Command Router (2619 LOC regex)** | Bypass del LLM para comandos simples via regex | No se reintroduce — Carter es LLM-first | La latencia de qwen3:14b en Ollama es ~5-10s. Un router regex ahorra ~3s pero agrega 2619 LOC de mantenimiento. No vale la pena para la filosofia zero-tools. |
| **Execution Verifier (tool outcome verification)** | Modulo que verificaba si un tool realmente funciono | Integrado en el prompt + logica anti-mentira del core | Carter verifica generando codigo de verificacion, no con un modulo separado. |
| **Prompt Injection Mitigation (Spotlighting)** | Tokens unicos en system prompt contra inyeccion | Se evalua como mejora futura, no critico ahora | Carter no procesa input externo no confiable (no web scraping de prompts). Si se agrega, sera ligero. |

---

## C) ELIMINAR

Todo esto mete latencia, rigidez o complejidad sin beneficio para la nueva arquitectura:

| Pieza | Por que se elimina |
|---|---|
| **Voice Stack completo (STT, TTS, wake word, 9 modulos)** | Carter v2 es texto. Voice es un proyecto entero aparte. Agrega ~5000 LOC, moonshine, whisper, pyaudio, webrtcvad. No mejora la autonomia del nucleo. |
| **GUI (CustomTkinter, 8 modulos, tray, panels)** | Carter v2 es CLI/REPL. Si se necesita GUI sera una capa separada, no parte del core. |
| **Tool Registry grande (59 tools)** | Filosofia zero predefined tools. Carter genera codigo, no llama tools. |
| **LangGraph + langchain-core** | Dependencia pesada para un loop que es un while. Carter usa un OODA loop simple en Python puro. |
| **Command Router (2619 LOC regex)** | Carter no tiene commands predefinidos. Todo pasa por el LLM. |
| **Social Presence + Transparent Continuity** | Features de nicho que no mejoran la autonomia base. Si se quieren, Carter las puede generar bajo demanda. |
| **Launcher Workflows hardcodeados** | Carter descubre como interactuar con launchers generando codigo. No necesita workflows pre-escritos por app. |
| **Speaker Verifier** | Feature de voice stack. No aplica. |
| **Entity Catalog (553 entities hardcoded)** | Carter busca info con codigo cuando la necesita. |
| **Session Recorder (audio WAV)** | No hay audio en v2. |
| **Runtime Diagnostics (33 command matrix)** | Carter no tiene commands predefinidos. Los tests son diferentes. |
| **PyInstaller build/packaging** | Prematuro. Se empaqueta cuando el core sea solido. |
| **llama-cpp-python (inferencia directa)** | Carter usa Ollama (API HTTP). No maneja modelos GGUF directamente. Mas simple, mismo resultado. |
| **RapidOCR / OpenCV** | Si Carter necesita OCR, genera codigo que lo instala y usa. No es dependencia del core. |
| **openwakeword** | Voice stack eliminado. |
| **pycaw, pyaudio, screen-brightness-control** | Tools que Carter genera si las necesita. No son dependencias del core. |

---

## Principio rector

Cada linea de codigo en Carter v2 debe pasar este filtro:

> "Hace a Carter mas autonomo, mas verificable, mas local, mas limpio o mas robusto SIN hacerlo mas lento ni mas torpe?"

Si no, no entra.
