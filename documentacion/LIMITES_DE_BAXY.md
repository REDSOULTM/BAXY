# Lo que BAXY hace siempre y lo que no hace

Para el dueño. Estado: **cierre de la misión de estabilización (2026-10-12)**. Las medidas son del banco definitivo
×3 sobre `0f2468bb1` (`cu-v3/estab_def.json` y los jueces `bancoB_def1..3_juez.json`, 12-10 12:55–16:49). Lo que
falta confirmar con el último banco lleva la marca **«pendiente: banco fx (b61edf336)»**: ese banco corre sobre la
integración final con el arreglo de teclas K.

BAXY corre con un modelo local de 4B y 4 GB de VRAM. Hace, al máximo y siempre, lo que puede con eso. Lo que no puede
hacer de forma fiable no lo intenta: lo dice corto, con la causa, y te deja lo más cerca posible por la parte segura.

## Lo que hace siempre

«3/3» quiere decir logrado en las tres corridas del banco definitivo, con juez independiente donde la firma cambió.
Todas las corridas son en modo bypass sobre blancos seguros. Los casos de voz de Discord (s11, s13, c7) y s14 corren en
Normal para comprobar la pregunta.

| Familia | Ejemplo real | Medida |
|---|---|---|
| Calculadora: calcular, cambiar de modo | «en la calculadora calculá 37*12» (s01) | s01 n2 e1 x1 x12 y1 y7: 3/3. x8 («abrí la calculadora y calculá 125 más 75») y c2: 2/3. En la corrida que falló se perdió una tecla al traer la Calculadora al frente. El arreglo K espera a que la ventana tenga el teclado → **pendiente: banco fx (b61edf336)** |
| Reloj: ir a una sección | «en el Reloj andá a Cronómetro» (s02) | s02 u7 n3 e3 v9 x2 x11 y3 y11: 3/3 |
| Configuración: ir a una sección, buscar, leer un valor | «abrí Configuración, andá a Personalización, entrá a Colores y decime si el modo es claro u oscuro» (c5) | s03 u8 n4 x3 x4 y2 y9 v3 v10 v11 c5: 3/3 |
| Explorador: ir a una carpeta, crear una carpeta | «en el Explorador de archivos andá a Documentos y creá una carpeta llamada baxy-prueba» (c3) | s04 n8 e4 v4 x6 y5 c3: 3/3 |
| Bloc de notas: escribir | «abrí el Bloc de notas, escribí "lista: pan", apretá Enter y escribí "leche"» (c1) | c1 x5 y4: 3/3 |
| Paint: elegir herramienta y color | «abrí Paint, elegí el lápiz y después el color rojo» (n1) | s07 n1 e2 v7 x9 y6 y12: 3/3 |
| Panel de control, Microsoft Store, Fotos | «en la Microsoft Store buscá Spotify» (v1) | s05 u2 v1 u3: 3/3 |
| Varias órdenes seguidas o encadenadas | «en el Reloj andá a Alarma» → «…a Cronómetro» → «en Configuración andá a Bluetooth y dispositivos» → «en la calculadora calculá 9 por 8» (w1, cuatro turnos) | w1 y1 y3 y5 v11 x10 y10: 3/3. c2 (calcular, copiar y pegar en el Bloc de notas): 2/3 → **pendiente: banco fx (b61edf336)** |
| Spotify: ir a secciones | «abrí Spotify y andá a tu biblioteca» (u1) | u1 y8 v8 u9 x7: 3/3 |
| Spotify: buscar y reproducir | «pon lo-fi para estudiar en spotify plis» (tanda t1-c07) | No está en el banco B. Con el arreglo SP suenan las tres órdenes de música de las tandas en fin3 y fin4 (6/6, redpc). Antes, en fin1 y fin2, sonaban 2 de 6 (el resto decía «no pude confirmar si se hizo»). **pendiente: tandas fin7/fin8** |
| Discord: abrir un chat y enviar (con confirmación) | «en Discord abrí el chat con Ron92, escribí "prueba BAXY C6" y mandalo» (c6) | c6: 3/3 en el banco y 3/3 en msg1–3. Dice «Listo, le mandé «prueba BAXY C6» a «Ron92» por «Discord».», y al «sí» siguiente, «Ya lo envié.». En Normal, s14 pregunta y con «no» no envía: 3/3 |
| Discord: leer lo último | «en Discord leé lo último que me escribió Ron92» (imp-dc-leer) | 3/3 en msg1–3 (12-10) y 1/1 en imp3. Responde desde lo que muestra el chat: «En lo que muestra el chat no hay mensajes de Ron92.» |
| Discord: entrar y salir de voz (con confirmación) | «en Discord entrá al canal Cotele» → «sí» → «en Discord salí del canal de voz» (imp-dc-voz) | En Normal pregunta y con «no» no entra: s11, s13 y c7, 3/3 cada uno. Entrar con «sí» y salir: imp-dc-voz 5/5 (imp1, imp2 y wac1–3 tras el arreglo VZ, con una sola pregunta: «¿Quieres confirmar que entre en «Cotele!!!😎» o cancelar?» → «Listo, estoy en «cotele».» → «Listo, hice clic en «Desconectar».»). Sin llamada activa dice «No estás en ningún canal de voz ni llamada, así que no pulsé nada.»: imp-dc-salir-voz 2/2 (imp2, imp3d) |
| WhatsApp: abrir un chat y enviar (con confirmación) | «en WhatsApp abrí el chat con Abuela», «en WhatsApp mandale a Abuela "prueba BAXY imp"» (imp-wa-abrir, imp-wa-enviar) | Banco final zw (14-10, da9a8bb78): abrir 3/3 y enviar 3/3, también con el chat fuera de la parte alta de la lista (TZ-WA2: se abre por su entrada, por «Todos» o por el buscador, nunca «Nuevo chat»). Antes: wac1–3 3/3, war1–3 enviar 3/3, Normal 3/3. Con el grupo archivado «Música», 0/12 |
| WhatsApp: leer lo último | «en WhatsApp leé lo último que me escribió Abuela» (imp-wa-leer) | **Correcto 3/3 en zw** («En lo que muestra el chat no hay mensajes de Abuela.»): el chat «Abuela» no tiene ningún mensaje de ella (14 burbujas, todas del dueño). WA-LEER deja la lectura lista para cuando escriba: el chat llega entero, la última burbuja no se pierde y las de la izquierda son las de la otra persona (14/14 sobre vistas congeladas con una burbuja suya; antes 7/14). Falta la prueba en vivo con un mensaje de ella. Nunca cita texto de la interfaz como mensaje |
| Steam: biblioteca, tienda, comunidad | «en Steam andá a la biblioteca y después a la tienda» (x10) | s12 n7 x10 y10 c7: 3/3 |
| Steam: lanzar un juego instalado | «lanzá Cuphead» (imp-steam-lanzar) | 3/3 (imp1, imp2, stm3 del 14-10): «He lanzado Cuphead.» |
| Steam: instalar y desinstalar (con confirmación) | «instalá Super Meat Boy en Steam», «desinstalá Super Meat Boy en Steam» | imp-steam-instalar y -desinstalar: 3/3 (imp1, imp2, stm3): «Listo, empecé a instalar el juego «Super Meat Boy».», «Listo, desinstalé el juego «Super Meat Boy».». Super Meat Boy queda como estaba. En Normal pregunta «¿Quieres confirmar que instale Super Meat Boy en Steam o cancelar la acción?» y con «no» no instala: imp-steam-instalar-normal 3/3 |
| Word y Excel (mejor esfuerzo) | «abrí Excel y elegí libro en blanco» (u5) | u5 n6 v5 v6: 3/3. Fuera de estas órdenes, ver los límites |
| Sistema: volumen, silencio, portapapeles, capturas, recordatorios, temporizador | «baja el volume a like 20 porfa» (t2-c12) | No está en el banco B. Tandas fin1–fin4 (redpc, 4 corridas): misma ruta en las 4 para volumen (t2-c12), silenciar (t1-c19), copiar al portapapeles (t2-c17, t3-c10), capturas (t1-c16, t2-c16, t3-c11, t4-c09), recordatorio (t1-c04) y temporizador (t1-c14, t2-c06, t3-c01) |
| Búsquedas y preguntas con búsqueda en la web | «busca en google los horarios del cercanias de madrid» (t4-c10), «quien gano el mundial del 2014» (t1-c18) | Tandas fin1–fin4: abre la búsqueda en 4/4 (t1-c08, t2-c08, t3-c06, t4-c10). La pregunta con búsqueda acierta 4/4 (t1-c18) |

