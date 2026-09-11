Completar íntegramente C03 — respuesta veraz de BAXY — según C03\_ASTRA\_AUTORIDAD.md,
C03\_RESPUESTA\_VERAZ.md, contrato de campaña, identidad y AGENTS.md, incorporados como
autoridad completa. Continuación de 01a074f6-9e0e-7fb3-8282-a6b706198a7e y de la tarea
en curso; no auditoría. Trabajar en D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO,
rama Goal-c03. Registrar goal activo y threadId en
artifacts/comprobaciones/C03/RELEVO\_ACTIVO.json. Leer AGENTS.md, identidad, CHECKPOINT.md
y HANDOFF.md; el checkpoint más reciente manda. Preservar main, cambios ajenos, artifacts,
scratchpad y la encuesta 742/rev1248.

VELOCIDAD — prioridad de esta fase.
Cierra C03 lo antes posible sin perder calidad. La calidad la garantizan el método
(paneles preregistrados y sellados, adjudicación contra hechos observados, pruebas dueñas
verdes antes de adoptar) y no el tiempo gastado: no relajes ninguno de esos tres pasos
para ir más rápido. Todo lo demás —preparación, bookkeeping, redacción de pruebas,
borradores de reparación— hazlo en paralelo.

MODO ULTRA Y PARALELISMO.
El modo Ultra está activo por decisión del dueño. Usa su descomposición automática y sus
subagentes únicamente dentro del pipeline de abajo: el pipeline define los frentes de
trabajo; no abras otros por iniciativa propia ni persigas mejoras tangenciales fuera de la
categoría en curso. Cada subagente recibe un único entregable, una lista cerrada de
ficheros que puede tocar y un tope de iteraciones; termina y devuelve resumen.

Un solo escritor canónico: sólo tú (raíz) adoptas, integras, haces commit y push en
Goal-c03. Prohibido a cualquier subagente, incluidos los que Ultra lance por su cuenta:
lanzar llama-server o cualquier inferencia local, ejecutar el Full, tocar el registro del
runtime, la encuesta o los paneles sellados, o escribir directamente en Goal-c03.

Pipeline por categoría — la GPU nunca espera:

- Mientras corre la tanda N en GPU: un subagente prepara y sella el panel de la categoría
  N+1 (literales de la encuesta + variantes que cambien nombres/valores/orden/idioma +
  casos límite, con SHA); otro escribe verification\_status por case\_id y actualiza la
  matriz con lo adjudicado en N−1; otro redacta pruebas dueñas para los defectos ya
  diagnosticados en N−1, partido Python / C#. Tú haces la adjudicación parcial en vivo.
- Al terminar la tanda N: tú adjudicas el panel completo; el juicio no se delega.
- Reparaciones en paralelo: para los dos o tres defectos independientes más frecuentes,
  un subagente por defecto en un worktree propio (git worktree add), con propiedad de
  ficheros disjunta declarada de antemano, propone reparación mínima + dueñas verdes y
  devuelve un parche. Nunca dos subagentes sobre el mismo fichero. Tú revisas, integras
  uno a uno en Goal-c03, corres dueñas, commit. Los worktrees se borran al integrar.
- Lanza la tanda N+1 inmediatamente tras el commit. El Full, cuando toque, va en una
  ventana sin tanda: satura la RAM y dispararía la guarda.

Recursos: la RAM libre es el límite real, no el número de hilos. Máximo 4 subagentes
concurrentes, también para los que Ultra decida lanzar. Si la guarda de RAM libre
(768 MiB) salta, reduce a 2 antes de reintentar. La tanda en GPU siempre tiene prioridad
sobre cualquier subagente. Cierra build servers y procesos ociosos antes de cada tanda.

ESFUERZO.
Adjudicar un panel y decidir una adopción con evidencia contradictoria son las tareas de
más juicio: hazlas tú, con el razonamiento completo. Preparación, bookkeeping y auditoría
no necesitan razonamiento profundo: si el modo permite fijar esfuerzo por subagente,
úsalo en medium para esos roles y en high para los que redactan reparaciones.

