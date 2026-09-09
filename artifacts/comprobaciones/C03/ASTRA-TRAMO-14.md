# C03 — tramo14: cancelación exacta y equivalencia de hora oral

EN_CURSO. Rama Goal-c03;main,stash ajeno y registro Granite intactos. Sin promoción,
Full final,cien nuevos,commit ni push. Todos los cambios son desarrollo.

## Cancelación: causa y contraste

personal-shell t18: el modelo inventaba estado pendiente del proceso. El transporte
conservaba sólo las lecturas previas de la misión y remaining_steps_cancelled;
la entrada cancelar no identificaba qué acción se había cancelado.
MissionNarration ahora comparte DescribeCurrentAction con confirmación y transmite
cancelledRequest/cancelledAction desde PendingMindPlanExecution, con argumentos de
la operación preparada si existen. Ambos caminos de cancelación usan ese contrato.
Python lo conserva sin convertir el cierre cancelado en un efecto observado.
No cambian autorización, efectos inciertos ni abandono de confirmaciones comenzadas.

Validación:18pass.NET (C03FactPreservationTests/MindPlanSessionTests),99passPython
(C03/compose),17pass/1skip ambiental (V8/STT);Ruff/format0. Logs c03-cancel-action-*.

Modelo real cancel-action: mismas21 entradas seguidas de3 averías +3 restauraciones,
86.39s,3497.56MiB GPU,5274.68MiB RAM. t18 ahora identifica fielmente el cierre
cancelado. t16 lee tareas realmente y t20 cierra ventana propia PID4124 verificado
journal sequence28.23/27publicados:1agotamiento espontáneo +3fallosinyectados.
ADJ individual conserva fallos de spanglish, gramática y analogías. No aceptar toda
una respuesta porque empiece con un hecho correcto.

## Recuperación misma sesión: evidencia y límite

reject→restaurar→hora;timeout→restaurar→hora/audio;exhaust→restaurar→task.list.
Todos los cambios de inyección y restauración usan PID33896, sin session.new ni
reinicio. Tres peticiones posteriores correctas. controlsUsable=true y state=idle
en eventos. No confundir continuidad con error comprensible: activity SYSTEM lleva
msg=composition_failed; no se ha verificado representación ni audio en UI real.
FieldProductChannel.cs:565–579 es el owner; búsqueda acotada en FieldUi/src no
encontró manejo literal de composition_failed/controlsUsable. Revisar el recorrido
visual antes de afirmar R07final. Runtime aquí sigue con override de desarrollo.

## Hora oral: otro rechazo falso demostrado

cancel-action t1: observado10:10; borrador Son las 10 y 10 repetido en todos los
reintentos, rechazado missing_name por exigir notación10:10 o unidades explícitas.
Python y UserMessagePolicy ahora reconocen marco horario son las/es la +hora y
minuto, con el mismo tratamiento AM/PM. No aceptan dos cantidades de archivos,
minuto distinto, AM por PM ni una segunda hora contradictoria. Se conservan las
otras representaciones admitidas. No se altera el texto del modelo.

Regresión reproduce el borrador exacto por compose_user_message y comprueba una
única llamada. Pruebas finales:123pass/1skip ambiental Python (C03/compose/V8/STT),
32pass.NET (C03FactPreservationTests/Goal06VisibleVoiceTests);Ruff/format0.
Logs scratchpad/c03-spoken-clock-python-final.log,c03-spoken-clock-dotnet.log,
c03-spoken-clock-format.log. Fuente llmSHA37c9a961547c57bf5343bbcfb5a89a65d6af6a5d423ade6219d7ac8829617e16;
STTSHA000de1a9ab1dc042f1f56e5312bf24ee701e747cc17497e6553a38a4aa985f21.
Contraste real spoken-clock preregistrado con mismas21, sin repetir averías.
Terminó68.25s,21/21publicados,3497.56MiB GPU,5405.79MiB RAM. t1 publica hora oral
correcta. Pero t18 cancelación FALLA: borrador correcto rechazado por fuga dewindowId,
reintento afirma cierre falso. Hechos conservados pero outcome=completed junto a
state=remaining steps cancelled;hipótesis concreta pendiente. ADJ documenta ambos
borradores. Sólo t20 cerró realmente PID9476,journalsequence28. No afirmar cancelación
resuelta por la primera captura favorable. Todos los procesos recogidos.

## Exploración acotada para siguiente causa

Alias natural de ventana pendiente. WindowsWindowControlProvider.cs:609 busca por
nombre de proceso y MainWindowHandle, no título ni ventanas múltiples del proceso.
WindowsInstalledApplicationOpenProvider.cs:910–974 hereda una limitación parecida:
primero exige MainWindowHandle y después toma LargestTopLevelWindow; no heredar
esa elección sin contraste cuando un host contiene aplicaciones diferentes.
El mismo fichero ya tiene EnumWindows en1084–1102; heredar enumeración e identidad
de ventanas reales antes de construir un mapa por aplicación. Ningún cambio de
provider ni catálogo en este tramo. Fuente histórica por índice:
biblioteca/carter/legacy/Carter_v3/Roadmap/02_round_2_process_probe_window.md;
es encargo antiguo, no prueba de un mecanismo implementado.

Siguen pendientes spanglish/calidad, desarrollo verde,UI,R07final,runtime registrado,
cien nuevos/Fullfinal/publicación y continuidad contractual. Ningún bloqueo externo.
