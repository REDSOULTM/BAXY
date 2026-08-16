# COMPETITOR_LANDSCAPE_AUDIT.md
# Auditoría de Competidores Públicos / Referenciales
# Generado por: Claude Code (claude-sonnet-4-6) — 2026-05-06
#
# AVISO: Esta sección se basa en conocimiento público documentado hasta agosto 2025.
# No hay código local de estos competidores. Datos marcados como [inferencia] donde
# no hay certeza directa. No hay internet disponible en esta sesión de auditoría.

---

## Tabla resumen

| Competidor | Tipo | Fortalezas | Debilidades | Local-first | GUI | Memoria | Safety | Testing | Qué puede aprender Carter |
|---|---|---|---|---|---|---|---|---|---|
| **Open Interpreter** | Python, ejecuta código LLM-generado en shell | Muy simple, potente para CLI, multi-OS | Sin verifier, sin policy, puede ejecutar código destructivo, no apto para PC general | SÍ (Ollama) | NO | NO (solo contexto) | DÉBIL | Limitado | Execution sandbox, progress streaming |
| **OpenHands** | Python+TypeScript, browser+terminal+filesystem | Agente para desarrollo de software, browser Playwright, Docker sandbox | No está diseñado para PC personal/Jarvis, orientado a coding tasks | SÍ (con modelo local) | Browser solamente | Conversation history | Docker sandbox | Moderado | Docker sandbox pattern, browser integration |
| **AutoGPT** | Python, multi-agent, tasks persistentes | Pionero del loop autónomo, plugin system | Loop infinito sin step budget, propenso a fake success, lento, costoso en tokens | SÍ (Ollama parcial) | NO | SÍ (básica) | MUY DÉBIL | Básico | Task persistence concept |
| **Microsoft AutoGen** | Python, multi-agent framework | Framework maduro para orquestación multi-agent, human-in-the-loop | No es asistente de PC, es framework de orquestación. No integra con Windows APIs. | SÍ | NO | Básica | Moderado | Bueno | Human-in-the-loop para HIGH risk, GroupChat concept |
| **LangGraph agents** | Python, stateful graph agents | State machine explícita, rollback de estado, checkpointing | Complejidad alta, requiere diseño de grafo previo, no out-of-the-box | SÍ | NO | Via tools | Moderado | Bueno | State machine explícita, checkpointing |
| **Goose (Block)** | Python+Rust, CLI agent | Provider-agnostic, toolkit pattern, extensible | Sin GUI control, sin UX de asistente personal | SÍ | NO | Básica | Moderado | Básico | Toolkit extension pattern |
| **OS-Copilot** | Python, agente para OS tasks | Diseñado para tareas de OS, GUI automation básica | Menos mantenido, sin policy, sin verifier | SÍ | SÍ (básica) | Básica | MUY DÉBIL | Mínimo | OS task patterns, GUI automation básica |
| **Agent-S** | Python, GUI agent | Especializado en GUI automation (UIA + screenshot), benchmark OSWORLD | Solo GUI, sin conversación natural, sin memoria, sin policy | SÍ (requiere VLM) | SÍ (especialidad) | NO | DÉBIL | Bueno (benchmarks) | GUI observation loop, UIA integration |
| **Claude Computer Use** | API Anthropic + pantallas | Muy capaz en GUI, entendimiento visual rico, verbaliza bien | 100% cloud (Anthropic API), lento, caro por token, sin privacidad | NO | SÍ (excelente) | NO (solo contexto) | Moderado | Descripción de pantalla, GUI understanding pattern |
| **Windows Copilot** | Microsoft, cerrado | Integración profunda con Windows | 100% cloud (Microsoft), sin privacidad, sin control de usuario | NO | SÍ | SÍ (MSA) | Corporativo | MUY LIMITADO | Integración shell/PowerShell, Windows APIs |

---

## Open Interpreter

### Qué es
Agente Python que toma input del usuario, llama al LLM para generar código (Python/Bash/JS), y lo ejecuta localmente en el shell del usuario.

### Fortalezas
- Extremamente simple de usar
- Soporta Ollama local
- Multi-OS
- Gran comunidad
- El LLM genera código flexible, no herramientas estáticas

### Debilidades
- Sin verifier — asume que el código corrió bien si no hubo excepción
- Sin policy pre-LLM — cualquier código destructivo puede ejecutarse
- Sin step budget fijo — puede generar loops
- Sin session state estructurado
- Sin memory persistente real
- Sin GUI automation
- Sin hardcode guard (no aplica — el código es generado dinámicamente)
- [inferencia] Fake success posible si el LLM genera `print("done")` sin efecto real

