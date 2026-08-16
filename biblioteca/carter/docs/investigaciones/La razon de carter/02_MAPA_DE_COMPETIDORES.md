# 02 - Mapa de competidores

Fecha de generacion: 2026-05-08

## Competidores encontrados

Todos los proyectos fueron encontrados bajo `Extras/Competidores`:

- `Agent-S-main`
- `autogen-main`
- `AutoGPT-master`
- `goose-main`
- `langgraph-main`
- `Mark-XXXIX-main`
- `open-interpreter-main`
- `openclaw-main`
- `OpenHands-main`
- `OS-Copilot-main`

## Matriz comparativa

| Competidor | Categoria | Objetivo | Local/cloud | OS control | GUI control | Browser control | Terminal/filesystem | Memory | Skills/procedural memory | Safety/permissions | Verifiers | Latencia esperada | Multilingue | Facilidad de instalacion | Cercania al objetivo de Carter | Amenaza competitiva | Que Carter deberia copiar | Que Carter no deberia copiar | Veredicto |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Agent-S | GUI/OS agent de investigacion | Usar computadora como humano y rendir en OSWorld/WindowsAgentArena | Principalmente cloud/API + grounding model; puede usar modelos locales para grounding | Alto en entornos GUI | Muy alto, con screenshot, grounding y pyautogui | Indirecto via GUI | Codigo/terminal por code agent | Procedural memory | Si, prompts/procedural memory y best-of-N | Warning de ejecucion arbitraria en code env | Verificacion por observacion/reflection, no equivalente a verifiers deterministas Carter | Mas alta/costosa por VLM y rollouts | Depende del modelo | Compleja | Alta por GUI/OS, media por producto usuario | Alta | Procedural memory, grounding, evaluacion publica, comparative judge | Dependencia fuerte de cloud/benchmarks y ejecucion arbitraria como default producto | Carter pierde en GUI benchmark; Carter final puede ganar en local privado Windows tools verificadas. |
| AutoGen | Framework multi-agent | Crear apps multi-agent distribuidas/event-driven | Cloud/local segun modelo | No especifico | Via extensiones/MCP | Via MCP/Playwright | Via code execution extensions | Si en patrones/framework | Si, agentes y workflows | Depende de app; warnings MCP | No como producto OS | Variable | Depende modelos | Media para devs, baja para usuario normal | Baja directa | Abstracciones, evaluacion, separacion agentes/tools | Overhead multi-agent para asistente rapido | No es rival directo; es referencia arquitectonica. |
| AutoGPT | Plataforma de workflows | Construir, desplegar y gestionar agentes continuos | Self-host/Docker y cloud segun despliegue | Bajo para OS local | Bajo | Alto para automatizacion web/workflows | Variable | Si, por plataforma | Bloques/workflows | Plataforma, permisos por integracion | Monitoreo, no verifiers OS deterministas | No optimizada para Alexa local | Depende modelos | Media-alta con Docker | Media-baja | Builder, monitoreo, triggers, evaluacion agbenchmark | Scope de plataforma/marketplace | Carter no debe competir en plataforma de workflows continuos. |
| goose | Desktop/CLI/API agent | Agente nativo para codigo, workflows, investigacion, escritura, automatizacion | Local app con 15+ providers, incluye Ollama | Medio-alto por extensions/MCP | Variable por extensions | Si | Si | Sesiones/extension ecosystem | 70+ MCP extensions | Permisos dependen de extension/config | No verifiers OS Carter por defecto segun README | Variable; puede ser local | Depende modelo | Alta para tecnicos | Alta | Desktop+CLI, MCP, extension ecosystem, proveedores locales | Convertirse en solo wrapper MCP generalista | Amenaza alta: compite por agente local general. |
| LangGraph | Framework de orquestacion | Agentes stateful con durable execution, HITL, memory | Cloud/local segun app | No especifico | No especifico | Via integraciones | Via integraciones | Si | Deep Agents encima | HITL/checkpoints | No OS verifiers | Variable | Depende app | Media para devs | Baja directa | Durable execution, checkpoints, interrupciones humanas, memory formal | Complejidad framework para producto simple | Carter debe aprender de esto, no competir de frente. |
| Mark-XXXIX | Personal assistant / desktop agent | Asistente tipo Jarvis con voz, vision, apps, archivos, terminal | Local execution + Gemini cloud | Alto declarado | Alto declarado con screen/webcam | Si | Si | JSON memory | Planner y tool list | Protecciones puntuales; mas hardcoded | Menos evidencia de verifiers deterministas | Buena por Gemini live, depende red | Probable por Gemini | Media | Alta | Voice/live UX, multimodal, planner/executor/recovery | Cloud-dependence, if/elif dispatch, generated-code fallback riesgoso | Rival mas parecido por producto; Carter gana solo si privacidad/verificacion importan. |
| Open Interpreter | Code/computer agent | Permitir que LLM ejecute codigo local y controle computadora | Cloud por defecto, local posible con Ollama/LM Studio | Alto via codigo | Medio via computer/browser APIs | Si | Muy alto | Conversacion/profiles | Profiles y computer APIs | Solicita aprobacion antes de codigo | No enfoque principal en verifiers OS | Variable; local mode limitado | Depende modelo | Alta para tecnicos | Media-alta | UX de aprobacion, perfiles, codigo local poderoso | Ejecucion arbitraria como estrategia principal | Gana en codigo/shell; Carter puede ganar en tools curadas y verificacion. |
| openclaw | Personal assistant local-first multi-canal | Asistente en dispositivos/canales propios con skills y gateway | Local-first + providers; Windows via WSL2 recomendado | Medio | Variable | Si | Si, host tools/sandbox | Si | Skills, hooks, prompt files | Pairing, allowlist, sandbox en sesiones no-main | No equivalente Carter segun README | Variable | Probable | Alta complejidad | Media | Multi-canal, pairing, skill packaging, sandbox por sesion | Distraerse con demasiados canales antes de PC core | Amenaza en asistente personal, no en Windows-first PC control. |
| OpenHands | Coding agent | Desarrollo de software con agentes, SDK, CLI, GUI, cloud | Local/cloud | Bajo para OS usuario | No foco | Si para dev | Muy alto en dev/runtime | Si | Skills/dev workflows | Sandbox/runtime | Eval dev, no OS action verifiers | Variable | Depende modelo | Media para devs | Baja para Carter producto | Runtime, evaluaciones, integraciones dev | Competir en SWE-bench | Gana en coding; no invalida Carter. |
| OS-Copilot | OS agent / research framework | Agentes generalistas para OS: web, terminal, files, multimedia, apps | OpenAI API por defecto; local parcial en embeddings | Alto conceptual | Vision en desarrollo segun README | Si | Alto por codigo/shell | Tool repository | Self-improving tools con retrieval | Riesgo por ejecucion de codigo; disclaimer data loss | LLM judge/refinement, no verifiers deterministas | Variable/costosa | Depende modelo | Media para investigadores | Media-alta | Tool repository, self-refinement, task planning | Code-generation-first sin enough guardrails | Competidor academico; Carter debe diferenciarse por Windows local verificable. |

