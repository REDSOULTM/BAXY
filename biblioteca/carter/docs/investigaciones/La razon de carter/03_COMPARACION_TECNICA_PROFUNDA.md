# 03 - Comparacion tecnica profunda

Fecha de generacion: 2026-05-08

## Arquitectura actual de Carter

Carter v4 usa un loop central en `Carter_v4/src/carter_v4/agent.py`: entrada de usuario, deteccion de mision, memoria, posible recuperacion de skills, safety, llamada a LLM local, tool calls, verificadores, reflexion si falla una tool, y respuesta final. La arquitectura es mas simple que frameworks multi-agent, pero tiene piezas concretas de producto OS.

Componentes clave:

| Componente | Archivo | Lectura honesta |
|---|---|---|
| Agent loop | `Carter_v4/src/carter_v4/agent.py` | Pragmatico, orientado a baja latencia. No es un planner general profundo. |
| Tool registry | `Carter_v4/src/carter_v4/tools/__init__.py` | Fuerte: tools tipadas con verifiers y destructive flags. |
| Safety | `Carter_v4/src/carter_v4/safety.py` | Buen inicio estructural, pero aun hay tokens simples de confirmacion/cancelacion. |
| Verification | `Carter_v4/src/carter_v4/verify.py`, `verifier_orchestrator.py` | Diferenciador real, aunque algunos checks son superficiales o aproximados. |
| Loop detection | `Carter_v4/src/carter_v4/loop_detection.py` | Resultado-aware con SHA-256; buena proteccion contra bucles tontos. |
| Memory | `Carter_v4/src/carter_v4/memory.py` | SQLite local, filtro de secretos, embeddings opcionales. |
| Skills | `Carter_v4/src/carter_v4/skill_store.py` | FTS5 y critic; prometedor, falta evidencia fuerte de impacto. |
| PC tools | `tools/apps.py`, `files.py`, `terminal.py`, `registry.py`, `clipboard.py`, `gui.py`, `gui_universal.py` | Amplia cobertura local Windows, pero GUI universal no esta cerrada. |

## Agent loop y planning

| Eje | Competidor | Carter actual | Carter final razonable | Veredicto honesto |
|---|---|---|---|---|
| GUI task loop | Agent-S | Worker con screenshot, grounding agent, procedural memory, code agent y best-of-N en `gui_agents/s3`. | Planner ligero y tools OS verificables, con GUI cascade robusta. | Incluso como producto final razonable, Carter probablemente no ganaria aqui si la metrica principal es OSWorld visual puro, porque Agent-S esta optimizado y publicado para eso. |
| Personal assistant loop | Mark-XXXIX | Planner + executor + error handler con Gemini en `agent/planner.py` y `agent/executor.py`. | Carter deberia ser menos espectacular en voz, pero mas local y verificable. | Carter actual ya tiene evidencia concreta en este eje: tool registry, verifiers, safety y tests. Mark parece mas demo multimodal, menos verificable. |
| Code-first loop | OS-Copilot | Planner/retriever/executor/self-refining con generacion de codigo en `friday_agent.py`. | Carter debe usar codigo/terminal de forma acotada, no como motor universal. | OS-Copilot es mas ambicioso como research OS agent; Carter final puede ganar en producto Windows si evita riesgos de code-generation-first. |
| Framework loop | LangGraph/AutoGen | Frameworks para durable/multi-agent/event-driven apps. | Carter podria incorporar checkpoints/HITL sin convertirse en framework. | No son rivales directos; son baselines arquitectonicos. |
| Code execution loop | Open Interpreter | Conversacion que ejecuta codigo local con aprobacion. | Carter deberia mantener tools curadas y terminal sandboxed. | Incluso como producto final razonable, Carter probablemente no ganaria aqui porque Open Interpreter esta construido para ejecucion de codigo general. |

## Tool registry y tool calling

