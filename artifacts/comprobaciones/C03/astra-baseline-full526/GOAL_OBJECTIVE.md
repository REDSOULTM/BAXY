Completar íntegramente C03 — respuesta veraz de BAXY — según C03\_ASTRA\_AUTORIDAD.md,
C03\_RESPUESTA\_VERAZ.md, contrato de campaña, identidad y AGENTS.md, incorporados como
autoridad completa. Continuación de 01a074f6-9e0e-7fb3-8282-a6b706198a7e y de la tarea
en curso; no auditoría ni trabajo paralelo. Trabajar en
D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO, rama Goal-c03. Registrar goal
activo y threadId en artifacts/comprobaciones/C03/RELEVO\_ACTIVO.json. Leer AGENTS.md,
identidad, CHECKPOINT.md y HANDOFF.md; el checkpoint más reciente manda. Preservar main,
cambios ajenos, artifacts, scratchpad y la encuesta 742/rev1248. Sin escritores paralelos
ni subagentes.

PUBLICACIÓN — sustituye la instrucción anterior de no commitear.
Haz commit en Goal-c03 cada vez que adoptes una fuente validada, con las pruebas dueñas
en verde y el checkpoint del tramo. Empieza con un commit de control de todo el WIP
actual antes de seguir. Push a la rama remota cuando el commit tenga sus dueñas verdes.
Main permanece intacto. No esperes al cierre para publicar: el objetivo es que ningún
tramo acumule más de un día de trabajo sin commit.

FULL — sustituye «no repetir Full durante reparación».
Ejecuta un Full de línea base ahora sobre el WIP actual y publica su resultado tal cual,
verde o rojo. Después, un Full cada vez que adoptes una fuente que toque C# y Python a la
vez, y el Full completo de cierre sobre el candidato final. No un Full por cambio.

MATRIZ — nuevo.
Actualiza 03\_MATRIZ\_DE\_CRITERIOS.md con la evidencia de tus propias filas C03 en cuanto
se cumplan, sin esperar al cierre. Para filas cuyo owner sea otro Cxx y para las que ya
hayas producido evidencia (al menos G03C.06 pico VRAM, G06.04 narración accesible por la
misma ruta de prosa, G05.03 terminales honestos de efecto incierto), añade la evidencia
en su celda con la marca «evidencia disponible — owner CXX» sin cambiar su estado. No
cierres filas ajenas.

RESERVA DE CIEN — sustituye la cláusula de idiomas.
La auditoría deja 112 candidatos limpios: 107 español, 1 inglés, 0 mezcla. La exigencia
de tres idiomas no es alcanzable con ese material y no se resuelve traduciendo. Procede
así: congela hasta 100 turnos españoles humanos acreditados con procedencia, contexto y
exposición auditada, distribuidos entre las ocho rutas. El inglés y la mezcla natural
forman un conjunto aparte con el material humano que exista, incluidos los cuatro
ejemplos de ACLARACION\_DUENO\_2026-09-06.md, y se adjudican con el mismo rigor sin
completarse con cuotas. Si el dueño aporta turnos nuevos escritos por él en inglés o
spanglish, son humanos y frescos y entran en la reserva por su fecha de escritura. Sigue
prohibido traducir, plantillar o etiquetar de nuevo material de desarrollo.

ENCUESTA — nuevo, hace medible la generalización.
Cubrir un requisito significa que la conducta pedida funciona verificada con variantes
que cambien nombres, valores, orden, referencias e idioma; no replicar el literal.
Escribe verification\_status por case\_id en el registro privado a medida que cubras cada
conducta, y publica en cada checkpoint cuántos de los 742 van cubiertos, cuántos abiertos
y cuántos no aplican. Los 3 con expectativa negativa y los 18 sin marca se conservan como
límites. La cobertura de la encuesta es requisito de cierre y debe ser consultable como
número, no estimable.

AUDIO FÍSICO — sustituye «voz/audio físico comprobados» dentro de C03.
Separa los dos caminos y no los puntúes juntos. Camino de loopback: lo que BAXY publica
por voz debe recuperarse íntegro del flujo de reproducción; ahí un fragmento es un fallo
real y se repara. Camino de micrófono: con el AEC activo, no transcribir la propia voz de
BAXY es el resultado correcto; mídelo como supresión de eco, nunca como transcripción, y
no lo cuentes como defecto. La voz humana física, la calibración de wake y FAR/FRR con
sus hablantes son de C08: documenta el estado alcanzado, deja la reanudación exacta y
anota la evidencia en las filas de C08 sin cerrarlas. Eso no reduce C03: hace medible su
criterio.

BLOQUEOS Y ESCALADO — sustituye «resolver todos los bloqueos, no aplazarlos».
Resuelve todo bloqueo cuya fila sea de C03. Si un defecto pertenece por matriz a otro Cxx,
repáralo sólo si impide una conducta de C03; en caso contrario documenta causa, evidencia
y reanudación en la fila de su owner y continúa. Y si encuentras una contradicción entre
dos exigencias del encargo, o una que el material disponible no permite cumplir, detente
y pregúntame antes de gastar tramos: no la dejes anotada en el checkpoint como dato.

Todo lo demás del encargo original sigue vigente sin cambios: las ocho rutas con voz
propia e idioma adecuado; las seis invariantes (catálogo tipado único, mente propone /
kernel autoriza / provider ejecuta, nada afirmado sin verificar, terminales honestos,
confirmación exacta, cero respuestas visibles fijas); modularidad sin código muerto ni
capas duplicadas; heredar primero y contrastar con documentación y papers acotados;
aislar el LLM nativo y añadir BAXY por piezas midiendo la primera transformación errónea,
una diferencia por vez; tras dos intentos comparables sin mejora cambiar de estrategia;
Qwen3-4B-Instruct-2507 Q4\_K\_M registrado es candidato y toda promoción exige perfil,
hashes, recursos y regresión; local, privado, techo conjunto 4 GB VRAM buscando el mínimo
que conserve calidad; averías aparte con causa y recuperación; producto compartido y UI
real de escritorio, sin que un conductor sin ventana acredite pantalla; pruebas dueñas y
Full de cierre verdes sin omitir ni relajar; CHECKPOINT por tramo y antes de compactar;
Markdown legible con entradas y respuestas literales, adjudicación y payloads,
preservando privacidad; revisar contratos y continuidad C04–C09 hasta instalación desde
MAPA\_COMPLETO\_2026-09-05.md sin ejecutar esos goals. Mantener EN\_CURSO hasta cierre
demostrado. Continuar autónomamente.