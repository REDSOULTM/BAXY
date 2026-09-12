# REPAIR1036 — diagnóstico estático de variantes de apertura

No hay una regresión nueva demostrada de anterioridad/reapertura en estos cinco fallos. Los cuatro desarrollos de apertura nunca llegaron a una operación app.open exitosa ni a su composición posterior. Comparten pérdida de la intención antes de ejecutar, con causas diferentes. Arreglarlas amplía el alcance original1036: son fallos de reconocimiento, selección y autoridad, no de los tres filtros corregidos.

Se leyeron primero HUECO_LEXICO_APPS.md y CUELLO_DE_BOTELLA_RECONOCEDOR.md. Su historial descarta repetir sólo extensiones de la cabeza verbal: dieron delta0. La afirmación histórica de «triplicar probabilidad» es correlación observada, no un efecto causal demostrado aplicable a cada petición.

## Evidencia fresca

Fuente: C03-repair1036-private/run/{turn-audit,compose-audit,raw-replies}.jsonl y case-observations.json. Identificadores de decisión locales, no IDs de invocación del kernel.

| Caso | request_id | Ruta observada y final |
|---|---:|---|
| dev01, «Me abrís Paint para dibujar un momento» |15| model/lexical; app.open ausente de las28 candidatas; propone office.document.create; domain_grounding retira la operación; termina diciendo que no puede abrir Paint ni dibujar. Compose t2 recibe failure/out_of_catalog. |
| dev02, «Open Paint; if it is already running, just use the existing window.» |21| explicit_clarification antes del modelo; intent_operations app.open pero ningún efecto. Final «What application should I open?». |
| dev03, «Poné la calculadora a mano sin abrir otra instancia si ya está abierta.» |26| model/lexical; app.open ausente; propone window.application.status dos veces. Ambas fallan compound_conservation, apply_compound_effect_conservation_veto:1873. Recovery sin efecto; compose t4 recibe turn_contract_failure/operationAttempted=false. |
| dev04, «Could you open Calculator for me?» |32| model/lexical con app.open; identidad fresca resuelve windows.calculator, catálogo completo293 entradas. Aun así domain_grounding lo convierte en unsupported, domain_confirmation en aclaración. Compose t5 pregunta tipo de calculadora, aunque la identidad ya estaba resuelta. |
| boundary01, «No abras Paint; sólo decime si podrías hacerlo.» |59| model/lexical propone app.installed; dos rechazos compound_conservation:1873; recovery turn_contract_failure. Compose t10 produce primero reversed_result y después missing_failure en cada ciclo; no publica respuesta, termina no_response/recovery/retry_exhausted. |

Las negaciones y citas restantes de1036 no autorizan abrir por coincidir un nombre. No debe repararse boundary01 quitando la conservación de efectos ni admitiendo app.installed sólo porque lo propuso el modelo.

## Dueños y causas concretas

1. effect_intent.py:7845 `_is_direct_request` y:13910 `resolve_explicit_effects`: el guardia anterior exige una cabeza del vocabulario. La expresión:7934 usa `_REQUEST_PREFIX` seguido de request_head; no admite el clítico inicial «me» de dev01. `_OPEN`:6923 tampoco incluye abrís. `_application_open_request`:3570 y `_indexed_authenticated_application_target`:3480 repiten gramáticas. Añadir abrís al matcher inferior deja vivo el rechazo superior; ésta explica por lectura la causa que el historial dejó por rastrear. No ejecuté una sonda nueva para atribuir una línea recorrida exacta.

2. effect_intent.py:3010–3033 `resolve_explicit_clarification_intent`: basta una cabeza open y encontrar «window» en cualquier parte; evita la aclaración sólo si aparece `_KNOWN_APPLICATION`. Esa lista:6903 no contiene Paint. No consulta el catálogo autenticado aquí. Por eso la condición adicional sobre reutilizar la ventana puede secuestrar una apertura cuyo destino está escrito. __main__.py:5820–5840 evalúa esa aclaración antes de `resolve_explicit_effects`:5950. La reparación no es añadir Paint a la lista fija: evitar que una referencia secundaria a ventana anule una identidad autenticada o limitar la regla de objeto genérico a la petición completa.

