# Rotación del journal de invocaciones

Código: `src/Baxy.Kernel/Journal/FileInvocationJournal.cs`. Tests: `tests/Baxy.Kernel.Tests/FileInvocationJournalRotationTests.cs`.

## Por qué

El 2026-10-07 el journal del perfil de prueba de computer use (`journal/missions.jsonl`) llegó a 65 MB. El tope es
de 64 MiB y cada escritura reserva 2 MiB, así que desde ese momento el Core rechazó toda operación y BAXY quedó
inservible. La compactación no lo evitaba: guarda el último estado de cada invocación y nunca descarta una
completada, porque esa completada es la que permite el replay idempotente. Un usuario real llega al mismo punto
usando BAXY lo suficiente.

## Qué hace

- **Umbral.** La rotación empieza cuando el segmento vivo pasa el 75 % del tope (48 MiB). Se revisa al abrir el
  journal y antes de asentar el inicio de cada invocación, y sólo si en el segmento vivo hay alguna invocación
  completada.
- **Sellado.** El segmento vivo pasa a llamarse `missions.<n>.jsonl` y queda junto a su ancla
  `missions.<n>.jsonl.anchor`. Esa ancla tiene la fase `archived`, el número `segment` y la posición final
  autenticada (secuencia, último tag y largo), además de un enlace `archive` al segmento archivado anterior. El
  número `n` es siempre mayor que cualquier segmento que haya en disco o que el manifiesto conozca, así que un
  archivado sólo puede enlazar a uno de número menor (no necesariamente el inmediato: un reinicio deja huecos).
- **Segmento nuevo.** El segmento vivo nuevo empieza con las invocaciones incompletas trasladadas como `started`, en
  una cadena HMAC nueva. Así ningún registro en curso se pierde y su reserva de cierre sigue valiendo.
- **Manifiesto.** El estado de la rotación vive en `missions.jsonl.segments`, un archivo propio autenticado con HMAC
  en otro dominio (`baxy.journal.segments.v1`): la lista de archivados retenidos (el más nuevo primero, cada uno con
  su posición sellada), el `floor` (el número más alto que dejó un reinicio), los podados cuyo borrado está
  pendiente, el estado autenticado de los ids retirados y, mientras una rotación está en curso, su intención.
- **Formato y vuelta atrás.** La versión del journal sigue en 2, los registros no cambian y **el ancla viva nunca
  lleva campos nuevos**: tiene exactamente los bytes del formato anterior a la rotación. Un Core anterior a este
  cambio (por ejemplo tras `setup --rollback`) abre el segmento vivo sin error y sólo pierde lo que no conoce: el
  replay de los archivados y los ids retirados. Un journal que nunca rotó no tiene manifiesto ni retirados.

## Orden durable y recuperación

1. Se escribe el candidato `missions.jsonl.rotating` con las incompletas y se verifica de punta a punta.
2. Se escribe el ancla del archivado (`missions.<n>.jsonl.anchor`).
3. Se escribe el manifiesto en la fase `rotation_pending`, con la intención: el enlace nuevo (`n` y la posición
   sellada) y la posición `next` del candidato. Desde aquí la rotación siempre se completa.
4. Se renombra `missions.jsonl` a `missions.<n>.jsonl`.
5. Se renombra el candidato a `missions.jsonl`.
6. Se escribe el ancla viva (`committed`, en `next`, formato anterior).
7. Se escribe el manifiesto en la fase `committed`, con el enlace nuevo delante de los retenidos.

Si el corte ocurre antes del paso 3, el ancla viva sigue apuntando al segmento sellado y éste sigue siendo el vivo.
El candidato y el ancla de archivado sobrantes (sin segmento, por encima de todo lo conocido) se borran al abrir. Si
ocurre después, la apertura completa los renombres antes de abrir el flujo y sólo acepta lo que prueban los largos
autenticados; luego lleva el ancla viva de la posición sellada a `next` (o comprueba que ya esté en `next`) y asienta
el manifiesto. Los tests cortan en cada etapa (`JournalCommitStage.Rotation*`).

Si otro proceso tiene abierto el archivo vivo sin compartir el borrado (por ejemplo un script que lo lee), el
renombre se reintenta durante unos 2 s. Si sigue fallando, la intención se revierte (el manifiesto vuelve al estado
anterior y el ancla viva nunca cambió) y la rotación se reintenta en la escritura siguiente. Mientras tanto siguen
valiendo la compactación y el tope duro.

