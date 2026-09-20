# Computer use en BAXY — diseño

Decisión del dueño, 2026-09-19: BAXY no debe resolver cada fila con un contrato a medida,
sino usar el ordenador como lo usaría una persona. De las 53 filas abiertas del registro,
**32 son computer use**: las 24 de vídeo y ocho más (navegar a un sitio nombrado, pulsar
algo en pantalla, completar el diálogo de descarga de Steam, descargar en Epic, leer el
último mensaje de un chat, y las dos misiones compuestas).

Lo que sigue es el diseño, con lo que lo sostiene: lo medido fuera, lo que BAXY ya tiene,
y el modelo concreto que corre aquí.

## 1. Los ojos son el árbol de accesibilidad, no la captura

OSWorld mide las tres formas de mirar una pantalla sobre las mismas tareas: árbol de
accesibilidad solo, **18–21 %**; captura sola, **5–15 %**; las dos juntas, **18–25 %**. La
causa que dan es directa: los modelos de visión no aciertan las coordenadas a partir de
una captura, y el árbol se las da hechas.

Para BAXY la elección ni siquiera está reñida. **La mente de este PC es Qwen3-4B, de
texto**: una captura no la puede leer. El árbol no es la mejor de dos opciones, es la
única que el modelo entiende.

Eso ya está hecho y es de lo que hay que partir: `input.visible.click` recorre primero
UIA, y sólo si no encuentra el control cae a OCR y después a visión
(`WindowsVisibleControlAdapter`, cascada de tres). El orden es el correcto y no se toca.

## 2. Un solo acto por paso, nombrado, nunca por coordenadas

Los trabajos de agentes de interfaz convergen en un repertorio mínimo y atómico —pulsar,
escribir, desplazar, tecla, esperar, terminar— y en que el objetivo se nombre por su
elemento, no por su píxel. `input.visible.click` ya toma exactamente eso: una etiqueta,
256 bytes, nada más. No hay coordenadas en el contrato, y es lo que evita el fallo en el
que caen los modelos de visión.

El repertorio de BAXY para el bucle queda en lo que ya existe:

| Acto | Operación |
|---|---|
| pulsar lo que se ve | `input.visible.click` (etiqueta) |
| escribir | `input.key.press` |
| enfocar / mover ventana | contratos de ventana |
| abrir la aplicación | `app.open` |
| mirar | lectura de pantalla (UIA, OCR) |
| terminar | decir lo que ve y parar |

## 3. Lo que falta es el bucle

Hoy un turno propone un puñado de operaciones, la raíz las aprueba de una vez y se
ejecutan. No hay ciclo. El bucle es: **mirar → elegir un acto → ejecutarlo → volver a
mirar**, hasta llegar al objetivo o hasta ver que no se llega.

Reglas del bucle, y por qué cada una:

- **Cada paso conserva su aprobación y su postlectura.** Un bucle multiplica las
  decisiones; multiplicar también las revisiones es lo que impide que un clic equivocado
  se encadene. Es además lo que miden los bancos de seguridad de agentes de ordenador
  (OS-Harm): el daño no viene del acto aislado, viene de la cadena sin freno.
- **Un clic sólo cuenta si la superficie cambió.** Ya es el criterio del instrumento de
  interfaz de esta campaña (`controlGoneAfterClick`, verificación de cambio de
  superficie). Pasa a ser la postlectura de cada paso del bucle.
- **Presupuesto de pasos y regla de parada.** Si la pantalla no cambia tras un acto, o el
  modelo elige dos veces el mismo control, el bucle para y BAXY dice qué ve. Terminar
  diciendo la verdad es un final válido; dar vueltas no lo es.

## 4. Especializado para Qwen3-4B

El modelo que corre aquí tiene 4096 de contexto y temperatura cero. Eso manda sobre el
diseño más que cualquier otra cosa:

- **El árbol se filtra, no se vuelca.** Los trabajos publicados le dan al modelo el árbol
  entero; aquí no cabe. Se le dan como mucho ~40 controles, sólo los visibles, habilitados
  y con nombre, uno por línea y en una línea corta: `id · tipo · nombre`. Todo lo demás
  sobra y, peor, empuja fuera del contexto lo que importa.
