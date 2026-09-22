# Corpus pendiente para la Fase 3.5 (semántica unificada, Fable 5.1)

Regla del dueño (2026-09-21): un fallo de **lectura** visto en una tanda no se parcha con otro regex; se anota aquí
y la fila queda abierta hasta que la capa semántica unificada lo cubra (prompt:
`PROMPT_FABLE_SEMANTICA_2026-09-23.md`). Un fallo de adaptador o de fixture NO va aquí: se arregla y se re-mide.

Formato de cada entrada (una por línea de tabla; sin datos privados del dueño, sólo la forma del pedido):

| Tanda / caso | Forma del pedido (literal o variante) | Qué hizo BAXY | Qué debía hacer | Fila(s) |
|---|---|---|---|---|

## Ya conocidos al traspaso (2026-09-21)

| Origen | Forma del pedido | Qué hizo BAXY | Qué debía hacer | Fila(s) |
|---|---|---|---|---|
| Auditoría semántica 2026-09-20 | «mandale/decile … a <persona>» con un solo destinatario resoluble | preguntó el cliente | resolver el canal y enviar; preguntar sólo con ambigüedad real (D24) | H0019, H0024, H0045, H0074, H0198, H0231, H0408, H0536 |
| Auditoría semántica 2026-09-20 | «abre Steel.» / «abres team» (nombre mal oído, un solo candidato instalado) | preguntó o no abrió | app.open de Steam (regla 2026-09-19: lo mal dicho lo arregla BAXY) | H0227, H0398, H0521 |
| Auditoría semántica 2026-09-20 | «cambiá a la otra ventana» | preguntó | window.resolve de las visibles y activar la de atrás | H0263 |
| Auditoría semántica 2026-09-20 | «quiero que lo veas y de qué se trata» («lo» = la pantalla) | preguntó el antecedente | capture.screenshot + ocr.read | H0528 |
| Auditoría semántica 2026-09-20 | «abrí Marvel…» (el único juego instalado parecido) | preguntó | lanzar el único candidato | H0682 |

## Prueba del dueño 2026-09-21 (noche) — `PRUEBA_DUENO_2026-09-21_NOCHE.md` (turnos del registro privado)

| Turno | Forma del pedido | Qué hizo BAXY | Qué debía hacer | Clase |
|---|---|---|---|---|
| 116 | charla terminada en «, como tu» | «el mensaje me llegó cortado» | seguir la charla | lectura (detector de corte) |
| 118–121, 164–167, 209, 231 | frases de charla o comentarios sin pedido | «En eso no encuentro un pedido para mí; ¿necesitás algo?» | contestar la charla | lectura (guarda de «sin pedido») |
| 140 | «hablando de amor, pon una canción de amor en YouTube» | preguntó el tono | media.play.youtube con búsqueda «canción de amor» | lectura |
| 142–145 | «quiero una canción de amor» → BAXY «¿en Spotify?» → «no, en YouTube» | volvió a preguntar | unir con el pedido de 140 (YouTube ya dicho) | contexto |
| 154 | «¿sabés qué peli estoy viendo en PotPlayer?» | «no pude entender» | leer el título de la ventana y contestar | lectura |
| 156–161 | «estoy viendo Colony… investigala, quiero saber qué piensa la gente» / «investigala» | «no encuentro un pedido» ×4 | web.search reseñas de la película; «investigala» = anáfora | lectura + contexto |
| 181 | «¿cuál fue el primer libro de zombies?» | inventó un título | hechos datados → búsqueda antes de afirmar | conocimiento |
| 198 | «mutea mi micrófono» | «no entendí “mutea”, “microfono”» | audio.microphone.mute | lectura (verbo mutear; sin tilde no es desconocido) |
| 202 | «activalo» (tras silenciar el micrófono) | «no entendí “activalo”» | reactivar el micrófono | contexto |
| 214–219 | «baja el volumen» → «¿cuánto?» → «20» → «¿ajusto el volumen?» → «sí» → «no pude entender» | no unió la cantidad al pedido pendiente | bajar 20 | contexto |
| 222–223 | «ahora súbelo a 100» | «¿a qué cosa?» | «lo» = el volumen del turno anterior | contexto |
| 226 | «¿la nueva peli de Resident Evil es buena?» | «no tengo información actualizada» | web.search y resumen | lectura |
| 228–229 | «pues investigala, dime si tiene buenas o malas reseñas» | «¿sobre qué producto?» | tema de dos turnos atrás | contexto |
| 188–191 | «pero quiero que le hagas click» / «no lo hiciste» | «Claro, ya le hice click» (sin operación) / «¿podrías explicarme qué hiciste?» | nunca afirmar un efecto sin operación; reconocer que no se hizo | presentación (lo arregla el notebook) + lectura |

## Añadidos por las tandas del notebook

(la sesión del notebook añade filas aquí)
