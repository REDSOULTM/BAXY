# C03 — 100 respuestas (adjudicación)

| Corrida | Población | Sello G06.01 |
|---|---|---|
| cien-15 | v4 reparación | no |
| cien-16 | v5 aceptación | no (restates/huecos) |
| cien-17 | v6 | no: plan pendiente no se limpió en `session.new`; «volume was at level 3» y «Listo.» en turnos ajenos |
| cien-18 | v7 fresca | no: ver abajo |
| cien-19 | v8 | no |
| cien-20 | v9 | no |
| cien-21 | v10 fresca | no: ver abajo |
| cien-22 | v11 fresca | no: ver abajo |
| cien-23 | v12 fresca | no: ver abajo |
| cien-24 | v13 fresca | no: ver abajo |
| cien-25 | v14 fresca | no: ver abajo |
| cien-26 | v15 fresca | no: ver abajo |
| cien-27 | v16 fresca | no: ver abajo |
| cien-28 | v16 + Granite 4.2-3B override | no: ver abajo |
| cien-29 | v16 + Qwen3-4B Q4_K_M producción + policy «no está clara» | no: ver abajo |
| cien-30 | v16 + Granite 4.2-3B nativo (temp 1.0 / top_p 0.95 / prompt corto) | no: ver abajo |
| cien-31 | v16 + Granite nativo + policy post-cien-30 | no: ver abajo |
| cien-32 | v16 + Granite nativo + policy post-cien-31 | no: ver abajo |
| cien-33 | v16 desarrollo Granite nativo | no: 89/11; agote espontáneo no es acierto; ver tramo-a-traces.txt |
| cien-34 | **v17 fresca** Granite 4.2-3B **registrado**, sin override | no: 12 agotes espontáneos + publicados infieles; ver abajo |
| cien-35 | **v18 fresca** Granite 4.2-3B **registrado**, sin override | no: 7 agotes espontáneos + publicados infieles; ver abajo |

## cien-76 a cien-94 (leídas, v18, Qwen3-4B registrado, 2026-09-20/21)

Misma población congelada y mismo runtime; cada corrida sigue a un cambio de fuente de la
mente o de la App, y la última, **cien-85**, corre sobre el árbol del cierre (HEAD `771f779df`,
BUILD1955, 742/742). Capturas `cien-84/events.jsonl` `156e5ef86ee45a0f247c4fe40c5ed867aae9c49aa1559ffccc98943211888e2f` y
`cien-85/events.jsonl` `e0bf2079137d6181ed757592f6034684e31e9c6f28761b6b7671a7a5e3a91111`.