Carter actual tiene un punto fuerte claro: el registro en `tools/__init__.py` no solo lista funciones; tambien separa descripcion, schema, verifier y si una accion es destructiva. Esto permite que safety y verification no dependan unicamente del prompt.

Comparacion:

- Agent-S usa acciones GUI/code generadas y grounded; es poderoso, pero mas dependiente de screenshots y modelos de grounding.
- Mark-XXXIX usa dispatch por if/elif en `agent/executor.py`; es practico, pero menos declarativo y menos auditable que Carter.
- OS-Copilot genera y almacena herramientas como codigo; es flexible, pero aumenta el riesgo de safety.
- AutoGen/LangGraph dan abstracciones mas generales; Carter tiene una implementacion mas concreta para producto.
- goose/openclaw usan ecosistemas de extensions/skills/MCP; Carter deberia aprender de la extensibilidad, pero sin perder el contrato de verificacion.

Veredicto: Carter actual ya tiene evidencia concreta en este eje: 55 tools cargadas, schemas y flags de verificacion/destruccion.

## Function calling y formato

Carter expone catalogo compatible con formato de function calling en `tools/__init__.py`, pero corre con Ollama/modelo local. Esta decision favorece portabilidad y latencia, aunque limita razonamiento frente a modelos cloud grandes.

Riesgo: el modelo local puede no elegir bien la tool bajo ambiguedad. El reporte `CARTER_540_REAL_PROGRESS_REPORT.md` muestra fallos por rendirse, no entender o no replanificar.

## Verificacion de acciones

| Aspecto | Carter | Competidores |
|---|---|---|
| Verifiers por tool | Si, via `verifier_name`. | No es el centro declarado en la mayoria. |
| Estado global de accion | Si, `verifier_orchestrator.py`. | Agent-S observa screenshot/reflection; OS-Copilot usa LLM judge; otros dependen de runtime/logs. |
| Anti fake-success textual | Si, `verify.py`. | No aparece como eje central en README de competidores. |
| Limitacion | Algunos verificadores son superficiales; plan-step verification es aproximada. | Agent-S puede verificar visualmente mejor GUI compleja con VLM/grounding. |

Como producto final Carter tendria una ventaja plausible en este eje, pero Carter actual todavia no lo demuestra completamente. La evidencia pendiente es demostrar que los verifiers reducen fake success contra baselines en tareas reales y no solo en tests internos.

## Manejo de errores y replanning

Carter tiene reflexion puntual tras fallo de tool en `agent.py`, loop detection y resultado partial/failed. Mark-XXXIX tiene error handler LLM que decide retry/skip/replan/abort. OS-Copilot tiene self-refinement y repair. Agent-S usa reflection desde screenshots.

Lectura honesta: Carter es mas controlado, pero menos general. Para usuario real, control puede ser bueno. Para tareas desconocidas, puede quedarse corto.

## GUI automation

Carter tiene dos capas:

- `tools/gui.py`: screenshot, click, type, keypress, window management, frame diff.
- `tools/gui_universal.py`: cascada UIA -> OCR -> VLM declarada, pero el VLM aparece como no activo.

Agent-S supera claramente a Carter actual en GUI research: usa screenshot, OCR, grounding model, procedural memory, pyautogui y reporta resultados OSWorld/WindowsAgentArena en `README.md`.

Veredicto: GUI es la parte que mas amenaza la tesis. Carter final razonable no necesita superar a Agent-S en OSWorld, pero si necesita resolver una GUI universal razonable en apps comunes. Si no lo hace, el producto parece incompleto.

## Terminal/filesystem

Carter:

- `tools/files.py`: operaciones sandboxed, diff, archive, open, delete destructive.
- `tools/_sandbox.py`: raices permitidas compartidas.
- `tools/terminal.py`: allowlist de binarios, `shell=False`, cwd sandbox, timeout y verifier por exit_code.

Competidores:

