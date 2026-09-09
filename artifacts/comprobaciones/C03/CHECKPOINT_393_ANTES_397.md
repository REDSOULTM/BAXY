# C03 — checkpoint392 — EN_CURSO

Actualización 393: fuente adoptada y validada. Pruebas antes de fuente: 10 fallos,
10 pass, 0 skips, 1m26s (ocho lecturas explícitas y dos flujos de almacén fallaban).
Sólo NameRecallPattern amplía consultas del nombre guardado ES/EN. Focal 20 pass,
0 skips, 1m08s; seis dueñas 1996 pass, 0 skips, 2m59s; Fast entero verde, build
17,97s sin warnings/errores. RESULT/PINS en astra-stored-name393. Handles64541,
72140 y7530 cerrados. Última fuente .NET es ahora393; Python continúa en383.
Producto393b ACTIVO, handle62347: scratchpad/c03-product393b.py, carpeta
astra-stored-product393b, privado LOCALAPPDATA/BAXY/C03-stored-product393b-private.
Seis controles sintéticos: guardar Jordan con confirmación; leer lo guardado;
declarar Álvaro sin guardar; preguntar otra vez por lo guardado y por el nombre
genérico. Este último sigue abierto, no se declara resuelto por393.
Preparado, NO iniciado: scratchpad/c03-retry-history394.py. Compara con averías
sintéticas el reintento de chat que pierde historial frente a retenerlo, sin
cambiar fuente/prompt/guardias. No iniciar otro modelo ni editar/build mientras393b corre.

Goal completo activo en Goal-c03, HEAD 2bf3d4c. Preservar WIP, main y evidencia.
Sin agentes, commit/push ni Full durante reparación. BAXY está cerrado para uso manual.
16 mensajes directos y 742 registros de encuesta rev1248 consolidados; automáticos excluidos.
Encuesta original y servidor 101140 intactos. No hay modelos ni producto de diagnóstico activos
al verificar procesos tras 392. Registros 389–392 completados en sus RESULT.md y PINS.json.

## Fuente y validación vigentes

Última .NET: 379, cancelación conserva operación y target seguros tras retirar la invocación.
Seis suites dueñas: 1977 pass, 0 skips, 2m18s. Fast 17,86s de build, cero warnings/errors.
Última Python: 383, conserva borrador nativo sin llamadas/finish_reason=stop como initial_reply
local al turno de conversación; lo somete a las guardias y reintentos de chat. No caché nueva.
Focal 9 pass, 0 skips, 957 deselected, 1,32s; dueñas 1342 pass, 0 skips, 6,01s;
Fast 1,52s de build, cero warnings/errors. Sin edición fuente posterior a 383, sin Full.
Pins V8 actuales actualizados en 383; evidencia histórica intacta.

## Qué está demostrado y qué falla

Producto 380 anterior a 383: 6/10 útiles + 1 parcial + 1 silencio (antes 370: 4/10).
Cancelaciones ya nombran bien la operación y respetan idioma. T5 silencio, T7 eco,
T9 identidad del asistente en vez de persona, T10 confusión entre contexto y persistencia.
No se habilitó ni guardó memoria: journal status completed y dos save/recall fallidos.
381/382 diagnóstico y 384 fuente real: 4/5 frente a 3/5 previo. 385→386 panel fijo de 17:
13/17→14/17 útiles en contenido. Falla persistencia explícita (catálogo público excluye memory),
persona Álvaro tras cancelación y persona Eva interpretada como cuenta Windows. No aceptación fresca.

387 descripción más precisa de system.identity: 2/4→2/4, rechazada.
388 descarga 9B experimental con SHA verificado; registro del producto intacto.
389 9B/ngl14 con mmap detenido antes de respuestas por RAM libre <768 MiB; sin juicio de calidad.
390 mismo 9B/ngl14 sin mmap: 2/4, no mejora identidad. GPU 2918,316 MiB, RAM 3987,754 MiB,
sin violaciones; usa RAM adicional y no acredita voz simultánea. No adoptar 9B.
391 última frase del selector pide contestar directamente: 5/8→4/8; identidad no mejora
y el aire se vuelve contradictorio. Rechazado; no más variantes comparables de redacción.
392 resolvedor contextual existente: 5/10. Confunde nombre de tercero/hermano con usuario,
inventa guardado y sigue negando Álvaro por memoria deshabilitada. Rechazado como dueño general.

## Siguiente acción y límites del diseño

Corregir separación contexto conversacional / memoria persistida / cuenta Windows, midiendo
primero el dueño adecuado. No volver a ampliar el prompt del selector ni instalar un nombre
en caché global. No usar respuestas anteriores del asistente como prueba del nombre.
Inspeccionados: llm._compose_literal_recall_answer (5965) conserva un literal mediante [[R1]],
pero presupone referencia ya resuelta; no demuestra a quién pertenece. _resolve_contextual_answer
no comprueba la verdad; 392 demuestra el riesgo. NaturalMemoryRequestParser.TryBindSaveInput
extrae una declaración sólo para un guardado previamente solicitado; AskToSave NO trae operación.
No hay diseño nuevo adoptado ni script393 preparado al escribir este checkpoint.
Herencia revisada: biblioteca/gemma4-agent/documentacion/08_memoria_jarvis/research/2_memoria.md
1–75: separación de hechos y procedencia útil como hipótesis; sus porcentajes/propuestas no son
mediciones de BAXY actual. No añadir capas de memoria, embeddings o resúmenes sin necesidad medida.

## Pendiente del goal completo

Ocho rutas con voz propia e idioma correcto; fallos de sesión 264 y base de 742 (cero aceptados
individualmente en el candidato final); 100 humanos frescos, literales y con procedencia/contexto
congelados (cero certificados/congelados); averías aparte; UI real; voz física/ASR/wake y recursos
conjuntos <=4 GB; runtime/instalación y contratos C04–C09 sin ejecutar otros goals; Full final verde
y publicación fuera de main. Sin bloqueo externo ni cierre. No porcentaje o plazo inventado.
Historial detallado: CHECKPOINT_386_ANTES_392.md y RESULT/PINS de cada tramo.
