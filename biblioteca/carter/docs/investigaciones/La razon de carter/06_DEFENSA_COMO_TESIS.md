# 06 - Defensa como tesis

Fecha de generacion: 2026-05-08

## Pregunta de investigacion posible

Puede un asistente LLM local, Windows-first y basado en herramientas verificables ejecutar tareas cotidianas de PC con menor tasa de exito no verificado que agentes generalistas basados en codigo, navegador o computer-use visual, manteniendo latencia interactiva y privacidad local?

## Hipotesis central

Un agente local con tool registry tipado, verificadores post-accion, memoria local, sandboxing y confirmaciones destructivas puede ofrecer un perfil de confiabilidad practico para tareas de PC Windows, aun cuando no iguale a modelos cloud/VLM en razonamiento visual general.

## Contribucion principal

La contribucion defendible no es "crear otro asistente". Es demostrar un patron de arquitectura y evaluacion para asistentes OS locales:

- herramientas concretas de Windows,
- verificacion por accion,
- reporte explicito de incertidumbre,
- separacion read-only/write/destructive,
- evaluacion masiva con auditoria manual y automatica,
- medicion de latencia y fake success.

## Metodologia

1. Definir suite de tareas Windows en categorias: sistema, apps, archivos, terminal, browser, clipboard, registry read-only, Steam, GUI, multi-step y safety.
2. Ejecutar Carter actual y competidores seleccionados en la misma maquina o VM.
3. Capturar logs, screenshots/video y estado antes/despues.
4. Clasificar cada intento como COMPLETED, PARTIAL, FAILED, UNVERIFIED o NEEDS_USER.
5. Medir tasa de exito real, tasa de fake success, latencia p50/p95, numero de confirmaciones, numero de replans y fallos por categoria.
6. Hacer auditoria manual ciega de una muestra para validar el auditor automatico.
7. Publicar tareas, criterios, scripts y limitaciones.

## Metricas

| Metrica | Por que importa |
|---|---|
| Task success real | Mide utilidad. |
| Fake-success rate | Mide honestidad, el eje central de Carter. |
| Unverified reporting accuracy | Mide si Carter sabe decir "no lo comprobe". |
| Latencia p50/p95 | Mide viabilidad como asistente interactivo. |
| Destructive-action safety | Mide riesgo de dano. |
| Recovery after failure | Mide robustez multi-step. |
| Cross-machine reproducibility | Mide si no es solo setup personal. |
| Manual vs automatic audit agreement | Mide confiabilidad de la evaluacion. |

## Experimentos

| Experimento | Baselines sugeridos | Resultado minimo necesario |
|---|---|---|
| Tareas OS directas Windows | Open Interpreter, Mark-XXXIX, goose | Carter debe ganar o empatar en acciones simples con menor fake success. |
| GUI apps comunes | Agent-S, Mark-XXXIX | Carter no necesita ganar OSWorld, pero debe demostrar GUI razonable en apps objetivo. |
| Terminal/filesystem seguro | Open Interpreter, OS-Copilot | Carter debe mostrar menos riesgo y buena tasa de exito en tareas acotadas. |
| Safety destructiva | Todos los comparables instalables | Carter debe bloquear o pedir confirmacion de forma consistente. |
| Latencia local | Carter perfiles 4B/14B y competidores locales | Carter debe sostener interactividad en tareas comunes. |
| Evaluacion auditor | Manual ciego vs automatico Carter | Reducir falsos positivos por debajo de un umbral publicado. |

## Baselines

- Agent-S para GUI/computer-use.
- Open Interpreter para codigo/shell local.
- Mark-XXXIX para asistente personal multimodal.
- goose para agente local general/desktop/CLI.
- OS-Copilot para agente OS research/self-improving.
- OpenHands solo para subtest developer, no como rival general de producto.
- AutoGPT, AutoGen y LangGraph como contexto de arquitectura/plataforma, no baselines primarios de PC local.

## Resultados minimos para que la tesis sea fuerte

- Exito real alto en tareas core Windows, no necesariamente en todo.
- Fake-success rate claramente menor que baselines.
- GUI y multi-step al menos razonables en apps seleccionadas.
- Auditor automatico calibrado contra auditoria manual.
- Latencia p95 aceptable para tareas no visuales.
- Modo local/offline documentado.
- Safety destructiva demostrada con tests adversariales.

