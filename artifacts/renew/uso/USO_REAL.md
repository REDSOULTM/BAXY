# BAXY en uso real: errores del dueño, uno a uno

Sesión en vivo del 2026-10-20/21. Empezó en el PC (REDPC) y siguió en el notebook (REDNOTE) por SSH, a pedido del dueño.
Rama `uso-real`, desde `hub/baxy-renew` 51cd74225 (modelo c2-e1.0, ayudas encendidas). Casos en genérico: las frases
literales del dueño no van a git.

Cómo se verificó cada caso:
- Por el dueño, en su BAXY.
- Por el banco e2e en BAXY real: `scripts/renew/bench_e2e.py`, con 15 casos de la sesión juzgados por el estado del mundo,
  corrido en el escritorio del notebook a pedido del dueño (`uso-nb-1`…`uso-nb-5`).

El plan general (investigación y piezas A1-A7, B1-B3, C1-C4) está en `PLAN_GENERAL.md`.

## Arreglados y verificados

| # | Caso (genérico) | Causa | Arreglo | Verificado |
|---|---|---|---|---|
| 1 | Buscar en Google con un navegador con nombre mientras otra app está delante: la página quedaba detrás y el texto iba a la otra app | Proveedor: un proceso en segundo plano no puede pasar el frente al navegador | El navegador va delante tras una navegación verificada (`BringToFrontAsync`); la página abierta recibe el teclado sin ventana (B2, `NoteOpened`); el permiso de primer plano se cede por PID (B3) | e2e U01 en nb-2 y nb-4; U15 (variante YouTube) en nb-1, nb-4 y nb-5 |
| 2 | Pedir dos veces una canción de un artista en Spotify: la segunda sonaba «Tus Me Gusta» y se daba por buena | Proveedor: con la misma consulta ya en el buscador no se aparta la página de antes; el «Reproducir» de más a la izquierda era el de la barra lateral | Candidatos sólo dentro de la vista de resultados («Spotify – Buscar») | Dueño («rock», 22:54); e2e U02 en nb-1 y nb-5 |
| 4 | Abrir Epic y mirar su ventana: `app.open` incierto y «ventana no encontrada» ×7 | Proveedor: el acceso directo `Win32` arranca la copia `Win64`; el título está localizado | Identidad aprendida al abrir (B1) y carpetas de arquitectura hermanas | Dueño («abre Epic Games», 02:44: verificado); e2e |
| 11 | «Busca X en Epic» acabó en instalar el juego | Las frases de `app.open` enumeraban a mano las apps con lugares, y Epic no estaba | Frase de lugares generada desde `app_places.v1.json` (A6); «no para buscar en una tienda» en instalar (C4); decision2 s0 230/268 (ref. 229) | Ya no instala en ninguna corrida |
| 12 | La página de un juego «en la aplicación» de Epic abría la tienda web | Faltaba un lugar «página de juego» en el lanzador | Lugar `game` con el hueco `{slug}` (`…/store/p/rocket-league`) | e2e U04 en nb-5 |
| 13 | Clic por índice que la vista no tenía (Epic, 0 controles) o que nombraba otro control (Steam, «Chrome Legacy Window»): el clic terminaba sin buscar la etiqueta | Proveedor: el índice inválido cortaba la cascada | El control del índice nunca se pulsa; la etiqueta va a su cascada atada a la ventana nombrada o a la de la última vista | e2e nb-3 y siguientes: desaparecen `identity_stale` y `label_mismatch` |
| 14 | Ventanas animadas (vídeo y carrusel de la tienda de Epic): cada clic se rechazaba o quedaba «sin leer» | Proveedor: se comparaba la ventana entera, que nunca está quieta | Mapa de movimiento por celdas: el punto vale si su entorno no cambió; un cambio fuera de lo que se mueve solo prueba el clic (A3/A4) | e2e nb-5: el clic de visión en el carrito se verificó |
| 15 | Botones sin texto (iconos) en apps sin árbol | No había visión conectada | Visión de respaldo: el mismo Qwen3.5-4B con su proyector en CPU, pregunta en `bbox_2d`, slot guardado y restaurado alrededor (A5); 10/10 en Epic medido aparte | e2e U05 en nb-5: carrito pulsado por visión y verificado |
| 16 | Tras una consulta de visión, la decisión siguiente tardaba 20-25 s | La consulta desalojaba la caché de la conversación (2 GB, no cabe en `-cram`); con 2 slots este modelo híbrido la pierde igual | Guardar y restaurar el slot a disco (1,35 s y 0,74 s); el archivo se borra | Log del servidor en el PC: «restored … checkpoints», 139-211 tokens releídos |
| 3 | Steam: «Tienda» y la búsqueda | App hecha con web; el modelo no usaba los lugares | Ayuda `app_places_next` (C3/b), A3/A4 | e2e U07 en nb-1, nb-4 y nb-5 |
| 7 | Calculadora: un «2» repetido salía 22 | Pantalla igual tras la pulsación | (El modelo usa `calculator.expression.evaluate`) | e2e U08 y U09 en todas las corridas |
| 8 | El tiempo de mañana: URLs de Google News de ~500 tokens copiadas mal | El modelo copiaba URLs enormes | Referencias cortas `ref:rN` (C1) | e2e U10 en todas las corridas |
| 9 | «Ábrela en mi navegador» tras leer una guía buscaba archivos | El modelo eligió mal | (Pasa ahora) | e2e U11 en todas las corridas |
| 23 | Buscar un juego en la tienda de Steam: pulsaba el buscador cuatro veces y decía «no pude escribir» sin escribir | El clic sí había puesto el cursor (la indicación desapareció, `labelStillOnScreen: false`), y el modelo no lo sabía | Ayuda `field_focused_next` (bd8dbd3b7): tras un clic completado cuyo texto ya no se ve, se dice que el campo puede tener el cursor y que lo siguiente es `input_text_type`; una vez por turno, en `turn.aid` | e2e U06 en nb-9: escribió, pulsó el resultado y quedó en la página del juego |

