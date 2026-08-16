# 01 - Tesis de Carter

Fecha de generacion: 2026-05-08

## Que es Carter realmente

Carter es un asistente local para Windows que combina un LLM local, memoria, un registro de tools tipadas, reglas de seguridad, sandboxing y verificadores post-accion para operar una PC real. La vision en `contextocarter.md` no es "chatbot con tools" solamente: la prioridad es que Carter actue, verifique y reporte con honestidad.

Evidencia local:

- `contextocarter.md`: insiste en local, privado, rapido, honesto, sin fake success y con verificacion.
- `Carter_v4/src/carter_v4/agent.py`: implementa loop de agente, plan ligero para misiones, safety, memoria, tools, verificadores y follow-up opcional.
- `Carter_v4/src/carter_v4/tools/__init__.py`: registro declarativo de tools con `verifier_name` e `is_destructive`.
- `Carter_v4/src/carter_v4/verify.py` y `verifier_orchestrator.py`: reescritura de claims no verificados y resultado global COMPLETED/PARTIAL/FAILED/UNVERIFIED/NEEDS_USER.

## Que NO es Carter

Carter no es:

- Un AGI.
- Un reemplazo de Agent-S en benchmarks visuales avanzados.
- Un reemplazo de OpenHands para desarrollo de software.
- Un reemplazo de AutoGPT como plataforma de workflows continuos.
- Un framework general tipo LangGraph o AutoGen.
- Un "Jarvis universal" que entiende cualquier app sin fallo.
- Un sistema que hoy pueda prometer 540/540 o GUI universal confiable.

## Contra que categoria compite

Carter compite parcialmente contra varias categorias, pero no pertenece limpiamente a una sola:

| Categoria | Carter compite? | Comentario |
|---|---:|---|
| Desktop/OS agent | Si | Es el eje principal. |
| GUI agent | Si, parcialmente | Necesita GUI, pero no deberia definirse solo por vision/clicks. |
| Browser agent | No principalmente | Web es una tool, no el producto. |
| Coding agent | No principalmente | Terminal/codigo son capacidades auxiliares. |
| Research agent | No | No es su nicho. |
| Framework agentico | No como producto | Puede incorporar patrones, pero el valor es producto local. |
| Personal assistant | Si | Pero con foco en PC Windows verificable. |

## Nicho real

El nicho defendible es: usuario de Windows que quiere automatizar acciones cotidianas en su propia PC, con privacidad local, baja latencia, tools concretas, confirmaciones para acciones destructivas y reporte honesto de acciones no verificadas.

Ese nicho es estrecho, pero real. No todos los competidores lo cubren bien:

- Agent-S apunta a computer-use visual y benchmarks.
- OpenHands apunta a software engineering.
- AutoGPT apunta a workflows continuos.
- LangGraph/AutoGen son frameworks.
- Open Interpreter apunta a ejecucion de codigo y shell.
- openclaw apunta a asistente multi-canal.
- Mark-XXXIX se acerca mas, pero usa Gemini cloud y mas dispatch/hardcoding.

## Por que "asistente local Windows-first privado y verificable" puede ser tesis valida

La tesis es valida porque combina restricciones que rara vez aparecen juntas:

1. Local-first: reduce dependencia de cloud y exposicion de datos.
2. Windows-first: prioriza el entorno real de muchos usuarios no tecnicos.
3. Tool-first: usa APIs y operaciones del sistema cuando existen, no solo vision/clicks.
4. Verifiable-by-design: cada accion importante deberia tener un chequeo posterior.
5. Honest reporting: si no hay evidencia, el sistema no deberia vender exito.
6. Low-latency: un asistente de PC debe sentirse interactivo, no como batch automation.

La contribucion no esta en inventar LLMs ni GUI automation desde cero. Esta en juntar esas restricciones en una arquitectura evaluable y usable.

## Innovacion, integracion e ingenieria de producto