## Demo convincente

Una demo convincente no es una tarea perfecta preparada. Debe mostrar:

1. Carter abre una app ambigua correctamente.
2. Manipula archivo/clipboard/ventanas.
3. Ejecuta terminal sandboxed.
4. Falla en una accion GUI dificil y lo reporta como no verificado.
5. Pide confirmacion ante una accion destructiva.
6. Replanifica una mision multi-step.
7. Muestra logs y verifiers despues.

## Evidencia insuficiente

- Solo videos editados.
- Solo un benchmark propio sin dataset.
- Solo "pass automatico" sin auditoria manual.
- Solo claims de privacidad sin documentar red/modelos.
- Solo comparacion contra prototipos debiles.

## Tres posibles titulos de tesis

1. Carter: un asistente local Windows-first con verificacion post-accion para reducir exito fingido en agentes de PC.
2. Arquitectura y evaluacion de un agente local verificable para tareas cotidianas en Windows.
3. Control de PC privado y verificable con LLMs locales: diseno, seguridad y evaluacion de Carter.

## Abstract academico

Los agentes basados en modelos de lenguaje pueden operar herramientas y entornos graficos, pero frecuentemente reportan exito sin evidencia, dependen de servicios cloud o se evaluan en benchmarks alejados del uso cotidiano de una PC personal. Esta tesis presenta Carter, un asistente local Windows-first que combina un modelo LLM local, un registro tipado de herramientas del sistema operativo, verificadores post-accion, memoria local, sandboxing y confirmaciones para acciones destructivas. Evaluamos Carter en una suite de tareas de PC real que incluye sistema, archivos, terminal, aplicaciones, portapapeles, registro read-only, ventanas, navegador y misiones multi-paso. La evaluacion distingue exito real, exito no verificado, fallos parciales, latencia y seguridad, y compara contra agentes de GUI, codigo y asistentes personales. El objetivo no es superar a modelos cloud en razonamiento general, sino medir si una arquitectura local verificable puede ofrecer un perfil practico y honesto para automatizacion cotidiana en Windows.

## Formulacion de hipotesis

H1: En tareas cotidianas de Windows que tienen APIs o herramientas del sistema disponibles, Carter reducira la tasa de exito fingido frente a agentes code-first o GUI-first sin perder latencia interactiva en tareas simples.

H0: La verificacion y el tool registry no producen mejora significativa; Carter falla igual o mas que baselines, o su latencia/scope lo vuelve impractico.

## Amenazas a la validez

- Sesgo de tareas: la suite puede favorecer tools de Carter.
- Sesgo de hardware: resultados dependen de PC, Windows, idioma, DPI y apps instaladas.
- Sesgo de modelo: qwen3 local puede cambiar con cuantizacion/configuracion.
- Auditoria imperfecta: falsos positivos/falsos negativos pueden distorsionar conclusiones.
- Competidores mal configurados: una mala instalacion no prueba inferioridad real.
- Generalizacion: exito en Windows no prueba exito en macOS/Linux ni apps empresariales.
- Safety incompleta: tests controlados no cubren todos los ataques.

## Clasificación de afirmaciones

Evidencia: arquitectura Carter y reporte 540 local.

Inferencia: fake-success es un eje academico defendible porque aparece como fallo central en agentes OS.

Hipotesis: Carter podra reducir fake-success contra baselines.

Opinion estrategica: una tesis estrecha y medible vale mas que un claim general de asistente personal.

Claim no defendible: "Carter demuestra AGI local" o "Carter supera estado del arte en computer-use".

## Limitaciones de este análisis

Este documento propone defensa, no resultados finales. Los resultados reales aun deben producirse con metodologia reproducible.

## Qué falta verificar

Falta construir la suite externa, definir baselines exactos, congelar versiones, ejecutar experimentos y publicar datos.

## Conclusión honesta

Carter puede ser tesis si se defiende como arquitectura local verificable y se evalua contra fake success, safety y latencia. No debe defenderse como asistente universal, porque esa defensa seria demasiado facil de desmontar.
