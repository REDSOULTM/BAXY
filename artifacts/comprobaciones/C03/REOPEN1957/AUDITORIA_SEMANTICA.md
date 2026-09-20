# Auditoría semántica de las 742 filas (plan post-goal, Fase 3 ampliada por D24)

Escritor: la raíz (Opus 5), 2026-09-20. Mandato del dueño (D24): analizar las 742 filas del registro contra lo que
la encuesta espera de cada una —literal, `expectation_kind`, la nota del dueño en `owner_review.note` y cómo debería
hacerse— y dejar la comprensión correcta, no sólo reabrir.

Regla de decisión (dueño, 2026-09-20): **actuar cuando el contexto es determinista o el candidato es único, y decir qué
se hizo; preguntar sólo con ambigüedad real; elegir por la persona sólo donde es determinista.**

## 1. Método

Las 742 filas se leyeron una por una (`audit_all_rows.txt` en el scratchpad de la sesión: literal, categoría de la
taxonomía, `expectation_kind`, estado, nota del dueño, `verification_reason` acreditada y tandas de evidencia). Para
cada fila se contrastó lo acreditado con lo que la encuesta pide. Se marcan tres defectos:

- **pregunta donde el contexto era determinista o el candidato único** (cero operaciones y una pregunta);
- **lectura en vez de la acción** (se acreditó una lectura de estado/biblioteca cuando la fila pide un efecto);
- **final que no responde exactamente lo pedido** (un fallo honesto acreditado como cobertura: búsqueda «fallida por
  resultados no pertinentes», clima sin clima, «Windows no aceptó», canal preguntado cuando el destino era único).

Todo lo demás (lecturas de estado correctas, efectos verificados, límites decididos por el dueño, entradas
ininteligibles, prohibiciones, idiomas fuera de aceptación) queda como está y se lista en §4 con su razón.

## 2. Resultado en cifras

| | Filas |
|---|---:|
| Filas auditadas | 742 |
| Ya abiertas por REOPEN1957 (D1/D11) | 35 |
| Reabiertas por esta auditoría (REOPEN1993) | 56 |
| De ellas, por decisión ya tomada del dueño (grupos A, B, C y D parcial) | 18 |
| De ellas, por hallazgo nuevo de la auditoría (grupos E–H, N, P, S, W, F) | 38 |
| Se mantienen cubiertas con la lectura actual | 651 |
| Registro tras REOPEN1993 | 651/742 cubiertas, 91 abiertas, 0 NA |

Las 56 filas se reabren con `reopen_1993.py` (esquema REOPEN1957): causa, tanda que acreditó, razón previa y decisión
en `reopen_history`; contadores y tabla por categoría reconstruidos desde el registro y `taxonomy.json`.

## 3. Grupos reabiertos, con la lectura correcta y cómo se mide

Leyenda de mecanismo: **mente** = lectura determinista en `effect_intent.py`/`__main__.py`/`llm.py` con tanda sellada
(literales por id, dos variantes, límites) y cien detrás; **tipada** = herramienta nueva del catálogo con verificación
propia de Windows; **motor** = necesita el motor general de computer use (Fable, D23/D24): queda abierta con causa
«requiere motor» hasta que se entregue.

### A. Contexto determinista (decidido por el dueño) — mente
| Fila | Literal | Hoy | Lectura correcta |
|---|---|---|---|
| H0011 | cancelá la alarma | pregunta cuál | `notification.list`; si hay exactamente una programada, `notification.cancel.latest`/`cancel.at` y decir cuál canceló; con varias, preguntar cuál nombrándolas; con ninguna, decirlo (nota del dueño: «a menos que baxy ya tenga una alarma justo en esta sesión») |
| H0263 | cambiá a la otra ventana | pregunta cuál | «la otra» = la ventana anterior al foco (orden Z, siguiente ventana visible distinta de la activa): `window.resolve` + `window.focus`, y decir a cuál cambió; con más de una candidata clara no hay ambigüedad (es la anterior) |
| H0299 | (ruta pegada de ROADMAP.md) | pregunta qué hacer | nota del dueño: «identificar de qué se trata, leerlo si es accesible y responder basándose en su contenido»: leer el archivo (texto/markdown por `document.*`/lectura de fichero conocido) y decir de qué trata citando su comienzo; si no es accesible, decirlo |
| H0528 | Quiero que lo veas y de que se trata? | pregunta qué mirar | «lo» sin antecedente = la pantalla (lo que hay delante): captura + OCR y decir de qué trata lo visible; sólo con un antecedente en la conversación (un archivo, una página) se mira eso |

