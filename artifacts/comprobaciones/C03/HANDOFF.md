# C03 — corrección de ventanas publicada; siguiente: prosa factual

Goal activo, rama `Goal-c03`. Fuente 646/651 publicada en `e1c6db6bb79bf1aa69e3c5ec72acac5656804700`; HEAD y origin verificados iguales tras el push. Main intacto (`5f572ee1b48cb5e2543ee5e06510e51057c9c845`). Encuesta: 25 cubiertos, 717 abiertos, 0 no aplicables. Ninguna decisión pendiente del dueño. Su autorización 536 permite histórico, encuesta y casos nuevos conservando procedencia. BAXY manual debe permanecer cerrado. Sin agentes.

## Validación y publicación

Full 651 terminó y la sesión 1464 fue recogida: exit 0. Python: 10411 pases, 3 skips y 466 subpruebas, 732,07 s. .NET: 4469 pases, 1 skip agregado y 16 omisiones opt-in impresas por separado. Dueñas: 3521 pases + 121 subpruebas, 0 skips; R4/R5/R6: 1408 pases; alcance: 97 pases. Fast exit 0, Release 4,66 s. No hay validación ni inferencia activa.

Full 646 queda sellado en rojo: sus 24 fallos comenzaron en 633, no en la referencia contextual 646. Se recuperaron sinónimos de primer plano y lecturas singulares acotadas dentro de enumeraciones sin alterar oráculos. 646 conserva las referencias de preguntas del usuario hasta los argumentos, pasando el historial existente del shell. No añade estado, modelo ni prosa visible fija. Se publicaron 32 pines de cinco campañas y se verificaron los seis archivos de fuente tanto en el árbol validado como en su representación Git LF.

`c03-close-window651.py` y `c03-update-survey647.py` YA ejecutados; no repetir. `c03-matrix-publication651.py` YA ejecutado, incluidas correcciones de legibilidad: actualiza sólo G04.06, G06.01 y G06.06. Este cambio documental se publica a continuación. No ejecutar `c03-close-context646.py`: quedó obsoleto al sellar ese rojo. SHA privado de requisitos: `841e78b31ff2cb6d2f97f78b12692588ffae3a85d35f378cd31f0ce4691a8f0b`.

## Siguiente acción: experimento 650

`scratchpad/c03-native-window-scope650.py` está preparado, NO ejecutado. Exige RESULT 651 con Full exit 0 antes de crear sus carpetas. El preflight capturó los 16 payloads: ocho casos por dos brazos; sólo cambia una instrucción de sistema sobre el alcance de lo observado. Usa la situación real de 647/t15 y comprueba igualdad exacta de su payload visible. Los otros siete casos son fixtures declarados, con idiomas, nombres y cantidades distintos. No presentar el conjunto como un replay exacto de HTTP ni como lecturas reales de esos nombres sintéticos.

El constructor usa el compositor actual y el perfil registrado: temperatura 0, 256 tokens, cache_prompt=false, pensamiento desactivado. 523 ya probó la receta documentada de Qwen sobre sus propios fallos sin promoción. El experimento 650 aísla una instrucción, no descarta modelos por sus defaults. Después, adjudicar a mano todos los borradores; el validador 649 es defectuoso y no debe actuar como oráculo. No adoptar una instrucción por una única respuesta favorable.

647, anterior a 651, obtuvo 18/20 finales frente a 15 en 642. Las cuatro referencias ya hacen lecturas nuevas correctas. t15 añade «running» sin observar procesos; t10 responde en español a una pregunta inglesa. H0040 sigue abierto por la prosa, ya no por referencias. Recursos de esa corrida sin UI/voz conjunta: GPU 3497,559 MiB y RAM 2290,973 MiB; no son un mínimo global. 648 explica dos ventanas de WhatsApp en procesos con el mismo AUMID, con identidad consultada posteriormente y esa limitación explícita. 649 conserva siete contradicciones/afirmaciones sin respaldo aceptadas de once controles: instalación, cantidad y estado de proceso. Heredar `_payload_fact_defect`; no basta bloquear una palabra ni añadir lecturas no pedidas.

El fallo de idioma es independiente: `request_reading._ES_WORDS` trata `has` como evidencia exclusivamente española. Conservar las lecturas españolas y mixtas al repararlo. No fuente factual o de idioma editada aún. `llm.py` sigue en SHA `464603566c9dc66204cc75e45a79c8058063d0bb06fe6ff554bf56529e5ea73e`. Registro, Qwen2507 Q4 y servidor b9980 intactos.

## UI y resto del objetivo

La herramienta `tools.mcp__node_repl__js({code,title})` está disponible. `import('@oai/sky')` inicializado y `sky.list_windows()` funciona. Es distinta de native CUA deshabilitado. Skill computer-use y docs guidance, confirmations y api LEÍDOS. No se abrió BAXY ni se activaron/capturaron ventanas. Para la UI futura: seleccionar una ventana recién devuelta, observar, parar, una acción y refrescar; verificar foco antes de escribir. No mezclar shell UIA con sky en el turno.

Heredar el arranque `py main.py` sin hooks del launcher 315, pero no repetir ese mutador: dejaba una instancia manual sin cierre. La nueva prueba debe terminar su propia instancia. Voz 259 mide eco puro; separar recuperación íntegra de loopback de supresión AEC, sin acreditar voz humana física de C08. Siguen pendientes prosa, idioma, cobertura de encuesta, ocho rutas, UI real, loopback/AEC, recuperación y Full final. La continuidad C04–C09 ya está documentada; no ejecutar esos goals.

Python de pruebas: `C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -X utf8`.
