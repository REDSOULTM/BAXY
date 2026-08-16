# 00 - Resumen ejecutivo

Fecha de generacion: 2026-05-08

Frase guia: no estoy auditando solo el Carter que existe hoy; estoy auditando si la vision final de Carter, llevada a producto real, tiene una razon legitima para existir frente a sus competidores.

## Veredicto brutalmente honesto

| Pregunta | Respuesta |
|---|---|
| Carter actual tiene sentido? | Si, parcialmente. Tiene una base tecnica seria, pero todavia no justifica claims amplios de asistente universal. |
| Carter final razonable tiene sentido? | Si, si demuestra robustez GUI, multi-step, verificacion externa y latencia local sostenida. |
| Carter tiene sentido como producto? | Si, en un nicho estrecho: asistente local, privado, Windows-first y verificable para PC real. |
| Carter tiene sentido como tesis? | Si, si se formula como sistema local verificable para control de PC, no como AGI ni "Jarvis universal". |
| Carter tiene sentido frente a competidores? | Si, no porque gane en todo, sino porque ocupa un eje que muchos competidores no priorizan: PC Windows local, baja latencia, privacidad y verificacion honesta. |

Veredicto final: Carter actual es defendible como prototipo avanzado; Carter final razonable si tendria una razon legitima para existir, pero la tesis se cae si no cierra GUI universal, misiones multi-paso, verificacion real y evaluacion externa.

## Tesis de Carter

Tesis en una frase: Carter es un asistente local Windows-first que intenta operar una PC real con tools verificables y memoria local sin fingir exito cuando no puede comprobar una accion.

Version academica: Carter explora si un agente LLM local, acoplado a un registro tipado de herramientas de sistema operativo, verificadores post-accion, memoria local y politicas de seguridad explicitas, puede ejecutar tareas cotidianas en Windows con menor dependencia de cloud y menor tasa de exito fingido que agentes generalistas basados en navegador, codigo o computer-use visual.

Version pitch honesta: un asistente privado para tu PC Windows que abre apps, maneja archivos, terminal, portapapeles, ventanas y acciones del sistema, y que debe decirte cuando no pudo verificar lo que hizo.

## Evidencia usada

| Tipo | Evidencia local |
|---|---|
| Vision declarada | `contextocarter.md` define Carter como asistente local, privado, rapido, honesto, sin fake success, con herramientas reales y verificadores. |
| Codigo Carter | `Carter_v4/src/carter_v4/agent.py`, `tools/__init__.py`, `verify.py`, `verifier_orchestrator.py`, `safety.py`, `memory.py`, `skill_store.py`. |
| Tools actuales | Carga local verificada: 55 tools registradas desde `carter_v4.tools`. |
| Tests | Ejecucion local: `python -m pytest -q` en `Carter_v4` dio 131 passed. |
| Evaluacion | `Carter_v4/CARTER_540_REAL_PROGRESS_REPORT.md` reporta 417/540 PASS REAL manual y 489/540 automatico, con falsos positivos importantes. |
| Competidores | Proyectos en `Extras/Competidores`: Agent-S, AutoGen, AutoGPT, goose, LangGraph, Mark-XXXIX, Open Interpreter, openclaw, OpenHands, OS-Copilot. |

## Nota sobre evidencia conflictiva

El prompt entregado por el usuario menciona 519/540 PASS REAL, 472/540 automatico, 95 tests verdes y 54 tools. El repositorio local revisado en esta auditoria muestra otro estado: 417/540 manual en `Carter_v4/CARTER_540_REAL_PROGRESS_REPORT.md`, 131 tests pasando y 55 tools cargadas. Para Carter actual, esta auditoria usa la evidencia local verificable como mas fuerte. Los numeros del prompt se tratan como contexto externo no verificado.

## Top 5 razones por las que Carter final si tiene sentido

1. Nicho claro: Windows local privado para usuario real, no solo benchmark, navegador o coding.
2. Tools verificables: el diseno no depende solo de "el LLM dijo que lo hizo"; hay verificadores y estado global de resultado.
3. Latencia plausible: el perfil local pequeno permite respuestas cercanas a asistente de voz en tareas simples, si no se abusa de vision/modelos grandes.
4. Superficie PC real: apps, procesos, ventanas, filesystem, terminal, clipboard, registry read-only, Steam y media estan dentro de la vision y parte ya existe.
5. Honestidad como producto: la tesis de "no fingir exito" es mas defendible que prometer automatizacion universal perfecta.

## Top 5 razones por las que Carter podria no tener sentido

