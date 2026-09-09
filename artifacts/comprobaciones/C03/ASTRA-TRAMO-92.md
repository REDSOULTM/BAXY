# C03 — contexto de recuperación — 92

86 conserva búsqueda vacía, pero el chat añade una incapacidad falsa y se veta.
La recuperación descarta la respuesta previa y fabrica cifrado.89/91, con el
mismo modelo/perfil y primera petición de recuperación exacta, recuperan causa
como dato de situation. Cálculo y checksum mantienen tema propio; seguimiento
de latencia conserva referente. El control de límites aún es metatexto, no5/5.
PRUEBAS_RECUPERACION86_89_91.md registra herencia y contraste actual.

Se conserva el context acotado ya enviado por App como previousResponse sólo
para conversación. No se restaura historial como roles assistant: ésa fue la
regresión de Granite panel-opus-4/5. Se elimina el contenedor previous_turn vacío
de primera generación y ambos reintentos. No se inventa emparejamiento con un
pedido anterior; PreviousUserRequests puede incluir turnos sin respuesta.

Un nombre de archivo aportado antes por la persona sigue siendo vocabulario
humano. Los guardas Python/C# consultan priorRequests sólo para eximir el mismo
token completo del veto de códigos. El pedido actual sigue gobernando intención;
contexto del asistente por sí solo no concede esa exención, y otro código interno
sigue vetado. Se reutiliza el parámetro priorUserText existente en C#.

Red:Python2fail/22deselected/0,56s; C#1fail/0pass/0skips/99ms. Acotadas nuevas
Python2pass/22deselected/0,34s. Suite amplia inicial8fail/1144pass: al retirar el
contenedor vacío quedaron referencias en reintentos; corregidas ambas.
--lf -x:8pass/1100deselected/1,16s. Cuatro suites completas:1152pass/0skips/5,49s.
Integración C03FactPreservation+PlannerAppBoundary+Goal06VisibleVoice:
182pass/0skips/15s. Fast16945exit0,Release15,01s,0 avisos/errores.
Logs TEMP/c03-context92-{python-fixed,dotnet,fast}.log.

files92-context iniciado, mismos cuatro turnos86. Qwen3.5 override sin promoción.
Progreso93 preparado para contraste nativo de thinking; no ejecutado en paralelo.
C03 EN_CURSO; sin Full, aceptación UI/audio o reserva humana.
