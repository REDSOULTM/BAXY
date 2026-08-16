# Cuarto corte productivo: desambiguación durable de notas

Estado del corte: implementado y verificado en `fa08653`. Cierra el P2
conocido de selección conversacional entre títulos duplicados, pero no cierra
ningún Must adicional ni los bloqueantes B-004/B-005/B-006. No añade voz,
conversación general, composición multioperación, instalador ni aceptación
física.

## Alcance exacto

Cuando `note.read`, `note.trash` o `note.restore` encuentran varias notas con
el mismo título, la GUI ya no termina en un error sin salida ni elige una nota
silenciosamente. Presenta una lista acotada y permite seleccionar una candidata
mediante gramáticas contextuales en español, inglés y spanglish.

La desambiguación tiene dos fases explícitas:

1. La operación original por título devuelve `note_ambiguous` sin efecto y con
   un snapshot ordenado de candidatas. Esa petición original permanece durable
   en el outbox mientras la elección no se resuelva.
2. La elección sustituye atómicamente la petición original por otra ligada a la
   candidata exacta. Conserva el mismo `missionId`, crea un nuevo
   `invocationId` y persiste la sustitución antes de enviar al core.

La interfaz no muestra UUID ni JSON. Cada opción expone número absoluto, estado,
hora de actualización y una vista previa del contenido. Las páginas contienen
cinco opciones y conservan numeración absoluta entre 1 y 512, de modo que
avanzar o retroceder no cambia la identidad de una opción.

## Snapshot y frontera de protocolo

El provider captura las candidatas bajo el mismo lock del store y las ordena
por `updatedAtUtc` descendente, con UUID ascendente como desempate estable. El
snapshot admite como máximo las 512 notas permitidas por el store. Cada vista
previa colapsa espacios y se limita a 128 bytes UTF-8 sin cortar una runa.

El resultado estructurado de `note_ambiguous` transporta por candidata el UUID,
la vista previa, fechas, revisión y estado; no repite el título en cada fila.
El journal conserva también este resultado de fallo, por lo que repetir la
misma invocación reconstruye el mismo shortlist en vez de consultar una lista
nueva y potencialmente distinta.

Una regresión adversarial serializa las 512 candidatas con vistas previas
hostiles y comprueba que la respuesta completa queda por debajo de 700.000
bytes y del límite de protocolo de 1 MiB. Esto acredita el máximo automatizado
de este corte; no amplía los límites generales de la frontera JSONL.

## Grounding y control de concurrencia

La segunda fase no reinterpreta el número elegido como una posición mutable.
Envía una selección ligada a:

- UUID canónico;
- título esperado normalizado en Unicode Form C y comparado con
  `OrdinalIgnoreCase`;
- revisión esperada;
- estado de ciclo de vida esperado.

El provider vuelve a validar esa tupla y ejecuta lectura o mutación bajo el lock
del store. Si la nota cambió, desapareció o ya no pertenece al estado esperado,
responde `note_selection_stale` sin efecto. Una lectura seleccionada tampoco
divulga contenido si la candidata está en la papelera. Papelera y restauración
solo actúan sobre el UUID exacto que eligió el usuario.

Este control es optimista y deliberadamente fail-closed: el snapshot sirve para
explicar opciones, pero nunca autoriza por sí solo una mutación posterior.

## Outbox, reinicio y replay

Antes de elegir, un reinicio del shell recupera la operación original por
título y pide continuar. Al reenviarla con la misma identidad, el replay del
journal devuelve el snapshot exacto ya registrado.

Después de elegir, el outbox contiene la ruta exacta por UUID y su binding, no
el ordinal textual. Si el shell o el core se interrumpen antes de una respuesta
terminal, la GUI recupera esa petición y pide continuar; no vuelve a interpretar
`primera`, `2` ni otra posición contra una lista distinta.