### B. Nombre aproximado o cortado (decidido; regla del dueño 2026-09-19 «lo mal dicho lo arregla BAXY») — mente
| Fila | Literal | Lectura correcta |
|---|---|---|
| H0227, H0398 | abre Steel. / Sí. Abre Steel. | único candidato instalado por similitud (Steam) → `app.open` sin preguntar, y decir que abrió Steam |
| H0386 | Abre stea, | ídem (el dueño confirmó Steam) |
| H0522 | Sí, abre Ste. | ídem |
| H0682 | Ve a Mad de Rivals. | único juego instalado parecido (Marvel Rivals) → `game.launch` y decir que lo lanzó |

Aplicada la misma regla, tres filas del grupo B **no cambian** y se mantienen cubiertas: H0521 «abres team» tiene dos candidatos instalados (Steam y Microsoft Teams; nota del dueño: no convertir Teams en equivalencia universal) → la pregunta con los dos nombres es la lectura correcta; H0393 «Ve a portal una.» y H0541 «Ve Portal 2 UN» no tienen ningún candidato instalado (no hay Portal ni Portal 2 en las cuatro bibliotecas de Steam de este PC) y el nombre llega cortado → preguntar es lo correcto (nota del dueño: «intentar entender con contexto y preguntar si no se puede»).

### C. Dentro de la aplicación (decidido) — motor, salvo H0097
| Fila | Literal | Lectura correcta |
|---|---|---|
| H0128, H0232, H0325, H0368 | silenciar el micrófono en Discord | pulsar el control «Silenciar» de Discord y verificar su estado (motor: vista → clic → postlectura); no el micrófono del sistema |
| H0344 | hace click en el boton rojo | color dominante HSV por control (visión sin LLM del motor, D23): el único control rojo se pulsa; con varios se pregunta cuál |
| H0097 | ponle hola | escribir «hola» en el control con el foco (`input.text.type`) cuando hay una ventana ajena en primer plano con un control editable enfocado; sin foco editable, preguntar dónde (nota del dueño: «salvo que el contexto previo deje claro el destino») — mente, sin motor |

### D. Elegir por la persona (decidido parcialmente) — H0701 mente; H0045/H0074 motor
| Fila | Literal | Lectura correcta |
|---|---|---|
| H0701 | Dime cuantos archivos .py hay en el directorio actual | «directorio actual» = la carpeta del Explorador en primer plano (ruta de la ventana CabinetWClass activa); sin Explorador delante, el escritorio; contar con `filesystem.known.list`/lectura de carpeta y decir la cifra y la carpeta |
| H0045, H0074 | contestale que llego en 10 / contestale que si | «contestale» = el remitente del último mensaje recibido (WhatsApp/Discord, por OCR de la banda de chats, CHATREAD1983); `message.send` a ese destinatario con confirmación en modo normal; sin ningún mensaje reciente legible, preguntar a quién |

Fuera de D por decisión del dueño: «pon algo/una serie en Netflix/Disney+» (H0010, H0113, H0130, H0252, H0270) siguen
preguntando qué ver; volumen/brillo relativos sin cantidad siguen preguntando la cantidad.

