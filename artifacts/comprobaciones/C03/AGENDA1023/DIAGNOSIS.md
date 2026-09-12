# Agenda1023 — cuatro literales, tres fronteras distintas

Lectura acotada de los cuatro turnos iniciales1021 y sus owners Python. Fuente comunicada20dab7ed sobre HEADd97670db; hashes efectivos abajo. Sin modificaciones ni pruebas/imports/build/HTTP/GPU. Herencia1006/1011: la frase visible no prueba por sí sola un defecto de prompt; distinguir contrato, extracción y composición.

| Literal | IDs observados | Primera pérdida observada y alcance |
|---|---|---|
| H0011, cancelar alarma sin selector | t1 / turn.decide8 | `explicit_clarification`, sin raw selector, fija notification.cancel.at. Pregunta comunicada por raíz: «¿A qué hora deseas cancelar la alarma?». El selector temporal de identidad se presenta como momento de cancelar. Un literal afectado. |
| H0121, aviso en30minutos | t3 / turn.decide26 / arguments27 | reminder.create reconocido explícitamente y conservado por todos los vetos; tras arguments.end aparece respuesta, sin Core. Se pierde la distinción tiempo ya expreso/contenido faltante en la frontera de argumentos. |
| H0343, aviso en una hora | t4 / turn.decide32 / arguments33 | Misma secuencia de reminder.create y aclaración desde argumentos, sin Core. Comparte con H0121 la frontera; dos literales. |
| H0043, tarea para viernes | t2 / turn.decide13 / arguments14 / plan15 | task.create sobrevive todos los vetos; shell seq53–54 registra llamada Core. El primer error verificable en los datos permitidos es `invalid_task`, ya presente al componer. El internal_code terminal comunicado por raíz NO está demostrado como rechazo del compositor Python. Un literal con dos incidencias por separar. |

## H0011: temporalidad de identidad frente a tiempo de ejecución

`effect_intent.py:3182–3209` reconoce cancelación sin reloj, sin selector latest y sin título exacto; para una alarma singular retorna `ClarificationIntent(("notification.cancel.at",), ("alarm_time",))`. El contrato selecciona una hora identificadora; no hay autorización para programar la cancelación a futuro ni cancelación enviada. `__main__.py:5855` usa `llm.formulate_explicit_clarification_question`; éste transmite recognized_operations/missing_information y solicita preguntar por esas claves (llm.py:9039–9118). La auditoría no guarda ese JSON ni su respuesta cruda: la selección y claves se reconstruyen inequívocamente por esta rama, pero no se atribuye el giro verbal a una supuesta plantilla del modelo.

Reanudación mínima: conservar el veto y la operación existente, hacer explícito que el dato solicitado identifica el objeto ya existente, no cuándo ejecutar. Usar el propósito/identidad de la aclaración existente; no sustituir por latest ni inventar una alarma. No se necesita provider nuevo. Corregir únicamente lenguaje sin conservar ese significado del selector sería insuficiente.

## H0121/H0343: pérdida compartida de información ya suministrada

Discrepancias estáticas concretas:
1. `effect_intent.py:2235–2256` `_time_only_reminder_request` sólo contempla sustantivo recordatorio/reminder con para/for. Su caller3170–3181 también exige ese sustantivo y ciertas cabezas. No reconoce avisame + duración sin contenido, aunque `_reminder_has_actionable_due:2259–2273` ya reconoce30minutos y una hora.
2. `__main__.py:4070–4101` `_explicit_relative_reminder_arguments` exige tanto duración como título; con sólo tiempo devuelve None. `arguments:8149–8166` continúa a `extract_direct_arguments`.
3. `llm.py:1098–1121` `_build_direct_argument_payload` ordena generar fallback para TODOS los required_fields. No dice sólo los que faltan. `extract_direct_arguments:9394–9400` valida la pregunta con TODOS esos campos; `prepare_direct_argument_result`, __main__.py:691–692, reutiliza el fallback si existe, incluso tras calcular campos pendientes. Esta es una causa de fuente compartida que favorece volver a preguntar el tiempo conocido.