PUBLICACIÓN.
Commit en Goal-c03 cada vez que adoptes una fuente validada, con dueñas verdes y el
checkpoint del tramo. Push cuando el commit tenga sus dueñas verdes. Main intacto. Ningún
tramo acumula más de un día sin commit.

FULL.
Un Full cada vez que adoptes una fuente que toque C# y Python a la vez, y el Full completo
de cierre sobre el candidato final. No un Full por cambio. Publica siempre el resultado
tal cual, verde o rojo.

MATRIZ.
Actualiza 03\_MATRIZ\_DE\_CRITERIOS.md con la evidencia de tus filas C03 en cuanto se
cumplan. Para filas de otro owner con evidencia ya producida, añádela en su celda como
«evidencia disponible — owner CXX» sin cambiar su estado. No cierres filas ajenas.

RESERVA DE CIEN — vigente AUTORIZACION\_DUENO\_536.md.
El dueño autorizó usar mensajes nuevos e históricos, incluidos los acreditados y esperados
de la encuesta, priorizando español y manteniendo inglés, exigiendo generalización. No
esperes material inédito ni prolongues auditorías de frescura como bloqueo. Congela el
panel de aceptación y sus expectativas antes de ejecutarlo; registra qué es desarrollo,
regresión o generalización. Sigue prohibido traducir, plantillar o reetiquetar material.

ENCUESTA.
Cubrir un requisito significa que la conducta funciona verificada con variantes; no
replicar el literal. Escribe verification\_status por case\_id a medida que cubras cada
conducta, y publica en cada checkpoint cubiertos / abiertos / no aplican sobre 742. Los 3
negativos y los 18 sin marca se conservan como límites. Debe ser consultable como número.

AUDIO FÍSICO.
Separa los dos caminos. Loopback: lo que BAXY publica por voz debe recuperarse íntegro del
flujo de reproducción; un fragmento es fallo real y se repara. Micrófono: con el AEC
activo, no transcribir la propia voz de BAXY es correcto; mídelo como supresión de eco y
no lo cuentes como defecto. Voz humana física, calibración de wake y FAR/FRR son de C08:
documenta estado, reanudación exacta y evidencia en sus filas sin cerrarlas.

BLOQUEOS Y ESCALADO.
Resuelve todo bloqueo cuya fila sea de C03. Si un defecto pertenece a otro Cxx, repáralo
sólo si impide una conducta de C03; si no, documenta causa, evidencia y reanudación en la
fila de su owner y continúa. Si encuentras una contradicción entre exigencias o falta
material, pregúntame en el mismo turno y continúa con todo lo que no dependa de la
respuesta. No marques el goal bloqueado mientras quede trabajo independiente; no repitas
la misma consulta más de una vez.

Todo lo demás del encargo original sigue vigente sin cambios: las ocho rutas con voz
propia e idioma adecuado; las seis invariantes (catálogo tipado único, mente propone /
kernel autoriza / provider ejecuta, nada afirmado sin verificar, terminales honestos,
confirmación exacta, cero respuestas visibles fijas); modularidad sin código muerto ni
capas duplicadas; heredar primero y contrastar con documentación y papers acotados;
aislar el LLM nativo y añadir BAXY por piezas midiendo la primera transformación errónea,
una diferencia por vez; tras dos intentos comparables sin mejora cambiar de estrategia;
Qwen3-4B-Instruct-2507 Q4\_K\_M elegido, comparaciones de modelo cerradas; local, privado,
techo conjunto 4 GB VRAM buscando el mínimo que conserve calidad; averías aparte con causa
y recuperación; producto compartido y UI real de escritorio; pruebas dueñas y Full de
cierre verdes sin omitir ni relajar; CHECKPOINT por tramo y antes de compactar; Markdown
legible con entradas y respuestas literales, adjudicación y payloads, preservando
privacidad; revisar contratos y continuidad C04–C09 hasta instalación desde
MAPA\_COMPLETO\_2026-09-05.md sin ejecutar esos goals. Mantener EN\_CURSO hasta cierre
demostrado. Continuar autónomamente.