### E. Destino único o aprendible en mensajería (hallazgo) — mente + `message.recipient.resolve`/`message.send`
Hoy estas filas terminan preguntando «¿por qué cliente?». Cuando el destinatario existe en exactamente un cliente
instalado, el canal es determinista y la encuesta pide el envío.
| Fila | Literal | Lectura correcta |
|---|---|---|
| H0019 | mandale a Música que ya voy | «Música» es un grupo de WhatsApp y no existe en Discord → resolver el destinatario en los clientes (`message.recipient.resolve` por canal); único → `message.send` (confirma en normal, D2/D3) y decir que lo mandó por WhatsApp |
| H0408 | Manda un mensaje a Música que dija hola | ídem («dija» es errata de «diga») |
| H0198, H0231, H0536 | mandale/enviale al grupo Musica: … | «al grupo» ya dice el canal (los grupos son de WhatsApp en este PC) → enviar sin preguntar el cliente |
| H0024 | escribile a Lucas que llego tarde | nota del dueño: «preguntar dónde enviar si no se conoce el canal; aprender si Lucas es contacto de WhatsApp, Discord… y guardar esa asociación»: primero resolver en los clientes; si no está, preguntar el canal y, tras la respuesta, guardar la asociación Lucas→canal en la memoria privada (con la memoria activa) para no volver a preguntar |

Se mantienen preguntando (el destinatario no existe en ningún cliente de este PC, ambigüedad real): H0108, H0303, H0423
(«mamá»), H0584 («mi amiga»); la lectura nueva intenta resolver antes de preguntar, así que en un PC donde exista el
chat «mamá» enviaría. No se reabren porque el resultado medible aquí es la misma pregunta.

### F. Búsquedas acreditadas como «fallidas por resultados no pertinentes» (hallazgo) — mente/web.search
| Fila | Literal | Lectura correcta |
|---|---|---|
| H0098 | buscá recetas de pizza | la búsqueda debe devolver recetas (CHAIN1931 ya buscó «receta de pizza» con éxito con DDG lite/Bing); el final nombra páginas y lo que dicen; se re-mide |
| H0380 | Busca Transformers | ídem: resultados sobre Transformers, no un fallo honesto |

### W. Clima (hallazgo): la encuesta pide el clima, no páginas sobre el clima — tipada `weather.current`
Trece filas acreditadas con «no obtuvo el clima» o «encontré páginas sobre el clima». Lectura correcta: una lectura
tipada `weather.current(location?)` (Open-Meteo: geocodificación del lugar nombrado + pronóstico actual/diario; sin
lugar, la ubicación de este PC por IP o por el país/zona configurados), sin clave, y un final con temperatura, estado
del cielo y, si se pregunta por lluvia, la probabilidad del día siguiente. Sólo si la API no responde, la búsqueda
web como reserva.
Filas: H0034, H0061, H0339, H0415, H0431 («en google» es un medio, se declina nombrándolo), H0478, H0590, H0617 («va
a llover mañana»), H0664 (Madrid), H0689, H0699, H0708 («en internet»). Se mantiene H0266 («clima en Bruno Mars»: no
es un lugar; el fallo honesto es la respuesta correcta).

### N. Noticias (hallazgo): la encuesta pide las noticias, no nombres de portales — tipada `web.news.headlines`
H0033, H0374 («buscá noticias de hoy»), H0509 («qué pasó hoy en el mundo»): hoy el final lista títulos de portales
(«Últimas noticias de Chile y el mundo en Meganoticias»). Lectura correcta: titulares del día (RSS de Google News
es-419/CL o del motor de búsqueda con modo noticias) y un final con tres a cinco titulares citados tal cual con su
medio.

