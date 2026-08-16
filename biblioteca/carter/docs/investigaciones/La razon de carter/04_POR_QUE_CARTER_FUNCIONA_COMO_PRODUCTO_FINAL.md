# 04 - Por que Carter funciona como producto final

Fecha de generacion: 2026-05-08

## Premisa

Carter final funciona solo si se acepta una definicion estrecha: asistente local Windows-first para acciones reales de PC, con privacidad, baja latencia y verificacion. Si se exige que sea mejor que todos los agentes en GUI, coding, browser automation, multi-agent workflows y research, no funciona.

## Argumentos por eje

| Punto | Evidencia actual | Evidencia pendiente | Riesgo |
|---|---|---|---|
| Diseno local | `agent.py` usa modelo local por Ollama; `data/models.json` contiene perfiles qwen3 locales. | Probar instalacion limpia offline y medir calidad sin cloud. | Modelos locales pequenos pueden rendirse o razonar peor que cloud. |
| Privacidad | Memoria SQLite local en `memory.py`; tools corren en maquina. | Documentar exactamente que sale a internet cuando se usa web_search/web_fetch. | Cualquier provider externo o busqueda web rompe claim absoluto de privacidad. |
| Windows-first | Tools de apps, registry, ventanas, Steam, procesos y volumen estan en `tools/apps.py`, `registry.py`, `gui.py`, `system.py`. | Validar en varias versiones de Windows, idiomas y escalados DPI. | Windows automation es fragil y cambia por app/actualizacion. |
| Control directo del sistema | 55 tools cargadas localmente cubren sistema, apps, archivos, terminal, office, clipboard, registry y GUI. | Medir exito real por categoria en PC fresca. | Cobertura amplia puede parecer completa sin ser robusta. |
| Tools verificables | `ToolSpec.verifier_name`, `verify.py`, `verifier_orchestrator.py`. | Medir reduccion de fake success frente a competidores. | Un verifier superficial puede dar falsa confianza. |
| Latencia razonable | Reporte local indica p50 cercano a 700ms y p95 alrededor de 3s en el estado medido. | Publicar latencia por tipo de tarea y hardware. | VLM, 14B o loops largos rompen experiencia tipo Alexa. |
| Arquitectura simple | Agent loop evita multi-agent pesado por defecto. | Demostrar que simplicidad no limita tareas reales. | Tareas multi-step pueden requerir memoria/planning mas sofisticados. |
| Evaluacion masiva | `CARTER_540_REAL_PROGRESS_REPORT.md` muestra matrix amplia y auditoria manual. | Abrir dataset, scripts, criterios y baselines. | Conflictos de numeros y falsos positivos reducen credibilidad. |
| Verifiers | Existen verificadores para filesystem, apps, windows, terminal, etc. | Validar contra fallos adversariales y apps lentas. | Verificar "app abierta" o "ventana cambio" no siempre equivale a exito de usuario. |
| Honestidad por diseno | `verify.py` reescribe claims no verificados; `verifier_orchestrator.py` distingue UNVERIFIED/PARTIAL. | Mostrar ejemplos reales donde Carter admite no haber verificado. | Si la respuesta final sigue sonando exitosa ante fallos, el diferenciador se pierde. |
| Integracion PC real | Steam manifests, protocols HKCR, normalization de nombres y sandbox en `apps.py` y `_sandbox.py`. | Probar con Steam/Discord/Spotify/Office/navegadores reales. | Apps modernas con launchers y updates complican verificacion. |
| Sin depender de cloud | Plausible con Ollama local para core. | Garantizar modo offline completo y documentado. | Web, busqueda o modelos externos introducen dependencia indirecta. |
| Sin hardcodes por app | `apps.py` usa StartApps, registry, PATH, manifests y protocols. | Reducir listas/tokens restantes y documentar excepciones. | La promesa absoluta es demasiado fuerte; siempre habra knowledge estructural. |

## Valor para usuario normal

El valor no es que Carter "sepa todo". Es que pueda hacer cosas pequenas de PC con friccion baja: abrir una app, buscar un archivo, mover/copiar, leer portapapeles, ajustar volumen, ejecutar un comando seguro, consultar bateria, abrir un juego de Steam, organizar ventanas y decir cuando no pudo hacerlo.

Para un usuario normal, eso puede ser mas util que un agente muy poderoso que requiere API keys, Docker, prompts complejos o permisos de codigo arbitrario.

## Valor para developer

Carter tiene valor como arquitectura de producto local: registro de tools, tests, sandbox, safety y verifiers. Un developer puede auditar cada accion mas facilmente que en agentes code-first.

## Valor para tesis

La pregunta interesante no es "puede Carter hacer todo?". La pregunta defendible es: "cuanto mejora la confiabilidad percibida y real de un asistente local de PC cuando cada tool tiene verificacion explicita y el sistema reporta acciones no verificadas?".

## Diferencia contra competidores

- Contra Agent-S: Carter no gana en GUI benchmark, pero puede ganar en acciones Windows directas, privadas y verificadas.
- Contra Open Interpreter: Carter no gana en codigo arbitrario, pero puede ganar en safety y UX de usuario normal.
- Contra Mark-XXXIX: Carter puede ganar en privacidad y verificabilidad, aunque pierda en voz/live multimodal.
- Contra goose/openclaw: Carter debe especializarse mas en Windows PC real, no extension ecosystem general.
- Contra OpenHands: Carter no compite en coding.

## Clasificación de afirmaciones

Evidencia: tools y tests locales, archivos de arquitectura, matrix 540 local.

Inferencia: el usuario final puede preferir un asistente menos general pero mas privado/verificable.

Hipotesis: que completar GUI y multi-step bastara para que el producto se sienta util.

Opinion estrategica: Carter final debe optimizar la sensacion de "hizo lo que pedi y lo comprobo", no la sensacion de magia.

Claim no defendible: que el producto final sera universal sin restricciones.

## Limitaciones de este análisis

Se evalua una vision final razonable, no un producto empaquetado. No se verifico instalador, UX grafica, voz, onboarding ni soporte tecnico.

## Qué falta verificar

Falta una prueba end-to-end con usuario externo: instalacion, primera tarea, permisos, errores, recuperacion y logs. Sin eso, "producto" sigue siendo mas tesis tecnica que experiencia lista.

## Conclusión honesta

Carter final puede funcionar porque su propuesta no es maxima inteligencia; es control local verificable de una PC Windows. Esa propuesta es suficientemente distinta para existir, pero solo si la implementacion deja de fallar justo en GUI, multi-step y ambiguedad cotidiana.
