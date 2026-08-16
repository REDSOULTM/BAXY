# Prompt Para Claude Code — Continuación de Carter_v2

Quiero que continúes el trabajo de **Carter_v2** a partir del estado actual del repo.

## Contexto principal

Este proyecto viene de un agente anterior llamado **Carter_v1**.
Ese proyecto acumuló mucho aprendizaje, pero también mucha deuda arquitectónica.

La decisión ya fue tomada:

- `Carter_v1/` queda como legado congelado y consultable
- `Carter_v2/` es ahora el proyecto principal
- Carter_v2 debe arrancar **casi desde cero**, con **código mínimo**, pero usando lo mejor aprendido en v1

## Prioridad arquitectónica

Toma como guía principal el documento:

- [Plan de trabajo.md](/c:/Users/usuario/Desktop/ETC/Programacion/Carter%20OS%20AI/Carter_v2/documentacion/Plan%20de%20trabajo.md)

Y como insumo principal de investigación:

- [Claude-Building a real Jarvis the definitive desktop agent architecture guide.md](/c:/Users/usuario/Desktop/ETC/Programacion/Carter%20OS%20AI/Carter_v2/documentacion/investigaciones/comparadas/Claude-Building%20a%20real%20Jarvis%20the%20definitive%20desktop%20agent%20architecture%20guide.md)

También puedes usar como contraste:

- [gpt-deep-research-report.md](/c:/Users/usuario/Desktop/ETC/Programacion/Carter%20OS%20AI/Carter_v2/documentacion/investigaciones/comparadas/gpt-deep-research-report.md)
- [Gemini-Transformar CARTER OS en Jarvis Investigación Tecnica.,md](/c:/Users/usuario/Desktop/ETC/Programacion/Carter%20OS%20AI/Carter_v2/documentacion/investigaciones/comparadas/Gemini-Transformar%20CARTER%20OS%20en%20Jarvis%20Investigaci%C3%B3n%20Tecnica.,md)

Pero la investigación de Claude tiene prioridad.

## Tesis obligatoria

No quiero más un sistema donde el LLM improvise scripts, protocolos y cierres para tareas simples.

Quiero un Carter_v2 donde:

- el LLM entiende intención y planifica
- el router decide qué capability usar
- la ejecución es determinista
- la verificación es factual y barata
- `UIA-first` es la estrategia GUI principal
- la visión solo entra bajo demanda

## Reglas de diseño obligatorias

1. **No arrastres el loop legacy de Carter_v1.**

2. **No copies grandes bloques de `carter_core.py` a Carter_v2.**
   Puedes inspirarte, pero no clonar deuda.

3. **No uses generación de Python o PowerShell como camino principal.**
   Si en el futuro existe una capability de sandbox, será excepcional y muy restringida.

4. **Diseña Carter_v2 como un sistema modular.**

5. **Toda interacción LLM -> ejecución debe ir por salidas estructuradas.**

6. **Toda capability debe devolver evidencia verificable.**

7. **La primera meta es matar los fails absurdos de tareas simples.**

## Qué piezas de Carter_v1 sí son valiosas

No quiero que ignores el trabajo previo.

Debes considerar como referencias para portado selectivo:

- ideas de `task_state`
- `verified_facts`
- `verification_targets`
- `completion_contract`
- `__CARTER_EVENT__`
- `accessibility_probe.py`
- `llm_backends.py`

Pero quiero que las portes con criterio, no que las copies enteras.

## Qué construir primero

La primera fase de Carter_v2 debe dejar un núcleo mínimo pero correcto:

### Módulos mínimos

- `orchestrator`
- `planner`
- `capabilities.base`
- `capabilities.registry`
- `capabilities.system`
- `capabilities.process`
- `capabilities.filesystem`
- `capabilities.web`
- `verification.facts`
- `verification.contracts`
- `adapters.llm`
- `adapters.uia`
- `event_bus`
- `types`

### Capacidades mínimas que deben existir primero

- `system.get_gpu_info`
- `system.get_audio_device`
- `process.start_app`
- `process.stop_app`
- `window.wait_for`
- `filesystem.create_folder`
- `filesystem.write_text`
- `filesystem.exists`
- `web.open_url`

## Qué NO construir todavía

No quiero que empieces por:

- voz
- memoria vectorial avanzada
- GUI visual compleja
- benchmarking masivo de modelos
- launchers complejos
- Office GUI profunda

Primero núcleo correcto.

## Cómo quiero que trabajes

1. Revisa `Carter_v2/` y el `Plan de trabajo.md`
2. Mantén la arquitectura limpia
3. Haz cambios pequeños pero estructuralmente correctos
4. Añade tests desde el principio
5. Si usas algo de v1, di exactamente qué estás portando y por qué
6. No metas hacks por app
7. No metas regexs para arreglar síntomas
8. No metas “prompt hacks” como sustituto de arquitectura

## Criterio de éxito de la primera etapa

La primera etapa de Carter_v2 está bien si puede resolver con capacidades deterministas:

- `Dime qué GPU tengo`
- `Dime qué dispositivo de audio está activo`
- `Abre Steam`
- `Cierra Steam`
- `Crea un archivo hola.txt`
- `Abre la página oficial de OpenAI`

Sin:

- parse errors
- JSON roto
- scripts generados como camino principal
- bucles tontos

## Tu tarea ahora

Continúa Carter_v2 desde este punto con la fase inicial del plan.

No re-arquitectures Carter_v1.
No sigas parchando el pasado.

Construye el nuevo núcleo correcto.