1. Si GUI universal sigue fallando, Carter pierde justo donde necesita parecer util para usuario normal.
2. Si el modelo local pequeno se rinde ante instrucciones ambiguas o multi-step, la UX se vuelve frustrante.
3. Si los benchmarks son propios y conflictivos, un evaluador externo no confiara en la tesis.
4. Si competidores con VLM/cloud ofrecen GUI mucho mas robusta, la ventaja local podria no compensar.
5. Si Carter se presenta como "Jarvis" general, parecera promesa exagerada y no producto defendible.

## Top 5 riesgos que pueden matar la tesis

1. GUI moderna: CEF/Chromium, Discord, Spotify, Steam y apps custom pueden romper UIA/OCR.
2. Multi-step real: planificar, ejecutar, verificar y replantear sin perder contexto sigue siendo debil.
3. Evaluacion sesgada: la matrix propia debe ser reproducible y comparada contra baselines externos.
4. Seguridad: command injection, prompt injection, acciones destructivas y verificacion superficial pueden generar dano real.
5. Latencia: agregar VLM, 14B o best-of-N puede destruir la promesa de experiencia tipo Alexa.

## Competidores mas relevantes

| Competidor | Amenaza | Por que importa |
|---|---|---|
| Agent-S | Alta | Publica resultados fuertes en OSWorld/WindowsAgentArena y ataca computer-use visual. Carter pierde aqui si se mide solo GUI benchmark. |
| goose | Alta | Es agente local/desktop/CLI extensible, con proveedores locales y MCP. Compite por el usuario de agente general en maquina propia. |
| Mark-XXXIX | Media-alta | Es muy cercano al imaginario "Jarvis" con voz, vision y control de PC, pero depende de Gemini y tiene mas hardcoding. |
| Open Interpreter | Media-alta | Muy fuerte en ejecucion de codigo/local shell. Carter no deberia intentar ganarle en arbitrary code execution. |
| OS-Copilot | Media | Tiene tesis academica de agente OS auto-mejorable, pero esta mas orientado a generacion/ejecucion de codigo y menos a Windows-first privado. |
| openclaw | Media | Fuerte como asistente personal multi-canal local-first, no especificamente Windows OS control. |
| OpenHands | Baja para Carter producto, alta para coding | Gana claramente en software engineering; Carter no compite ahi. |
| AutoGPT | Media en automatizacion | Fuerte en workflows continuos y plataforma; menos cercano a PC local interactiva. |
| AutoGen | Baja directa | Framework multi-agent, no asistente final para usuario normal. |
| LangGraph | Baja directa | Framework de orquestacion; Carter puede copiar ideas, no competir como producto final. |

## Que falta demostrar

- GUI universal razonable en apps reales, no solo acciones simples.
- Misiones multi-paso con replanificacion y verificacion paso a paso.
- Comparacion reproducible contra Agent-S, Open Interpreter, Mark-XXXIX, goose y OS-Copilot en tareas locales de Windows.
- Auditor automatico con menos falsos positivos y falsos negativos.
- Seguridad ante prompts maliciosos, comandos peligrosos y datos sensibles.
- Latencia p50/p95 publicada por categoria de tarea.

## Clasificación de afirmaciones

Evidencia: 55 tools cargadas, 131 tests pasando, existencia de sandbox, safety, verifiers, memoria, skill store y reporte 540 local.

Inferencia razonable: Carter final puede ser competitivo si convierte esa base en robustez GUI/multi-step medible.

Hipotesis pendiente: que un modelo local pequeno pueda sostener calidad suficiente en lenguaje natural ambiguo sin cloud.

Opinion estrategica: Carter debe aceptar un nicho estrecho y no competir contra todos los agentes en todos los ejes.

Claim no defendible: "Carter ya resolvio el control universal de PC" o "Carter es mejor que Agent-S/OpenHands/Open Interpreter en sus dominios".

## Limitaciones de este análisis

La auditoria leyo documentacion y archivos principales de todos los competidores, con lectura mas profunda en Carter, Agent-S, Mark-XXXIX y OS-Copilot. No se ejecuto cada competidor ni se reprodujeron sus benchmarks. Algunas capacidades declaradas por competidores vienen de sus README y no fueron verificadas en runtime local.

## Qué falta verificar

Hace falta ejecutar una bateria comun local con los competidores instalables, capturar videos/logs, medir latencia real y publicar el dataset de tareas. Tambien falta reconciliar el desfase entre el prompt del usuario y el reporte local actual de Carter.

## Conclusión honesta

Carter merece seguir si se formula como asistente local verificable para Windows, no como agente universal. Su razon de existir no es ganar OSWorld, SWE-bench, workflows cloud o multi-agent frameworks. Su razon defendible es que un usuario de PC tenga un agente privado, rapido y honesto que haga acciones reales y verificadas en Windows. Hoy Carter demuestra una base seria, pero no demuestra todavia la parte mas dificil con suficiente fuerza.