- **Una pregunta por paso, no un plan.** A un modelo de 4B no se le pide que planifique
  cinco actos: se le pide *uno*, con los controles delante y el objetivo escrito.
- **«Ninguno de estos» es siempre una opción explícita.** Sin esa salida, un modelo
  pequeño elige el control menos malo con tal de contestar algo. Con ella, puede decir que
  no ve por dónde seguir, que es la respuesta honesta y la que esta campaña acredita.
- **Temperatura cero es una ventaja, no una limitación.** La misma pantalla da el mismo
  acto, así que un fallo se reproduce y se repara. Toda la campaña depende de eso: la
  lección de hoy, cuatro veces, es que lo que no se reproduce no se arregla.

## 4b. Medido en Steam: el árbol de accesibilidad puede estar vacío

El diálogo de instalación de Steam se abrió y se leyó con la lectura nueva. UIA devuelve
**un solo nodo, «Chrome Legacy Window», sin un solo hijo**. Se pidió dos veces, por si
Chromium activaba su árbol bajo demanda tras la primera petición; no lo activa.

La interfaz de Steam —y la de Epic y la de Discord, que son de la misma familia— es
Chromium incrustado. Para ellas **el canal que los papers miden como el mejor no existe**,
y manda la cascada de OCR que el clic ya tiene detrás de UIA. Es el caso inverso al de una
aplicación nativa como la Calculadora, donde UIA lo da todo.

De aquí salen dos consecuencias para el bucle:

- **La lectura de controles tiene que decir cuándo no ve nada.** Un único nodo contenedor
  no es una pantalla sin controles: es una pantalla que este canal no sabe leer. El bucle
  debe pasar a OCR en ese caso, no concluir que no hay nada que pulsar.
- **Un paso puede necesitar más de un clic.** El diálogo de DOOM Eternal viene con la
  unidad por defecto (C:, 54,62 GB libres) para un juego de 89,52 GB: completarlo de
  verdad exige elegir antes otra unidad. La fila que dice «completalo haciendo click en
  instalar» no se cumple con un clic, y el criterio tiene que decirlo.

## 4c. Medido en Netflix: un navegador conducido no puede reproducir DRM

Con la sesión del dueño sembrada en el perfil de BAXY, se condujo el navegador por CDP
paso a paso. El camino entero quedó a la vista:

1. Netflix enseña **«¿Quién está viendo ahora?»** con los cinco perfiles de la casa. Sin
   elegir uno no hay búsqueda. Pulsar el primero funciona.
2. La búsqueda **ya no da enlaces `/title/`**: cada resultado es un `<a data-uia=
   "standard-card">` cuyo href lleva `jbv=<id del vídeo>`. Buscando sólo `/title/`, lo
   único que aparecía eran las notificaciones del menú, que es exactamente por qué el
   contrato decía «título no encontrado».
3. Con el id se llega al reproductor, y ahí se acaba el camino: **la página del
   reproductor no crea ningún elemento `<video>`**, ni en el documento ni en ningún shadow
   root. Lo único que queda en pantalla es el botón «Regresar a Explorar», que es la
   página de error de Netflix.

La causa está medida, no supuesta: **`navigator.webdriver` vale `true`**. Un navegador
abierto con puerto de depuración se declara automatizado, y las plataformas con DRM se
niegan a reproducir en esa condición. No es el `--disable-gpu` —aunque ése también deja la
página en blanco y hay que quitarlo para streaming—, ni la sesión, ni el título.

**Consecuencia para las 24 filas de vídeo.** El contrato por CDP puede iniciar sesión,
elegir perfil, buscar y llegar al reproductor, pero **nunca podrá verificar que el vídeo
avanza**, porque el vídeo no va a empezar. La única vía que queda es la que pidió el
dueño: computer use sobre una ventana normal del navegador, conducida con ratón y teclado
de verdad, donde `navigator.webdriver` es falso y la página no distingue a BAXY de una
persona.