Cancelar resuelve y elimina durablemente la petición original antes de informar
la cancelación. Una orden natural completa y no relacionada puede sustituir la
desambiguación pendiente de forma atómica y empezar una misión nueva. Si ya hay
una selección enviada con resultado incierto, la interfaz conserva esa identidad
y restringe la recuperación a continuar el mismo intento.

## Parser contextual y accesibilidad

El parser de selección solo se activa mientras existe una aclaración. Acepta
números y ordinales acotados como `1`, `la opción 2`, `choose la 3`,
`la primera`, `the second one` o `elige el tercero`, además de navegación,
cancelación y continuación en español/inglés. Rechaza cero, posiciones fuera de
1–512, signos, decimales, selecciones múltiples, controles y UTF-16 malformado.
Un número aislado nunca se convierte en una orden natural global.

El prompt y sus recuperaciones usan el mismo evento de mensajes y la región
viva de la GUI, y su cuerpo se publica también como `AccessibleText`. Esta es
evidencia automatizada de la frontera de accesibilidad; no sustituye pruebas
físicas con Narrator/NVDA, teclado real o DPI al 200 %.

## Evidencia ejecutada

| Evidencia | Resultado |
|---|---:|
| Contratos .NET | 23/23 |
| Kernel .NET | 27/27 |
| Provider Windows .NET | 64/64 |
| Integración .NET | 261/261 |
| Total .NET Release | 375/375 |
| Python canónico | 59/59 + 148 subtests |
| Corpus específico | 36/36 + 54 subtests |
| Total conjunto principal | 434/434 |
| Formato/diff | limpio |

Las regresiones atraviesan provider, core y ViewModel para lectura, papelera y
restauración de duplicados; comprueban que solo cambia la candidata elegida,
que no se filtran UUID/JSON, que el outbox termina vacío y que snapshots o
selecciones sobreviven a reinicios. También cubren candidatos stale por cambios
externos, replay de resultados fallidos, paginación hasta la opción 512,
normalización Unicode, casing, sustitución durable atómica y fallo antes del
commit del outbox.

La auditoría adversarial final no encontró P0/P1. Durante el corte se corrigió
el riesgo de exceder la línea JSONL al repetir títulos por candidata, y se
endurecieron casing/Form C y UTF-16 malformado antes de cerrar el red-team.

Los artefactos protegidos permanecieron byte a byte intactos:

- `artifacts/corpus_cutoff/source_manifest.json`:
  `9da873e4b30dd81d1cc85d6e9bf4b19fb13aa96e8fcc5ce3b1f8265012ca59b0`;
- `scripts/freeze_historical_sources.py`:
  `27acb6ccc34b6820ab8614a19d41409645aabeb151803bfec4d34843e6c4ae5c`;
- `artifacts/technology_tournament/protocol.json`:
  `383a9e54cfc5a186de61f060aeb2a6cd013bab3ec21bdeb387063d935d99a892`.

## Límites y deuda explícita

- La reconciliación de trash/restore tras una interrupción entre efecto y
  completion usa la aproximación estricta `revisión esperada + 1` más UUID,
  título y estado objetivo. Todavía no existe un recibo persistente de mutación
  con schema v2 que pruebe causalidad por invocación; cualquier desviación falla
  como stale y no ejecuta otro efecto.
- Las notas y el outbox siguen en texto plano, sin cifrado ni HMAC. El journal
  encadena SHA-256, pero tampoco acredita autenticidad adversarial.
- No existe operación de renombrado, voz, conversación general, composición
  multioperación ni memoria completa.
- El build distribuible del segundo corte no fue regenerado; sigue siendo un
  directorio de desarrollo, no un instalador MSI/MSIX ni una instalación
  validada en Windows limpio.
- No hay nueva evidencia física de Narrator/NVDA, DPI al 200 %, equipo con GPU
  de 4 GB, VM limpia ni gates completos de `app.open`.
- El progreso permanece en 5/15 Must (33,3 %). Este corte reduce B-004, pero
  B-004/B-005/B-006 continúan abiertos.