### Local-first
SÍ, con Ollama o cualquier OpenAI-compat endpoint.

### Qué puede aprender Carter
- **Code execution sandbox**: permitir que el LLM genere y ejecute código en un sandbox controlado (como complement a las tools declarativas actuales)
- **Progress streaming**: Open Interpreter hace streaming de la ejecución del código en tiempo real
- **Simplicity**: la API de usuario es mucho más simple que Carter

---

## OpenHands (antes OpenDevin)

### Qué es
Agente para desarrollo de software. Puede usar browser, terminal, filesystem, y sandboxes Docker. Orientado a tasks de coding como "implementa esta feature", "arregla este bug".

### Fortalezas
- Docker sandbox por defecto (acciones peligrosas no afectan el host)
- Browser Playwright real
- Terminal con PTY
- State machine de tarea visible
- Soporte multi-modelo
- [inferencia] Buena cobertura de tests

### Debilidades
- No está diseñado para PC personal tipo Jarvis
- Sin control de apps de escritorio (Steam, Spotify, etc.)
- Sin voz/cámara
- Sin memoria persistente de usuario
- El sandbox Docker añade overhead para un asistente personal

### Local-first
SÍ, con modelos locales.

### Qué puede aprender Carter
- **Docker sandbox para terminal**: para comandos HIGH/CRITICAL risk, ejecutar en sandbox primero
- **Visible task state**: el agente expone su task state de forma estructurada
- **PTY terminal support**: consola completa, no solo `subprocess.run`

---

## AutoGPT

### Qué es
El OG de los agentes autónomos (2023). Loop: Think → Plan → Execute → Memory → Loop. Plugin system para tools.

### Fortalezas
- Pionero del concepto
- Task persistence (guarda tareas en disco)
- Plugin system
- Multi-OS

### Debilidades
- Loop sin step budget fijo → puede ejecutar infinitamente
- Propenso a fake success y hallucination
- Costos altos en tokens (muchas llamadas LLM)
- UX pobre (CLI con muchos prompts de confirmación)
- [inferencia] Sin verifier real por acción
- Complejidad alta para tareas simples

### Qué puede aprender Carter
- **Task persistence**: guardar el estado de una tarea larga para reanudarla
- El resto no vale la pena — AutoGPT tiene más anti-patrones que Carter

---

## Microsoft AutoGen

### Qué es
Framework de orquestación multi-agent. Permite crear grupos de agentes que se comunican entre sí para resolver tareas.

### Fortalezas
- Human-in-the-loop estructurado (`HumanProxyAgent`)
- GroupChat para múltiples agentes con distintos roles
- Conversable agents (cada agente puede conversar con otros)
- Buen soporte para code execution controlado
- Framework maduro, bien documentado, bien testeado
- [inferencia] Integra con Azure OpenAI

### Debilidades
- No es un asistente de PC — es un framework de orquestación
- Sin GUI automation nativa
- Sin voz/cámara
- Requiere diseño explícito de "quién habla con quién"
- Overhead de multi-agent para tareas simples de PC

### Qué puede aprender Carter
- **Human-in-the-loop explícito**: el pattern de `HumanProxyAgent` para pedir confirmación es excelente
- **Roles de agente especializados**: para misiones complejas, Carter podría spawn un "planner agent" y un "executor agent" separados

---

## LangGraph Agents

### Qué es
Framework Python de LangChain para agentes con state machine explícita (grafo de nodos). Permite checkpointing y rollback.

### Fortalezas
- State machine explícita (nodos, edges, condiciones)
- Checkpointing: puede guardar estado a mid-task y reanudar
- Rollback a estado anterior si el agente falla
- Human-in-the-loop via interrupts en el grafo
- Compiling del grafo previo a ejecución (validación)

### Debilidades
- Requiere diseñar el grafo explícitamente (no es out-of-the-box)
- Complejidad arquitectónica alta
- Sin GUI automation
- Sin PC-specific tools

### Qué puede aprender Carter
- **State machine explícita**: el agent.py actual es imperativo. Un grafo LangGraph-style haría la lógica más testeable.
- **Checkpointing de task**: para misiones largas, poder guardar el estado intermedio
- **Interrupt points**: para pedir confirmación al usuario en puntos críticos del flujo

---

## Goose (Block)