## Priorizacion

| Prioridad | Competidores | Motivo |
|---|---|---|
| Alta | Agent-S, goose, Mark-XXXIX | Son los mas cercanos a PC/desktop/OS assistant o agente local general. |
| Media | Open Interpreter, OS-Copilot, openclaw | Compiten por subdominios importantes: codigo local, OS research, personal assistant multi-canal. |
| Baja directa | OpenHands, AutoGPT, AutoGen, LangGraph | Son fuertes, pero en dominios distintos: coding, workflows, frameworks. |

## Evidencia por competidor

- Agent-S: `Extras/Competidores/Agent-S-main/README.md`, `gui_agents/s3/agents/agent_s.py`, `worker.py`, `grounding.py`, `code_agent.py`, `memory/procedural_memory.py`, `s3/bbon/comparative_judge.py`.
- AutoGen: `Extras/Competidores/autogen-main/README.md`.
- AutoGPT: `Extras/Competidores/AutoGPT-master/README.md`.
- goose: `Extras/Competidores/goose-main/README.md`.
- LangGraph: `Extras/Competidores/langgraph-main/README.md`.
- Mark-XXXIX: `Extras/Competidores/Mark-XXXIX-main/Mark-XXXIX-main/readme.md`, `main.py`, `agent/planner.py`, `agent/executor.py`, `agent/error_handler.py`, `actions/file_controller.py`, `memory/memory_manager.py`.
- Open Interpreter: `Extras/Competidores/open-interpreter-main/README.md`.
- openclaw: `Extras/Competidores/openclaw-main/README.md`.
- OpenHands: `Extras/Competidores/OpenHands-main/README.md`.
- OS-Copilot: `Extras/Competidores/OS-Copilot-main/README.md`, `oscopilot/agents/friday_agent.py`, `modules/planner/friday_planner.py`, `modules/executor/friday_executor.py`, `tool_repository/manager/tool_manager.py`, `environments/env.py`.

## Clasificación de afirmaciones

Evidencia: nombres, objetivos declarados y arquitectura primaria tomados de archivos locales.

Inferencia: amenaza competitiva segun cercania al nicho Carter.

Hipotesis: latencia esperada de competidores cuando no hay medicion local.

Opinion estrategica: que Carter copie mecanismos de evaluacion/verificacion pero no el scope de plataforma de otros.

Claim no defendible: que Carter sea superior globalmente a cualquier competidor listado.

## Limitaciones de este análisis

No se instalaron ni ejecutaron todos los competidores. Algunas filas resumen capacidades declaradas en README. La lectura de codigo fue mas profunda en los competidores OS/desktop mas cercanos.

## Qué falta verificar

Falta medir cada competidor en una misma maquina Windows con la misma suite de tareas: abrir apps, manipular archivos, usar terminal, controlar ventanas, portapapeles, navegacion, GUI compleja y misiones multi-step.

## Conclusión honesta

El mapa competitivo no destruye a Carter, pero lo obliga a ser especifico. Carter no gana por ser "otro agente"; gana solo si demuestra una combinacion concreta que los demas no priorizan: local, Windows-first, privado, rapido y verificable.
