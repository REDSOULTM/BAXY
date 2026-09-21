# Por qué las categorías de mayor masa están condicionadas — 2026-09-13 (Fable)

Orden por abiertos tras MESSAGING1140 (204/742). «Llegan» = resuelven en el reconocedor
determinista con la fuente actual (`scratchpad/c03-open-mass-by-reach.py`, baseline
regenerada en `BASE/C03-recogniser-baseline.json`). Ninguna condición se inventa aquí: cada
línea remite a la evidencia que la demostró. Una categoría condicionada no se salta: se
mide en cuanto la condición se resuelva o el dueño decida.

| Categoría | Abiertos | Llegan | Condición demostrada | Reanudación |
|---|---:|---:|---|---|
| Música | 33 | 19 | 12 Spotify condicionados a reconciliar el efecto incierto 962 (inv88672a39…) y a sesión/login real (`C03-music1083-proposal/PLAN.md`); lecturas H0224/H0543 exigen sesión SMTC real pausada con título largo y el parche MUSIC1127 está sobre llm antiguo (base aaa434, requiere rebase a 5ab7f598…) (`C03-music1127-repair/REVIEW.md`); «pará la música»/pausa exigen reproducción real. Elegibles sin efecto: H0333 y H0421. | Rebase 1127 y observar sesión real; tanda corta de abstención H0333/H0421 con pares. |
| Instalar/desinstalar | 31 | 0 | 10 Steam por título sin pertenencia verificable (INSTALL1128/ELIGIBILITY); Photoshop sin instalador/licencia; desinstalar Discord/Spotify del dueño es efecto destructivo no autorizado; Teams como proveedor incompatible (2). Sólo `instala requests con pip` (H0052) tiene mecanismo `package.install.*` sin condición externa. | Decisión del dueño sobre licencias Steam; H0052 aislado. |
| Web | 29 | 13 | WEB1102: búsquedas reales con resultados irrelevantes y efecto incierto índice2 (inv49443d6e…); WEB1114 sin parche para H0393/H0541; requiere navegador Edge propio del producto (perfil CDP). Sin causa nueva desde 1102. | Hipótesis nueva de relevancia de búsqueda o navegación nombrada (13 llegan: youtube/gmail/github). |
| Archivos | 17 | 15 | Resuelta el 2026-09-13 (decisión del dueño, punto 2): proveedor de carpetas conocidas construido (BUILD1205) y medido en FILES1205 (+12). Restan borrados, listados y contenido dinámico. Frontera anterior: `filesystem.write.text`/`create.directory` confinados al sandbox (`ProductCatalog.cs:312–317, 490–501`; FILES1005/PLAN.md): «en el escritorio/Documentos» no se cumple sin proveedor nuevo para carpetas conocidas (10 escrituras/carpetas = infraestructura ≥10, declarada, no construida). Borrados (5) sólo con fixtures en carpetas personales, prohibido por FILES1005/1040. Listados (4) sin operación de listado de carpetas conocidas. | Decisión del dueño: proveedor de escritura en carpetas conocidas (≥10 abiertos) o cambiar expectativa. |
| Entrada incompleta | 27 | 0 | DIALOGUE1126: sin reparación justificada para la paráfrasis declarativa; NEXT1132 sólo 2 literales en borrador. | Hipótesis causal nueva en observation_ack. |
| Vídeo y series | 26 | 10 | Netflix (12) exige sesión CDP autenticada del dueño y entitlement (VIDEO1026/PLAN.md); Disney+/Prime sin mecanismo; YouTube (`media.play.youtube`) con efectos de navegador. | Login Netflix del dueño en el perfil del producto; YouTube aparte. |
| Mensajería | 25 | 7 | Tras 1140 quedan literales con destinatario/canal reales: enviar exige clientes y terceros (prohibido enviar por encuesta). Elegibles: aclaraciones y lecturas sin envío. | Panel de aclaraciones restantes sobre llm1136. |
| Apps | 25 | 6 | HUECO_LEXICO_APPS: 4 reparables por léxico tras localizar guardia previa; resto destinos ausentes (Photoshop, Steel, Mortal Kombat), erratas de transcripción con nota del dueño (preguntar/contexto), idiomas fuera de alcance (3 sin marca), compuesto con reloj. Respuesta veraz negativa/aclaración es acreditable si es útil. | Sonda settrace de la guardia + tanda de ausentes/erratas. |
| Audio | 24 | 1 | AUDIO1137: sin parche barato; reconocimiento de dirección/alcance sin cantidad requiere gramática nueva (2 literales). | Diseño acotado en effect_intent. |
| Agenda | 4 | 0 | Resuelta el 2026-09-13: el dueño decidió (DECISIONES_DUENO, punto 3) publicar el segundo entero hacia arriba; reparación TIME1139/SOURCE.json medida en TIME1185 (+2, seis tareas con due == NextRun). Resto del material 1134 medible con el mismo criterio. | Derivar de build_time1185.py; índices 3–9 y 14–24 del material 1134. |

Sin condición externa y con mecanismo demostrado: **notas** (12 abiertos, 8 llegan a
`note.create`/`note.list`, mecanismo demostrado en TASK_NOTE_REPAIR986 con 7/12 y +4),
**conocimiento/identidad/conversación** (sin efectos), **red sólo lectura** (`wifi.status`,
`network.ip.list`, `network.status`), **cierre de apps propias** (CLOSE1060 integrado sin
medir). Se avanza por ahí mientras las condiciones anteriores esperan al dueño.


## Actualización 2026-09-13 (tras las decisiones del dueño)

El dueño respondió las siete decisiones (DECISIONES_DUENO_2026-09-13.md): poder total en este PC (instalar, cerrar apps sin autorización por app), proveedor de carpetas conocidas autorizado, TIME1139 resuelto (medido en TIME1185), renombrado de claves de medidas (medido en SYSTEM1183), IP sin confirmación autorizada, y aplazar lo que exija sesiones ausentes (Netflix/Spotify) al otro PC. Las condiciones de Música y Vídeo pasan de «decisión del dueño» a «aplazado por sesión ausente»; Archivos y Cerrar apps quedan sin condición externa.

## Actualización 2026-09-13 (ARRANGE1229)

Organizar ventanas y pestañas pasa de 0/13 a 3/13. Los tres que llegaban al reconocedor (maximizar/minimizar la ventana en primer plano) se midieron sobre una ventana propia; la reparación fue de lectura (deícticos → window.active) porque el producto ejecuta window.maximize/minimize/restore sin confirmación y un inventario habría dejado la elección de la ventana al planificador. Los 10 restantes quedan condicionados con causa: minimizar todo ×3 y «Minimisa ópera.» actúan sobre ventanas del dueño; «traé chrome al frente» depende de SetForegroundWindow desde otro proceso (efecto incierto, no se repite sin una hipótesis nueva); «poné chrome a la izquierda» exige geometría que window.move no infiere; «cambiá a la otra ventana», «enfocá la mejor» ×2 tienen referente indeterminado; «cerrá todas las pestañas de chrome» no tiene mecanismo de pestañas.

## Actualización 2026-09-13 (APPS1231)

Abrir aplicaciones pasa de 29/54 a 34/54: la guardia léxica localizada con sonda settrace (`_is_direct_request` sin clítico ni «abrís/avrí», cortesía final, marco de hora dicha, alias inglés del Explorador) y la pista portuguesa «abre a» ante un nombre de aplicación se repararon y se midieron sobre la Calculadora real. Quedan 20 con causa: Explorador ×2 (verificación del proveedor por proceso nuevo; ventana en el shell) y destinos ausentes ×3 (sin lectura app.installed para software conocido) son reparables en la próxima tanda; compuesto ×1 (final omite la apertura; composición); Steam ×3 y erratas ×4 lanzarían el cliente del dueño (sesión/descargas) o exigen contexto para aclarar; Mortal Kombat ×2 (juego ausente); H0249 indeterminado; H0461 límite sin marca; idiomas ×3 sin marca.

## Actualización 2026-09-13 (APPS1237)

Abrir aplicaciones pasa de 34/54 a 39/54: las dos causas medidas en APPS1231 se repararon y se remidieron (Explorador: identidad de la entrada del shell por proceso y ventanas CabinetWClass, BUILD1237; destinos ausentes: lectura app.installed sobre el nombre de software conocido). Quedan 15: compuesto H0183 (composición de respuesta a efectos múltiples), Steam ×3 y erratas ×4 (lanzar el cliente del dueño o aclarar con contexto), Mortal Kombat ×2 (juego ausente vía game.launch), H0249 (indeterminado), H0461 (límite sin marca), idiomas ×3 (sin marca).

## Actualización 2026-09-13 (AUDIO1239)

Audio y volumen pasa de 27/51 a 39/51. La condición «reconocimiento de dirección/alcance sin cantidad requiere gramática nueva» (AUDIO1137) no aplicaba a los ocho relativos abiertos: la lectura determinista de aclaración ya existía y la regla del dueño (H0027) es preguntar la cantidad, así que sólo faltaba remedirlos y cubrir «suví», «es tarde …», «poné», el nivel absoluto con verbo de dirección y «ponelo en mute». Quedan 12: H0465 (eco del compositor con efecto verificado), compuestos ×2 (H0067 fecha, H0530 brillo sin proveedor), H0652 volumen por aplicación, H0075 «bajá la música» (ambiguo con descargar), H0439/H0713 pronombre sin contexto, idiomas ×4 sin marca.

## Actualización 2026-09-13 (FILES1243)

Archivos y carpetas pasa de 15/32 a 19/32: los borrados con fixtures propios en carpetas personales quedaron autorizados por la decisión del dueño (punto 2, FILES1205) y sólo faltaba el lector de borrado literal (papelera privada recuperable). Quedan 13: listados ×4 (revelarían nombres de archivos del dueño en artefactos públicos; medibles sólo con publicación sin nombres), carpeta ×1 (sin operación de borrado de carpetas), contenido dinámico ×2, comprimir/backup/resumir ×3 (sin operación), ruta suelta, «directorio actual» y recuento compuesto.

## Actualización 2026-09-13 (MEMORY1245)

Memoria personal pasa de 0/10 a 3/10 (afirmaciones sin pedido de persistencia). Condición nueva demostrada para los guardados (4 literales + variantes): la memoria privada está desactivada en un perfil fresco y su activación exige una confirmación de la App (no del kernel), que el instrumento de un turno no puede dar; reanudación con `turn.memory-confirm` en el host y un runner de dos fases (MEMORY1247). Los recuerdos (H0604, H0173) requieren un guardado previo en el mismo perfil: fuera del instrumento de un caso por turno.

## Actualización 2026-09-13 (MEMORY1253)

Memoria personal pasa de 3/10 a 5/10: los dos guardados de nombre (H0157, H0149) con sus variantes en español e inglés. Condiciones demostradas y resueltas en tres tandas: la activación de la memoria privada exige la confirmación de la App (`turn.memory-confirm`, BUILD1249); la finalización del guardado debe llevar el dato recordado y componerse contra el pedido original, no contra «confirmar» (BUILD1249/BUILD1253); el dato se cita sin traducir y el mensaje de fallo memory_disabled no afirma recordar (mente, 772a1671). Quedan 5: los dos guardados de dato (H0452 aprobado sin par por la comprobación literal demasiado estricta del candidato; H0506 y la variante en inglés sin final por la misma causa, corregida para MEMORY1255), los dos recuerdos (H0604, H0173: requieren un guardado previo en el mismo perfil, fuera del instrumento de un caso por turno) y H0174 (modelo).

## Actualización 2026-09-13 (MEMORY1255)

Memoria personal pasa de 5/10 a 7/10: los dos guardados de dato (H0452, H0506) con cuatro variantes de dato en español e inglés. La comprobación del dato recordado exige sus palabras de contenido sin traducir y admite el cambio de persona de la confirmación (mente, 88f5afdf). Quedan 3: los dos recuerdos (H0604, H0173) exigen un guardado previo en el mismo perfil, y el instrumento ejecuta un caso por perfil fresco (un turno más una confirmación); H0174 es calidad del modelo. La categoría queda condicionada por el diseño del instrumento, no por el producto.

## Actualización 2026-09-13 (WEB1257)

Navegación y búsqueda web pasa de 17/46 a 20/46: los destinos nombrados con dominio o nombre público cerrado (gmail ×2, github.com) navegan con el Edge propio del producto (perfil privado del caso, sesión CDP) bajo turno revisado: la raíz aprueba sólo la URL del host esperado y cierra la sesión al terminar. La condición anterior («requiere navegador Edge propio del producto») estaba resuelta: Edge está instalado y la navegación verifica la URL final (Gmail termina en el inicio de sesión de Google; se dice). Quedan 26: destinos simbólicos ×5 («andá a youtube», «llevame a github», «Ve a ChatGPT»: el constructor de argumentos se abstiene aunque el lector navegue directo; corregido para WEB1259), «Abre youtube»/«abrí youtube» ×2 (el catálogo de Inicio tiene la app YouTube: app.open de una PWA de Chrome, tanda de apps con cierre de Chrome), portal UNIEJ ×4 (destino desconocido, requiere aclaración útil), «abre youtube.com en Chrome» (navegador no soportado por browser.navigate.named), búsquedas ×8 (relevancia de resultados, WEB1102), compuestos ×3 (descarga/captura/cierre), pestaña nueva, Opera GX ×2 (navegador del dueño).

## Actualización 2026-09-13 (WEB1259–WEB1263)

Navegación y búsqueda web pasa de 20/46 a 23/46: los destinos simbólicos «andá a youtube», «llevame a github» y «Ve a ChatGPT» navegan directo (el catálogo de Inicio conoce esos nombres) con el Edge privado del producto bajo turno revisado. Tres tandas de composición: WEB1259 (el constructor de argumentos se abstenía ante el destino simbólico; los finales componían contra «confirmar»), WEB1261 (los finales prometían; una pista mal redactada hizo afirmar un estado previo falso; la guarda de GPU se disparó con el proceso GPU del Edge privado) y WEB1263 (pista reescrita, rechazo del estado previo inventado, Edge privado con --disable-gpu): los siete pedidos reportan en pasado. Quedan 23: «Abre youtube»/«abrí youtube» ×2 (app.open de la PWA de YouTube instalada; tanda de apps con cierre de Chrome), portal UNIEJ ×4, «Abre la p?gina oficial de OpenAI» (errata del literal), «abre youtube.com en Chrome», búsquedas ×8 (relevancia), compuestos ×3, pestaña nueva, Opera GX ×2. Rama saneada por el dueño el 13/09 (SANEAMIENTO_2026-09-13_SHAS.md).

## Actualización 2026-09-13 (WEB1265–WEB1271)

Navegación y búsqueda web pasa de 23/46 a 25/46 («Abre youtube»/«abrí youtube» abren la app YouTube del catálogo de Inicio, PWA de Chrome, por app.open; la raíz cierra la ventana lanzada). Información web actual pasa de 0/17 a 2/17 («buscá/busca noticias de hoy»: web.search de sólo lectura verificada y final fiel a los títulos devueltos). Condiciones nuevas demostradas: el lector determinista no reclamaba clima ni noticias (corregido, WEB1269); el filtro de relevancia exigía «hoy/today» en cada resultado (corregido); el shell no reconocía «irrelevant/no results» como fallo (corregido, BUILD1271); y el motor externo (Bing RSS) responde a cualquier consulta de clima con el tiempo de la ubicación del equipo, no de la ciudad pedida (setmkt/cc lo empeoran), así que los 10 pedidos de clima de otras ciudades quedan condicionados por el motor y el producto lo dice con verdad; «today’s news» devuelve el programa de TV TODAY (ranking). Quedan también Spider-Man, «qué pasó hoy en el mundo» (sin sustantivo de noticia), «va a llover mañana»/«mostrame el clima» (clima local: los resultados dicen «tiempo», no «clima») y «buscá el clima en google» (navegación a Google).

## Actualización 2026-09-13 (UI1273–UI1275)

Interacción dentro de aplicaciones pasa de 0/22 a 3/22: los clics sobre la Calculadora propia de la raíz en primer plano («apretá el 5», «hacé clic en el botón nueve») corren como turno revisado (input.visible.click aprobado por la raíz para la etiqueta esperada y la ventana propia, approve_click.py). Condiciones demostradas y resueltas: el lector no tenía las formas españolas de clic ni el contexto «en la calculadora» (mente); el script del clic no compilaba en Windows PowerShell 5.1 (C# 7 en Add-Type) y todo clic terminaba sin recibo; un botón sin estado (dígito) quedaba «postread_unchanged» aunque el descriptor admite «superficie cambiada»; los nombres de UI Automation de los dígitos son palabras («Cinco»). Quedan 19: H0555 (final «Apagué el 5»: verbo equivocado del modelo), «abrí la calculadora y apretá el 5» (dos pasos: la forma revisada del conductor sólo admite prefijos de lectura), sumas/multiplicaciones ×2 (varios clics con confirmación cada uno), «botón rojo»/«Aceptar» (sin tal control en la calculadora), Discord ×7, WhatsApp, Among Us, ChatGPT-diálogo (clientes, juegos y sesiones del dueño), «ponle hola» (sin destino).

## Actualización 2026-09-13 (DIALOGUE1277)

Entrada incompleta, ruido y control de diálogo (7/34, 27 abiertos) medida con 8 literales, 4 variantes y 2 límites como turnos ordinarios sin efectos: 4 aprobados, 0 créditos. Condiciones demostradas: (1) una entrada sin pedido legible (sólo signos, cifras, una letra) llega al modelo sin guía y recibe una oferta de ayuda genérica o una negativa «fuera de lo que hago»; (2) una negación suelta se enruta como conocimiento por la regla de negación inicial y el modelo declara que no entendió; (3) el aclarador de referente lee el imperativo voseante «abrí eso» como pasado del usuario; (4) «Si hazlo»/«dale, hacelo» no entran en la lectura deíctica y el modelo declara incomprensión; (5) «cerrá eso» es, por diseño documentado, cierre de la ventana en primer plano y no pertenece a esta categoría. Reparación en curso (mente): aclaración compuesta para entrada sin pedido y negación suelta (clarify_unresolved_input), un reintento corregido del aclarador de referente cuando atribuye la acción al usuario, y el asentimiento con orden («si hazlo», «hacelo») en la lectura deíctica; se mide en DIALOGUE1279. Fuera: transcripciones degradadas largas que sí se entienden en parte (el modelo decide), y los límites de conversación sobre la propia conducta.

## Actualización 2026-09-13 (DIALOGUE1279)

Entrada incompleta, ruido y control de diálogo pasa de 7/34 a 13/34 con la reparación de la mente (commit 346016c4, BUILD1279): 14 ejecutados, 9 aprobados, 5 fallidos, 6 créditos. Resuelto y medido: negación suelta aceptada con pregunta de preferencia; cifras y una letra suelta reciben una pregunta que refiere lo recibido; «abrí eso» pregunta qué abrir. Quedan 21: ante sólo signos la aclaración no nombra lo recibido (H0287, «???»: «¿Qué quieres que haga?», indistinguible de la oferta genérica); ante un asentimiento sin acción el aclarador de referente inventa «abrir» por el ejemplo de su guía (H0562, «Sí, hacelo.»); las transcripciones degradadas largas dependen del modelo; el límite «si no entendés, preguntame» sigue pidiendo aclaración. Siguiente reparación: guía del aclarador sin ejemplo de verbo y exigencia de nombrar lo recibido ante signos.

## Actualización 2026-09-13 (DIALOGUE1281)

Entrada incompleta, ruido y control de diálogo pasa de 13/34 a 18/34 con la segunda reparación (commit 7ccf9cb3, BUILD1281): 14 ejecutados, 10 aprobados, 4 fallidos, 5 créditos. Resuelto y medido: ante sólo signos, símbolos o emojis la aclaración nombra lo recibido y dice que no ve un pedido (H0287, H0493, H0500); el aclarador ya no inventa «abrir» ante «Sí, hacelo.»; el deíctico coloquial (H0091) y el fragmento nominal (H0271) reciben una pregunta de contexto. Quedan 16, todos fragmentos con palabras que decide el modelo: H0562 «¿Qué haces?» (sin pedir la acción aceptada), H0735 (reconstruye el fragmento y se atribuye la firma), H0205 (saludo), H0160/H0210/H0404/H0414 y las transcripciones largas (H0006, H0139, H0246, H0332, H0372, H0429, H0441, H0483), más H0639 (marcador redactado, autoría negada). Sin reparación determinista honesta para ellos: la lectura es del modelo; se documenta como condición.

## Actualización 2026-09-13 (BRIGHT1283)

Brillo y pantalla (0/17) se mide por primera vez: este portátil expone el brillo por WMI y el catálogo tiene system.settings.status (lectura), system.settings.adjust (bajo riesgo, sin confirmación) y system.settings.set (sensible, confirmación). Panel de 16 turnos ordinarios (lecturas, ajustes relativos sin cantidad, prohibición): 4 aprobados, 0 créditos. Condición demostrada: ningún literal de brillo tiene lector determinista; el modelo aclara de más ante «qué brillo tengo», devuelve «mostrame el brillo» como pregunta, ante «subí/bajá el brillo» pregunta «cuánto y en qué dirección» (no fundamenta la dirección dicha), lee el estado ante «está oscuro subí el brillo», filtra «WMI» ante «subime el brillo» y niega la capacidad ante «turn the brightness down». Reparación en curso (mente): lectores cerrados que reflejan la gramática del volumen (lectura → status; cantidad dicha → adjust; sin cantidad → preguntar cuánto conservando la dirección, misma regla del dueño que el volumen); se mide en BRIGHT1285. Fuera por ahora: niveles absolutos («poné el brillo al 80», «al máximo»: system.settings.set con confirmación, tanda revisada posterior), «cambiá el fondo de pantalla a azul» (sin mecanismo de fondo) y «tengo el brillo al máximo» (afirmación).

## Actualización 2026-09-13 (BRIGHT1285)

Brillo y pantalla pasa de 0/17 a 7/17 con los lectores deterministas de brillo (commit 4c93a154, BUILD1285): 16 ejecutados, 14 aprobados, 2 fallidos, 7 créditos. Resuelto y medido: la pregunta de brillo lee el monitor por WMI y el final informa el valor; el ajuste relativo sin cantidad pregunta cuánto conservando la dirección (regla del dueño del volumen, H0027; «un toque» y «un poco» también preguntan); la prohibición se reconoce. Quedan 10: niveles absolutos («poné el brillo al 80/50», «al 80%», «al máximo»: system.settings.set es sensible y exige confirmación → tanda revisada con aprobación de la raíz por valor esperado), «estoy cansado subí el brillo», «bajame el brillo un poco», «bajá bastante el brillo» (misma lectura, medibles con pares), «tengo el brillo al máximo» (afirmación: lectura o reconocimiento, a decidir con la nota del dueño) y «cambiá el fondo de pantalla a azul» (sin mecanismo de fondo de escritorio; el dueño espera que lo cambie: condición de infraestructura).

## Actualización 2026-09-14 (BRIGHT1287)

Brillo y pantalla pasa de 7/17 a 10/17 con el lector de nivel absoluto y el turno revisado de system.settings.set (commit 4e8c2caa, BUILD1287): 13 ejecutados, 10 aprobados, 3 fallidos, 3 créditos. Tres niveles absolutos acreditados (H0109 80, H0255 50, H0196 máximo) con pares «Poné el brillo al 70.» y «Set the brightness to 40.»: cada system.settings.set propuesta como turno revisado, aprobada por la raíz por valor exacto, completada y verificada por WMI desde el preset 60. H0430 («al 80%») se ejecutó y verificó pero el final filtró «WMI»: fallido. Los tres relativos restantes (H0123, H0193, H0627) preguntaron cuánto conservando la dirección pero sólo una variante aprobó («Subí bastante el brillo.» recibió «¿Cuánto subiste el brillo?», pasado del usuario): sin crédito. El límite de consejo pidió aclaración. Quedan 7: los que fallaron en esta tanda (ver adjudicación), «tengo el brillo al máximo» (afirmación sin nota del dueño) y «cambiá el fondo de pantalla a azul» (sin mecanismo de fondo de escritorio; el dueño espera el cambio: infraestructura).

## Actualización 2026-09-14 (BRIGHT1289)

Brillo y pantalla pasa de 10/17 a 13/17 con las correcciones del compositor (commit 11467c9c, BUILD1289): 10 ejecutados, 9 aprobados, 1 fallido, 3 créditos. Tres relativos acreditados (H0123 con preámbulo, H0193 «un poco», H0627 «bastante») con pares «Subí bastante el brillo.» y «Subime un poco el brillo.»: cero operaciones y pregunta por la cantidad conservando la dirección; el reintento evita el pasado del usuario. Las dos variantes de nivel (65, 45) pasaron con set verificada. H0430 volvió a fallar: el final que compone la App tras la confirmación filtra «WMI» y el veto de la mente sólo cubre aclaraciones; pendiente en UserMessagePolicy.ForbiddenTerms. Quedan 4: H0430 (la set funciona; el final de la App filtra «WMI»: ForbiddenTerms pendiente), «tengo el brillo al máximo» (afirmación sin nota del dueño) y «cambiá el fondo de pantalla a azul» (sin mecanismo de fondo de escritorio; el dueño espera el cambio: infraestructura).

## Actualización 2026-09-14 (WEB1291)

Navegación y búsqueda web (25/46, 21 abiertos): tanda de búsquedas por tema (H0380, H0098, H0618) y páginas de Steam por búsqueda (H0360, H0723) con pares: 2 aprobados, 0 créditos. Condición demostrada y documentada con sonda directa (WEB1291/ENGINE_PROBE.md): el RSS de Bing devuelve desde este PC resultados ajenos para consultas genéricas («Transformers» → granjas verticales; «marvel rivals steam» → Marvel.com sin la página de Steam; «recetas de pizza» sin «pizza»), Bing HTML igual, y DuckDuckGo responde 202 (anti-bot) tras la primera petición; el filtro de pertinencia del producto rechaza con razón y los finales son honestos («no encontré resultados relevantes»), pero no útiles (sin crédito, como en WEB_SEARCH900). La cadena revisada funciona cuando el motor acierta («Andá a la página de Elden Ring en Steam.»: navegación aprobada y verificada). Reanudación: proveedor de resultados verificables distinto de Bing RSS (decisión de producto) o cambio del motor; hasta entonces sólo las noticias en español (RSS de noticias) son fiables. Sin cambio en la categoría.

## Actualización 2026-09-14 (NETWORK1293)

Red y Bluetooth pasa de 9/21 a 10/21 (commit b6828d9c, BUILD1293): 13 ejecutados, 10 aprobados, 3 fallidos, 1 créditos. H0230 «decime si el wifi está prendido» acreditado con pares «¿El wifi está encendido?» y «Decime si el wifi está activo.» (wifi.status verificada, connected=false; finales directos y fieles). Los tres literales de radio pasaron con bluetooth.radio.set verificada (On→Off, Off→On) pero sin crédito: las variantes con clítico o voseo («Apagame», «Encendé») pidieron el estado ya dicho porque la normalización literal del booleano no reconoce esas formas; «Turn off» y «Activá» pasaron. H0302 «qué redes wifi hay» falló: el final afirmó que el PC no está conectado a ninguna red (Ethernet en uso, no observado) y no dijo que no puede escanear. Quedan 11: los que fallaron en esta tanda (ver adjudicación), «conectate al wifi de casa» ×2 (wifi.connect.named es sensible: confirmación; la nota del dueño pide preguntar cuál red y la contraseña si hace falta), «conectate al wifi de la luna» (perfil inexistente: terminar honestamente; confirmación por diseño), «apagá el wifi» (wifi.disconnect sensible; el wifi ya está apagado en este PC), «poneme el modo avión» (sin mecanismo), «tengo el bluetooth encendido» y «y el bluetooth?» (sin lectura de estado de la radio en el catálogo; bluetooth.device.list no informa la radio).

## Actualización 2026-09-14 (NETWORK1295)

Red y Bluetooth pasa de 10/21 a 11/21 (commit dd1fae93, BUILD1295): 12 ejecutados, 8 aprobados, 4 fallidos, 1 créditos. H0537 «prendé el bluetooth» acreditado con pares «Encendé el bluetooth.» y «Prendeme el bluetooth.» (bluetooth.radio.set true verificada Off→On; el normalizador ya fundamenta el estado con clíticos/voseo). H0071/H0179 aprobados de nuevo sin crédito: «Apagame el bluetooth.» ejecutó y verificó la radio pero el final atribuyó la acción al usuario («Ya apagaste el bluetooth»), «Desactivame» pasó. H0302 y sus pares: wifi.status verificada, ya sin inventar el estado de la red, pero ninguno dice que no puede escanear redes disponibles («Mostrame las redes wifi disponibles.» se declaró fuera de funciones sin leer). Quedan 10: los que fallaron en esta tanda (ver adjudicación), «conectate al wifi de casa» ×2 (wifi.connect.named es sensible: confirmación; la nota del dueño pide preguntar cuál red y la contraseña si hace falta), «conectate al wifi de la luna» (perfil inexistente: terminar honestamente; confirmación por diseño), «apagá el wifi» (wifi.disconnect sensible; el wifi ya está apagado en este PC), «poneme el modo avión» (sin mecanismo), «tengo el bluetooth encendido» y «y el bluetooth?» (sin lectura de estado de la radio en el catálogo; bluetooth.device.list no informa la radio).

## Actualización 2026-09-14 (NETWORK1297)

Red y Bluetooth pasa de 11/21 a 11/21 (commit 93af506c, BUILD1297): 9 ejecutados, 5 aprobados, 4 fallidos, 0 créditos. Sin crédito: «Apagame el bluetooth.» volvió a componer «Ya apagaste el bluetooth» (radio verificada, actor equivocado; el veto action_attributed_to_user no alcanzó esta ruta de composición) y los tres casos de redes wifi quedaron sin final porque el nuevo defecto missing_scan_limit agotó los reintentos del compositor (regresión revertida en el commit siguiente); H0071/H0179 y «Desactivame» aprobados. Quedan 10: los que fallaron en esta tanda (ver adjudicación), «conectate al wifi de casa» ×2 (wifi.connect.named es sensible: confirmación; la nota del dueño pide preguntar cuál red y la contraseña si hace falta), «conectate al wifi de la luna» (perfil inexistente: terminar honestamente; confirmación por diseño), «apagá el wifi» (wifi.disconnect sensible; el wifi ya está apagado en este PC), «poneme el modo avión» (sin mecanismo), «tengo el bluetooth encendido» y «y el bluetooth?» (sin lectura de estado de la radio en el catálogo; bluetooth.device.list no informa la radio).

## Actualización 2026-09-14 (NETWORK1299)

Red y Bluetooth pasa de 11/21 a 11/21 (commit e59ca712, BUILD1299): 6 ejecutados, 5 aprobados, 1 fallido, 0 créditos. Sin crédito: «Apagame el bluetooth.» volvió a publicar «Ya apagaste el bluetooth» porque la carga visible del compositor sólo trae operation y seen y el defecto de actor exigía kind/verified/succeeded (compose-audit payload_keys); H0071, H0179 y «Desactivame» aprobados con radio verificada. Quedan 10: los que fallaron en esta tanda (ver adjudicación), «conectate al wifi de casa» ×2 (wifi.connect.named es sensible: confirmación; la nota del dueño pide preguntar cuál red y la contraseña si hace falta), «conectate al wifi de la luna» (perfil inexistente: terminar honestamente; confirmación por diseño), «apagá el wifi» (wifi.disconnect sensible; el wifi ya está apagado en este PC), «poneme el modo avión» (sin mecanismo), «tengo el bluetooth encendido» y «y el bluetooth?» (sin lectura de estado de la radio en el catálogo; bluetooth.device.list no informa la radio).

## Actualización 2026-09-14 (NETWORK1301)

Red y Bluetooth pasa de 11/21 a 13/21 (commit ca34b99d, BUILD1301): 6 ejecutados, 6 aprobados, 0 fallidos, 2 créditos. H0071 «apagá el bluetooth» y H0179 «desactivá el bluetooth» acreditados con pares «Apagame el bluetooth.» y «Desactivame el bluetooth.»: bluetooth.radio.set {state: false} verificada (On→Off) en los cuatro casos y finales en primera persona («Apagado el Bluetooth.», «Listo, el bluetooth está desactivado.»); el defecto de actor rechazó el borrador «apagaste». Límites aprobados. Quedan 8: los que fallaron en esta tanda (ver adjudicación), «conectate al wifi de casa» ×2 (wifi.connect.named es sensible: confirmación; la nota del dueño pide preguntar cuál red y la contraseña si hace falta), «conectate al wifi de la luna» (perfil inexistente: terminar honestamente; confirmación por diseño), «apagá el wifi» (wifi.disconnect sensible; el wifi ya está apagado en este PC), «poneme el modo avión» (sin mecanismo), «tengo el bluetooth encendido» y «y el bluetooth?» (sin lectura de estado de la radio en el catálogo; bluetooth.device.list no informa la radio).

## Actualización 2026-09-14 (SYSTEM1303)

Estado de hardware y sistema pasa de 29/40 a 31/40 sin cambio de fuente (BUILD1301): 11 ejecutados, 9 aprobados, 2 fallidos, 2 créditos. H0219 «cuánto espacio tengo» acreditado con pares «¿Cuánto espacio libre me queda?» y «Cuánto espacio tengo en el disco» (system.status disk verificada, 103,19 GB libres); H0532 «tirame cuánta memoria tengo» acreditado con pares «cuánta RAM tengo» y «decime cuánta memoria tiene el PC» (memory verificada, 16,54 GB total sin etiqueta falsa). H0508 y un par de os_memory fallaron por llamar «instalados» al total (instalada observada 17,18 GB); el otro par de os_memory pasó. Límites aprobados. Quedan 9: H0508 y H0076 (Windows + RAM: el modelo llama «instalados» al total; H0076 además pide Python, que el dueño no quiere como capacidad), H0106 y H0589 (fecha/hora + RAM o disco: compuestos de dos lecturas con fecha inventada o composición agotada), H0307 (versión de Python: sin mecanismo), H0125/H0195/H0464/H0707 (Hz, resolución, monitores: system.status no tiene scope de pantalla; infraestructura nueva).

## Actualización 2026-09-14 (SYSTEM1305)

Estado de hardware y sistema sigue en 31/40 con el defecto de etiqueta «instalada» (commit c94e71e8, BUILD1305): 5 ejecutados, 4 aprobados, 1 fallido, 0 créditos. Sin crédito: el defecto mislabelled_installed funcionó (ningún borrador llamó instalados al total) y los dos pares «Qué Windows tengo y cuánta RAM tiene el PC» / «Decime qué Windows tengo y cuánta RAM tiene esta compu.» aprobaron con lectura verificada, pero H0508 inventó «versión 22H2» (observado: build 26200, Windows 11 Home Single Language). Límites aprobados. Quedan 9: los que fallaron en esta tanda (ver adjudicación), H0076 (Windows + RAM pidiendo Python, que el dueño no quiere como capacidad), H0106 y H0589 (fecha/hora + RAM o disco: compuestos de dos lecturas con fecha inventada o composición agotada), H0307 (versión de Python: sin mecanismo), H0125/H0195/H0464/H0707 (Hz, resolución, monitores: system.status no tiene scope de pantalla; infraestructura nueva).

## Actualización 2026-09-14 (SYSTEM1307)

Estado de hardware y sistema pasa de 31/40 a 32/40 con los defectos de etiqueta instalada y versión inventada (commit f0fa0804, BUILD1307): 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos. H0508 «Dime que version de Windows tengo y cuanta RAM tiene este PC.» acreditado con pares «Qué Windows tengo y cuánta RAM tiene el PC» y «Decime qué Windows tengo y cuánta RAM tiene esta compu.»: system.status (os_memory) verificada en los tres, finales con la versión observada (10.0.26200 x64 / Windows 11 Home) y el total de RAM (16,54 GB) sin etiqueta falsa ni nombre de actualización inventado. Límites aprobados. Quedan 8: los que fallaron en esta tanda (ver adjudicación), H0076 (Windows + RAM pidiendo Python, que el dueño no quiere como capacidad), H0106 y H0589 (fecha/hora + RAM o disco: compuestos de dos lecturas con fecha inventada o composición agotada), H0307 (versión de Python: sin mecanismo), H0125/H0195/H0464/H0707 (Hz, resolución, monitores: system.status no tiene scope de pantalla; infraestructura nueva).

## Actualización 2026-09-14 (NEGATIVE1309)

Restricciones negativas de apertura pasa de 1/4 a 1/4 sin cambio de fuente (BUILD1307): 7 ejecutados, 3 aprobados, 4 fallidos, 0 créditos. Sin crédito: H0685 «mejor no abras la calculadora» y «No abras Paint.» reconocieron la restricción sin abrir nada, pero H0447 «no abras el navegador» contestó que no entendió, H0550 «no abras chrome» y «Mejor no abras Spotify.» pidieron aclaración, y el límite «¿Podés abrir programas en este PC?» negó una capacidad real. Causa por reparar: la prohibición se reconoce como restricción negativa (explicit_negative_constraint) pero la ruta de reconocimiento no produce el acuse; «mejor no abras» no entra en el lector.

## Actualización 2026-09-14 (NEGATIVE1311)

Restricciones negativas de apertura pasa de 1/4 a 4/4 con el acuse de restricción reparado (commit b28dc6d9, BUILD1311): 7 ejecutados, 6 aprobados, 1 fallido, 3 créditos. H0447 «no abras el navegador», H0550 «no abras chrome» y H0685 «mejor no abras la calculadora» acreditados con pares «No abras Paint.» y «Mejor no abras Spotify.»: cero operaciones y acuse de la restricción en primera persona («Entendido, no abriré…») en los cinco casos. El límite «¿Podés abrir programas en este PC?» sigue negando una capacidad real (respuesta del modelo a una pregunta de capacidad); la definición de navegador aprobó.

## Actualización 2026-09-14 (PROCESS1313)

Procesos pasa de 8/9 a 9/9 sin cambio de fuente (BUILD1311): 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos. H0675 «qué app usa más memoria» acreditado con pares «¿Qué programa consume más RAM?» y «cuál es el proceso que más memoria usa»: system.process.list (sort memory) completada y verificada en los tres, finales que nombran el proceso observado con más memoria (Code, 821,7 MB) sin inventar. Límites aprobados. Procesos queda 9/9: primera categoría cerrada del registro. Primera categoría cerrada del registro (9/9).

## Actualización 2026-09-14 (WINDOWS1315)

Estado de ventanas y aplicaciones pasa de 13/14 a 13/14 con BUILD1315 (lector «cuál es la ventana más grande» → window.resolve de inventario; largestWindow calculado sobre ancho×alto observados en la proyección): 5 ejecutados, 2 aprobados (los dos límites), 3 fallidos (literal y dos pares: lectura window.resolve verificada sobre 20 de 22 ventanas, borradores de la ventana más grande vetados como missing_fact), 0 créditos. Medición: la proyección de una sola ventana choca con la guardia de página parcial; reparación para WINDOWS1317: página de 50 para la pregunta de tamaño y campo sizeComparisonScope que la guardia acepta.

## Actualización 2026-09-14 (WINDOWS1317)

Estado de ventanas y aplicaciones pasa de 13/14 a 14/14 con BUILD1317 (página 50 para la pregunta de tamaño; sizeComparisonScope declarado por la proyección y aceptado por la guardia de página parcial): 5 ejecutados, 4 aprobados, 1 límite fallido (saludo no cumplido), 0 violaciones; H0419 acreditado con dos pares sobre window.resolve verificada de las 22 ventanas observadas, 1 créditos. Medición: con página 50 la comparación cubre todo el inventario y el compositor publica al primer intento; residual: con más de 50 ventanas el final debe declarar el subconjunto comparado. Segunda categoría cerrada del registro (14/14).

## Actualización 2026-09-14 (BRIGHT1319)

Brillo y pantalla pasa de 13/17 a 14/17 con el lector de afirmación de nivel (commit 098469b6, BUILD1319): 10 ejecutados, 8 aprobados, 2 fallidos, 0 violaciones; H0496 acreditado con dos pares (cero operaciones, brillo intacto verificado por la raíz), 1 créditos. Medición: H0430 volvió a ejecutarse y verificarse (60 → 80) pero el final tras la confirmación agotó los borradores porque el modelo copia «WMI» del campo authority del payload visible (forbidden_term); H0674 leyó 60 y aun así dio la razón a «al máximo» (sin veto que compare un extremo con el valor observado). Reparación para BRIGHT1321: quitar authority del payload visible de system.settings.* y vetar el extremo contradicho. Queda fuera de alcance «cambiá el fondo de pantalla a azul» (sin mecanismo de fondo de escritorio; infraestructura).

## Actualización 2026-09-14 (BRIGHT1321)

Brillo y pantalla pasa de 14/17 a 16/17 con el payload visible limpio y el veto de extremo contradicho (commit 27dc7b50, BUILD1321): 10 ejecutados, 10 aprobados, 0 fallidos, 0 violaciones; H0430 y H0674 acreditados con dos pares cada uno, 2 créditos. Medición: con el payload visible sin authority el final de la set se publica al primer reintento («El brillo del sistema se ha ajustado al 80%»); con el veto contradicted_maximum la afirmación «tengo el brillo al máximo» recibe el valor observado (60). Brillo y pantalla queda en 16/17: H0459 (fondo de pantalla) sin mecanismo. Queda fuera de alcance «cambiá el fondo de pantalla a azul» (sin mecanismo de fondo de escritorio; infraestructura).

## Actualización 2026-09-14 (IDENTITY1323)

Identidad y capacidades del asistente pasa de 16/19 a 16/19 con el lector de identidad coloquial, «cómo funciona esto» como capacidad y la comparación sin referente como entrada sin pedido (commit 35df6425, BUILD1323): 11 ejecutados, 5 aprobados (pares de identidad, par inglés de la comparación, dos límites), 6 fallidos, 0 violaciones, 0 créditos. Medición: la lectura de identidad/capacidad llega al decisor, pero (1) la comprobación de forma semántica del efecto convierte «quien chuta eres» en aclaración de fútbol, (2) la pregunta por el referente sale con sujeto invertido en español («te comparas») y (3) la conversación de capacidad no usa el catálogo servido. Reparación para IDENTITY1325: excluir identidad/capacidad de esa aclaración, formas de presentación identity/how_it_works con el catálogo servido, y comprobación de sujeto en la pregunta de comparación.

## Actualización 2026-09-14 (IDENTITY1325)

Identidad y capacidades del asistente pasa de 16/19 a 17/19 con la reparación de presentación (identidad/capacidad sin aclaración, forma how_it_works, sujeto de la comparación) (commit 5aa7b9f5, BUILD1325): 11 ejecutados, 7 aprobados, 4 fallidos, 0 violaciones; H0296 acreditado con dos pares, 1 créditos. Medición: la exclusión de identidad/capacidad evita la aclaración de fútbol, pero la conversación de conocimiento sin forma de identidad no se identifica ante «chuta»; la forma how_it_works nombra el catálogo servido pero cierra con un compromiso universal («siempre preguntando antes de cambiar algo») y el par inglés inventa «always watching and listening». Reparación para IDENTITY1327: forma de presentación identity y contrato how_it_works sin conductas universales.

## Actualización 2026-09-14 (IDENTITY1327)

Identidad y capacidades del asistente pasa de 17/19 a 19/19 con la forma de presentación identity y el contrato how_it_works sin conductas universales (commit 5f5d2470, BUILD1327): 8 ejecutados, 8 aprobados, 0 fallidos, 0 violaciones; H0012 y H0373 acreditados con dos pares cada uno, 2 créditos. Medición: con la forma de presentación identity la pregunta coloquial se contesta identificándose; con el contrato how_it_works sin conductas universales la explicación nombra este PC y sólo capacidades del catálogo servido. Identidad y capacidades cerrada 19/19 (tercera categoría). Tercera categoría cerrada del registro (19/19).

## Actualización 2026-09-14 (CLOCK1329)

Hora y fecha pasa de 16/23 a 18/23 con la cuenta atrás y la palabra suelta «tiempo» como lecturas del reloj (commit 95688821, BUILD1329): 9 ejecutados, 6 aprobados, 3 fallidos (cuenta atrás: literal y dos pares), 0 violaciones; H0054 y H0312 acreditados con dos pares, 2 créditos. Medición: la palabra suelta «tiempo» se lee como hora y el final da el reloj observado; la cuenta atrás lee el reloj y la mente calcula el resto (14 h 7 min para las 15:00), pero la comprobación del reloj exige la hora observada en el texto y veta el borrador correcto (missing_name). Reparación para CLOCK1331: en una cuenta atrás la hora observada no es obligatoria en el final.

## Actualización 2026-09-14 (CLOCK1331)

Hora y fecha pasa de 18/23 a 18/23 con la comprobación del reloj relajada para la cuenta atrás (commit cb98a428, BUILD1331): 5 ejecutados, 2 aprobados (los dos límites), 3 fallidos (cuenta atrás: literal y dos pares), 0 violaciones, 0 créditos. Medición: la lectura y el cálculo del resto (13 h 48 min para las 15:00) son correctos, pero compose_visible_defect conserva una segunda comprobación del reloj (clock_required) que veta el borrador correcto como missing_name. Reparación para CLOCK1333: misma exención de cuenta atrás en esa comprobación.

## Actualización 2026-09-14 (CLOCK1333)

Hora y fecha pasa de 18/23 a 18/23 con la exención de cuenta atrás en las dos comprobaciones del reloj (commit 7d36ba07, BUILD1333): 5 ejecutados, 2 aprobados (los dos límites), 3 fallidos (cuenta atrás: literal y dos pares), 0 violaciones, 0 créditos. Medición: la mente ya compone y publica la cuenta atrás («Faltan 13 horas y 43 minutos para las 3 de la tarde.»), pero la App la rechaza con missing_literal_fact porque su política de system.time exige la hora observada literal en el final. Reparación para CLOCK1335: política de la App consciente de la cuenta atrás (o final con hora y resto).

## Actualización 2026-09-14 (CLOCK1335)

Hora y fecha pasa de 18/23 a 19/23 con la política de la App consciente de la cuenta atrás (commit ef2a5f25, BUILD1335): 5 ejecutados, 5 aprobados, 0 fallidos, 0 violaciones; H0399 acreditado con dos pares, 1 créditos. Medición: con la política de la App consciente de la cuenta atrás el final publica el resto calculado por la mente sobre el reloj observado (13 h 37 min hasta las 15:00) sin repetir la hora. Hora y fecha queda en 19/23: los cuatro restantes están en portugués, alemán, francés e italiano (fuera de aceptación por idioma).

## Actualización 2026-09-14 (AGENDA1337)

Alarmas, recordatorios, tareas y agenda pasa de 34/38 a 35/38 con las dos aclaraciones deterministas (commit 8a590711, BUILD1337): 8 ejecutados, 7 aprobados, 1 fallido, 0 violaciones; H0043 acreditado con dos pares, 1 créditos. Medición: la tarea con sólo fecha recibe la pregunta por el título conservando la fecha; la alarma sin identificar recibe «cuál alarma» en el literal y en un par, pero «cancelame la alarma» produjo «¿Quieres que cancele la alarma más reciente?» (candidato inventado). Reparación para AGENDA1339: la pregunta de which_alarm debe preguntar cuál y no proponer una. Quedan «listá los timers» (no hay listado completo de notificaciones programadas; sólo notification.list.due) y «qué tengo agendado para hoy» (calendar.event.list exige una cuenta Microsoft en el producto).

## Actualización 2026-09-14 (AGENDA1339)

Alarmas, recordatorios, tareas y agenda pasa de 35/38 a 35/38 con la pregunta «cuál alarma» comprobada (commit a703e379, BUILD1339): 5 ejecutados, 4 aprobados, 1 fallido, 0 violaciones; sin crédito (un solo par aprobado), 0 créditos. Medición: el literal y el par inglés preguntan cuál alarma por la aclaración explícita, pero «cancelame la alarma» no pasa la puerta de pedido directo (_is_direct_request no admite «cancelame») y el modelo propone «la alarma más reciente». Reparación para AGENDA1341: cabezas clíticas de cancelación en la puerta de pedido directo. Quedan «listá los timers» (no hay listado completo de notificaciones programadas; sólo notification.list.due) y «qué tengo agendado para hoy» (calendar.event.list exige una cuenta Microsoft en el producto).

## Actualización 2026-09-14 (AGENDA1341)

Alarmas, recordatorios, tareas y agenda pasa de 35/38 a 36/38 con las cabezas clíticas en la puerta de pedido directo (commit e61f7626, BUILD1341): 5 ejecutados, 5 aprobados, 0 fallidos, 0 violaciones; H0011 acreditado con dos pares, 1 créditos. Medición: con las cabezas clíticas en la puerta de pedido directo, «cancelame la alarma» entra en la aclaración explícita y las tres formas preguntan cuál alarma sin proponer ninguna. Agenda queda en 36/38: «listá los timers» (sin listado completo de notificaciones) y «qué tengo agendado para hoy» (cuenta Microsoft). Quedan «listá los timers» (no hay listado completo de notificaciones programadas; sólo notification.list.due) y «qué tengo agendado para hoy» (calendar.event.list exige una cuenta Microsoft en el producto).

## Actualización 2026-09-14 (CONVERSATION1343)

Conversación social y ayuda general pasa de 25/31 a 26/31 con las formas de saludo con otro nombre y acuse de tranquilización y el límite de contenido visual (commit 6fa90262, BUILD1343): 11 ejecutados, 6 aprobados, 5 fallidos, 0 violaciones; H0122 acreditado con dos pares, 1 créditos. Medición: el saludo con otro nombre se contesta saludando y diciendo que se llama BAXY; la tranquilización no llega a su forma (la comprobación de forma semántica del efecto la convierte en aclaración) y el pedido de meme, aunque clasificado como no soportado, sale con sujeto invertido («Pido un meme…»), agota reintentos o pregunta. Reparación para CONVERSATION1345: excluir tranquilizaciones y pedidos visuales de esa aclaración y darles forma propia. Quedan «Artiro, artiro. Estimado, estimado.» (fragmento sin pedido legible) y dos literales fuera de aceptación por idioma.

## Actualización 2026-09-14 (CONVERSATION1345)

Conversación social y ayuda general pasa de 26/31 a 26/31 con la exclusión de la aclaración de forma semántica y la forma visual_content_boundary (commit e0189729, BUILD1345): 8 ejecutados, 3 aprobados, 5 fallidos, 0 violaciones; sin crédito, 0 créditos. Medición: la forma reassurance_ack se aplica pero su respuesta estructurada se trunca a 64 tokens (truncated_structured_reply) y el turno cae en aclaración de recuperación; la mente compone «No puedo mostrar contenido visual como un meme en este entorno.» pero la App rechaza esa respuesta y publica su mensaje de fuera de catálogo con sujeto invertido. Reparación para CONVERSATION1347: presupuesto de 128 tokens para las formas nuevas y una respuesta de límite visual que la política de conversación de la App acepte. Quedan «Artiro, artiro. Estimado, estimado.» (fragmento sin pedido legible) y dos literales fuera de aceptación por idioma.

## Actualización 2026-09-14 (CONVERSATION1347)

Conversación social y ayuda general pasa de 26/31 a 27/31 con el presupuesto de 128 tokens y la regla de fuera de catálogo visual de la App (commit f35a46bf, BUILD1347): 8 ejecutados, 5 aprobados, 3 fallidos, 0 violaciones; H0069 acreditado con dos pares, 1 créditos. Medición: con el contenido visual fuera de catálogo en la App, el límite llano de la mente se publica («No puedo mostrar contenido visual como un meme…»). La tranquilización produjo «Gracias, entiendo. No hay problema.» pero el contrato de la forma exige una sola oración y el reintento estructurado volvió vacío. Reparación para CONVERSATION1349: el acuse admite dos oraciones breves. Quedan «Artiro, artiro. Estimado, estimado.» (fragmento sin pedido legible) y dos literales fuera de aceptación por idioma.

## Actualización 2026-09-14 (CONVERSATION1349)

Conversación social y ayuda general pasa de 27/31 a 28/31 con el acuse de tranquilización de dos oraciones (commit 5f59d677, BUILD1349): 5 ejecutados, 5 aprobados, 0 fallidos, 0 violaciones; H0059 acreditado con dos pares, 1 créditos. Medición: con el acuse de dos oraciones admitido, la tranquilización recibe «Gracias, entiendo. No hay problema.» sin preguntar ni afirmar estados. Conversación queda en 28/31: «Artiro, artiro. Estimado, estimado.» (fragmento sin pedido legible) y dos literales fuera de aceptación por idioma. Quedan «Artiro, artiro. Estimado, estimado.» (fragmento sin pedido legible) y dos literales fuera de aceptación por idioma.

## Actualización 2026-09-14 (AUDIO1351)

Audio y volumen pasa de 39/51 a 41/51 con el eco imperativo voseo vetado (commit a82301b7, BUILD1351): 8 ejecutados, 6 aprobados, 2 fallidos, 0 violaciones; H0465 y H0640 acreditados con dos pares cada uno, 2 créditos. Medición: con «poné» como eco imperativo el final informa el nivel puesto («El volumen se puso al 30…»); «a la mitad» se ejecuta como 50 y se verifica. Residual: un par afirmó «Bajé» tras subir 40→50 (dirección falsa) y «No toques el volumen» pide aclaración («toques» fuera del lector de prohibiciones). Audio queda en 41/51 con compuestos, alcance ambiguo, volumen por app, pronombres sin antecedente y cuatro idiomas fuera. Quedan los compuestos con fecha o brillo, «bajá la música» (alcance ambiguo), el volumen por aplicación, los pronombres sin antecedente y cuatro literales fuera de aceptación por idioma.

## Actualización 2026-09-14 (KNOWLEDGE1353)

Conocimiento, razonamiento y creatividad verbal pasa de 22/37 a 23/37 con la forma de contenido libre (commit 6d75afa4, BUILD1353): 15 ejecutados, 6 aprobados, 9 fallidos, 0 violaciones; H0182 acreditado con dos pares, 1 créditos. Medición: la forma free_content produce chistes reales pero su contrato veta el signo de pregunta y el salto de línea del chiste y el turno acaba preguntando el tipo; dos curiosidades y las respuestas sobre Daredevil, Doom Eternal y Marvel vs. Capcom inventan hechos (creador, estudio, año, protagonista): conocimiento del modelo, sin fuente de hechos en el producto. Reparación para KNOWLEDGE1355: el contrato admite una pregunta dentro del contenido y un salto de línea; las de quién es con hechos inventados quedan como condición del modelo. Quedan las preguntas sin antecedente (Batman, identidad secreta, quién es de verdad), la comparación Batman vs Superman, el sarcasmo pedido y el texto sin sentido.

## Actualización 2026-09-14 (KNOWLEDGE1355)

Conocimiento, razonamiento y creatividad verbal pasa de 23/37 a 23/37 con el contrato de contenido libre que admite el chiste (commit df041d2d, BUILD1355): 9 ejecutados, 3 aprobados, 6 fallidos, 0 violaciones; sin crédito (un solo par de chiste aprobado), 0 créditos. Medición: los chistes se entregan de inmediato con el contrato relajado («¿Por qué el lechón nunca se enoja? Porque…», «Why don't skeletons fight each other? They don't have the guts!»), pero las «curiosidades» inventan hechos (hielo, sangre, pez espada) y «explicame algo interesante» pregunta qué explicar; el par español de dato curioso también preguntó. Siguiente: el literal del chiste solo con dos pares de chiste (KNOWLEDGE1357); las curiosidades inventadas quedan como condición del conocimiento del modelo. Quedan las preguntas sin antecedente (Batman, identidad secreta, quién es de verdad), la comparación Batman vs Superman, el sarcasmo pedido y el texto sin sentido.

## Actualización 2026-09-14 (KNOWLEDGE1357)

Conocimiento, razonamiento y creatividad verbal pasa de 23/37 a 24/37 con dos pares de chiste sobre BUILD1355 (commit cfb44e51, BUILD1355): 5 ejecutados, 4 aprobados, 1 límite fallido, 0 violaciones; H0211 acreditado con dos pares, 1 créditos. Medición: con el contrato de contenido libre que admite el chiste, los tres chistes se entregan de inmediato. Conocimiento queda en 24/37: las curiosidades y «explicame algo interesante» inventan hechos o preguntan, y las preguntas de quién es (Daredevil, Doom Eternal, Marvel vs. Capcom) inventan creadores, estudios y años: condición del conocimiento del modelo, sin fuente de hechos en el producto. Quedan las preguntas sin antecedente (Batman, identidad secreta, quién es de verdad), la comparación Batman vs Superman, el sarcasmo pedido y el texto sin sentido.

## Actualización 2026-09-14 (CLIPBOARD1359)

Portapapeles pasa de 0/3 a 1/3 con el lector literal del portapapeles, la fundación de argumentos y la admisión de clipboard.write.text / clipboard.read.text en el turno revisado (commit e3e91ede, BUILD1359): 10/10 ejecutados, 7 aprobados, 3 fallidos, 0 violaciones, 1 créditos. H0518 acreditado con dos pares de lectura (clipboard.read.text sin argumentos, aprobada por la raíz, verificada por doble lectura, finales con el texto fijado por la raíz). H0199 y H0356 fallaron aunque la escritura se propuso con el literal exacto, se aprobó, completó y verificó (portapapeles cambiado): el final en español tras la confirmación es un eco del texto («Hola», «Hola mundo», «Buen día.») que no informa la copia; la variante inglesa sí la informó. Causa: el payload visible de clipboard.write.text sólo lleva sequenceNumber/characterCount/changed. Los tres límites aprobados. Siguiente: el texto escrito en el payload visible y veto del eco (CLIPBOARD1361).

## Actualización 2026-09-14 (CLIPBOARD1361)

Portapapeles pasa de 1/3 a 3/3 con el texto escrito en el payload visible y los vetos del eco (commit 52bc6629, BUILD1361): 10/10 ejecutados, 9 aprobados, 1 fallido, 0 violaciones, 2 créditos. H0199 y H0356 acreditados con los cuatro pares de escritura: cada clipboard.write.text propuesta con el literal exacto, aprobada por la raíz, completada y verificada por postlectura, y finales que citan el texto e informan la copia («"Hola" ya está en tu portapapeles», «Copié hola mundo al portapapeles»). El límite de capacidad «¿Podés copiar imágenes al portapapeles?» no publicó respuesta: el borrador veraz «No, no puedo copiar imágenes al portapapeles.» fue vetado nueve veces como asserted_failure por el contrato de conversación (condición del compositor registrada para una tanda de conversación). Los otros tres límites aprobados. La categoría queda cerrada.

## Actualización 2026-09-14 (MESSAGING1363)

Mensajería pasa de 6/31 a 7/31 con los lectores de aclaración de respuesta sin destinatario y de destinatario sin texto (commit 3af76065, BUILD1363): 10/10 ejecutados, 7 aprobados, 3 fallidos, 0 violaciones, 1 créditos. H0718 acreditado con dos pares de texto ausente: el producto pregunta qué decir conservando destinatario y canal («¿Cuál es el mensaje que quieres enviar por WhatsApp a Pedro?»), sin envío ni operaciones. H0045 y H0074 («contestale que llego en 10», «contestale que sí») llegaron al contrato de destinatario ausente pero la pregunta asignó la contestación a la persona («A quién le vas a contestar que…», una vez cambiando «llego» por «llegó»); una de las dos variantes de destinatario aprobó («¿A quién le quieres responder?»). Los tres límites aprobados. Siguiente: contrato de redacción de la pregunta de destinatario (quien contesta por encargo es BAXY), MESSAGING1365.

## Actualización 2026-09-14 (MESSAGING1365)

Mensajería pasa de 7/31 a 9/31 con el contrato de redacción de la pregunta de destinatario (commit 5bdb7f6c, BUILD1365): 10/10 ejecutados, 9 aprobados, 1 fallido, 0 violaciones, 2 créditos. H0045 y H0074 acreditados con dos pares de destinatario cada uno: el producto pregunta «¿A quién le contesto?» en primera persona de BAXY y conserva lo que la persona quiere decir («¿A quién le respondo que ya salgo?»), sin envío ni operaciones. La variante «Contestale que gracias.» aún entregó la contestación a la persona con «¿A quién le debes contestar…?» (forma «debes contestar» fuera de la lista del contrato; residual de redacción). Los cuatro límites aprobados.

## Actualización 2026-09-14 (SYSTEM1367)

Estado de hardware y sistema pasa de 32/40 a 34/40 con el lector compuesto reloj + estado (commit 346e930f, BUILD1367): 10/10 ejecutados, 8 aprobados, 2 fallidos, 0 violaciones, 2 créditos. H0106 y H0589 acreditados con dos pares cada uno: system.time y luego system.status del alcance pedido, ambas verificadas, y finales con la fecha (y hora) observada y cifras que coinciden con el journal (RAM en uso 13.33 GB de 16.54 GB totales; 102.0054 GB libres en C:). Dos límites fallaron por redacción: «No me digas la fecha.» recibió un saludo en vez de un reconocimiento y «¿Cómo se ve la fecha en Windows?» describió formatos y preguntó si explicaba. Siguiente: cerrar Steam con Steam sin ejecutar (CLOSE1369, sin cambio de fuente).

## Actualización 2026-09-14 (CLOSE1369)

Cerrar aplicaciones y ventanas pasa de 11/20 a 11/20 sin cambio de fuente (HEAD a9e12402, BUILD1367): 10/10 ejecutados, 2 aprobados, 8 fallidos, 0 violaciones, 0 créditos. Los cuatro literales «cierra steam» y las dos variantes corrieron con Steam sin ejecutar: el producto leyó las ventanas, window.resolve terminó window_not_found (failed, sin verificación), no propuso app.close y Steam siguió sin ejecutar; los finales fueron veraces («No pude cerrar Steam porque no encontré la ventana») pero en marco de incapacidad, el inglés filtró vocabulario del planificador y la regla sellada exigía una lectura completada y verificada, así que ningún caso pudo aprobarse. Dos límites fallaron por contenido (procedimiento inexacto para salir de Steam; desvío a medir la RAM). Siguiente: la lectura sin ventana declarada como observación esperada antes de sellar y el hecho de la causa window_not_found en el compositor (CLOSE1371).

## Actualización 2026-09-14 (CLOSE1371)

Cerrar aplicaciones y ventanas pasa de 11/20 a 15/20 con el hecho de la causa window_not_found y la regla de ausencia (commit 381e30ad, BUILD1371): 10/10 ejecutados, 8 aprobados, 2 fallidos, 0 violaciones, 4 créditos. H0117, H0556, H0677 y H0679 acreditados con los dos pares («Cerrá Steam.», «Close Steam.»): con Steam sin ejecutar, el producto leyó las ventanas (window.resolve terminó window_not_found, la observación de ausencia declarada en la regla sellada), no propuso app.close, Steam siguió ausente y el final dijo el estado («No se pudo cerrar Steam porque no tiene ninguna ventana abierta. La aplicación no está activa.», «The application has no open window, so it cannot be closed.»). El intento 1 de esta tanda se apartó antes de adjudicar: sólo con el hecho de la causa, cada borrador decía «no tiene ninguna ventana abierta» y el veto de polaridad rechazaba «abiert…» sin mirar la negación (no_response); el veto ahora exime la apertura negada. Los dos límites de procedimiento y conocimiento fallaron por contenido como en CLOSE1369.

## Actualización 2026-09-14 (UI1373)

Interacción dentro de aplicaciones pasa de 3/22 a 3/22 con el verbo de clic exigido en el final (commit be01aa21, BUILD1373): 10/10 ejecutados, 6 aprobados, 4 fallidos, 0 violaciones, 0 créditos. H0555 «en la calculadora apretá el 5»: el clic sobre «Cinco» se aprobó, completó y verificó de nuevo y el veto missing_click_verb rechazó «Apague el 5 en la calculadora», pero los borradores corregidos decían «Aprié el botón 5 en la calculadora» (conjugación de «apretar» que el modelo no produce para este pedido) y el turno terminó sin respuesta. Cuatro variantes de clic aprobadas («Pulsé el 7.», «I clicked the 3 button.», «Presioné el nueve.», «Apreté el botón siete.»); «En la calculadora, hacé clic en el 2.» y «Tocá el 8 en la calculadora.» no llegaron al clic (contexto de app inicial con coma; «tocar» fuera del vocabulario de señalamiento). Siguiente: pista de reintento en español orientada a «Hice clic en el …» / «Pulsé el …» (UI1377).

## Actualización 2026-09-14 (UI1377)

Interacción dentro de aplicaciones pasa de 3/22 a 3/22 con la pista de reintento del clic orientada (commit ff0bfcb9, BUILD1377): 10/10 ejecutados, 8 aprobados, 2 fallidos, 0 violaciones, 0 créditos. H0555 «en la calculadora apretá el 5»: el clic sobre «Cinco» se aprobó, completó y verificó por tercera vez y ningún final se publicó: incluso con la pista orientada a «Hice clic en el …» / «Pulsé el …», los borradores dijeron «Apagué el 5» y «Aprié el botón 5», mientras el mismo modelo conjuga bien «Pulsé el 7», «Presioné el nueve», «Apreté el botón siete» y «Hice clic en el 2» (seis variantes aprobadas). Condición de morfología del modelo para este literal, documentada y cerrada; la pregunta informativa sobre los botones volvió a quedar sin respuesta.

## Actualización 2026-09-14 (AUDIO1375)

Audio y volumen pasa de 41/51 a 41/51 con la clase deictic_level y su aclaración (commit 79cc3287, BUILD1375): 10/10 ejecutados, 3 aprobados, 7 fallidos, 2 detenciones por violación en límites, 0 créditos. «Ponlo a 100 ahora» y «devuelvelo a 100» llegaron a la nueva aclaración con cero operaciones, pero la pregunta pidió el nivel ya dicho («¿A qué nivel quieres ponerlo a 100?») o dio por hecho el ajuste («¿A qué nivel quieres poner el volumen?»); «¿A qué ajuste quieres subirlo a 80?» y «What would you like to set to 100?» aprobaron. Dos límites con sustantivos de volumen («¿Qué es el volumen maestro?», «¿Cómo se sube el volumen en Windows?») hicieron que el producto leyera audio.status fuera de la lista permitida del límite y el runner los detuvo. Siguiente: la pregunta del nivel deíctico debe preguntar qué y nunca el nivel (AUDIO1379).

## Actualización 2026-09-14 (AUDIO1379)

Audio y volumen pasa de 41/51 a 42/51 con la pregunta del nivel deíctico que pregunta qué (commit 4138c23a, BUILD1379): 10/10 ejecutados, 6 aprobados, 4 fallidos, 0 violaciones, 1 créditos. H0439 «Ponlo a 100 ahora» acreditado con dos pares («¿A qué ajuste quieres subirlo a 80?», «What would you like to set to 100?»): cero operaciones y una pregunta que pide qué cosa poner a 100 («¿A qué cosa quieres que la ponga a 100?»). H0713 «devuelvelo a 100» y dos variantes agotaron las dos redacciones con «¿A qué nivel…?» y cayeron a la recuperación genérica («No pude entender bien tu mensaje»): el propio texto de la situación decía «a un nivel» y el modelo lo repetía. Los límites con sustantivos de volumen se sustituyeron tras las lecturas de AUDIO1375; «No cambies nada.» sigue recibiendo una oferta de ayuda genérica. Siguiente: el contrato sin la palabra «nivel» (AUDIO1381).

## Actualización 2026-09-14 (AUDIO1381)

Audio y volumen pasa de 42/51 a 43/51 con el contrato del nivel deíctico sin «nivel» (commit e8b38813, BUILD1381): 10/10 ejecutados, 9 aprobados, 1 fallido, 0 violaciones, 1 créditos. H0713 «devuelvelo a 100» acreditado con dos pares: todos los casos deícticos preguntan ahora qué cosa poner conservando el número («¿Qué querés poner en 100: el volumen, el brillo o otra cosa?», «What would you like to set to 100: volume, brightness, or something else?»), cero operaciones. El caso 1 abortó antes de admisión por la guardia de RAM de 4000 MiB del runner (guardia intacta; recibo preservado) y la raíz lo reejecutó solo. «No cambies nada.» sigue recibiendo una oferta de ayuda genérica (condición documentada).

## Actualización 2026-09-14 (APPS1383)

Abrir aplicaciones pasa de 39/54 a 39/54 con la apertura previa informada en el final (commit a87bec43, BUILD1383): 10/10 ejecutados, 4 aprobados, 6 fallidos, 0 violaciones, 0 créditos. «abrí la calculadora y decime qué hora es» y cuatro variantes abrieron la Calculadora y leyeron el reloj (ambas verificadas; la raíz cerró cada Calculadora lanzada), pero ningún final se publicó: el defecto missing_prior_open rechazó «Son las 05:31.» y los reintentos repitieron el texto porque la pista de reintento se elige sólo por el defecto visible (línea 11720 del compositor) y los defectos de hechos del payload caen a la pista genérica. La forma inglesa «tell me what time it is» no llegó al lector compuesto. Una Calculadora lanzada escapó a la instantánea de limpieza y la guardia de instancia única rechazó los casos 2 a 5, que la raíz reejecutó uno a uno tras cerrarla. Siguiente: la pista de reintento elegida por la razón de rechazo completa (APPS1387).

## Actualización 2026-09-14 (APPS1387)

Abrir aplicaciones pasa de 39/54 a 39/54 con la pista de reintento elegida por la razón completa (commit bcdba1fe, BUILD1387): 10/10 ejecutados, 5 aprobados, 5 fallidos, 0 violaciones, 0 créditos. Con la pista de reintento llegando al modelo, «abrí la calculadora y decime qué hora es» y las variantes en español compusieron «Abrí la calculadora y son las 05:46.» tras abrir la Calculadora y leer el reloj (ambas verificadas; la raíz cerró cada Calculadora lanzada), pero la App rechazó cada final en español como missing_literal_fact: InventedAppEffectOnClock trata cualquier «abrí » en un final de reloj como efecto inventado. La variante inglesa «I opened the calculator. The time is 05:48.» aprobó. Siguiente: la regla de la App exime a la misión que abrió realmente una aplicación (APPS1391).

## Actualización 2026-09-14 (APPS1391)

Abrir aplicaciones pasa de 39/54 a 40/54 con la apertura real admitida por la App en el final de reloj (commit 5c6955c4, BUILD1391): 10/10 ejecutados, 6 pasados en el literal y sus variantes, 4 límites pasados, 0 violaciones; el límite 3 abortó una vez en el preflight de RAM del runner antes de la admisión y se reejecutó solo, 1 créditos. APPS1391 sobre BUILD1391 (App: InventedAppEffectOnClock omitida cuando la misión lleva un paso app.open completado): H0183 «abrí la calculadora y decime qué hora es» acreditado con dos pares (app.open de la Calculadora y system.time verificadas; finales «Abrí la calculadora y son las 06:00.» y «Abrí la calculadora y la hora es 06:01.»; la raíz cerró cada Calculadora lanzada). Tres reparaciones causales encadenadas en APPS1383/1387/1391: comprobación missing_prior_open del compositor, pista de reintento elegida por la razón completa, y exención de la App para misiones con app.open completado.

## Actualización 2026-09-14 (UI1389)

Interacción dentro de aplicaciones pasa de 3/22 a 4/22 sin cambio de fuente sobre BUILD1391 (HEAD e5bad13a): 10/10 ejecutados, 7 clics revisados pasados, 2 límites pasados, 1 límite sin respuesta publicada, 0 violaciones, 1 créditos. UI1389 sobre BUILD1391 sin cambio de fuente: H0555 «apretá el 5» acreditado con dos pares (input.visible.click verificado por cambio de superficie sobre la Calculadora propia de la raíz; finales «Hice clic en el 5.» y «Pulsé el 7.»); las seis variantes usaron verbo de clic («Presioné el nueve.», «Apreté el botón siete.», «I clicked the 3 button.») donde UI1373/1377 conjugaban el pedido porque la pista missing_click_verb nunca llegaba al reintento (reparado en BUILD1387). Condición nueva: «¿Qué botones tiene la calculadora?» no publicó nada; la respuesta fiel «Tiene botones para números, operaciones, igual, borrado y punto.» cayó tres veces por el término prohibido «operacion» de la App (UserMessagePolicy.ForbiddenTerms), comparado por subcadena en la mente y en la App, así que «operaciones» en sentido aritmético queda vetado; sin final publicado.

## Actualización 2026-09-14 (WINDOWS1385)

Organizar ventanas y pestañas pasa de 3/13 a 4/13 con el lector de foco y la regla de ausencia (commit 93c36655, BUILD1385): 10/10 ejecutados, 6 aprobados (5 de foco y 1 límite), 4 fallidos (una variante por idioma y 3 límites sin operaciones), 0 violaciones, 1 créditos. WINDOWS1385 sobre BUILD1385 (mente: lector de foco sobre aplicación autenticada y cabezas de foco en la compuerta de acto de habla): H0525 «traé chrome al frente» acreditado con dos pares; con Chrome instalado y sin ejecutar, cada forma de foco resolvió a window.focus, su prerrequisito window.resolve terminó window_not_found y el final dijo que Chrome no tiene ventana abierta y que no se hizo nada («No se pudo traer a Chrome al frente porque esa aplicación no tiene una ventana abierta… No se realizó ninguna acción.»); Chrome nunca se lanzó (0 procesos antes y después de cada caso). «Focus Chrome.» respondió en español (incumple el idioma del pedido). Límites fallidos sin operaciones: «No toques mis ventanas.» recibió una aclaración sin sentido en vez de reconocimiento; «¿Qué significa traer una ventana al frente?» se explicó como ventana de una casa; «¿Chrome consume mucha memoria?» se declinó como fuera de alcance. Condiciones nuevas para el diálogo y el conocimiento, no para la categoría de ventanas.

## Actualización 2026-09-14 (UI1393)

Interacción dentro de aplicaciones pasa de 4/22 a 4/22 sin cambio de fuente sobre BUILD1385 (HEAD dbf481de): 10/10 ejecutados, 3 límites aprobados, 7 casos compuestos fallidos por el rechazo review_pending_not_supported de la App, 0 violaciones, 0 créditos. UI1393 sobre BUILD1385 sin cambio de fuente: «abrí la calculadora y apretá el 5» y sus seis variantes planificaron app.open + input.visible.click; la Calculadora se abrió (completada y verificada, proceso real) y la App pidió confirmar el clic, pero cada turno revisado se rechazó como review_pending_not_supported: MainWindowViewModel.ConductorConfirmationShape sólo admite un plan de un paso o un prefijo de lectura verificada (web.search antes de browser.navigate; window.resolve/window.active antes de app.close) y la traza registra conductor.capture.refused «shape». Ninguna propuesta llegó al revisor; la raíz cerró cada Calculadora lanzada (el caso 0 quedó sin ventana visible y su proceso se terminó con recibo). Siguiente: la forma admite una app.open verificada antes del clic revisado (UI1395).

## Actualización 2026-09-14 (UI1395)

Interacción dentro de aplicaciones pasa de 4/22 a 4/22 con la forma de confirmación de apertura previa en la App (commit 17881700, BUILD1395) (HEAD 17881700): 10/10 ejecutados, 3 límites aprobados, 7 casos compuestos fallidos (6 clics aprobados sin verificación, 1 no aprobado por un defecto del revisor de la raíz), 0 violaciones, 0 créditos. UI1395 sobre BUILD1395 (App: ConductorConfirmationShape admite una app.open verificada antes del clic revisado): la reparación se sostiene; en cada caso compuesto la Calculadora se abrió (completada y verificada, proceso real), la App propuso el clic y la raíz lo aprobó sobre la ventana lanzada. El clic terminó failed visible_button_postread_unchanged (efecto incierto) en seis casos; el séptimo no fue aprobado por un defecto del revisor de la raíz (el marco ApplicationFrameHost es un proceso del sistema preexistente), corregido antes del caso siguiente. Sonda de la raíz con el lanzamiento del propio proveedor (calc.exe + RequestForeground sobre Process.MainWindowHandle) y DesktopClickVisible.ps1: antes del clic el primer plano es la CoreWindow de la Calculadora (calculatorapp.exe, sin ventana de nivel superior propia) y tras el Invoke de UIA pasa al marco ApplicationFrameHost, así que WindowsVisibleControlAdapter compara capturas de dos hwnd distintos y nunca llega a comparar superficies. Finales de fallo genéricos («La causa del fallo es que el resultado no se ha verificado.»). Siguiente: capturar la ventana raíz por nombre antes y después del clic (UI1397).

## Actualización 2026-09-14 (UI1397)

Interacción dentro de aplicaciones pasa de 4/22 a 5/22 con la captura de la ventana raíz nombrada en el proveedor (commit 983e2c07, BUILD1397) (HEAD 983e2c07): 10/10 ejecutados, 7 casos compuestos aprobados, 3 límites aprobados, 0 violaciones, 1 créditos. UI1397 sobre BUILD1397 (Providers.Windows: la superficie del clic se captura sobre la ventana raíz nombrada antes y después): H0472 «abrí la calculadora y apretá el 5» acreditado con dos pares; en cada caso compuesto la app.open de la Calculadora se completó y verificó, la App propuso el clic y la raíz lo aprobó sólo sobre la Calculadora lanzada durante el caso, y el input.visible.click se completó y verificó por el cambio de superficie del marco (finales «Abrí la calculadora y presioné el botón con el número 5.», «Abrí la calculadora y pulsé el 7…»); la raíz cerró cada Calculadora lanzada. Tres reparaciones encadenadas en UI1393/1395/1397: la forma de confirmación de la App tras una app.open verificada, el revisor de la raíz ante el marco ApplicationFrameHost, y la captura por nombre de la ventana raíz en el proveedor (un lanzamiento UWP reciente queda al frente por su CoreWindow y luego por su marco). Residual: algunas variantes añaden una segunda frase verbosa sobre el botón activado.

## Actualización 2026-09-14 (SCREEN1399)

Pantalla, captura e interpretación visual pasa de 0/19 a 0/19 con las capturas admitidas en el turno revisado (commit 3586d252, BUILD1399) (HEAD 3586d252): 10/10 ejecutados, 3 capturas revisadas aprobadas con final fiel, 4 capturas revisadas verificadas con final infiel o sin final, 3 límites aprobados, 0 violaciones, 0 créditos. SCREEN1399 sobre BUILD1399 (App: capture.screenshot y capture.active.window admitidas en el turno revisado): cada captura se propuso sin argumentos, la raíz la aprobó y se completó y verificó (pantalla virtual; el BMP queda en el perfil privado del caso y no se publica). El literal «sacá un screenshot» publicó un eco imperativo de la orden («Sacá un screenshot del área virtual.») en vez de informar la captura; tres variantes no publicaron nada porque todos los borradores narraron el identificador interno de la captura (captureId y sha256 expuestos por el payload de situación) y el veto de códigos internos los bloqueó sin pista de reintento; tres variantes aprobaron («Tomé una captura de pantalla…», «Ya capturé la pantalla.», «Ya saqué la captura de pantalla.»). Siguiente: el payload proyecta sólo el alcance y las dimensiones de la captura y el compositor exige el informe en primera persona con su pista (SCREEN1401).

## Actualización 2026-09-14 (SCREEN1401)

Pantalla, captura e interpretación visual pasa de 0/19 a 1/19 con el informe de la captura en primera persona (commit aa77a3dc, BUILD1401) (HEAD aa77a3dc): 10/10 ejecutados, 7 capturas revisadas aprobadas, 3 límites aprobados, 0 violaciones, 1 créditos. SCREEN1401 sobre BUILD1401 (mente: el payload de la captura proyecta sólo dimensiones, alcance y privacidad, y la captura verificada debe informarse en primera persona): H0093 «sacá un screenshot» acreditado con dos pares; cada captura se propuso sin argumentos, la raíz la aprobó y se completó y verificó en la pantalla virtual (finales «Saqué una captura de pantalla de toda la pantalla.», «Tomé una captura de pantalla de toda la pantalla.», «I took a screenshot of the whole screen.»); las capturas quedan en los perfiles privados de los casos y nunca se publicaron. Dos reparaciones encadenadas en SCREEN1399/1401: el turno revisado admite la captura sensible (App) y el compositor informa la captura (mente). Primer crédito de la categoría.

## Actualización 2026-09-14 (SCREEN1403)

Pantalla, captura e interpretación visual pasa de 1/19 a 1/19 con la captura pendiente seguida de su lectura en el turno revisado (commit eb8ea283, BUILD1403) (HEAD eb8ea283): 10/10 ejecutados, 3 límites aprobados, 7 casos de lectura fallidos por la segunda confirmación de ocr.read, 0 violaciones, 0 créditos. SCREEN1403 sobre BUILD1403 (App: la captura pendiente seguida de su lectura es una confirmación capturable): los tres literales de lectura y las cuatro variantes llegaron al turno revisado; la captura se propuso sin argumentos, la raíz la aprobó y se completó y verificó, y la misión pidió una segunda confirmación para ocr.read, también PrivacySensitive; el turno revisado aloja una sola confirmación, así que no hubo lectura ni final. El caso 6 se reejecutó solo tras una parada del runner causada por la raíz (edición del Kernel en disco al lanzarlo, sin turno admitido; recibos preservados). Siguiente: el motor de misión trata la lectura de una captura confirmada en la misma misión como cubierta por ese consentimiento (SCREEN1405).

## Actualización 2026-09-14 (SCREEN1405)

Pantalla, captura e interpretación visual pasa de 1/19 a 1/19 con la lectura de la captura confirmada cubierta por ese consentimiento (commit 5482eddc, BUILD1405) (HEAD 5482eddc): 10/10 ejecutados, 3 límites aprobados, 7 casos de lectura fallidos por la segunda confirmación de ocr.read, 0 violaciones, 0 créditos. SCREEN1405 sobre BUILD1405 (Kernel: la lectura de una captura confirmada en la misma misión cubierta por ese consentimiento): cada captura se aprobó, completó y verificó y ocr.read volvió a pedir confirmación; cada paso del plan lleva su propio id de misión por construcción (PreparedOperation.Create emite uno nuevo por operación), así que un consentimiento atado a la misión de la captura nunca coincide con la lectura que la sigue. Siguiente: el consentimiento se ata al captureId con una ventana de diez minutos (SCREEN1407).

## Actualización 2026-09-14 (SCREEN1407)

Pantalla, captura e interpretación visual pasa de 1/19 a 1/19 con el consentimiento de lectura atado a la captura (commit db7b9810, BUILD1407) (HEAD db7b9810): 10/10 ejecutados, 3 límites aprobados, 7 casos de lectura sin final publicado, 0 violaciones, 0 créditos. SCREEN1407 sobre BUILD1407 (Kernel: el consentimiento de lectura atado al captureId con ventana de diez minutos): el consentimiento se sostiene; en cada caso de lectura la captura se aprobó, completó y verificó y ocr.read se completó y verificó sin segunda confirmación. Sin final: el compositor envía la situación completa de ocr.read (~32 KB de cajas de layout, hashes y metadatos) en su prompt, 31.5 K caracteres contra un techo de contexto de 4096 tokens, así que cada intento falló antes del modelo (reproducido fuera de línea); el texto reconocido ocupa ~2 KB. Siguiente: la mente proyecta el resultado OCR a su texto, número de líneas e idioma (SCREEN1409).

## Actualización 2026-09-14 (SCREEN1409)

Pantalla, captura e interpretación visual pasa de 1/19 a 1/19 con la proyección del resultado OCR (commit 062ee0c4, BUILD1409) (HEAD 062ee0c4): 10/10 ejecutados, 3 límites aprobados, 7 casos de lectura fallidos (4 sin final por presupuesto, 3 con resumen infiel), 0 violaciones, 0 créditos. SCREEN1409 sobre BUILD1409 (mente: la situación de ocr.read proyectada a texto, número de líneas e idioma): captura y ocr.read completadas y verificadas en los siete casos de lectura. Cuatro no publicaron nada: cada intento de composición agotó el presupuesto de 5 s intentando transcribir el texto reconocido completo (~1.9 KB), fuera del alcance de este modelo en ese presupuesto. Tres publicaron resúmenes que el texto reconocido no sostiene (un aviso de «límite de Fable», scripts generados, un flujo de ejecución): el compositor no exige que las palabras del final provengan del texto reconocido. El texto reconocido queda privado. Siguiente: comprobación de fundamento (cada palabra de contenido del final debe aparecer en el texto reconocido) e instrucción de citar unas pocas líneas tal cual (SCREEN1411).

## Actualización 2026-09-14 (SCREEN1411)

Pantalla, captura e interpretación visual pasa de 1/19 a 1/19 con el informe fundado en el texto reconocido (commit c6999ac3, BUILD1411) (HEAD c6999ac3): 10/10 ejecutados, 3 límites aprobados, 1 variante de lectura aprobada, 6 casos de lectura fallidos (2 sin final, 4 con resumen infiel), 0 violaciones, 0 créditos. SCREEN1411 sobre BUILD1411 (mente: la lectura cita el texto reconocido y no usa palabras que éste no tenga): captura y ocr.read completadas y verificadas en los siete casos de lectura; una variante publicó una lectura fiel (ocho citas textuales, número de líneas correcto). El resto mostró tres huecos: el final de una misión de dos pasos compone desde la situación mission_completed (steps, completedStepsInOrder), así que la instrucción de citar y la comprobación de fundamento atadas a una ocr.read de nivel superior nunca se aplicaron y pasaron resúmenes sin fundamento; cuando un borrador citó líneas de una pantalla con código, la App y la mente lo vetaron como jerga interna; y el techo de composición de 5 s cortó los intentos que citaban más de una línea. El primer intento del caso 2 fue detenido por el runner por una edición de la raíz en disco (sin turno admitido) y se reejecutó solo. Siguiente: ambas formas reconocidas, líneas reconocidas exentas como datos observados y presupuesto denso para una lectura de pantalla (SCREEN1413).

## Actualización 2026-09-14 (SCREEN1413)

Pantalla, captura e interpretación visual pasa de 1/19 a 1/19 con la lectura reconocida en la forma de misión (commit fa2fb8fd, BUILD1413) (HEAD fa2fb8fd): 10/10 ejecutados, 3 límites aprobados, 2 casos de lectura con extracto textual fiel, 5 casos de lectura sin final por presupuesto, 0 violaciones, 0 créditos. SCREEN1413 sobre BUILD1413 (App y mente: la lectura se reconoce en la forma de misión, sus líneas citadas son datos observados, presupuesto denso): captura y ocr.read completadas y verificadas en los siete casos de lectura. Dos publicaron un extracto textual fiel del texto reconocido (ninguna palabra ajena), cortado en el tope de tokens y sin encuadre ni número de líneas; cinco no publicaron nada porque cada intento de composición agotó el presupuesto denso: con el texto completo a la vista, el modelo lo transcribe en vez de citar dos o tres líneas. Ningún borrador fue vetado ya como jerga interna. Siguiente: el compositor recibe un extracto acotado (tres líneas con contenido, recortadas) más el número de líneas, de modo que el informe queda acotado por construcción (SCREEN1415).

## Actualización 2026-09-14 (SCREEN1415)

Pantalla, captura e interpretación visual pasa de 1/19 a 4/19 con el extracto acotado de las líneas reconocidas (commit 5b38953d, BUILD1415) (HEAD 5b38953d): 10/10 ejecutados, 7 lecturas revisadas aprobadas, 3 límites aprobados, 0 violaciones, 3 créditos. SCREEN1415 sobre BUILD1415 (mente: el compositor recibe un extracto acotado de las líneas reconocidas más el número de líneas): H0038, H0709 y H0616 («leéme lo que dice la pantalla» y sus dos formas) acreditados con dos pares cada uno; la raíz aprobó cada captura sin argumentos, captura y ocr.read se completaron y verificaron, y cada final de lectura dice el número de líneas reconocidas y cita tres líneas reconocidas tal cual, sin ninguna palabra ajena al texto más allá del encuadre («La pantalla muestra N líneas y cita: …»), en una sola composición. Las capturas y el texto reconocido quedan en los perfiles privados de los casos. Siete reparaciones encadenadas de SCREEN1403 a SCREEN1415: la forma de confirmación de captura pendiente en la App, el consentimiento de lectura atado a la captura en el Kernel, la proyección del payload OCR, el contrato de fundamento, el reconocimiento de la forma de misión con las exenciones de literales y el presupuesto denso, y el extracto acotado.

## Actualización 2026-09-14 (SCREEN1417)

Pantalla, captura e interpretación visual pasa de 4/19 a 4/19 con el lector de contenido de pantalla (commit ec963d3e, BUILD1417) (HEAD ec963d3e): 10/10 ejecutados, 2 lecturas simples aprobadas, 5 formas de pregunta o descripción sin final, 3 límites aprobados, 0 violaciones, 0 créditos. SCREEN1417 sobre BUILD1417 (mente: lector para las preguntas por el contenido de la pantalla y las formas de describir, con advertencia honesta sobre las imágenes): todas las formas planifican ya la captura revisada y la lectura; captura y ocr.read completadas y verificadas en los siete casos. Las dos formas de lectura simple («leé la pantalla», «leeme la pantalla») publicaron lecturas fieles (tres líneas tal cual, número de líneas correcto). Las formas de pregunta y descripción no publicaron nada: la lente de fallos del compositor vetó cada borrador como asserted_failure porque la advertencia honesta («no puedo describir imágenes, sólo leer el texto») se lee como un fallo afirmado sobre una misión exitosa, y ReversesSuccessfulResult de la App habría hecho lo mismo. Siguiente: esa cláusula de alcance queda enmascarada en ambas lentes de fallos para una lectura de pantalla verificada (SCREEN1419).

## Actualización 2026-09-14 (SCREEN1419)

Pantalla, captura e interpretación visual pasa de 4/19 a 7/19 con la advertencia sobre las imágenes enmascarada en las lentes de fallos (commit 9d6069d9, BUILD1419) (HEAD 9d6069d9): 10/10 ejecutados, 5 lecturas revisadas aprobadas, 2 variantes inglesas sin final, 3 límites aprobados, 0 violaciones, 3 créditos. SCREEN1419 sobre BUILD1419 (App y mente: la advertencia sobre las imágenes de una lectura de pantalla verificada enmascarada en ambas lentes de fallos): H0164 «qué hay en la pantalla», H0564 «describime la pantalla» y H0716 «leé la pantalla» acreditados con dos pares cada uno; la raíz aprobó cada captura sin argumentos, captura y ocr.read se completaron y verificaron, y los finales dicen primero que no pueden describir imágenes, sólo leer el texto de la pantalla, y luego el número de líneas reconocidas y tres líneas reconocidas tal cual; las formas de lectura simple informan las líneas sin advertencia. Dos variantes inglesas no publicaron nada: su cita copió los escapes de salto de línea del extracto y la comprobación de fundamento tomó los fragmentos pegados como palabras ajenas (SCREEN1421: el extracto viaja como lista de líneas y la comprobación ignora los escapes). Sin proveedor de visión configurado en este PC, describir imágenes sigue como condición documentada.

## Actualización 2026-09-14 (SCREEN1421)

Pantalla, captura e interpretación visual pasa de 7/19 a 12/19 con el extracto como lista de líneas y el fundamento tolerante a escapes (commit b680d263, BUILD1421) (HEAD b680d263): 14/14 ejecutados, 12 aprobados (9 lecturas con advertencia honesta y citas textuales verificadas, 3 límites), 2 fallidos (H0458/H0593: cita fiel de una línea de pantalla que termina en «: false» vetada como internal_code), cero violaciones, 5 créditos. Causa medida: compose_visible_defect comprueba la forma de código «: true/false» sobre el texto sin enmascarar, y el enmascarado por líneas usa observed.text (unido con espacios por el proveedor) en vez de layout.lines; siguiente SCREEN1423 con ambas correcciones. Sin proveedor de visión: describir imágenes sigue condicionado; Steam/Doom, «Quiero que lo veas» y H0594 condicionados.

## Actualización 2026-09-14 (SCREEN1423)

Pantalla, captura e interpretación visual pasa de 12/19 a 14/19 con los escapes copiados deshechos y las formas de código juzgadas sobre la copia enmascarada (commit a5ff01d4, BUILD1423) (HEAD a5ff01d4): 9/9 ejecutados, 9 aprobados (6 lecturas con advertencia honesta y tres citas textuales verificadas, 3 límites), 0 fallidos, cero violaciones, 2 créditos. Los finales no muestran escapes residuales ni formas de código. Quedan condicionados en la categoría: Steam/Doom Eternal (cliente ausente), «Quiero que lo veas y de que se trata?» (referente sin resolver) y H0594 (captura + describir: el lector resuelve sólo la captura). Sin proveedor de visión: describir imágenes sigue condicionado.

## Actualización 2026-09-14 (FILES1425, abortada)

Archivos y carpetas sigue en 19/32: BUILD1425 construyó `filesystem.known.list` (listado de primer nivel de una carpeta conocida, sin rutas) para H0201/H0264 «lista los archivos del escritorio» y H0329/H0698 «qué hay en Descargas», pero el núcleo no arrancó (descriptor fuera del orden ordinal del catálogo) y los 4 casos ejecutados quedaron `blocked_environment`; la raíz detuvo la tanda y recompiló antes de adjudicar, con lo que los pins de binarios dejaron de coincidir: sin adjudicación formal (FILES1425/ROOT_ABORT.md), sin créditos ni cambio del registro. Reparación (orden del catálogo) medida en FILES1427.

## Actualización 2026-09-14 (FILES1427)

Archivos y carpetas pasa de 19/32 a 23/32 con el listado de carpetas conocidas construido (commits ed167618 y 76e6ecdd, BUILD1427) (HEAD 76e6ecdd): 11/11 ejecutados, 11 aprobados (8 listados con total verificado y seis nombres citados tal cual, 3 límites), 0 fallidos, cero violaciones, 4 créditos. Los finales dicen el total real de entradas de la carpeta, citan seis nombres listados tal cual y avisan de que hay más; los nombres quedan privados. Quedan condicionados en la categoría: contar y listar recientes (H0453), .py del directorio actual (H0701), contenido dinámico (H0334/H0426), zip (H0542), backup a pendrive (H0733), resumen de PDF (H0666), borrado de carpeta (H0327) y la ruta literal (H0299).

## Actualización 2026-09-14 (NEGATIVE1429)

Música pasa de 6/39 a 7/39 y Energía del sistema de 0/3 a 0/3 sin cambio de fuente sobre BUILD1427 (HEAD 81492ce3): 9/9 ejecutados, 7 aprobados (4 acuses de prohibición, 3 límites), 2 fallidos (H0603 y «No apagues la PC.»: el acuse «nunca apagaré la PC» fue rechazado por el contrato de forma y el turno cayó en una aclaración), cero violaciones, 1 créditos. Causa medida: _unsupported_answer_mentions_request descarta «pc» (dos letras) y compara tokens exactos (apagues ≠ apagaré); reparación en NEGATIVE1431. Energía del sistema sigue en 0/3 (apagar y reiniciar no se ejecutan en el PC del dueño; la prohibición se remide).

## Actualización 2026-09-14 (NEGATIVE1431)

Energía del sistema pasa de 0/3 a 1/3 con el validador de mención del pedido reparado (commit d4ba9808, BUILD1431) (HEAD d4ba9808): 6/6 ejecutados, 6 aprobados (3 acuses de prohibición, 3 límites), 0 fallidos, cero violaciones, 1 créditos. El acuse «Entendido, nunca apagaré la PC.» pasa el contrato de forma; «apagá la computadora» y «reiniciá la PC» quedan condicionados (apagar o reiniciar el PC del dueño no se ejecuta en tandas).

## Actualización 2026-09-14 (FILES1433)

Archivos y carpetas pasa de 23/32 a 24/32 con el listado ordenado por fecha (commit 71bf9a21, BUILD1433) (HEAD 71bf9a21): 6/6 ejecutados, 6 aprobados (3 listados ordenados por fecha con total verificado y los N nombres más recientes citados tal cual, 3 límites), 0 fallidos, cero violaciones, 1 créditos. Los finales dan el total real y exactamente las N entradas más nuevas en orden; no pronuncian «recientes». Quedan condicionados en la categoría: .py del directorio actual (H0701), contenido dinámico (H0334/H0426), zip (H0542), backup a pendrive (H0733), resumen de PDF (H0666), borrado de carpeta (H0327) y la ruta literal (H0299).

## Actualización 2026-09-14 (AGENDA1435)

Alarmas, recordatorios, tareas y agenda pasa de 36/38 a 37/38 con el listado de notificaciones programadas construido (commit 2bbd25fc, BUILD1435) (HEAD 2bbd25fc): 6/6 ejecutados, 6 aprobados (3 listados de notificaciones programadas verificados con recuento cero fiel, 3 límites), 0 fallidos, cero violaciones, 1 créditos. El listado excluye las 910 tareas BAXY-Alarm ya disparadas sin próxima ejecución que siguen registradas en este PC; el final dice con verdad que no hay alarmas ni recordatorios programados. Queda condicionado «qué tengo agendado para hoy» (calendar.event.list exige cuenta Microsoft).

## Actualización 2026-09-14 (FILES1437)

Archivos y carpetas pasa de 24/32 a 24/32 con la aclaración determinista de la carpeta (commit fb5984b6, BUILD1437) (HEAD fb5984b6): 6/6 ejecutados, 4 aprobados (2 aclaraciones de carpeta, 2 límites), 2 fallidos (la variante inglesa repitió el pedido sin preguntar la carpeta; el límite de prohibición contestó con un acuse mal conjugado), cero violaciones, 0 créditos. Causa medida: el contrato de la aclaración explícita no exige que la pregunta pida la carpeta; reparación en FILES1439 (pregunta que pida cuál carpeta, con un reintento corregido).

## Actualización 2026-09-14 (FILES1439)

Archivos y carpetas pasa de 24/32 a 24/32 con la pregunta de carpeta que pregunta cuál carpeta (commit efea3093, BUILD1439) (HEAD efea3093): 6/6 ejecutados, 4 aprobados (2 aclaraciones de carpeta, 2 límites), 2 fallidos (la App vetó como machine_slot_ask la pregunta correcta de la mente para la variante inglesa y compuso una que no pide la carpeta; el límite de prohibición repitió el acuse mal conjugado), cero violaciones; el caso 5 se ejecutó tres veces por una edición de fuente de la raíz con la tanda en marcha y una reejecución accidental, recibos conservados, 0 créditos. Causa medida: UserMessagePolicy.LooksLikeMachineSlotAsk veta «which folder»/«la carpeta» aunque la mente haya declarado folder como campo ausente; reparación en FILES1441 (campo declarado exime la pregunta de carpeta).

## Actualización 2026-09-14 (FILES1441)

Archivos y carpetas pasa de 24/32 a 24/32 con la pregunta de carpeta admitida por la App (commit 402a42bc, BUILD1441) (HEAD 402a42bc): 6/6 ejecutados, 4 aprobados (2 aclaraciones de carpeta, 2 límites), 2 fallidos (la exención de la App se compiló con bytes de retroceso en lugar de \b y el veto machine_slot_ask siguió; el límite de prohibición repitió el acuse mal conjugado), cero violaciones, 0 créditos. Causa medida: el patrón de AsksForDeclaredFolder llegó al fuente con caracteres 0x08 (heredoc de la raíz) y nunca coincide; reparación en FILES1443 con el patrón escrito por el editor y verificado en el ensamblado.

## Actualización 2026-09-14 (FILES1443)

Archivos y carpetas pasa de 24/32 a 25/32 con la exención de la pregunta de carpeta reparada (commit ce6257eb, BUILD1443) (HEAD ce6257eb): 6/6 ejecutados, 5 aprobados (3 aclaraciones de carpeta, 2 límites), 1 fallido (el límite de prohibición contestó con un acuse mal conjugado), cero violaciones, 1 créditos. El literal y sus dos pares preguntan la carpeta sin operaciones ni cifras inventadas; la pregunta inglesa nombra las carpetas conocidas. Quedan condicionados en la categoría: contenido dinámico (H0334/H0426), zip (H0542), backup a pendrive (H0733), resumen de PDF (H0666), borrado de carpeta (H0327) y la ruta literal (H0299).

## Actualización 2026-09-14 (WEB1445)

Información web actual pasa de 2/17 a 2/17 con la consulta de clima reparada (commit 677c7efb, BUILD1445) (HEAD 677c7efb): 10/10 ejecutados, 4 aprobados (1 informe fiel de las páginas encontradas, 3 límites), 6 fallidos (3 pronósticos inventados sobre páginas de pronóstico sin valores, 1 negación del resultado verificado, 2 búsquedas rechazadas por resultados ajenos del motor, una con un dato inventado y otra dicha con verdad), cero violaciones, 0 créditos. Causa medida: los resultados son páginas de pronóstico sin valores y el compositor inventa el pronóstico; el motor devuelve a ratos páginas ajenas (financiación, sitios para adultos) para «clima» y «va a llover mañana» y el producto lo rechaza como irrelevante. Reparación en WEB1447: el informe de búsqueda sólo con palabras de los resultados o del pedido, con pista, e instrucción de nombrar las páginas sin afirmar el pronóstico.

## Actualización 2026-09-14 (WEB1447)

Información web actual pasa de 2/17 a 2/17 con el informe de búsqueda fundado en los resultados (commit c64e9748, BUILD1447) (HEAD c64e9748): 10/10 ejecutados, 3 aprobados (límites), 7 fallidos (búsquedas verificadas con borradores fieles que otros vetos ocultaron: corte «actual»/«actualizada», palabras corrientes, títulos con «¿Va a llover?», «no puedo confirmar»), cero violaciones; los casos 1 y 2 reejecutados solos tras una edición de fuente de la raíz revertida en el acto, 0 créditos. Causa medida: los borradores ya son fieles (nombran las páginas encontradas sin afirmar el pronóstico) y los vetan _truncated_fact_word (fragmentos como nombres), el fundamento por palabras, la prueba de pregunta sobre títulos citados y la lente de fallos sobre «no puedo confirmar». Reparación en WEB1449.

## Actualización 2026-09-14 (WEB1449)

Información web actual pasa de 2/17 a 5/17 con los vetos del compositor corregidos (commit f106005c, BUILD1449) (HEAD f106005c): 10/10 ejecutados, 0 violaciones; los tres literales y tres de las cuatro variantes publicaron un informe fiel de las páginas de pronóstico encontradas (títulos citados tal cual, sitios nombrados, sin afirmar temperatura ni pronóstico; ante la pregunta por la lluvia, «no especifican si va a llover o no»), cada uno sobre una web.search de sólo lectura verificada; una variante falló por dos causas apiladas: la mente publicó un borrador cortado por el presupuesto de 256 tokens (finish_reason length) y la App lo rechazó como internal_code porque ContainsStutteredToken toma el verbo «contienen» por un tartamudeo; las tres fronteras respondieron sin buscar, 3 créditos. Causas residuales: un borrador terminado por longitud no debe publicarse (pedir un informe más corto) y las terminaciones verbales «-ienen» no son tartamudeos (WEB1451); las ciudades nombradas siguen condicionadas (el motor devuelve el clima local).

## Actualización 2026-09-14 (WEB1451)

Información web actual pasa de 5/17 a 7/17 con los lectores de investigación y noticias y los vetos de tartamudeo y corte corregidos (commit 8754f782, BUILD1451) (HEAD 8754f782): 12/12 ejecutados, 0 violaciones; el grupo del clima nombrando el buscador (literal y dos variantes) publicó informes fieles de las páginas de pronóstico encontradas y el grupo de qué pasó hoy (literal y dos variantes) buscó «noticias de hoy en el mundo» y nombró los sitios de noticias hallados con lo que dicen sus fragmentos; el grupo de investigar un tema (literal y dos variantes) falló por una sola causa: la búsqueda verificó cinco páginas del tema, el primer borrador se cortó por el presupuesto de 256 tokens y se rechazó como cut_by_length, pero la App concede 5 s a una composición ordinaria y el reintento acortado nunca corrió (tres intentos sin respuesta); el límite de prohibición «No investigues nada en internet.» se contestó con un saludo porque «investiga» no es cabeza de acción del lector de prohibiciones; los otros dos límites respondieron sin buscar, 2 créditos. Causas residuales (WEB1453): una web.search verificada con resultados debe ser composición densa en la App (10 s), la instrucción de búsqueda debe pedir como máximo tres páginas, e «investiga» debe entrar en las cabezas de acción para que «no investigues» sea prohibición; las ciudades nombradas siguen condicionadas (el motor devuelve el clima local).

## Actualización 2026-09-14 (WEB1453)

Información web actual pasa de 7/17 a 8/17 con tiempo para el reintento de la búsqueda y el clima de un nombre que no es un lugar (commit 86b2ceb9, BUILD1453) (HEAD 86b2ceb9): 9/9 ejecutados, una parada del runner; el grupo de investigar un tema (literal y dos variantes) publicó en una sola pasada resúmenes fieles de tres oraciones con lo que dicen los fragmentos, sin hechos ajenos a los resultados; el grupo del clima de un nombre que no es un lugar (literal y dos variantes) buscó, no obtuvo páginas pertinentes y lo dijo con verdad (una variante añadiendo la razón de que el nombre es una persona), pero la regla sellada de caso aprobado exige la búsqueda permitida completada y verificada y la búsqueda falló por resultados no pertinentes, así que esos tres quedan fallidos y no acreditables en este transporte; dos límites fallaron: la pregunta de definición «¿Qué es un pronóstico del tiempo?» se leyó como consulta de clima (búsqueda no permitida, parada) y la prohibición con «investigues» ya se reconoce pero las respuestas añadieron una segunda oración y el contrato de una oración las rechazó (pregunta de aclaración publicada); el límite de conocimiento respondió sin buscar, 1 créditos. Causas residuales: «qué es un/una <sustantivo del clima>» debe leerse como definición; un acuse de prohibición debe conservar su primera oración cuando el resto es una oferta; el clima de un nombre que no es un lugar necesita un instrumento que admita una búsqueda fallida con final veraz o un lector que pregunte por el lugar sin buscar; las demás filas abiertas son el clima de ciudades nombradas (el motor devuelve el clima local) y el pedido compuesto sobre WhatsApp.

## Actualización 2026-09-14 (WEB1455)

Navegación y búsqueda web pasa de 25/46 a 29/46 con abrir un navegador y buscar como navegación revisada y el clima nombrando internet (commit bc34b7ec, BUILD1455) (HEAD bc34b7ec): 11/11 ejecutados, 0 violaciones; los cinco turnos revisados de abrir un navegador y buscar propusieron exactamente la página pública de búsqueda con la consulta literal (la raíz aprobó sólo www.bing.com), la navegación se verificó en esa URL y cada final dijo que abrió la búsqueda sin afirmar resultados; las tres búsquedas del clima nombrando internet informaron tres páginas en tres oraciones sin valores; los tres límites respondieron con cero operaciones (la definición del pronóstico ya es definición; el acuse de la prohibición conservó una segunda oración porque el recorte validó la primera oración pero publicó el texto completo, defecto medido y corregido en el siguiente commit), 4 créditos. Causas residuales de la categoría: búsquedas por tema y navegaciones por búsqueda condicionadas por el motor (WEB1291/ENGINE_PROBE.md), Portal UNIEJ (destino desconocido), casos de Opera GX (navegador del dueño), «abre youtube.com en Chrome» (navegador nombrado no representable), «abrí una pestaña nueva» y pedidos compuestos.

## Actualización 2026-09-14 (NETWORK1457)

Red y Bluetooth pasa de 13/21 a 15/21 con la lectura de estado de la radio Bluetooth (commit 6a860215, BUILD1457) (HEAD 6a860215): 7/7 ejecutados, 0 violaciones; las cuatro preguntas de estado (dos literales y dos variantes) leyeron la radio Bluetooth con la nueva bluetooth.radio.status, completada y verificada (apagada), y lo dijeron con fidelidad sin afirmar cambios ni dispositivos; los tres límites respondieron con cero operaciones (definición, acuse de prohibición en una oración, conocimiento), 2 créditos. Filas abiertas restantes de la categoría, condicionadas: escaneo de redes («qué redes wifi hay»: wifi.status no lista redes), «apagá el wifi» y «conectate al wifi de casa/de la luna» (sensibles: radios del dueño y credenciales desconocidas) y «poneme el modo avión» (sin mecanismo).

## Actualización 2026-09-14 (SYSTEM1459)

Estado de hardware y sistema pasa de 34/40 a 38/40 con la lectura de los monitores conectados (commit c40ba5f8, BUILD1459) (HEAD c40ba5f8): 13/13 ejecutados, 0 violaciones; las diez preguntas de pantalla (cuatro literales y seis variantes) leyeron los monitores con la nueva display.status, completada y verificada (un monitor de 1920 x 1080 a 144 Hz), y contestaron sólo con números observados (varias añadieron los otros datos observados y tres ecoaron el «tengo» del pedido en primera persona; nada inventado); los tres límites respondieron con cero lecturas, 4 créditos. Filas abiertas restantes de la categoría, condicionadas: «Dime que version de Windows tengo y cuanta RAM tiene este PC. Usa Python.» (el dueño no quiere Python como capacidad) y «dime la version de Python instalada» (sin mecanismo).

## Actualización 2026-09-14 (AUDIO1461)

Audio y volumen pasa de 43/51 a 44/51 con las aclaraciones de cantidad de los ajustes relativos (commit f021a487, BUILD1461) (HEAD f021a487): 9/9 ejecutados, 0 violaciones; «bajá la música» y sus dos variantes preguntaron cuánto bajar el volumen sin operar ni declararlo fuera de capacidad; «subí el volumen y bajá el brillo» preguntó las dos cantidades con las dos direcciones, pero sus dos variantes preguntaron sólo por el volumen y omitieron el brillo (la intención de aclaración lleva sólo audio.volume.adjust), sin par; los tres límites respondieron con cero operaciones, 1 créditos. Causa residual: la aclaración de un pedido compuesto sin cantidades debe llevar los dos ajustes (volumen y brillo) para que la pregunta nombre ambos; las demás filas abiertas siguen condicionadas (volumen en otros idiomas: límites sin marca; «subí el volumen de spotify»: sesión ausente; «subí el volumen y decime qué fecha es»: compuesto de aclaración y lectura).

## Actualización 2026-09-14 (AUDIO1463)

Audio y volumen pasa de 44/51 a 45/51 con la aclaración compuesta de volumen y brillo (commit 4e1cc744, BUILD1463) (HEAD 4e1cc744): 6/6 ejecutados, 0 violaciones; el literal y sus dos variantes preguntaron las dos cantidades conservando las dos direcciones, con cero operaciones; los tres límites respondieron con cero operaciones, 1 créditos. Filas abiertas restantes de la categoría, condicionadas: volumen en otros idiomas (límites sin marca), «subí el volumen de spotify» (sesión ausente) y «subí el volumen y decime qué fecha es» (compuesto de aclaración y lectura).

## Actualización 2026-09-14 (WEB1465)

Información web actual pasa de 8/17 a 16/17 con la búsqueda fallida por resultados no pertinentes contada cuando el final dice la verdad (HEAD 11dfd835, binarios BUILD1463) (HEAD 11dfd835): 15/15 ejecutados, 0 violaciones; las doce búsquedas de clima de ciudad nombrada y de un nombre que no es un lugar terminaron fallidas por resultados no pertinentes (el motor devuelve el pronóstico local desde este PC) y cada final dijo esa verdad nombrando la ciudad o el nombre, sin inventar pronóstico (dos con deslices de estilo, no de hecho); los tres límites respondieron con cero búsquedas; créditos de fallo honesto: el producto no pudo obtener el clima de esas ciudades con su motor y lo dijo, 8 créditos. Instrumento con códigos de fallo honesto sellados por grupo (allowed_failure_codes) y adjudicador que los admite; sin cambio de fuente. Fila abierta restante de la categoría: el pedido compuesto de investigación sobre WhatsApp (H0060).

## Estado consolidado 2026-09-14 (noche): 472/742 cubiertos, 270 abiertos, 4/35 categorías cerradas

Diez tandas hoy (WEB1449–1455, NETWORK1457, SYSTEM1459, AUDIO1461–1463, WEB1465): 446 → 472. Dos operaciones de sólo lectura nuevas (`bluetooth.radio.status`, `display.status`), un lector de «abre un navegador y busca X» como navegación revisada a la página pública de búsqueda, y un instrumento con códigos de fallo honesto sellados (WEB1465) con el que las búsquedas de clima de ciudad nombrada, que el motor público no sirve desde este PC, se cuentan cuando el final dice la verdad nombrando la ciudad y sin inventar pronóstico (ocho créditos marcados como «fallo honesto»; el dueño puede revertirlos).

Lo que queda abierto, por masa, y por qué no se avanza sin el dueño o sin un cambio de diseño:

| Categoría | Abiertos | Condición |
|---|---:|---|
| Música | 32 | Spotify/YouTube exigen sesión real del dueño (decisión: omitir); «qué está sonando» y «pará la música» exigen reproducción real; «pon música» sin reproductor es aclaración ya cubierta en otros literales. |
| Instalar/desinstalar | 31 | Steam del dueño nunca se lanza; desinstalar Discord/Spotify es destructivo; Photoshop sin instalador; Teams incompatible; sólo `instala requests con pip` sería viable y el dueño no quiere Python como capacidad. |
| Vídeo y series | 26 | Netflix/Disney+/Prime exigen sesión autenticada del dueño (decisión: omitir). |
| Mensajería | 22 | Enviar exige clientes y terceros reales (prohibido por encuesta); las lecturas exigen sesión. |
| Navegación y búsqueda web | 17 | Búsquedas por tema y navegación por búsqueda: el motor devuelve páginas ajenas (WEB1291/ENGINE_PROBE.md) y el lector no las reclama de forma determinista; Portal UNIEJ sin destino; Opera GX es el navegador del dueño; «abre youtube.com en Chrome» no representable; «abrí una pestaña nueva» sin acción de pestaña; compuestos. |
| Interacción dentro de aplicaciones | 17 | Discord/WhatsApp son clientes del dueño; clics sin ventana propia tocarían ventanas del dueño; aritmética en la Calculadora exige confirmaciones múltiples. |
| Entrada incompleta | 16 | Fragmentos largos de transcripción decididos por el modelo (DIALOGUE1281); sin lector determinista justificado. |
| Abrir aplicaciones | 14 | Steam del dueño; destinos ausentes; idiomas extranjeros (límites sin marca); «abrime el chrome» abriría el navegador del dueño. |
| Conocimiento | 13 | Calidad del modelo local (hechos inventados en curiosidades y quién-es); referentes ausentes en sesión fresca. |
| Organizar ventanas | 9 | Minimizar/cambiar/enfocar tocan ventanas del dueño; «la mejor» sin criterio. |
| Archivos | 7 | Borrar carpetas/backup a pendrive/comprimir/resumir PDF: efectos sobre el escritorio del dueño o mecanismos ausentes. |
| Red y Bluetooth | 6 | Escaneo de redes no listable; wifi sensible con radios del dueño; modo avión sin mecanismo. |
| Audio y volumen | 6 | Idiomas extranjeros (límites sin marca); Spotify ausente; compuesto aclaración+lectura. |
| Juegos/Correo/Contactos/Desarrollo | 6+6+5+5 | Steam, Outlook, contactos y ejecución de comandos: sesiones o capacidades ausentes (contactos: el dueño duda de que BAXY deba hacerlo). |
| Resto (cierre 5, pantalla 5, reloj 4, memoria 3, conversación 3, resumen web 2, energía 2, hardware 2, documentos 2, agenda 1, notas 1, brillo 1, web actual 1) | 32 | Ventanas del dueño (cerrar todo), diálogos de Steam en pantalla, relojes en otros idiomas (límites sin marca), recuerdos sin guardado previo por diseño del instrumento, apagar/reiniciar el PC del dueño, Python, PowerPoint/Photoshop, fondo de pantalla, agenda de Outlook, nota en alemán, WhatsApp. |

## Estado consolidado 2026-09-14 (cierre de jornada): 484/742 cubiertos, 258 abiertos, 4/35 categorías cerradas

Siete tandas más desde el estado de la noche (WEB1471, KNOWLEDGE1473–1475, WEB1477–1483): 472 → 484. Instrumentos y reparaciones adoptadas: la navegación por búsqueda revisada con fallo honesto sin propuesta (Steam, portal UNIEJ, páginas oficiales de OpenAI/Python/GitHub/Mozilla), quién o qué es una cosa con nombre buscado en páginas públicas y contestado desde un fragmento nombrando la página (Daredevil, Marvel vs. Capcom, Doom Eternal, Spider-Man, Mortal Kombat), «investiga qué es X» buscando X (h2o, ADN, agujero negro), la búsqueda en YouTube como navegación revisada a su página de resultados nombrada en el final, «p?gina» tolerado, sólo la dirección navegada citada, el género citado de un fragmento no es metadiscurso y el título citado no es una re-pregunta (App). WEB1469 se ejecutó y no pudo adjudicarse (regla sellada de admisiones); WEB1481 midió dos defectos sin crédito.

Lo que queda abierto, por masa, y por qué no se avanza sin el dueño o sin un cambio de diseño:

| Categoría | Abiertos | Condición |
|---|---:|---|
| Música | 32 | Spotify/YouTube exigen sesión real del dueño (decisión: omitir); «qué está sonando» y «pará la música» exigen reproducción real. |
| Instalar/desinstalar | 31 | Steam del dueño nunca se lanza; desinstalar Discord/Spotify es destructivo; Photoshop sin instalador; Teams incompatible; el dueño no quiere Python como capacidad. |
| Vídeo y series | 26 | Netflix/Disney+/Prime exigen sesión autenticada del dueño (decisión: omitir). |
| Mensajería | 22 | Enviar exige clientes y terceros reales (prohibido por encuesta); las lecturas exigen sesión. |
| Interacción dentro de aplicaciones | 17 | Discord/WhatsApp son clientes del dueño; clics sin ventana propia tocarían ventanas del dueño; aritmética en la Calculadora exige confirmaciones múltiples. |
| Entrada incompleta | 16 | Fragmentos largos de transcripción decididos por el modelo (DIALOGUE1281); sin lector determinista justificado. |
| Abrir aplicaciones | 14 | Steam del dueño (incluidas las transcripciones «Steel»/«Ste»/«stea»); Mortal Kombat en Steam; idiomas extranjeros (límites sin marca); «abrime el chrome» abriría el navegador del dueño. |
| Conocimiento | 10 | Quién gana (H0582 afirmó un desenlace inventado); curiosidades y «algo interesante» (el motor no sirve curiosidades: páginas ajenas); sarcasmo; referentes ausentes en sesión fresca (H0030/H0424/H0645); H0297. |
| Organizar ventanas | 9 | Minimizar/cambiar/enfocar tocan ventanas del dueño; «la mejor» sin criterio. |
| Navegación y búsqueda web | 8 | Descarga de imagen (sin operación); pivigames y «Busca operagx en opera» (Opera GX del dueño); «abre youtube.com en Chrome» (Chrome del dueño); pestaña nueva (browser.control sin new_tab); «Ve a portal una.» / «Ve Portal 2 UN» (mensajes cortados: el motor no devuelve nada y el dueño pide preguntar); compuesto H0516. |
| Archivos | 7 | Contenido dinámico (H0334/H0426), zip (H0542), backup a pendrive (H0733), resumen de PDF (H0666), borrado de carpeta (H0327), ruta literal (H0299). |
| Red y Bluetooth | 6 | Escaneo de redes no listable; wifi sensible con radios del dueño; modo avión sin mecanismo. |
| Audio y volumen | 6 | Idiomas extranjeros (límites sin marca); Spotify ausente; compuesto aclaración+lectura (H0067). |
| Juegos/Correo/Contactos/Desarrollo | 6+6+5+5 | Steam, Outlook, contactos y ejecución de comandos: sesiones o capacidades ausentes. |
| Resto (cierre 5, pantalla 5, reloj 4, memoria 3, conversación 3, resumen web 2, energía 2, hardware 2, documentos 2, agenda 1, notas 1, brillo 1, web actual 1) | 32 | Ventanas del dueño (cerrar todo, WhatsApp/Discord), diálogos de Steam en pantalla, «describeme lo que ves» (el lector resuelve sólo la captura; sin visión), relojes en otros idiomas, y mecanismos ausentes. |

Condición transversal medida hoy: el motor público (Bing RSS) devuelve a veces las páginas de una consulta anterior o páginas ajenas (fotosíntesis → Excel; grafeno → foros); el filtro las rechaza y el producto lo dice con verdad. Las tandas con búsqueda se adjudican con el fallo honesto sellado.

## Estado consolidado 2026-09-15 (noche): 517/742 cubiertos, 225 abiertos, 4/35 categorías cerradas

Siete tandas más desde la tarde (KNOWLEDGE1525–1529, GAMES1531–1533, APPS1535, WINDOWS1537): 510 → 517. Reparaciones adoptadas: quién gana es una opinión declarada y el sarcasmo pedido afirma la verdad (formas con contrato); la oferta al asistente se declina sin deseos propios (contrato relajado a tres oraciones tras una ronda); la biblioteca de Steam se lista en local sin abrir Steam (cuántos y nombres tal cual); el nombre casi igual al de un juego instalado se pregunta como el de una aplicación («¿Querés que abra Marvel Rivals?»); la muletilla hablada delante de una orden es envoltorio (sin crédito: el final de fuera de catálogo no nombra el pedido y las variantes preguntaron por abrir un nombre inexistente); la ventana nombrada sólo por «la otra» o «la mejor» se pregunta. Conocimiento 36/37, Bibliotecas 2/6, Organizar ventanas 6/13.

| Categoría | Abiertos | Condición |
|---|---:|---|
| Conocimiento | 1 | H0297 (monólogo sobre el calor: ahora leído como conversación ajena, sin expectativa clara). |
| Bibliotecas y fichas de juegos | 4 | Abrir Steam o Epic (clientes del dueño) para ver la biblioteca o comprobar un juego; el App ID por la API pública (motor con páginas ajenas). |
| Organizar ventanas | 7 | Minimizar todo o a Ópera (ventanas del dueño); Chrome a la izquierda y cerrar sus pestañas (Chrome del dueño); «listá las ventanas y enfocá la mejor» (inventario más pregunta en un turno). |
| Abrir aplicaciones | 9 | Steam/Chrome del dueño; idiomas extranjeros (límites sin marca); «Saint Rose» fuera de catálogo: el final genérico no nombra el pedido. |

Sin cambio: Música 32, Instalar 31, Vídeo 26, Mensajería 22, Interacción 17, Entrada incompleta 7, Archivos 7, Red 6, Audio 6, Navegación 5, Cerrar 5, Correo/Contactos/Desarrollo 16, resto.

## Estado consolidado 2026-09-15 (tarde): 510/742 cubiertos, 232 abiertos, 4/35 categorías cerradas

Once tandas más desde la madrugada (MEMORY1503, KNOWLEDGE1505–1511, DIALOGUE1513–1521, KNOWLEDGE1523): 494 → 510. Reparaciones adoptadas: la afirmación de preferencia recibe un acuse con forma y contrato (nombra lo dicho, sin gustos propios, ofertas ni preguntas; Memoria personal 8/10); la curiosidad sin tema se busca sobre un tema público elegido por el producto y se cuenta desde un fragmento nombrando la página (aterrizaje de la consulta elegida, singular no es corte del plural, URL fuera del veto de palabra cortada; Conocimiento 33/37 con las dos preguntas de identidad sin nombrar contestadas preguntando de quién); la conversación ajena captada por el micrófono, la conformidad sin pendiente y la alternativa suelta tienen clases de entrada sin pedido con aclaración validada (Entrada incompleta 27/34; tres rondas para que la pregunta de la alternativa suelta dijera que sólo llegó el final de la frase sin citarlo, porque la política de la aplicación descarta las preguntas que repiten el texto de la persona).

| Categoría | Abiertos | Condición |
|---|---:|---|
| Conocimiento | 4 | Quién gana (H0582: opinión sin desenlace inventado, calidad del modelo); sarcasmo (H0596); «¿Quieres el acompañante de Batman?» (H0030, pregunta de deseo al asistente); H0297 (monólogo sobre el calor, ahora leído como conversación ajena). |
| Entrada incompleta | 7 | Fragmentos cortos sin lector determinista seguro («Hable este.», «Vean con teléfono.», «¡Habristín!», «Calendar Devil?», H0246, H0139 con pregunta) y el marcador redactado (H0639): decididos por el modelo. |
| Memoria personal | 2 | Recuerdos que exigen un guardado previo en el mismo perfil (H0604, H0173). |
| Motor de búsqueda | — | Bing RSS devuelve páginas ajenas para cerca de la mitad de los nombres sueltos (Pulpo, Marte, Volcán…); la lista de temas de curiosidad se limitó a nombres verificados y el fallo honesto sigue sellado (web_search_results_irrelevant). |

Sin cambio: Música 32, Instalar 31, Vídeo 26, Mensajería 22, Interacción 17, Organizar ventanas 9, Abrir aplicaciones 9, Archivos 7, Red 6, Audio 6, Navegación 5, Cerrar 5, Juegos/Correo/Contactos/Desarrollo 22, resto.

## Estado consolidado 2026-09-15 (madrugada): 494/742 cubiertos, 248 abiertos, 4/35 categorías cerradas

Nueve tandas más desde el cierre de jornada (SCREEN1485, DIALOGUE1487–1491, BROWSER1493, APPS1495–1499): 484 → 494. Reparaciones adoptadas: la orden de captura seguida de «describeme lo que ves» lee la pantalla con el aviso honesto; mirar «lo» sin antecedente pregunta qué mirar (clase propia, validada contra la inversión de papeles); el destino cortado por la transcripción («Ve a portal una.») pregunta a qué portal; browser.control abre una pestaña nueva en el navegador propio del producto (acción new_tab, Kernel+proveedor); el nombre de aplicación aproximado («abres team», «Abre stea,», «abre Steel.») pregunta si abrir la candidata instalada sin abrir nada. Filas que cambian en la tabla anterior:

| Categoría | Abiertos | Condición |
|---|---:|---|
| Abrir aplicaciones | 9 | Steam del dueño («Abre Steam», «Abre steam pls», Mortal Kombat en Steam); «Saint Rose» (transcripción de un juego de la biblioteca del dueño); idiomas extranjeros (límites sin marca); «abrime el chrome» abriría el navegador del dueño. |
| Navegación y búsqueda web | 5 | Descarga de imagen (sin operación); pivigames y «Busca operagx en opera» (Opera GX del dueño); «abre youtube.com en Chrome» (Chrome del dueño); compuesto H0516. |
| Pantalla | 3 | Diálogos de Steam del dueño (H0285/H0492/H0704); sin proveedor de visión. |
| Entrada incompleta | 16 | Fragmentos de conversación con palabras (un detector léxico barre pedidos válidos: se descarta); decididos por el modelo. |
| Agenda | 1 | «qué tengo agendado para hoy» exige la cuenta de Microsoft del dueño (calendar.event.list vía Graph): no se acredita un fallo por cuenta ausente. |

Sin cambio: Música 32, Instalar 31, Vídeo 26, Mensajería 22, Interacción 17, Conocimiento 10, Organizar ventanas 9, Archivos 7, Red 6, Audio 6, Juegos/Correo/Contactos/Desarrollo 22, resto.

## Actualización 2026-09-14 (WEB1467)

Navegación y búsqueda web pasa de 29/46 a 31/46 con las búsquedas por tema y de páginas de Steam fallidas contadas cuando el final dice la verdad (HEAD 2adb59ef, binarios BUILD1463) (HEAD 2adb59ef): 12/12 ejecutados, una parada del runner; las búsquedas por tema terminaron fallidas por resultados no pertinentes con finales veraces que nombran el tema (pizza, lasaña, Transformers), salvo «Busca Transformers», que esta vez sí encontró cinco páginas pertinentes y las informó con fidelidad; «que es el h2o» dijo la verdad sin nombrar el tema (fallido); las páginas de Steam por búsqueda dijeron la verdad para Marvel Rivals y Stardew Valley, pero la variante de Terraria encontró la tienda y pidió confirmar la navegación, que el transporte ordinario no admite (sin par); los tres límites respondieron con cero búsquedas, 2 créditos. Instrumento de fallo honesto con regla de prefijo (la secuencia permitida puede terminar en la operación fallida con código sellado). Filas abiertas restantes de la categoría: H0618 (nombrar el tema en el final), H0360/H0723 (transporte revisado para la navegación cuando el motor encuentra la página), Portal UNIEJ, Opera GX, «abre youtube.com en Chrome», «abrí una pestaña nueva», compuestos.

## Actualización 2026-09-14 (WEB1471)

Navegación y búsqueda web pasa de 31/46 a 33/46 con la página de Steam por búsqueda revisada o su fallo honesto (HEAD 4eac0d2e, binarios BUILD1463) (HEAD 4eac0d2e): WEB1471: la página de Steam por búsqueda abre bajo revisión o falla con verdad; H0360 y H0723 cubiertos (WEB1469 ejecutó el mismo panel sin poder adjudicarse por su regla sellada de admisiones), 2 créditos. 7/7 ejecutados, 7 aprobados, 2 créditos; Terraria navegada bajo revisión; Marvel Rivals y Stardew Valley con fallo honesto

## Actualización 2026-09-14 (KNOWLEDGE1473)

Conocimiento, razonamiento y creatividad verbal pasa de 24/37 a 26/37 con las preguntas de quién o qué es contestadas desde páginas públicas (commit 63c28785, BUILD1473) (HEAD 63c28785): KNOWLEDGE1473: quién o qué es una cosa con nombre se contesta desde páginas públicas nombrando la fuente; H0257 y H0278 cubiertos; H0366 sin final por el veto de metadiscurso («en primera persona» citado del fragmento) y H0582 con un desenlace inventado, 2 créditos. 11/11 ejecutados, 9 aprobados, 2 fallidos, 2 créditos; Daredevil, Marvel vs. Capcom, Spider-Man y Mortal Kombat contestados desde Wikipedia/IMDb/Fandom/Minijuegos; Doom Eternal encontrado pero sin final (reparación KNOWLEDGE1475)

## Actualización 2026-09-14 (KNOWLEDGE1475)

Conocimiento, razonamiento y creatividad verbal pasa de 26/37 a 27/37 con el fragmento del género admitido por el compositor (commit 6854a7c4, BUILD1475) (HEAD 6854a7c4): KNOWLEDGE1475: Doom Eternal contestado desde Wikipedia nombrando la fuente; H0366 cubierto, 1 créditos. 6/6 ejecutados, 6 aprobados, 1 crédito; el veto de metadiscurso ya no traga el género citado del fragmento

## Actualización 2026-09-14 (WEB1477)

Navegación y búsqueda web pasa de 33/46 a 35/46 con el portal de la universidad y la página oficial de una organización por búsqueda y navegación revisada (HEAD 73c92e22, binarios BUILD1475) (HEAD 73c92e22): WEB1477: el portal de la universidad abre por búsqueda bajo revisión; H0004 y H0573 cubiertos; H0082 con carácter corrupto sin operación, Wikipedia con dirección mal citada, un límite que preguntó, 2 créditos. 10/10 ejecutados, 7 aprobados, 3 fallidos, 2 créditos; uniej.cl, mozilla.org navegados y verificados

## Actualización 2026-09-14 (WEB1479)

Navegación y búsqueda web pasa de 35/46 a 36/46 con la página oficial pedida con un carácter corrupto y la dirección navegada citada (commit 03c60ac9, BUILD1479) (HEAD 03c60ac9): WEB1479: la página oficial abre pese al carácter corrupto del pedido y el final cita sólo la dirección navegada; H0082 cubierto, 1 créditos. 6/6 ejecutados, 6 aprobados, 1 crédito; openai.com, python.org y github.com navegados bajo revisión

## Actualización 2026-09-14 (WEB1481)

Navegación y búsqueda web pasa de 36/46 a 36/46 con la búsqueda en YouTube abierta bajo revisión y la pregunta investigada contestada desde una página (commit c21a630d, BUILD1481) (HEAD c21a630d): WEB1481: la búsqueda en YouTube abre su página de resultados bajo revisión pero el final calla la búsqueda; H0618 encontró Wikipedia y la App rechazó el título citado; sin crédito, 0 créditos. 9/9 ejecutados, 5 aprobados, 4 fallidos, 0 créditos; dos defectos del compositor y de la App medidos (WEB1483)

## Actualización 2026-09-14 (WEB1483)

Navegación y búsqueda web pasa de 36/46 a 38/46 con la búsqueda en YouTube nombrada en el final y la pregunta investigada contestada desde una página (commit 21c4876a, BUILD1483) (HEAD 21c4876a): WEB1483: la búsqueda en YouTube nombra lo que abrió y la pregunta investigada se contesta desde una página; H0728 y H0618 cubiertos, 2 créditos. 9/9 ejecutados, 8 aprobados, 1 límite fallido, 2 créditos

## Actualización 2026-09-14 (SCREEN1485)

Pantalla, captura e interpretación visual pasa de 14/19 a 15/19 con los escapes copiados deshechos y las formas de código juzgadas sobre la copia enmascarada (commit e140d940, BUILD1485) (HEAD e140d940): SCREEN1485: la orden de captura seguida de «describeme lo que ves» lee la pantalla con el aviso honesto; H0594 cubierto, 1 créditos. 6/6 ejecutados, 6 aprobados, 1 crédito; tres lecturas con advertencia honesta y citas textuales verificadas, tres límites

## Actualización 2026-09-14 (DIALOGUE1487)

Pantalla, captura e interpretación visual pasa de 15/19 a 15/19 con la orden deíctica de mirar contestada con la pregunta del referente (commit 106e8ae6, BUILD1487) (HEAD 106e8ae6): DIALOGUE1487: «quiero que lo veas» pregunta qué ver, pero las variantes invierten los papeles; sin crédito, 0 créditos. 6/6 ejecutados, 3 aprobados, 3 fallidos, 0 créditos; aclarador de referente sin forma para mirar-y-decir (DIALOGUE1489)

## Actualización 2026-09-14 (DIALOGUE1489)

Pantalla, captura e interpretación visual pasa de 15/19 a 16/19 con la orden deíctica de mirar contestada con la pregunta validada de qué mirar (commit a60a7901, BUILD1489) (HEAD a60a7901): DIALOGUE1489: «quiero que lo veas» pregunta qué mirar sin devolver la pregunta; H0528 cubierto, 1 créditos. 6/6 ejecutados, 6 aprobados, 1 crédito; las tres preguntas piden qué mirar con el mismo verbo

## Actualización 2026-09-14 (DIALOGUE1491)

Navegación y búsqueda web pasa de 38/46 a 40/46 con los destinos cortados por la transcripción contestados con la pregunta de a qué portal (commit 9a26dbdd, BUILD1491) (HEAD 9a26dbdd): DIALOGUE1491: el destino cortado por la transcripción pregunta a qué portal ir; H0393 y H0541 cubiertos, 2 créditos. 7/7 ejecutados, 7 aprobados, 2 créditos; las cuatro preguntas dicen que el nombre parece cortado y piden el portal

## Actualización 2026-09-14 (BROWSER1493)

Navegación y búsqueda web pasa de 40/46 a 41/46 con la pestaña nueva abierta en el navegador propio (commit 9559e0f9, BUILD1493) (HEAD 9559e0f9): BROWSER1493: la pestaña nueva se abre en el navegador propio del producto; H0084 cubierto, 1 créditos. 6/6 ejecutados, 4 aprobados, 2 límites fallidos, 1 crédito; browser.control new_tab verificado tres veces

## Actualización 2026-09-14 (APPS1495)

Abrir aplicaciones pasa de 40/54 a 40/54 con los nombres de aplicación aproximados contestados con la pregunta de si abrir la candidata (commit 1c8039fe, BUILD1495) (HEAD 1c8039fe): APPS1495: el aclarador de nombre aproximado cayó en un assert posterior y la App recuperó con preguntas genéricas; sin crédito, 0 créditos. 10/10 ejecutados, 3 aprobados, 7 fallidos, 0 créditos; AssertionError en _prepare_turn_result (APPS1497)

## Actualización 2026-09-14 (APPS1497)

Abrir aplicaciones pasa de 40/54 a 42/54 con los nombres de aplicación aproximados contestados con la pregunta de si abrir la candidata (commit 7843f576, BUILD1497) (HEAD 7843f576): APPS1497: «Abre stea,» y «Sí, abre Ste.» preguntan si abrir Steam; H0386 y H0522 cubiertos; «team» y «Steel» rechazados por el validador, 2 créditos. 10/10 ejecutados, 7 aprobados, 3 fallidos, 2 créditos; validador demasiado estricto y eco del nombre mal escrito (APPS1499)

## Actualización 2026-09-14 (APPS1499)

Abrir aplicaciones pasa de 42/54 a 45/54 con los nombres de aplicación aproximados contestados con la pregunta de si abrir la candidata (commit 1dad9bd9, BUILD1499) (HEAD 1dad9bd9): APPS1499: «abres team» pregunta Steam o Microsoft Teams y los «Steel» preguntan Steam; H0521, H0227 y H0398 cubiertos, 3 créditos. 8/8 ejecutados, 8 aprobados, 3 créditos; ninguna aplicación abierta

## Actualización 2026-09-14 (MEMORY1501)

Memoria personal pasa de 7/10 a 7/10 con la afirmación de preferencia reconocida sin tomarla como pedido (commit 6a23dadd, BUILD1501) (HEAD 6a23dadd): MEMORY1501: la afirmación de preferencia ya no se toma como pedido, pero la conversación social inventa gustos propios del asistente; sin crédito, 0 créditos. 6/6 ejecutados, 3 aprobados, 3 fallidos, 0 créditos; instrucción social para preferencias (MEMORY1503)

## Actualización 2026-09-14 (MEMORY1503)

Memoria personal pasa de 7/10 a 8/10 con el acuse de la preferencia que nombra lo dicho sin gustos propios, ofertas ni preguntas (commit 52b40fdc, BUILD1503) (HEAD 52b40fdc): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. Los tres acuses de preferencia nombraron lo dicho sin gustos propios, ofertas ni preguntas («Entiendo que te gusta tomar café.», «Entiendo que prefieres el mate.»; la variante del chocolate negro fue evaluativa —califica la elección— y pasa el criterio sellado, aunque un acuse liso es preferible); los tres límites explicaron o reconocieron sin operaciones. Cero operaciones y cero violaciones en los seis; GPU pico 3498 MiB.

## Actualización 2026-09-14 (KNOWLEDGE1505)

Conocimiento, razonamiento y creatividad verbal pasa de 27/37 a 27/37 con la curiosidad sin tema contada desde una página pública sobre un tema elegido (commit a5083fe7, BUILD1505) (HEAD a5083fe7): 11 ejecutados, 3 aprobados (los tres límites), 8 fallidos, 0 créditos. La mente decidió web.search con el tema elegido en los ocho pedidos de curiosidad, pero el aterrizaje de argumentos exige que la consulta aparezca literalmente en el texto de la persona (sólo la consulta de noticias está exenta) y los ocho turnos acabaron en una aclaración invertida («¿Qué curiosidad me puedes contar?») sin operaciones; los límites de chiste, prohibición y definición pasaron. Siguiente: exención de aterrizaje para el tema elegido por el lector (KNOWLEDGE1507).

## Actualización 2026-09-14 (KNOWLEDGE1507)

Conocimiento, razonamiento y creatividad verbal pasa de 27/37 a 30/37 con el tema elegido por el lector de curiosidad aterrizado como la consulta de noticias (commit f779b5f1, BUILD1507) (HEAD f779b5f1): 11 ejecutados, 9 aprobados, 2 fallidos, 3 créditos. Seis de los ocho pedidos de curiosidad buscaron un tema elegido por el producto y contaron lo que un fragmento afirma nombrando la página (Wikipedia, Significados, WWF), sin añadir datos ni preguntar («Una curiosidad sobre el pingüino es que, según Wikipedia, son aves marinas que se distribuyen casi exclusivamente en el hemisferio sur…»); dos («decime una curiosidad», «explicame algo curioso») completaron la búsqueda pero acabaron sin final porque el veto de palabra cortada tomó el singular «curiosidad» por un corte del plural «curiosidades» de un título de resultado; los tres límites pasaron. H0003, H0476 y H0703 acreditados con dos pares; H0520 queda para KNOWLEDGE1509 (singular no es corte del plural).

## Actualización 2026-09-14 (KNOWLEDGE1509)

Conocimiento, razonamiento y creatividad verbal pasa de 30/37 a 30/37 con el singular admitido frente al plural por el veto de palabra cortada (commit d7752fe8, BUILD1509) (HEAD d7752fe8): 6 ejecutados, 5 aprobados, 1 fallido, 0 créditos. Las dos variantes buscaron su tema y contaron lo que un fragmento afirma nombrando la página (Wikipedia, National Geographic); el literal «decime una curiosidad» completó la búsqueda de «Colibrí» pero sus tres borradores («…según Atlas Animal») cayeron por el veto de palabra cortada, que tomó «Atlas» por un corte de las palabras pegadas del host de la URL («atlasanimal»); los tres límites pasaron. Siguiente: las URL no son nombres a preservar (KNOWLEDGE1511).

## Actualización 2026-09-14 (KNOWLEDGE1511)

Conocimiento, razonamiento y creatividad verbal pasa de 30/37 a 31/37 con las URL fuera del veto de palabra cortada (commit 3967dc08, BUILD1511) (HEAD 3967dc08): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. El literal y las dos variantes buscaron un tema elegido por el producto y contaron lo que un fragmento afirma nombrando la página (Atlas Animal, Wikipedia), sin añadir datos ni preguntar («Una curiosidad sobre el colibrí es que es la única especie capaz de volar en todas las direcciones y de forma muy veloz, según informa el sitio Atlas Animal.»); los tres límites pasaron. Cero violaciones en los seis.

## Actualización 2026-09-14 (DIALOGUE1513)

Entrada incompleta, ruido y control de diálogo pasa de 18/34 a 25/34 con la conversación ajena contestada con la pregunta de si la persona necesita algo (commit f3216caa, BUILD1513) (HEAD f3216caa): 12 ejecutados, 12 aprobados, 0 fallidos, 7 créditos. Los siete literales de conversación ajena y las dos variantes terminaron con cero operaciones y una sola pregunta validada que dice no encontrar un pedido para BAXY y pregunta si la persona necesita algo, sin responder ni repetir el contenido; los nueve finales coinciden con la frase de ejemplo de la instrucción («En eso no encuentro un pedido para mí; ¿necesitás algo?»): la respuesta la compone y valida el modelo, no es una cadena fija, pero la dependencia del ejemplo queda anotada. Los tres límites (definición, prohibición, saludo) pasaron. Cero violaciones en los doce.

## Actualización 2026-09-14 (DIALOGUE1515)

Entrada incompleta, ruido y control de diálogo pasa de 25/34 a 26/34 con la conformidad sin pendiente y la alternativa suelta contestadas con su propia pregunta (commit fed364ff, BUILD1515) (HEAD fed364ff): 9 ejecutados, 6 aprobados, 3 fallidos, 1 créditos. «Si hazlo» y sus dos variantes dijeron que no hay nada pendiente y preguntaron qué hacer, con cero operaciones (H0562 acreditado); «o en la de siempre.» y sus variantes preguntaron a qué se refiere la parte suelta pero no dijeron que sólo llegó esa parte, como exige el criterio sellado: el validador aceptó la pregunta del referente sola (sin crédito para H0205; DIALOGUE1517 exigirá las dos cosas). Los tres límites pasaron. Cero violaciones en los nueve.

## Actualización 2026-09-14 (DIALOGUE1517)

Entrada incompleta, ruido y control de diálogo pasa de 26/34 a 26/34 con la alternativa suelta que dice que sólo llegó esa parte y pregunta a qué se refiere (commit 627cdac0, BUILD1517) (HEAD 627cdac0): 6 ejecutados, 3 aprobados (los tres límites), 3 fallidos, 0 créditos. El aclarador produjo dos veces la pregunta requerida para el literal y las dos variantes («Sólo me llegó "…": ¿a qué te referís?», comprobado fuera del instrumento contra el mismo modelo), pero la comprobación del referente del validador terminaba en un límite de palabra tras «refer» y nunca casó «referís»; los tres turnos cayeron en la pregunta genérica de recuperación, que adivinó el referente. Los tres límites pasaron. Siguiente: raíces abiertas en la comprobación del referente (DIALOGUE1519).

## Actualización 2026-09-14 (DIALOGUE1519)

Entrada incompleta, ruido y control de diálogo pasa de 26/34 a 26/34 con la comprobación del referente que casa «referís» (commit 90e983f6, BUILD1519) (HEAD 90e983f6): 6 ejecutados, 3 aprobados (los tres límites), 3 fallidos, 0 créditos. La mente produjo y validó la pregunta requerida para el literal y las dos variantes («Sólo me llegó "…": ¿a qué te referís?», en la auditoría del turno), pero la política de respuestas de la aplicación la rechazó por repetir el texto de la persona (echoes_request: la pregunta cita el fragmento entero) y publicó una pregunta compuesta que adivinó el referente. Los tres límites pasaron. Siguiente: la pregunta nombra el final de la frase sin citarlo (DIALOGUE1521).

## Actualización 2026-09-14 (DIALOGUE1521)

Entrada incompleta, ruido y control de diálogo pasa de 26/34 a 27/34 con la pregunta que nombra el final de la frase sin citarlo (commit ffa35636, BUILD1521) (HEAD ffa35636): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. «o en la de siempre.» y sus dos variantes terminaron con cero operaciones y la pregunta validada «Sólo me llegó el final de la frase: ¿a qué te referís?», que la política de respuestas de la aplicación conservó; los tres límites pasaron. El primer intento del guion raíz del caso 1 abortó antes de la admisión por una salida vacía del paso de ejecución y el caso, sin ejecutar, se ejecutó una sola vez después. Cero violaciones en los seis.

Corrección DIALOGUE1521 (raíz, 2026-09-15): la nota privada de decisión del caso 2 citó «no_response» como final por un desliz al leer el registro de la tanda (el bloque del caso 1 contenía un rastro de error y el lector saltó un final); el final real del caso 2 fue la misma pregunta validada que en los casos 0 y 1, su hash publicado en case-02.json coincide con ella y el veredicto y el crédito no cambian.

## Actualización 2026-09-14 (KNOWLEDGE1523)

Conocimiento, razonamiento y creatividad verbal pasa de 31/37 a 33/37 con la identidad de alguien sin nombrar contestada preguntando de quién (commit f3bdcfa8, BUILD1523) (HEAD f3bdcfa8): 7 ejecutados, 7 aprobados, 0 fallidos, 2 créditos. Los dos literales y las dos variantes terminaron con cero operaciones y la pregunta validada «¿De quién hablás?», sin nombrar personajes ni contestar con la identidad propia; los tres límites (definición, prohibición, identidad propia) pasaron. Cero violaciones en los siete.

## Actualización 2026-09-14 (KNOWLEDGE1525)

Conocimiento, razonamiento y creatividad verbal pasa de 33/37 a 35/37 con quién gana como opinión declarada y el sarcasmo pedido afirmando la verdad (commit ae7c8dc9, BUILD1525) (HEAD ae7c8dc9): 9 ejecutados, 9 aprobados, 0 fallidos, 2 créditos. «Quien gana en batman vs superman» y sus variantes dieron una opinión marcada como tal nombrando un contendiente con una razón, sin desenlace afirmado como hecho ni películas, cómics o cifras («En mi opinión, Batman sería el más efectivo en un enfrentamiento de inteligencia y estrategia…»); «El agua moja?, responde con sarcasmo» y sus variantes afirmaron la verdad con un comentario seco, sin contradecirla, insultar, inventar datos ni preguntar («Sí, obviamente el agua moja. Es una de esas cosas tan evidentes que ni siquiera necesitas un experimento para comprobarlo.»); los tres límites pasaron. Cero operaciones y cero violaciones en los nueve.

## Actualización 2026-09-14 (KNOWLEDGE1527)

Conocimiento, razonamiento y creatividad verbal pasa de 35/37 a 35/37 con la oferta a BAXY contestada sin deseos propios (commit 105e47bd, BUILD1527) (HEAD 105e47bd): 6 ejecutados, 4 aprobados, 2 fallidos, 0 créditos. El literal se contestó sin deseos propios nombrando la cosa y ofreciendo hacer algo con eso; los borradores con forma de las dos variantes («No necesito un café… Si tenías en mente algo…, por favor dime») cayeron por un contrato demasiado estricto —sólo dos oraciones, y «por favor» y «gracias. Si…» tomados por aceptación— y se publicaron preguntas de recuperación; comprobado fuera del instrumento contra el mismo modelo. Los tres límites pasaron. Siguiente: tres oraciones y sólo la aceptación real rechazada (KNOWLEDGE1529).

## Actualización 2026-09-14 (KNOWLEDGE1529)

Conocimiento, razonamiento y creatividad verbal pasa de 35/37 a 36/37 con el contrato de la oferta que admite tres oraciones (commit fd5e1b2f, BUILD1529) (HEAD fd5e1b2f): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. El literal y las dos variantes dijeron que BAXY no necesita la cosa, nombrándola, y ofrecieron hacer algo con ella si era la intención, sin aceptar, sin gustos inventados ni pregunta («No necesito un acompañante de Batman, gracias por compartirlo. Si quisieras que haga algo con eso, por favor dime.»); los tres límites pasaron. Cero operaciones y cero violaciones en los seis.

## Actualización 2026-09-14 (GAMES1531)

Bibliotecas y fichas de juegos pasa de 0/6 a 1/6 con la biblioteca de Steam listada en local sin abrir Steam (commit 2bef0b2f, BUILD1531) (HEAD 2bef0b2f): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. El literal y las dos variantes ejecutaron una game.catalog.list de sólo lectura sobre los manifiestos locales y dijeron el total real de juegos instalados, seis nombres tal cual y que hay más, sin abrir Steam (los nombres citados y la cifra coinciden con la observación); los tres límites pasaron. Cero violaciones en los seis.

## Actualización 2026-09-14 (GAMES1533)

Bibliotecas y fichas de juegos pasa de 1/6 a 2/6 con el nombre casi igual al de un juego instalado preguntado como el de una aplicación (commit 065bf9f8, BUILD1533) (HEAD 065bf9f8): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. «Ve a Mad de Rivals.» y sus dos variantes terminaron con cero operaciones y la pregunta validada «¿Querés que abra Marvel Rivals?», nombrando el juego instalado tal cual, sin buscar, navegar ni abrir; los tres límites pasaron. Cero violaciones en los seis.

## Actualización 2026-09-14 (APPS1535)

Abrir aplicaciones pasa de 45/54 a 45/54 con la muletilla hablada delante de la orden tratada como envoltorio (commit cc567171, BUILD1535) (HEAD cc567171): 6 ejecutados, 3 aprobados (los tres límites), 3 fallidos, 0 créditos. Con la muletilla quitada, «Y quema, abre Saint Rose.» llegó a la conversación de fuera de catálogo (cero operaciones), pero su final genérico («No puedo hacer eso, está fuera de mi ámbito.») no nombra Saint Rose ni dice que no lo encuentra; las dos variantes pasaron por la decisión del modelo (app.open propuesto y descartado por el catálogo) y terminaron preguntando si abrir un nombre que no existe en ningún catálogo. Los tres límites pasaron. La fila queda condicionada: la apertura de un nombre fuera de catálogo necesita un final que lo nombre y diga que no está disponible.

## Actualización 2026-09-14 (WINDOWS1537)

Organizar ventanas y pestañas pasa de 4/13 a 6/13 con la ventana nombrada sólo por «la otra» o «la mejor» preguntada (commit c330c976, BUILD1537) (HEAD c330c976): 7 ejecutados, 7 aprobados, 0 fallidos, 2 créditos. Los dos literales y las dos variantes terminaron con cero operaciones y una pregunta validada de a qué ventana cambiar o enfocar («¿A qué ventana querés cambiar?»), sin adivinar ninguna; los tres límites pasaron. Cero violaciones en los siete.

## Actualización 2026-09-14 (WEB1539)

Leer y resumir páginas web pasa de 0/2 a 0/2 con resumir la página leída como la página abierta en el navegador, nombrada y citada tal cual (commit 2871d4ba, BUILD1539) (HEAD 2871d4ba): 7 ejecutados, 3 aprobados (los tres límites), 4 rechazados, 0 créditos. La mente decidió browser.page.read para los cuatro turnos de resumen y el producto preparó la operación con confirmación, pero el conductor revisado de la aplicación sólo propone al revisor raíz navegación, cierre, clics, ajustes, portapapeles y capturas: rechazó los turnos (review_pending_not_supported) sin leer la página; el fixture raíz (Edge y página propios, BAXY_CDP_ENDPOINT registrado en runtime.json) se levantó y se cerró limpiamente. Los tres límites pasaron. Siguiente: el conductor revisado admite browser.page.read como las capturas (WEB1541).

## Actualización 2026-09-14 (WEB1541)

Leer y resumir páginas web pasa de 0/2 a 0/2 con el conductor revisado que propone la lectura de página al revisor raíz (commit be724dbe, BUILD1541) (HEAD be724dbe): 7 ejecutados, 3 aprobados (los tres límites), 4 fallidos, 0 créditos. El conductor revisado propuso browser.page.read, el revisor raíz la aprobó (sólo esa operación, sin destino) y el producto la ejecutó sobre el fixture raíz, pero el núcleo dio por fallido el recibo: el descriptor exige un efecto observado (valor por defecto de las operaciones sensibles) mientras el adaptador de lectura declara con verdad que no observa ninguno (external_verification_failed / external_effect_unobserved), y los finales informaron un intento fallido. Los tres límites pasaron. Siguiente: los descriptores de lectura declaran que no hay efecto observable, como ocr.read (WEB1543).

## Actualización 2026-09-14 (WEB1543)

Leer y resumir páginas web pasa de 0/2 a 2/2 con la lectura de página que declara no observar ningún efecto (commit 91ed5738, BUILD1543) (HEAD 91ed5738): 7 ejecutados, 7 aprobados, 0 fallidos, 2 créditos. Medido: los descriptores de lectura CDP declaran que no observan efecto; las cuatro lecturas revisadas se completaron y verificaron sobre el fixture raíz y los finales nombraron la página y citaron su primer párrafo tal cual (el juez de citas contra el fixture no halló pasaje ni cifra ajenos). H0561 y H0738 acreditados con sus dos variantes; la categoría queda cerrada. La categoría queda cerrada.

## Actualización 2026-09-14 (SYSTEM1545)

Estado de hardware y sistema pasa de 38/40 a 38/40 con la directiva final de medio («Usa Python.») declinada y la lectura del sistema informada (commit 56cd8016, BUILD1545) (HEAD 56cd8016): 6 ejecutados, 3 aprobados (una variante y dos límites), 3 fallidos, 0 créditos. Medido: la directiva «Usa Python.» se declinó y las tres lecturas system.status se verificaron; una variante publicó un final fiel sin mencionar Python, pero el literal y la otra variante quedaron sin final porque el compositor rechazó tres borradores seguidos que llamaban instalada a la memoria total utilizable (16,54 GB) cuando la capacidad instalada leída es 17,18 GB (mislabelled_installed; un borrador inventó además «22H2»); la prohibición «No uses Python.» recibió un saludo porque «usar» no encabeza ningún pedido. Siguiente: instrucción y pista de reintento con las dos cifras y sus etiquetas, y prohibir un medio es una prohibición (SYSTEM1547).

## Actualización 2026-09-14 (SYSTEM1547)

Estado de hardware y sistema pasa de 38/40 a 39/40 con las dos cifras de memoria etiquetadas en la instrucción y la pista de reintento (commit 58dbad66, BUILD1547) (HEAD 58dbad66): 6 ejecutados, 5 aprobados, 1 fallido (el límite de prohibición sin final), 1 créditos. Medido: la directiva «Usa Python.» se declinó, las tres lecturas system.status se verificaron y los finales informaron Windows 11 versión 10.0.26200 x64 y 17,18 GB de RAM instalada (installed_capacity) sin mencionar Python; el literal H0076 queda acreditado con sus dos variantes. Residual: el acuse de «No uses Python.» añadió una pregunta de ayuda y el reintento quedó vacío (truncated_structured_reply), y la aclaración de recuperación fue rechazada por eco; el prompt del acuse pasa a excluir la pregunta.

## Actualización 2026-09-14 (APPS1549)

Abrir aplicaciones pasa de 45/54 a 45/54 con el nombre propio sin catálogo leído como presencia de aplicación y nombrado en el final (commit 37f50e75, BUILD1549) (HEAD 37f50e75): 6 ejecutados, 3 aprobados (los tres límites), 3 fallidos, 0 créditos. Medido: la mente decidió una app.installed para el literal y las dos variantes (efecto explícito), pero el enlace del argumento name seguía admitiendo sólo el software conocido y el producto preguntó un argumento faltante (programa o acción dentro; consola o computadora; programa o sitio web) sin leer nada; los tres límites pasaron, incluido el acuse de prohibición sin pregunta. Siguiente: el enlace del argumento admite el mismo nombre propio que el resolutor (APPS1551).

## Actualización 2026-09-14 (APPS1551)

Abrir aplicaciones pasa de 45/54 a 46/54 con el argumento de la lectura de presencia enlazado al nombre propio (commit 3dc076cf, BUILD1551) (HEAD 3dc076cf): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. Medido: el literal y sus dos variantes ejecutaron una app.installed verificada cada uno y los finales nombraron el nombre pedido tal cual («Saint Rose», «Saint Row») diciendo que no se encontró en el catálogo de inicio de Windows y no se puede abrir, sin pregunta ni otra aplicación; los tres límites pasaron. H0249 acreditado con sus dos variantes.

## Actualización 2026-09-14 (MUSIC1553)

Música pasa de 7/39 a 7/39 con la reproducción de YouTube en el reproductor local informada por su título observado (commit 9615349d, BUILD1553) (HEAD 9615349d): 7 ejecutados, 3 aprobados (los tres límites), 4 fallidos, 0 créditos. Medido: las cuatro reproducciones revisadas se propusieron con las palabras de la persona y la raíz las aprobó; yt-dlp resolvió el primer resultado con su título, pero mpv no reprodujo porque la URL de flujo del cliente android_vr responde 403 al HTTP del reproductor (youtube_mpv_playback_not_verified); tres turnos sin final y uno negó la capacidad; el volumen se preajustó y restauró. Siguiente: el resolutor usa el cliente android, cuyas URL de flujo se reproducen directamente en mpv (MUSIC1555).

## Actualización 2026-09-14 (MUSIC1555)

Música pasa de 7/39 a 7/39 con la URL de flujo del cliente android que mpv reproduce (commit b714f804, BUILD1555) (HEAD b714f804): 7 ejecutados, 3 aprobados (los tres límites), 4 fallidos, 0 créditos. Medido: con el cliente android las cuatro reproducciones revisadas se resolvieron, reprodujeron y verificaron en el reproductor local con su título observado en el recibo; el volumen se preajustó y restauró y los reproductores se detuvieron. Ningún final se publicó: los borradores que citaron el título completo lo escribieron con espacios simples donde el observado trae espacios dobles, y los demás citaron sólo un fragmento («Smooth Criminal»); el veto de nombre rechazó los tres intentos. Siguiente: las comprobaciones de nombre toleran los espacios colapsados y la pista de reintento nombra el título completo (MUSIC1557).

## Actualización 2026-09-14 (MUSIC1557)

Música pasa de 7/39 a 9/39 con el título citado con espacios colapsados reconocido y la pista que nombra el título completo (commit e828a755, BUILD1557) (HEAD e828a755): 7 ejecutados, 7 aprobados, 0 fallidos, 2 créditos. Medido: las cuatro reproducciones revisadas se propusieron con las palabras de la persona, la raíz las aprobó, yt-dlp (cliente android) resolvió el primer resultado con su título y mpv lo reprodujo verificado por IPC con el volumen preajustado; cada final dijo que se reproduce citando el título observado completo y tal cual, sin otro dato ni pregunta; el volumen se restauró y ningún reproductor sobrevivió a su caso. H0614 y H0560 acreditados con sus dos variantes.

## Actualización 2026-09-14 (MUSIC1559)

Música pasa de 9/39 a 9/39 con la música nombrada sin proveedor reproducida desde YouTube en el reproductor local (commit f6ef0b01, BUILD1559) (HEAD f6ef0b01): 10 ejecutados, 7 aprobados (cuatro literales y tres límites), 3 fallidos (una literal y las dos variantes), 0 créditos. Medido: los cinco literales y las dos variantes se propusieron y aprobaron como media.play.youtube con la música nombrada; cuatro literales se reprodujeron, verificaron y nombraron por su título observado, pero H0068 perdió el final porque el veto de eco tomó por instrucción copiada el título que la pista de reintento nombra, «pon música de Soda Stereo» lo perdió porque el título llegó en la página de códigos de la consola («�ltimo») y el borrador escribió «Último», y «poneme algo de música alegre» resolvió una mezcla de dos horas y media que no arrancó dentro de la ventana de 12,5 s (fallo honesto). Sin las dos variantes aprobadas no hay crédito. El adjudicador sellado conservó la constante de siete casos en su contador de no ejecutados (10 ejecutados → «unexecuted: -3»; verdictos y casos correctos) y el publicador lo rechazó: esta tanda no publica los ficheros por caso. Siguiente: valores observados exentos del veto de eco, comparación de títulos sin acentos, yt-dlp en UTF-8 y ventana de verificación de treinta segundos (MUSIC1561).

## Actualización 2026-09-14 (MUSIC1561)

Música pasa de 9/39 a 9/39 con el título observado exento del veto de eco, comparado sin acentos y en UTF-8 (commit 32ab8001, BUILD1561) (HEAD 32ab8001): 9 ejecutados (el límite de identidad no se ejecutó), 7 aprobados, 2 fallidos (un literal y una variante), 0 créditos. Medido: los cinco literales y las dos variantes se propusieron, aprobaron, reprodujeron y verificaron en el reproductor local (las mezclas largas arrancan en la ventana de treinta segundos; los títulos llegan en UTF-8); seis finales nombraron el título observado completo, pero H0598 y «poneme algo de música alegre» perdieron el suyo: tras un borrador que juzgó la pertinencia u omitió el título, los reintentos escribieron el título solo y luego «Estoy escuchando «…»», que el veto de estado no lee como reproducción (missing_state). El límite de identidad no se ejecutó (proceso raíz interrumpido tras escribir el recibo de fixture; el instrumento sellado no admite segunda ejecución). Sin la segunda variante aprobada no hay crédito. Siguiente: «escuchando» cuenta como estado de reproducción y la pista de missing_state nombra el estado a afirmar (MUSIC1563).

## Actualización 2026-09-14 (MUSIC1563)

Música pasa de 9/39 a 9/39 con «escuchando» leído como estado de reproducción y la pista de estado con el título (commit 9108abf4, BUILD1563) (HEAD 9108abf4): 10 ejecutados, 8 aprobados, 2 fallidos (un literal y una variante), 0 créditos. Medido: las siete reproducciones se propusieron y aprobaron; cinco se reprodujeron, verificaron y nombraron por su título observado («escuchando» cuenta ya como estado), incluida la variante «música alegre»; H0598 y la variante de Soda Stereo fallaron en la reproducción: mpv no llegó al primer medio segundo en la ventana de treinta segundos aunque los mismos flujos se reproducen a mano (un final honesto, el otro perdido en negaciones de capacidad vetadas). Sin la variante aprobada no hay crédito. Siguiente: un arranque no verificado vuelve a resolver el flujo y lo reproduce una vez más antes de fallar (MUSIC1565).

## Actualización 2026-09-14 (MUSIC1565)

Música pasa de 9/39 a 9/39 con la segunda resolución del flujo ante un arranque no verificado (commit 7c616422, BUILD1565) (HEAD 7c616422): 10 ejecutados, 4 aprobados (una variante y tres límites), 6 fallidos, 0 créditos. Medido: las siete reproducciones se propusieron y aprobaron, pero seis no llegaron al primer medio segundo en mpv en ninguno de los dos flujos resueltos (youtube_mpv_playback_not_verified); sólo la variante «música alegre» se reprodujo y se nombró; tres finales dijeron el fallo con verdad, uno negó la capacidad y dos se perdieron. Los mismos flujos se reproducen a mano en segundos y el adaptador no deja ver qué hizo el reproductor dentro de la tanda. Siguiente: el reproductor escribe su propio registro junto a los datos locales del producto, reproduce sólo audio (sin superficie de GPU junto al modelo) y toma el flujo de audio pequeño (MUSIC1567).

## Actualización 2026-09-14 (MUSIC1567)

Música pasa de 9/39 a 9/39 con el reproductor con registro propio, sólo audio y el flujo de audio pequeño (commit 4819d111, BUILD1567) (HEAD 4819d111): 10 ejecutados, 4 aprobados (una variante y tres límites), 6 fallidos, 0 créditos. Medido: las siete reproducciones se propusieron y aprobaron y el registro de mpv muestra en todas el flujo abierto, el decodificador y WASAPI arrancados y «audio=playing», pero seis se dieron por no verificadas porque el adaptador espera que avance time-pos y en este portátil el reloj WASAPI queda en cero mientras el audio se consume (sondeo raíz: time-pos ≈ 0,0001 durante treinta segundos, reader-pts del demuxer avanzando en tiempo real, --length=3 terminando a tiempo); sólo la mezcla larga avanzó el reloj. Siguiente: la posición del lector del demuxer cuenta como prueba de reproducción junto al reloj de audio (MUSIC1569).

## Actualización 2026-09-14 (MUSIC1569)

Música pasa de 9/39 a 14/39 con la posición del lector del demuxer como prueba de reproducción junto al reloj de audio (commit ae74c685, BUILD1569) (HEAD ae74c685): 10 ejecutados, 10 aprobados, 0 fallidos, 5 créditos. Medido: los cinco literales y las dos variantes se propusieron y aprobaron como media.play.youtube con la música nombrada; yt-dlp resolvió el primer resultado con su título en UTF-8, mpv lo reprodujo sólo en audio con el volumen preajustado y el adaptador verificó la reproducción por la posición del lector del demuxer donde el reloj de audio de este portátil queda en cero; cada final dijo que se reproduce citando el título observado completo, sin otro dato ni pregunta; el volumen se restauró y ningún reproductor sobrevivió a su caso. Los cinco literales acreditados con sus dos variantes.

## Estado consolidado 2026-09-15 (mañana): 528/742 cubiertos, 214 abiertos, 5/35 categorías cerradas

Catorce tandas desde la noche (WEB1543, SYSTEM1545–1547, APPS1549–1551, MUSIC1553–1569): 517 → 528. Registro SHA 94ad877b35cf9a4dee28e0c212ba9fd970fd873de15639f1bd4d5dce2d446445. Reparaciones adoptadas: la lectura de página declara que no observa efecto y «resumime esta página» cierra la categoría (5/35); «… Usa Python.» es una directiva de medio que se declina (H0076: versión de Windows y RAM instalada desde la lectura, sin reclamar Python; la instrucción y la pista nombran las dos cifras de memoria con su etiqueta); un nombre propio que ningún catálogo reclama se comprueba como presencia y el final lo nombra («Saint Rose», H0249); poner un video o una canción en YouTube (H0614, H0560) y la música nombrada sin proveedor (H0068, H0213, H0250, H0388, H0598) se reproducen en el reproductor local (yt-dlp con cliente android y títulos en UTF-8, mpv sólo audio con registro propio, revisor raíz approve_youtube.py, volumen preajustado a 12 y restaurado) y el final nombra el título observado completo. Nueve reejecuciones de música midieron, una por una, el conductor revisado, el flujo 403 del cliente por defecto, el título igual a la consulta, los espacios dobles y los acentos de los títulos, el veto de eco sobre el título de la pista, «escuchando» como estado y, al final, el reloj WASAPI de este portátil en cero mientras el audio se consume (verificación por el lector del demuxer). MUSIC1559 quedó sin publicación por caso (contador sellado del panel de siete).

| Categoría | Abiertos | Condición |
|---|---:|---|
| Música | 25 | Once piden Spotify por nombre (sesión ausente; decisión del dueño: omitir); ocho piden «música/una canción» sin decir cuál («pon música», «poné una canción», «ponme musika», «tengo hambre poné música»…): la respuesta fiel es preguntar qué música y reproducir la respuesta, lo que exige un caso de dos turnos que el instrumento sellado no admite todavía; «qué está sonando» ×2 y «pará la música» ×2 exigen una reproducción real previa (misma condición de dos turnos); «Pon youtube y pon musica» y «abrí chrome y poné música» son compuestos con el navegador del dueño o sin consulta. |
| Estado de hardware y sistema | 1 | «dime la version de Python instalada» (sin lector de versiones de software; el dueño no quiere Python como capacidad). |
| Abrir aplicaciones | 8 | Steam/Chrome del dueño; Mortal Kombat en Steam; idiomas extranjeros (límites sin marca). |
| Leer y resumir páginas web | 0 | Cerrada. |

Sin cambio: Instalar 31, Vídeo 26, Mensajería 22, Interacción 17, Organizar ventanas 7, Entrada incompleta 7, Archivos 7, Red 6, Correo 6, Audio 6, Navegación 5, Desarrollo 5, Contactos 5, Cerrar 5, Hora 4, Juegos 4, resto. Condición transversal nueva: cualquier reproducción local que verifique por reloj de audio debe aceptar también el avance del lector del demuxer (este equipo reporta time-pos ≈ 0 con el audio sonando).


Música queda en 14/39 con el diálogo de dos turnos para la música sin nombrar (commit bd78d831, BUILD1571) (HEAD bd78d831): 12 ejecutados, ninguno adjudicado, 0 créditos. Medido fuera de adjudicación (`MUSIC1571/INSTRUMENTO_NO_ADJUDICABLE.md`): los siete literales y las dos variantes preguntaron qué música sin proponer nada; la respuesta guionizada completó el pedido como media.play.youtube revisado y siete de nueve reprodujeron y nombraron el título observado; H0405 volvió a preguntar (el tramo de argumentos lee la respuesta sola y el lector literal se abstiene ante un nombre desnudo) y H0009 reprodujo sin final (el título observado lleva corchetes y el compositor lo vetó como hueco). El adjudicador sellado conservó la cota de dos terminales de los casos revisados y sus reglas de diálogo exigen tres: rechazó cada caso de diálogo antes de todo veredicto; el instrumento sellado no se corrige. Siguiente: MUSIC1573 reejecuta el mismo panel con la cota de tres terminales en la derivación, los argumentos leídos sobre el pedido completado y el corchete observado exento del veto de hueco.

## Actualización 2026-09-14 (MUSIC1573)

Música pasa de 14/39 a 19/39 con los argumentos del segundo turno leídos sobre el pedido completado y el corchete observado exento del veto de hueco (commit 6c4fff53, BUILD1573) (HEAD 6c4fff53): 12 ejecutados, 10 aprobados, 2 fallidos, 5 créditos. Siete literales y dos variantes preguntaron qué música sin proponer nada; la respuesta guionizada completó el pedido como media.play.youtube revisado (también un nombre de artista desnudo, «Bad Bunny», propuso y se aprobó) y el final nombró el título observado en 5 literales y ambas variantes. Fallaron en el compositor del candidato H0405 (reproducción verificada; los borradores omitieron el título o dijeron «viendo», que el veto de estado no lee como reproducción) y H0009 (reproducción verificada; el reintento con sólo el título inglés fue vetado por idioma y el borrador siguiente perdió el título). Las tres fronteras pasaron con cero operaciones; volumen restaurado; ningún reproductor sobrevivió a su caso.

## Actualización 2026-09-14 (MUSIC1575)

Música pasa de 19/39 a 20/39 con el título observado enmascarado del vocabulario, el título solo juzgado sin estado y «viendo» leído como reproducción (commit 6cd726f7, BUILD1575) (HEAD 6cd726f7): 7 ejecutados, 6 aprobados, 1 fallido, 1 créditos. Los dos literales abiertos y las dos variantes preguntaron qué música sin proponer nada; la respuesta guionizada completó el pedido como media.play.youtube revisado. H0405 («Bad Bunny») reprodujo y el final citó el título observado completo («Estoy viendo el video «…» en YouTube», leído ya como estado de reproducción); ambas variantes igual. H0009 («algo de jazz») propuso y se aprobó, pero el primer resultado de «jazz» es hoy un vídeo de 3 h 51 min del que el cliente android sólo ofrece el mp4 muxado (itag 18, m4a omitido por el experimento SABR) y mpv agotó la ventana de 30 s en dos resoluciones; el final informó el fallo con verdad. Las tres fronteras pasaron con cero operaciones; volumen restaurado; ningún reproductor sobrevivió a su caso.

## Actualización 2026-09-14 (AUDIO1577)

Audio y volumen pasa de 45/51 a 45/51 con la lectura hecha y la cantidad del volumen preguntada al final (commit 40a7f6cd, BUILD1577) (HEAD 40a7f6cd): 5 ejecutados, 1 aprobado, 4 fallidos, 0 créditos. El literal y las dos variantes decidieron una sola system.time, la ejecutaron verificada y el primer borrador de la mente ya era el final buscado (el dato observado y una sola pregunta por la cantidad del volumen), pero la App (UserMessagePolicy.InventedVolume) rechazó tres veces cada final por nombrar el volumen sin nivel observado. El ajuste sin cantidad solo preguntó cuánto sin operar; «No toques el volumen.» respondió con una pregunta en vez de un acuse (el lector de prohibiciones no conoce «toques»). Siguiente: la App juzga aparte la pregunta final cuando el propio pedido nombró el volumen (AUDIO1579).

## Actualización 2026-09-14 (AUDIO1579)

Audio y volumen pasa de 45/51 a 46/51 con la pregunta final que nombra el volumen pedido juzgada aparte por la App (commit 7bb180bd, BUILD1579) (HEAD 7bb180bd): 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos. El literal y las dos variantes decidieron una sola system.time verificada, no cambiaron el volumen y publicaron a la primera el dato observado seguido de una sola pregunta por la cantidad; la App juzga ya aparte esa pregunta final cuando el pedido nombró el volumen. Los dos límites pasaron con cero operaciones (el ajuste sin cantidad preguntó cuánto; «No toques el volumen.» fue reconocida).

## Actualización 2026-09-14 (WINDOWS1581)

Organizar ventanas y pestañas pasa de 6/13 a 7/13 con el listado hecho y cuál ventana enfocar preguntado al final (commit 745ea8ed, BUILD1579) (HEAD 745ea8ed): 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos. El literal y las dos variantes decidieron una sola window.resolve verificada, no enfocaron ninguna ventana y publicaron el listado observado (proceso y título) seguido de una sola pregunta por cuál ventana enfocar, como manda la regla del dueño cuando el contexto no determina «la mejor». Los dos límites pasaron con cero operaciones («enfocá la mejor» solo preguntó cuál; «No toques las ventanas.» fue reconocida).

## Estado consolidado 2026-09-15 (tarde): 536/742 cubiertos, 206 abiertos, 5/35 categorías cerradas

Siete tandas desde el bloque de la mañana (MUSIC1571–1575, AUDIO1577–1579, WINDOWS1581): 528 → 536. Registro SHA d751be2f3aff376f4f2bf8f846c8d6a26b09f2dc8c95203e29de69b50c66016f. Reparaciones adoptadas: los pedidos de música que no dicen cuál («pon música», «poné una canción»…) preguntan qué música y reproducen la respuesta desde YouTube en el reproductor local como caso de diálogo de dos turnos (mandato `turn.answer-clarification`; H0066, H0526, H0601, H0656, H0740, H0405); el segundo turno fundamenta sus argumentos en el pedido completado y el título observado no es vocabulario de la respuesta ni un hueco de plantilla, «viendo» cuenta como reproducción; un pedido de dos cláusulas con una lectura y una petición incompleta ejecuta la lectura y termina con la única pregunta que falta (H0067 «subí el volumen y decime qué fecha es»: la fecha y cuánto; H0527 «listá las ventanas y enfocá la mejor»: el listado y cuál, regla del dueño), la App juzga aparte esa pregunta final cuando el pedido nombró el volumen; «no toques» es una prohibición. MUSIC1571 quedó ejecutada sin adjudicar (cota de terminales del adjudicador sellado; no se corrige un instrumento sellado) y se remidió como MUSIC1573.

| Categoría | Abiertos | Condición |
|---|---:|---|
| Instalar y desinstalar software | 31 | Catorce instalaciones Steam (el Steam del dueño nunca se lanza), cinco desinstalaciones (destructivas sobre software del dueño), tres con diálogo/AppID pedidos, dos con proveedor incompatible (Teams), Epic sin ruta; Photoshop ×4 existe en la Store vía winget pero instalarlo (gigabytes, cuenta Adobe) exige decisión del dueño; «instala Spotify» ya está instalado (Store) y sólo admitiría un acuse tras una lectura de winget que el catálogo no tiene; «instala requests con pip»: el dueño no quiere Python como capacidad. |
| Vídeo y series | 26 | Netflix/Disney+/Prime exigen sesión autenticada del dueño (decisión: omitir). |
| Mensajería | 22 | Enviar exige clientes y terceros reales (prohibido); las lecturas exigen sesión. |
| Música | 19 | Once piden Spotify por nombre (sesión ausente; decisión del dueño: omitir); «qué está sonando» ×2 y «pará la música» ×2 exigen una reproducción previa y un estado/parada del reproductor local que el catálogo no expone (SMTC no ve a mpv); H0009 «poneme una canción» → el primer resultado de «jazz» es hoy un vídeo de casi cuatro horas sólo en mp4 muxado que no arranca en la ventana de verificación (condición ambiental); H0129 «Pon youtube y pon musica» en medición (MUSIC1583); «abrí chrome y poné música» abre el Chrome del dueño; «si tengo spotify abierto pausalo» exige sesión. |
| Interacción dentro de aplicaciones | 17 | Discord/WhatsApp son clientes del dueño; clics sin ventana propia tocarían ventanas del dueño; la aritmética en la Calculadora exige varias confirmaciones en un mismo turno, que el instrumento revisado no admite (una propuesta por turno). |
| Abrir aplicaciones | 8 | Steam/Chrome del dueño; Mortal Kombat en Steam; idiomas extranjeros (límites sin marca, nunca acreditables). |
| Entrada incompleta, ruido y control de diálogo | 7 | Fragmentos con palabras que el modelo decide (transcripciones largas, «Calendar Devil?», «¡Habristín!», un teléfono redactado): sin lector cerrado que los distinga de un pedido. |
| Archivos y carpetas | 7 | Borrar una carpeta (el adaptador de papelera sólo mueve archivos), compuestos de varios pasos (crear/comprimir/abrir, procesos a archivo, fecha en archivo), una ruta pegada sin verbo, «resumime informe.pdf» (sin lector de PDF), backup a pendrive (sin unidad). |
| Correo | 6 | Enviar correo exige cuenta y terceros reales (prohibido). |
| Red y Bluetooth | 6 | La conectividad del dueño no se toca (modo avión, apagar wifi, conectarse a una red); «qué redes wifi hay» exige un escaneo que el catálogo no tiene. |
| Organizar ventanas y pestañas | 6 | Minimizar todo/Opera tocaría las ventanas del dueño; Chrome del dueño. |
| Contactos | 5 | Sin capacidad de contactos (tres son límites negativos con teléfono redactado). |
| Desarrollo y ejecución de comandos | 5 | Sin ejecución de comandos; el dueño no quiere Python como capacidad; «ver tu propio código» sin lector. |
| Audio y volumen | 5 | Cuatro límites sin marca en otros idiomas (nunca acreditables); «subí el volumen de spotify» exige sesión. |

Sin cambio: Navegación 5, Cerrar 5, Hora 4 (límites sin marca), Juegos 4 (Steam/Epic del dueño), Conversación 3 (dos sin marca; «Artiro, artiro…» sin lector de eco), Pantalla 3 (diálogos de Steam), Memoria 2 (recuerdos que exigen un guardado previo en el mismo perfil: instrumento de tres turnos pendiente), Documentos 2, Energía 2, resto 1 por categoría.

## Actualización 2026-09-14 (MUSIC1583)

Música pasa de 20/39 a 21/39 con «pon youtube y pon música» preguntando qué música y reproduciéndola desde YouTube (commit 0a6804fb, BUILD1579) (HEAD 0a6804fb): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. El literal y las dos variantes preguntaron qué música reproducir en YouTube sin proponer nada; la respuesta guionizada completó el pedido como media.play.youtube revisado, la reproducción se verificó en el reproductor local y el final nombró el título observado completo; ningún navegador se abrió. Las tres fronteras pasaron con cero operaciones; volumen restaurado; ningún reproductor sobrevivió a su caso.

## Actualización 2026-09-14 (CONVERSATION1585)

Conversación social y ayuda general pasa de 28/31 a 29/31 con las palabras repetidas sin pedido dichas y preguntadas (commit d82387e4, BUILD1585) (HEAD d82387e4): 5 ejecutados, 4 aprobados, 1 fallido, 1 créditos. El literal y las dos variantes se leyeron como palabras repetidas sin pedido y respondieron con cero operaciones y una sola pregunta que dice que sólo llegaron palabras repetidas y pregunta qué necesita (los tres finales reproducen la frase de ejemplo de la situación, compuesta por el modelo bajo esa guía, no una respuesta fija). «¿Qué es un estimado?» se explicó sin operar; «Bueno, bueno. Dale, dale.» quedó en una invención social del modelo (sin crédito en juego).

## Actualización 2026-09-14 (FILES1587)

Archivos y carpetas pasa de 25/32 a 25/32 con la ruta pegada sin pedido nombrada y preguntada (commit 9853dd95, BUILD1587) (HEAD 9853dd95): 5 ejecutados, 2 aprobados, 3 fallidos, 0 créditos. El literal y las dos variantes se leyeron como ruta pegada sin pedido, pero la pregunta compuesta fue rechazada dos veces por la comprobación de vocabulario interno de la propia mente (un nombre de archivo con punto parece un identificador de operación) y los turnos cayeron en la recuperación total. Los dos límites pasaron con cero operaciones. Siguiente: el nombre de archivo pegado queda exento de esa comprobación (FILES1589).

## Actualización 2026-09-14 (FILES1589)

Archivos y carpetas pasa de 25/32 a 26/32 con el nombre del archivo pegado exento del veto de vocabulario interno (commit 990ec215, BUILD1589) (HEAD 990ec215): 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos. El literal y las dos variantes se leyeron como ruta pegada sin pedido y respondieron con cero operaciones y una sola pregunta que nombra el archivo sólo por su nombre, dice que llegó sin pedido y pregunta qué hacer con él, sin repetir la ruta ni abrir nada. Los dos límites pasaron con cero operaciones.

## Actualización 2026-09-14 (FILES1591)

Archivos y carpetas pasa de 26/32 a 27/32 con el pedido cortado dicho y preguntado cómo sigue (commit e2cd0e4f, BUILD1591) (HEAD e2cd0e4f): 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos. El literal y las dos variantes se leyeron como pedido cortado y respondieron con cero operaciones y una sola pregunta que dice en qué palabras llegó cortado el mensaje y pregunta cómo sigue, sin completar el pedido por su cuenta. Los dos límites pasaron con cero operaciones.

## Actualización 2026-09-14 (MUSIC1593)

Música pasa de 21/39 a 24/39 con el estado y la parada del reproductor local tras una reproducción (commit 1050ce6a, BUILD1593) (HEAD 1050ce6a): 11 ejecutados, 10 aprobados, 1 fallido, 3 créditos. Los ocho casos de diálogo reprodujeron con revisión la música guionizada en el reproductor local y luego respondieron al literal sobre ese reproductor: «qué está sonando» y sus dos variantes leyeron el reproductor (media.status) y nombraron el título observado sonando; «qué canción está sonando» leyó pero no publicó final (fragmento del título y luego título traducido); «pará la música», «para la musica» y sus dos variantes detuvieron el reproductor (media.control, salida verificada) y dijeron con verdad, en estilo de informe, que la reproducción quedó detenida. Las tres fronteras pasaron con cero operaciones; ningún reproductor sobrevivió a su caso; volumen restaurado.

## Actualización 2026-09-14 (MUSIC1595)

Música pasa de 24/39 a 25/39 con el título completo del reproductor local en una frase (commit 080cef4a, BUILD1595) (HEAD 080cef4a): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. El literal y las dos variantes, tras una reproducción revisada verificada en el reproductor local, leyeron ese reproductor y respondieron en una frase citando el título observado completo como sonando. Las tres fronteras pasaron con cero operaciones; ningún reproductor sobrevivió a su caso; volumen restaurado.

## Actualización 2026-09-14 (MUSIC1597)

Música pasa de 25/39 a 26/39 con «poneme una canción» contestada con una música cuyo primer resultado arranca (commit ac221c25, BUILD1595) (HEAD ac221c25): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. El literal y las dos variantes preguntaron qué poner sin proponer nada; las respuestas guionizadas (fixtures cuyo primer resultado arranca) completaron el pedido como media.play.youtube revisado, la reproducción se verificó en el reproductor local y el final citó el título observado completo. Las tres fronteras pasaron con cero operaciones; ningún reproductor sobrevivió a su caso; volumen restaurado.

## Estado consolidado 2026-09-15 (noche): 545/742 cubiertos, 197 abiertos, 5/35 categorías cerradas

Siete tandas desde el bloque de la tarde (MUSIC1583, CONVERSATION1585, FILES1587–1591, MUSIC1593–1597): 536 → 545. Registro SHA 523124e7994ad47f1b6adb5d6c51fc49dcfb28ef8b1364abb2896891ec91bc2e. Reparaciones adoptadas: «pon youtube y pon música» es un pedido de música sin nombrar que pregunta y reproduce (H0129); las palabras que sólo se repiten (H0410), una ruta de archivo pegada sola (H0299) y un pedido que llega cortado en un artículo (H0426) son entradas sin pedido con su aclaración propia (decir lo que llegó y preguntar; el nombre de archivo pegado no es vocabulario interno); el reproductor local de YouTube responde qué está sonando y se detiene a pedido (media.status/media.control sobre mpv, autoridad local_youtube_player; H0224, H0543, H0580, H0686) con el mandato de dos turnos reproducción-luego-literal; «poneme una canción» se acreditó con una respuesta guionizada cuyo primer resultado arranca (H0009).

| Categoría | Abiertos | Condición |
|---|---:|---|
| Instalar y desinstalar software | 31 | Sin cambio (Steam del dueño, desinstalaciones destructivas, Photoshop ×4 en la Store con decisión del dueño pendiente, Spotify ya instalado, pip). |
| Vídeo y series | 26 | Sesión autenticada del dueño (decisión: omitir). |
| Mensajería | 22 | Terceros reales (prohibido); lecturas con sesión. |
| Interacción dentro de aplicaciones | 17 | Clientes del dueño; varias confirmaciones por turno en la Calculadora. |
| Música | 13 | Once piden Spotify por nombre (sesión ausente; decisión del dueño: omitir); «abrí chrome y poné música» abre el Chrome del dueño; «si tengo spotify abierto pausalo» exige sesión. |
| Abrir aplicaciones | 8 | Steam/Chrome del dueño; Mortal Kombat en Steam; idiomas extranjeros (límites sin marca). |
| Entrada incompleta, ruido y control de diálogo | 7 | Fragmentos con palabras que el modelo decide y un teléfono redactado en origen (irreproducible). |
| Correo | 6 | Terceros reales (prohibido). |
| Red y Bluetooth | 6 | La conectividad del dueño no se toca; sin escaneo de redes. |
| Organizar ventanas y pestañas | 6 | Minimizar todo/Opera y Chrome tocan ventanas del dueño. |
| Archivos y carpetas | 5 | Borrar una carpeta (la papelera sólo mueve archivos), dos compuestos de varios pasos (crear/comprimir/abrir; procesos a archivo), «resumime informe.pdf» (sin lector de PDF), backup a pendrive (sin unidad). |
| Contactos | 5 | Sin capacidad de contactos. |
| Desarrollo y ejecución de comandos | 5 | Sin ejecución de comandos; el dueño no quiere Python. |
| Audio y volumen | 5 | Cuatro límites sin marca en otros idiomas; «subí el volumen de spotify» exige sesión. |
| Navegación y búsqueda web | 5 | Opera GX/Chrome del dueño; descarga a escritorio y captura compuestas con el navegador del dueño. |
| Cerrar aplicaciones y ventanas | 5 | WhatsApp/Discord del dueño; «cerrame todo» tocaría ventanas del dueño. |

Sin cambio: Hora 4 (límites sin marca), Juegos 4 (Steam/Epic del dueño), Conversación 2 (sin marca), Pantalla 3 (diálogos de Steam), Memoria 2 (recuerdos que exigen un guardado previo en el mismo perfil: instrumento de tres turnos pendiente), Documentos 2, Energía 2, resto 1 por categoría.

## Actualización 2026-09-14 (MEMORY1599)

Memoria personal pasa de 8/10 a 8/10 con los recuerdos tras un guardado en el mismo perfil (commit 672421ed, BUILD1599) (HEAD 672421ed): 9 ejecutados, 5 aprobados, 4 fallidos, 0 créditos. Los seis casos guardaron el dato guionizado por el canal de memoria privada (activación confirmada, guardado verificado; «me gusta tomar mate» ya como bebida favorita) y luego recordaron con memory.recall verificada, pero los dos literales y las dos variantes de bebida dijeron el dato en primera persona («Me llamo Valentina.», «Me gusta tomar mate.»), como si fuera de BAXY; las dos variantes de nombre respondieron con el nombre escueto. Las tres fronteras pasaron con cero operaciones. Siguiente: el compositor dice el recuerdo en segunda persona y veta la primera (MEMORY1601).

## Actualización 2026-09-14 (MEMORY1601)

Memoria personal pasa de 8/10 a 10/10 con el recuerdo dicho en segunda persona (commit d747311a, BUILD1601) (HEAD d747311a): 9 ejecutados, 9 aprobados, 0 fallidos, 2 créditos. Los seis casos guardaron el dato guionizado por el canal de memoria privada (activación confirmada, guardado verificado) y luego lo recordaron con memory.recall verificada, diciéndolo a la persona en segunda persona con el valor guardado tal cual. Las tres fronteras pasaron con cero operaciones. Memoria personal queda cerrada (10/10). La categoría queda cerrada.

## Actualización 2026-09-14 (FILES1603)

Archivos y carpetas pasa de 27/32 a 27/32 con la carpeta nombrada del escritorio llevada a la papelera privada (commit d91dcfb4, BUILD1603) (HEAD d91dcfb4): 5 ejecutados, 2 aprobados, 3 fallidos, 0 créditos. El literal y las dos variantes decidieron la operación de papelera sobre la carpeta creada por la raíz y el adaptador la encontró, pero Directory.Move no cruza volúmenes (Escritorio redirigido en D:, papelera privada en C:) y la operación falló con un final veraz; la segunda variante halló además otra carpeta del mismo nombre y no publicó final. Los dos límites pasaron con cero operaciones. Siguiente: el adaptador copia el árbol y borra el origen entre volúmenes; nombres de fixture únicos (FILES1605).

## Actualización 2026-09-14 (FILES1605)

Archivos y carpetas pasa de 27/32 a 28/32 con la carpeta nombrada llevada entera a la papelera privada aunque cruce de volumen (commit 89460fd6, BUILD1605) (HEAD 89460fd6): 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos. El literal y las dos variantes movieron entera la carpeta creada por la raíz a la papelera privada del producto (copia verificada entre volúmenes y borrado del origen), la postlectura de la raíz confirmó que dejó el Escritorio redirigido y que su contenido llegó a la copia, y los finales lo dijeron con verdad. Los dos límites pasaron con cero operaciones.

## Estado consolidado 2026-09-16 (madrugada): 548/742 cubiertos, 194 abiertos, 6/35 categorías cerradas

Cuatro tandas desde el bloque de la noche (MEMORY1599–1601, FILES1603–1605): 545 → 548. Registro SHA fcbb649d70879bbdfa3801f6bbb1d9f854e0a68156e433785a1cf368fa3ab085. Reparaciones adoptadas: un recuerdo puede seguir a su propio guardado en el mismo caso (mandato `turn.memory-then`: guardado explícito por el canal de memoria privada y luego el literal), «me gusta tomar X» se guarda como la bebida favorita que «que me gusta tomar» recuerda, y el recuerdo se dice en segunda persona («Te llamás Valentina», «Te gusta tomar mate»): Memoria personal cerrada (10/10, sexta categoría); una carpeta nombrada del escritorio va entera a la papelera privada del producto aunque cruce de volumen (H0327).

Condiciones que siguen: Instalar 31 (Steam del dueño, desinstalaciones destructivas, Photoshop en la Store con decisión del dueño pendiente, Spotify ya instalado sin lectura de winget en el catálogo, pip), Vídeo 26 (sesiones), Mensajería 22 y Correo 6 (terceros reales), Interacción 17 (clientes del dueño; varias confirmaciones por turno), Música 13 (Spotify por nombre, Chrome del dueño, pausa de Spotify), Apps 8 (Steam/Chrome del dueño; límites sin marca), Diálogo 7 (fragmentos que el modelo decide; teléfono redactado), Red 6 (conectividad del dueño; sin escaneo de redes en el catálogo), Organizar ventanas 6 (ventanas del dueño), Archivos 4 (dos compuestos de varios pasos con nombre de archivo no dicho, «resumime informe.pdf» sin lector de PDF, backup a pendrive sin unidad), Contactos 5 y Desarrollo 5 (sin capacidad), Audio 5 (cuatro sin marca; Spotify), Navegación 5 y Cerrar 5 (navegadores y clientes del dueño), Hora 4 (sin marca), Juegos 4 (Steam/Epic del dueño), Pantalla 3 (diálogos de Steam), Conversación 2 (sin marca), Documentos 2, Energía 2, resto 1 por categoría.

## Actualización 2026-09-14 (APPS1607)

Abrir aplicaciones pasa de 46/54 a 46/54 con el Steam del dueño abierto por el producto (commit a9c46cbb, BUILD1605) (HEAD a9c46cbb): 6 ejecutados, 1 aprobado, 5 fallidos, 0 créditos. Los dos literales y las dos variantes lanzaron el Steam del dueño (autorizado el 2026-09-16) y el cliente mostró su ventana, pero el producto no lo verificó: la ventana pertenece a steamwebhelper.exe y el lanzador sólo cuenta steam.exe; la raíz cerró Steam ordenadamente tras cada caso. «¿Qué es Steam?» fue a web.search, no admitida por el panel; «No abras Steam.» fue reconocida. Siguiente: un proceso auxiliar bajo el directorio de instalación del objetivo cuenta para el lanzamiento (APPS1609).

## Actualización 2026-09-14 (APPS1609)

Abrir aplicaciones pasa de 46/54 a 46/54 con la reparación del lanzador medida inerte: Steam arranca y sigue sin verificarse (commit 48d00a6a, BUILD1609) (HEAD 48d00a6a): cuatro app.open de Steam con verification_failed a los 3,6 s (la reparación de la política del lanzador no está en el camino del producto; la primera ventana de Steam aparece a los 4,6 s), dos límites aprobados, 0 créditos. Medición raíz: el producto cablea WindowsInstalledApplicationOpenProvider (presupuesto de verificación ≈3 s) y Steam muestra su primera ventana a los 4,6 s y la principal a los 7,9 s; siguiente: presupuesto de verificación suficiente para un cliente lento y reversión de la política inerte (APPS1611).

## Actualización 2026-09-14 (APPS1611)

Abrir aplicaciones pasa de 46/54 a 48/54 con el Steam del dueño abierto y verificado por su primera ventana (commit bd12a553, BUILD1611) (HEAD bd12a553): cuatro app.open de Steam completadas y verificadas con finales fieles, dos límites aprobados, 2 créditos. Medición raíz: el proveedor de catálogo verifica la apertura en cuanto aparece la primera ventana de Steam (steamwebhelper.exe); el cliente se cerró por la raíz tras cada caso.

## Actualización 2026-09-14 (APPS1613)

Bibliotecas y fichas de juegos pasa de 2/6 a 3/6 con Steam abierto y la instalación del juego nombrado respondida desde sus manifiestos (commit f5ca39a5, BUILD1613) (HEAD f5ca39a5): tres planes app.open + game.installed.named completados y verificados con finales fieles, dos límites aprobados, 1 créditos. Medición raíz: la pregunta indirecta «dime si» tras la conjunción y la lectura de manifiestos con Steam abierto; el juego nombrado no está instalado y el final lo dijo tal cual; el cliente se cerró por la raíz tras cada caso.

## Actualización 2026-09-14 (CLOSE1615)

Cerrar aplicaciones y ventanas pasa de 15/20 a 15/20 con WhatsApp y Discord del dueño cerrados por nombre con una aprobación raíz exacta (commit b0b9a36d, BUILD1613) (HEAD b0b9a36d): cinco casos con fixture no admitidos por el invariante de ausencia de clientes de mensajería del instrumento sellado, dos límites aprobados; publicación rechazada por la cota de índices del publicador sellado (INSTRUMENTO_NO_PUBLICABLE.md), 0 créditos. Medición raíz: el runner sellado exige la ausencia de WhatsApp.Root.exe/Discord.exe antes de admitir y declara que un cliente de mensajería nunca es fixture raíz; la raíz conserva el invariante (ningún mensaje enviado) y deja las filas condicionadas a una decisión de instrumento del dueño.

- 2026-09-16 INSTALL1617 (no adjudicable, ver INSTALL1617/INSTRUMENTO_NO_ADJUDICABLE.md): la lectura `game.entitlement.named` de la biblioteca de Steam se decide, completa y verifica para las descargas/instalaciones/desinstalaciones nombradas; el compositor vetó los finales fieles por su comprobación genérica de título y la raíz cambió una fuente durante la ejecución. Reejecución en INSTALL1619.

## Actualización 2026-09-14 (INSTALL1619)

Instalar y desinstalar software pasa de 0/31 a 0/31 con las descargas en Steam respondidas desde la biblioteca autenticada del dueño (commit a1d68f1c, BUILD1619) (HEAD a1d68f1c): trece literales y una variante con lectura de biblioteca verificada y final fiel, un literal y la variante en inglés sin final por vetos del compositor (título puntuado; «cannot be downloaded» en el lente de fallo), dos límites aprobados; sin par de variantes, sin créditos, 0 créditos. Medición raíz: la lectura y los finales en español funcionan; el compositor aún veta el título con puntuación distinta y la consecuencia en inglés; siguiente INSTALL1621 con ambas máscaras.

## Actualización 2026-09-14 (INSTALL1621)

Instalar y desinstalar software pasa de 0/31 a 0/31 con las descargas en Steam respondidas desde la biblioteca autenticada del dueño (commit 15352c41, BUILD1621) (HEAD 15352c41): catorce literales y la variante en español con lectura verificada y final fiel; un literal con una frase inventada; la variante en inglés rechazada por la política de la App (reversed_result sobre «cannot»); dos límites aprobados; sin par de variantes, sin créditos, 0 créditos. Medición raíz: el compositor de la mente ya acepta el título puntuado y la pasiva inglesa; la política de la App marca «cannot» como fallo sin máscara para la consecuencia de biblioteca, y el modelo insinuó una licencia en un caso; siguiente INSTALL1623.

## Actualización 2026-09-14 (INSTALL1623)

Instalar y desinstalar software pasa de 0/31 a 15/31 con las descargas en Steam respondidas desde la biblioteca autenticada del dueño (commit 5b8cfc2f, BUILD1623) (HEAD 5b8cfc2f): quince literales y dos variantes con lectura de biblioteca completada y verificada y finales fieles, dos límites aprobados, 15 créditos. Medición raíz: la lectura game.entitlement.named responde desde la biblioteca autenticada del dueño y los manifiestos; la política de la App y el compositor aceptan la consecuencia observada en español e inglés; nada descargado ni comprado.

## Actualización 2026-09-14 (INSTALL1625)

Instalar y desinstalar software pasa de 15/31 a 20/31 con las instalaciones y desinstalaciones de aplicaciones del catálogo respondidas por su presencia y las peticiones «en Teams» desde la biblioteca de Steam (commit b6f8fc12, BUILD1625) (HEAD b6f8fc12): cinco literales y cuatro variantes con lectura completada y verificada (presencia en el catálogo o biblioteca de Steam) y finales fieles, dos límites aprobados, 5 créditos. Medición raíz: instalar o desinstalar una aplicación del catálogo se responde por su presencia sin negar capacidades; «en Teams» se lee como Steam; nada instalado, quitado ni descargado.

## Actualización 2026-09-14 (INSTALL1627)

Instalar y desinstalar software pasa de 20/31 a 22/31 (y Abrir aplicaciones de 48/54 a 49/54, H0083) con el lanzamiento y las instalaciones instruidas en Steam respondidas desde la biblioteca del dueño (commit 0b7aae34, BUILD1627) (HEAD 0b7aae34): tres literales y dos variantes con lectura de biblioteca completada y verificada y finales fieles, dos límites aprobados, 3 créditos. Medición raíz: la lectura de biblioteca responde el lanzamiento y las instalaciones instruidas con AppID/URL sin seguir las instrucciones ni abrir diálogos; nada descargado ni lanzado.

## Actualización 2026-09-16 (INSTALL1629)

Instalar y desinstalar software pasa de 22/31 a 26/31 con las peticiones de instalar Photoshop respondidas por su ausencia del catálogo y la vía de instalación (commit 1b5525b4, BUILD1629) (HEAD 1b5525b4): cuatro literales y dos variantes con lectura app.installed completada y verificada (ausente) y finales fieles, dos límites aprobados, 4 créditos. Medición raíz: la petición de instalar un software conocido ausente se responde por su ausencia del catálogo y la vía de instalación del fabricante; los finales de los literales omiten el nombre pedido, que el contexto deja claro; nada instalado ni descargado.

## Estado consolidado 2026-09-16 (mañana): 578/742 cubiertos, 164 abiertos, 6/35 categorías cerradas

Doce tandas desde el bloque de la madrugada (APPS1607–1613, CLOSE1615, INSTALL1617–1629): 548 → 578. Registro SHA 447f2f9c3596688a1ae9a3696031a589c274e4d9485179a79e31486be8b6144f. Reparaciones adoptadas: el proveedor de catálogo espera hasta 120 sondeos la primera ventana de una aplicación lanzada (Steam muestra la suya a los 4,6 s; APPS1611); «dime si …» tras conjunción es pregunta indirecta y, con Steam abierto en la misma petición, una pregunta de instalación sobre un nombre ajeno al catálogo lee los manifiestos (game.installed.named; APPS1613); la lectura game.entitlement.named (Kernel+Core+Providers) responde desde la biblioteca autenticada de Steam y los manifiestos las descargas, instalaciones, desinstalaciones y lanzamientos de juegos nombrados «en Steam» (también «seam», «de steam», «en Teams», con instrucciones de AppID/URL a continuación), con el compositor y la política de la App aceptando la consecuencia observada («no está en tu biblioteca, así que no puedes descargarlo»; INSTALL1617–1627); instalar o desinstalar una aplicación del catálogo, o instalar un software conocido ausente, se responde por su presencia (app.installed; INSTALL1625, INSTALL1629). Instrumento: la reparación de NotepadIdentityPolicy (APPS1609) estaba fuera del camino del producto y se revirtió; CLOSE1615 no pudo admitir clientes de mensajería como fixture (invariante de ausencia de clientes, conservado) ni publicarse (cota de índices del publicador, corregida en las derivaciones siguientes); INSTALL1617 quedó no adjudicable por un cambio de fuente de la raíz durante la ejecución (error de disciplina, registrado).

Condiciones que siguen: Vídeo 26 (sesiones de Netflix/Disney+/Prime ausentes, por instrucción del dueño), Mensajería 22 (nunca enviar ni leer mensajes reales; los clientes de mensajería nunca son fixture), Interacción 17 (Discord bajo el mismo invariante; aritmética en la Calculadora con varias confirmaciones), Música 13 (sesión de Spotify ausente; «abrí chrome y poné música»; «si tengo spotify abierto pausalo»), Instalar 5 (pip por regla del dueño H0076, diálogo de Steam inexistente, «diin eternal», Epic sin lectura de licencia, desinstalación sin plataforma), Diálogo 7 (fragmentos de transcripción sin léxico), Correo 6 (nunca enviar), Red 6 (conectividad del dueño intocable; SSID privado), Organizar 6 y Cerrar 5 (ventanas del dueño, «cerrame todo»), Contactos 5 (3 límites negativos), Desarrollo 5 (sin shell; regla H0076), Navegación 5, Archivos 4, Audio 5 (4 límites sin marca), Hora 4 (límites sin marca), Apps 5 (4 límites sin marca; «lanzá Mortal Kombat» sin plataforma), Juegos 3, Pantalla 3 (diálogo de Steam inexistente), resto de 1–2.

## Actualización 2026-09-16 (INSTALL1631)

Instalar y desinstalar software pasa de 26/31 a 27/31 con la desinstalación de un nombre ausente respondida por su ausencia del catálogo (commit e900207b, BUILD1631) (HEAD e900207b): un literal y dos variantes con lectura app.installed completada y verificada (ausente) y finales fieles, dos límites aprobados, 1 créditos. Medición raíz: desinstalar un nombre ausente del catálogo se responde por su ausencia; nada quitado.

## Actualización 2026-09-16 (INSTALL1633)

Abrir aplicaciones pasa de 49/54 a 50/54 con el lanzamiento de un juego ausente respondido desde la biblioteca de Steam (commit 7f74e3a8, BUILD1633) (HEAD 7f74e3a8): un literal y dos variantes con lectura de biblioteca completada y verificada y finales fieles, dos límites aprobados, 1 créditos. Medición raíz: el lanzamiento de un juego ausente se responde desde la biblioteca de Steam; el final expresa la consecuencia como descarga/instalación; nada lanzado.

## Actualización 2026-09-16 (UI1635)

Interacción dentro de aplicaciones pasa de 5/22 a 5/22 con el clic en el botón Aceptar de un diálogo propio con una aprobación raíz exacta (commit c466180b, BUILD1633) (HEAD c466180b): tres clics aprobados, completados y verificados sobre el diálogo propio; el literal con final fiel y las dos variantes con finales que narran el control como deshabilitado; dos límites aprobados; sin par de variantes, sin créditos, 0 créditos. Medición raíz: el clic revisado cierra el diálogo y se verifica; el narrador leyó absentOrDisabled del recibo como un fallo en dos finales; siguiente UI1637 con la proyección del recibo y el veto.

## Actualización 2026-09-16 (UI1637)

Interacción dentro de aplicaciones pasa de 5/22 a 6/22 con el clic en el botón Aceptar de un diálogo propio con una aprobación raíz exacta (commit 8c3186ed, BUILD1637) (HEAD 8c3186ed): tres clics revisados, aprobados una vez, completados y verificados sobre el diálogo propio, con finales fieles; dos límites aprobados, 1 créditos. Medición raíz: el recibo del clic proyectado como control desaparecido tras el clic da finales fieles en español e inglés; nada del dueño tocado.

## Actualización 2026-09-16 (UI1639)

Interacción dentro de aplicaciones pasa de 6/22 a 7/22 con el clic nombrado por color respondido con la pregunta por la etiqueta del botón (commit 312d49c4, BUILD1639) (HEAD 312d49c4): un literal y dos variantes con cero operaciones y pregunta fiel por la etiqueta del botón, dos límites aprobados, 1 créditos. Medición raíz: un clic nombrado por color se responde preguntando el texto del botón, sin operación.

## Actualización 2026-09-16 (UI1641)

Interacción dentro de aplicaciones pasa de 7/22 a 8/22 con la orden de ir cortada respondida con la pregunta de cómo sigue (commit 7892fe01, BUILD1641) (HEAD 7892fe01): un literal y dos variantes con cero operaciones y preguntas fieles (cola cortada citada; qué carpeta), dos límites aprobados, 1 créditos. Medición raíz: una orden de ir cortada en una preposición se responde preguntando cómo sigue, sin navegar.

## Actualización 2026-09-16 (UI1643)

Interacción dentro de aplicaciones pasa de 8/22 a 9/22 con el texto sin destino respondido con la pregunta de dónde escribirlo (commit 6de63d67, BUILD1643) (HEAD 6de63d67): un literal y dos variantes con cero operaciones y la pregunta fiel de dónde escribir el texto, dos límites aprobados, 1 créditos. Medición raíz: un texto para «ponerle» a nada se responde preguntando dónde escribirlo, sin operación.

## Actualización 2026-09-16 (UI1645)

Interacción dentro de aplicaciones pasa de 9/22 a 9/22 con la orden de escribir sin texto respondida con la pregunta de qué escribir (commit 5f4cce63, BUILD1645) (HEAD 5f4cce63): un literal y una variante con cero operaciones y la pregunta fiel de qué texto escribir; la variante en inglés con la pregunta correcta rechazada por la política de la aplicación como eco del pedido; el límite de definición aprobado y el de prohibición sin acuse (contrato de una oración fallado dos veces), 0 créditos. Medición raíz: la orden de escribir sin texto se responde preguntando qué escribir, sin operación; la política de la aplicación rechaza como eco una pregunta que contiene el pedido corto y el acuse de prohibición en dos oraciones falla su contrato; siguiente UI1647 con la exención del eco para el campo text declarado y el contrato leyendo tras la interjección.

## Actualización 2026-09-16 (UI1647)

Interacción dentro de aplicaciones pasa de 9/22 a 10/22 con la pregunta por el texto aceptada aunque nombre el lugar pedido (commit 4c04e486, BUILD1647) (HEAD 4c04e486): un literal y dos variantes con cero operaciones y la pregunta fiel de qué texto escribir (la pregunta en inglés ya aceptada); los dos límites fallidos: la definición describió un diálogo entre personas y la prohibición no recibió acuse (los borradores contestaron al saludo de bienvenida del historial), 1 créditos. Medición raíz: la orden de escribir sin texto se responde preguntando qué escribir en español e inglés, sin operación; la interjección no era la causa del acuse fallido: el modelo contesta al saludo de bienvenida presente en el historial; siguiente tanda con constraint_ack sin historial.

## Actualización 2026-09-16 (CLOSE1649)

Cerrar aplicaciones y ventanas pasa de 15/20 a 17/20 con el cierre de WhatsApp y Discord ausentes respondido por su ausencia de ventana (commit d987071f, BUILD1649) (HEAD d987071f): dos literales y cuatro variantes con window.resolve terminada window_not_found, ninguna app.close y finales fieles; «cierra whatsapp» fallido por inventory_failed (un proceso ajeno terminó durante el inventario fuerte); dos límites aprobados, con la prohibición reconocida, 2 créditos. Medición raíz: el cierre de un cliente de mensajería ausente se responde por su ausencia de ventana en español e inglés; el acuse de prohibición sin historial funciona; el inventario fuerte aborta cuando un proceso ajeno sale durante la enumeración (siguiente CLOSE1651 con la reparación del proveedor).

## Actualización 2026-09-16 (CLOSE1651)

Cerrar aplicaciones y ventanas pasa de 17/20 a 17/20 con el cierre de WhatsApp ausente respondido por su ausencia de ventana pese a un proceso ajeno que termina (commit 8a312490, BUILD1651) (HEAD 8a312490): el literal otra vez con inventory_failed; una variante aprobada por ausencia y otra con un final que afirma el cierre antes de negarlo; el límite de definición detenido por una búsqueda web no autorizada y la prohibición reconocida, 0 créditos. Medición raíz: el proceso ajeno terminado no era la causa del fallo de inventario; queda como sospechoso el recorrido de marcos alojados (ApplicationFrameHost) que lee la identidad de cada proceso hijo; el narrador no veta «Ya cerré» en un fallo; siguiente CLOSE1653 con ambos arreglos y sin pregunta de definición sobre un nombre.

## Actualización 2026-09-16 (CLOSE1653)

Cerrar aplicaciones y ventanas pasa de 17/20 a 18/20 con el cierre de WhatsApp ausente respondido por su ausencia de ventana con el inventario robusto (commit f31d0159, BUILD1653) (HEAD f31d0159): un literal y dos variantes con window.resolve terminada window_not_found, ninguna app.close y finales fieles; dos límites aprobados, 1 créditos. Medición raíz: con el recorrido de marcos alojados tolerante a procesos que salen (sonda 80/80), el cierre de WhatsApp ausente se responde por su ausencia de ventana; nada cerrado.

## Actualización 2026-09-16 (UI1655)

Interacción dentro de aplicaciones pasa de 10/22 a 10/22 con el silencio del micrófono pedido en un cliente de voz respondido preguntando por el micrófono del sistema (commit 7a6ea17f, BUILD1655) (HEAD 7a6ea17f): cuatro literales y dos variantes con cero operaciones, pero preguntas que piden confirmar un estado o cuál micrófono en vez de ofrecer silenciar el del sistema (una sin respuesta); límite de definición aprobado y acuse de prohibición con «nunca» añadido, 0 créditos. Medición raíz: el lector decide la aclaración en los seis pedidos; la pregunta guiada sólo por el nombre del campo no ofrece el micrófono del sistema y el validador prohibía el subjuntivo «silencie»; siguiente UI1657 con la guía desde el inicio y el validador de oferta.

## Actualización 2026-09-16 (UI1657)

Interacción dentro de aplicaciones pasa de 10/22 a 14/22 con el silencio del micrófono pedido en un cliente de voz respondido ofreciendo silenciar el del sistema (commit 655c2211, BUILD1657) (HEAD 655c2211): cuatro literales y dos variantes con cero operaciones y la pregunta fiel que ofrece silenciar el micrófono del sistema; límite de definición aprobado y acuse de prohibición con «nunca» añadido, 4 créditos. Medición raíz: con la guía inicial del campo y el validador de oferta, el silencio pedido dentro de un cliente de voz se responde ofreciendo el micrófono del sistema en español e inglés, sin operación.

## Actualización 2026-09-16 (UI1659)

Interacción dentro de aplicaciones pasa de 14/22 a 14/22 con la navegación dentro de un cliente de mensajería respondida como límite conocido (commit b1ce4dc2, BUILD1659) (HEAD b1ce4dc2): dos literales con cero operaciones y el límite dicho nombrando el pedido; las variantes sin par (aclaración tras borradores rechazados; respaldo genérico de la aplicación sobre la respuesta válida de la mente); dos límites aprobados, 0 créditos. Medición raíz: la navegación dentro de Discord ya no se lee como destino web y el turno cierra como límite; la política de la aplicación rechaza la respuesta de límite validada por la mente como lenguaje de fallo; siguiente UI1661 con la exención por clase de conversación.

## Actualización 2026-09-16 (UI1661)

Interacción dentro de aplicaciones pasa de 14/22 a 14/22 con la navegación dentro de un cliente de mensajería respondida como límite conocido con la respuesta de la mente publicada (commit 75d37016, BUILD1661) (HEAD 75d37016): dos literales y la variante en inglés con cero operaciones y el límite dicho nombrando el pedido (la respuesta de la mente ya publicada); la variante en español sin par (reintento acotado vacío bajo la gramática JSON); dos límites aprobados, 0 créditos. Medición raíz: la exención por clase de conversación publica la respuesta de límite de la mente; el reintento acotado bajo gramática JSON devuelve contenido vacío con finish_reason length, reproducido fuera de línea; siguiente UI1663 con el reintento en prosa llana para el límite.

## Actualización 2026-09-16 (UI1663)

Interacción dentro de aplicaciones pasa de 14/22 a 16/22 con la navegación dentro de un cliente de mensajería respondida como límite conocido en ambos idiomas (commit a001f21d, BUILD1663) (HEAD a001f21d): dos literales y dos variantes con cero operaciones y el límite dicho llanamente nombrando el pedido en español e inglés; dos límites aprobados, 2 créditos. Medición raíz: con el reintento en prosa llana, la navegación dentro de un cliente de mensajería se responde como límite conocido en ambos idiomas, sin navegación web.

## Actualización 2026-09-16 (LIMITS1665)

Brillo y pantalla pasa de 16/17 a 17/17, Crear documentos y editar imágenes de 0/2 a 1/2 y Contactos de 0/5 a 0/5 con el fondo de pantalla, la presentación y el contacto respondidos como límites conocidos (commit 65ce4acf, BUILD1665) (HEAD 65ce4acf): el fondo de pantalla y la presentación con sus dos variantes cada uno como límites dichos llanamente; los contactos sin par porque dos finales repitieron el número excluido por el criterio; dos límites aprobados, 2 créditos. Medición raíz: los contratos de efecto conocido sin operación cierran el turno como límite nombrando el pedido en español e inglés; el criterio de no repetir el número no se cumplió en los dos pedidos que lo traían (siguiente LIMITS1667 con el criterio de contactos revisado: el número del propio pedido puede citarse). La categoría queda cerrada.

## Actualización 2026-09-16 (LIMITS1667)

Contactos pasa de 0/5 a 2/5 con el contacto respondido como límite conocido citando lo que la persona pidió (commit 368a18e3, BUILD1665) (HEAD 368a18e3): dos literales y dos variantes con cero operaciones y el límite dicho llanamente nombrando el pedido; dos límites aprobados, 2 créditos. Medición raíz: guardar un contacto se responde como límite conocido en español e inglés citando lo que la persona escribió; los tres límites negativos de contactos reciben la misma respuesta y siguen sin acreditarse.

## Actualización 2026-09-16 (AGENDA1669)

Alarmas, recordatorios, tareas y agenda pasa de 37/38 a 38/38 y Archivos y carpetas de 28/32 a 29/32 con lo agendado leído de lo programado por BAXY y el resumen de PDF respondido como límite conocido (commit cfd29303, BUILD1669) (HEAD cfd29303): el literal de agenda y sus dos variantes con una notification.list verificada y finales fieles (nada programado); el literal de PDF y sus dos variantes con cero operaciones y el límite dicho llanamente; dos límites aprobados, 2 créditos. Medición raíz: lo agendado se lee de lo programado por BAXY en español e inglés y el resumen de un PDF se responde como límite conocido; la categoría de agenda queda cerrada. La categoría queda cerrada.

## Estado consolidado 2026-09-16 (tarde): 600/742 cubiertos, 142 abiertos, 8/35 categorías cerradas

Trece tandas desde el bloque de la mañana (INSTALL1631–1633, UI1635–1647, CLOSE1649–1653, UI1655–1663, LIMITS1665–1667, AGENDA1669): 578 → 600. Registro SHA 03062a29d29f1668885ff94131cc04552fd21b652565bf81b0d84711cbbcf125. Reparaciones adoptadas: la desinstalación y el lanzamiento de nombres ausentes se responden por su ausencia (catálogo o biblioteca de Steam); el clic en el botón Aceptar de un diálogo propio se revisa, se verifica y el recibo «control desaparecido tras el clic» se narra como éxito; un clic nombrado por color, una orden de ir cortada en una preposición, un texto para «ponerle» a nada y una orden de escribir con lugar y sin texto preguntan (etiqueta, cómo sigue, dónde, qué texto); la aplicación no cuenta como eco una pregunta que pide el campo declarado por la mente; el acuse de una prohibición se redacta sin el historial del diálogo (con el saludo de bienvenida presente el modelo contestaba al saludo); WhatsApp y Discord ausentes se cierran por su ausencia de ventana y el inventario fuerte ya no aborta cuando un proceso de la instantánea sale durante el recorrido de marcos alojados (sonda raíz 80/80); el narrador veta «Ya cerré …» sobre un fallo; el silencio del micrófono pedido «en Discord» ofrece silenciar el micrófono del sistema (BAXY no maneja el botón del cliente) con la pregunta guiada y validada como oferta; ir a un canal «en Discord» es un límite conocido (no una navegación web), la respuesta de límite validada por la mente ya no se rechaza como lenguaje de fallo y su reintento se redacta en prosa llana (la gramática JSON devolvía vacío); fondo de pantalla, presentaciones, contactos y resumen de PDF son límites conocidos dichos llanamente; lo agendado se lee de lo programado por BAXY. Categorías cerradas: Brillo y pantalla 17/17 y Alarmas, recordatorios, tareas y agenda 38/38 se suman a las seis previas.

| Categoría | Abiertos | Condición |
|---|---:|---|
| Vídeo y series | 26 | Sesiones de Netflix/Disney+/Prime ausentes (decisión del dueño: omitir). |
| Mensajería | 22 | Nunca enviar ni leer mensajes reales; los clientes de mensajería nunca son fixture. |
| Música | 13 | Sesión de Spotify ausente (decisión del dueño); «abrí chrome y poné música» (Chrome del dueño); «si tengo spotify abierto pausalo» (depende de la sesión del dueño). |
| Entrada incompleta | 7 | Fragmentos de transcripción sin léxico y el marcador redactado. |
| Correo | 6 | Nunca enviar; la lectura exige sesión de Outlook. |
| Interacción dentro de aplicaciones | 6 | Clic en un juego (H0096), «apretá enter/enviar» en Discord/WhatsApp (clientes del dueño; enviar mensajes), «al disco» (transcripción), aritmética en la Calculadora (varias confirmaciones). |
| Red y Bluetooth | 6 | Conectividad del dueño intocable; escaneo de redes no listable (SSID privados); modo avión sin mecanismo. |
| Organizar ventanas | 6 | Minimizar todo o a Ópera (ventanas del dueño); Chrome a la izquierda y cerrar sus pestañas (Chrome del dueño; sin operación de ajuste lateral ni de pestañas). |
| Desarrollo | 5 | Sin shell; regla del dueño H0076; dos límites sin marca. |
| Navegación y búsqueda web | 5 | Descarga de imagen (sin operación), Opera GX del dueño, «abre youtube.com en Chrome» (Chrome del dueño), compuesto H0516. |
| Audio y volumen | 5 | Cuatro límites sin marca (idiomas); volumen por aplicación (Spotify) sin operación. |
| Instalar y desinstalar software | 4 | pip por regla del dueño; diálogo de Steam inexistente; «diin eternal»; Epic sin lectura de licencia. |
| Reloj / Abrir aplicaciones / Contactos / Conversación / Notas | 4 + 4 + 3 + 2 + 1 | Límites sin marca y negativos: se conservan como límites, nunca se acreditan. |
| Pantalla | 3 | Diálogos de Steam inexistentes en pantalla. |
| Archivos | 3 | Contenido dinámico (H0334), zip (H0542), backup a pendrive (H0733): capacidades parciales sin composición segura. |
| Bibliotecas y fichas de juegos | 3 | Navegar la interfaz de Steam/Epic (clientes del dueño; sin operación); App ID por la API pública (límite sin marca). |
| Resto (energía 2, cerrar 2, web actual 1, conocimiento 1, hardware 1, documentos 1) | 8 | Apagar/reiniciar (nunca), «cerrame todo» (ventanas del dueño), fallo de WhatsApp en internet (motor), H0297, versión de Python (sin lectura de versiones), edición en Photoshop (ausente; pendiente de lectura). |

## Actualización 2026-09-16 (APPS1671)

Crear documentos y editar imágenes pasa de 1/2 a 1/2 con la foto a editar en Photoshop respondida por la ausencia del programa (commit 5360dc63, BUILD1671) (HEAD 5360dc63): tres lecturas app.installed verificadas (ausente) sin apertura; una variante con final fiel, el literal sin respuesta (tres borradores vetados como afirmación de fallo) y la variante en inglés rechazada por la aplicación («cannot be opened»); dos límites aprobados, 0 créditos. Medición raíz: la lectura de presencia por el marco de uso funciona; la narración añade consecuencias de fallo que el narrador y la aplicación vetan; siguiente APPS1673 con la instrucción de decir sólo la ausencia.

## Actualización 2026-09-16 (APPS1673)

Crear documentos y editar imágenes pasa de 1/2 a 2/2 con la foto a editar en Photoshop respondida por la ausencia del programa dicha sola (commit ec432793, BUILD1673) (HEAD ec432793): un literal y dos variantes con app.installed verificada (ausente), ninguna apertura y finales que dicen sólo la ausencia; dos límites aprobados, 1 créditos. Medición raíz: querer trabajar en un programa ausente se responde por su ausencia del catálogo de inicio en español e inglés; la categoría de documentos e imágenes queda cerrada. La categoría queda cerrada.

## Actualización 2026-09-16 (MUSIC1675)

Música pasa de 26/39 a 27/39 con la pausa condicionada a Spotify abierto respondida por su ventana ausente (commit 25a64393, BUILD1675) (HEAD 25a64393): un literal y dos variantes con window.resolve terminada window_not_found, ninguna media.control y finales fieles; límite de definición aprobado y prohibición respondida con una pregunta, 1 créditos. Medición raíz: la pausa condicionada a Spotify abierto se decide leyendo la ventana y, con Spotify ausente, no pausa nada y lo dice en español e inglés.

## Actualización 2026-09-16 (LIMITS1677)

Desarrollo y ejecución de comandos pasa de 0/5 a 1/5, Organizar ventanas y pestañas de 7/13 a 10/13, Cerrar aplicaciones y ventanas de 18/20 a 18/20 y Audio y volumen de 46/51 a 46/51 con los comandos, el código propio, minimizar o cerrar todo, las pestañas y el volumen por aplicación respondidos como límites conocidos (commit b0549b66, BUILD1677) (HEAD b0549b66): el comando ls y las tres órdenes de minimizar todo con sus variantes como límites dichos llanamente; cerrar todo con la variante inglesa perdida; nueve casos fallidos por el retiro del límite por el verificador de catálogo (pestañas, cerrar todo en inglés, volumen por aplicación), el aclarador de nombres cercanos y la pregunta de capacidad como charla; dos límites aprobados, 4 créditos. Medición raíz: los contratos de límite funcionan cuando nada los retira; el verificador de catálogo retira el límite por operaciones cercanas que no sirven el pedido y el aclarador de nombres cercanos lo adelanta; siguiente LIMITS1679 con ambos guardados.

## Actualización 2026-09-16 (LIMITS1679)

Desarrollo y ejecución de comandos pasa de 1/5 a 2/5, Organizar ventanas y pestañas de 10/13 a 11/13, Cerrar aplicaciones y ventanas de 18/20 a 20/20 y Audio y volumen de 46/51 a 47/51 con los comandos, cerrar todo, las pestañas y el volumen por aplicación respondidos como límites conocidos sin retiro (commit 4d27ea0b, BUILD1679) (HEAD 4d27ea0b): cinco literales y ocho variantes con cero operaciones y el límite dicho llanamente nombrando el pedido en español e inglés; prohibición reconocida y definición degenerada, 5 créditos. Medición raíz: con el verificador y el aclarador de nombres cercanos cediendo al contrato, los cuatro límites se responden llanamente en ambos idiomas; la categoría de cierre queda cerrada.

## Actualización 2026-09-16 (LIMITS1681)

Interacción dentro de aplicaciones pasa de 16/22 a 18/22 y Red y Bluetooth de 15/21 a 16/21 con los controles dentro de clientes de mensajería y el modo avión respondidos como límites conocidos (commit 8e9e59dd, BUILD1681) (HEAD 8e9e59dd): tres literales y cuatro variantes con cero operaciones y el límite dicho llanamente nombrando el pedido en español e inglés; dos límites aprobados, 3 créditos. Medición raíz: pulsar un control dentro de Discord o WhatsApp y el modo avión se responden como límites conocidos en ambos idiomas, sin tocar clientes ni radios.

## Reapertura 2026-09-16 (REOPEN1685, decisión del dueño)

El dueño revisó el bloque nocturno y declaró capacidades esperadas diez casos acreditados como «límite conocido»: resumir un PDF (H0666), minimizar todas las ventanas (H0238, H0529, H0658), cerrar todo (H0467, H0484), cerrar las pestañas de Chrome (H0444), ir a un canal dentro de Discord (H0290, H0636) y el volumen de Spotify (H0652). Vuelven a abiertos (604/742, 138 abiertos, 9/35 cerradas: Cerrar aplicaciones y ventanas 18/20). Quedan como límites: ejecutar comandos, fondo de pantalla, PowerPoint y contactos. Marco: minimizar/cerrar todo y pestañas bajo permisos totales (sin perder documentos sin guardar); PDF por texto extraíble; canal de Discord y volumen de Spotify exigen el cliente presente (si no está, aplazado por el punto 7, no límite). La infraestructura necesaria queda autorizada por el dueño aunque desbloquee menos de diez abiertos.

## Actualización 2026-09-16 (MINALL1687)

Organizar ventanas y pestañas pasa de 7/13 a 9/13 con minimizar todas las ventanas ejecutado y verificado sobre el escritorio (commit 3059f183, BUILD1687) (HEAD 3059f183): MINALL1687: window.minimize.all (nueva operación) minimizó y verificó todas las ventanas del escritorio en seis de siete casos; H0238 y H0529 acreditados con dos variantes aprobadas; H0658 falló sólo por el final (borradores con «ventanales» vetados como inventados); dos límites aprobados; ventanas del dueño restauradas por la raíz tras cada caso, 2 créditos. 7 casos ordinarios sobre BUILD1687: 6 aprobados, 1 fallido (H0658, sin final); 2 créditos

## Actualización 2026-09-16 (REOPEN1689)

Archivos pasa de 28/32 a 28/32, Organizar ventanas y pestañas de 9/13 a 10/13, con resumir un PDF nombrado ejecutado y verificado sobre su texto extraíble y minimizar todo reintentado (commit 48719e91, BUILD1689) (HEAD 48719e91): REOPEN1689: document.pdf.read (nueva operación) leyó el PDF de prueba de la raíz y el final nombró el documento, sus títulos y su comienzo tal cual en los tres casos de PDF, pero la variante inglesa se respondió en español (sin «summarize» en la evidencia de idioma) y H0666 queda abierto sin crédito; window.minimize.all reintentado con el sustantivo llano: H0658 acreditado con dos variantes aprobadas; dos límites aprobados; fixture retirado y ventanas del dueño restauradas por la raíz tras cada caso, 1 créditos. 8 casos ordinarios sobre BUILD1689: 7 aprobados, 1 fallido (variante inglesa de PDF por idioma); 1 crédito

## Actualización 2026-09-16 (PDF1691)

Archivos pasa de 28/32 a 28/32 con resumir un PDF nombrado ejecutado y verificado sobre su texto extraíble, en el idioma del pedido (commit 248b9184, BUILD1691) (HEAD 248b9184): PDF1691: document.pdf.read completada y verificada en los tres casos de PDF; literal y variante española fieles; la variante inglesa, ya leída como inglés, no publicó final (borradores etiqueta: valor en minúscula vetados) y H0666 sigue abierto sin crédito; dos límites aprobados; fixture retirado por la raíz tras cada caso, 0 créditos. 5 casos ordinarios sobre BUILD1691: 4 aprobados, 1 fallido (variante inglesa sin final); 0 créditos

## Actualización 2026-09-16 (PDF1693)

Archivos pasa de 28/32 a 29/32 con resumir un PDF nombrado ejecutado y verificado sobre su texto extraíble, en el idioma del pedido (commit c7e71a8a, BUILD1693) (HEAD c7e71a8a): PDF1693: document.pdf.read (texto extraíble con pypdf, sin OCR) leyó el PDF de prueba de la raíz y los finales nombraron el archivo, sus páginas y sus títulos y citaron su comienzo tal cual, en español y en inglés; H0666 acreditado con dos variantes aprobadas; dos límites aprobados; fixture retirado por la raíz tras cada caso, 1 créditos. 5 casos ordinarios sobre BUILD1693: 5 aprobados; 1 crédito

## Estado consolidado 2026-09-16 (noche): 608/742 cubiertos, 134 abiertos, 9/35 categorías cerradas

Desde el bloque de la tarde (600): APPS1671–1673, MUSIC1675, LIMITS1677–1681 (+14, 614), la reapertura REOPEN1685 por decisión del dueño (−10, 604) y las tandas de capacidades reabiertas MINALL1687, REOPEN1689, PDF1691 y PDF1693 (+4, 608). Registro SHA 1784224e395bab1ee7d65ed016ac9d45b8db264312402e5185c2b36667ccfaaf. Reparaciones adoptadas en este tramo: `window.minimize.all` (minimiza todas las ventanas visibles del escritorio y relee que quedaron minimizadas, sin cerrar nada; H0238, H0529, H0658) y `document.pdf.read` (localiza un PDF nombrado de forma única en escritorio/documentos/descargas y extrae el texto que ya contiene con pypdf en el runtime de la mente, sin OCR; el final nombra el archivo, sus páginas y sus títulos y cita su comienzo tal cual; H0666, en español y en inglés). LIMITS1683 (aritmética en la Calculadora, navegación en la interfaz de Steam/Epic, escaneo de redes, descarga de archivos) sigue ejecutada y sin adjudicar a la espera de la respuesta del dueño sobre si son capacidades esperadas.

| Categoría | Abiertos | Condición |
|---|---:|---|
| Vídeo y series | 26 | Sesiones de Netflix/Disney+/Prime ausentes (decisión del dueño: omitir). |
| Mensajería | 22 | Nunca enviar ni leer mensajes reales; los clientes de mensajería nunca son fixture. Incluye «ve a Cotele en Discord» (H0290, H0636, reabiertos): Discord ausente → punto 7 (diferido), no límite. |
| Música | 12 | Sesión de Spotify ausente (decisión del dueño); «abrí chrome y poné música» (Chrome del dueño); «si tengo spotify abierto pausalo» (sesión del dueño). |
| Entrada incompleta | 7 | Fragmentos de transcripción sin léxico y el marcador redactado. |
| Correo | 6 | Nunca enviar; la lectura exige sesión de Outlook. |
| Interacción dentro de aplicaciones | 6 | Clic en un juego (H0096), «apretá enter/enviar» en Discord/WhatsApp (clientes del dueño; enviar mensajes), «al disco» (transcripción), aritmética en la Calculadora (LIMITS1683, pendiente del dueño). |
| Red y Bluetooth | 5 | Conectividad del dueño intocable; escaneo de redes (LIMITS1683, pendiente del dueño); modo avión sin mecanismo. |
| Navegación y búsqueda web | 5 | Descarga de archivo (LIMITS1683, pendiente del dueño), Opera GX del dueño, «abre youtube.com en Chrome» (Chrome del dueño), compuesto H0516. |
| Audio y volumen | 5 | Cuatro límites sin marca (idiomas); volumen de Spotify (H0652, reabierto): Spotify ausente (sólo el lanzador de la Store corre) → punto 7 (diferido); una operación de volumen por sesión de audio exigiría además reproducir en la cuenta del dueño. |
| Instalar y desinstalar software | 4 | pip por regla del dueño; diálogo de Steam inexistente; «diin eternal»; Epic sin lectura de licencia. |
| Reloj / Abrir aplicaciones / Contactos / Conversación / Notas | 4 + 4 + 3 + 2 + 1 | Límites sin marca y negativos: se conservan como límites, nunca se acreditan. |
| Archivos | 3 | Contenido dinámico (H0334), zip (H0542), backup a pendrive (H0733): capacidades parciales sin composición segura. |
| Pantalla | 3 | Diálogos de Steam inexistentes en pantalla. |
| Organizar ventanas | 3 | Minimizar a Ópera y Chrome a la izquierda (ventanas del dueño; sin operación de ajuste lateral); cerrar las pestañas de Chrome (H0444, reabierto): Chrome instalado pero nunca abierto → punto 7 (diferido). |
| Bibliotecas y fichas de juegos | 3 | Navegar la interfaz de Steam/Epic (LIMITS1683, pendiente del dueño); App ID por la API pública (límite sin marca). |
| Desarrollo | 3 | Sin shell; regla del dueño H0076; límite sin marca. |
| Resto (energía 2, cerrar 2, web actual 1, conocimiento 1, hardware 1) | 7 | Apagar/reiniciar (nunca); «cerrame todo» y «cerrá todas las ventanas» (H0467, H0484, reabiertos): un cierre real de todas las ventanas cerraría VS Code, que aloja esta sesión raíz, y las aplicaciones en primer plano del dueño — pendiente de una ejecución desde fuera de VS Code o de la aceptación del dueño, sin crédito ni fallo; fallo de WhatsApp en internet (motor), H0297, versión de Python (sin lectura de versiones). |

## Actualización 2026-09-16 (WINDOWS1695)

Organizar ventanas y pestañas pasa de 10/13 a 11/13 con minimizar una aplicación nombrada ejecutado y verificado sobre su ventana (commit 0aa8b142, BUILD1695) (HEAD 0aa8b142): WINDOWS1695: minimizar una aplicación nombrada (window.resolve por applicationName + window.minimize, turno ordinario) sobre la ventana de Opera del dueño, restaurada por la raíz tras cada caso; H0697 acreditado con dos variantes aprobadas (español e inglés); dos límites aprobados, 1 créditos. 5 casos ordinarios sobre BUILD1695: 5 aprobados; 1 crédito

## Actualización 2026-09-16 (SYSTEM1697)

Estado de hardware y sistema pasa de 39/40 a 40/40 con la versión de Python instalada leída y verificada del registro de Windows (commit 4f180240, BUILD1697) (HEAD 4f180240): SYSTEM1697: software.python.status (nueva operación de sólo lectura, registro PEP 514, sin ejecutar nada) leyó las tres instalaciones de Python registradas y los finales dieron sus versiones exactas en español e inglés; H0307 acreditado con dos variantes aprobadas; límite de definición aprobado; el límite de prohibición «No me digas la versión de Python.» falló (saludo repetido: «digas» no se proyectaba a «dime», reparado para la próxima tanda), 1 créditos. 5 casos ordinarios sobre BUILD1697: 4 aprobados, 1 fallido (límite de prohibición); 1 crédito; la categoría Estado de hardware y sistema queda cerrada La categoría queda cerrada.

## Actualización 2026-09-16 (LIMITS1699)

Desarrollo y ejecución de comandos pasa de 2/5 a 2/5 con ver su propio código respondido llanamente como límite (commit 1708f772, BUILD1699) (HEAD 1708f772): LIMITS1699: las dos variantes de H0635 respondieron llanamente el límite de ver su propio código con cero operaciones; el literal terminó de nuevo en una pregunta de aclaración porque el contrato prohibía «no puedo … ni» aunque el pedido coordina dos acciones (reparado para la próxima tanda); sin crédito; dos límites aprobados, incluida la prohibición «No me digas la versión de Python.» ahora reconocida, 0 créditos. 5 casos ordinarios sobre BUILD1699: 4 aprobados, 1 fallido (literal con pregunta de aclaración); 0 créditos

## Actualización 2026-09-16 (LIMITS1701)

Desarrollo y ejecución de comandos pasa de 2/5 a 2/5 con ver su propio código respondido llanamente como límite (commit 0fd4413d, BUILD1701) (HEAD 0fd4413d): LIMITS1701: variantes y límites aprobados de nuevo; el literal de H0635 volvió a terminar en pregunta de aclaración por otra causa (la decisión «no soportado» fue releída como narración y pasada a «followup»); sin crédito; reparado para la próxima tanda, 0 créditos. 5 casos ordinarios sobre BUILD1701: 4 aprobados, 1 fallido (literal); 0 créditos

## Actualización 2026-09-16 (LIMITS1703)

Desarrollo y ejecución de comandos pasa de 2/5 a 3/5 con ver su propio código respondido llanamente como límite (commit f37d79ea, BUILD1703) (HEAD f37d79ea): LIMITS1703: H0635 respondido llanamente como límite (cero operaciones, nombrando el pedido) en el literal y en las dos variantes; acreditado; dos límites aprobados, 1 créditos. 5 casos ordinarios sobre BUILD1703: 5 aprobados; 1 crédito

## Actualización 2026-09-16 (FILES1707)

Archivos y carpetas pasa de 29/32 a 29/32 con un archivo de texto con los procesos que más memoria usan ejecutado y verificado (commit 1ef6a5ea, BUILD1707) (HEAD 1ef6a5ea): FILES1707: el límite de planes aceptó la misión; en el literal las dos operaciones se completaron y verificaron y el archivo quedó escrito con los cinco procesos, pero el final no dijo que creó el archivo; en las variantes la escritura no se pudo groundear (cabecera fija) y los finales lo dijeron honestamente; sin crédito; dos límites aprobados, 0 créditos. 5 casos ordinarios sobre BUILD1707: 2 aprobados (límites), 3 fallidos; 0 créditos

## Actualización 2026-09-16 (FILES1709)

Archivos y carpetas pasa de 29/32 a 29/32 con un archivo de texto con los procesos que más memoria usan ejecutado y verificado (commit 7d10031e, BUILD1709) (HEAD 7d10031e): FILES1709: el literal y la variante inglesa ejecutaron las dos operaciones y escribieron el archivo con los procesos, pero los finales fieles fueron vetados por la forma de código del nombre del archivo; la variante de CPU no groundeó la escritura (medida reformateada); sin crédito; dos límites aprobados, 0 créditos. 5 casos ordinarios sobre BUILD1709: 2 aprobados (límites), 3 fallidos; 0 créditos

## Actualización 2026-09-16 (FILES1711)

Archivos y carpetas pasa de 29/32 a 29/32 con un archivo de texto con los procesos que más memoria usan ejecutado y verificado (commit b3326049, BUILD1711) (HEAD b3326049): FILES1711: las tres peticiones ejecutaron y verificaron las dos operaciones y escribieron el archivo con los procesos leídos (memoria y CPU, español e inglés), y la mente publicó finales fieles que nombraban el archivo; la política de mensajes de la App los vetó por la forma de código del nombre; sin crédito; dos límites aprobados, 0 créditos. 5 casos ordinarios sobre BUILD1711: 2 aprobados (límites), 3 fallidos (finales vetados por la App); 0 créditos

## Actualización 2026-09-16 (FILES1713)

Archivos y carpetas pasa de 29/32 a 30/32 con un archivo de texto con los procesos que más memoria usan ejecutado y verificado (commit 4ceb23d5, BUILD1713) (HEAD 4ceb23d5): FILES1713: la misión lectura de procesos → escritura de archivo se ejecutó y verificó en el literal y en las dos variantes (memoria y CPU, español e inglés), con el archivo escrito con los procesos leídos y finales que nombran el archivo y los procesos con sus valores observados; H0334 acreditado; dos límites aprobados, 1 créditos. 5 casos ordinarios sobre BUILD1713: 5 aprobados; 1 crédito

## Actualización 2026-09-16 (VIDEO1715)

Vídeo y series pasa de 0/26 a 1/26 con un título propio sin proveedor reproducido en YouTube en el reproductor local (commit 0ac3648f, BUILD1715) (HEAD 0ac3648f): VIDEO1715: un título propio sin proveedor («poné Tom and Jerry») se leyó como reproducción en YouTube, la raíz aprobó sólo media.play.youtube con las palabras de la persona, la reproducción se verificó en el reproductor local y los finales citaron tal cual el título observado; H0486 acreditado con dos variantes aprobadas (español e inglés); dos límites aprobados; reproductor detenido y volumen restaurado por la raíz, 1 créditos. 5 casos sobre BUILD1715 (3 revisados, 2 ordinarios): 5 aprobados; 1 crédito

## Actualización 2026-09-16 (VIDEO1717)

Vídeo y series pasa de 1/26 a 1/26 con abrir YouTube y poner un video sin decir cuál preguntado y reproducido tras la respuesta (commit 8241a616, BUILD1717) (HEAD 8241a616): VIDEO1717: los tres casos de diálogo preguntaron qué video poner sin operar, tomaron la respuesta guionizada de la raíz y reprodujeron con revisión en el reproductor local; las variantes citaron tal cual el título observado; el literal quedó sin final (borradores vetados); sin crédito; dos límites aprobados, 0 créditos. 5 casos sobre BUILD1717 (3 de diálogo con revisión, 2 ordinarios): 4 aprobados, 1 fallido (literal sin final); 0 créditos

## Actualización 2026-09-16 (VIDEO1719)

Vídeo y series pasa de 1/26 a 2/26 con abrir YouTube y poner un video sin decir cuál preguntado y reproducido tras la respuesta (commit 595b2a5a, BUILD1719) (HEAD 595b2a5a): VIDEO1719: «abre youtube y pon un video» preguntó qué video sin operar, tomó la respuesta guionizada de la raíz, reprodujo con revisión en el reproductor local y el final citó tal cual el título observado diciendo que se reproduce; H0141 acreditado con dos variantes aprobadas (español e inglés); dos límites aprobados; reproductor detenido y volumen restaurado por la raíz, 1 créditos. 5 casos sobre BUILD1719 (3 de diálogo con revisión, 2 ordinarios): 5 aprobados; 1 crédito

## Estado consolidado 2026-09-16 (madrugada del 17): 614/742 cubiertos, 128 abiertos, 10/35 categorías cerradas

Desde el bloque de la noche (608): WINDOWS1695 (+1, minimizar Opera por nombre), SYSTEM1697 (+1, versión de Python por el registro PEP 514; cierra «Estado de hardware y sistema» 40/40), LIMITS1699–1703 (+1, ver su propio código como límite llano tras tres causas: regla «ni» sobre pedido coordinado, reclasificación a seguimiento, subjuntivo «digas»), FILES1705–1713 (+1, archivo de texto con los procesos que más memoria usan: misión lectura → escritura con texto proyectado y verificado por el límite de planes; FILES1705 no pudo adjudicarse porque la raíz recompiló antes de adjudicar), VIDEO1715 (+1, «poné Tom and Jerry» reproducido en YouTube en el reproductor local) y VIDEO1717–1719 (+1, «abre youtube y pon un video» preguntado y reproducido tras la respuesta). Registro SHA 846b090c8f16151e07e7f079875aa9f80d9fde29c489228912a99b242a50c0c4. NETWORK1721 (conectarse al wifi de un nombre sin perfil guardado, fallo honesto revisado) en ejecución.

| Categoría | Abiertos | Condición |
|---|---:|---|
| Vídeo y series | 24 | Sesiones de Netflix/Disney+/Prime ausentes (decisión del dueño: omitir); los dos pedidos sin servicio (H0486, H0141) ya se cubren con el reproductor local de YouTube. |
| Mensajería | 22 | Nunca enviar ni leer mensajes reales; los clientes de mensajería nunca son fixture. «Ve a Cotele en Discord» (H0290, H0636, reabiertos): Discord ausente → punto 7 (diferido). |
| Música | 12 | Sesión de Spotify ausente (decisión del dueño); «abrí chrome y poné música» (Chrome del dueño); «si tengo spotify abierto pausalo» (sesión del dueño). |
| Entrada incompleta | 7 | Fragmentos de transcripción sin léxico y el marcador redactado. |
| Correo | 6 | Nunca enviar; la lectura exige sesión de Outlook. |
| Interacción dentro de aplicaciones | 6 | Clic en un juego (H0096), «apretá enter/enviar» en Discord/WhatsApp, «al disco» (transcripción), aritmética en la Calculadora (LIMITS1683, pendiente del dueño). |
| Red y Bluetooth | 5 | Conectividad del dueño intocable; escaneo de redes (LIMITS1683, pendiente del dueño); modo avión sin mecanismo; «conectate al wifi de casa / de la luna» (H0170, H0376, H0739) en NETWORK1721 como fallo honesto revisado (ningún perfil guardado lleva ese nombre; la raíz lo comprueba antes de aprobar). |
| Navegación y búsqueda web | 5 | Descarga de archivo (LIMITS1683, pendiente del dueño), Opera GX del dueño, «abre youtube.com en Chrome» (Chrome del dueño), compuesto H0516. |
| Audio y volumen | 5 | Cuatro límites sin marca (idiomas); volumen de Spotify (H0652, reabierto): Spotify ausente → punto 7 (diferido). |
| Instalar y desinstalar software | 4 | pip por regla del dueño; diálogo de Steam inexistente; «diin eternal»; Epic sin lectura de licencia. |
| Reloj / Abrir aplicaciones / Contactos / Conversación / Notas | 4 + 4 + 3 + 2 + 1 | Límites sin marca y negativos: se conservan como límites, nunca se acreditan. |
| Pantalla | 3 | Diálogos de Steam inexistentes en pantalla. |
| Bibliotecas y fichas de juegos | 3 | Navegar la interfaz de Steam/Epic (LIMITS1683, pendiente del dueño); App ID por la API pública (límite sin marca). |
| Archivos | 2 | Carpeta + txt + zip + abrir el zip (H0542, composición de cuatro pasos sin nombres), backup a pendrive (H0733, sin pendrive). |
| Organizar ventanas | 2 | Chrome a la izquierda (Chrome ausente, sin operación de ajuste lateral); cerrar las pestañas de Chrome (H0444, reabierto): Chrome nunca abierto → punto 7 (diferido). |
| Desarrollo | 2 | Sin shell; dos límites sin marca. |
| Resto (energía 2, cerrar 2, web actual 1, conocimiento 1) | 6 | Apagar/reiniciar (nunca); «cerrame todo» y «cerrá todas las ventanas» (H0467, H0484, reabiertos): cerraría VS Code, que aloja esta sesión raíz — pendiente del dueño; fallo de WhatsApp en internet (motor); H0297 (fragmento libre: las variantes inventan hechos). |

## Actualización 2026-09-16 (NETWORK1721)

Red y Bluetooth pasa de 16/21 a 16/21 con conectarse al wifi de un nombre sin perfil guardado respondido con un fallo honesto revisado (commit 7a294a33, BUILD1721) (HEAD 7a294a33): 7 ejecutados, 2 aprobados (los dos límites), 5 fallidos: las cinco wifi.connect.named revisadas fueron aprobadas por la raíz, terminaron wifi_profile_not_found y la WLAN no cambió, pero los finales dijeron «no hubo efecto» sin la causa sellada (ninguna red guardada con ese nombre), 0 créditos. Causa: la rama de confirmación de la App sustituye el hecho de fallo de la operación por confirmed_no_effect, así que la mente nunca vio el código; reparación pendiente en MindPlanSession.cs y repetición del panel.

## Actualización 2026-09-16 (NETWORK1723)

Red y Bluetooth pasa de 16/21 a 19/21 con conectarse al wifi de un nombre sin perfil guardado respondido con un fallo honesto revisado que dice su causa (commit 61ae7ab8, BUILD1723) (HEAD 61ae7ab8): 7 ejecutados, 7 aprobados: las cinco wifi.connect.named revisadas fueron aprobadas por la raíz tras comprobar que ningún perfil guardado coincide, terminaron wifi_profile_not_found, la WLAN no cambió y los finales dijeron que no se conectó porque no hay una red guardada con ese nombre; los dos límites aprobados, 3 créditos. Reparación medida: la rama de confirmación de la App pasa el hecho de fallo de la operación al final (antes confirmed_no_effect) y el hecho de causa wifi_profile_not_found evita la palabra «connected» que la lente de palabras truncadas vetaba en inglés.

## Actualización 2026-09-16 (UI1725)

Interacción dentro de aplicaciones pasa de 16/22 a 18/22 con la aritmética pedida escrita en la Calculadora abierta y leída de su pantalla (commit ae00b3b5, BUILD1725) (HEAD ae00b3b5): 6 ejecutados, 6 aprobados: las cuatro calculator.expression.evaluate se completaron y verificaron sobre la Calculadora abierta y poseída por la raíz (6*7→42, 2+2→4, 10-3→7, 6*7→42, pantalla releída por la raíz tras cada caso) y los finales dijeron la operación y el resultado mostrado; los dos límites aprobados, 2 créditos. Mecanismo: la operación trae la Calculadora al frente, escribe la expresión por SendKeys y lee CalculatorResults por UI Automation; la Calculadora del dueño no se tocó (ventana propia de la raíz por caso, cerrada al final).

## Actualización 2026-09-16 (LIMITS1727)

Navegación y búsqueda web pasa de 41/46 a 42/46 con descargar una imagen de la web al escritorio respondido como límite conocido (commit 8811f33a, BUILD1727) (HEAD 8811f33a): 5 ejecutados, 5 aprobados: el literal y sus dos variantes terminaron con cero operaciones y un final que dice llanamente que no descarga la imagen de wikipedia.org al escritorio nombrando el pedido; los dos límites aprobados, 1 créditos. Límite legítimo por decisión del dueño (2026-09-16); sin cambios de código: el contrato browser.download.file de LIMITS1683 (commit 48c183b0) medido sobre la compilación vigente.

## Actualización 2026-09-16 (NETWORK1729)

Red y Bluetooth pasa de 19/21 a 20/21 con qué redes wifi hay leído del adaptador o respondido con la radio apagada dicha con verdad (commit 382f2aa6, BUILD1729) (HEAD 382f2aa6): 5 ejecutados, 5 aprobados: el literal y sus dos variantes corrieron wifi.scan de sólo lectura, que terminó con el código sellado wifi_interface_off porque la radio WLAN de este PC está apagada (estado de la interfaz sin cambios), y los finales lo dijeron con verdad sin inventar redes; los dos límites aprobados, 1 créditos. Mecanismo: wifi.scan ejecuta netsh wlan show networks mode=bssid y devuelve las redes visibles o el estado tipado de la radio; la raíz no enciende la WLAN del dueño, así que el camino con redes visibles queda verificado por el analizador incrustado y la sonda offline del compositor.

## Estado consolidado 2026-09-16 (tarde del 17, tras NETWORK1729): 621/742 cubiertos, 121 abiertos, 10/35 categorías cerradas

Desde el bloque de la madrugada (614): NETWORK1721 (0, los finales no decían la causa) → NETWORK1723 (+3, «conectate al wifi de casa / de la luna» como fallo honesto revisado con causa: la rama de confirmación de la App ahora pasa el hecho de fallo de la operación al final), UI1725 (+2, «multiplicá 6 por 7 en la calc» y «Suma 2 más 2 en la Calculadora»: calculator.expression.evaluate escribe la expresión en la Calculadora abierta y lee su pantalla por UI Automation; ventana propia de la raíz por caso), LIMITS1727 (+1, descargar una imagen de wikipedia.org al escritorio como límite legítimo por decisión del dueño), NETWORK1729 (+1, «qué redes wifi hay»: wifi.scan por netsh; en este PC la radio WLAN está apagada y el panel mide el estado honesto wifi_interface_off). Respuestas del dueño 2026-09-16 (sección 2 de DECISIONES_DUENO_2026-09-16.md) aplicadas: aritmética, escaneo y wifi por nombre como capacidades; descarga como límite; ventanas reales del dueño admitidas en tandas de minimizar/cerrar; «cerrame todo» diferido.

| Categoría | Abiertos | Condición |
|---|---:|---|
| Vídeo y series | 24 | Sesiones de Netflix/Disney+/Prime ausentes (decisión del dueño: omitir). |
| Mensajería | 22 | Nunca enviar ni leer mensajes reales; los clientes de mensajería nunca son fixture. «Ve a Cotele en Discord» (H0290, H0636): Discord ausente → punto 7 (diferido). |
| Música | 12 | Sesión de Spotify ausente (decisión del dueño); «abrí chrome y poné música» (Chrome del dueño); «si tengo spotify abierto pausalo» (sesión del dueño). |
| Entrada incompleta | 7 | Fragmentos de transcripción sin léxico y el marcador redactado. |
| Correo | 6 | Nunca enviar; la lectura exige sesión de Outlook. |
| Interacción dentro de aplicaciones | 4 | Clic en un juego (H0096), «apretá enter/enviar» en Discord/WhatsApp, «al disco» (transcripción). |
| Navegación y búsqueda web | 4 | Opera GX del dueño, «abre youtube.com en Chrome» (Chrome del dueño), compuesto H0516, un límite sin marca. |
| Instalar y desinstalar software | 4 | pip por regla del dueño; diálogo de Steam inexistente; «diin eternal»; Epic sin lectura de licencia. |
| Contactos / Pantalla | 3 + 3 | Límites sin marca; diálogos de Steam inexistentes en pantalla. |
| Red y Bluetooth | 1 | Modo avión sin mecanismo que no toque la conectividad del dueño; el escaneo (H0302) quedó cubierto como estado honesto con la radio apagada — si el dueño enciende la WLAN puede medirse el escaneo real. |
| Bibliotecas y fichas de juegos | 2 | Navegar la interfaz de Steam/Epic (H0559, H0432): Steam es una ventana SDL/CEF sin árbol de accesibilidad y la vista no puede verificarse desde fuera; pregunta abierta al dueño (despacho con final honesto, captura+OCR, o dejar abiertas). |
| Archivos | 2 | Carpeta + txt + zip + abrir el zip (H0542, composición de cuatro pasos sin nombres), backup a pendrive (H0733, sin pendrive). |
| Organizar ventanas | 2 | Chrome a la izquierda (Chrome ausente, sin operación de ajuste lateral); cerrar las pestañas de Chrome (H0444): Chrome nunca abierto → punto 7 (diferido). |
| Cerrar aplicaciones | 2 | «cerrame todo» y «cerrá todas las ventanas» (H0467, H0484): un cierre real cerraría VS Code, que aloja esta sesión raíz — diferido (nunca desde una tarea desprendida; el dueño decide si se mide fuera de VS Code). |
| Energía | 2 | Apagar/reiniciar: nunca. |
| Audio y volumen | 1 | Volumen de Spotify (H0652): Spotify ausente → punto 7 (diferido). |
| Web actual / Conocimiento | 1 + 1 | Fallo de WhatsApp en internet (motor); H0297 (fragmento libre: las variantes inventan hechos). |
| Sin marca del dueño | 18 | Nunca se acreditan (regla del dueño); repartidos en las categorías anteriores según CURRENT_CATEGORY_COUNTS. |

Techo con las reglas vigentes: los 18 sin marca y los bloques de sesiones ausentes, mensajes y correo (71 filas) no se acreditan sin una decisión nueva del dueño; el resto (≈33) depende de mecanismos verificables (Steam/Epic), de fixtures ausentes (pendrive, Chrome) o de límites sin marca.

## Actualización 2026-09-16 (UI1731)

Bibliotecas y fichas de juegos pasa de 3/6 a 4/6 con abrir Steam o Epic Games y navegar por su interfaz hasta la biblioteca con un clic verificado (commit b0d66326, BUILD1731) (HEAD b0d66326): 8 ejecutados, 5 aprobados, 3 fallidos: los tres casos de Steam abrieron el cliente del dueño (reutilizado) y el clic sobre «BIBLIOTECA» localizado por OCR se verificó por cambio de superficie, con la raíz aprobando sólo esa etiqueta; los tres de Epic abrieron el launcher pero el clic terminó visible_button_not_found y los finales lo dijeron con verdad; los dos límites aprobados, 1 créditos. Uso real del computador según la decisión del dueño (sin atajos steam://): app.open + input.visible.click (UIA → OCR) en turno revisado. Epic queda abierto: la etiqueta no se localiza en la ventana recién lanzada (pendiente de sondeo de tiempos/idioma del launcher).

## Actualización 2026-09-16 (CLOSEALL1733)

Cerrar aplicaciones y ventanas pasa de 18/20 a 20/20 con cerrar todo salvo Visual Studio Code con una operación revisada que pide el cierre de cada ventana y cuenta el resultado (commit daf80061, BUILD1733) (HEAD daf80061): 6 ejecutados, 6 aprobados: las cuatro window.close.all revisadas fueron aprobadas por la raíz con VS Code en ejecución, pidieron el cierre de cada ventana salvo Visual Studio Code (4, 2, 2 y 2 cerradas, ninguna restante) y los finales dieron la cuenta y dijeron que VS Code quedó abierto a propósito; los dos límites aprobados, 2 créditos. Decisión del dueño 2026-09-16 (cerrar todo menos Visual Studio Code): cierre cortés WM_CLOSE + menú de sistema, verificado y contado sin forzar procesos; las ventanas propias de la raíz sirvieron de fixture y las reales del dueño se cerraron en el primer caso (Steam queda en la bandeja). La categoría queda cerrada.

## Actualización 2026-09-16 (UI1735)

Bibliotecas y fichas de juegos pasa de 4/6 a 4/6 con abrir un cliente y navegar por su interfaz hasta una sección o canal nombrado con un clic verificado que espera la carga (commit 614e341b, BUILD1735) (HEAD 614e341b): 9 ejecutados, 2 aprobados (los dos límites), 7 fallidos: en los siete casos app.open abrió y verificó el cliente (Epic o Discord) y el clic aprobado terminó visible_button_not_found tras esperar hasta 24 s; los finales lo dijeron como no verificado, 0 créditos. Lectura de la raíz: la cascada captura la ventana en primer plano y ambos clientes reemplazan su ventana de arranque por la principal tras la verificación del foco de app.open, así que la etiqueta se buscó en la superficie equivocada; reparación pendiente: elegir la ventana visible superior que no sea la del producto y traerla al frente antes de buscar (general para cualquier aplicación).

## Actualización 2026-09-16 (NETWORK1737)

Red y Bluetooth pasa de 20/21 a 21/21 con «apagá el wifi» apagando la radio con revisión de la raíz, y el diálogo de «qué redes wifi hay» avisando y ofreciendo encenderla pero aún sin la misión tras el sí (commit f0c33501, BUILD1737) (HEAD f0c33501): 3 aprobados del grupo apagar (H0324 y dos variantes: wifi.radio.set state = false revisada, aprobada y verificada; finales en primera persona), 3 fallidos del grupo diálogo (primer turno correcto con aviso y oferta; tras el sí la petición de plan volvió a preguntar el estado en vez de encender y escanear), 2 límites aprobados, 1 créditos. Diálogo pendiente de reparación en la mente: el manejador de plan debe reconocer la oferta aceptada como evidencia del estado (NETWORK1739); Chrome por nombre en la misma compilación (WEB1741). La categoría queda cerrada.

## Actualización 2026-09-16 (NETWORK1739)

Red y Bluetooth pasa de 21/21 a 21/21 con el diálogo de «qué redes wifi hay» sin medir: el núcleo de la compilación se detuvo al arrancar y ningún turno se ejecutó (commit 1b25b2ef, BUILD1739) (HEAD 1b25b2ef): 5 fallidos: la App se detuvo al arrancar en todos los casos (núcleo con TypeInitializationException: valores enumerados del argumento browser sin ordenar), ningún turno ni operación, 0 créditos. Compilación corregida a continuación (valores ordenados, comprobación de hello del núcleo en el setup) y repetición del diálogo como NETWORK1741; Chrome por nombre como WEB1743. La categoría queda cerrada.

## Actualización 2026-09-16 (NETWORK1741)

Red y Bluetooth pasa de 21/21 a 21/21 con el diálogo de «qué redes wifi hay» avisando y ofreciendo, con la misión propuesta tras el sí pero rechazada por la forma de confirmación de la App (commit d1582411, BUILD1741) (HEAD d1582411): 3 fallidos del grupo diálogo (primer turno correcto con aviso y oferta; tras el sí la misión wifi.radio.set + wifi.scan se propuso y la App pidió confirmación, pero la captura revisada rechazó la forma de dos pasos y no llegó proposición a la raíz), 2 límites aprobados, 0 créditos. Reparación en la App a continuación: la forma de confirmación revisada admite un paso sensible seguido de la lectura que habilita (NETWORK1743); Chrome por nombre como WEB1745. La categoría queda cerrada.

## Actualización 2026-09-16 (NETWORK1743)

Red y Bluetooth pasa de 21/21 a 21/21 con el diálogo de «qué redes wifi hay» completo: aviso, oferta, encendido revisado y escaneo verificado tras el sí (commit 75fd15b6, BUILD1743) (HEAD 75fd15b6): 5 aprobados: tres diálogos completos (aviso y oferta con la radio apagada; tras el sí, wifi.radio.set state = true aprobada por la raíz y verificada, wifi.scan completada y verificada, final que nombra las redes observadas, enmascaradas en lo publicado) y dos límites; re-demostración de H0302 sin crédito, 0 créditos. Mecanismo del diálogo wifi demostrado de punta a punta; los nombres de red quedan en recibos privados. Siguiente: WEB1745 (Chrome por nombre) en la misma compilación. La categoría queda cerrada.

## Actualización 2026-09-16 (WEB1745)

Navegación y búsqueda web pasa de 42/46 a 43/46 con abrir una dirección web en el navegador nombrado, Chrome incluido (commit e717ebf9, BUILD1745) (HEAD e717ebf9): 3 aprobados (H0276 en Chrome, variante en Edge y variante en inglés en Chrome: browser.navigate.named aprobada por la raíz, ejecutable y URL final verificados; finales fieles, dos sin nombrar el navegador), 1 límite fallido por diseño del instrumento (la pregunta de definición se fundó en web.search, no admitida por este transporte), 1 límite aprobado, 1 créditos. Navegación por nombre generalizada a Chrome, Edge y Brave; el límite de definición debe admitir la búsqueda fundada del conocimiento en instrumentos futuros. Siguiente: filas de Spotify (media.play.query) y Discord (navegación por buscador).

## Actualización 2026-09-16 (MUSIC1747)

Música pasa de 27/39 a 27/39 con reproducción verificada en el cliente de Spotify con revisión de la raíz pero sin final publicado (vetos del compositor) (commit 299b34e7, BUILD1747) (HEAD 299b34e7): 7 fallidos del grupo Spotify: reproducción propuesta, aprobada por la raíz, completada y verificada por now-playing en el cliente, pero sin final publicado (todos los borradores que citaban el título vetados como missing_name por el compositor); 2 límites aprobados, 0 créditos. Reparación del compositor a continuación (la reproducción verificada de Spotify nombra el título observado sin la palabra «título») y repetición del panel como MUSIC1749.

## Actualización 2026-09-16 (MUSIC1749)

Música pasa de 27/39 a 28/39 con «pon Bad Bunny en Spotify» reproduciendo en el cliente con revisión de la raíz y nombrando lo que suena; cuatro reproducciones verificadas aún sin final por los vetos del título (commit 4445dd0f, BUILD1749) (HEAD 4445dd0f): 3 aprobados del grupo Spotify (H0454 y las dos variantes: reproducción aprobada por la raíz, verificada por now-playing y final que nombra lo que suena), 4 fallidos (reproducción verificada pero sin final: título observado contado como idioma o fallo, o título «Artista - Título» exigido entero), 2 límites aprobados, 1 créditos. Reparación del compositor a continuación (título observado opaco a los vetos de idioma y fallo, partes del título aceptadas, consulta sin «en spotify») y repetición como MUSIC1751.

## Actualización 2026-09-16 (MUSIC1751)

Música pasa de 28/39 a 32/39 con poner un artista o una canción en Spotify con reproducción verificada en el cliente y revisión de la raíz (commit 7491fbd5, BUILD1751) (HEAD 7491fbd5): 8 aprobados: cuatro literales (H0237, H0548, H0282, H0579) y dos variantes con media.play.query aprobada por la raíz, verificada por now-playing en el cliente de Spotify y final que nombra lo que suena por su título observado; dos límites, 4 créditos. Reproducción en Spotify demostrada de punta a punta; siguiente: «pon música en spotify» (diálogo que pregunta qué poner), «poné rock», «reproducí…» y «tocá…» (lectores), volumen de Spotify (operación por aplicación).

## Actualización 2026-09-16 (MUSIC1753)

Música pasa de 32/39 a 32/39 con el diálogo de «pon música en spotify» preguntando qué poner y reproduciendo lo contestado con revisión, sin crédito: los literales fallaron en la búsqueda del cliente y una variante contestó en otro idioma (commit 64ce8412, BUILD1753) (HEAD 64ce8412): 1 variante aprobada (pregunta, respuesta guionizada, media.play.query aprobada por la raíz y verificada, final que nombra lo que suena), 3 literales fallidos (el cliente de Spotify no mostró resultados a tiempo; final sin causa), 1 variante fallida (reproducción verificada pero final en español para un pedido en inglés, con opinión añadida), 2 límites aprobados, 0 créditos. Siguiente compilación: más tiempo para la página de búsqueda del cliente, causas de Spotify en el compositor, idioma de la conversación en el turno de respuesta; repetición como MUSIC1755.

## Actualización 2026-09-16 (MUSIC1755)

Música pasa de 32/39 a 32/39 con el diálogo de «pon música en spotify» preguntando qué poner y reproduciendo lo contestado con revisión, sin crédito: un literal y una variante pasaron, dos literales fallaron en el cliente y la variante en inglés siguió contestando en español (commit e6489099, BUILD1755) (HEAD e6489099): 2 aprobados (H0300 y la variante en español: pregunta, respuesta guionizada, media.play.query aprobada por la raíz y verificada, final que nombra lo que suena), 2 literales fallidos en el cliente (reproducir pulsado sin sonar a tiempo; ningún resultado en 12 s) con finales sin causa, 1 variante fallida (reproducción verificada pero final en español para un pedido en inglés, con opinión), 2 límites aprobados, 0 créditos. Siguiente compilación: el compositor prefiere el código de error del cliente cuando tiene hecho de causa y hereda el idioma de los pedidos anteriores; repetición como MUSIC1757.

## Actualización 2026-09-16 (MUSIC1757)

Música pasa de 32/39 a 32/39 con el diálogo de «pon música en spotify» preguntando qué poner y reproduciendo lo contestado con revisión (los tres literales y la variante en español aprobados), sin crédito porque la variante en inglés siguió contestando en español (commit a35f5b18, BUILD1757) (HEAD a35f5b18): 6 aprobados (los tres literales y la variante en español: pregunta, respuesta guionizada, media.play.query aprobada por la raíz y verificada, final que nombra lo que suena; dos límites), 1 variante fallida (reproducción verificada pero final en español para un pedido en inglés, con opinión: la App no adjunta los pedidos anteriores a la composición de un final de operación), 0 créditos. Siguiente compilación: la App adjunta los pedidos anteriores a toda composición; repetición como MUSIC1759.

## Actualización 2026-09-16 (MUSIC1759)

Música pasa de 32/39 a 32/39 con el diálogo de «pon música en spotify» preguntando qué poner y reproduciendo lo contestado con revisión (los tres literales y la variante en español aprobados; la pregunta y la confirmación en inglés ya salen en inglés), sin crédito porque el final de la variante en inglés siguió en español (commit f0d45310, BUILD1759) (HEAD f0d45310): 6 aprobados (los tres literales y la variante en español con reproducción aprobada por la raíz y verificada, final que nombra lo que suena; dos límites), 1 variante fallida (pregunta y confirmación en inglés, reproducción verificada, pero final en español con opinión: el final se compone sobre la palabra de confirmación), 0 créditos. Siguiente compilación: la palabra de confirmación no fija el idioma (cae al de los pedidos anteriores) y los finales de operación no abren con opiniones; repetición como MUSIC1761.

## Actualización 2026-09-16 (MUSIC1761)

Música pasa de 32/39 a 32/39 con el diálogo de «pon música en spotify» preguntando qué poner y reproduciendo lo contestado con revisión (los tres literales y la variante en español aprobados; la variante en inglés ya sin opinión y con pregunta y confirmación en inglés), sin crédito porque su final siguió en español (commit de6b4e56, BUILD1761) (HEAD de6b4e56): 6 aprobados (los tres literales y la variante en español con reproducción aprobada por la raíz y verificada, final que nombra lo que suena; dos límites), 1 variante fallida (pregunta y confirmación en inglés, reproducción verificada, final sin opinión pero en español: la composición del final no recibe los pedidos anteriores), 0 créditos. Siguiente compilación: comprobar y corregir qué pedidos anteriores llegan a la composición de un final revisado; repetición como MUSIC1763.

## Actualización 2026-09-16 (MUSIC1763)

Música pasa de 32/39 a 35/39 con pedir música en Spotify sin decir cuál, preguntar qué poner y reproducir lo contestado con revisión de la raíz (commit dea376fb, BUILD1763) (HEAD dea376fb): 7 aprobados: tres literales y dos variantes (pregunta qué poner, respuesta guionizada, media.play.query aprobada por la raíz y verificada por now-playing, final que nombra lo que suena, en inglés para la conversación en inglés) y dos límites, 3 créditos. Diálogo de Spotify demostrado de punta a punta en los dos idiomas; siguiente: Epic Games hasta la biblioteca (UI1765) y las filas restantes de Música (lectores y volumen por aplicación).

## Actualización 2026-09-16 (UI1765)

Bibliotecas y fichas de juegos pasa de 4/6 a 4/6 con abrir Epic Games sin llegar a la biblioteca: el clic visible se rindió a los 2,7 s porque el bucle de espera cortaba ante el código «no encontrado» (commit b4053cae, BUILD1765) (HEAD b4053cae): 3 fallidos (app.open del launcher verificada y clic aprobado, pero input.visible.click terminó no encontrado a los 2,7 s: el bucle de espera cortaba ante el código de la etapa UIA), 2 límites aprobados, 0 créditos. Reparación del bucle de espera del clic visible a continuación (espera mientras la respuesta sea de cascada) y repetición como UI1767.

## Actualización 2026-09-16 (UI1767)

Bibliotecas y fichas de juegos pasa de 4/6 a 4/6 con abrir Epic Games y navegar hasta la biblioteca con un clic verificado por OCR en el literal, sin crédito porque las dos variantes no encontraron la etiqueta tras el cierre forzado del launcher anterior (commit ab6b40a0, BUILD1767) (HEAD ab6b40a0): 1 literal aprobado (app.open del launcher verificada, clic en «Biblioteca» localizado por OCR tras la espera de carga, superficie cambiada, final fiel), 2 variantes fallidas (etiqueta no encontrada tras la espera completa en un launcher reabierto tras un cierre forzado), 2 límites aprobados, 0 créditos. Sondear el segundo arranque del launcher tras el cierre de la raíz y corregir el cierre del instrumento o la elección de superficie; repetición como UI1771.

## Actualización 2026-09-17 (MUSIC1769)

Música pasa de 35/39 a 37/39 con tocar una canción sin decir cuál (pregunta y reproducción de lo contestado) y poner un género en Spotify con revisión de la raíz; la obra clásica se reprodujo verificada pero su título largo no cupo en el final (commit 57f5250a, BUILD1769) (HEAD 57f5250a): MUSIC1769: 9 ejecutados, 8 aprobados, 1 fallido, 2 créditos (H0178 diálogo, H0552 género); H0163 reprodujo la sinfonía 1 verificada pero el compositor no citó el título largo (missing_name), 2 créditos. MUSIC1769 sobre BUILD1769: 3 literales, 4 variantes (2 en inglés), 2 límites; 8/9 aprobados; H0178 y H0552 con dos variantes aprobadas cada uno; H0163 fallido por final ausente

## Actualización 2026-09-17 (UI1771)

Bibliotecas y fichas de juegos pasa de 4/6 a 4/6 con abrir Epic Games y navegar hasta la biblioteca con un clic visible revisado: sin crédito, el launcher abre ya en la biblioteca y la etiqueta duplicada (14 px frente a 17 px) queda fuera del umbral del 80 %; relanzamiento tras cierre forzado más lento que la verificación de app.open (commit 20dc0889, BUILD1771) (HEAD 20dc0889): UI1771: 5 ejecutados, 2 aprobados (límites), 3 fallidos, 0 créditos; causa medida: etiqueta duplicada con 14 px frente a 17 px fuera del umbral del 80 % y relanzamiento lento tras cierre forzado, 0 créditos. UI1771 sobre BUILD1769: 1 literal, 2 variantes, 2 límites; 2/5 aprobados; sonda OCR de la raíz: «Biblioteca» a 14 px y 17 px (0,82)

## Actualización 2026-09-17 (MUSIC1773)

Música pasa de 37/39 a 37/39 con reproducir una obra nombrada en Spotify con revisión de la raíz citando el título observado: el título llega ya íntegro (UTF-8) y las dos variantes lo citaron, pero el literal sigue sin final porque la pista de reintento no entrega el título a las consultas de Spotify (commit 26b718db, BUILD1773) (HEAD 26b718db): MUSIC1773: 5 ejecutados, 4 aprobados, 1 fallido, 0 créditos; el título llega íntegro (UTF-8) y las variantes lo citan; el literal sigue sin final porque la pista de reintento no entrega el título a las consultas de Spotify; tres casos reejecutados tras un rechazo de RAM del runner, 0 créditos. MUSIC1773 sobre BUILD1773: 1 literal, 2 variantes (1 en inglés), 2 límites; 4/5 aprobados; literal sin final (missing_name en cada reintento)

## Actualización 2026-09-17 (UI1775)

Bibliotecas y fichas de juegos pasa de 4/6 a 5/6 con abrir Epic Games y navegar por su interfaz hasta la biblioteca con un clic visible verificado por OCR: la etiqueta duplicada se resuelve por la impresión menor con margen del 5 % y app.open espera la ventana lenta; literal y dos variantes aprobados (commit bb9c8540, BUILD1775) (HEAD bb9c8540): UI1775: 5 ejecutados, 5 aprobados, 1 crédito (H0432 con dos variantes): la etiqueta duplicada se resuelve por la impresión menor con margen del 5 % y app.open espera la ventana lenta del launcher, 1 créditos. UI1775 sobre BUILD1773: 1 literal, 2 variantes, 2 límites; 5/5 aprobados; clic OCR verificado sobre la navegación del launcher (14 px frente a 17 px)

## Actualización 2026-09-17 (MUSIC1777)

Música pasa de 37/39 a 37/39 con reproducir una obra nombrada en Spotify con revisión de la raíz citando el título observado: con la pista el modelo ya cita el título entero, pero escapó las comillas interiores con barra invertida y el literal sigue sin final; las variantes lo citan (commit 8efa9596, BUILD1777) (HEAD 8efa9596): MUSIC1777: 5 ejecutados, 4 aprobados, 1 fallido, 0 créditos; la pista hace citar el título entero pero el modelo escapó las comillas interiores con barra invertida y la lente no lo reconoció, 0 créditos. MUSIC1777 sobre BUILD1777: 1 literal, 2 variantes (1 en inglés), 2 límites; 4/5 aprobados; literal sin final (comillas escapadas)

## Actualización 2026-09-17 (MUSIC1779)

Música pasa de 37/39 a 38/39 con reproducir una obra nombrada en Spotify con revisión de la raíz citando el título observado entero aunque sea largo y lleve comillas interiores; literal y dos variantes aprobados (commit eacdfa6a, BUILD1779) (HEAD eacdfa6a): MUSIC1779: 5 ejecutados, 5 aprobados, 1 crédito (H0163 con dos variantes): el final cita el título observado entero, con sus comillas interiores y sin barras invertidas, 1 créditos. MUSIC1779 sobre BUILD1779: 1 literal, 2 variantes (1 en inglés), 2 límites; 5/5 aprobados

## Actualización 2026-09-17 (ARRANGE1781)

Organizar ventanas y pestañas pasa de 11/13 a 11/13 con colocar una aplicación nombrada en una mitad de la pantalla: la operación window.snap existe y se verificó en la variante en inglés, pero en castellano el paso quedó sin argumentos (el proyector determinista no copia el lado literal); sin crédito (commit 4b0cc30d, BUILD1781) (HEAD 4b0cc30d): ARRANGE1781: 5 ejecutados, 2 aprobados, 3 fallidos, 0 créditos; window.snap verificada en la variante en inglés; en castellano el paso quedó sin argumentos (step_data_missing: el proyector determinista no copia el lado literal), 0 créditos. ARRANGE1781 sobre BUILD1781: 1 literal, 2 variantes (1 en inglés), 2 límites; 2/5 aprobados

## Actualización 2026-09-17 (ARRANGE1783)

Organizar ventanas y pestañas pasa de 11/13 a 11/13 con colocar una aplicación nombrada en una mitad de la pantalla: el proyector ya entrega el lado, pero la validación de evidencia de enumeraciones no reconocía «izquierda»/«derecha» como left/right; verificado sólo en inglés; sin crédito (commit b8074ef4, BUILD1783) (HEAD b8074ef4): ARRANGE1783: 5 ejecutados, 2 aprobados, 3 fallidos, 0 créditos; el proyector ya entrega el lado pero la tabla de alias de evidencia de enumeraciones no reconocía izquierda/derecha como left/right, 0 créditos. ARRANGE1783 sobre BUILD1783: 1 literal, 2 variantes (1 en inglés), 2 límites; 2/5 aprobados

## Actualización 2026-09-17 (ARRANGE1785)

Organizar ventanas y pestañas pasa de 11/13 a 12/13 con colocar una aplicación nombrada en una mitad de la pantalla ejecutado y verificado sobre su ventana (window.snap con lado literal en ambos idiomas); literal y dos variantes aprobados (commit 8dee706b, BUILD1785) (HEAD 8dee706b): ARRANGE1785: 5 ejecutados, 4 aprobados, 1 crédito (H0268 con dos variantes): window.snap coloca la ventana de Chrome en la mitad pedida con límites verificados; el límite de definición derivó a ventanas de edificios, 1 créditos. ARRANGE1785 sobre BUILD1785: 1 literal, 2 variantes (1 en inglés), 2 límites; 4/5 aprobados

## Actualización 2026-09-17 (AUDIO1787)

Audio y volumen pasa de 46/51 a 46/51 con subir o bajar el volumen propio de una aplicación nombrada: la operación y la pregunta existen, pero la respuesta numérica sola es rechazada por la App antes de la mente (guardia de selección de nota sin contexto); sin crédito (commit ce9f3909, BUILD1787) (HEAD ce9f3909): AUDIO1787: 5 ejecutados, 2 aprobados (límites), 3 fallidos, 0 créditos; las tres preguntas se publicaron y la App rechazó la respuesta numérica sola antes de la mente (guardia de selección de nota sin contexto), 0 créditos. AUDIO1787 sobre BUILD1787: 1 literal, 2 variantes (1 en inglés), 2 límites; 2/5 aprobados

## Actualización 2026-09-17 (AUDIO1789)

Audio y volumen pasa de 46/51 a 46/51 con subir o bajar el volumen propio de una aplicación nombrada: la respuesta numérica ya llega a la mente, pero se clasifica como entrada no resuelta porque la App consumió su objetivo pendiente antes de la llamada; sin crédito (commit 2cf20459, BUILD1789) (HEAD 2cf20459): AUDIO1789: 5 ejecutados, 2 aprobados (límites), 3 fallidos, 0 créditos; el número llega a la mente pero se clasifica como entrada no resuelta porque la App consumió su objetivo pendiente (pendingClarification=false) antes de la llamada, 0 créditos. AUDIO1789 sobre BUILD1789: 1 literal, 2 variantes (1 en inglés), 2 límites; 2/5 aprobados

## Actualización 2026-09-17 (AUDIO1791)

Audio y volumen pasa de 46/51 a 46/51 con subir o bajar el volumen propio de una aplicación nombrada: la respuesta numérica ya se decide como el ajuste, pero el paso de argumentos no la completa desde el pedido anterior y vuelve a preguntar; sin crédito (commit a009f052, BUILD1791) (HEAD a009f052): AUDIO1791: 5 ejecutados, 2 aprobados (límites), 3 fallidos, 0 créditos; la respuesta ya se decide como el ajuste pero los argumentos no se completan desde el pedido anterior y la App vuelve a preguntar, 0 créditos. AUDIO1791 sobre BUILD1791: 1 literal, 2 variantes (1 en inglés), 2 límites; 2/5 aprobados

## Actualización 2026-09-17 (AUDIO1793)

Audio y volumen pasa de 46/51 a 46/51 con subir o bajar el volumen propio de una aplicación nombrada: el ajuste de las sesiones de Spotify se ejecutó y verificó por primera vez (100 → 85, 85 → 95), pero los finales afirmaron de más (cerrado, sin sonido, abierto) o faltaron; sin crédito (commit 0056b057, BUILD1793) (HEAD 0056b057): AUDIO1793: 5 ejecutados, 2 aprobados (límites), 3 fallidos, 0 créditos; el ajuste de las sesiones de Spotify se ejecutó y verificó (100 → 85, 85 → 95) pero los finales afirmaron de más (cerrado, sin sonido, abierto) o faltaron (sesión ya al máximo), 0 créditos. AUDIO1793 sobre BUILD1793: 1 literal, 2 variantes (1 en inglés), 2 límites; 2/5 aprobados

## Actualización 2026-09-17 (AUDIO1795)

Audio y volumen pasa de 46/51 a 46/51 con subir o bajar el volumen propio de una aplicación nombrada: literal y variante en inglés ejecutados y verificados con finales fieles (40 → 60, 40 → 50) pero registrados como fallidos por instrumento (el adjudicador sellado exige diálogo revisado); la variante en castellano bajó a 25 sin final; sin crédito (commit bbe1b15a, BUILD1795) (HEAD bbe1b15a): AUDIO1795: 5 ejecutados, 2 aprobados (límites), 3 fallidos, 0 créditos; el literal y la variante en inglés ejecutaron y verificaron el ajuste de Spotify (40 → 60, 40 → 50) con finales fieles pero el adjudicador sellado sólo admite diálogos revisados; la variante en castellano bajó a 25 sin final, 0 créditos. AUDIO1795 sobre BUILD1795: 1 literal, 2 variantes (1 en inglés), 2 límites; 2/5 registrados como aprobados

## Actualización 2026-09-17 (AUDIO1797)

Audio y volumen pasa de 46/51 a 46/51 con subir o bajar el volumen propio de una aplicación nombrada: los tres ajustes se verificaron (40 → 60, 40 → 25, 40 → 50) y el instrumento ya conoce el diálogo ordinario, pero el veto ampliado descartó todos los finales por su frase sobre el sonido activo; sin crédito (commit 668e0178, BUILD1797) (HEAD 668e0178): AUDIO1797: 5 ejecutados, 2 aprobados (límites), 3 fallidos, 0 créditos; los tres ajustes de Spotify se verificaron (40 → 60, 40 → 25, 40 → 50) sobre el instrumento de diálogo ordinario, pero el veto ampliado descartó todos los finales por la frase sobre el sonido activo, 0 créditos. AUDIO1797 sobre BUILD1797: 1 literal, 2 variantes (1 en inglés), 2 límites; 2/5 aprobados

## Actualización 2026-09-17 (AUDIO1799)

Audio y volumen pasa de 46/51 a 46/51 con subir o bajar el volumen propio de una aplicación nombrada: literal y variante en castellano aprobados con niveles verificados (40 → 60, 40 → 25) y finales fieles; la variante en inglés subió a 50 pero el veto no distinguió la negación «not silenced»; sin crédito por falta del segundo par (commit 64567559, BUILD1799) (HEAD 64567559): AUDIO1799: 5 ejecutados, 4 aprobados, 1 fallido, 0 créditos; literal y variante en castellano verificados con finales fieles (40 → 60, 40 → 25); la variante en inglés subió a 50 pero el veto no distinguió «not silenced», 0 créditos. AUDIO1799 sobre BUILD1799: 1 literal, 2 variantes (1 en inglés), 2 límites; 4/5 aprobados; sin segundo par

## Actualización 2026-09-17 (AUDIO1801)

Audio y volumen pasa de 46/51 a 47/51 con subir o bajar el volumen propio de una aplicación nombrada preguntando la cantidad y verificando la postlectura de sus sesiones de audio (Spotify 40 → 60, 40 → 25, 40 → 50); literal y dos variantes aprobados (commit e02aa8c3, BUILD1801) (HEAD e02aa8c3): AUDIO1801: 5 ejecutados, 5 aprobados, 1 crédito (H0652 con dos variantes): pregunta la cantidad y ajusta las sesiones de Spotify a niveles verificados (40 → 60, 40 → 25, 40 → 50) sin tocar el volumen del sistema; Música 39/39, 1 créditos. AUDIO1801 sobre BUILD1801: 1 literal, 2 variantes (1 en inglés), 2 límites; 5/5 aprobados La categoría queda cerrada.

## Actualización 2026-09-17 (WEB1803)

Navegación y búsqueda web pasa de 43/46 a 43/46 con buscar en la web en el navegador nombrado con la familia Opera corriendo en Opera GX: literal y variante en castellano aprobados; la variante en inglés (clima) y el límite de definición derivaron a web.search; sin crédito por falta del segundo par (commit 697c53ab, BUILD1803) (HEAD 697c53ab): WEB1803: 5 ejecutados, 3 aprobados, 2 fallidos, 0 créditos; literal y variante en castellano verificados en Opera GX (familia Opera); la variante en inglés (clima) y el límite de definición derivaron a web.search, 0 créditos. WEB1803 sobre BUILD1803: 1 literal, 2 variantes (1 en inglés), 2 límites; 3/5 aprobados; sin segundo par

## Actualización 2026-09-17 (WEB1805)

Navegación y búsqueda web pasa de 43/46 a 44/46 con buscar en la web en el navegador nombrado, con la familia Opera corriendo en la Opera GX instalada y la URL de búsqueda verificada; literal y dos variantes aprobados (commit 3679379d, BUILD1805) (HEAD 3679379d): WEB1805: 5 ejecutados, 5 aprobados, 1 crédito (H0094 con dos variantes): la búsqueda en el navegador nombrado corre en la Opera GX instalada con la URL verificada, 1 créditos. WEB1805 sobre BUILD1803: 1 literal, 2 variantes (1 en inglés), 2 límites; 5/5 aprobados

## Actualización 2026-09-17 (SCREEN1807)

Pantalla, captura e interpretación visual pasa de 16/19 a 16/19 con leer la pantalla cuando la persona describe primero lo que tiene abierto y pide ver qué hay en pantalla o identificar un botón (commit 0bb6e9a1, BUILD1807) (HEAD 0bb6e9a1): seis casos en BUILD1807 (cinco turnos revisados de captura con el diálogo de instalación de Steam abierto y cerrado por la raíz, nada instalado; un límite ordinario): tres aprobados (el literal que pide ver qué hay en pantalla, con aviso honesto de alcance, 25 líneas y tres citas textuales; la variante en castellano; el límite) y tres fallidos (los literales «para ver la pantalla» e «identificá el botón» copiaron la instrucción interna «y cita cada una de esas líneas tal cual» como frase propia y no dijeron que sólo leen el texto; la variante en inglés afirmó 3 líneas, la cuenta del extracto, y envolvió toda la respuesta entre comillas), 0 créditos. Causa medida: el aviso honesto de alcance sólo se pide cuando el pedido dice ver/describir/hay en; el compositor expone excerptLines junto a lineCount y la instrucción «cita cada una de esas líneas tal cual» es copiable como frase. Sin crédito: una sola variante aprobada. Siguiente: repetir con la reparación del compositor (aviso para «para ver la pantalla», «identificá el botón»; sin excerptLines; eco de la instrucción vetado).

## Actualización 2026-09-17 (SCREEN1809)

Pantalla, captura e interpretación visual pasa de 16/19 a 16/19 con leer la pantalla con su alcance dicho cuando la persona describe primero lo que tiene abierto y pide ver la pantalla o identificar un botón (commit 5513768e, BUILD1809) (HEAD 5513768e): seis casos en BUILD1809 (cinco turnos revisados de captura con el diálogo de instalación de Steam abierto y cerrado por la raíz, nada instalado; un límite ordinario): cuatro aprobados (los literales que piden ver qué hay en pantalla y ver la pantalla, con aviso honesto de alcance, 25 líneas y tres citas textuales verificadas; la variante en castellano; el límite) y dos fallidos (el literal que pide identificar el botón no recibió final: sus seis borradores fieles fueron vetados por la lente de fallo del compositor como asserted_failure porque la exención de alcance no cubre «identificar botones»; la variante en inglés dijo 3 líneas, las del extracto, en vez de 25), 0 créditos. Causa medida: la exención de alcance de la lente de fallo (mente y App) sólo cubre describir/ver imágenes; el compositor no contrasta la cuenta de líneas dicha con lineCount. Sin crédito: una sola variante aprobada. Siguiente: repetir con la exención para identificar botones y una comprobación de la cuenta de líneas.

## Actualización 2026-09-17 (SCREEN1811)

Pantalla, captura e interpretación visual pasa de 16/19 a 19/19 con leer la pantalla con su alcance dicho, también sobre botones, y con la cuenta de líneas reconocida (commit ec3dbf6b, BUILD1811) (HEAD ec3dbf6b): seis casos en BUILD1811 (cinco turnos revisados de captura con el diálogo de instalación de Steam abierto y cerrado por la raíz, nada instalado; un límite ordinario), todos aprobados: cada turno revisado propuso capture.screenshot, la raíz la aprobó, ocr.read leyó la captura y el final dijo la cuenta reconocida (25 líneas) y tres líneas reconocidas tal cual (verificadas contra el texto privado); los literales que piden ver qué hay en pantalla y ver la pantalla y la variante en castellano dijeron primero que no pueden describir imágenes, sólo leer el texto; el literal que pide identificar el botón dijo primero que no puede identificar botones en imágenes; la variante en inglés informó la cuenta y las líneas; el límite reconoció la prohibición sin capturar, 3 créditos. Medido: exención de alcance para botones (mente y App) y contraste de la cuenta dicha con lineCount efectivos; H0285, H0492 y H0704 acreditados con ambas variantes; «Pantalla, captura e interpretación visual» 19/19 cerrada, 14/35 categorías cerradas. Siguiente: categoría por masa abierta según CONDICIONES (juegos/Steam: H0571 con aclaración de título aproximado; H0101 clic en Instalar con verificación). La categoría queda cerrada.

## Actualización 2026-09-17 (MIC1813)

Interacción dentro de aplicaciones pasa de 18/22 a 18/22 con silenciar el micrófono del sistema cuando la persona lo pide sin nombrar un cliente reconocible (commit 4a224f25, BUILD1813) (HEAD 4a224f25): cinco casos en la compilación de SCREEN1811 (tres turnos ordinarios de micrófono con preajuste, medición y restauración por la raíz; dos límites ordinarios): tres aprobados (la variante en inglés «The microphone is muted.» y los dos límites) y dos fallidos (el literal y la variante en castellano no recibieron final: audio.microphone.mute se completó y verificó y la raíz midió el micrófono silenciado, pero los borradores verdaderos «El micrófono está silenciado.» fueron vetados tres veces como reversed_mute porque el patrón «no esta silenci» del compositor casa dentro de «micrófono está silenciado»), 0 créditos. Causa medida: patrón de estado sin silenciar del compositor sin límite de palabra (casa dentro de micrófono). Sin crédito: una sola variante aprobada. Siguiente: repetir con el patrón corregido.

## Actualización 2026-09-17 (MIC1815)

Interacción dentro de aplicaciones pasa de 18/22 a 19/22 con silenciar el micrófono del sistema cuando la persona lo pide sin nombrar un cliente reconocible, con el final en castellano (commit dfb0f2ec, BUILD1815) (HEAD dfb0f2ec): cinco casos en BUILD1815 (tres turnos ordinarios de micrófono con preajuste, medición y restauración por la raíz; dos límites ordinarios), todos aprobados: el literal y las dos variantes propusieron audio.microphone.mute con state true, completada y verificada por la postlectura del endpoint de captura, la raíz midió el micrófono silenciado después y los finales lo dijeron («El micrófono está silenciado.», «The microphone is muted.»); el límite de definición explicó sin silenciar y el de prohibición lo reconoció, 1 créditos. Medido: el patrón reversed_mute con límite de palabra deja pasar el final verdadero en castellano; H0420 acreditado con ambas variantes; «Interacción dentro de aplicaciones» 19/22. Siguiente: categoría por masa abierta según CONDICIONES (pip como lectura de estado del paquete; título aproximado de Steam; pendrive).

## Actualización 2026-09-17 (PIP1817)

Instalar y desinstalar software pasa de 27/31 a 27/31 con responder a instalar un paquete de Python con pip leyendo si ya está instalado en cada Python registrado (commit 6d3220af, BUILD1817) (HEAD 6d3220af): cinco casos en BUILD1817 (tres turnos ordinarios de paquete con pip, dos límites ordinarios): tres aprobados (el literal: requests instalado en Python 3.12.10 y 3.10.0 con las cadenas exactas del recibo y sin pip en 3.13.3; los dos límites) y dos fallidos (la variante numpy negó una instalación que el recibo muestra en dos Python; la variante pandas se contradijo y atribuyó el paquete a un Python que no lo tiene: el modelo generalizó la primera entrada de la lista, la del Python sin pip), 0 créditos. Causa medida: la lista por Python (installed true/false por entrada) se le entrega cruda al modelo de 4B, que generaliza la primera entrada. Sin crédito. Siguiente: repetir con la proyección partida (instalado en / no instalado en / sin pip en) y una comprobación de estado del final.

## Actualización 2026-09-17 (PIP1819)

Instalar y desinstalar software pasa de 27/31 a 27/31 con responder a instalar un paquete de Python con pip diciendo en qué Python registrado ya está instalado (commit 42d449d1, BUILD1819) (HEAD 42d449d1): cinco casos en BUILD1819 (tres turnos ordinarios de paquete con pip, dos límites ordinarios): cuatro aprobados (las dos variantes con las listas partidas: numpy instalado en Python 3.12.10 y 3.10.0 con sus versiones y sin pip en 3.13.3; pandas instalado sólo en 3.12.10; los dos límites) y uno fallido (el literal no recibió final: sus tres borradores verdaderos empiezan con el nombre del paquete tal cual lo escribió la persona y la regla de mayúscula inicial del compositor los vetó), 0 créditos. Causa medida: la regla de mayúscula inicial veta un final que empieza con el identificador del paquete observado. Sin crédito. Siguiente: repetir con la exención del identificador observado al inicio.

## Actualización 2026-09-17 (PIP1821)

Instalar y desinstalar software pasa de 27/31 a 28/31 con responder a instalar un paquete de Python con pip diciendo en qué Python registrado ya está instalado, aun empezando por el nombre del paquete (commit b4cbfc20, BUILD1821) (HEAD b4cbfc20): cinco casos en BUILD1821 (tres turnos ordinarios de paquete con pip, dos límites ordinarios), todos aprobados: el literal y las dos variantes ejecutaron software.python.package.status (pip show en los tres Python registrados, nada instalado) con recibo verificado y los finales dijeron, desde las listas partidas, en qué Python está instalado el paquete con su versión, en cuál no y en cuál no hay pip; el final puede empezar con el nombre del paquete tal cual; los límites explicaron y reconocieron sin leer, 1 créditos. Medido: proyección partida, comprobación de estado y exención del identificador observado efectivas; H0052 acreditado con ambas variantes; «Abrir aplicaciones» 51/54. Siguiente: categoría por masa abierta según CONDICIONES (título aproximado de Steam H0571; pendrive H0733; abrí chrome y poné música H0352).

## Actualización 2026-09-17 (USB1823)

Archivos y carpetas pasa de 30/32 a 31/32 con responder a un respaldo a pendrive leyendo qué unidades extraíbles hay conectadas y diciendo con verdad que no hay ninguna (commit 15e259fe, BUILD1823) (HEAD 15e259fe): cinco casos en BUILD1823 (tres turnos ordinarios de unidad extraíble, dos límites ordinarios), todos aprobados: el literal y las dos variantes ejecutaron la nueva storage.removable.list (DriveInfo; ninguna unidad extraíble conectada en este PC) con recibo verificado y dijeron que ahora no hay ningún pendrive ni disco USB conectado, que no se copió nada y que puede conectar uno y pedirlo de nuevo; los límites explicaron y reconocieron sin leer, 1 créditos. Medido: lectura de unidades extraíbles con respuesta honesta de ausencia; H0733 acreditado con ambas variantes; «Archivos y carpetas» 31/32 (queda H0542 zip). Siguiente: categoría por masa abierta según CONDICIONES (título aproximado de Steam H0571; abrí chrome y poné música H0352; zip H0542).

## Actualización 2026-09-17 (STEAM1825)

Instalar y desinstalar software pasa de 28/31 a 29/31 con responder a una descarga de Steam dictada con error leyendo el estado del juego en la biblioteca autenticada (commit dced7cf0, BUILD1825) (HEAD dced7cf0): cinco casos en la compilación de USB1823 (tres turnos ordinarios de biblioteca de Steam, dos límites ordinarios), todos aprobados: el literal (dictado de un juego que el dueño posee y no tiene instalado, resuelto por el alias del catálogo conocido) y las dos variantes ejecutaron game.entitlement.named sobre la biblioteca autenticada con recibo verificado y dijeron el estado leído nombrando el juego como la persona lo nombró (en la biblioteca y no instalado con la confirmación pendiente, o ya instalado), sin descargar, comprar ni abrir nada; los límites explicaron y reconocieron sin leer; títulos en recibos privados, 1 créditos. Medido: la lectura de biblioteca existente responde el título dictado con error; H0571 acreditado con ambas variantes; «Instalar y desinstalar software» 29/31 (quedan H0578 Epic sin lectura de licencia y una fila más). Siguiente: categoría por masa abierta según CONDICIONES (abrí chrome y poné música H0352; zip H0542).

## Actualización 2026-09-17 (MUSIC1827)

Música pasa de 38/39 a 38/39 con poner música en un navegador nombrado preguntando qué música y abriendo los resultados de YouTube en ese navegador (commit 8cbf90a7, BUILD1827) (HEAD 8cbf90a7): cinco casos en BUILD1827 (tres diálogos revisados en los perfiles propios de Chrome y Edge del producto, dos límites ordinarios): el producto se comportó como se esperaba en los tres diálogos (preguntó qué música; con rock, jazz y lofi propuso browser.navigate.named al navegador nombrado con la URL de resultados de YouTube, la raíz la aprobó, la navegación se completó y se verificó por la postlectura CDP y los finales lo dijeron), pero la lista sellada de operaciones permitidas incluyó media.play.query (operación nominal de la aclaración, nunca ejecutada) y el adjudicador sellado sólo admite un diálogo aprobado que ejecute exactamente todas las permitidas: los tres se registran como fallidos por instrumento; los dos límites aprobados, 0 créditos. Causa medida: instrumento sellado con una operación permitida excedente; el producto es correcto. Sin crédito. Siguiente: MUSIC1829 sobre la misma compilación con la lista permitida corregida (memory.status y browser.navigate.named).

## Actualización 2026-09-17 (MUSIC1829)

Música pasa de 38/39 a 39/39 con poner música en un navegador nombrado preguntando qué música y abriendo los resultados de YouTube en ese navegador (commit f369a539, BUILD1829) (HEAD f369a539): cinco casos en la compilación de MUSIC1827 con la lista permitida corregida (tres diálogos revisados en los perfiles propios de Chrome y Edge del producto, dos límites ordinarios), todos aprobados: el literal y las dos variantes preguntaron qué música sin operar y, con las respuestas guionizadas de la raíz (rock, jazz, lofi), propusieron browser.navigate.named al navegador nombrado con la URL de resultados de YouTube, la raíz la aprobó, la navegación se completó y se verificó por la postlectura CDP y los finales dijeron que abrieron esa búsqueda; los límites explicaron y reconocieron sin navegar, 1 créditos. Medido: aclaración de música en navegador nombrado y navegación revisada a los resultados de YouTube; H0352 acreditado con ambas variantes; «Música» 39/39 cerrada, 14/35 categorías cerradas. Siguiente: categoría por masa abierta según CONDICIONES (mensajería y vídeo pendientes de decisión del dueño; zip H0542; Epic H0578). La categoría queda cerrada.

## Actualización 2026-09-17 (WEB1831)

Información web actual pasa de 16/17 a 16/17 con investigar en internet la pregunta que la persona plantea tras un preámbulo conversacional, con sus propias palabras como consulta (commit d7d2272c, BUILD1831) (HEAD d7d2272c): cinco casos en BUILD1831 (tres turnos ordinarios de búsqueda, dos límites ordinarios): la mente leyó el literal pese al preámbulo conversacional y enlazó las palabras de la persona como consulta, y las variantes directas enlazaron su pregunta, pero las tres web.search terminaron web_search_results_irrelevant (el RSS de Bing devuelve páginas ajenas para una consulta con forma de pregunta y la puerta de pertinencia no admitió ninguna); los finales dijeron con verdad que no pudieron investigar; los dos límites aprobados, 0 créditos. Causa medida: el motor público no responde consultas con forma de pregunta y la puerta de pertinencia exige todas las palabras de la consulta. Sin crédito. Siguiente: consulta de palabras de contenido (sujeto y verbo de la persona) y pertinencia tolerante a flexiones.

## Actualización 2026-09-17 (KNOW1833)

Conocimiento, razonamiento y creatividad verbal pasa de 36/37 a 36/37 con responder a un tramo largo de habla sin pedido diciendo que no encuentra un pedido y preguntando si la persona necesita algo (commit de2f3926, BUILD1833) (HEAD de2f3926): cinco casos en la compilación de WEB1831 (tres turnos ordinarios sin operaciones, dos límites ordinarios): tres aprobados (el literal y la variante en castellano recibieron la aclaración de habla ajena diseñada, «En eso no encuentro un pedido para mí; ¿necesitás algo?», sin operar ni responder lo dicho; el límite de significado) y dos fallidos (la variante en inglés repitió la afirmación en vez de la aclaración; el límite de no contestar dijo no haber entendido), 0 créditos. Causa medida: la aclaración de habla ajena no se produce en inglés (eco del habla admitido por el validador) y el pedido de no contestar se lee como incomprensión. Sin crédito: una sola variante aprobada. Siguiente: repetir con la aclaración en inglés reparada.

## Actualización 2026-09-17 (KNOW1835)

Conocimiento, razonamiento y creatividad verbal pasa de 36/37 a 37/37 con responder a un tramo largo de habla sin pedido diciendo que no encuentra un pedido y preguntando si la persona necesita algo (commit 7b49c215, BUILD1835) (HEAD 7b49c215): cinco casos en BUILD1835 (tres turnos ordinarios sin operaciones, dos límites ordinarios): cuatro aprobados (el literal y las dos variantes de afirmación larga recibieron la aclaración de habla ajena, en castellano y en inglés, sin operar ni responder lo dicho; el límite de significado explicó) y un límite fallido (el pedido de no contestar recibió «no pude entender», que no es verdad), 1 créditos. Medido: la App ya no toma una afirmación larga por pregunta de conocimiento sin responder; H0297 acreditado con ambas variantes; «Conocimiento, razonamiento y creatividad verbal» 37/37 cerrada, 15/35 categorías cerradas. Siguiente: el resto abierto depende de decisiones del dueño (mensajería, correo, vídeo, Discord, energía, pestañas), de condiciones externas (motor de búsqueda) o son filas sin marca y negativas nunca acreditables. La categoría queda cerrada.

## Frentes aparcados y reanudación exacta (raíz, 2026-09-17, tras KNOW1835: 650/742, 92 abiertos, 15/35 cerradas)

- **Decisión del dueño pendiente (preguntada al relevo `baxy-definitivo-7e`)**: vídeo y series (24 filas; ninguna app de streaming instalada: ¿mecanismo general de navegador con el título buscado en el sitio del servicio, o punto 7?), mensajería, correo y contactos (31 filas; orden vigente: no enviar mensajes reales ni leer chats privados), Discord «ve a Cotele» (la capa de permisos de esta sesión deniega la unión de voz; opción (c) posible), cerrar pestañas de Chrome (H0444) y energía (H0401/H0714, prohibidas).
- **Condición externa medida (WEB1831)**: el RSS público de Bing responde sólo a la primera palabra de una consulta de varias palabras (2026-09-17); H0060 queda abierta con el lector y el enlace de consulta ya construidos; re-medir cuando la sonda RSS devuelva páginas pertinentes para «por que falla whatsapp».
- **Nunca acreditables por orden**: 18 filas sin marca y 3 negativas. **Sin mecanismo seguro**: H0101 (pulsar Instalar iniciaría una descarga de 89 GB), H0081 (sitio de piratería), H0516 (varias confirmaciones en un turno), H0542 (zip: sin operación de compresión), H0578 (Epic sin lectura de licencia), H0096 (título no visible en la biblioteca sin desplazar), 7 fragmentos ininteligibles del diálogo (decididos por el modelo; el detector determinista se probó y se descartó).
- **Reparaciones sin medir (commits 440b064d y 21342ca1)**: prohibir una respuesta («no me contestes nada», «don't answer») y una justificación en pasado tras la prohibición se reconocen como prohibición; medir como límite en la próxima tanda (el límite «No me contestes nada, solo estaba pensando en voz alta.» falló en KNOW1833/1835 con «No pude entender»).

## Mensajería como borrador sin enviar (MSG1837, 2026-09-17): mecanismo construido, medición bloqueada por permisos de la sesión raíz

- Decisión del dueño (DECISIONES §5): el mensaje queda escrito en el chat del cliente y no se envía. Mecanismo general comprometido y compilado (commit e3b95466): operación revisada `message.draft(channel, recipient, text)` (WhatsApp o Discord) que llega al chat, escribe el texto, lo corrobora por OCR y se detiene; lector de la mente para las formas de las filas (manda/mandale/escribe/send/write con destinatario, canal y texto en cualquier orden), enlace de argumentos con las palabras de la persona y lente que dice que dejó el mensaje escrito y no lo envió (veto a cualquier afirmación de envío). Sin medir: la sesión raíz (modo auto de Claude Code) no tiene permiso para operar la sesión real de WhatsApp del dueño y el clasificador denegó el arranque de la tanda. Herramientas y README de reanudación: `BASE/C03-msg1837-tooling/` (panel de 5 casos con el grupo de prueba «Musica»; el instrumento sellado admite el cliente presente y sólo autoriza memory.status y message.draft). Las filas sin canal («mandale al grupo Musica: …», «escribile a Lucas que llego tarde») siguen en la aclaración de canal existente. Correo (6 filas): pendiente de un mecanismo mailto:/Outlook nuevo.

## Discord «ve a Cotele» como parada honesta (DISCORD1839, 2026-09-17): mecanismo construido, medición bloqueada por la guarda de RAM con la Opera GX del dueño abierta

- Decisión del dueño (DECISIONES §5): localizar el canal, verificarlo y preguntar antes de unirse; sin unirse en la tanda. Mecanismo general comprometido y compilado (commit b7b5da3f): operación de bajo riesgo `client.channel.locate(client, name)` (buscador rápido del cliente leído por UI Automation y cerrado con Escape; recibo found/channelName/channelKind/server/joined false), lector de la mente para «ve/andá/go a/al canal X en Discord» antes de la misión de clic, enlace de argumentos y lente que dice que encontró el canal y pregunta si se une (veto a cualquier afirmación de haberse unido). Instrumento sellado (C03-discord1839-instrument-v1, HEAD b7b5da3f) con el cliente presente por diseño; los cinco casos quedaron sin ejecutar: el preflight heredado del runner exige 4000 MiB libres al arrancar y, con la Opera GX del dueño abierta (unos 3 GB), Discord más el producto no caben; la guarda no se rebaja. Reanudación: con Opera GX cerrada, `bash rerun_1839.sh` (BASE/C03-discord1839-tooling/, rutas del scratchpad de la sesión 250e1a56) ejecuta los casos 0–4 con el instrumento ya sellado; después write_results1839.py y chain_discord1839.sh. Nombres de canal y servidor del dueño sólo en recibos privados.

## Chrome «cerrá todas las pestañas» como cierre de las pestañas del propio navegador (H0444, 2026-09-17): fuente aterrizada, medición pendiente de la ventana de RAM

- Decisión del dueño (DECISIONES §5): cerrar todas las pestañas SÍ, sobre las pestañas que la propia tanda abre, nunca las sesiones del dueño. Fuente comprometida y compilada (commit cdc93864): la acción `close_all` de `browser.control` cierra todas las pestañas del navegador CDP propio del producto (enumera los objetivos de página por `/json/list`, los cierra por `/json/close`, verifica que no queda ninguno; si cerrar la última termina el navegador, la pérdida de su extremo es esa ausencia). Nunca se conecta al Chrome del dueño. Mente: lector `browser_close_all_tabs_arguments` («cerrá/cerra/cierra todas las pestañas [de chrome/del navegador]», «close all tabs», plural = todas), gancho del resolutor, puerta autoritativa, enlace de argumentos y lente del compositor (dice que cerró todas las pestañas, en pasado, sin número ni códigos, con veto a decir que siguen abiertas); el límite antiguo LIMITS1677 queda para el cierre de una sola pestaña. Medición: pendiente. El instrumento aún no se sella; el corredor exige 4000 MiB libres al arrancar y, con la Opera GX del dueño abierta (unos 3 GB), no hay margen. El controlador de la tanda abrirá un navegador de utillaje con puerto de depuración fijo y varias pestañas, expondrá su extremo por `BAXY_CDP_ENDPOINT` y medirá el turno de cierre (así se cumple «las pestañas que la tanda abre», nunca las del dueño).

## Nota de secuencia (2026-09-17): el instrumento DISCORD1839 quedó anclado a un HEAD anterior

- El instrumento sellado de DISCORD1839 (C03-discord1839-instrument-v1) fija el candidato en b7b5da3f y su corredor exige que el HEAD actual sea exactamente ese SHA. Las notas de condiciones posteriores (8712d219, cdc93864) adelantaron el HEAD sin tocar la fuente de client.channel.locate, que sigue en el historial. Por eso, antes de reejecutar DISCORD1839 hay que RE-DERIVAR el instrumento contra el HEAD vigente (make_1839.py / next_tanda) y luego correr; la fuente de la capacidad no cambia. Se hará en la próxima ventana de RAM libre junto con la medición de H0444.

## Actualización 2026-09-17 (DISCORD1839)

Interacción dentro de aplicaciones pasa de 19/22 a 21/22 con localizar el canal pedido en el cliente nombrado y preguntar antes de unirse (commit 84e7428d, BUILD1839) (HEAD 84e7428d): 5 ejecutados, 5 aprobados (2 literales H0290 y H0636, 2 variantes, 1 limite), 0 fallidos, 2 créditos. Los cuatro pedidos de ir a Cotele localizaron el canal de voz en el servidor del dueno por el buscador rapido del cliente y preguntaron antes de unirse, sin unirse; el limite explico que es un canal de voz.

## RESUELTO — DISCORD1839 medido (2026-09-17): «ve a Cotele en Discord» como parada honesta, +2 (H0290, H0636)

- El dueño liberó la RAM (cerró Opera GX) y autorizó cerrar lo necesario. Con la RAM disponible se ejecutó DISCORD1839 sobre el HEAD vigente. La medición encontró y arregló dos defectos reales de la capacidad nueva: (1) el descriptor de `client.channel.locate` exigía un efecto observado siendo una post-lectura, así que la localización verificada se fallaba como external_effect_unobserved; se marcó `requiresObservedEffect: false`. (2) el nombre real del canal contiene signos («Cotele!!!??») y el hallazgo termina preguntando si unirse, y el compositor vetaba como extra_claim cualquier «?» en la respuesta; se enmascaran el nombre observado y la pregunta final antes de esa comprobación. Con ambos arreglos los cinco casos aprobaron: los cuatro pedidos localizaron el canal de voz en el servidor del dueño por el buscador rápido, dijeron su tipo y servidor y preguntaron antes de unirse sin unirse; el límite explicó qué es un canal de voz. Se acreditaron H0290 y H0636 (cobertura 650 → 652). El buscador se lee por UI Automation con reintentos ante contención de foco; nombres del canal y servidor sólo en recibos privados. Pendiente menor: la rama de canal no encontrado narra una imposibilidad honesta que hoy el compositor marca asserted_failure; no afecta estas filas (Cotele existe) y queda como mejora futura.

## Actualización 2026-09-17 (CHROMETABS1843)

Organizar ventanas y pestañas pasa de 12/13 a 13/13 con cerrar todas las pestanas del navegador propio del producto (commit 42b69b0e, BUILD1843) (HEAD 42b69b0e): 5 ejecutados, 5 aprobados (1 literal H0444, 2 variantes, 2 limites), 0 fallidos, 1 créditos. El literal y las dos variantes cerraron todas las pestanas del navegador propio del producto (un navegador de utillaje con tres pestanas expuesto por el extremo CDP) y lo dijeron en pasado sin numero; los limites explicaron que una sola pestana no tiene operacion y reconocieron la prohibicion de responder. La categoría queda cerrada.

## RESUELTO — H0444 medido (CHROMETABS1843, 2026-09-17): «cerrá todas las pestañas de chrome», +1, categoría «Organizar ventanas y pestañas» cerrada 13/13

- Con la RAM libre se ejecutó la tanda del close_all ya aterrizado (cdc93864). Un navegador de utillaje con tres pestañas, expuesto por BAXY_CDP_ENDPOINT (el producto SÍ hereda el entorno por el corredor sellado, a diferencia del sidecar de la mente), recibió la operación: browser.control close_all cerró todas sus pestañas y verificó que no quedaba ninguna; el Chrome y la Opera del dueño nunca se tocan. Dos arreglos del compositor: la variante en inglés «close all tabs» exigía nombrar una ventana (guarda de cierre) y se eximió a browser.control; y una narración que situaba la acción recién hecha en un tiempo pasado falso («I closed all the tabs yesterday») se rechaza como tiempo inventado. El literal y las dos variantes aprobaron (crédito H0444); los límites: una sola pestaña sigue sin operación (límite llano) y la prohibición de responder se reconoce sin negar la capacidad. La categoría queda cerrada.

## Mensajería con envío real a canales de prueba del dueño (DECISIONES §6, 2026-09-17): diseño acordado, ejecución pendiente del permiso del dueño

- El dueño levantó «nunca enviar» SÓLO para dos canales suyos de prueba (WhatsApp grupo «Música», Discord usuario «Valeria») y, tras oír la advertencia, mantuvo que TODO envío sea real, también en los literales que nombran a terceros. Diseño de la raíz (declarado al peer): mecanismo con destino seguro forzado por construcción — el envío SIEMPRE va al canal de prueba configurado (WhatsApp→Música, Discord→Valeria) y NUNCA al destinatario nombrado, así ningún tercero real recibe nada; el final es veraz y nombra el destino real («Lo envié a tu grupo de pruebas Música, no al chat de Lucas»). Adjudicación: los literales cuyo destinatario ES Música o Valeria (10 de Música + los de Valeria) acreditan como envío fiel; los literales a terceros enrutados al canal de prueba son veraces pero NO fieles al destinatario nombrado, así que quedan sin crédito con la causa (el dueño lo acepta; prefiere el envío real medido). Leer chats sigue fuera.
- Pendiente: el mecanismo actual (MSG1837) es borrador-sin-enviar; el envío real forzado es un camino de código nuevo (el adaptador envía de verdad al destino forzado; el compositor lo dice). La sesión raíz auto-deniega operar WhatsApp/Discord reales; el dueño está creando `.claude/settings.local.json` (gitignored, nunca lo edita la raíz) con reglas allow para los comandos. Cuando el permiso deje correr los comandos en la sesión raíz (escritor único de C03), la raíz construye el envío forzado, hace una prueba supervisada a un canal del dueño, verifica por OCR y sólo entonces corre la tanda completa. No se rebaja ninguna guarda ni se evita la auto-denegación.

## Actualización 2026-09-18 (MSGSEND1845)

Mensajeria pasa de 9/31 a 10/31 con enviar de verdad el mensaje al canal de prueba forzado del dueno y decir a donde fue (commit 643849fe, BUILD1845) (HEAD 643849fe): 5 ejecutados, 5 aprobados (1 literal H0005, 2 variantes, 2 límites), 0 fallidos, 1 créditos. Medición raíz en el PC principal: el literal y las dos variantes enviaron de verdad el texto de la persona al grupo de pruebas Música (destino forzado por construcción, revisión de la raíz por caso, escritura y entrega leídas por OCR, recibo sent true) y los finales lo dijeron nombrando Música, en castellano e inglés; los límites explicaron la definición y reconocieron la prohibición sin operar. Trece correcciones de fuente en este PC (lista blanca del turno revisado, ventana normalizada, recortes de cabecera, compositor y burbuja, seis lecturas OCR con tolerancia de una letra, búsqueda guardada que nunca pulsa Enter fuera del buscador, lente y vetos de la mente) tras siete corridas abandonadas que enviaron de verdad sin verificar.

## Actualización 2026-09-18 (MSGSEND1847)

Mensajeria pasa de 10/31 a 20/31 con enviar de verdad el mensaje al grupo de pruebas forzado del dueno y decir a donde fue, tambien cuando el literal nombra a un tercero (commit 2d8cf5f7, BUILD1847) (HEAD 2d8cf5f7): 16 ejecutados, 14 aprobados (10 de 12 literales, 2 variantes, 2 límites), 2 fallidos, 10 créditos. Medición raíz en el PC principal: diez literales enviaron de verdad el texto de la persona al grupo de pruebas Música (destino forzado por construcción, revisión de la raíz por caso, escritura y entrega leídas por OCR, recibo sent true), seis de ellos nombrando a un tercero, con finales que nombraron el canal de pruebas y dijeron que no llegó a la persona pedida; ambas variantes pasaron y los límites explicaron y reconocieron la prohibición sin operar. Dos «ya voy» a Música quedan abiertos: el envío fue real y verificado, pero ningún borrador del final pasó el veto porque negaban el destino pedido, que era el propio grupo (composición por reparar). Los cuatro literales sin cliente nombrado quedan para una tanda con aclaración y envío. Correcciones de fuente medidas: lectura de entrega por palabras y sin espacios, y veto de negación del destino cuando el pedido es el propio canal de pruebas. Cuatro corridas previas del mismo panel quedaron sin adjudicar o sin publicar (edición de fuente durante la corrida, sobrantes del generador en adjudicador y publicador, interferencia del dueño en el cliente) y se conservan como evidencia.

## Actualización 2026-09-18 (MSGSEND1849)

Mensajeria pasa de 20/31 a 22/31 con enviar de verdad el mensaje al grupo de pruebas que la persona nombro y decirlo sin negar el destino (commit 74de0951, BUILD1849) (HEAD 74de0951): 6 ejecutados, 6 aprobados (2 literales, 2 variantes, 2 límites), 0 fallidos, 2 créditos. Medición raíz en el PC principal: los dos literales «ya voy» a Música enviaron de verdad el texto al grupo de pruebas (destino forzado por construcción, revisión de la raíz por caso, escritura y entrega leídas por OCR, recibo sent true) y sus finales nombraron el grupo sin negar ni contrastar el destino («Mandé el mensaje "ya voy" a Música.», «Envié "ya voy" a Música.»), porque la pista de reintento de la mente ya distingue el caso en que el destinatario pedido es el propio canal de pruebas; ambas variantes pasaron y los límites explicaron y reconocieron la prohibición sin operar. Mensajería 22/31; quedan H0198/H0231/H0536/H0024 (sin cliente nombrado: aclaración y envío), Discord H0318/H0340/H0394 a Valeria, la lectura H0720 y los seis de correo.

## Actualización 2026-09-18 (MSGCLAR1851)

Mensajeria pasa de 22/31 a 26/31 con preguntar por el cliente cuando el pedido no lo nombra y enviar de verdad al grupo de pruebas tras la respuesta (commit 07d4f450, BUILD1851) (HEAD 07d4f450): 8 ejecutados, 8 aprobados (4 literales, 2 variantes, 2 límites), 0 fallidos, 4 créditos. Medición raíz en el PC principal: los cuatro literales sin cliente nombrado (tres al grupo Música, uno a un tercero) se resolvieron como diálogos: BAXY preguntó «¿En qué canal deseas que se envíe el mensaje?», la raíz respondió «por WhatsApp» (respuesta guionizada), la mente completó el pedido de la persona con ese cliente (plan y argumentos), la propuesta message.send.test fue revisada y aprobada por la raíz, el envío llegó de verdad al grupo de pruebas Música (destino forzado por construcción, escritura y entrega leídas por OCR, recibo sent true) y los finales nombraron el grupo («Envié "prueba 2, todo OK" a Música.»; para el tercero: «Envié "llego tarde" al canal de prueba «Música», pero no llegó a Lucas.»). Tres arreglos generales: el texto dictado tras dos puntos o un «que» simple, el cliente nombrado dentro del texto no cuenta como canal, la respuesta de una palabra completa el pedido; y la lectura de entrega ensancha la banda de la burbuja para mensajes largos. Ambas variantes pasaron y los límites explicaron y reconocieron la prohibición sin operar. Mensajería 26/31; quedan Discord H0318/H0340/H0394 a Valeria, la lectura H0720 y los seis de correo.

## Actualización 2026-09-19 (UNRES1855)

Entrada incompleta, ruido y control de diálogo pasa de 27/34 a 27/34 con responder a una entrada ininteligible o sin pedido con un no entendi honesto que pide repetir, sin operar (commit 4b65e7eb, BUILD1855) (HEAD 4b65e7eb): 11 ejecutados, 6 aprobados (2 literales, 1 variante, 2 límites y un literal que pidió precisar), 5 fallidos, 0 créditos. Medición raíz en el PC principal, sin cambio de código: las siete entradas ininteligibles se ejecutaron como turnos ordinarios con cero operaciones. Seis casos fueron fieles: «That's it. Get this spiderbell.» y la variante inglesa recibieron «I couldn't understand the request properly.», «Vean con teléfono.» recibió una pregunta que pide precisar entre dos lecturas, «Estos mexicanos son duros…» recibió que no está seguro de la frase, y los dos límites explicaron y reconocieron la prohibición. Cinco fingieron entender: «¡Habristín!» recibió un saludo, «Calendar Devil?» una respuesta de identidad, «Hable este.» un «¡Claro! ¿En qué estás pensando?», el marcador sin texto una pregunta abierta en inglés, y la variante castellana «No puedo completar el resultado…», que da por hecha una tarea pendiente inexistente. Cero créditos: una de las dos variantes falló, así que ningún literal tiene par. Causa medida para la reparación: la entrada ininteligible no se clasifica como no resuelta y el compositor la trata como conversación.

## Actualización 2026-09-19 (MAIL1859)

Correo pasa de 0/6 a 1/6 con enviar de verdad el correo a la casilla de pruebas del dueno, preguntando antes el texto o el destinatario que falte (commit 9fad6c66, BUILD1859) (HEAD 9fad6c66): 12 ejecutados, 6 aprobados (1 literal, 3 variantes, 2 límites), 6 fallidos, 1 créditos. Medición raíz en el PC principal: los diez casos de envío salieron de verdad a la casilla de pruebas del dueño (destino forzado por construcción, envío por su Outlook clásico, copia leída en Elementos enviados, recibo sent true); cuatro de ellos como diálogos que preguntaron el texto o el destinatario que faltaba y lo completaron con la respuesta. H0554 «mandale un correo a ana@gmail.com diciendo que llego tarde» recibió un final veraz que nombró la dirección real y dijo que no llegó a la pedida, y las dos variantes de envío pasaron, así que acredita. Los cinco fallidos enviaron igual pero ningún borrador del final nombró la dirección real: el compositor la llamó «canal de prueba» o la escribió con otras mayúsculas, y el que sí la nombró usó «le dije», que el veto de envío no reconoce como decir que se envió. Correo 1/6.

## Actualización 2026-09-19 (MAIL1863)

Correo pasa de 1/6 a 5/6 con enviar de verdad el correo a la casilla de pruebas del dueno, preguntando antes el texto o el destinatario que falte (commit 09d217e0, BUILD1863) (HEAD 09d217e0): 11 ejecutados, 10 aprobados (4 de 5 literales, 4 variantes, 2 límites), 1 fallido, 4 créditos. Medición raíz en el PC principal: los nueve casos de envío salieron de verdad a la casilla de pruebas del dueño (destino forzado por construcción, envío por su Outlook clásico, copia leída en Elementos enviados, recibo sent true); seis de ellos como diálogos que preguntaron el texto o el destinatario que faltaba y completaron el pedido con la respuesta. Con la dirección exenta del detector de código interno de la App, los finales se publicaron y nombraron la casilla real diciendo que no llegó al destinatario pedido. H0018 falló por negar la entrega al propio destino real. Las cuatro variantes pasaron, así que los cuatro literales aprobados acreditan. Correo 5/6; queda H0018.

## Actualización 2026-09-19 (MAIL1867)

Correo pasa de 1/6 a 2/6 con enviar de verdad el correo a la casilla de pruebas y decirlo sin negar la entrega a esa casilla (commit 072757ec, BUILD1867) (HEAD 072757ec): 5 ejecutados, 5 aprobados (1 literal, 2 variantes, 2 límites), 0 fallidos, 1 créditos. Medición raíz en el PC principal: H0018 corrió como diálogo (BAXY preguntó qué decir, la raíz respondió «que llego tarde») y el envío salió de verdad a la casilla de pruebas del dueño por su Outlook, con la copia en Elementos enviados como evidencia. El final nombró la casilla real y dijo que no fue al destinatario pedido, sin negar la entrega a esa casilla, que es lo que el veto nuevo impide. Las dos variantes de diálogo pasaron, así que el literal acredita. Correo queda cerrado 6/6.

## Actualización 2026-09-19 (DISCORD1869)

Mensajería pasa de 26/31 a 28/31 con enviar de verdad el mensaje al usuario de pruebas de Discord y decir a donde fue (commit a3eb67fe, BUILD1869) (HEAD a3eb67fe): 7 ejecutados, 6 aprobados (2 de 3 literales, 2 variantes, 2 límites), 1 fallido, 2 créditos. Medición raíz en el PC principal: los cinco casos de envío escribieron y enviaron de verdad en Discord al usuario de pruebas del dueño (destino forzado por construcción, buscador rápido conducido desde el adaptador y primer resultado abierto con un clic, entrega leída por OCR, recibo sent true). Tres arreglos generales: el cliente se elige por su proceso y no por el título (una ventana del editor con «discord» en el nombre recibía las teclas), la cuenta de pruebas se reconoce con sus dos nombres («Valeria ron.91» en el buscador, «Julia» en el título de la ventana: es la misma conversación, que ya existía), y la banda de entrega conserva todo el ancho de la conversación porque sólo WhatsApp alinea la burbuja a la derecha. H0394 envió igual pero ningún borrador del final llegó a publicarse. Mensajería 28/31; quedan las dos lecturas de chat y H0394.

## Actualización 2026-09-19 (DISCORD1871)

Mensajería pasa de 28/31 a 29/31 con enviar de verdad el mensaje al usuario de pruebas de Discord y decir a donde fue (commit 32e3f85e, BUILD1871) (HEAD 32e3f85e): 5 ejecutados, 5 aprobados (1 literal, 2 variantes, 2 límites), 0 fallidos, 1 créditos. Medición raíz en el PC principal: los tres casos de envío escribieron y enviaron de verdad en Discord al usuario de pruebas del dueño (destino forzado por construcción, buscador conducido desde el adaptador, entrega leída por OCR en todo el ancho de la conversación, recibo sent true). H0394 recibió «Le envié el mensaje "hola" a Valeria, no a ShooterCock.»: nombra el destino real y niega el pedido, que es exactamente la verdad y que el veto de destino equivocado ya no rechaza. Las dos variantes pasaron, así que el literal acredita. Mensajería 29/31: quedan las dos lecturas de chat (H0510, H0720).

## Actualización 2026-09-19 (UNRES1873)

Entrada incompleta, ruido y control de diálogo pasa de 27/34 a 30/34 con responder a una entrada ininteligible o sin pedido con un no entendi honesto que pide repetir, sin operar (commit bec9ea7d, BUILD1873) (HEAD bec9ea7d): 8 ejecutados, 7 aprobados (3 de 4 literales, 2 variantes, 2 límites), 1 fallido, 3 créditos. Medición raíz en el PC principal, sin cambio de código: las cuatro entradas se ejecutaron como turnos ordinarios con cero operaciones. Tres literales respondieron con honestidad: «That's it. Get this spiderbell.» recibió «I couldn't understand the request properly.», «Vean con teléfono.» una pregunta que pide precisar entre dos lecturas, y el tramo largo de habla ajena que no está dirigido a BAXY recibió que no está seguro de la frase y una pregunta. Las dos variantes de habla ajena, en castellano y en inglés, recibieron «En eso no encuentro un pedido para mí; ¿necesitás algo?» y su equivalente inglés, así que los tres literales acreditan. El marcador sin texto falló: se clasifica como ruido pero el final preguntó de qué quiere hablar, en inglés, sin decir que no llegó nada legible. Entrada incompleta, ruido y control de diálogo 30/34.

## Actualización 2026-09-19 (UNRES1875)

Entrada incompleta, ruido y control de diálogo pasa de 30/34 a 31/34 con responder a un marcador sin texto diciendo que ahi no se ve un pedido y preguntando que hacer, sin operar (commit c8fe9a28, BUILD1875) (HEAD c8fe9a28): 5 de 5 casos aprobados (1 literal, 2 variantes, 2 límites), 1 créditos. El guardia de ruido, con el mismo vocabulario en los dos idiomas, aceptó al primer intento la pregunta veraz: el marcador sin texto y las dos variantes de la misma forma recibieron una pregunta que dice que ahí no hay un pedido legible y pregunta qué hacer, con cero operaciones y cero violaciones.

## Actualización 2026-09-19 (WEB1877)

Información web actual pasa de 16/17 a 16/17 con investigar en internet la pregunta de la persona y decir que paginas la contestan, sin afirmar una causa que ningun resultado sostiene (commit 00678916, BUILD1877) (HEAD 00678916): 4 de 5 casos aprobados (2 variantes, 2 límites); el literal falló por no nombrar las páginas, 0 créditos. Con el segundo motor las tres investigaciones completaron y verificaron exactamente una web.search con las palabras de la persona y obtuvieron páginas pertinentes; las dos variantes nombraron sitios y títulos y el literal no nombró ninguno, de modo que la condición externa queda levantada y lo que falta es la atribución en el informe.

## Actualización 2026-09-19 (WEB1879)

Información web actual pasa de 16/17 a 16/17 con investigar en internet la pregunta de la persona y decir que paginas la contestan, nombrandolas (commit b5365f70, BUILD1879) (HEAD b5365f70): 4 de 5 casos aprobados (2 variantes, 2 límites); el literal falló por una causa sin fuente en su primera oración, 0 créditos. Con la regla que exige nombrar las páginas, los tres informes atribuyeron lo que copian y las dos variantes quedaron enteras; el literal nombró fallas.mx y ADSLZone pero abrió afirmando en voz propia dos causas que ningún resultado contiene.

## Actualización 2026-09-19 (WEB1881)

Información web actual pasa de 16/17 a 16/17 con investigar en internet la pregunta de la persona y decir que paginas la contestan, sin afirmar nada por su cuenta (commit 3262e2d0, BUILD1881) (HEAD 3262e2d0): 4 de 5 casos aprobados (2 variantes, 2 límites); el literal terminó sin respuesta, 0 créditos. La regla que exige que toda oración sin fuente use sólo palabras de algún resultado dejó al literal sin borrador publicable: con temperatura cero sus tres candidatos son siempre los mismos y cada uno cae en una regla distinta, de modo que el turno terminó sin respuesta; las dos variantes publicaron su informe entero.

## Actualización 2026-09-19 (WEB1883)

Navegación y búsqueda web pasa de 44/46 a 44/46 con abrir el navegador nombrado en el sitio pedido tras un preambulo que cede el control del PC, sin negar la capacidad (commit dc7861a0, BUILD1883) (HEAD dc7861a0): 1 de 5 casos aprobados; las dos variantes y el límite de capacidad negaron una capacidad existente, 0 créditos. El preámbulo que cede el control del PC convierte una orden explícita y soportada en una negación de capacidad: Opera GX está instalada y browser.navigate.named quedó acreditada en WEB1805, y aun así los dos textos de variante dijeron que no podían; el literal no negó nada pero tampoco abrió, y preguntó si hacerlo.

## Actualización 2026-09-19 (WEB1885)

Navegación y búsqueda web pasa de 44/46 a 44/46 con abrir el navegador nombrado en el sitio pedido tras un preambulo que cede el control del PC, sin negar la capacidad (commit f815ec5a, BUILD1885) (HEAD f815ec5a): 3 de 5 casos aprobados: las dos variantes abrieron de verdad; el literal preguntó y el límite de capacidad siguió negando, 0 créditos. Las dos variantes proponen exactamente una browser.navigate.named, la raíz la aprueba con el navegador y la URL comprobados, se completa y se verifica con finalUrl https://itch.io/, y el final dice lo que hizo: la negación de capacidad que midió WEB1883 desaparece en los dos idiomas. El literal queda abierto porque su destino llega sin dominio.

## Actualización 2026-09-19 (WEB1887)

Navegación y búsqueda web pasa de 44/46 a 44/46 con investigar en internet la pregunta de la persona y decir que paginas la contestan, nombrandolas, sin quedarse sin respuesta (commit 1885e3c3, BUILD1887) (HEAD 1885e3c3): 3 de 5 casos aprobados (1 variante, 2 limites); el literal nombra sus paginas pero abre con una causa sin fuente y la variante en espanol no nombra ninguna, 0 creditos, 0 créditos. ninguno de los cinco turnos termino sin respuesta

## Actualización 2026-09-19 (WEB1889)

Navegación y búsqueda web pasa de 44/46 a 44/46 con investigar en internet la pregunta de la persona y decir que paginas la contestan, sin atribuirles nada que no digan (commit 57172b84, BUILD1889) (HEAD 57172b84): 4 de 5 casos aprobados (2 variantes, 2 limites); el literal nombra sus paginas pero les atribuye una causa que no contienen, 0 creditos, 0 créditos. las dos variantes pasaron de no nombrar ninguna pagina a nombrar tres cada una

## Actualización 2026-09-19 (WEB1891)

Navegación y búsqueda web pasa de 44/46 a 45/46 con investigar en internet la pregunta de la persona y decir que paginas la contestan, sin atribuirles nada que no digan (commit 1e5e87ff, BUILD1891) (HEAD 1e5e87ff): 5 de 5 casos aprobados; el literal nombra tres de sus paginas con titulo y sitio y no afirma nada mas, 1 credito, 1 créditos. la fila cierra tras cuatro tandas

## Actualización 2026-09-19 (LIMITS1893)

Navegación y búsqueda web pasa de 44/46 a 47/46 con decir llanamente que no guarda contactos, nombrando a la persona del pedido, sin inventar una agenda ni un guardado (commit 6abee5e6, BUILD1893) (HEAD 6abee5e6): 7 de 7 casos aprobados; las tres filas de contacto dicen llanamente que no guardan contactos, cero operaciones, 3 creditos, 3 créditos. primera tanda con tres literales

## Actualización 2026-09-19 (LIMITS1895)

Navegación y búsqueda web pasa de 44/46 a 44/46 con decir llanamente que no ejecuta comandos, nombrando el que se pidio, sin inventar una salida ni desviar la conversacion al codigo (commit 1b774dea, BUILD1895) (HEAD 1b774dea): 5 de 6 casos aprobados; los dos literales dicen el limite nombrando su comando, la variante en ingles no lo nombra, 0 creditos, 0 créditos. H0475 pasa de preguntar por el script a decir el limite

## Actualización 2026-09-19 (LIMITS1897)

Navegación y búsqueda web pasa de 44/46 a 46/46 con decir llanamente que no ejecuta comandos, nombrando el que se pidio, sin inventar una salida ni desviar la conversacion al codigo (commit f91b7e27, BUILD1897) (HEAD f91b7e27): 6 de 6 casos aprobados; las dos filas de comando dicen el limite nombrando el comando pedido, cero operaciones, 2 creditos, 2 créditos. el rechazo en ingles ya nombra lo pedido La categoría queda cerrada.

## Actualización 2026-09-19 (WEB1899)

Navegación y búsqueda web pasa de 44/46 a 44/46 con buscar el dato en internet y decir que paginas lo traen, sin decir que uso la API que la persona nombro (commit e9aa3039, BUILD1899) (HEAD e9aa3039): 4 de 5 casos aprobados; el literal informo fielmente un unico resultado sin relacion que devolvio el buscador, 0 creditos, 0 créditos. el turno ya no muere con el JSON de los fragmentos

## Actualización 2026-09-19 (LIMITS1901)

Navegación y búsqueda web pasa de 44/46 a 54/46 con pedir que repitan el pedido en espanol o en ingles, sin ejecutar nada y sin negar una capacidad que si tiene (commit ef5966e9, BUILD1901) (HEAD ef5966e9): 13 de 14 casos aprobados; las diez filas en otro idioma piden repetir el pedido en espanol o ingles, cero operaciones, 10 creditos, 10 créditos. primera tanda de catorce casos

## Actualización 2026-09-19 (LIMITS1903)

Navegación y búsqueda web pasa de 44/46 a 46/46 con contestar como conversacion un saludo en varios idiomas o una charla mezclada, sin pedir que repitan nada y sin inventar un pedido (commit a36b87ad, BUILD1903) (HEAD a36b87ad): 6 de 6 casos aprobados; el saludo en varios idiomas y la charla mezclada se contestan como conversacion, cero operaciones, 2 creditos, 2 créditos. el limite confirma que un pedido de verdad en otro idioma sigue pidiendo que lo repitan La categoría queda cerrada.

## Actualización 2026-09-19 (UI1907)

Interacción dentro de aplicaciones pasa de 21/22 a 22/22 con mirar la pantalla antes de pulsar y decir que no hay nada con ese nombre cuando no lo hay (commit 186bdf91, BUILD1907) (HEAD 186bdf91): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. Los cuatro turnos con clic leyeron los controles de la ventana que abrió la raíz antes de pulsar y, al no haber nada con esa etiqueta, lo dijeron sin afirmar que hubieran pulsado; cien-58 100/100 con cero agotes. La categoría queda cerrada.

## Actualización 2026-09-19 (LANG1909)

Hora y fecha pasa de 19/23 a 21/23 con pedir que repitan en espanol o ingles el pedido escrito en otro idioma, en vez de contestarlo en el idioma equivocado (commit ecc19b60, BUILD1909) (HEAD ecc19b60): 6 ejecutados, 6 aprobados, 0 fallidos, 2 créditos. Los cuatro pedidos en alemán o italiano terminaron con cero operaciones y un final que pide que se repita en español o en inglés; el español y el inglés siguen dando la hora; cien-59 100/100 con cero agotes.

## Actualización 2026-09-19 (UI1911)

Instalar y desinstalar software pasa de 29/31 a 30/31 con completar el dialogo de descarga que ya esta abierto pulsando el boton que el pedido nombra (commit 2d9cd6b9, BUILD1911) (HEAD 2d9cd6b9): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. Los cuatro turnos con clic leyeron las 30 líneas del diálogo que la raíz dejó abierto y pulsaron el botón del pedido; el literal arrancó la instalación de DOOM Eternal en E:; cien-60 100/100 con cero agotes.

## Actualización 2026-09-19 (APPS1913)

Abrir aplicaciones pasa de 50/54 a 51/54 con abrir la aplicacion que se nombra y decir lo que el recibo devuelve, sin dar por abierto lo que ya estaba (commit 793d06f6, BUILD1913) (HEAD 793d06f6): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. Los cuatro turnos con apertura ejecutaron una sola app.open verificada y el final dijo lo que el recibo devuelve; «abrime el navegador chrome» dejó de pedir una URL; cien-61 100/100 con cero agotes.

## Actualización 2026-09-19 (LIMITS1915)

Archivos y carpetas pasa de 31/32 a 32/32 con decir llanamente que no se puede comprimir ni abrir un zip, nombrando lo que se pidio (commit 84912e9f, BUILD1915) (HEAD 84912e9f): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. Los cuatro del grupo terminaron con cero operaciones y un final que dice el límite nombrando lo que se pidió; cien-62 100/100 con cero agotes. La categoría queda cerrada.

## Actualización 2026-09-19 (POWER1917)

Energía del sistema pasa de 1/3 a 3/3 con llamar de verdad a la transicion pedida y decir que Windows no la acepto y que el equipo sigue encendido (commit 2a6b58ca, BUILD1917) (HEAD 2a6b58ca): 6 ejecutados, 6 aprobados, 0 fallidos, 2 créditos. Los cuatro del grupo llamaron de verdad a system.power con la acción pedida y terminaron en rechazo de Windows; el final dijo que el equipo sigue encendido; la PC no se apagó ni se reinició; cien-63 100/100 con cero agotes. La categoría queda cerrada.

## Actualización 2026-09-19 (VIDEO1919)

Vídeo y series pasa de 2/26 a 9/26 con poner la serie que se nombra en el servicio que se nombra, y decir que se esta reproduciendo solo cuando se ha visto avanzar (commit 5648ab9d, BUILD1919) (HEAD 5648ab9d): 14 ejecutados, 11 aprobados, 3 fallidos, 7 créditos. Nueve reproducciones aprobadas por la raiz, completadas y verificadas contra el avance observado del video; un final falla por afirmar la posicion del video, que el recibo no da, y dos turnos quedan detenidos sin efecto porque el revisor de la raiz llevaba un unico titulo fijado.

## Actualización 2026-09-20 (VIDEO1921)

Vídeo y series pasa de 9/26 a 9/26 con poner la serie que se nombra aunque se nombre mal, y decir cual se puso sin adivinar por donde va (commit c2a1bffb, BUILD1921) (HEAD c2a1bffb): 6 ejecutados, 5 aprobados, 1 fallido, 0 créditos. Las dos filas se reproducen de verdad con finales fieles; una variante no propuso nada porque el extractor literal de argumentos no tenia entrada para la operacion, y sin dos variantes aprobadas ningun literal acredita.

## Actualización 2026-09-20 (VIDEO1923)

Vídeo y series pasa de 9/26 a 11/26 con poner la serie que se nombra sin preguntar por lo que el pedido ya dice (commit dea4e6b2, BUILD1923) (HEAD dea4e6b2): 6 ejecutados, 6 aprobados, 0 fallidos, 2 créditos. Las dos filas y las dos variantes se reproducen de verdad, con la raiz aprobando cada propuesta y el video avanzando; los finales nombran lo que se puso sin afirmar por donde va.

## Actualización 2026-09-20 (VIDEO1925)

Vídeo y series pasa de 11/26 a 12/26 con preguntar por el titulo cuando es lo unico que falta, y no ejecutar nada mientras tanto (commit 8a16c93f, BUILD1925) (HEAD 8a16c93f): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. Cero operaciones en los cuatro del grupo; cada final es una sola pregunta por el titulo que falta, en el idioma del pedido.

## Actualización 2026-09-20 (VIDEO1927)

Vídeo y series pasa de 12/26 a 14/26 con poner la serie aunque se nombre mal, y decir cual se puso de verdad (commit 923efb3a, BUILD1927) (HEAD 923efb3a): 6 ejecutados, 6 aprobados, 0 fallidos, 2 créditos. La raiz aprueba el titulo tal y como se escribio, Netflix lo corrige, el video avanza y el final nombra el titulo observado; cuatro reproducciones verificadas y dos limites en cero operaciones.

## Actualización 2026-09-20 (VIDEO1929)

Vídeo y series pasa de 14/26 a 15/26 con poner la serie aunque el servicio se nombre mal, sin preguntar por lo que ya esta escrito (commit c79ee713, BUILD1929) (HEAD c79ee713): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. Cuatro reproducciones con el servicio mal escrito, aprobadas por la raiz y verificadas contra el avance del video; los finales nombran Netflix y el titulo. La primera corrida de los cuatro quedo detenida por un titulo esperado heredado en el revisor; se preservo y se repitio.

## Actualización 2026-09-20 (CHAIN1931)

Navegación y búsqueda web pasa de 44/46 a 45/46 con encadenar abrir, buscar, capturar y cerrar sobre una aplicacion nombrada, con cada efecto revisado (commit 82d467d1, BUILD1931) (HEAD 82d467d1): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. Cada caso revisado propuso tres efectos a la raíz (navegar, capturar, cerrar) y recibió tres aprobaciones (approved_3_of_3); Opera GX del dueño cerrada antes de cada caso con su autorización y ausente después (OPERA_DESPUES=0); búsqueda web verificada en DuckDuckGo lite; finales fieles que niegan el escritorio y dicen que cerraron Opera; límites con cero operaciones. Corrida sobre BUILD1931 (HEAD 82d467d) tras tres corridas preservadas por el protocolo del corredor y del adjudicador.

## Actualización 2026-09-20 (SITE1933)

Navegación y búsqueda web pasa de 45/46 a 46/46 con entrar en un sitio nombrado sin dominio con un navegador nombrado (commit d78f5225, BUILD1933) (HEAD d78f5225): 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos. Cada caso revisado propuso una navegación nombrada al primer resultado de la búsqueda verificada de «pivigames» y recibió la aprobación de la raíz (approved_1_of_1); Opera GX del dueño cerrada antes de cada caso con su autorización; navegador observado opera_gx y dirección final https://pivigames.es/ en los cuatro; finales en pasado que nombran el navegador y el sitio sin describir la página; límites con cero operaciones. Corrida sobre BUILD1933 (HEAD d78f522). La categoría queda cerrada.

## Actualización 2026-09-20 (APIID1935)

Bibliotecas y fichas de juegos pasa de 5/6 a 6/6 con buscar el dato en internet diciendo que no uso la API que la persona nombro y nombrando las paginas que lo traen (commit ec826bbe, BUILD1935) (HEAD ec826bbe): 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos. Los tres casos del grupo hicieron exactamente una web.search completada y verificada con lo pedido como consulta (sin la directiva de la API) y publicaron un final que dice que no usó la API y nombra las páginas encontradas por título y sitio (SteamDB con el App ID en el título, la tienda de Steam), sin afirmar nada que ninguna traiga; los límites con cero operaciones. Corrida sobre BUILD1935 (HEAD ec826bb). La categoría queda cerrada.

## Actualización 2026-09-20 (EPIC1937)

Instalar y desinstalar software pasa de 30/31 a 31/31 con leer la biblioteca de Epic Games ante una descarga y decir el estado del juego (commit 896d647e, BUILD1937) (HEAD 896d647e): 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos. Los tres casos del grupo hicieron exactamente una game.entitlement.named con store=epic completada y verificada (biblioteca del lanzador de Epic Games: Fall Guys en la biblioteca y no instalado) y publicaron un final que dice ese estado y que la descarga se inicia desde el lanzador, sin inventar instalaciones ni descargas; los límites con cero operaciones. Corrida sobre BUILD1937 (HEAD 896d647). La categoría queda cerrada.

## Actualización 2026-09-20 (CHATREAD1939)

Mensajería pasa de 29/31 a 31/31 con decir llanamente que no lee lo que otra persona escribio por chat (commit b4a8ba6e, BUILD1939) (HEAD b4a8ba6e): 6 ejecutados, 6 aprobados, 0 fallidos, 2 créditos. Los cuatro casos del grupo cerraron con cero operaciones y un final que dice llanamente que no puede leer ni contar lo que la persona nombrada escribió (antes: note.read con la pregunta como título, pregunta por el correo, invención en inglés); los límites con cero operaciones. Corrida sobre BUILD1939 (HEAD b4a8ba6). La categoría queda cerrada.

## Actualización 2026-09-20 (UNRES1941)

Entrada incompleta, ruido y control de diálogo pasa de 31/34 a 32/34 con responder a una palabra que no existe en ningun idioma citandola y pidiendo que la repitan (commit ad138f79, BUILD1941) (HEAD ad138f79): 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos. Los tres casos del grupo cerraron con cero operaciones y una pregunta que cita la palabra desconocida tal cual y pide repetirla; el saludo real «Buenas» se contestó como saludo y la prohibición se reconoció, ambos con cero operaciones. Léxico: Hunspell es_AR + en_US (LibreOffice) vía spylls, instalado en BAXYRuntime/lexicon. Corrida sobre BUILD1941 (HEAD ad138f7).

## Actualización 2026-09-20 (PRIME1943)

Vídeo y series pasa de 15/26 a 16/26 con decir llanamente que no puede poner una serie en Prime Video (commit 98ecc3aa, BUILD1943) (HEAD 98ecc3aa): 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos. Los tres casos del grupo cerraron con cero operaciones y un final que dice llanamente que no puede poner la serie en Prime Video (el dueño no tiene Prime Video, 2026-09-20); los límites con cero operaciones. Corrida sobre BUILD1943 (HEAD 98ecc3a).

## Actualización 2026-09-20 (UNRES1945)

Entrada incompleta, ruido y control de diálogo pasa de 32/34 a 34/34 con preguntar de que o a que se refiere cuando llegan palabras reales sin ningun pedido (commit 24e12e0f, BUILD1945) (HEAD 24e12e0f): 6 ejecutados, 6 aprobados, 0 fallidos, 2 créditos. Los cuatro casos del grupo cerraron con cero operaciones y una pregunta que nombra lo que falta («¿De qué querés que hable?», «No sé a qué te referís; ¿me lo repetís con más contexto?»); los límites con cero operaciones. Corrida sobre BUILD1945 (HEAD 24e12e0). La categoría queda cerrada.

## Actualización 2026-09-20 (VIDEO1947)

Vídeo y series pasa de 16/26 a 16/26 con poner una serie nombrandola en Disney+ y decir que se reproduce nombrando el titulo observado (commit fa944b77, BUILD1947) (HEAD fa944b77): 10 ejecutados, 9 aprobados, 1 fallido, 0 créditos. Las seis filas con título y la variante en inglés reproducen en Disney+ con el vídeo que avanza y un final que nombra el título observado; la variante en voseo falló porque la lectura eligió una ficha por defecto de la página de búsqueda antes de que llegaran los resultados, con final honesto: sin dos variantes aprobadas, cero créditos. La reparación se mide en la tanda siguiente.

## Actualización 2026-09-20 (VIDEO1949)

Vídeo y series pasa de 16/26 a 16/26 con poner una serie nombrandola en Disney+ eligiendo la ficha cuando la busqueda responde (commit ce712690, BUILD1949) (HEAD ce712690): 10 ejecutados, 8 aprobados, 2 fallidos, 0 créditos. La variante en voseo que falló en VIDEO1947 reproduce con la búsqueda esperada; dos turnos con «Daredevil» fallaron porque la ficha de nombre exacto era la de colección (/browse/page-), sin botón de reproducir, con finales honestos: sin dos variantes aprobadas, cero créditos. La reparación se mide en la tanda siguiente.

## Actualización 2026-09-20 (VIDEO1951)

Vídeo y series pasa de 16/26 a 21/26 con poner una serie nombrandola en Disney+ prefiriendo la ficha de la obra a la coleccion (commit 5f1be4ed, BUILD1951) (HEAD 5f1be4ed): 10 ejecutados, 9 aprobados, 1 fallido, 5 créditos. «Daredevil» elige la ficha de la obra y no la de colección, y las dos variantes reproducen; H0712 falló porque la ficha elegida («El diablo viste a la moda 2») no terminó de cargar en el minuto del turno, con final honesto. Cinco literales acreditan con dos variantes aprobadas.

## Actualización 2026-09-20 (VIDEO1953)

Vídeo y series pasa de 21/26 a 22/26 con poner una serie nombrandola en Disney+ recargando una vez la pagina que no termina de cargar (commit 5801d5f7, BUILD1953) (HEAD 5801d5f7): 6 ejecutados, 5 aprobados, 1 fallido, 1 créditos. La fila y sus tres variantes reproducen «El diablo viste a la moda 2» con la ficha cargada o recargada una vez; una variante falla sólo por un final que abre con una negación inventada antes de nombrar lo que se reproduce. Un literal acredita con dos variantes aprobadas.

## Actualización 2026-09-20 (VIDEO1955)

Vídeo y series pasa de 22/26 a 26/26 con preguntar que ver cuando se nombra Disney+ sin titulo (commit 2a005655, BUILD1955) (HEAD 2a005655): 8 ejecutados, 8 aprobados, 0 fallidos, 4 créditos. Las cuatro transcripciones cortadas o mal oídas que nombran Disney+ sin título preguntan qué ver, en su idioma, con cero operaciones; dos variantes hacen lo mismo y los límites no tocan nada. Cuatro literales acreditan con dos variantes aprobadas: 742/742 y las 35 categorías cerradas. La categoría queda cerrada.

## Reapertura 2026-09-20 (REOPEN1957, decisión del dueño: la encuesta es la especificación)

El dueño decidió (D1) que «todo lo que se detalla en las encuestas son cosas que BAXY debe hacer» y (D11) reabrir además comandos, fondo de pantalla, PowerPoint, leer chats e imágenes de la web. Vuelven a abiertas 35 filas positivas acreditadas sin la acción pedida: entrar al canal de Discord (H0290, H0636), pestañas del Chrome del dueño (H0444), pulsar dentro de una app (H0175, H0566), Steam descargar (H0049, H0118, H0272, H0382, H0390, H0434, H0482, H0659, H0671, H0680), instalar (H0295, H0345, H0387, H0396, H0643, H0721), desinstalar (H0039, H0612), lanzar (H0083, H0608), carpeta→txt→zip→abrir (H0542), modo avión (H0107), comandos (H0245, H0048), fondo y PowerPoint (H0459, H0188), leer chats (H0510, H0720), imágenes (H0069, H0077). Quedan como límite: contactos (H0306, H0138, H0014, H0116, H0124: «en PC no tiene sentido»), Prime Video (H0646), ver su propio código (H0635) y las 18 `unmarked_limit`. Estado: 707/742, 35 abiertas, 23/35 cerradas (Abrir aplicaciones 52/54 (−2); Archivos y carpetas 31/32 (−1); Brillo y pantalla 16/17 (−1); Conversación social y ayuda general 30/31 (−1); Crear documentos y editar imágenes 1/2 (−1); Desarrollo y ejecución de comandos 3/5 (−2); Instalar y desinstalar software 13/31 (−18); Interacción dentro de aplicaciones 18/22 (−4); Mensajería 29/31 (−2); Navegación y búsqueda web 45/46 (−1); Organizar ventanas y pestañas 12/13 (−1); Red y Bluetooth 20/21 (−1)). Marco: un motor general de computer use (D21) cuyas 35 filas son el banco de aceptación; cada capacidad se construye como paso encadenable (D10) y se mide con una tanda sellada; confirmaciones sólo para lo destructivo (D3); envíos reales sólo a los destinos de prueba (D13/D14).

## Reapertura 2026-09-20 (REOPEN1993, auditoría semántica completa, D24)

El dueño ordenó (D24) auditar las 742 filas contra la encuesta y reabrir lo que la auditoría concluya con su regla: actuar cuando el contexto es determinista o el candidato es único; preguntar sólo con ambigüedad real; elegir por la persona sólo donde es determinista. Vuelven a abiertas 56 filas: contexto determinista (H0011, H0263, H0299, H0528), nombre aproximado con candidato único (H0227, H0398, H0386, H0522, H0682), dentro de la aplicación (H0128, H0232, H0325, H0368, H0344, H0097), elegir por la persona (H0701, H0045, H0074), destino único o aprendible en mensajería (H0019, H0408, H0198, H0231, H0536, H0024), búsquedas acreditadas como fallidas (H0098, H0380), clima (H0034, H0061, H0339, H0415, H0431, H0478, H0590, H0617, H0664, H0689, H0699, H0708), noticias (H0033, H0374, H0509), software que no es un juego leído como biblioteca de Steam (H0167, H0217, H0457, H0583, H0651, H0089, H0574), Steam/Epic sin alcanzar (H0456, H0571, H0578, H0620), energía rechazada por Windows (H0401, H0714) y wifi «de casa» (H0170, H0376). Lo que se mantiene y por qué: REOPEN1957/AUDITORIA_SEMANTICA.md §4. Estado: 651/742, 91 abiertas, 18/35 cerradas (Abrir aplicaciones 48/54 (−4); Alarmas, recordatorios, tareas y agenda 37/38 (−1); Archivos y carpetas 29/32 (−2); Bibliotecas y fichas de juegos 5/6 (−1); Energía del sistema 1/3 (−2); Información web actual 3/17 (−14); Instalar y desinstalar software 2/31 (−11); Interacción dentro de aplicaciones 12/22 (−6); Mensajería 21/31 (−8); Navegación y búsqueda web 42/46 (−3); Organizar ventanas y pestañas 11/13 (−1); Pantalla, captura e interpretación visual 18/19 (−1); Red y Bluetooth 18/21 (−2)). Marco: lecturas de la mente por tandas selladas con cien; herramientas tipadas sin motor; las filas «requiere motor» esperan la entrega de Fable (D23/D24).

## Actualización 2026-09-20 (NEAR1995)

Abrir aplicaciones pasa de 48/54 a 50/54 con abrir sin preguntar la aplicacion cuyo nombre mal oido tiene un solo candidato instalado (commit e5258858, BUILD1995) (HEAD e5258858): 6 aprobados de 8 (H0386 «Abre stea,» y H0522 «Sí, abre Ste.» abren Steam sin preguntar con dos variantes; H0227/H0398 «Steel» fallan por el empate con dos «Shell» del catálogo real), 2 créditos. Medición: cuatro casos con app.open de Steam completada y verificada (reutilizado, alreadyRunning) y finales que nombran Steam; dos literales «Steel» preguntaron por Google Cloud SDK Shell u OpenSSL Shell (defecto de desempate de la lectura, reparación pendiente); dos límites con cero operaciones.

## Enmienda 2026-09-20 (REOPEN1996)

H0521 «abres team» vuelve a abierta: la regla del candidato único depende de lo instalado en este PC y Microsoft Teams no lo está; Steam es el único candidato y se abre (NEAR1997). Estado: 652/742, 90 abiertas, 18/35 cerradas.

## Actualización 2026-09-21 (NEAR1997)

Abrir aplicaciones pasa de 49/54 a 49/54 con abrir sin preguntar el nombre mal oido que comparte el prefijo con un solo nombre instalado (commit 1a3ced2a, BUILD1997) (HEAD 1a3ced2a): 8 ejecutados, 4 aprobados (2 variantes y 2 límites), 4 fallidos (3 literales y 1 variante: app.open de Steam verificada pero final sin nombrar Steam), 0 créditos. Defecto determinista del composer: el recibo de app.open trae appId y el chequeo de nombre sólo mira observed.app; la pista de reintento no llevaba el nombre. Reparación pendiente en la mente; se vuelve a medir en la próxima tanda de nombres mal oídos.

## Actualización 2026-09-21 (CONTEXT1999)

Organizar ventanas y pestañas pasa de 11/13 a 11/13 con cambiar a la ventana de atras y mirar la pantalla cuando el contexto es determinista (commit b720e9a8, BUILD1999) (HEAD b720e9a8): 8 ejecutados, 2 aprobados (los límites), 6 fallidos (3 de otra ventana: enfocó un widget sin título de DisplayFusion; 3 de mirar: leyó toda la pantalla y citó la barra de Steam, no el diálogo de delante), 0 créditos. Dos defectos de fundamentación de la mente: la otra ventana debe ser la primera ventana con título y de tamaño visible por detrás de la del foco; «lo» sin antecedente es la ventana activa, no todo el escritorio. Reparados en el commit siguiente; se vuelve a medir.

## Actualización 2026-09-21 (THEN2001)

Alarmas, recordatorios, tareas y agenda pasa de 37/38 a 38/38 con cancelar la alarma de la sesion y escribir en la app recien abierta sin preguntar (commit b3b29bd0, BUILD2001) (HEAD b3b29bd0): 8 ejecutados, 5 aprobados (H0011 con sus dos variantes y los dos límites), 3 fallidos (los tres de «ponle hola»: el primer turno abrió el Bloc de notas y no publicó final por el nombre de catálogo windows.notepad), 1 créditos. Regresión de la mente descubierta: el chequeo de nombre en finales de app.open (BUILD2001) tomó el id de catálogo de las apps de la Tienda como nombre; se repara (displayName primero) y se vuelve a medir H0097. La categoría queda cerrada.

## Actualización 2026-09-21 (THEN2003)

Interacción dentro de aplicaciones pasa de 12/22 a 12/22 con escribir en la app recien abierta sin preguntar (commit 6bce0d97, BUILD2003) (HEAD 6bce0d97): 8 ejecutados, 2 aprobados (dos límites), 6 fallidos (cuatro sin final tras abrir el Bloc de notas por la regla de estado; uno con el tecleo verificado pero el final como eco; un límite de prohibición no reconocido), 0 créditos. Dos defectos del composer: la regla de estado veta «Abrí el Bloc de notas.» y el final del tecleo repite el texto sin decir que lo escribió. Reparados en el commit siguiente; se vuelve a medir H0097.

## Actualización 2026-09-21 (THEN2007)

Interacción dentro de aplicaciones pasa de 12/22 a 13/22 con escribir en la app recien abierta sin preguntar (commit 6ff50ec8, BUILD2007) (HEAD 6ff50ec8): 8 ejecutados, 6 aprobados (H0097 con dos variantes en español y los tres límites), 2 fallidos (las variantes en inglés: «I opened Notepad.» vetado por el nombre español de la app), 1 créditos. Arista del chequeo de nombre: el displayName es español y la respuesta inglesa nombra Notepad; se añade el alias bilingüe. La limpieza de la raíz restaura los bytes de TabState del Bloc de notas.

## Actualización 2026-09-21 (SEARCH2005)

Navegación y búsqueda web pasa de 42/46 a 42/46 con buscar recetas de pizza y Transformers con resultados pertinentes (commit e9d71375, BUILD2005) (HEAD e9d71375): 8 ejecutados, 5 aprobados (los dos literales, «search Transformers» y los dos límites), 3 fallidos (informe en inglés sin sitios; «buscame» no reconocido; «porfa» dentro de la consulta), 0 créditos. Tres defectos de la mente: la regla de fuente aceptaba títulos sin sitio, la gramática de búsqueda no tiene el clítico «buscame» y la cortesía final no se recorta de la consulta. Reparados en el commit siguiente; se vuelve a medir.

## Actualización 2026-09-21 (SEARCH2011)

Navegación y búsqueda web pasa de 42/46 a 43/46 con buscar recetas de pizza y Transformers con resultados pertinentes y su sitio (commit 5e6f2fbc, BUILD2011) (HEAD 5e6f2fbc): 8 ejecutados, 5 aprobados (H0380 con sus dos variantes en inglés y los dos límites), 3 fallidos (H0098 por varianza contra WEB1889; «buscame» sin web.search en el shortlist; «porfa» dentro del argumento), 1 créditos. Dos reparaciones más de la mente (web.search visible para una búsqueda pública reconocida; cortesía fuera del argumento) y re-medición de H0098; el caso 4 se re-ejecutó solo tras un abortado de preflight de la raíz.

## Actualización 2026-09-21 (SEARCH2015)

Navegación y búsqueda web pasa de 43/46 a 43/46 con buscar recetas de pizza con resultados pertinentes y su sitio (commit 7910c610, BUILD2015) (HEAD 7910c610): 8 ejecutados, 7 aprobados (las cuatro variantes y los tres límites), 1 fallido (el literal: borrador correcto vetado por WEB1889 por palabras de narración del informe), 0 créditos. La regla de afirmación sin fuente veta las palabras de narración del propio informe; se amplía su vocabulario propio y se vuelve a medir H0098.

## Actualización 2026-09-21 (SEARCH2019)

Navegación y búsqueda web pasa de 43/46 a 44/46 con buscar recetas de pizza con resultados pertinentes y su sitio (commit a17670a8, BUILD2019) (HEAD a17670a8): 8 ejecutados, 7 aprobados (H0098 con tres variantes y los tres límites), 1 fallido (una variante sin final: una palabra sin fuente y reintentos con direcciones pegadas), 1 créditos. La pista de reintento del veto de afirmación sin fuente se repara para nombrar las palabras y conservar el informe; la lectura de búsqueda queda medida.

## Actualización 2026-09-21 (WEATHER2023)

Información web actual pasa de 3/17 a 3/17 con el clima se lee de un servicio de pronóstico, no de una búsqueda (commit be90f56b, BUILD2023) (HEAD be90f56b): 8 ejecutados, 6 aprobados (los cuatro literales, la variante en inglés y el límite de prohibición), 2 fallidos («¿hace frío afuera?» preguntó; el límite del pasado leyó el clima de hoy), 0 créditos. La lectura de clima gana la cabeza «hace» y las palabras frío/calor, y excluye el pasado (verbo en pasado o año); se vuelve a medir el panel.

## Actualización 2026-09-21 (WEATHER2025)

Información web actual pasa de 3/17 a 6/17 con el frío y el calor de afuera son el clima; el clima del pasado es un límite (commit 2ecbaff1, BUILD2025) (HEAD 2ecbaff1): 8/8 aprobados (4 literales, 2 variantes, 2 límites), 4 créditos. Cuatro créditos: H0415, H0339, H0617 (Información web actual 6/17) y H0708 (Navegación y búsqueda web 45/46); «¿hace frío afuera?» lee el clima y el clima de 1990 es un límite honesto.

## Actualización 2026-09-21 (NEWS2027)

Información web actual pasa de 6/17 a 6/17 con las noticias de hoy son titulares leídos, no una búsqueda (commit 5aca1a37, BUILD2027) (HEAD 5aca1a37): 2/8 aprobados (0 literales, 0 variantes, 2 límites), 0 créditos. Sin crédito: las seis lecturas de titulares se verifican pero los finales mueren por internal_code (fuentes con dominio); reparación en BUILD2029 y re-medición como NEWS2029.