Steam: la página de un juego y buscar en la tienda no tienen caso medido en vivo, así que no figuran como «siempre».
Buscar dentro de la biblioteca es un límite (ver abajo).

## Identidad, comprobada en vivo en los dos PC

| Parte | Notebook | redpc |
|---|---|---|
| Vive en la bandeja, arranca con Windows y se queda | FUNCIONA, 11-10 (`cu-v3/estab/I_identidad_notebook.md`, build `f5a2d6f09`) | FUNCIONA, 12-10 09:58–10:41 (`I_identidad_redpc.md`, build `0650deac3`). Arranca oculto con el icono, la X lo deja vivo, «Salir» cierra todo y `Run\BAXY` queda intacto |
| Habla en cada respuesta, voz en español | FUNCIONA, 11-10 (9 respuestas, 9 ráfagas de audio) | FUNCIONA, 12-10 (3 respuestas, 3 ráfagas) |
| Memoria visible, editable y borrable entera | FUNCIONA, 11-10 23:21 (`I_identidad_notebook_2.md`) y 12-10 01:39–01:47 (`I_identidad_notebook_3.md`, build `4708cd575`). El 11-10 08:37 había salido ROJO; se arregló en M | FUNCIONA, 12-10. Panel, editar, borrar uno y borrar todo con confirmación; se conserva tras reiniciar |
| Modo bypass consciente y a la vista | FUNCIONA, 11-10 23:21 y 12-10 01:47 | FUNCIONA, 12-10 (aviso, indicador «bypass · sin confirmaciones», vuelve a `normal`) |
| Modo accesible de la interfaz | FUNCIONA, 11-10 23:21 y 12-10 01:47 | FUNCIONA, 12-10 (escala ×1,27, foco amarillo, por interfaz y por chat) |