- Open Interpreter gana en ejecucion flexible de codigo/shell.
- OS-Copilot genera y ejecuta Python/Shell/AppleScript.
- OpenHands gana en tareas de desarrollo profesional.

Veredicto: Carter no deberia ganar por potencia bruta. Debe ganar por seguridad, previsibilidad y adecuacion a usuario normal.

## Memory y skills

Carter usa SQLite local (`memory.py`) y FTS5 para skills (`skill_store.py`). Agent-S tiene procedural memory muy orientada a GUI. OS-Copilot tiene repositorio de herramientas con Chroma y self-improvement. openclaw tiene skills y prompt files. LangGraph da memoria/checkpoints como patron.

Lectura honesta: Carter tiene piezas, pero falta demostrar mejora medible. Una memoria que no mejora tareas o que introduce datos incorrectos no es ventaja.

## Safety, permisos y sandbox

Carter tiene flags destructivos por tool y gates en `safety.py`; filesystem y terminal estan sandboxed. Registry es read-only. Esto es un argumento fuerte contra agentes code-first.

Riesgo: safety aun depende de clasificacion de tools y parametros; prompt injection en web/clipboard/files puede empujar acciones indirectas. La defensa requiere tests adversariales.

## Evaluacion y benchmarks

Evidencia local Carter:

- `Carter_v4/CARTER_540_REAL_PROGRESS_REPORT.md`: 417/540 manual y 489/540 automatico; falsos positivos relevantes.
- Tests locales: 131 passing.

Competidores:

- Agent-S publica resultados fuertes en OSWorld/WindowsAgentArena/AndroidWorld.
- OpenHands declara SWE-bench 77.6 en README.
- AutoGPT tiene agbenchmark/Agent Protocol en su ecosistema.

Lectura honesta: Carter tiene una matrix grande, pero todavia no tiene el peso externo de OSWorld/SWE-bench. La evaluacion propia es util para desarrollo, insuficiente para tesis fuerte sin apertura, reproducibilidad y baselines.

## Simplicidad vs generalidad

Carter es mas simple que LangGraph/AutoGen y menos general que Open Interpreter/OS-Copilot. Eso no es automaticamente bueno ni malo. Es bueno si produce latencia baja, menos superficie de fallo y UX de usuario normal. Es malo si impide resolver tareas no previstas.

## Localidad y privacidad

Carter tiene ventaja clara frente a Mark-XXXIX, Agent-S por defecto y muchos setups cloud si se mantiene con Ollama local. goose y Open Interpreter pueden usar local tambien, por lo que la privacidad no basta como diferenciador. Carter necesita sumar Windows-first + verificadores.

## Clasificación de afirmaciones

Evidencia: rutas de codigo y reportes citados arriba.

Inferencia: Carter final puede ganar por combinacion local/private/verifiable, no por maxima inteligencia.

Hipotesis: que la verificacion estructural compense parte de la menor capacidad del modelo local.

Opinion estrategica: evitar code-generation-first como motor principal es correcto para producto seguro.

Claim no defendible: "Carter ya tiene GUI universal"; `gui_universal.py` no demuestra VLM activo ni robustez en apps modernas.

## Limitaciones de este análisis

No se hizo trazado line-by-line completo de todos los competidores. La comparacion tecnica profunda se basa en archivos principales y arquitectura visible. No se midio runtime real de cada proyecto.

## Qué falta verificar

Falta instalar Agent-S, Mark-XXXIX, Open Interpreter, goose y OS-Copilot bajo una suite local comun. Tambien falta medir si Carter mantiene sus garantias cuando herramientas fallan, apps tardan en abrir o Windows cambia de idioma/tema/escalado.

## Conclusión honesta

Carter tiene una arquitectura suficientemente distinta para merecer evaluacion, pero no para declararse ganador. Su ventaja tecnica real es el contrato tool + verifier + safety en entorno Windows local. Su debilidad tecnica real es que la GUI y las misiones largas todavia son exactamente donde los agentes modernos mas fuertes concentran su avance.
