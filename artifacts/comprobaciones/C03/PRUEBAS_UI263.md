# C03 — regresión en escritorio tras recuperar Steam:263

Fuente262,37archivos congelados en astra-source263-snapshot, sin cambios durante
la corrida. Qwen3.5 sigue override. Entrada real py main.py; cinco controles
introducidos por el agente mediante Computer Use, reutilizando literales que el
dueño había escrito en260. Ningún mensaje sintético inyectado por el hook. No reserva.
El orden cambia respecto260; esto es regresión de causa, no comparación pareada
de todas las respuestas de aquella secuencia.

| Caso | Respuesta final visible | Resultado |
|---|---|---|
| abre steam | Steam ya está abierto. | Correcto: app.open, Core succeeded/verified, alreadyRunning=true, ventana132992. |
| Tengo en mente que abras steam | Ya he abierto Steam. | No aceptado: no hubo nueva operación/lectura; el compositor reutilizó previousResponse. |
| Si, abre steam | No puedo abrir Steam porque está fuera de mis capacidades en este equipo. | Fallo: negativa falsa. |
| mhhhhh, porque no?, cuales son tus capacidades? | Sin prosa final; alerta Response error y estado error. | Fallo normal espontáneo; entrada permanece disponible. |
| abre steam (después del error) | Steam ya está abierto. | Recuperación comprobada: nueva app.open verificada, alerta desaparece y estado idle. |

La reparación262 sí llega al producto: el primer y último control resuelven y
verifican Steam sin pedir confirmación. Ya estaba abierto: no se presenta como
un lanzamiento nuevo. La ventana real y los hechos del Core se contrastaron.

La frase larga todavía tiene shortlist28 sin app.open. Dos selecciones nativas
(HTTP id5 con28tools e id7 con4) contestan «Steam ya está abierto.» sin toolcalls;
la mente genera después «No puedo abrir Steam directamente, pero puedo ayudarte
a encontrar enlaces o guiar los pasos para hacerlo tú mismo.» El compositor
publica «Ya he abierto Steam.» desde previousResponse=«Steam ya está abierto.».
No hubo Core app.open para t2; el historial no acredita una verificación actual.

«Si, abre steam» entra en explicit_conversation/unsupported(request15); el
chequeo adicional HTTP id11 ve sólo cuatro operaciones game.install y responde
sin toolcalls. `_catalog_unavailable_turn_decision` sigue siendo un owner a
inspeccionar: su patrón game_request abarca open/abre y puede cerrar antes del
selector normal cuando la extracción de identidad no coincide.

Capacidades(request19): selección nativa id18 devuelve una lista larga y
finish_reason=length. Enumera capacidades de su shortlist incompleta, niega
abrir aplicaciones y termina truncada. Segundo intento id22: TimeoutError.
Recuperación turn_runtime_failure; varios borradores de error son rechazados
por extra_claim. Se observa estado error, sin final público. El siguiente turno
normal sí funciona. No se relajan límites ni validadores para convertirlo en pass.

HTTP lógico completo y respuestas se conservan privados en
C03-ui263-private/http-posts.jsonl. El hook observa LlmRuntime._post y eventos
de voz; no modifica parámetros, resultados ni criterios. UI_STEAM_SETTLED,
UI_LONG,UI_FOLLOWUP,UI_CAPABILITIES_TERMINAL y UI_RECOVERY_SETTLED guardan
las vistas estables. Algunas vistas inmediatas anteriores conservan caché UIA
antigua mientras la imagen ya había cambiado; no usarlas solas para adjudicar.
set_value falló sin escribir; se usó el teclado sobre el campo visible.

Recursos:3504,71MiB GPU y5624,86MiB RAM residente,600,41s; atribución disponible.
No captura acústica activada en263: no sustituye la medición conjunta260.
El botón cerrar ocultó la ventana por la presencia en bandeja; el monitor cerró
su árbol al límite600s. Exec80211 exit0 recogido, launcher0,cleanup0,
volumen restaurado exactamente y ningún proceso observado sobreviviente.

No fuente editada en263 ni pruebas repetidas. Fuente262 conserva39tests dueños
sin skips y Fast verde. C03 íntegro EN_CURSO: falta reparar los tres recorridos
anteriores antes de aceptación fresca, promoción, Full y publicación.
