# C03 — tramo53: identidad previa a lectura de archivo

Estado: candidata Python en medición; no adoptada. Fuente52 anterior vigente.

## Evidencia y herencia

La captura wire-context47 ya mostraba selección de filesystem.read.text seguida
de una ruta truncada como resourceId y pregunta por la ruta que ya estaba dada.
Inspección del consumidor52: ReadText sólo revalida handles propios del
LocalFilesystemProvider configurado con dataRoot/filesystem-sandbox. No acepta
IDs de la búsqueda de carpetas conocidas ni rutas absolutas como identidad.

La herencia Carter_v5 filesystem-workflow, biblioteca/carter/carter_v5/skills/
filesystem-workflow/SKILL.md:23–44, separaba búsqueda y lectura, y advertía que
una búsqueda vacía no demuestra inexistencia global. Se hereda esa relación;
no sus herramientas genéricas ni crear un archivo ausente sin haberlo pedido.
Registro de mantenibilidad:5790–5804 probaba que «lee el contenido del archivo
notas.txt» conserva autoridad semántica, pero no probaba identidad ni lectura
extremo a extremo. El hueco no está en el selector nativo ni necesita otro prompt.

apply_turn_action_grounding_gate ya difiere al plan las identidades de operaciones
con required_predecessors. read.text faltaba en ese registro y en _IDENTITY_CONSUMERS,
aunque el shortlist añadía filesystem.list. La candidata añade search/list como
productores alternativos, prefiriendo búsqueda por nombre y refrescando identidad
para lecturas posteriores. Reutiliza un listado ya pedido si existe. El shortlist
añade search sólo cuando no hay ninguno de esos productores; backup conserva list.
No se crea ninguna operación, parser de rutas, proveedor ni catálogo paralelo.

## Base reproducida

astra-files53-baseline: cinco controles técnicos, fixtures/hash/perfil en CASES.
Uno UTF8 legible, uno inválido y un nombre duplicado dentro/fuera del sandbox.
La petición exterior conserva una ruta absoluta: devolver el archivo interior
sería un fallo de identidad, aunque su lectura sea real. Se reutiliza ausente47
literal y se termina con una lectura de hora como recuperación.
Ninguna petición de escritura; los fixtures fueron preparados por el instrumento
y no pertenecen a la reserva humana ni a los archivos del dueño.

Base fuente52: **1/5 útil**, sólo la hora. Los otros cuatro turnos repiden ruta
o un ID interno, incluso con archivo válido del sandbox.68,09s,GPU3497,56MiB,
RAM5328,06MiB,registro intacto,sesión37225 exit0. paired.json contiene los literales.

## Validación de candidata

Cuatro pruebas nuevas fallaron antes de editar: diferir identidad primaria y
recuperada sin extractor, búsqueda/refresco por archivo, y dependencia de listado
ya pedido. Tras corregir pasan; el test derivado de todos los consumidores añade
también la nueva relación. Diez suites pytest: **3128 pass,115 subtests,0 skips,
45,51s**, sesión13966 exit0, log c03-files53-owners.log. No se relajó ningún control.

Producto astra-files53-candidate terminó exit0:76,06s,GPU3497,56MiB,
RAM5197,95MiB,registro intacto. **1/5 útil**, sólo la hora; no mejora respecto
a la base. t1/t4 publican «No pude leer el archivo porque el plan está incompleto»;
t2/t3 composition_failed. No se llegó a comprobar lectura/UTF8/sustitución.
RESULT.json y paired.json conservan la evidencia; no quedan Baxy/llama-server.

El contrato C# estaba incompleto: MissionPlanValidator.RequiredPredecessorOperations
omite read.text y MindSidecarClient.ValidateExpectedPlanResult compara la secuencia
Python con ese registro. Rechaza search/read como si añadiera un efecto ajeno;
DependencyAuthorityFields también omite resourceId. La candidata sólo Python no
se adopta. Se prueba el contrato compartido antes de repetir producto.

Además, la composición rechaza «No se pudo leer...» y «La causa del fallo...»
como missing_failure, y el nombre literal c03-lectura.txt como internal_code en
progreso. Son fallos observados, pendientes de reparación; publicar otro error
interno no convertiría las peticiones normales en respuestas útiles.
No Fast53/Full, UI, audio ni reserva100 aún. No usar path.ensure.absent: puede borrar.

## Contrato compartido y resultado

Dos nuevas pruebas de frontera fallaron antes de corregir C#:2fail/0pass/0skips,
56ms, log c03-files53-boundary-red.log. Se añadió la misma pareja search/list
al registro requerido de MissionPlanValidator y resourceId al campo de autoridad.
No se admite known.search como productor. El primer fixture unitario nuevo
usaba argumentos title inválidos para search/list: se corrigió el fixture según
los schemas, sin cambiar producto ni relajar validación.

Kernel MissionPlanValidatorTests:12pass/0skips/48ms; integración
PlannerAppBoundaryTests+MindPlanSessionTests:88pass/0skips/4s. Sesión60933 exit0,
logs c03-files53-kernel-fixed.log/c03-files53-boundary.log. La comparación
astra-files53-boundary terminó87,12s,GPU3497,56MiB,RAM5381,73MiB,registro intacto,
sesión34806 exit0. Continúa **1/5 respuestas útiles**, pero ahora t2 ejecuta
search/read con identidad verificada y el borrador contiene el texto correcto.
El veto internal_code por el nombre literal impide publicarlo; es una primera
transformación errónea distinta, localizada en compose_visible_defect y C#.
t1/t4 sólo dicen resultado no verificado; t3 sigue sin prosa final. No se afirma
que esos límites/averías estén resueltos ni que el control de scope esté aprobado.

Se conserva el contrato como candidata integrada pendiente del veto de literales
del tramo54. No cambiar modelo ni añadir otra búsqueda por nombre para desplazar
el síntoma. No Full hasta resolver todas las conductas de C03.