Los cuatro logs no retienen los envelopes arguments27/33, sus argumentos parciales o requested_fields; por tanto no se afirma que el modelo extrajera mal la duración, ni qué bifurcación de rechazo recorrió. Sí está demostrado que no fue selectorunsupported, dominio ni composición posterior de resultado. La inversión de actor de la pregunta comunicada por raíz es otro defecto de la pregunta final, no una instrucción de actor invertido observada en el payload.

Reparación dirigida más pequeña: ampliar el reconocimiento temporal sin contenido reutilizando la gramática de duración existente y retornar la aclaración existente únicamente para title, conservando la duración original para la continuación. No convertir el tiempo en título ni inventar contenido/dueUTC. La corrección transversal del fallback debe preguntar por información realmente ausente, preservando lo aportado; no devolver argumentos parciales como ejecución autorizada ni eliminar grounding. Son alternativas de alcance diferente, no dos parches obligatorios. Dos literales potenciales aquí; los pares siguen pendientes de juicio raíz.

## H0043: invalid_task anterior; internal_code no localizado en Python

Composición t2: los registros error capturados, todos `stage:first`, `reason:""`, `published:true`, mismo draft «No se pudo crear la tarea. La causa es que la tarea es inválida.». Payload: outcome failed, reason causa invalid task/operation task.create. Situation: mission_failed, steps[], reason operation task.create, verified=false, succeeded=false, error invalid_task. También existe un status working publicado; ninguno de esos registros informa veto internal_code. Shell muestra nueva planificación tras el fallo Core, seguida de varias solicitudes message.compose; no demuestra qué validación externa cerró el terminal. `raw-replies` es de conversación y no permite reconstruir arguments14; no se vinculan sus respuestas ajenas a este caso.

El lector task.create (`__main__.py:4644–4679`) sólo deriva un título explícito con dos construcciones; para el texto recibido no lo obtiene y pasa a extracción nativa. Sin el resultado exacto de arguments14/Core no se puede afirmar qué título/fecha mandó ni cuál provocó invalid_task. Próxima lectura mínima, si raíz la autoriza: recibo privado de esa única invocación task.create y razón del validador App del terminal; ninguna repetición del efecto. No reparar llm.py internal_code a partir de un código final ausente de su propia auditoría ni afirmar que basta con un prompt.

## Evidencia y límites

Cuatro literales revisados, grupo compartido demostrado de dos (H0121/H0343); cancelaciónH0011 e invalid_task/composiciónH0043 son independientes. No adjudicación, parche ni crédito. Los fallos no justifican ampliar a toda agenda.
Hashes SHA256 de snapshot de run activo, bajo `C:/Users/usuario/AppData/Local/BAXY/C03-agenda1021-private/run/`:
- turn-audit.jsonl `bfbdfee3e266c09abfe117ff0c27900e15d8919dedb4d7590cb32e11d672000f`.
- raw-replies.jsonl `10e04a15d5064f6466b5392983d406f7413d307f2de9585452da948de43bc55e`.
- compose-audit.jsonl `e4a51e4ccccf04b1328d1c568df026d9f528fd051a54f779e04dc43e6d31e385`.
- shell-trace.jsonl `ff42049555c3e14c6471527e9914f5053401a15ba1d609cc60ecb7ace1b9023b`.
Selecciones estables: líneas JSON originales unidas por LF, UTF8 sin terminador final: audit request8/13/26/32,7líneas `574eec35cb2a716e71b26e3882a5fbd4e9a60f3fd2610c6c46deaff38b43fb93`; compose trace t1–t4,11líneas `c2caa6292e2eae0b10f844e7ca1fc91f3910b4d1e486e38e8c558c9ae3eb6c48`; shell id t1–t4,100líneas `717662817d4b9267502099eaea407d245fecee22f4e61adba1cd6241e454827f`.
Fuente leída en `src/baxy_mind/`: effect_intent.py `3bb83dc8f0c8736c86d402d0faf656915044a9089b8b27b9b9a430b36365cade`; __main__.py `6d4a5856d5fc8827d9024b3f38312679e15f2cf9bf00692a895137556a0279ba`; llm.py `b95557d9da12cd87fc33f08e8ccc881e22965c4c855ef79492edc8bc73ef5df0`.