### Qué es
CLI agent Python/Rust de Block (Jack Dorsey's company). Provider-agnostic, toolkit-based.

### Fortalezas
- Provider-agnostic (cualquier OpenAI-compat endpoint)
- Toolkit pattern: cada "toolkit" es un conjunto de tools relacionadas (browser, developer, computer use)
- Extensible vía plugins Python
- [inferencia] Soporta modelos locales

### Debilidades
- Sin UX de asistente personal (CLI solamente)
- Sin GUI automation nativa de Windows
- Sin memoria persistente robusta
- [inferencia] Sin verifier por acción

### Qué puede aprender Carter
- **Toolkit pattern**: agrupar tools relacionadas (system_toolkit, browser_toolkit, filesystem_toolkit) con una interfaz común de configuración

---

## OS-Copilot

### Qué es
Agente Python académico para tareas de OS (file management, web browsing, GUI basics).

### Fortalezas
- Diseñado explícitamente para OS tasks
- Tiene GUI automation básica
- Memory de usuario

### Debilidades
- Menos mantenido (paper de 2024)
- Sin policy engine
- Sin verifier
- GUI automation frágil (coordinate-based)
- [inferencia] Sin tests robustos

### Qué puede aprender Carter
- Referencia de categorías de OS tasks (sus benchmarks son relevantes)
- No hay mucho código que adaptar

---

## Agent-S

### Qué es
Agente académico especializado en GUI automation. Benchmark OSWORLD. Usa VLM (Vision Language Model) para entender pantallas.

### Fortalezas
- Especializado en GUI automation
- UIA integration real
- VLM para entender interfaces
- Benchmark OSWORLD (gold standard de GUI agents)
- Observation loop explícito: observe → plan → act → verify

### Debilidades
- Requiere VLM pesado (GPT-4V, Claude, etc.)
- No es un asistente conversacional
- Sin memoria persistente
- Sin voz
- Sin policy pre-LLM
- 100% orientado a clicks/teclado, no a acción general

### Qué puede aprender Carter
- **Observation-action-verification loop** explícito: observe primero, actúa segundo, verifica tercero
- **UIA integration**: Carter ya tiene esto parcialmente, pero Agent-S lo hace más sistemático
- **OSWORLD benchmark**: métricas relevantes para evaluar GUI automation de Carter

---

## Claude Computer Use (Anthropic pattern)

### Qué es
API de Anthropic donde Claude puede controlar un computador mediante screenshots + acciones (click, type, scroll). Disponible en Claude 3.5 Sonnet y superiores.

### Fortalezas
- LLM entiende muy bien las interfaces
- Observación visual rica (VLM nativo)
- Sin hardcodes por app — trabaja con cualquier interfaz visualmente
- Verbalización honesta de lo que ve vs. lo que hizo

### Debilidades
- 100% cloud (Anthropic API)
- Caro por token (cada screenshot es muchos tokens)
- Lento (tarda varios segundos por acción)
- Sin privacidad (la pantalla se envía a Anthropic)
- Sin memoria persistente de usuario
- Sin voz

### Qué puede aprender Carter
- **Universal GUI via vision**: el concepto de "if UIA fails, use screenshot + VLM to understand" es el correcto
- Carter ya tiene este ladder. La diferencia es que Claude CU tiene mejor VLM.
- La idea de **describe antes de actuar** (screenshot → comprende → actúa → screenshot → verifica) es excelente.

---

## Windows Copilot (Microsoft)

### Qué es
Asistente de Windows 11 integrado por Microsoft. Puede controlar apps, ejecutar acciones del sistema, buscar en la web.

### Fortalezas
- Profundamente integrado con Windows APIs
- Shell integration (PowerShell, Windows APIs nativas)
- MSA memory (preferencias sincronizadas)

### Debilidades
- 100% cloud (Microsoft Azure)
- Sin privacidad (todo se envía a Microsoft)
- Sin control del usuario sobre el modelo
- Sin extensibilidad real para el usuario
- Sin voz/cámara propia (usa otras apps de Microsoft)
- [inferencia] Sin verifier por acción

### Qué puede aprender Carter
- **Shell integration profunda**: usar `Get-StartApps`, PowerShell, WMI más agresivamente
- **Windows APIs nativas**: Carter ya hace esto bien (psutil, win32api, etc.)
- No hay mucho más que copiar — la filosofía es opuesta (cloud vs local)

---

## Nota de honestidad

Los análisis de Open Interpreter, OpenHands, AutoGPT, AutoGen, LangGraph, Goose, OS-Copilot, Agent-S, Claude Computer Use y Windows Copilot se basan en conocimiento público hasta agosto 2025. **No hay código local disponible para estos competidores en esta sesión.** Cualquier dato marcado [inferencia] no fue verificado directamente desde el código fuente.