| Parte | Naturaleza | Evidencia |
|---|---|---|
| Registro tipado de tools con verifiers/destructive flags | Ingenieria fuerte, no investigacion pura | `tools/__init__.py` |
| Orquestador de verificacion y anti fake-success | Contribucion defendible si se evalua | `verify.py`, `verifier_orchestrator.py` |
| Windows app resolver, Steam manifests, registry read-only | Integracion de producto con valor real | `tools/apps.py`, `tools/registry.py` |
| Sandbox compartido filesystem/terminal/office | Ingenieria de seguridad | `tools/_sandbox.py`, `tools/files.py`, `tools/terminal.py` |
| Memoria local + skill store | Integracion conocida, util si se mide | `memory.py`, `skill_store.py` |
| GUI universal UIA/OCR/VLM | Promesa parcialmente implementada | `tools/gui_universal.py` |
| Evaluacion 540 | Contribucion potencial si se publica y limpia | `CARTER_540_REAL_PROGRESS_REPORT.md` |

## Carter actual vs Carter final vs Carter ideal exagerado

| Nivel | Definicion | Estado honesto |
|---|---|---|
| Nivel A - Carter actual | Codigo existente y resultados medidos localmente. | 55 tools, 131 tests pasando, safety/verifiers/sandbox, 417/540 manual en reporte local. Base seria, no producto completo. |
| Nivel B - Carter final razonable | Roadmap plausible segun `contextocarter.md`: Windows local, GUI razonable, multi-step, verificacion robusta, memoria, latencia aceptable. | Tesis fuerte si se demuestra con evaluacion externa y tareas reales. |
| Nivel C - Carter ideal exagerado | "Controla cualquier app", "nunca falla", "mejor que todos los agentes", "Jarvis real". | NO defendible todavia. Claim exagerado / marketing / no comprobado. |

## Claims defendibles

- Carter actual ya tiene evidencia concreta en este eje: registro amplio de tools, tests automatizados y verificadores estructurales.
- Carter actual ya tiene evidencia concreta en este eje: control de filesystem, terminal sandboxed, registry read-only, clipboard, apps, procesos, media y ventanas.
- Carter final puede defender el claim de asistente local Windows-first verificable si demuestra que sus verificadores reducen fake success en tareas reales.
- Carter final puede defender privacidad local para tareas que no usan web/cloud, porque el modelo y las tools corren en la maquina.

## Claims exagerados

- "Carter ya es un asistente universal de PC".
- "Carter no usa hardcodes"; hay todavia tokens simples en safety/verify y conocimiento estructural por tools.
- "Carter supera a Agent-S en GUI"; no hay evidencia local equivalente a OSWorld/WindowsAgentArena.
- "Carter supera a OpenHands en coding"; no es su dominio.
- "Carter tiene latencia tipo Alexa en todas las tareas"; no aplica a GUI pesada, vision, terminal largo o modelos grandes.
- "Carter es completamente seguro"; ninguna automatizacion OS con LLM puede prometer eso sin limites fuertes.

## Claim central recomendado

Carter es un asistente local Windows-first que prioriza acciones verificables sobre promesas: cuando controla tu PC, debe comprobar lo que hizo o decir que no pudo comprobarlo.

## Claim que nunca deberia usar

"Carter es mejor que todos los agentes existentes" o "Carter ya resolvio el control universal del sistema operativo".

## Clasificación de afirmaciones

Evidencia: archivos Carter v4, tests locales, reporte 540 local, lista de tools cargada.

Inferencia: el nicho Windows local privado existe porque competidores cercanos priorizan otros ejes.

Hipotesis: que el usuario final valore mas privacidad/verificacion que maxima capacidad VLM cloud.

Opinion estrategica: Carter debe vender menos fantasia y mas trazabilidad.

Claim no defendible: cualquier formulacion que lo presente como AGI, OSWorld SOTA o coding agent SOTA.

## Limitaciones de este análisis

No se corrio Carter en una sesion interactiva de usuario ni se midio una demo completa. La tesis se evalua desde codigo, docs y reportes locales. Tampoco se ejecuto cada competidor.

## Qué falta verificar

Falta una evaluacion externa con tareas identicas, grabacion de pantalla, logs de verificacion y comparacion contra competidores instalados. Tambien falta demostrar que la memoria y skill store mejoran resultados sin degradar safety.

## Conclusión honesta

La tesis existe, pero no es "hacer otro agente". La tesis es construir un asistente local Windows-first que haga menos magia falsa y mas acciones comprobables. Carter actual ya apunta a eso. Carter final lo justificaria si convierte esa filosofia en resultados reproducibles, especialmente en GUI y multi-step.
