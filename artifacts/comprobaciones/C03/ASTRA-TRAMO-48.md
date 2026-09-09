# C03 — tramo48 en reparación: plan compuesto y progreso

Fuente47 adoptada; candidata48 retira el atajo C# heredado338e4cb que detectaba
hora/audio por Contains y fabricaba siempre dos pasos. Se eliminaron método,
rama de ejecución y hint de fallback; unknown deja la decisión en su ruta.
La frontera E2E exige pasar la petición completa para pares, triples y restricciones.
No cambiosPython48, modelo, sampler ni provider. No se adopta todavía la candidata:
la integración expuso fallos del lector y del compositor antes ocultos por el atajo.

186tests .NET pass,0skips,2m30s,exit0 (95894): MindShellEndToEndTests,
Goal06VisibleVoiceTests,C03FactPreservationTests,NaturalSystemStatusRequestParserTests.
Comando y log:%TEMP%/c03-compound48-dotnet.log. No Fast48/Full aún.
Se mantiene el verde Python2945pass/115subtests/0skips de fuente47, sin cambiosPython48.

## Producto

astra-compound-shell48: siete controles técnicos de sólo lectura,84,20s,
GPU3497,56MiB,RAM4559,80MiB,registro intacto,exit0(10929). Sin procesos propios.
Sin hook de payload, sólo auditoría de composición/turno habitual. Contexto distinto
del prefijo13 anterior, declarado en PREREG; no comparar latencia como efecto controlado.

t1 ahora ejecuta system.time,audio.status,system.status(cpu); resultado final
verificado00:02,volumen100,CPU47,9167%→47,9%. Pero su aviso previo publicado
inventa14:30 yCPU45%, por lo que el turno completo FALLA. Dos borradores de progreso:
primero14:32 rechazado por acting_asserted, segundo14:30 aceptado porque incluye
«en curso» en la primera frase. El payload sólo decía kind=status,state=in progress,
sin observaciones. No es un error de proveedor ni información del usuario.

t2/t3 españoles/ingleses consultan sóloaudio.status y dicen que la hora no está
disponible. t4mezcla también pierdehora y termina composition_failed al rechazar
14:30 inventada. El lector literal ya devuelve sóloaudio.status para los tres;
no culpar al selector nativo ni reparar con otro prompt. _strict_catalog_request
(effect_intent:7221–9094) no incluye system.time entre dominios; acepta un único
dominio y devuelve audio antes de la lectura general. La lectura de reloj en
_review_system_and_network_effects:9173 exige final de cláusula; coordinación con
objeto compartido necesita conservar ambos pedidos. Heredar gramática/cláusulas
existentes, sin volver al atajo C# ni otro detector duplicado.

t5 conserva la consulta y prohibición independiente:00:02,ningúnmute. t7leeaudio100.
t6ejecuta hora/CPU correctamente, Python compone resultados fieles pero App rechaza
«No hay fallos registrados» como reversed_result. UserMessagePolicy.LooksLikeFailure
usa Contains("fallo"), confunde la ausencia de fallos con un fracaso y agota reintentos.
No retirar el control de polaridad: corregir su lectura con positivos/negativos.

Dictamen: sólo t5/t7 cumplen el turno completo(2/7). t1final es fiel pero el progreso
lo invalida; t2/t3parciales; t4/t6sin respuesta. La ruta progreso está observada pero
no acreditada. paired.json conserva entradas, salidas, etiquetas, hechos y errores.
La prueba no consume reserva humana ni acredita UI/audio físico.

## Siguiente

Reparar primero conservación de reloj/audio en el lector, luego progreso sin
resultados aún y falsa inversión de «no hay fallos». Comparar los mismos siete
controles después de pruebas dueñas. No repetir por azar ni cerrar con rojos.
El aviso de progreso se genera por _emit_early_turn_signal (tracevacío); las
etiquetas publicadas están en boot_stage.label. Contarlas, no sólo activities.
Investigar representación nativa del progreso antes de cambiar tratamiento.

El fallo de ruta de archivo47 sigue pendiente, con una precisión de alcance:
resourceId admite35caracteres. ProductCatalog sólo ofrece lectura desde identidad
revalidada; list/search son del sandbox, known.search es desktop/documents/downloads.
No hay en ese conjunto lookup arbitrario de AppData. La ruta de ausente47 está en
AppData: no inventar una nueva capacidad ni tratar una ruta como resourceId.
filesystem.path.ensure.absent puede BORRAR moviendo a papelera; nunca usarlo como
lookup para esta lectura. El producto debe expresar su límite útil o resolver por
las operaciones realmente disponibles cuando corresponda, sin repedir la ruta dada.

Reserva100,UI/voz final,contratosC04–C09,limpieza,Full y publicación siguen pendientes.
Goal activo; sin commit/push ni main. No bloqueo externo.
