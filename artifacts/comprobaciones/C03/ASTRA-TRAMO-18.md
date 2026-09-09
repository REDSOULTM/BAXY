# C03 — tramo18: heredar extracción literal, sin proceso inventado

EN_CURSO. La tanda anterior fue progreso: reparaciones verificadas, capturas negativas
y el informe literal pedido por el dueño. No cierre, Full, promoción ni cien frescos.

Herencia consultada en ../Probando Gemma 4/gemma4_agent/:
routing/command_splitter.py:385–413 extrae destino literal de cierre;
agent_core/agent.py:5289–5309 lo usa cuando el modelo omite el nombre;
tests/test_window_geom_and_confirm_honesty.py:77–84 comprueba ese mecanismo.
La biblioteca window.md diferencia cerrar ventana y matar proceso. No se heredan
ejecución directa, respuestas fijas, listas de apps ni el límite histórico de4palabras.

El repositorio actual ya contiene _explicit_arguments_from_evidence y validación
tipada. explicit_window_title sustituye la relación booleana del tramo17 por una
extracción literal compartida: conserva superficie, tildes, espacios/puntuación;
quita sólo delimitadores de comillas; rechaza vacíos/comillas incompletas/múltiples
relaciones y sufijo fuera de una cita. Suministra process=título/byTitle=true sólo
al catálogo que admite ese selector, nunca HWND inventado ni ventana activa.
Resolver y cerrar siguen pasando por provider, kernel y confirmación exacta.

Tests:1622pass/1fallo/115subtests en80,27s (planner+effect_intent). El caso nuevo con
schema viejo destapó que se retiraba byTitle para acomodar process. Se añadió la
validación del schema completo antes de normalizar este literal. Recheck dueño:
147pass/115subtests en2,10s;Ruff0. Logs c03-window-title-literal-{tests,recheck}.log.
Pines actuales main ddd1979996aef3c49ed233c20011dc3bbbc1aa796f430ae42b662fb7ea72bf14;
effect_intent a8c7239fe179beefcca75fe15bd8402f97535e719c8707c7b6fed9125e39d021;
STT8f2d8706894365d0226ae978cf241ecd83344720b47c752245fbdc37adf086b3.

E5 NO falta: snapshot fijado verificado completo en D:/BAXYRuntime/assets/huggingface/
hub, revisión614241f622f53c4eeff9890bdc4f31cfecc418b3,10ficheros,manifest e1ab2f…940.
Worker real CPU iniciado y apagado por protocolo:40,05s,ready,exit0 (sesión51910).
Esto no demuestra que el catálogo del producto se promoviera: capturas seguían
lexical. Hipótesis pendiente: carga/promoción durante capturas cortas; no descargar
otra copia ni afirmar que restaurar E5 ya arregló selección.

window-title-literal fue interrumpida por reinicio Windows11:32:23; sesión6829 y
procesos ausentes, sin RESULT. Ver INTERRUPCION.md. No se cuenta como aprobación.
Se detuvo árbol autoiniciado27996,comando/exe verificados, para preservar una instancia.
Nueva captura window-title-literal-resume,sesión89257 terminó0,46,14s,GPU3497,56MiB,
RAM4475,62MiB;registro intacto.5publicados/6. Ahora título resuelto, cancelación real,
nueva confirmación y cierre real PID15012/journal8. Hora y task.list fieles después.
t4 agotamiento internal_code al narrar cierre,por tanto panel NO aprobado. ADJ escrita.
Seis borradores Python aceptados contienen La ventana "Ventana C03 de prueba";
HasRepeatedWord C# elimina comillas y podría vetar ventana/ventana. Reproducción en
test dueño en curso,sesión81886; no excepción por título ni relajación de honestidad.