### G. Instalar/desinstalar software que no es un juego (hallazgo): se acreditó una lectura de la biblioteca de Steam — tipada (winget)
Leer «instala Photoshop» o «desinstalá Discord» como consulta a la biblioteca de Steam es una comprensión equivocada.
Lectura correcta: `package.install.prepare/commit` (winget, ya en catálogo) para instalar y una `package.uninstall`
(winget uninstall; WorkLoss → confirma) para desinstalar, con postlectura del catálogo de Inicio/winget.
| Fila | Literal | Resultado esperado en este PC |
|---|---|---|
| H0167, H0217, H0457, H0583 | instala Photoshop | winget no lo ofrece (Adobe lo distribuye por Creative Cloud): final honesto que lo diga tras buscarlo, no una lectura de Steam |
| H0651 | instala Spotify | ya está instalado: decirlo tras comprobarlo por winget/catálogo (o instalarlo si no estuviera) |
| H0089, H0574 | desinstalá Discord / desinstalá Spotify | desinstalación real por winget con confirmación; en la tanda se mide con un paquete de prueba instalado por la raíz (D13: literal sustituido, `literal_measured` anotado); nunca se desinstala una app del dueño en una tanda |

### S. Filas de Steam/Epic que REOPEN1957 no alcanzó (hallazgo) — banco de Steam de la Fase 5
| Fila | Literal | Nota |
|---|---|---|
| H0456 | Descarga Worms Rumble en Steam. IMPORTANTE: primero busca el AppID via … | descarga real (steam:// + manifiesto); la directiva del enlace se declina o se usa si es seguro (nota del dueño) |
| H0571 | Descarga diin  eternal de steam | errata de dictado → Doom Eternal (nota del dueño); descarga real |
| H0578 | Descarga Fall guys en epic games | descarga real en Epic (protocolo del lanzador `com.epicgames.launcher://` + manifiesto, o el motor sobre el lanzador) |
| H0620 | Desinstala Worms Rumble | `game.uninstall.named` (steam://uninstall + ausencia de manifiesto; confirma) |

### P. Energía (hallazgo): «Windows no aceptó la solicitud» es un defecto del producto, no un final válido — tipada
H0401 «reiniciá la PC», H0714 «apagá la computadora»: `InitiateSystemShutdownEx` falla porque el proceso no habilita
`SeShutdownPrivilege` (`WindowsPowerTransitionAdapter.cs`). Lectura correcta: habilitar el privilegio
(`AdjustTokenPrivileges`) y pedir la transición con un plazo corto; WorkLoss → confirma en normal. Medición sin apagar
el PC: la transición se pide con un retraso y la raíz la aborta (`shutdown /a`) tras verificar que quedó programada.

### H. Wifi «de casa» (hallazgo) — mente + `wifi.profile.list`/`wifi.connect.named` + memoria
H0170, H0376: nota del dueño: «preguntar cuál red si no la conoce, solicitar contraseña si hace falta y continuar; si
ya conoce credenciales…». Hoy termina en «no hay ningún perfil con ese nombre», que no pregunta ni aprende. Lectura
correcta: «casa» no es un SSID → listar los perfiles guardados/visibles, preguntar cuál es la de casa, guardar la
asociación en la memoria privada y conectar; con la asociación ya guardada, conectar directo. H0739 («wifi de la
luna») se mantiene: nombre inexistente, fallo honesto correcto.

## 4. Lo que se mantiene, por grupo y razón

- **Volumen y brillo relativos sin cantidad** (20 filas: H0027, H0028, H0031, H0058, H0075, H0123, H0193, H0242,
  H0294, H0308, H0357, H0436, H0446, H0488, H0494, H0530, H0563, H0606, H0627, H0695): regla vigente del dueño
  (H0027/AUDIO1020), reafirmada el 2026-09-20.
- **«Ponlo a 100 / devuélvelo a 100» sin antecedente** (H0439, H0713): ambigüedad real fuera de una conversación.
- **Hora sin AM/PM** (H0036, H0197, H0222, H0234, H0473): el dueño aceptó la aclaración en la revisión; no es
  determinista sin contexto. Nota para el futuro: «la próxima ocurrencia» sería una regla posible, no decidida.
- **Alarma/tarea/recordatorio sin contenido o sin hora** (H0043, H0121, H0137, H0343, H0585): las notas del dueño
  piden preguntar; H0715 ya lleva el contenido y se creó.
- **Reunión sin duración** (H0119): la duración no es determinista.
- **«pon algo / una serie en Netflix/Disney+»** (H0010, H0113, H0130, H0252, H0270) y **«pon música / poneme una
  canción»** (H0009, H0066, H0129, H0141, H0352, H0405, H0526, H0601, H0656, H0740): preguntan qué poner; decisión del
  dueño para vídeo, misma lógica para música.
- **Deícticos sin antecedente, pedidos cortados, texto/destino ausentes** (H0088, H0091, H0216, H0265, H0349,
  H0426, H0531, H0534, H0619, H0704, H0718): las notas del dueño piden usar contexto o preguntar; sin contexto se
  pregunta.
- **Entradas ininteligibles, ajenas, símbolos, negaciones, repeticiones** (DIALOGUE/UNRES/CLARIFY: H0006, H0139,
  H0140, H0160, H0181, H0205, H0210, H0246, H0271, H0287, H0297, H0313, H0332, H0336, H0372, H0404, H0410, H0414,
  H0429, H0441, H0483, H0493, H0500, H0562, H0570, H0581, H0610, H0639, H0694, H0735): fieles a las notas del dueño.
- **Identidad, conversación y conocimiento** (todas): respuestas correctas y sin invención; H0424/H0645 («identidad
  secreta», «quién es de verdad») dependen del contexto según el dueño.
- **Prohibiciones y restricciones** (H0057, H0333, H0407, H0427, H0447, H0496, H0507, H0519, H0550, H0603, H0685).
- **Idiomas fuera de aceptación oficial** (18 `unmarked_limit`): decisión del dueño.
- **Contactos** (H0014, H0116, H0124 negativos; H0138, H0306): decisión del dueño («en PC no tiene sentido»).
- **Prime Video** (H0646), **ver su propio código** (H0635), **pip/git/python** (H0052, H0468, H0475): decisiones
  o pendientes deliberados del dueño; `shell.command.run` de la Fase 5 servirá también a H0468 cuando exista.
- **Apps o archivos que no existen** (H0249, H0289, H0322, H0406, H0503, H0558, H0632, H0691, H0739): fallo honesto
  correcto (el dueño lo pide así); H0691 respeta la instrucción más reciente.
- **Cierres/foco/pausa sobre una app ausente** (H0112, H0117, H0421, H0525, H0546, H0556, H0677, H0679, H0693): se
  midieron con la app cerrada; la capacidad con la app abierta está cubierta por las tandas de cierre/arreglo.
- **Lecturas de estado, aperturas, cierres, archivos, notas, agenda, memoria, portapapeles, capturas, ventanas,
  red, Bluetooth, música y vídeo verificados**: efectos reales medidos; nada que objetar.
- **H0733** (backup a un pendrive): no hay pendrive conectado en este PC; la copia no se puede medir sin uno. Queda
  cubierta como lectura honesta y anotada en APLAZADOS: cuando el dueño conecte un pendrive se mide la misma misión
  (`storage.removable.list` + copia + verificación).
- **H0594/H0742 «describe lo que ves»**: OCR y honestidad sobre la imagen; la descripción visual llegará con la
  visión sin LLM del motor (D23), no se reabre por adelantado.

## 5. Estado

Presentado al dueño el 2026-09-20 (grupos A–D) y decidido; los grupos E–H, N, P, S, W y F son hallazgos de la
auditoría completa y se reabren por el mandato D24 («reabrir todo lo que la auditoría concluya»). Aplicación:
`REOPEN1993/REGISTRY_UPDATE.json`. Orden de trabajo: primero las lecturas de la mente (A, B, H0097, H0701, E, F, H),
luego las tipadas sin motor (W, N, G, P, S por `steam://`), y las de motor (C, H0045/H0074) cuando Fable entregue.