Eso mueve el bloque de vídeo entero del contrato al bucle, y con él la parte del diseño
que decía que el árbol de accesibilidad bastaba: para una página web conducida a mano hará
falta leerla por su propio árbol, no por UIA.

## 5. Lo que este diseño no resuelve

- **Las sesiones.** Que BAXY sepa pulsar «Reproducir» no le da la cuenta de Netflix. El
  perfil de navegador con sesión iniciada es un requisito aparte y lo pone el dueño.
- **El DRM.** El navegador que BAXY levanta corre sin GPU; Netflix y Disney+ pueden
  negarse a reproducir por eso aunque la sesión esté puesta. Hay que medirlo antes de
  prometer las 24 filas.
- **Lo que no está.** Among Us no está instalado: ningún bucle lo va a encontrar. Ahí lo
  correcto es mirarlo y decir que no está, que es lo que el dueño pidió.

## 6. Corrección con la biblioteca: el estorbo del vídeo no es el webdriver, es Widevine

El 19-09, antes de buscar en la biblioteca, esta campaña concluyó que Netflix rechazaba
la reproducción porque el navegador conducido expone `navigator.webdriver: true`. La
generación anterior ya había investigado esto entero y dice lo contrario, con fuentes:

> «None of Netflix, Disney+, HBO Max, or Prime Video aggressively fingerprint
> Playwright/CDP for *playback* purposes (the dominant blocker is Widevine, which is
> upstream of fingerprinting).» […] «`navigator.webdriver === true` is set when CDP is
> attached, and some sites read it. **None of the four streaming platforms gate playback
> on this flag**.»
> — `biblioteca/gemma4-agent/documentacion/04_computer_use/streaming_playback_field_guide_2026.md`

Lo que sí bloquea, según esa guía:

1. **Widevine.** El navegador tiene que ser un Chrome o Edge **real y firmado**. Un
   Chromium empaquetado no trae el CDM y Netflix devuelve M7701-1003 / M7121-1331. El
   adaptador de BAXY ya levanta `msedge.exe` real, de modo que este requisito se cumple.
2. **La sesión.** El perfil del navegador que BAXY levanta es el directorio de datos del
   turno: con un perfil nuevo por caso —que es lo que exige la medición— nunca hay
   sesión iniciada. Es el estorbo estructural, no el DRM.
3. **`--disable-gpu`.** Se añadió para no pasar del techo de memoria (WEB1261). La guía
   no lo nombra, pero la ruta de medios protegidos puede depender de la GPU: es lo
   primero que hay que medir cuando haya una sesión.

Y su veredicto de arquitectura, que es la respuesta a «cómo se hacía esto bien»:

> «**Use Architecture B (attach to a real, signed Google Chrome started with
> `--remote-debugging-port=9222`) as the primary path.**» — login gratis, Widevine
> funciona, misma huella que el usuario. El coste: Chrome tiene que arrancar con el
> puerto, y no puede haber otra instancia usando ese mismo perfil.

Con eso, la ruta del vídeo deja de ser OCR a ciegas: se conduce por DOM, con selectores
que la guía ya fijó —`[data-uia="search-title-card"]` y `[data-uia="play-button"]` en
Netflix, `/search?q=` que sí existe allí y no en Disney+—. Para Disney+ la guía advierte
que no hay URL de búsqueda con parámetro y que hay que escribir en el campo; y avisa de
lo que aquí se acababa de tropezar: «Avoid OCR — exactly the failure mode the user
already identified».

La palanca que la guía marca como la de mayor rendimiento es una caché de
«título → URL»: la primera vez que se reproduce algo se guarda la URL final, y a partir
de ahí se va directo sin buscar.

## 7. Medido el 19-09 con la sesión puesta: Netflix reproduce

El dueño inició sesión en el perfil compartido del navegador de BAXY. Con eso, y con
`streaming.play.named` añadida a la lista de operaciones que el revisor de la raíz puede
confirmar, la fila «pon stranger things en netflix» llegó hasta el final:

```
streaming.play.named     → completada y verificada
playbackStatus           → playing
observedProgressSeconds  → 0,70
finalUrl                 → https://www.netflix.com/watch/80077368
authority                → netflix_cdp_video_progress_postread
```

Es decir: **el DRM no era el problema**. Con el perfil persistente, Widevine se instala
como componente —la carpeta `WidevineCdm` aparece en el perfil— y Edge reproduce. Lo que
bloqueaba las 24 filas era que el perfil moría con el turno.

### Lo que falta, con su síntoma exacto

1. **El buscador de títulos es intermitente.** De nueve corridas, tres llegaron a
   reproducir y el resto terminaron en `netflix_title_or_play_control_not_found` tras
   agotar los 240 intentos (60 s). El patrón sospechado —un Edge vivo sobre el perfil
   compartido— explicaba parte, pero no todo: hubo fallos con el perfil limpio. Lo que
   cambia entre una corrida y la siguiente es el estado en que queda Netflix después de
   reproducir. Hay que mirar la página en el momento del fallo antes de tocar el JS.
2. **El final no se redacta.** Con la reproducción verificada, la composición agota los
   tres borradores y el turno termina en `composition_failed`. El primer borrador que
   registra la auditoría es de la confirmación, no del resultado; falta ver qué payload
   recibe el redactor tras el éxito.
3. **Disney+ no está en el catálogo.** `streaming.navigate` acepta netflix, prime_video y
   youtube; `streaming.play.named`, sólo netflix. Diez de las veinticuatro filas son
   Disney+, y la guía de la biblioteca advierte que allí no hay URL de búsqueda con
   parámetro: hay que escribir en el campo.

### Higiene que la tanda tendrá que hacer

Cada caso mide en un perfil nuevo de BAXY, pero el perfil del navegador ahora es
compartido a propósito. El paso de la raíz tendrá que cerrar los Edge que queden sobre
ese perfil antes de cada caso, igual que hoy cierra los clientes de mensajería.

## 8. Tres tandas de vídeo, y la orden del dueño sobre lo mal dicho (2026-09-19/20)

**Lo que cerró.** VIDEO1919 (14 casos), VIDEO1921 (6) y VIDEO1923 (6) llevaron «Vídeo y
series» de 2/26 a 11/26 y la cobertura de 709 a 718/742. En las tres, cada reproducción
aprobada por la raíz se verificó viendo avanzar el vídeo en el reproductor: llegar a la
página no cuenta.

**Los tres pendientes de §7, resueltos.** (1) El buscador «intermitente» no lo era: lo que
variaba entre corridas era el punto en que Netflix reanuda la serie, y la comprobación
exigía que la página repitiera el título, que a 1:51 de metraje ya no está en pantalla.
(2) El final que no se redactaba: el guardián del nombre sólo admitía las operaciones de
transporte de medios; ahora admite ésta. (3) Disney+ sigue fuera del catálogo; queda como
tanda propia con tres capas (catálogo, adaptador, mente).

**La orden del dueño, 2026-09-19.** «Baxi debe de arreglar las cosas que el usuario diga
mal. Porque lo más probable es que nuestro modelo de transcripción no sea tan bueno.» Es
decir: la errata suele ser del oído de BAXY, y cobrársela a la persona es un defecto. Lo
que se hizo, y por qué no fue una búsqueda web encima:

- La búsqueda de Netflix **ya es difusa**. El adaptador, después de buscar, exigía que la
  tarjeta contuviera literalmente lo pedido y tiraba la corrección que el servicio acababa
  de dar. Ahora se queda con lo que Netflix pone arriba. Pidiendo «stranger thins» se
  reproduce Stranger Things.
- La prueba de que se abrió lo pedido es la **ficha elegida**, no el texto de la página.
  Medido: la ficha de Stranger Things es la 80057281 y el reproductor acaba en 80077368
  —la serie y el episodio al que Netflix redirige—; exigir el id en la URL rechazaba una
  reproducción correcta. Y un título traducido («Wednesday» → «Merlina») ya no se
  descarta.
