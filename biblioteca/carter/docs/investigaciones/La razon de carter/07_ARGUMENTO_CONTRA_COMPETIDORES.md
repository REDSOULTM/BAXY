# 07 - Argumento contra competidores

Fecha de generacion: 2026-05-08

## Punto central

Carter no tiene que ser mejor que todos. Carter debe ser mejor en un eje especifico: control local, privado, Windows-first y verificable de una PC real para tareas cotidianas.

Si Carter intenta ganar todos los ejes, pierde. Si gana ese eje, merece existir.

## El eje donde Carter debe ganar

Eje: "accion local verificable en Windows con baja latencia y bajo fake-success".

Este eje incluye:

- ejecutar acciones reales en la PC del usuario,
- usar APIs/tools del sistema cuando existen,
- confirmar acciones destructivas,
- verificar despues de actuar,
- reportar no verificado cuando no puede comprobar,
- mantener privacidad local,
- responder suficientemente rapido para uso cotidiano.

## El eje donde Carter NO debe intentar ganar

Carter no debe intentar ganar en:

- OSWorld SOTA contra Agent-S,
- SWE-bench contra OpenHands,
- arbitrary code execution contra Open Interpreter,
- workflows cloud/no-code contra AutoGPT,
- framework general de agentes contra LangGraph/AutoGen,
- asistente multi-canal/dispositivos contra openclaw,
- demo voice/live multimodal contra Mark-XXXIX si depende de cloud.

Perder ahi no invalida Carter porque no son el problema principal que Carter promete resolver.

## Contra quien pierde y por que no invalida la tesis

| Competidor | Donde Carter pierde | Por que no invalida |
|---|---|---|
| Agent-S | GUI visual benchmark, grounding, OSWorld/WindowsAgentArena. | Carter no necesita ser SOTA GUI; necesita ser util, local y verificable en Windows cotidiano. |
| OpenHands | Desarrollo de software profesional. | Carter no es coding agent. |
| Open Interpreter | Codigo/shell general y flexibilidad. | Carter apunta a tools curadas y seguridad, no a ejecucion arbitraria. |
| AutoGPT | Workflows continuos, marketplace, builder. | Carter es asistente interactivo de PC, no plataforma de automatizacion empresarial. |
| LangGraph/AutoGen | Orquestacion generica de agentes. | Carter es producto aplicado, no framework. |
| openclaw | Multi-canal y gateway personal. | Carter debe especializarse en PC Windows local. |
| Mark-XXXIX | Espectacularidad multimodal/voz con Gemini. | Carter puede ser menos llamativo pero mas privado/verificable. |

## Contra quien puede ganar y por que importa

| Competidor | Donde Carter puede ganar | Condicion |
|---|---|---|
| Mark-XXXIX | Privacidad local, registro declarativo, verifiers, tests. | Debe cerrar UX y GUI sin depender de cloud. |
| Open Interpreter | Seguridad de acciones OS cotidianas. | Debe demostrar que tools curadas resuelven tareas reales mejor que codigo libre. |
| OS-Copilot | Producto Windows-first y menor riesgo code-generation-first. | Debe tener benchmarks claros y mejor safety. |
| goose | Especializacion Windows verificable. | Debe sostener mejor experiencia para usuario normal, no solo extension ecosystem. |
| AutoGPT | Baja friccion para tareas PC interactivas. | Debe evitar volverse plataforma pesada. |

## Comparacion por ejes importantes

| Eje | Competidor | Carter actual | Carter final razonable | Veredicto honesto |
|---|---|---|---|---|
| GUI visual pura | Agent-S | C13 GUI debil en reporte local; VLM no activo. | GUI razonable con UIA/OCR/VLM, pero no necesariamente SOTA. | Incluso como producto final razonable, Carter probablemente no ganaria aqui porque Agent-S esta optimizado para computer-use visual. |
| Acciones Windows directas | Mark-XXXIX | 55 tools, registry read-only, Steam, clipboard, filesystem, terminal. | Mayor cobertura verificable y local. | Carter actual ya tiene evidencia concreta en este eje: tools Windows y tests. |
| Codigo local | Open Interpreter | Terminal sandboxed con allowlist. | Terminal seguro para tareas comunes. | Incluso como producto final razonable, Carter probablemente no ganaria aqui porque Open Interpreter prioriza ejecucion libre de codigo. |
| Verificacion honesta | goose/openclaw/Mark | Verifiers, UNVERIFIED, anti fake-success. | Evaluacion externa de fake-success. | Como producto final Carter tendria una ventaja plausible en este eje, pero Carter actual todavia no lo demuestra completamente. La evidencia pendiente es comparar fake-success contra baselines. |
| Producto usuario normal | AutoGen/LangGraph | Carter ya esta mas cerca de acciones PC concretas. | UI/instalacion simple y tareas cotidianas. | Carter puede ganar porque frameworks no son producto final para usuario normal. |

## Donde Carter es mas practico para usuario real

Carter es mas practico cuando el usuario quiere:

- abrir una app o juego local,
- manipular archivos dentro de rutas permitidas,
- leer/escribir portapapeles,
- consultar sistema,
- correr comandos seguros,
- controlar volumen/media,
- organizar ventanas,
- recibir una respuesta honesta si algo no se verifico.

## Cuando un competidor seria mejor opcion

- Agent-S: tareas visuales GUI complejas y benchmark computer-use.
- OpenHands: arreglar repos, PRs, issues y software engineering.
- Open Interpreter: analisis de datos, scripting y ejecucion de codigo flexible.
- AutoGPT: agentes persistentes con triggers/workflows.
- LangGraph/AutoGen: construir sistemas multi-agent propios.
- openclaw: asistente personal multi-canal con gateway.
- Mark-XXXIX: experiencia de voz/live multimodal con Gemini.

## Argumento competitivo honesto

Carter merece existir si demuestra que un asistente local puede ser mas confiable para acciones concretas de PC que un agente mas general. La ventaja no es "sabe mas"; la ventaja es "opera con menos mentira".

## Clasificación de afirmaciones

Evidencia: comparacion basada en archivos locales citados en `02_MAPA_DE_COMPETIDORES.md`.

Inferencia: el eje de verificacion local es diferenciador porque no domina los READMEs de competidores.

Hipotesis: usuarios valoran fake-success bajo mas que capacidades espectaculares ocasionales.

Opinion estrategica: Carter debe aceptar perder benchmarks ajenos.

Claim no defendible: decir que Carter gana contra competidores sin definir eje y metricas.

## Limitaciones de este análisis

El argumento competitivo todavia no esta respaldado por una tabla experimental comun. Es una tesis estrategica basada en arquitectura y objetivos declarados.

## Qué falta verificar

Falta construir la comparacion Carter vs Agent-S vs Open Interpreter vs Mark-XXXIX vs goose en tareas Windows locales, con logs y auditoria manual.

## Conclusión honesta

Carter no gana por amplitud. Gana si se vuelve el agente que menos finge y mas comprueba en una PC Windows local. Ese eje es suficiente para existir, pero no perdona fallos de GUI, multi-step o evaluacion.
