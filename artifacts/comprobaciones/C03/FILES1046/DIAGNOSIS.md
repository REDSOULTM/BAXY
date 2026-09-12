# FILES1046 — dos bloqueos independientes, propuesta externa

Se leyó ROOT_ADJUDICATION de REPAIR1043: 7pass,5fail,3insufficient_evidence,0créditos. Herencia inmediata: FILES1040 y reparación1043 reutilizan filesystem.known.search existente; no se propone infraestructura nueva, fixtures ni búsqueda auxiliar del disco. Sólo se inspeccionaron fuente dueña y traces t2/t4.

## Primera pérdida observada

H0696/t2: operación verified=true/succeeded=true, count0, files[] y authority windows_known_folders_bounded_postread. Primer raw: «No encontré el archivo presupuesto.xlsx en las carpetas que revisé.» Retry: «No se encontró ningún archivo llamado presupuesto.xlsx en las carpetas buscadas.» Ambos fueron rechazados asserted_failure repetidamente y no hubo respuesta final. No falló la búsqueda: el fullmatch de llm.py:4741–4757 exige una oración completa con unas formulaciones de ámbito y determinantes. La relativa «que revisé» y el cuantificador «ningún» no entran. El blanco de reparación es la distinción entre hallazgo negativo y fallo de ejecución, no una ampliación de frases completas permitidas.

T4 es diferente: count5, con cinco resultados cuyo nombre es MERGE_CHECKLIST.md o RELEASE_CHECKLIST.md, ninguno exactamente checklist.md. Primer borrador combina ausencia del nombre exacto con coincidencias próximas; retry sólo afirma ausencia; otro borrador describe cinco relacionados y ninguna coincidencia exacta y cae como invented. No es resultado vacío, por lo que la excepción propuesta no lo modifica. Ausencia exacta dentro de los resultados devueltos no prueba ausencia en toda la raíz, ni que los resultados sean «los más cercanos»: MatchesQuery usa substring, no ranking de similitud. No extender la excepción vacía a count>0 para hacer pasar t4.

EVIDENCE.json conserva raws distintos por trace/hash/reason, con query/count y nombres deduplicados; evita catálogos y repeticiones masivas. Mantiene adjudicación histórica sin reescribirla.

## Propuesta mínima de presentación — llm.py

DIFF.patch sustituye la whitelist de oración completa por una proyección de predicado: sólo con _verified_empty_known_file_query válido se retira del texto inspeccionado por _asserts_failure un predicado negativo de encontrar ligado a la query observada exacta. Son componentes gramaticales generales de negación/verbo/objeto, sin IDs, nombres de archivo concretos ni lista de oraciones. La forma relativa del ámbito queda libre porque el detector de fallo no es el dueño de verificar ese ámbito.

El resto de la respuesta permanece en failure_assertions: «no pude buscar», «no respondió», «falló», una segunda acción fallida o permisos no se borran por acompañar un hallazgo vacío. Todos los demás validadores reciben el texto ORIGINAL y hechos originales. No se borra toda la respuesta ni se devuelve éxito anticipado. Tampoco se toca el helper de recibo vacío, otros providers, casos de fracaso real o count>0.

Reserva: al dejar de exigir un ámbito textual predefinido, la verificación semántica/general de fidelidad sigue siendo responsable de rechazar una ausencia global no demostrada. El campo de ámbito propuesto aporta los hechos faltantes; la mejora de esa fidelidad debe observarse, no deducirse del diff. Revisión necesaria con hallazgo vacío fiel, fallo mezclado, archivo distinto y extrapolación global antes de adoptar; no se creó panel ni se ejecutaron tests aquí.

## Propuesta de alcance observado — WindowsKnownFileAdapter.cs

Hoy Search devuelve query/count/files/authority. Con files=[] desaparecen las etiquetas de carpeta del recibo: el texto de usuario no acredita dónde se buscó. Esa falta afecta las variantes t6 Desktop, t9 Documents y t10 Downloads, que raíz dejó insufficient_evidence. No se convierten en pasadas retrospectivamente.

El diff agrega un único objeto searchScope al resultado existente, sin operación nueva:

- enumerationRoots: pares folder/path registrados cuando la raíz efectiva pasó Directory.Exists y se inicia su enumeración. Usa las raíces ya resueltas por Roots/SubdirectoryRoots; no las infiere del usuario ni enumera sólo la configuración. Una raíz inexistente no aparece.
- maxRecursionDepth12, ignoreInaccessible=true y skipReparsePoints=true: límites efectivos actuales del enumerador.
- resultLimit y resultsMayBeTruncated=(count==limit): aviso conservador; igualdad significa posibilidad, no prueba de truncamiento.
- exhaustive=false: nunca afirmar que se recorrió todo el disco o toda carpeta accesible. IgnoreInaccessible puede omitir descendientes sin contar/reportar errores; depth12 y reparse excluyen partes. enumerationRoots significa raíz de intento completado bajo esos límites, NO prueba de acceso exhaustivo ni ausencia de omisiones.

El OrderBy actual materializa la enumeración antes de Take; si lanza excepción no se produce este recibo success. Una raíz que exista pero resulte inaccesible con IgnoreInaccessible puede quedar en enumerationRoots: por eso su nombre es ámbito de enumeración intentada, no carpeta íntegramente leída. No afirmar que se leyó su contenido. El campo basta para establecer destino efectivo intentado bajo límites y permite un negativo honesto dentro del ámbito observado; no certifica ausencia total.

Paths permanecen en la evidencia privada local, no se publican en checkpoint. El cambio no añade otro recorrido ni cambia resultados, orden, límite o matching. Duplicates/Trash conservan el mismo Enumerate con parámetro opcional null. El resultado v1 sólo se amplía con datos observados; root debe comprobar que recibo→situation.observed→payload.seen conserva searchScope durante la medición. Aquí no se afirma ese transporte ya verificado.

## Alcance y entrega

Dos owners de fuente propuestos, ambos externos. H0696 tiene bloqueo de redacción directamente demostrado; H0001 permanece literal pasado pendiente de pares. Tres variantes tienen bloqueo de evidencia de ámbito. No sumar esos tres como requisitos ni prometer créditos. T4, internal_code t5 y fallo de interpretación t7 no quedan reparados por esta propuesta.

Ficheros DIFF.patch, llm.py.PROPOSAL, WindowsKnownFileAdapter.cs.PROPOSAL, EVIDENCE.json e IDENTITY.json en esta carpeta. Revisión textual completa del diff. Sin fuente canónica, tests, imports de producto, AST, build, GPU, registro, adjudicación o panel. Root decide siguiente subset y adopción después de terminar la tanda activa.