3. effect_intent.py:1050 `_curated_domain_is_grounded(app.open)` acepta exactos del catálogo, deseos exactos o `_open_application_spans`. Este último:12443 acepta cortesía final por favor/please/ahora/now, pero no «for me»; `_application_target_forms`:3424 sí elimina «for me» mediante `_APPLICATION_TRAILING_REQUEST`:3418. La resolución final de identidad además conoce aliases. Así una misma petición tiene identidad windows.calculator en el audit, pero la puerta de dominio vuelve a rechazarla por una representación léxica más estrecha. Ésta es inconsistencia observada, no una conjetura sobre temperatura. __main__.py:6320–6421 lleva el retiro a domain_confirmation en lugar de usar el recibo de identidad de ese mismo objetivo. La pregunta final inventa ambigüedad.

4. dev03 y boundary01 tienen contratos compuestos no conservados, según auditoría. __main__.py:1806–1873 conserva las cláusulas y sólo autoriza si cada asignación está fundamentada/compatible; su rechazo impide ejecutar una lectura distinta de la intención. Sin observar el contrato completo ni trazar su constructor, no atribuyo el fallo a un patrón particular. Hace falta distinguir una restricción sobre la misma apertura (no duplicar) de otro efecto, y una prohibición con consulta de capacidad de una orden de lectura instalada. Es más alcance que arreglar cortesía.

5. __main__.py:6078–6106: reconocedor válido fuerza sus operaciones en shortlist; sin él usa `planner_catalog.shortlist(routing_objective)`. El audit muestra recuperación lexical y ausencia de app.open en dev01/dev03. No hay evidencia de fallo nuevo del proceso router ni motivo para cambiar encoder/proveedor: la caída al modelo y las candidatas efectivas están visibles.

## Reparación mínima candidata y masa

Primero una corrección dentro de mecanismos existentes, no infraestructura: hacer coherente el reconocimiento de apertura simple y su dominio con el mismo destino autenticado/alias y las mismas formas de cortesía. Conservar objetivo completo, negaciones, cita, condición y autorización; no autorizar por mera aparición de nombre. Priorizar dev04: ya tiene petición directa e identidad única; ningún provider nuevo ni catálogo ampliado hace falta. No usar «ya resuelto» como permiso global para ignorar un veto de seguridad.

Para aportar varios literales abiertos, ampliar de forma conjunta y acotada la cabeza autorizante y la gramática ordinaria a clítico+verbo, y compartir cortesía final reconocida por identidad/dominio. Historial identifica H0730 («me abrís la calculadora»), H0348 («abrime la calculadora dale») y H0487 («Abre steam pls») como tres candidatos concretos; H0165 requiere además tolerancia de errata y debe separarse. No afirmo que un patch todavía inexistente desbloquee esos tres: su predicción exige comprobación posterior y producto. Es trabajo de mecanismo existente; masa conocida3, no justifica infraestructura nueva ni un catálogo/motor nuevo.

No meter dev02/dev03/boundary01 en una ampliación de sufijos que corte texto arbitrariamente: las condiciones contienen restricciones ejecutables. Resolverlos con conservación del objetivo exige su propio alcance dirigido. Para1036 ahora se conserva H0575 abierto por faltar dos variantes pertinentes, aun si su literal pasó; las cuatro variantes de mayúsculas no acreditan app.open.

## Límites de este diagnóstico

Una iteración sólo lectura. Sin editar fuente, importar producto, ejecutar sondas, suites, GPU, build ni commit. No hay línea base contemporánea de estos mismos cinco textos antes del candidato1036: fallos actuales y semejanza histórica no demuestran regresión causada por1036. Las guardas anteriores/reapertura corregidas ni siquiera fueron ejercitadas por las cuatro aperturas fallidas. No reetiquetar los fallos ni repetir el panel completo.