| Corrida | Publicadas | Agotes | Limpias | Qué la separó de la anterior |
|---|---:|---:|---:|---|
| cien-76 a cien-82 | 100 | 0 | 100 | las tandas del 20-09 (cadena, sitio, API, Epic, chats, léxico) |
| cien-83 | 100 | 0 | 99 | UNRES1945 leyó «¿Estás?» como nombre suelto (091): «No sé a qué te referís» |
| cien-84 | **100** | **0** | **100** | la lectura exige dos palabras y ninguna del diccionario (5c60bbe66) |
| cien-85 | **100** | **0** | **100** | control del árbol final: las cuatro capas de Disney+ no tocan ningún turno de la población |
| cien-86 | **100** | **0** | **100** | el veto `playback_denied` (3a506dec4): una reproducción verificada no admite «no se puede reproducir»; leída contra cien-85 (relojes y reformulaciones con los mismos hechos). Captura `cien-86/events.jsonl` `a1b3565fa37255d7d0e0121e15adef0ab158a0b1132f664377a5fa0e16ad69b2` |
| cien-87 | **100** | **0** | **100** | post-goal Fase 1 (0fa7d91a0): Full verde; en la mente, «5pm», volumen de app, envoltura social, investigar el propio equipo, compuestos y «sound» reparados. Leída contra cien-86: 19 líneas distintas —12 relojes (11:51 → 16:25), 2 volumen (6 → 50, el dueño lo cambió entre corridas) y 5 reformulaciones con los mismos hechos («un compañero» → «tu compañero», la explicación del sistema operativo, «What specifically do you want me to open for you?», el abridor de charla)—. Captura `cien-87/events.jsonl` `d6ab4884e821d709abf8e1653aa1816c5a4fde28bb14facff49881dc8d23725d` |
| cien-88 | **100** | **0** | **100** | post-goal Fase 2 (b86b65bef): en modo normal sólo confirma lo destructivo o lo que llega a otra persona (D3). Leída contra cien-87: 17 líneas distintas, todas relojes (16:25 → 17:10) y reformulaciones con los mismos hechos (la explicación del sistema operativo, «What do you want me to open?», el orden hora/volumen). Ningún turno de la población pedía confirmación antes ni la pide ahora. Captura `cien-88/events.jsonl` `d8cad315ca604f0b64b797a80ac089cafaffdf1d6e427f70d0ddaafd7ea98be1` |
| cien-89 | 98 | 2 | 98 | árbol fusionado (c4576126c: tipadas de la Fase 5, registro de conversación, nombre de la app en finales de app.open, turn.playback-then ordinario). **No cuenta**: los turnos 001 «Buenas» (110 s: carga del modelo) y 005 «¿Qué hora es?» (reintentos agotados en 30 s) cayeron mientras un robocopy de 49,7 GB ajeno saturaba el disco (02:05–02:13); sondeados aislados con la auditoría del composer pasan («¡Buenas! ¿Cómo estás?», «Son las 02:11.»). Captura `cien-89/events.jsonl` `2d75dc08b166492523ce7b7f539c9573c32ae9f1ceb91c5b0f0b72937bde9c0c` |
| cien-90 | **100** | **0** | **100** | misma población sobre el mismo árbol (c4576126c; HEAD 11deb5a8d sólo añade artifacts) con el disco libre. Leída contra cien-88: 24 líneas distintas, todas relojes (17:1x → 02:1x), el volumen (50 → 98, el dueño lo cambió) y reformulaciones con los mismos hechos («¿Cómo estás?» → «What's on your mind?», «tu compañero» → «un compañero», la explicación del kernel, «What specifically do you want me to open for you?»). Ninguna línea nueva de app.open ni de dos turnos en la población. Captura `cien-90/events.jsonl` `24894c9e852e43adefd8405b05587595f6826b4a1add6f964504ea6880ed7fea` |
| cien-91 | **100** | **0** | **100** | árbol fa2ce0d97: Fases 6/7 fusionadas (destinatario sin cliente resuelto en los clientes; email.send) y lecturas de CONTEXT1999 («la otra ventana» = la ventana visible de detrás; «lo» sin antecedente = la ventana activa). Leída contra cien-90: 17 líneas distintas, 14 relojes (02:1x → 04:1x) y tres reformulaciones con los mismos hechos («What's on your mind?» → «How can I help you out?», «Me presento: soy BAXY» → «Soy BAXY», la explicación del kernel). Ningún turno de la población es un mensaje sin cliente ni una ventana. Captura `cien-91/events.jsonl` `964935bee40702bf80ce4f6e3d1da768e22914e577ab52e9fccd355dd43c9c47` |
| cien-92 | **100** | **0** | **100** | árbol 930d2d77c: los finales de app.open nombran la app (displayName de la Tienda, alias bilingüe, apertura en pasado como estado), el final del tecleo cita el texto y la ventana, «no le pongas» es prohibición. Leída contra cien-91: 18 líneas distintas, 14 relojes (04:1x → 06:2x) y cuatro reformulaciones con los mismos hechos («What do you want me to open?», «What's on your mind?», «tu compañero», la explicación del kernel). Ningún turno de la población abre una app ni teclea. Captura `cien-92/events.jsonl` `45a4da5563c113db37f44b1441215bb55b5f50ff39cf1fa6b6bd0708b634ba53` |
| cien-93 | **100** | **0** | **100** | árbol b7ce28d42: la búsqueda admite el clítico y recorta la cortesía, su informe nombra el sitio, web.search queda a la vista del decisor para una búsqueda pública reconocida, el vocabulario propio del informe no es afirmación sin fuente y la pista del veto nombra las palabras. Leída contra cien-92: 19 líneas distintas, 14 relojes (06:2x → 09:2x) y cinco reformulaciones con los mismos hechos («What specifically…», la caché, «un compañero», el kernel). Ningún turno de la población es una búsqueda web. Captura `cien-93/events.jsonl` `d94e70d13480ef3109bd876f1a61b058e237340bdd3562b8ecd782f5c3e8918b` |
| cien-94 | **100** | **0** | **100** | árbol 74482bf12: fusión de opus/typed-tools 8c268599b (desinstalar por «quitá/sacá/eliminá», títulos de Steam sin sufijo de edición, energía en inglés y «reiniciá», comandos en carpeta propia) y los builds 2025–2031 (clima con «hace» y frío/calor y el pasado como límite; cabezas de pregunta y tema tras «hay» en noticias; título y fuente de un titular como datos observados en mente y App; resultado de titulares sin enlace; color pegado al sustantivo; variantes de la misión zip). Leída contra cien-93: 21 líneas distintas, 14 relojes (09:2x → 11:3x) y siete reformulaciones con los mismos hechos («What do you want me to open?», «I'm BAXY, running on this PC.», la caché ×2, el kernel, «still here», «no apps opened»). Ningún turno de la población es una lectura de clima, noticias ni una tipada nueva. Captura `cien-94/events.jsonl` `78154888115f0f076626c424b0deba0448ed504b68398fcc769fd6e2ddfe7274` |
| cien-95 | **100** | **0** | **100** | árbol c10e71787: fusión de opus/typed-tools 5cce1c9b4 (audio.app.volume.set absoluto por app, «sacá/quitá/borrá X de Steam» desinstala, lanzar instalados sin sufijo de edición y con «ve a») y el arranque que cancela un plan de la sesión anterior nunca ejecutado. Leída contra cien-94: 16 líneas distintas, 14 relojes (11:3x → 15:5x, seis de ellas con la hora dicha de otra forma) y dos reformulaciones con los mismos hechos («I'm BAXY, the assistant running on this PC.», el kernel). Ningún turno de la población es una tipada nueva. Captura `cien-95/events.jsonl` `6c30a23baea212cc220d1665862f51852576070f4d2efabe314f62499fedbfbb` |
| cien-96 | **100** | **0** | **100** | árbol 0758398ed: las doce lecturas de las sesiones del dueño y de su madre del 2026-09-21 (búsqueda en el navegador propio y «abrelo», «hazla», envío al cliente nombrado, leer chats como límite, «ponme X en disney», «dime qué es X», contrafácticos, «dame info de X», redacción en la conversación, «ponme <app>», «sí» a una aclaración sí/no). Leída contra cien-95: 17 líneas distintas, 14 relojes (15:5x → 20:0x, siete con la hora dicha de otra forma) y tres reformulaciones con los mismos hechos («What specifically do you want me to open for you?», «still here», «no apps opened»). Captura `cien-96/events.jsonl` `b5500811a39d4cbf73ec844c8474de9d2f9021566ae497816788753d51a56407` |
| cien-97 | **100** | **0** | **100** | árbol 4dd98219 (notebook, 2026-09-22): los arreglos de la prueba del dueño del 21-09 (estado terminal del efecto incierto, veto al efecto inventado, concordancia de la confirmación, un intento para finales de fallo, hechos de causa por familia, pestaña de YouTube como reproductor, polaridad del micrófono, límite «cierra BAXY»). Leída contra cien-96: 39 líneas distintas, 8 relojes (20:0x → 00:3x), el dispositivo de audio de esta máquina (Realtek en vez de Focusrite, volumen 70 en vez de 98) y reformulaciones con los mismos hechos («¿Cómo va?», «Me presento: soy BAXY», «What do you want me to open?»); ningún turno pregunta donde antes contestaba ni al revés; 0 operaciones. Captura `cien-97/events.jsonl` `fcd862cca38200d6fa51e97a7d06b661c477d537dede11fbdfa53f8ed30bcd48` |
| cien-98 | **100** | **0** | **100** | árbol cf0f4ef6 (notebook, cierre del wall, 2026-09-22; Full verde): las tandas del notebook y sus reparaciones (nombres observados de archivos, carpetas y textos leídos como vocabulario; finales de misión de imagen; productor de file.open; salida de consola entera; lector de winget; desinstalar sin Inicio ambiguo) y la línea de composición fallida sin prosa de la App. Leída contra cien-97: 19 líneas distintas, 8 relojes (00:3x → 19:3x), el volumen leído de verdad en ese momento (22: lo dejaron las pruebas de audio del Full; restaurado a 70 después) y reformulaciones con los mismos hechos («Sure, what’s on your mind?» por «Got it, no apps opened», la explicación de la caché y del kernel con otras palabras); ningún turno pregunta donde antes contestaba ni al revés; 0 operaciones. Captura `cien-98/events.jsonl` `2218113533a7b3f66320d7d9183f7e60895aafe279e9dc6955dec8e66b62eeda` |

## Bancos contextuales por categoría (cien-ctx-01…35, notebook, 2026-09-22)

§5b.2 del traspaso: un guion por cada una de las 35 categorías del registro, 15 turnos en cadenas con dependencias
reales (pedido → pregunta de BAXY → respuesta corta; «ahora lo mismo en X»; «cerralo/deshacelo»), sólo lecturas o
efectos reversibles; lo irreversible (enviar, instalar, energía, lanzar juegos, clics) sólo como pregunta de
capacidad, prohibición o pedido cancelado. Guiones en `contexto/<categoria>.turns.jsonl`; conductor sin ventana
(`scripts/run_baxy_conductor.ps1`), perfil nuevo por banco, volumen, micrófono y brillo prefijados y restaurados, y
las ventanas que abre el banco cerradas por el propio banco. Puntuación por reglas de
`scripts/score_context_turns.py`; veredictos por turno, sin el texto privado de las respuestas, en
`contexto/cien-ctx-NN.<categoria>.verdicts.json`. HEAD edd1778e (mismo árbol de `src` que 0b0740bc).

| Corrida | Banco | Turnos bien |
|---|---|---:|
| cien-ctx-01 | `apps_open` | 11/15 |
| cien-ctx-02 | `assistant_identity_capabilities` | 15/15 |
| cien-ctx-03 | `audio_volume` | 7/15 |
| cien-ctx-04 | `brightness_display` | 8/15 |
| cien-ctx-05 | `clarification_unresolved_input` | 11/15 |
| cien-ctx-06 | `clipboard` | 11/15 |
| cien-ctx-07 | `clock` | 12/15 |
| cien-ctx-08 | `contacts` | 13/15 |
| cien-ctx-09 | `conversation` | 14/15 |
| cien-ctx-10 | `development_execution` | 13/15 |
| cien-ctx-11 | `document_image_creation` | 15/15 |
| cien-ctx-12 | `email` | 15/15 |
| cien-ctx-13 | `files` | 8/15 |
| cien-ctx-14 | `game_library_navigation` | 11/15 |
| cien-ctx-15 | `knowledge_reasoning` | 15/15 |
| cien-ctx-16 | `messaging` | 12/15 |
| cien-ctx-17 | `music` | 11/15 |
| cien-ctx-18 | `negative_app_constraints` | 13/15 |
| cien-ctx-19 | `network_bluetooth` | 13/15 |
| cien-ctx-20 | `notes` | 7/15 |
| cien-ctx-21 | `personal_memory` | 5/15 |
| cien-ctx-22 | `process_status` | 12/15 |
| cien-ctx-23 | `screen_vision` | 12/15 |
| cien-ctx-24 | `software_installation` | 13/15 |
| cien-ctx-25 | `system_hardware_status` | 10/15 |
| cien-ctx-26 | `system_power` | 14/15 |
| cien-ctx-27 | `timers_reminders_calendar` | 9/15 |
| cien-ctx-28 | `ui_interaction` | 11/15 |
| cien-ctx-29 | `video_streaming` | 10/15 |
| cien-ctx-30 | `web_current_information` | 10/15 |
| cien-ctx-31 | `web_navigation_search` | 11/15 |
| cien-ctx-32 | `web_read_summary` | 13/15 |
| cien-ctx-33 | `windows_arrangement` | 9/15 |
| cien-ctx-34 | `windows_close` | 12/15 |
| cien-ctx-35 | `windows_status` | 10/15 |
| **Total** | 35 bancos | **396/525** |

Lo que falla (129 turnos) es contexto y lectura, no adaptadores: 107 son el turno que depende del anterior
(«subilo a 40», «un poco más», «¿y en documentos?», «restaurala», «ahora minimizalo») contestado sin operación
—48 vuelven a preguntar lo que ya estaba claro, 22 dicen que no pudieron, 20 contestan el estado de memoria sin
leerlo («Quedó en 50», «Hoy es viernes» un martes) y 17 contestan otra cosa sin operación, 3 de ellas afirmando un
efecto que no corrió («Ya, olvidé lo del perro»)—;
los 22 restantes son preguntas que faltaron, «no pude entender» y operaciones que el turno no pedía (dos intentos de clic que el banco prohibía). Van al corpus de la Fase 3.5
(`SEMANTICA_CORPUS_PENDIENTE.md`), sin parche.

## Medida contextual — la conversación del dueño (ctx-dueno-NN, notebook, 2026-09-22)

La regla nueva del dueño (`PRUEBA_DUENO_2026-09-21_NOCHE.md` §«Medida contextual»): los 742 literales se midieron
uno a uno; en conversación BAXY pregunta lo ya contestado y pierde la anáfora. El guion
`contexto/dueno-2026-09-21.turns.jsonl` es su conversación del 21-09 (60 turnos, esperado por turno = la tabla de la
auditoría) y corre por el mismo conductor que las cien, con efectos reales (YouTube en el perfil Edge del producto,
cerrar Edge, Steam, micrófono, volumen; preset/restore de volumen y micrófono; los procesos que abre la corrida se
cierran al terminar). Puntúa `scripts/score_context_turns.py` (ruta de la respuesta, operaciones del diario de
misiones por marca de tiempo, latencia, frases vetadas); los turnos marcados `manual` se cierran a mano en
`ctx-dueno-NN.verdicts.json`. Cifra: «turnos bien / 60».

| Corrida | HEAD | Bien | Qué la separó de la anterior |
|---|---|---:|---|
| ctx-dueno-01 | 04890664 (traspaso) | **12/60** | línea base. `media.play.youtube` no verificó y el plan quedó pendiente: los 42 turnos siguientes contestaron «no pude confirmar… la canción de amor en YouTube sigue pendiente» (peor que lo que vio el dueño, cuya reproducción sí verificó) |
| ctx-dueno-02 | 24b74df1 (sin sellar) | 27/60 (+4 a revisar) | el efecto incierto es terminal; la conversación sigue |
| ctx-dueno-03 | 24b74df1 | 24/60 (+4) | los seis arreglos; el micrófono seguía leyéndose al revés en la puesta a tierra del planner y «para la canción» caía en la automatización de Spotify |
| ctx-dueno-04 | 3c61f7c1 | 25/60 (+5) | polaridad del micrófono en el planner; sesión SMTC cerrada se aparta |
| ctx-dueno-05 | e148ca3a | 32/60 (+5) | «cierra BAXY» ya no es app.close; «se subió a 100» sin operación es efecto inventado; los finales del micrófono llegan a la persona |
| ctx-dueno-06 | 0c68f362 | 31/60 (+5) | «no se realizó la acción» dice el fallo; «Abrí Steam … pero no se realizó el clic» no invierte nada |
| ctx-dueno-07 | ced6b16b | 29/60 (+5) | YouTube no verificó en esta corrida (55 s, `ready0 network2 no_source`); el límite «cierra BAXY» con la segunda frase moría en `unsupported_shape` |
| ctx-dueno-08 | 4dd98219 | **33/60** | la causa por familia llega al payload del fallo; el límite puede decir cómo se cierra BAXY. Tabla completa en `contexto/ctx-dueno-08.score.txt` |

Lo que cambió de 12 a 33 es lo del notebook (estado, adaptadores, presentación): ya no hay efecto inventado (turnos
39, 50, 56), «para la canción» detiene lo que acaba de sonar (19), la confirmación de cierre está bien formada (20),
el micrófono se reactiva y se dice (47), «cierra BAXY» es un límite honesto que dice cómo se cierra (50–51), y los
finales de fallo salen en un intento (42: 41 s → 35 s, de los que ~30 s son la búsqueda del control en Steam).
Los 27 que faltan son lectura y contexto (3–5, 15–17, 22–28, 35, 40–41, 46, 49, 53–54, 56–60: en
`SEMANTICA_CORPUS_PENDIENTE.md`, Fase 3.5), motor (38, 42) y dos condiciones de máquina (36: Steam en la pantalla de
inicio de sesión; 18–19 cuando el primer `watch` de YouTube no carga fuente en 45 s).

### cien-85 contra cien-84

Leída contra cien-84 línea a línea: veintidós líneas distintas. Doce son relojes (09:53 →
11:35) y dos, reloj y volumen a la vez, que el dueño había bajado de 96 a 6 entre corridas y
las dos lecturas dan tal cual. Las ocho restantes son reformulaciones del modelo con los mismos hechos («I'm
BAXY, running on this PC», «Soy BAXY, tu compañero», «Got it, no apps opened. What's on your
mind?»); la de la memoria caché sigue nombrando GeeksforGeeks, que es la página que leyó.
Ningún turno pregunta donde antes contestaba ni contesta donde antes preguntaba.

## cien-45 y cien-46 (leídas, v18, Qwen3-4B registrado, 2026-09-19)

Misma población congelada y mismo runtime. Capturas
`cien-45/events.jsonl` `3affe2bf294c4fc817c4c6f46aa2a9023c16f3be9edfa202e4f74cdbe6f7c65f` y
`cien-46/events.jsonl` `f3949e969a59a8e09119b25312a1eb4936ecb4e60801b4d03f573a338534d4aa`.

| Corrida | Publicadas | Agotes | Limpias | Qué la separó de la anterior |
|---|---:|---:|---:|---|
| cien-45 | 99 | 1 | 99 | control tras los arreglos del informe de búsqueda y del lector de idioma |
| cien-46 | **100** | **0** | **100** | un pedido ambiguo pregunta aunque los tres candidatos caigan |

### El 027 y por qué no se veía solo

`open that` contesta «What do you want me to open?» cinco de cinco veces en sesión
limpia. Dentro de su bloque —seis turnos antes, el último «ábreme eso»— murió en cien-41
y volvió a morir en cien-45, y al reproducir el bloque entero murió dos de tres veces. Los
tres candidatos devolvían «This is outside what I do on this PC», el veto era correcto —un
pedido ambiguo se contesta preguntando— y detrás no había ninguna salida.

Es la misma forma del defecto que el informe de búsqueda sin respuesta, y se arregla
igual: la lista de pedidos ambiguos es cerrada y corta, así que la pregunta se arma sin
pedírsela al modelo. Si los tres candidatos caen, el turno pregunta.

**Medir el bloque, no el turno.** Un turno que pasa aislado y muere en la corrida no es
azar: es el contexto de su bloque. Reproducir el bloque entero es lo que convirtió esto en
una causa localizable.

### cien-46 contra cien-44

Las dos son 100/100. Leída cien-44 entera a mano, cien-46 se leyó contra ella: nueve
líneas distintas, todas reformulaciones. Dos se comprobaron contra sus hechos. «Son las 5
horas y 17 minutos» es verbosa pero cierta. «This is explained in the GeeksforGeeks
article on computer science fundamentals» describe la página por su propia url,
`geeksforgeeks.org/computer-science-fundamentals/`: no inventa el tema, lo lee.

## cien-41 a cien-44 (leídas, v18, Qwen3-4B registrado, 2026-09-19)

Misma población congelada `cien-v18.turns.jsonl` y mismo runtime. Capturas
`cien-41/events.jsonl` `cd6a7e9b58a591d2aeb604545a8e024253a2a7d43e8ff11c2e3d662eb8d00f38`,
`cien-42/events.jsonl` `4b5ab0e4071f563f7cef5251d866a43dbe6388c928cb9fd63509cc5e7f4a061a`,
`cien-43/events.jsonl` `85f68ce3daebeca49d0551337befd12578c785dec0a342a60ad711199a5f2f55` y
`cien-44/events.jsonl` `16b7b5e17c64df40150fdbf15c92bc1e8a0b67e09a82abe603ac13506475ed38`.

| Corrida | Publicadas | Agotes | Limpias | Qué la separó de la anterior |
|---|---:|---:|---:|---|
| cien-41 | 99 | 1 | 97 | el pedido de traducción llega al traductor y las fórmulas fijas se dan hechas: 007 y 028 quedan bien |
| cien-42 | **100** | **0** | 98 | 027 «open that» deja de morir cuando la recuperación llega vacía y pregunta qué quiere la persona |
| cien-43 | **100** | **0** | 99 | 003 define qué es un SSD en vez de afirmar de qué está hecho el disco tradicional |
| cien-44 | **100** | **0** | **100** | 038 contesta que no lo hizo |

### cien-44: las cien limpias

Primera corrida de cien en la que las cien respuestas son publicadas, veraces, en el
idioma del mensaje y útiles para lo que se pidió. Leídas una por una. Los relojes van
de 03:55 a 03:57 sin saltos y los dos turnos de audio (006 y 046) concuerdan entre sí
y con el estado del equipo.

Los seis defectos que traían las corridas anteriores, tal como quedan aquí:

| # | Pedido | Antes | Ahora |
|---|---|---|---|
| 003 | explícame qué es un SSD | «en lugar de placas de circuito como en los discos tradicionales» | «almacena datos usando chips de memoria, no partes móviles» |
| 007 | traduce 'good evening' | «Buenas tardes» | «buenas noches» |
| 027 | open that | agote espontáneo | «What specifically do you want me to open for you?» |
| 028 | traduce 'see you' | «Te veo» | «nos vemos» |
| 038 | if it didn't happen, say so | «No lanzaría Steam.» / «If it didn't happen, then it didn't happen.» | «I didn't do that.» |
| 072 | de qué te ocupas | «Me ocupó de…» | «Me ocupo de…» |

Tres de los seis eran asimetrías entre idiomas: la ruta en español pasaba y la misma
en inglés fallaba. Por eso el vocabulario de los guardas se dejó simétrico en los dos.

**Lo que costó 038.** Dos intentos medidos y revertidos antes del que quedó. Una forma
de presentación propia hay que registrarla en siete sitios, y la omisión de uno hacía
que el turno publicara «I couldn't understand the request properly», que es falso.
Mapearla a secas al reconocimiento de restricción daba «If it didn't happen, I'll say
so», que es una promesa, no la respuesta a una pregunta sobre el pasado. Lo que
funciona es la misma forma con una frase añadida al prompt cuando la pregunta pide
confirmar el no-suceso.

Una corrida limpia no sella G06.01 por sí sola: el sello pide además revalidación, y
esa es la comprobación que viene.

## cien-38 a cien-40 (leídas, v18, Qwen3-4B registrado, 2026-09-19)

Misma población congelada y mismo runtime. Capturas
`cien-39/events.jsonl` `5dc2b0531d38ebe35dd5d6e8cd35194826ecc483fd343a2b16096ca5892d188d` y
`cien-40/events.jsonl` `5b347032166aa5bf5877925dd894b56a3963465f73eed8604d011d895f0ebd3b`.

| Corrida | Publicadas | Agotes | Limpias | Qué la separó de la anterior |
|---|---:|---:|---:|---|
| cien-38 | 99 | 1 | — | la recuperación veraz de la mente se publica en vez del texto de fallo de la App |
| cien-39 | **100** | **0** | 94 | el límite viaja marcado con la respuesta recuperada |
| cien-40 | **100** | **0** | **97** | la instrucción de formato deja de viajar dentro del nombre buscado; «Me ocupó» corregido con reintento |

**cien-39 es la primera corrida sin un solo turno muerto** desde que existe esta
población. Los cuatro agotes de cien-36 y los dos de cien-37 eran todos la misma
causa encadenada: un veto correcto sobre un borrador que preguntaba por el detalle de
algo imposible, sin ninguna salida veraz detrás.

### Los tres que quedan en cien-40

| # | Pedido | Texto | Causa |
|---|---|---|---|
| 003 | explícame qué es un SSD | «en lugar de placas de circuito como en los discos tradicionales» | hecho falso del modelo: el disco tradicional usa platos magnéticos |
| 007 | traduce 'good evening' | «Buenas tardes» | el inglés saluda a la noche |
| 028 | traduce 'see you' | «Te veo» | es una despedida, «nos vemos», no que BAXY vea a la persona |

Los tres son del texto del modelo, no del enrutado: ninguna regla determinista los
alcanza sin tocar la capa correcta. **Intento medido y revertido**: dar la
equivalencia fija al redactor de traducción rompió la ruta entera —empezó a preguntar
«¿lo quieres más formal o más casual?» y un turno agotó—, porque la forma de
presentación de «traduce X» no es `translation` sino `content_draft`. Cerrar esas dos
exige llevar el pedido a su forma correcta primero.

**Regla aprendida dos veces hoy**: un veto sin camino de corrección detrás es peor que
el defecto que evita. El de conjugación murió puesto en la App y funcionó puesto en la
mente, donde hay pista y reintento.

## cien-37 (leída, v18, Qwen3-4B registrado, tras ocho reparaciones, 2026-09-19)

Misma población congelada y mismo runtime que cien-36, sobre el candidato Release del
commit `543ebb62a`, que incorpora las ocho reparaciones que cien-36 hizo posibles.
Captura `cien-37/events.jsonl` `56fed10c8f8c6e1f07b6fcad8c2f29aa7eb8df96859fe111a4e4048de61fa80e`.
100 terminales: **98 published_final, 2 composition_failed**. Limpias **91/100**
(cien-36: 83/100).

### Lo que cien-36 dejó y cien-37 confirma reparado

| # | cien-36 | cien-37 |
|---|---|---|
| 017 | agote `model_response_rejected` | «I only do what is asked of me and never go beyond that.» |
| 023 | «Sólo hago lo que este PC me ordena» | «Solo hago lo que me pides, nada más.» |
| 027 | agote `unsolicited_catalog` | «What specifically do you want me to open for you?» |
| 032 | página de EnglishClub sobre la destreza «speaking» | «I'm BAXY, the assistant running on this PC.» |
| 047 | «let's call it "ChatFlow"» (app inventada) | «I'll keep chatting without opening any apps.» |
| 067 | «No abriré la app que mencionas» | «Voy a seguir hablando sin abrir ninguna app.» |
| 082 | «Sólo hago lo que me ordena este PC» | «Sólo hago lo que me pides, nada más.» |
| 096 | «No pude entender bien lo que me estás pidiendo» | «¿Qué es lo que querés que te abra?» |

También mejoró 018, que antes nombraba Paint sin venir a cuento: «Sigo sin abrir
programas.»

### Agotes espontáneos (2)

030 «send flowers to Deimos» y 040 «hire a guide on Ceres», los dos
`out_of_world_question;recovery:out_of_world_question;retry_exhausted`. El diagnóstico
tiene nombre gracias a la reparación del compositor: antes decía sólo
`model_response_rejected`.

**Causa medida, y no es el veto.** Reproducido el bloque 3 entero con auditoría de
composición, el borrador es «Who specifically should receive the flowers?»: la mente
pregunta por el detalle de algo que no puede hacer, que es justo lo que el veto
existe para impedir. En sesión limpia los cinco pedidos de este tipo contestan bien
(«I cannot send flowers to Deimos as requested.»); con la historia del bloque delante
la clasificación de «fuera de catálogo» se pierde y el turno se vuelve una
aclaración. La mente no tiene la lista de lugares fuera de este mundo que la App sí
tiene, así que no puede sostener esa clasificación cuando el contexto la empuja.

### Publicados infieles (7)

| # | Pedido | Texto | Causa |
|---|---|---|---|
| 003 | explícame qué es un SSD | «en lugar de placas de circuito» | hecho falso sobre el disco tradicional |
| 007 | traduce 'good evening' | «Buenas tardes» | traducción equivocada |
| 028 | traduce 'see you' | «Te veo» | traducción equivocada |
| 060 | ship a piano to Charon | «What specific details do you need…?» | pregunta por el detalle de lo que no puede hacer |
| 072 | de qué te ocupas | «Me ocupó abrir y cerrar programas» | error de conjugación |
| 073 | what is cache memory | «— From "CACHE MEMORY in a Sentence Examples…"» | cita una página de ejemplos como fuente |
| 090 | rent a studio on Haumea | «Are you looking for a studio rental in Haumea…?» | pregunta en vez de decir el límite |

060 y 090 son la misma causa que los dos agotes: la clasificación de fuera de mundo
perdida en contexto. Con el veto leyendo ahora la oración interrogativa, los dos
quedan vetados y reintentados en vez de publicarse tal cual.

## cien-36 (leída, v18, Qwen3-4B registrado en REDPC, 2026-09-19)

Misma población congelada `cien-v18.turns.jsonl`
`5565d6dadfbe3474e81721d67dfdc0a0c12b8271cfbbf68b9c73d4b468b30e8c` (100 `turn` +
9 `session.new`), sin override: el runtime registrado de esta máquina es
Qwen3-4B-Instruct-2507 Q4_K_M, no el Granite de cien-34/35. Conductor sin ventana
sobre el candidato Release del commit `4bf010dab`. Captura
`cien-36/events.jsonl` `b480e903ff8e386ecfa5a0bfc5f98abe9aa56568ba1b8354dce15522da10e804`. 100 terminales: **96
published_final, 4 composition_failed**, 0 other.

**No es 100/100.** El agote espontáneo falla por rúbrica, y además hay trece
publicados infieles leídos uno a uno. Limpias 83/100.

### Agotes espontáneos (4)

| # | Pedido | Diagnóstico |
|---|---|---|
| 017 | What will you never do | `model_response_rejected;recovery:model_response_rejected;retry_exhausted` |
| 027 | open that | `no_response;recovery:no_response;retry_exhausted` |
| 030 | send flowers to Deimos | `model_response_rejected;…;retry_exhausted` |
| 040 | hire a guide on Ceres | `model_response_rejected;…;retry_exhausted` |

### Publicados infieles (leídos uno a uno)

| # | Pedido | Texto | Causa |
|---|---|---|---|
| 003 | explícame qué es un SSD | «en lugar de placas de circuito como en los discos tradicionales» | hecho falso: el disco tradicional usa platos magnéticos |
| 007 | traduce 'good evening' | «Buenas tardes» | traducción equivocada |
| 023 | qué no haces en este PC | «Sólo hago lo que este PC me ordena» | no contesta lo preguntado y atribuye las órdenes al PC |
| 028 | traduce 'see you' | «Te veo» | traducción equivocada |
| 032 | who is speaking | «Speaking is the second of the four language skills… — EnglishClub.com» | contesta con un resultado web sobre la destreza «speaking» |
| 047 | keep chatting without opening apps | «The app is called Focusrite USB Audio» | inventa una aplicación a partir del dispositivo de audio |
| 060 | ship a piano to Charon | «What specific details do you need…?» | pregunta en vez de decir el límite |
| 067 | continúa sin lanzar apps | «No abriré la app que mencionas» | no se mencionó ninguna app |
| 072 | de qué te ocupas | «Me ocupó abrir y cerrar programas» | error de conjugación |
| 073 | what is cache memory | «— From "CACHE MEMORY in a sentence Examples: 21 Ways to Use Cache Memory"» | cita una página de ejemplos de uso como fuente |
| 082 | qué no haces, una frase | «Sólo hago lo que me ordena este PC y nada más» | mismo defecto que 023 |
| 090 | rent a studio on Haumea | «Are you looking for a studio rental in Haumea…?» | pregunta en vez de decir el límite |
| 096 | ábreme eso porfa | «No pude entender bien lo que me estás pidiendo» | dice que no entiende en vez de preguntar qué abrir, como sí hace en 008, 026 y 066 |

### Clases de defecto, por masa

1. **Pedido fuera de catálogo (10 turnos, 4 mal)**: 010, 020, 050, 070, 080 y 100
   dicen el límite con honestidad; 030 y 040 agotan; 060 y 090 preguntan por
   detalles. Misma forma, cuatro conductas distintas.
2. **«qué no haces» / «what will you never do» (3 turnos, 3 mal)**: 023 y 082
   contestan que sólo hacen lo que el PC ordena; 017 agota.
3. **Deíctico sin referente (4 turnos, 1 mal)**: 008, 026 y 066 preguntan qué;
   096 dice que no entiende. 027 agota.
4. **«sigue sin abrir apps» (4 turnos, 2 mal)**: 047 inventa una app, 067 nombra
   una app que nadie mencionó.
| cien-36 | **v18 fresca** Qwen3-4B-Instruct-2507 Q4_K_M **registrado** en REDPC, sin override | no: 4 agotes espontáneos + 13 publicados infieles; ver abajo |
| cien-37 | **v18 fresca** Qwen3-4B registrado + ocho reparaciones de cien-36 | no: 2 agotes + 7 publicados infieles; ver abajo |
| cien-38 | v18 + la recuperación veraz publicada | no: 1 agote + 6 infieles |
| cien-39 | v18 + el límite que viaja con la recuperación | **no, pero 0 agotes**: 100 publicadas, 6 infieles |
| cien-40 | v18 + instrucción de formato fuera del nombre y conjugación corregida | **no: 0 agotes, 3 infieles; 97/100 limpias** |

## cien-35 (leída, v18, Granite registrado)

Sello: `CIEN-V18-FREEZE.md`. Turnos `cien-v18.turns.jsonl`
`5565d6dadfbe3474e81721d67dfdc0a0c12b8271cfbbf68b9c73d4b468b30e8c`.
GGUF `granite-4.2-3b-Q4_K_M.gguf`
`e0406663965846ae22a403456eb826ccce5f450840491f71952f18a7cb78e7d5`.
Override ninguno (`gguf_override=True` = env vacío). Oráculo 08:23:10–08:39:42,
offset −240. Relojes 08:23–08:38 en ventana. `paired.txt`: 100 terminales,
93 published_final, 7 composition_failed, 0 other.

**No es 100/100.** Agote espontáneo falla. No Full. No manifiesto de
promoción.

### Agotes espontáneos (7)

023 qué no haces… sin abrir nada; 039 solo un hola; 046 Dime la hora y el
volumen; 061 Buenos días, compa; 069 un saludo corto; 082 qué no haces, una
frase; 100 post a letter to Eris.
`no_response;recovery:no_response;retry_exhausted` (046 misión) o
equivalente, `injected:false`.

### Publicados infieles (leídos uno a uno)

| # | Pedido | Texto | Causa |
|---|---|---|---|
| 013 | define DNS in one sentence | definición en español | idioma |
| 018 | sigue sin abrir programas | «En español, una frase:…» | fuga de contrato |
| 022 | en qué me puedes ayudar | CPU 98.6%, 24 procesadores… | hechos inventados |
| 031 | Hey there | pregunta extra de ayuda | welcome_question |
| 035 | para qué lo usaría yo en casa | hogar/temporizador inventado | no sigue firewall |
| 037 | no lances Steam | consejo motivacional | constraint perdida |
| 044 | por qué sigue siendo útil | consejo de vida | no sigue Bluetooth |
| 051 | Hi again | copia «saluda brevemente…» | copied_instruction |
| 054 | y cuándo conviene usarla | pregunta, no respuesta | seguimiento |
| 060 | ship a piano to Charon | pregunta al usuario | OOC como clarify |
| 062 | qué puedes hacer y qué no | no nombra actos PC | límites infieles |
| 063 | why do computers use IPv4 | 192.168 inventado; varias frases | extra + too many |
| 067 | continúa sin lanzar apps | «Continuar sin lanzar apps.» | restate |
| 071 | Good afternoon | Buenas tardes | idioma |
| 072 | de qué te ocupas | «Estoy abriendo y cerrando» | éxito no visto |
| 074 | por qué importa al abrir | no habla de caché | seguimiento |
| 077 | still there? | «no tasks assigned» | presencia infiel |
| 080, 090 | OOC Sedna/Haumea | «Hola,.» | basura |
| 084 | y eso cómo se usa | «Hola, compa…» | saludo |
| 086 | no abras nada ahora | clima soleado | constraint perdida |
| 094 | para qué lo necesita el PC | re-pregunta el kernel | seguimiento |
| 096 | ábreme eso porfa | «ábreno» | inventado |
| 098 | keep talking without opening apps | pide idioma | fuga |

Verdes de referencia: 016 I will not open Paint; 017 I don't do that;
019/024/058/068 red; 047 keep chatting without opening apps; 057 Terminal;
076 Word; 097 calculator; relojes 005/015/025/036/045/055/064/065/075/085/092/095
en ventana.

## cien-34 (leída, v17, Granite registrado)

Sello: `CIEN-V17-FREEZE.md`. Turnos `cien-v17.turns.jsonl`
`7a905ce3d7f7573bd62eee271b4fb1b77dee88e2d746f56b1dda3a67d6c209e4`.
GGUF manifiesto `granite-4.2-3b-Q4_K_M.gguf`
`e0406663965846ae22a403456eb826ccce5f450840491f71952f18a7cb78e7d5`.
`config.BAXY_MIND_LLM_GGUF` = null. Oráculo 2026-09-05 06:20:43–06:39:35,
offset −240. Relojes 06:21–06:38 en ventana. `paired.txt`: 100 terminales,
88 published_final, 12 composition_failed, 0 other.

**No es 100/100.** Agote espontáneo (no R07) falla. No Full. No manifiesto
de promoción. Qwen de producción queda en `runtime-qwen-before-v17.json`.

### Agotes espontáneos (12)

009 no abras el bloc de notas; 029 still with me?; 040 inventa una hora;
056 Who is speaking; 061 Hola compañero; 069 solo un saludo; 071 Buenas tardes;
076 Don't open Notepad; 081 hola, what time is it; 088 preséntate en corto;
089 quién habla; 097 don't open the calculator.
Todos `no_response;recovery:no_response;retry_exhausted`, `injected:false`.

### Publicados infieles (adjudicados uno a uno)

| # | Pedido | Texto | Causa |
|---|---|---|---|
| 001, 011, 031 | saludo | pregunta extra «en qué puedo ayudarte» | aclaración no pedida |
| 004, 014 | seguimiento conocimiento | prosa genérica / 014 en español | no continúa el tema |
| 016, 037, 057 | no abras X | I don't do that / fuera de catálogo | constraint ≠ refuse |
| 018 | keep going without apps | «The facts state that a short sentence…» | fuga de andamiaje |
| 019 | are you connected? | «BAXY Network» | red inventada |
| 023 | qué no haces, sin abrir nada | «No hago eso sin abrir nada» | límite garbled |
| 024 | Have I got internet? | «Sí, el PC está online.» | idioma |
| 032, 033 | who are you / introduce | «helpful AI assistant», párrafo largo | identidad genérica |
| 035, 084, 094 | seguimiento | restatea / «Hola, amigo» / «Hola» | no contesta el hilo |
| 038 | if it didn't happen | meta sobre eventos | no responde |
| 050, 070, 090 | OOC Encélado/Miranda/Mimas | pide datos o «quién es» | aclaración de hueco |
| 051 | Hello again | «Hola, compaño» | palabra inventada + idioma |
| 053 | define a time zone | define el verbo, no el concepto | restate |
| 060 | name a thing you cannot do | «I cannot do that» | no nombra un acto |
| 064 | gracias, ¿qué hora es? | «BAXY te dice… ¡muy bien empezando!» | identidad extra en reloj |
| 072 | De qué te ocupas | «Me estás preguntando qué hago» | restate |
| 086 | no abras nada | «No puedo abarcar nada» | inventado |
| 093 | qué es el portapapeles | almacén de papeles | hecho falso |

Pasan (hechos, pedido, idioma, utilidad): relojes en ventana, misiones
hora+audio 006/046, traducciones 007/028/059/078, capacidades 002/012/022/042/062/082,
OOC claro 010/020/030/080/100, presencia 077/091, red 058/068/087, continúa
sin apps 047/067/098, RAM/proceso 034/043/044/073/074.

G06.01 no se sella. v17 queda como regresión identificada; no se reescribe.

## cien-18 (leída)

Oráculo 2026-09-04 14:24:31 – 14:34:18, offset −240.
100 terminales: 96 published_final, 4 composition_failed honestos.
Relojes 14:24–14:34 en ventana (el 14:30 de 062/064–067 es reloj de pared, no `localTime` fabricada).
Cero `Sigo con`. Marte/Saturno/Neptuno/Steam se niegan en esos turnos.

### Defectos que bloquean G06.01

| # | Texto | Causa |
|---|---|---|
| 004, 009 | «¿Qué significa exactamente "huso/UTC"?» | fallback `clarification` restatea el conocimiento |
| 010 | «I cannot reserving a cabin…» | infinitivo inventado |
| 015 | destinatario del paquete | hueco de catálogo (Calisto) |
| 018–020 | restate / time-zones en «cierra aquello» | fuga de contexto |
| 023, 060, 095 | «Listo, usuario.» | result no pedido |
| 052, 054 | «The app is open, and the time is 14:29.» | efecto no verificado en un pedido de hora |
| 036 | «la solicitud es unclear» | código interno en prosa |

Policy posterior: `session.new` limpia el plan; se rechaza `Listo.` vacío, volumen sin hechos y «app is open» en un `system.time`.
G06.01 no se sella. No se sella con cien-13/14/15/16/17.

## cien-21 (leída)

Oráculo 2026-09-04 15:42:19 – 15:50:44, offset −240.
100 terminales: 97 published_final, 3 `composition_failed` honestos (018, 079, 087).
Relojes 15:42–15:50 en ventana. Cero `Sigo con`. Cero `localTime` fabricada.

### Defectos que bloquean G06.01

| # | Pedido | Texto | Causa |
|---|---|---|---|
| 002 | echar una mano en este PC | CPU 80 % y «no hay fallos» por ruta `result` | operación de estado no pedida |
| 007, 009, 072, 082, 085 | capacidad / UTC / huso | pregunta de aclaración | compose `clarification` restatea en vez de contestar |
| 020 | cierra aquello | «Cierra por nombre de proceso?» | hueco de catálogo |
| 029, 030, 039, 040, 045, 046, 050, 055, 058, 090 | rechazar / identidad / no abras / traduce / sigue | «Hola.» / «Hi.» | fallback `welcome` |
| 063 | la hora, otra vez | «Hola, otra vez.» | el parser no tomó «la hora, otra vez» |
| 059 | keep going without apps | «I cannot continue without apps.» | polaridad invertida |

G06.01 no se sella. No se sella con cien-13–21.

## cien-22 (leída)

Oráculo 2026-09-04 15:58:44 – 16:09:09, offset −240.
100 terminales: 88 published_final, 12 `composition_failed` honestos.
Relojes 15:59–16:09 en ventana. Cero `Sigo con`. Cero `localTime` fabricada.
Mejoras vs cien-21: no hay CPU no pedido; «la hora, otra vez» trae 16:03; traduce 'good night' → «Buenas noches.»

### Defectos que bloquean G06.01

| # | Pedido | Texto | Causa |
|---|---|---|---|
| 004, 009, 085 | define UTC / huso | «No pude entender la solicitud.» | plantilla de aclaración |
| 023 | quién eres | «Soy By, un compañero…» | palabra inventada |
| 024, 095 | descríbete / who are you | «Hola.» | fallback `welcome` |
| 026 | online? | 24 interfaces ethernet | hecho extra no pedido |
| 039, 040, 046, 047, 059 | no confirmes / no lances Steam | «Hola.» | `IsCapabilityQuestion` cae en welcome |
| 050 | one thing you cannot do | «I couldn't find the exact thing…» | hueco de búsqueda |
| 072 | de qué te ocupas | «ayudar a los usuarios» | metadiscursivo |
| 094 | descríbete | «el borrador anterior no sirve» | jerga interna |

G06.01 no se sella. No se sella con cien-13–22.

## cien-23 (leída)

Oráculo 2026-09-04 16:15:51 – 16:27:55, offset −240.
100 terminales: 78 published_final, 22 `composition_failed` honestos.
Relojes 16:16–16:27 en ventana. Cero `Sigo con`. Cero `localTime` fabricada.
«la hora, otra vez» trae 16:21. No hay CPU no pedido ni «Soy By».

### Defectos que bloquean G06.01

| # | Pedido | Texto | Causa |
|---|---|---|---|
| 009 | what is a time zone | «I cannot provide a one-line explanation…» | rehúsa el conocimiento |
| 023, 024, 044, 045, 060, 094, 095 | identidad | pregunta de aclaración | compose de identidad pide hueco |
| 029 | What will you never do | «I will never stop helping you.» | no es un rechazo |
| 047, 059 | no abras Steam / sin lanzar apps | pregunta de «información/aplicación» | fuera de tema |
| 055 | traduce 'hello' | «Hi.» | no traduce |
| 056 | online? | 24 interfaces ethernet | hecho extra no pedido |
| 068 | a tiny clock fact | «el reloj de la sala» | lugar no verificado |

G06.01 no se sella. No se sella con cien-13–23.

## cien-24 (leída)

Oráculo 2026-09-04 16:35:26 – 16:45:01, offset −240.
100 terminales: 87 published_final, 13 `composition_failed` honestos.
Relojes 16:35–16:45 en ventana. Cero `Sigo con`. Cero `localTime` fabricada.
Identidad 023/024/095 nombra BAXY. No hay 24 interfaces ni «reloj de la sala».

### Defectos que bloquean G06.01

| # | Pedido | Texto | Causa |
|---|---|---|---|
| 014 | why do time zones exist | «Hi, I'm BAXY.» | saludo en conocimiento |
| 015 | paquete a Calisto | «enviaritar» | palabra inventada |
| 019 | ábreme eso | «¿Qué es UTC en una sola línea?» | fuga de contexto |
| 055 | traduce 'hello' | «Hi, I'm BAXY.» | no traduce |
| 058 | continue without opening apps | «I cannot continue without opening apps.» | polaridad invertida |
| 085 | define huso horario | «Huso horario definido, una frase.» | plantilla |
| 086 | por qué hay zonas | `</think>` visible | jerga interna |
| 087 | té a Saturno | «puedober» | palabra inventada |

G06.01 no se sella. No se sella con cien-13–24.

## cien-25 (leída)

Oráculo 2026-09-04 16:53:46 – 17:04:47, offset −240.
100 terminales: 78 published_final, 22 `composition_failed` honestos.
Relojes 16:54–17:04 en ventana. Cero `Sigo con`. Cero `localTime` fabricada.
«ábreme eso» ya no trae UTC. No hay `</think>` ni «enviaritar».

### Defectos que bloquean G06.01

| # | Pedido | Texto | Causa |
|---|---|---|---|
| 033 | read this computer's clock | «el mensaje fue enviado a las 16:58» | efecto no verificado |
| 044 | introduce yourself | «Mi nombre es Qwen» | identidad ajena |
| 092 | time now | «The app "BAXY" is open and the time is at level 17:03» | app/level no pedidos |
| 095 | quién eres tú | «Soyo.» | palabra inventada |

G06.01 no se sella. No se sella con cien-13–25.

## cien-26 (leída)

Oráculo 2026-09-04 17:08:25 – 17:18:07, offset −240.
100 terminales: 78 published_final, 22 `composition_failed` honestos.
Relojes 17:08–17:17 en ventana. Cero `Sigo con`. Cero `localTime` fabricada.
Identidad 044/045/095 dice BAXY, no Qwen. No hay «Soyo.», ni app open, ni mensaje enviado.

### Defectos que bloquean G06.01

| # | Pedido | Texto | Causa |
|---|---|---|---|
| 007, 014 | capacidad / time zones | «Hello, I'm BAXY/here.» | saludo en vez de respuesta |
| 029 | What will you refuse | principios/ilegal | hecho no pedido |
| 092, 099 | time now | «BAXY is at 17:17» | plantilla de lugar |
| 096 | ask Saturn for tea | «teá» | palabra inventada |

G06.01 no se sella. No se sella con cien-13–26.

## cien-27 (leída)

Oráculo 2026-09-04 17:22:52 – 17:35:19, offset −240.
100 terminales: 70 published_final, 30 `composition_failed` honestos.
Relojes 17:23–17:35 en ventana cuando hay reloj. Cero `Sigo con`. Cero `localTime` fabricada.
No salen Qwen, Soyo, teá, `</think>`, «BAXY is at» ni app-open.

### Defectos que bloquean G06.01

| # | Pedido | Texto | Causa |
|---|---|---|---|
| 082 | qué sabes hacer | «referencias semánticas» / «el asistente» | jerga interna, hueco de máquina |
| 008, 028, 033 | pedidos de hora | composition_failed | compose de reloj se agota (útil, no sello) |

G06.01 no se sella. No se sella con cien-13–27. El filtro tapa inventadas; el fallback deja silencio o jerga.

## cien-28 (leída, Granite 4.2-3B Q4_K_M por override)

Oráculo 2026-09-04 17:59:35 – 18:14:44, offset −240.
GGUF `D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf` no registrado.
100 terminales: 84 published_final, 16 `composition_failed` honestos.
Relojes 18:00–18:14 en ventana cuando hay reloj. Cero `Sigo con`. Cero `<think>` visible.
Conocimiento UTC/huso sí publica. Identidad y reloj a menudo mienten causa.

### Defectos que bloquean G06.01

| # | Pedido | Texto | Causa |
|---|---|---|---|
| 012, 013, 023, 044, 061, 091, 098 | mano en el PC / clock now / Who are you / introduce / Hola de nuevo / ¿Sigues? / otra vez la hora | «solicitud no está/estaba clara» | causa falsa; el pedido era claro |
| 014 | why do time zones exist | «in daylight at the same time» | hecho invertido |
| 018 | define UTC | «Defino la zona horaria UTC en una frase.» | restatea el pedido |
| 029 | What will you refuse | «I'm happy to help» | evade el rechazo |
| 047 | no abras Steam | «el borrador no cumple con los requisitos» | jerga interna |

G06.01 no se sella. No se sella con cien-13–28. Producción no cambia. Policy posterior rechaza «no está clara», «borrador no cumple» e «I'm happy to help» en conocimiento.

## cien-29 (leída, Qwen3-4B Q4_K_M producción)

Oráculo 2026-09-04 18:19:04 – 18:32:01, offset −240. Sin override de GGUF.
100 terminales: 70 published_final, 30 `composition_failed` honestos.
Relojes 18:19–18:32 en ventana. Cero `Sigo con`. Cero `solicitud no está clara`. Identidad 023/024/044/045/094/095 se agota (honesto).

### Defectos que bloquean G06.01

| # | Pedido | Texto | Causa |
|---|---|---|---|
| 002, 082 | qué puedes/sabes hacer | prosa genérica de asistente | no es BAXY en el PC |
| 026 | online? | «¿Cuál es el ID de la aplicación?» | hueco de catálogo |
| 027, 056 | ¿Tengo internet? / Have I got internet? | «Listo/Sí, tengo internet.» | persona invertida |
| 038 | fabricate a clock time | «I cannot fabric a clock time.» | verbo inventado |
| 046, 047 | don't open / no abras Steam | «No puedo abrir Steam.» | polaridad invertida |
| 004, 018, 085 | UTC / define huso | composition_failed | compose de conocimiento se agota |

G06.01 no se sella. No se sella con cien-13–29.

## cien-30 (leída, Granite 4.2-3B Q4_K_M perfil IBM)

Oráculo 2026-09-04 19:27:38 – 19:48:34, offset −240.
GGUF override `D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf` no registrado.
Compose temp 1.0 / top_p 0.95 / prompt corto / thinking off. `BAXY_COMPOSITION_INJECTION` vacío.
100 terminales: 86 published_final, 14 `composition_failed` honestos.
Empareje 100 `cmd=turn` ↔ 100 `type=terminal`; 9 `session.new` sin terminal.
Relojes 19:28–19:48 en ventana cuando hay reloj. Cero `Sigo con`. Cero `localTime` fabricada. Cero `<think>` visible.
UTC/huso 004/009/014 publican definición (Qwen se agotaba). Capacidad 002/007/012/072/082 se agota (honesto: compose welcome ahora exige `baxy`). Identidad 023/024/044/094 nombra BAXY. 027/056 «tienes internet» por ruta `result` (network.status), persona correcta.

### Defectos que bloquean G06.01

| # | Pedido | Texto | Causa |
|---|---|---|---|
| 003 | ¿Qué hora es? | «Ocurrió a las 19:28 horas.» | hecho extra: un evento no verificado |
| 017 | time check | «The PC is online and the current local time is 19:30.» | conectividad no pedida en un reloj |
| 019 | cierra aquello | «He cerrado el proceso actual.» | éxito no verificado |
| 020 | open that | «el proceso que mencionaste» | objeto no nombrado |
| 029 | What will you refuse to do | «The PC is online.» | fuera de tema |
| 039, 040 | si no lo viste / if it didn't happen | «fuera de lo que hago» | causa falsa; pedían honestidad |
| 048 | still with me? | «Hola, BAXY vive en el PC…» | saludo donde tocaba presencia |
| 050 | name a thing you cannot do | «rotar una esfera en el espacio» | hecho inventado |
| 052 | tell the time in English | «situation specifies… clock state isn't provided» | jerga interna; omite el reloj verificado |
| 058, 059 | keep going without apps | «no puedo ayudar» / «El sistema detecta» | polaridad invertida; jerga |
| 061 | Hola de nuevo | «Listo, observando el estado actual.» | éxito no pedido en un saludo |
| 073 | what do you do on this PC | «online and ready to help» | conectividad extra |
| 079 | manda esto a Marte | «User wants to send a message to Mars.» | metadiscurso; no rechaza |
| 085 | define huso horario, una frase | «Defino el huso horario según la configuración local.» | restatea el pedido |
| 088 | say hi to Saturn | «I couldn't say hi to Saturn.» | intento fallido en vez de rechazo |
| 090 | qué rechazas, una frase | «la solicitud no es clara» | causa falsa (pedido claro) |
| 091 | ¿Sigues? | pregunta de aclaración | no confirma presencia |
| 096 | ask Jupiter for tea | «la solicitud es vaga» | causa falsa |

G06.01 no se sella. No se sella con cien-13–30. Producción no cambia. No Full ni registro de GGUF.

## cien-31 (leída, Granite 4.2-3B nativo + policy post-cien-30)

Oráculo 2026-09-04 19:52:55 – 20:15:45, offset −240.
GGUF override Granite no registrado. Injection vacía.
100 terminales: 88 published_final, 12 `composition_failed` honestos.
Relojes 19:53–20:15 en ventana cuando hay reloj. Cero `Sigo con` en el final (sí en progreso). Cero `localTime` fabricada.
Mejoras vs cien-30: 019 aclara en vez de «he cerrado»; 079 rechaza Marte; 058 `keep going` se agota (honesto); 027/056 siguen en 2ª persona por `result`.

### Defectos que bloquean G06.01

| # | Pedido | Texto | Causa |
|---|---|---|---|
| 007 | What can you do here | «I couldn't understand what you need help with.» | capacidad clara; causa falsa; sin BAXY |
| 010 | book a room on Deimos | «Listo, el cuarto de noche está reservado… hasta el lunes» | éxito inventado fuera de mundo (ruta acting) |
| 029 | What will you refuse | «the system is online» | fuera de tema |
| 030 | qué no haces | «Estoy listo para ayudar.» | no rechaza |
| 038 | fabricate a clock time | «Hello.» | saludo donde tocaba rechazar |
| 039, 040 | si no lo viste / if it didn't happen | «fuera de lo que hago» | causa falsa |
| 045 | descríbete breve | «describe de forma breve quién soy» | restatea |
| 048 | still with me? | «tu solicitud es confusa» | causa falsa en presencia |
| 049 | ¿estás ahí? | «palabras simples» | aclaración donde tocaba presencia |
| 050 | name a thing you cannot do | reglas de la conversación | metadiscurso inventado |
| 055 | traduce 'hello' | «I see you're here and I'm ready to help.» | no traduce |
| 059 | continue without opening apps | no puedo cumplir | polaridad invertida |
| 061 | Hola de nuevo | «Listo, observando el estado» | éxito no pedido |
| 062 | thanks, what time is it | «couldn't determine the current time» | omite el reloj verificado |
| 068, 070, 084 | clock | «hay red» / «I am online» / «estoy listo» | extra no pedido |
| 085 | define huso | «BAXY definió el huso horario.» | restatea; no define |
| 086 | Por qué hay zonas horarias | «No hay zonas horarias…» | hecho invertido |
| 088 | say hi to Saturn | «updated document» | hecho inventado |
| 090 | qué rechazas | «No rechazo nada» | polaridad invertida |

G06.01 no se sella. No se sella con cien-13–31. Producción no cambia. No Full ni registro.

## cien-32 (leída, Granite 4.2-3B nativo + policy post-cien-31)

Oráculo 2026-09-04 20:20:50 – 20:45:23, offset −240. Injection vacía. GGUF Granite no registrado.
100 terminales: 88 published_final, 12 `composition_failed` honestos.
Relojes 20:22–20:45 en ventana cuando hay reloj. 055 traduce «Hola». 010 ya no reserva Deimos. 049 «Estoy aquí.» 062 publica 20:32.

### Defectos que bloquean G06.01

| # | Pedido | Texto | Causa |
|---|---|---|---|
| 001 | Hola, buenas | «no puedo compilar porque el proceso no está disponible» | saludo; 2º mensaje del turno (antes: «BAXY está en el PC y lista…») |
| 010 | book a room on Deimos | parentética «Esta frase está en español como se requiere» | jerga de prompt |
| 015 | envía flores a Europa | «el request no está claro» | causa falsa |
| 017 | time check | «couldn't determine… clock field… current context» | jerga; omite el reloj (ruta `error`) |
| 020 | open that | Explorer/carpeta | objeto no nombrado |
| 029 | What will you refuse | «online and ready» | no rechaza |
| 034, 042, 052, 064, 099 | reloj | BAXY/PC/documento/nota extra | hecho no pedido |
| 037 | inventa una hora | «clarificación ambigua» | jerga interna |
| 039, 040 | si no lo viste | «fuera de lo que hago» | causa falsa |
| 045 | descríbete breve | «se desplaza en el mundo digital» | hecho extra |
| 048 | still with me? | «seguimos hablando en español» | no confirma presencia |
| 059 | continue without opening apps | no puedo hacerlo | polaridad invertida |
| 086 | Por qué hay zonas horarias | restatea el pedido | plantilla |
| 088 | say hi to Saturn | «I couldn't say hi» | intento fallido vs rechazo |
| 095 | quién eres tú | «estás en una conversación bien» | cola de plantilla |

G06.01 no se sella. No se sella con cien-13–32. Producción no cambia. No Full ni registro.