**Una rotación pospuesta nunca es silenciosa.** Cada una se cuenta (`RotationPostponements`, con la causa en
`LastRotationPostponement`) y se informa por el callback de diagnóstico: el Core la escribe en su stderr («BAXY core:
Journal rotation postponed (…)»), que la App guarda en sus diagnósticos. Se informa la primera y luego una de cada
64, para que un journal que va hacia el tope se vea antes de llegar a él.

## Validación de los archivados

Al abrir, el manifiesto se autentica (HMAC, bytes canónicos, forma) y los segmentos archivados que lista se
autentican enteros, del más nuevo al más viejo, la primera vez que se abren sellados. Para cada uno se comprueba:

- el ancla: fase, número y posición iguales al enlace del manifiesto, y su enlace `archive` igual al siguiente
  retenido más viejo;
- la cadena HMAC, los bytes canónicos y el largo exacto;
- que sus incompletas aparezcan, con la misma huella, en el segmento siguiente.

Además, todo `missions.<k>.jsonl` en disco con `k` mayor que el `floor` tiene que estar en el manifiesto (retenido o
podado pendiente), y si hay segmentos archivados el manifiesto tiene que existir. Así un manifiesto borrado o
reemplazado por uno anterior auténtico se detecta.

**Índice de los sellados (2026-10-09).** Un sellado no cambia, así que el resultado de esa validación entera (sus
completadas y sus incompletas, con su huella) se guarda en `missions.<k>.jsonl.index`, autenticado con la misma clave
(dominio `baxy.journal.segment.index.v1`) y atado al número del segmento, a la posición sellada del enlace (cuyo
`lastTag` cierra su cadena HMAC), a su largo y a su hora de escritura. Las aperturas siguientes usan el índice en vez
de releer hasta 48 MiB por segmento; si algo de eso no coincide (otra clave, otro largo, otra hora, otra posición, un
índice manipulado o ausente) el segmento se valida entero otra vez y el índice se rehace. El índice sólo recuerda una
validación que ya pasó: una respuesta archivada se sigue leyendo del segmento, que se autentica entero antes de
confiar en ella, así que un byte cambiado dejando la misma hora se detecta en la siguiente lectura de ese segmento
y la operación no se acepta. Medido con un journal sintético de 75,5 MB (23,4 MB vivos): apertura validando los
sellados 950 ms en caliente (5,4 s en frío), con su índice 194 ms. El índice se borra con su segmento al podarlo.

**El saludo no espera la validación entera.** El Core abre el journal en paralelo con la lectura del catálogo y el
saludo lo espera como mucho `CoreStartupBudget.HelloJournalWait` (6 s) desde el arranque: un journal que falla antes
para el Core sin saludo, como siempre; uno que sigue validándose deja salir el saludo y el Core no lee ninguna
solicitud hasta que la validación termina (si falla, sale con 74 sin ejecutar nada). Medido el 2026-10-09: con 33 MB
vivos y 50 MB sellados el saludo tardaba 7,5 / 14,1 / 19,5 s con la máquina cargada y el App lo daba por perdido a
los 10 s.

Cualquier manipulación da `JournalIntegrityException` y nunca se acepta una operación sobre ella. Cuándo se detecta
depende de qué se tocó: el segmento vivo, el manifiesto, las anclas, los ids retirados o un sellado con otro largo u
otra hora se detectan al abrir y el Core no arranca; un índice que no coincide sólo fuerza la validación entera del
sellado (y si éste está manipulado, tampoco arranca); un sellado manipulado con el largo y la hora repuestos se
detecta al leer una respuesta archivada suya, y esa operación se rechaza (el Core sale con 74). Los
casos probados son: un byte cambiado, un registro truncado, el archivado borrado, el ancla del archivado borrada, el
ancla del archivado copiada como viva, el ancla viva copiada como archivada, el manifiesto borrado, el manifiesto
modificado, un manifiesto anterior repuesto y el archivo de ids retirados modificado.

## Reinicio del journal (segmentos huérfanos)

Si el segmento vivo y su ancla desaparecen (una persona o un arnés los mueve) y quedan segmentos de rotaciones
anteriores, el Core abre un segmento vivo nuevo, como siempre que falta el journal. Ese estado anterior ya no
responde por este journal: el manifiesto y los ids retirados se apartan con el sufijo `.reset-<fecha UTC>` (no se
borran), los segmentos viejos se quedan donde están y el manifiesto nuevo los cubre con `floor` = el número más alto
en disco. La rotación siguiente usa ese número + 1. Antes de este arreglo la rotación pedía otra vez el segmento 1,
chocaba con el huérfano, se posponía en silencio en cada escritura y el journal volvía al muro de 64 MiB.