Defectos de redacción que salieron en estas comprobaciones, corregidos e integrados en `b61edf336`:
- **Notebook, «nah» tras «Borra de tu memoria…».** Respondía «He borrado…» sin borrar nada. Corregido en M2, `cd6d890f8`.
- **redpc, tres defectos.** «El modo accesible ya está activado.» al activarlo, cuando no lo estaba; el panel no se refrescaba tras un guardado por chat; la ventana de la bandeja se titulaba «B». Corregidos en I2, `ce99ffebc`.

No hay informe propio de una recomprobación en vivo de esas correcciones. `PROGRESO_V3.md` (17:15 del 12-10) las da
por buenas.

## Lo que no hace, y lo dice

Cada límite se comprobó en vivo: BAXY responde corto, con la causa, y no actúa a medias.

| Límite | Por qué | Qué dice BAXY (en vivo) | Comprobado en vivo |
|---|---|---|---|
| Arrastrar y soltar (archivos, diapositivas, notas, dibujar con el ratón) | El modelo no ve coordenadas fiables para un arrastre | «Eso no lo hago: arrastrar un archivo a una carpeta.» · «Eso no lo hago: dibujar una línea recta en Paint.» | t-drag-1…4 (limites2, 12-10) |
| Scroll largo en listas virtualizadas | Lo que no está en pantalla no está en la vista | «No pude hacerlo en «Configuración»: la lista es demasiado larga y lo que queda fuera de la pantalla no lo veo.» | t-scroll-1, t-scroll-2 (limites2, 12-10) |
| Clic derecho sobre un elemento | Los menús contextuales no entran en la vista | «No pude hacerlo en «Explorador de archivos»: los menús del clic derecho no entran en lo que veo.» | t-menu-1, t-menu-2 (limites2, 12-10) |
| Controles fuera de la vista del modelo (cinta de Office: negrita, tablas…) | La cinta no entra en lo que ve el modelo | «No pude hacerlo en «Word»: los botones de formato de la cinta (negrita, tablas y similares) no entran en lo que veo; antes de parar escribí «Informe semanal».» | t-long-2 (limites2); t4-c13 en fin1–fin4 |
| Office fuera de lo medido (mejor esfuerzo) | Sólo u5, n6, v5 y v6 están medidos 3/3; otra forma de pedir lo mismo puede no llegar | «No pude hacerlo en «Excel»: se agotaron los pasos previstos sin llegar.» («bro abre excel y crea un blank workbook», t4-c06) · «Abrí «Word», pero no pude hacerlo: la aplicación está en su pantalla de inicio, sin ningún documento abierto.» (t2-c10) | fin3 y fin4 (redpc, 12-10): falla honesto en las dos |
| Aplicaciones que corren como administrador | Windows no deja que otra aplicación las maneje | «Abrí «Administrador de tareas», pero no pude llegar a «rendimiento»: esa aplicación corre como administrador y Windows no deja que otra aplicación la controle.» | s06 (banco definitivo 3/3) |
| Buscar dentro de la biblioteca de Steam | Su buscador no acepta texto por accesibilidad | «Llegué a «BIBLIOTECA», pero no puedo hacer lo que sigue: el buscador de la biblioteca no me deja escribir; si querés, lo busco en la tienda.» | g1 (banco definitivo 3/3) |
| Órdenes sin aplicación nombrada («guarda esto») mientras trabajas en otra ventana | No actúa sobre tu ventana: pregunta en cuál | «¿En cuál ventana?» | t-guarda-1 (limites2, 12-10) |
| Brillo, Bluetooth o Wi-Fi que el equipo no tiene | Brillo: el monitor no lo expone a Windows. Bluetooth: no hay radio. Wi-Fi: no hay adaptador | «Este equipo no deja cambiar el brillo desde Windows (el monitor no lo expone).» · «Este equipo no tiene Bluetooth.» / «This computer has no Bluetooth.» · «Llegué a «Red e Internet», pero no puedo ir a «Wi-Fi»: este equipo no tiene adaptador Wi-Fi.» | Brillo y Bluetooth: fin3 y fin4 en redpc (12-10, arreglo H2), 2/2 en t2-c03, t3-c04, t4-c04, t1-c11, t2-c15 y t4-c11. Wi-Fi: n5 (banco definitivo 3/3, notebook) |
| Tareas de muchos pasos en aplicaciones fuera del banco | Un 4B no sostiene cadenas largas fuera de lo medido | Para con lo hecho y la causa | t-long-2 (limites2) |