| 24 | Preguntar por un dato guardado («¿cómo me llamo?»): «no lo tengo guardado» sin consultar la memoria; el guardado siguiente chocó con el recuerdo que sí existía | El modelo no llamó a `memory_recall` | Ejemplo «¿cómo me llamo?» en `memory_recall` (cb1fd41aa); decision2 s0 231/268 (base 232) | Pendiente de la prueba del dueño |
| 25 | «Estás en una llamada» sin llamada: BAXY ofreció pausar la música | Windows dejaba como en uso registros viejos del micrófono (carpetas antiguas de Discord, un juego de meses atrás) y el latido los creía (`HeartbeatMoment.cs`) | Un uso cuenta sólo si empezó tras el arranque y, en un programa de escritorio, si su ejecutable corre (f8adb4951, `MicrophoneUse`) | Kernel 592/592; leído en el registro del PC |
| 26 | «Sal de pantalla completa»: tres «close» fallidos (`user_browser_page_unreadable`) | `browser_control` no tenía acción para salir; el modelo eligió cerrar, que lee la barra de pestañas que la pantalla completa oculta | Acción `exit_fullscreen` (e77ade350, 8e9433d92): el botón de salir de la página por UI Automation (CDP en el navegador propio), probada por la ventana que deja de cubrir el monitor; decision2 s0 231/268 | e2e U17 en nb-13 |
| 27 | YouTube puso otro tema que el pedido (el primer resultado) | El proveedor tomaba siempre el primer vídeo | De los cinco primeros, el primero cuyo título lleva todas las palabras buscadas; si ninguno, el primero con `titleMatchesQuery: false` | Pruebas de `YouTubeSearch` |
| 28 | Steam: la página de un juego; el modelo pulsó «Chrome Legacy Window» | La vista listaba la superficie de dibujo de Chromium sin accesibilidad como el control 0 | El worker de UIA no la lista (clase de `render_surface_classes` y el nombre fijo de Chromium) (90e9e23a5) | e2e U16 en nb-13 |

## Pendientes

