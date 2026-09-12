# REPAIR1042 — retroceso de historial, subset dirigido

Reparación propuesta externa atómica de effect_intent.py y __main__.py. No se aplica durante FILES1040 o CLARIFY1041. Root liga candidato después de adoptar ambos owners y completar la validación que corresponda. Esta preparación no ejecuta ni acredita.

## Material y precondiciones

13 casos, 26 líneas wire: dos literales exactos H0326/H0605 actualmente open, cinco variantes originales estructurales ES/EN y una reejecución fallida WEB1039-dev-10 y cinco límites: negación, cita, condicional diferido, pasado y página de PDF. Registro snapshot 156 covered, SHA en SEAL.json. Mantener los tres negativos y 18 sin marca globales como límites; filas originales en case-map.json, sin ejecutarlas de nuevo por esta preparación.

Preparación inicial única por root: pestaña CDP real con al menos 8 entradas anteriores disponibles. Snapshot inicial/final y journal por invocación. El provider back existente lee y verifica historial antes/después de cada acción y realiza postread; no requiere preparación externa por caso. session.new sólo separa conversación. Recibo inicial fresco readonly con endpoint, target_id, entry_count y current_index; root liga su hash al candidato. Los turnos sellados no contienen la preparación ni respuestas esperadas. Límites deben observar que no hubo retroceso web ni efectos adicionales. Página de documento no equivale a historial de navegador: una aclaración útil puede ser correcta.

Adjudicar contra terminales y recibos reales, sin plantillas ni traducciones. Crédito sólo para literal útil y fiel ejecutado con candidato actual y dos variantes pertinentes aprobadas. Root ya aprobó WEB1039 dev04/request42 y dev08/request65: ambos tienen back y CDP postread verificados; el presente contemporáneo es válido. Esos pares anteriores cuentan y no se reejecutan aquí. Las cinco variantes nuevas y la reejecución fallida acreditan generalización, nunca IDs de encuesta. Escribir verification_status al adjudicar, fallos individuales open con causa, sin repetir el panel entero.

## Revisión estática de seguridad

El primer borrador usaba _strip_request_envelope, que además de cortesías retira marcos de tarea, rectificaciones, frases de discurso y cierres sociales. Se revisó su código y _REQUEST_PREFIX. Para que el early return no dependa de toda esa gramática compartida, el helper final NO lo usa: _fold + fullmatch del acto completo, con prefijo/sufijo opcional por favor/please. Conserva negación, citas, condición, tiempo pasado, calificadores, órdenes adicionales y ámbito documental. No reconoce solicitudes compuestas, URLs ni cambio a otra pestaña. Las construcciones no reconocidas mantienen su vía previa, no se afirma que sean reparadas.

El early return ocurre después de explicit_non_action_frame y exige operación disponible y helper sobre texto ORIGINAL, no folded del envelope ni fragmento recortado. Sólo devuelve una operación y conserva evidencia original; límite de 16384 caracteres. _is_direct_request llama el mismo helper sobre su texto contextual existente pero no concede por sí solo argumentos ni ejecución; resolve y extracción vuelven a exigir la solicitud completa. No se usa un alias global back=anterior, IDs o lista de literales.

__main__ sólo conecta el parser para browser.control. None conserva abstención y fallback previo. El resultado action=back pasa el JSON Schema exacto como las otras identidades de parsers cerrados; no se permite un valor inventado ni se relaja catálogo/provider/autorización. La propuesta no incluye cambios de composición: presente contemporáneo útil + efecto observado pasa, sin penalización automática por tiempo verbal.

## Sello y ejecución

SEAL.json fija material, propuesta conjunta y owners originales. Es sello de material, NO sello de candidato ni autorización para ejecutar. Runner heredado de WEB1039 incluido: root debe fijar binarios/runtime/manifest y conservar todas las guardas (584/18/5, RAM 4000/768, GPU 3800, 900 s y timeout 120000). No lanzar el turns.jsonl sin recibo inicial fresco que verifique >=8 entradas anteriores. El historial observado por root fue índice 23/26 entradas; ese dato no sustituye la lectura inicial fresca. No se agrega infraestructura ni guión por caso. El PLAN público aún no existe al sellar; este PLAN privado es la propuesta completa revisable. Si root cambia textos o criterios debe crear sello nuevo antes de ejecutar.

Ambos textos Python propuestos pasan ast.parse; no imports de producto, pruebas, GPU ni ejecución del helper. Se revisó el diff completo de 100 líneas. Fuente, registro y repositorio intactos. Subset pendiente de adopción y medición.

Corrección de procedencia antes de ejecutar: el slot anteriormente llamado REPAIR1042-dev04 es literalmente web1039-dev-10. Se conserva su case_id original, texto exacto y origen; kind failed_variant_reexecution. REEXECUTION_SOURCE.json fija la fila original. Conteo: 2 literales, 5 variantes originales, 1 reejecución fallida y 5 límites; 13 casos/26 wire. No es material nuevo ni crédito de encuesta.
