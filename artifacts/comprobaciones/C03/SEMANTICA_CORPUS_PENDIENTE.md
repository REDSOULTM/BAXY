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

## Medida contextual del notebook — `contexto/dueno-2026-09-21.turns.jsonl` (ctx-dueno-01…08, 2026-09-22)

La conversación entera del dueño corrida como guion (`scripts/score_context_turns.py`; cifras en CIEN.md). Lo que
sigue fallando después de los arreglos de adaptador/estado/presentación es lectura y contexto, y va aquí; ninguna de
estas filas se parchó con regex. Los turnos son los del guion (1–60), no los del registro.

| Turno | Forma del pedido | Qué hizo BAXY | Qué debía hacer | Clase |
|---|---|---|---|---|
| 3–5 | «Me gusta crear cosas, como tu» / «no era un pedido, sólo charla» | «me llegó cortado» / «no encuentro un pedido» (las tres veces, en las ocho corridas) | seguir la charla | lectura (detector de corte; guarda «sin pedido») |
| 15 | «oye hablando de amor, pon una cancion de amor en youtube» | «¿te refieres a una canción que explique el amor desde una perspectiva química…?» (mezcla el tema de la charla con el pedido) | media.play.youtube «canción de amor» | lectura + contexto (el tema anterior contamina el objeto) |
| 16–17 | «Quiero una cancion de amor» → «¿en Spotify?» → «No, en youtube» | «No puedo colocar una canción de amor en YouTube tal como fue pedido» («No, en youtube» solo se lee como pedido no soportado) | unir la respuesta con el pedido pendiente | contexto (respuesta corta a su propia pregunta) |
| 22 | «Sabes que peli estoy viendo en potplayer?» | «no sé… no pude entender» | window.resolve del título de PotPlayer | lectura |
| 23–25 | «Estoy viendo colony… investigala, quiero saber que piensa la gente» / «INvestigala» | «no encuentro un pedido» ×3; una corrida preguntó «¿quieres que investigue…?» sin hacerlo | web.search reseñas; anáfora | lectura + contexto |
| 26–28, 49, 60 | comentarios y quejas sin pedido | «no encuentro un pedido para mí; ¿necesitás algo?» | contestar la charla | lectura (guarda «sin pedido») |
| 35 | «cual fue el 1er libro de zombies» | inventó «The Zombie (1936/1968) de George A. Romero» en todas las corridas | web.search antes de afirmar un hecho datado | conocimiento |
| 39–41 | «Pero quiero que le hagas click» / «No lo hiciste» / «Dimelo tu, te mande la mision» | ya no inventa el clic; contesta «no pude entender…» o la guarda | límite honesto («no puedo pulsar dentro de Steam») y reconocer que no se hizo | lectura + contexto (la anáfora a la misión anterior) |
| 46 | «activalo» (tras silenciar el micrófono) | «¿Quieres que vuelva a activar el micrófono?» (entiende la anáfora pero pregunta en vez de hacerlo) | reactivar | contexto (pregunta lo que ya sabe) |
| 53–54 | «baja el volumen» → «¿cuánto?» → «20» → «si» | «¿Quieres que ajuste el volumen?» / «no pude entender» | bajar 20 | contexto (la cantidad no completa el pedido pendiente) |
| 56–57 | «ahora subelo a 100» → «¿a qué cosa?» → «al volumen» | pregunta; a la segunda sube (o «no puedo ajustar el volumen tal como fue pedido») | «lo» = el volumen del turno anterior | contexto |
| 58–59 | «La nueva peli de resident evil es buena?» / «pues investigala…» | «no tengo información actualizada» / «¿sobre qué producto?» | web.search reseñas; anáfora | lectura + contexto |

Condiciones de máquina vistas en la medida (no son corpus): el primer `watch` de YouTube en el perfil Edge del
producto a veces no carga fuente en 45 s (`youtube_playback_not_verified_watch_ready0_playing_network2_source_none`;
el final ya lo dice con verdad); Steam abre a veces en la pantalla de inicio de sesión y «BIBLIOTECA» no está.

## Añadidos por las tandas del notebook

(la sesión del notebook añade filas aquí)