- El recibo dice **el título observado**, y el final lo nombra: la persona ve la
  corrección en vez de que se le oculte. Eso es lo que la identidad exige.
- Los argumentos salen del pedido: el extractor literal no tenía entrada para esta
  operación, y el planificador, a ciegas, preguntaba «¿qué servicio y qué título?» con
  los dos escritos delante. Se probó también una habilidad de planificador y se retiró:
  en la ruta del esqueleto cerrado no se lee. Ley 2.

**Dos lecciones de instrumento.** El revisor de la raíz llevaba un solo título fijado para
doce casos y rechazó la propuesta fiel de un título mal escrito: defecto del instrumento,
no del producto (VIDEO1919, dos casos). Y una variante verificada contra el lector y no
de extremo a extremo dejó una tanda entera sin crédito (VIDEO1921): las variantes se
prueban de extremo a extremo antes de sellar.

**Lo que sigue en vídeo (15 filas).** H0355/H0377 («stranger thins») reproducen bien pero
su final salió inestable; H0737 («nerflix») acaba preguntando pese a que en frío todo lo
determinista lo acepta (APLAZADOS); H0010 sin título; diez de Disney+ y una de Prime
Video, sin servicio en el catálogo; dos ininteligibles.

## 9. VIDEO1925 y el muro de Disney+ (2026-09-20)

**H0010 «prende algo en netflix».** Sin título no hay qué poner; la regla común de la encuesta
es preguntar únicamente por lo que falta. BAXY contestaba «¿Quieres que reproduzca un video en
Netflix?», un sí o no que no pedía nada. Ahora pregunta por el título y sólo por él, en el
idioma del pedido. Seis de seis, 719/742.

**Disney+ (diez filas) tiene el recorrido medido y un muro delante.** Con la sesión del dueño:
la búsqueda no admite `?q=` (la biblioteca tenía razón), vive en `/browse/search` y se
escribe en `#searchInput`; las fichas son `a[data-testid="set-item"]` hacia
`/browse/entity-<id>` con el título en el `aria-label`; la ficha ofrece
`a[data-testid="playback-action-button"]` hacia `/play/<id>`. Y ahí el `<video>` se queda
sin fuente, sin error, tráiler incluido, también a mano y sin depuración. La causa la
sospechó el dueño y la medición la confirmó: en el perfil de BAXY, Widevine sólo concede
`SW_SECURE_CRYPTO` y rechaza `SW_SECURE_DECODE`; PlayReady 2000/3000 sí. Netflix se
conforma; Disney+ no. Es el módulo de descifrado del perfil, no BAXY, y la comprobación
siguiente es del dueño: si Disney+ reproduce en su Edge normal, y si el módulo Widevine
del perfil de BAXY está actualizado.

**Lección del método, dos veces en un día.** Una variante verificada contra el lector y
no de extremo a extremo dejó VIDEO1921 sin créditos; desde entonces cada variante se
prueba de extremo a extremo antes de sellar. Y una habilidad de planificador escrita para
«start …» no hacía nada —en la ruta del esqueleto cerrado no se lee— mientras una entrada
en el extractor literal lo arreglaba; se midió con y sin, y la habilidad se retiró.

## Fuentes

- [OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments](https://arxiv.org/html/2404.07972v2)
- [OS-Harm: A Benchmark for Measuring Safety of Computer Use Agents](https://arxiv.org/html/2506.14866v1)
- [Agent S: An Open Agentic Framework that Uses Computers Like a Human](https://arxiv.org/pdf/2410.08164)
- [Agent S2: A Compositional Generalist-Specialist Framework for Computer Use Agents](https://arxiv.org/pdf/2504.00906)
- [Structuring GUI Elements through Vision Language Models: Towards Action Space Generation](https://arxiv.org/html/2508.16271v1)
- [AgentCPM-GUI: Building Mobile-Use Agents with Reinforcement Fine-Tuning](https://arxiv.org/pdf/2506.01391)