| # | Caso (genérico) | Causa | Estado |
|---|---|---|---|
| 5 | Pedir una suma y responder «lo que quieras»: vuelve a preguntar | Límite del modelo | Pasó en el e2e (U09); se mantiene como límite intermitente |
| 6 | Una frase confusa sobre «apagar y encender» cerró Spotify (Bypass, sin confirmación) | El modelo eligió mal | Anotado |
| 10 | Historia (Arturo Prat): mezcla hechos de los fragmentos o no busca e inventa | Límite del modelo | Pasó en nb-5, falló en nb-1 y nb-4 |
| 17 | «Busca X en Epic» va al catálogo o a «¿lo tengo?» en vez de la búsqueda | El modelo eligió mal | Probada la frase «cuándo no usar: buscar en una tienda» en esas dos herramientas (a5df99b69): decision2 s0 232 → 231/268, y en BAXY real (nb-11) siguió eligiendo el catálogo. Revertida (0b457c596). Límite del modelo |
| 18 | «La configuración del sistema… pantalla» abre msconfig, protegido, en vez de Configuración | El modelo confunde dos nombres casi iguales; el recibo ya le dice qué app tiene el lugar | Límite del modelo |
| 19 | Pulsar un icono sin texto (el carrito del lanzador): la visión señaló el botón «Tienda» (icono de bolsa) y el clic se dio por bueno porque la página cambió | Proveedor: la visión no comprobaba qué había escrito bajo su punto (`WindowsVisibleVisionLocator.cs`) | Arreglado en bd8a3f1fe y 0aafc68c1: el OCR lee lo escrito junto al punto (margen lateral de una altura de letra); si es otra etiqueta, se pregunta otra vez diciendo cuál no es, y un segundo punto así no pulsa. En nb-9 y nb-10 rechazó los puntos malos. U05 sigue fallando porque el modelo a veces no pide «Carrito» (pulsa «Tienda» u ofertas): límite del modelo |
| 20 | Opera GX en el notebook: página «Actualización finalizada» y bucles de pestaña nueva | Entorno (actualización) y el modelo | Pasó en nb-2 y nb-4; repetir con el entorno quieto |
| 29 | «Pon una canción de rock»: sonó una canción con «rock» en el título | El proveedor de Spotify busca la palabra y toca el primer resultado | Pendiente (buscar por género toca el prefijo) |
| 30 | Tras pausar, el modelo dijo que la canción «sigue sonando»; el recibo decía `paused` | El modelo narró de más | Límite del modelo |
| 21 | Steam en el notebook: la ventana no aparece en la mirada | Entorno: el agente local del notebook trabajaba en el escritorio durante nb-5 | Con el entorno quieto (nb-8) Steam sí se vio; luego resuelto como el caso 23 |
| 22 | Abrir la página de un juego en el lanzador: el modelo pulsó por la tienda hasta la caja de pago de otro juego («Cómpralo ya» ×2) e intentó «Pagar» | Seguro de compras: sólo reconocía el verbo en infinitivo (`RiskPolicy.cs:363`), así que «Cómpralo ya» pasó sin preguntar. «Pagar» sí se detuvo y se respondió «no»: no se pagó nada (journal sin la entrada de ese clic) | Arreglado en 587477ff9: también el imperativo, con pronombre pegado, «Purchase», «Pre-order» y «Adquirir»; el sustantivo («Compras») no. Kernel 588/588, y el patrón probado con el motor de PowerShell del worker de UIA. **Falta la prueba en BAXY**, que espera al dueño |

## Medidas del e2e en el notebook (15 casos)

| Corrida | Aciertos | Notas |
|---|---|---|
| nb-1 | 8/15 | Consola del lanzador visible delante (contaminó) |
| nb-4 | 8/15 | Consola oculta; índices inválidos ya en cascada |
| nb-5 | 10/15 | Mapa de movimiento y lugar `game` de Epic; el agente local trabajaba a la vez (Steam) |
| nb-6 | U01 1/1 | Entorno quieto: el foco con Opera pasa |
| nb-7 | — | Detenida por el dueño: el caso 22 (caja de pago sin preguntar) |
| nb-8 | 0/4 (U03, U05, U06, U13) | Con el seguro de compras arreglado y un vigilante que corta todo ante una caja de pago: no cortó nada |
| nb-9 | U06 1/1, U05 0/1 | Ayuda del campo con el cursor; la visión ya no pulsa sobre otra etiqueta |
| nb-10 | U05 0/1 | El modelo no pidió «Carrito»; la visión rechazó dos puntos malos |
| nb-11 | U03 0/1 | Con la frase «buscar en una tienda» (revertida) |
| nb-12 | 10/17 | Banco con U16 (página de un juego en Steam) y U17 (salir de pantalla completa); estos dos con la ruta del oráculo rota |
| nb-13 | 3/4 (U11, U16, U17 sí; U12 no) | Sin «Chrome Legacy Window» en la vista y con los oráculos arreglados |

Toda corrida desde nb-8 lleva el vigilante de compras (`guard_compras.ps1`, fuera del repositorio): ninguna caja de pago, ningún clic de compra.