Las invocaciones completadas de los archivados quedan indexadas por `invocationId` y huella. Cuando se repite un id
archivado, su respuesta se reproduce desde el segmento, que se autentica de nuevo, y la operación no se vuelve a
ejecutar. Un id archivado con otra huella da `idempotency_conflict`.

## Retención (lo único que el journal borra solo)

Se conservan los **2 segmentos archivados más nuevos** (`DefaultRetainedArchiveSegments`). En disco eso es como
máximo unos 48 MiB × 2 más el segmento vivo; al abrir se lee entero el vivo y, de cada sellado, su índice (el
sellado entero sólo la primera vez o si su índice no coincide). Los segmentos más viejos, sus anclas y sus índices se
borran después de cada rotación y al abrir. Si otro proceso tiene abierto uno de esos archivos, queda
en la lista `pruned` del manifiesto y el borrado se reintenta en la pasada siguiente.

**Un id podado nunca se vuelve a ejecutar.** Antes de que un segmento salga del manifiesto, cada invocación que
completó deja un id retirado en `missions.jsonl.retired`: 32 hex de un HMAC del `invocationId` (otro dominio,
`baxy.journal.retired.id.v1`) y un salto de línea, 33 bytes por id frente a unos 13 KB por vista. El largo y el HMAC
del archivo entero van en el manifiesto. Un id retirado responde `idempotency_conflict` en `MissionEngine` y
`RecordStartedAsync` lo rechaza. La App reintenta con el mismo id desde su outbox (`DurableRetryStore` y
`DurablePlanStore`, sin caducidad; sólo las misiones de computer use y sus primitivas se retiran al arrancar otra
sesión), así que sin esto un reintento tardío repetiría el efecto.

Orden: se agregan los ids retirados y se hace fsync; después se escribe el manifiesto sin el segmento podado y con el
largo nuevo de los retirados; recién entonces se borran los archivos. Un corte antes del manifiesto deja bytes de
más en `.retired`, que la apertura recorta al largo autenticado (el segmento sigue retenido y se poda otra vez). Los
tests cortan en las dos etapas (`JournalCommitStage.Retention*`).

Lo que se pierde al podar es la respuesta, no la identidad: el id deja de reproducirse y pasa a rechazarse. Los ids
retirados crecen sin tope, unos 230 KB por segmento podado de 7 000 invocaciones, y se cargan en memoria al abrir.

## Lectores

- Kernel: `FindStartedFingerprintAsync` y `FindCompletedAsync` consultan el segmento vivo y los archivados
  retenidos; `IsRetiredAsync` (nuevo en `IInvocationJournal`) responde por los podados. `MissionEngine` rechaza un id
  retirado con `idempotency_conflict` antes de evaluar la política.
- Scripts: `scripts/cu_live/jsteps.py` lee las últimas N líneas a través de los segmentos que enlaza el manifiesto.
  `scripts/score_context_turns.py` lee esos archivados en orden y después el vivo, y omite el inicio repetido de una
  incompleta trasladada. Ninguno lee segmentos huérfanos de un reinicio.
- Hay scripts de compuerta que sólo comprueban que `missions.jsonl` y su ancla existan (`attest_in_place_upgrade.ps1`
  y `test_gpu_status.ps1`). Siguen valiendo.

## Medición del tamaño por tipo de registro

Medido sobre el journal archivado del 2026-10-07 (65 013 047 bytes, 6 918 invocaciones, todas `retained_completed`
tras compactar). Sólo se midieron largos; no se descifró nada.

| Operación | Registros | % de bytes | Bytes por línea |
|---|---:|---:|---:|
| `input.visible.controls` | 4 397 | 93,2 % | 13 782 |
| `input.visible.click` | 898 | 2,6 % | 1 886 |
| `memory.status` | 666 | 1,8 % | 1 785 |
| `app.open` | 477 | 1,0 % | 1 332 |
| `input.key.press` | 273 | 0,8 % | 1 902 |

En una vista, `response.result.controls` ocupa unos 6,0 KB, con una media de 35 controles. El `rect` es el campo
más pesado. `response.message` ocupa unos 3,5 KB y es la narración `observed`, una segunda copia compacta de la
misma vista. Lo demás es el escape JSON del mensaje.

Esto **no se redujo** en este cambio. La respuesta journalizada es exactamente la que se reproduce cuando se repite
el mismo `invocationId`, y la usan las herramientas del arnés (`jsteps.py` lee `message.observed` de las vistas).
Recortarla cambiaría el contrato de replay de una lectura. Una reducción segura sería no journalizar como terminal
las lecturas sin efecto, o journalizar sólo su resumen. Eso es una decisión de contrato del `MissionEngine`, y la
rotación ya acota el disco sin necesitarla.