### Un límite que BAXY no siempre dice: datos de memoria en una conversación

Si respondes a una pregunta de datos sin buscar, el modelo local de 4B contesta de memoria y puede equivocarse. Cuando
duda, lo avisa: «No pude comprobarlo; de memoria, puede no ser exacto…» (t4-c02 t3, en 3 de 4 corridas). Pero no
siempre: «dame 4 paises de sudamerica que no tengan salida al mar» dio «Bolivia, Paraguay, Perú y Uruguay» en las
cuatro corridas fin1–fin4, con dos errores y sin aviso. Si pides que lo busque («buscalo en google»), BAXY abre la
búsqueda (4/4). Para un dato que importa, pídeselo con búsqueda.

## Cómo se mide

- **Banco B.** 72 casos, tres corridas sobre el mismo código, jueces independientes donde la firma cambia.
- **Imprescindibles.** Corridas propias: imp1–imp3 y msg1–3, el 12-10.
- **Tandas de uso real.** t1–t4, 123 turnos, en redpc: fin1–fin4.
- **Límites.** limites1 y limites2.

Todas las pruebas corren en modo bypass sobre blancos seguros: envíos sólo a Ron92 en Discord o al grupo «Música» en
WhatsApp, y en Steam sólo Super Meat Boy. Un caso por familia en modo Normal comprueba que la pregunta de confirmación
sale y es fiel. Detalle por caso: `computer-use/ESTABILIDAD.json` y `computer-use/ESTABILIDAD.md`.
