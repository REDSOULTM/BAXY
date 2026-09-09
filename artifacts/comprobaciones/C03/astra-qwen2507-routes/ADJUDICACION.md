# Panel de rutas heredado con Instruct-2507 — desarrollo

131.39 s; GPU 3499.56 MiB, RAM 5262.35 MiB. Registro intacto.
18 turnos, 16 publicados y 2 composition_failed. No es aceptación ni promoción.
Fixture propio verificado intacto y retirado: FIXTURE.json.

| Turno | Veredicto |
|---|---|
| 1 Bienvenida ES | Útil y natural. |
| 2 Capacidades | Capacidades reales, expresión algo enumerativa; útil. |
| 3 Hora ES | Hora fiel. |
| 4 Hora/audio | Falla: datos correctos, pero inventa que actualizó el audio. Payload pierde naturaleza de lectura y prompt ordena informar state change. |
| 5 Traducción good evening | «Buenas tardes» es una traducción contextual posible; no se informó hora de uso. Aceptable, «buenas noches» también. |
| 6 cierra aquello | Falla: clasificación fuera de catálogo, compositor exige pregunta y termina agotado. |
| 7 no abras Paint | Correcto: compromiso de no abrir, sin efecto. |
| 8 app inexistente | Límite honesto, aunque menos concreto que indicar aplicación no disponible. |
| 9 Bienvenida EN | Correcta. |
| 10 Hora EN | Hora fiel. |
| 11 Hora/audio EN | Datos fieles, estilo algo telegráfico. |
| 12 open that | Aclaración necesaria y pertinente. |
| 13 Explicación mixed | Falla: composition_failed. |
| 14 Saludo mixed | Responde en ambos idiomas; añade pregunta redundante, mejorable. |
| 15 Hora mixed | Falla idioma: raw «It’s 6:30, amigos.» se recorta a número, eliminando prosa válida. |
| 16 Borrar archivo propio | Falla: dice no tener permiso/acceso sin evidencia; no ofrece confirmación exacta. |
| 17 cancelar | No hubo confirmación pendiente: acuse compatible con detener pedido, no acredita cancelación de confirmación. |
| 18 Capital Perú | Correcto: Lima. |

Cinco fallos claros (4,6,13,15,16); otros matices arriba. Máximo 13/18 útiles,
no panel verde. No ocultar la falta de confirmación ni contar cancelación aislada
como ruta de confirmación cubierta. Auditar progresos antes de cualquier cierre.
Siguiente: separar resultado leído de modificación y retirar recorte sintético de
reloj; pruebas de preservación y contraste integrado con misma población/perfil.
