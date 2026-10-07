# Computer use universal — progreso (Fase 4, goal 2026-10-06)

Goal: `documentacion/GOAL_COMPUTER_USE_2026-10-06.md`. Rama `fable/computer-use-universal` (worktree
`%LOCALAPPDATA%\BAXY\cu-universal-wt`), base `codex/kiro-goal-c03`. Evidencia de misiones en vivo fuera del repo:
`%LOCALAPPDATA%\BAXY\cu-universal-evidencia\<misión>`; perfil de prueba `%LOCALAPPDATA%\BAXY\cu-universal-perfil`.

## Hecho

| Paso | Estado | Commit |
|---|---|---|
| Fusión de `fable/computer-use-engine` (13 conflictos de contenido) | hecho; Kernel 207/207, Providers 950/950 | 6cb48f77 |
| Clic: worker UIA del motor + atadura M132 a la ventana recién abierta; `DesktopClickVisible.ps1` retirado | hecho | 6cb48f77 |
| Mente: ganchos del motor portados a `semantic/patterns.py`, `semantic/arguments.py`, `__main__.py` | hecho; `tests/test_computer_use.py` 16/16 | 6cb48f77 |
| Enrutado: pestañas → misión en «navegador»; verbos en cualquier persona; `close_all` confirmado | hecho; Kernel 212, Providers 963, Integración 2430 (1 skip) | 444ebd47 |
| CEF/Steam: tapada al abrir, menú, llegada `page:`, OCR multipalabra, paso robusto | hecho | 88ab1432, d33f709e |
| Procedimientos: no se aprende con pasos fallidos; se reproduce sólo sobre la ventana de la app | hecho | 9afbef63 |
| Contrato de paquete ordenado (Setup 477/477); MEDICIONES.md (cobertura, latencia, procedimientos) | hecho | 1425cf71 |
| Prioridad: lo tipado gana salvo primitivas de la misión; verbo suelto → decisor; finales en 1.ª persona | hecho; pytest 9272 (84 ficheros) | c727f1cf |

## Decisiones (criterio por defecto)

- Misión 2 («cerrá todas las pestañas del navegador») va por `browser.control close_all` —el catálogo ya la tenía,
  declinada sólo porque `RiskPolicy` no ligaba la confirmación a un argumento; el motor trajo `RiskPolicy` por
  argumentos—. Cierre pestaña a pestaña con el camino medido en Opera GX (clic central) y relectura del marco.
- Misión 7 («ve a la pestaña de YouTube») va al motor: aplicación = categoría «navegador», que el provider resuelve a
  la ventana delantera del navegador predeterminado (`UserBrowser*`). Sin código por navegador.
- Las misiones en vivo corren con el conductor de la App (`Baxy.exe --conductor`, mismo turno que la UI); la
  confirmación es el turno siguiente («sí»).

## Misiones en vivo

| # | Pedido | Resultado | Pasos | Latencia | Nota |
|---|---|---|---|---|---|
| 1 | ve a Cotele en Discord → «no» | **lograda** — «He encontrado el canal de voz "Cotele!!!??" en el servidor Choche… pero no me he unido. ¿Quieres que lo haga?» → «no» → no se unió | ruta tipada `client.channel.locate` (catálogo) | 17 s | intento 1 por el motor: el 4B pulsó 6 veces sin hallar el canal → la ruta tipada del catálogo ya no la engloba la misión |
| 2 | cerrá todas las pestañas del navegador → «sí» | **lograda** (intento 2) — pide confirmación; «Cerré cuatro pestañas; queda una abierta.»; Opera con 1 pestaña (UIA) | `browser.control close_all` (4 cierres releídos) | 13 s tras el «sí» | intento 1: «GX Corner» no se cierra como activa y el final calló las 3 cerradas → respaldo por otra pestaña + final con la cifra (e9139d30) |
| 3 | abre Steam y ve a la biblioteca | **lograda** (intento 8) — captura: BIBLIOTECA resaltada, «Tus colecciones» | 2 (clic «biblioteca» → menú; clic en su entrada) | misión 9,3 s (modelo 4,6 s) | 7 intentos fallidos enseñaron 6 arreglos generales (ventana tapada al abrir, contención sólo en ítems con título, OCR de varias palabras, menú abierto por el clic, llegada `page:`, paso ilegible). Falsos éxitos/negativos medidos y corregidos |
| 4 | en Discord apretá enter | **lograda** — Enter pulsado en el MD de prueba Ron92, nada enviado (captura) | 1 (tecla dictada) | misión 2,9 s, turno 4,6 s | final «…y vi que la acción se completó» → compositor: con una tecla sólo «Pulsé Enter» |
| 5 | abrí Configuración y activá el modo avión | **lograda** — «Activé el modo avión y se apagó el Bluetooth.»; radio Bluetooth leída `Off`; revertido con «desactivá el modo avión» → `On` | ruta tipada `system.settings.set` (D21: Windows lo verifica mejor que la pantalla) | 1,6 s | Configuración ya estaba abierta (del dueño), no se tocó |
| 6 | en la calculadora calculá 12×7 | **lograda** — la Calculadora muestra «84», expresión «12 × 7=» (UIA independiente) | 2 (escribir `12*7`, Enter; dictados sin modelo) | 41 s el turno (misión 35,9 s) | final en 3.ª persona → arreglado (c727f1cf); procedimiento aprendido |
| 7 | ve a la pestaña de YouTube | **lograda** — Opera GX: `TabItem «(126) YouTube» [selected]` (UIA independiente) | 2 (traer el navegador, clic en la pestaña) | misión 4,9 s | aplicación «navegador» → ventana delantera del predeterminado |
| 8 | pon La Casa del Dragón en HBO Max | **lograda** — Opera GX reproduce un episodio (`play.hbomax.com/video/watch/…`, pestaña con sonido, subtítulos de la serie) | ruta tipada `streaming.play.named` | 23 s | sesión de Opera del dueño respaldada antes y restaurada byte a byte después |
| 9 | abrí el Reloj y andá a Cronómetro (UWP que BAXY no conoce) | **lograda** — `ListItem Cronómetro [selected]` (UIA independiente) | — | 35 s el turno | final fiel: «Fui al Cronómetro y vi que estaba pausado a las 96 horas…» (el cronómetro del dueño lo mostraba) |

## Cierre

- Misiones: **9/9 logradas y verificadas** en vivo (más Win32 extra: Panel de control → «Sistema y seguridad», y
  humo tras mover el lector a `semantic/missions.py`: Calculadora «84»).
- Compuerta Full verde (e46afeaf): Contracts 70, Integration 2431 (+1 skip ambiental: pruebas opt-in de runtime
  real), Kernel 212, Providers.Windows 963, Setup 477, pytest 18 735.
- Mediciones: `MEDICIONES.md` (cobertura por tipo de app, latencia por paso, ahorro de procedimientos).
- Estado del PC devuelto: volumen 60 y brillo 40 como al empezar; modo avión revertido; Steam, Discord, Opera,
  Reloj, Calculadora y Panel de control abiertos por las pruebas, cerrados; sesión de Opera del dueño restaurada
  byte a byte desde la copia previa.

## v2 (2026-10-07): universal, encadenado, rápido

Pedido del dueño (00:10): que BAXY use el PC como una persona, en cualquier app, con misiones encadenadas, rápido y
con calidad; plazo 13:00. Rama `fable/cu-universal-v2`. Análisis (fase A): el tiempo era sobrecoste de BAXY (UWP 30 s,
PowerShell por tecla, esperas fijas, finales y progreso por LLM, paso del modelo con 148 tokens), y la universalidad
fallaba por un solo acto por pedido, sin búsqueda dentro de la app ni objetivos libres.

| Cambio | Commit |
|---|---|
| Paso del modelo con gramática de acto primero (4 s → 0,2–0,7 s medido en llama-server) | bf38d6b4 |
| Mente: BUSCAR universal, encadenado `steps[]`, objetivos libres, guardas, nombres bilingües | 9ff5b4fc |
| Último recurso: una orden sobre el PC sin operación la intenta el motor | df446de1 |
| Vista para el modelo: 30 controles por el objetivo + «N de M» | 2a6b2c3e |
| Provider (agente A): UWP por su marco, teclas en proceso, clic rápido, worker precalentado, scroll por control | merge 8177a776 |
| App/Kernel (agente B): sub-objetivos, esperas de 150 ms, OCR a demanda, guardas, política ampliada | merge cbbf199c |
| Arreglos medidos en vivo: escritorio no es ventana de app; espera de arranque; ventana elevada; page: contra la vista previa al clic; clic físico si no se invoca; límite no anula misión | ea14333b, b396dfe8, fa009cf1 |
| «abrí X» dentro de una app es ir a X; la cláusula interior sólo se pesa contra el catálogo en activar/desactivar | a6c10401 |
| Dos falsos éxitos cerrados: `page:` sólo en ventanas sin árbol; la misión probada no la anula el veto de conservación; procedimiento rancio se abandona | 165aa153 |
| BUSCAR sigue con el buscador tras pulsar algo que nombra el destino sin llegar | e8a6a560 |
| Texto con la grafía dicha; «mandalo» es enviar; cursor en el campo antes de escribir; el eco no prueba llegada; tecleo por carácter | 2e06fa28 |
| Enviar lo escrito siempre se pregunta antes (Enter en un campo de mensaje ilegible cuenta como envío) | 3ae1dc88 |
| Tecleo a 3 ms por carácter (luego 35 ms: 5ac16f90) | e04bc54b |
| Un clic en el nombre del lugar que deja la ventana igual: ya estaba ahí (retirado en la revisión: 8f61d456) | e4254ef6 |
| Una ventana elevada encontrada es la app abierta (`QueryFullProcessImageName`; s06: 30 s → ~1 s) | d3939711 |
| La dirección escrita de una página sin árbol nombra dónde está (Steam en store.steampowered.com) | 4149e598 |
| Composición fallida: frase honesta en el idioma de la persona, no «⚠ (código)» | 43060a1e, ecb80d30 |
| «andá a Documentos y creá una carpeta llamada X» por la ruta tipada (c3) | 14b8e238, f311d3be |
| Lector de misiones: crear, renombrar, buscar, elegir, reproducir, copiar/pegar, direcciones, cada una con su comprobación; segunda tanda no vista 28/28; verbo con pronombre no se pega al nombre | 5937a9f8, d58dccbf, 19eacf1f, 46702f23 |
| Capturas de ventana en memoria (75 → 8 ms); abrir una ventana de un proceso que ya corría no es un lanzamiento (s04) | c0123a16 |
| El eco de lo tecleado sólo descarta un control si se tecleó en una búsqueda o una dirección | ee5b5c18 |
| Un clic por identidad prueba que la app abierta está dibujada (u3: 26 s → sin espera); arranque medido por lo accionable (Spotify) | 9c3f600d, c19115cd |
| Un clic verificado en el control que abre el lugar llega a él («Abre Tu biblioteca», Spotify) | f00da879 |

### Seguridad v2

Revisión de seguridad del 2026-10-07, sobre lo que el motor puede pulsar o escribir sin que la persona lo vea venir.

| Cambio | Commit |
|---|---|
| La ventana de la aplicación se reconoce por su proceso, su ejecutable o el último segmento « - » del título como palabras enteras; nunca VS Code, Visual Studio, un editor, una terminal, una consola o BAXY no nombrados (medido: «SteamLocalAdapter.cs - … - Visual Studio Code» era la primera ventana titulada «Steam») | fdd0b381, 2a98304a |
| Teclas y texto atados a la ventana de la misión (`window`): el provider la trae al frente o no envía nada, también al confirmar tras el «sí» con BAXY delante; escribir se para si la ventana pierde el frente o se cancela; si la vista no es la ventana de la app nombrada, nada se pulsa ni se escribe (`computer_use_window_not_application`); un texto con salto de línea o tabulador se rechaza | 4e60cbec, 2cc6bd9a |
| Enter o espacio sobre enviar/responder/comentar, o sobre un campo sin nombre que no expone su valor, llevan `target: message_composer` y preguntan; Suprimir sólo va directo con `target: text_field`, fuera de un campo de texto pregunta | 2a98304a, f54d657a |
| `RiskPolicy`: enviar, reenviar, invitar o responder abren la etiqueta sea lo que siga; un verbo destructivo (no guardar, descartar, papelera, quitar, vaciar, limpiar, eliminar, desinstalar) en una etiqueta de ≤ 6 palabras pregunta; las etiquetas se pliegan sin caracteres de formato ni la pista «(Ctrl+…)» | f54d657a |
| Ninguna entrada al motor (lector, objetivo libre del decisor, último recurso) toma una meta que quita, descarta, tira a la papelera, cancela o contrata una suscripción, alquila, dona, vende, restablece, limpia, vacía o sale de un servidor | 29ef7ca9 |
| Ir a un lugar nunca pulsa un interruptor (casilla, opción, conmutador, deslizador, o un control on/off): `changes_a_setting` (medido: buscando «Colores» el modelo pulsó «Invertir colores» de la Lupa) | 72093a4a |
| El modelo no pulsa un control que abre otra pestaña o ventana si el objetivo no lo pide (`opens_elsewhere`) | 15920d7f |

### Correcciones de la revisión

Falsos éxitos y esperas halladas al repasar el banco; cada una con su prueba de unidad.

| Cambio | Commit |
|---|---|
| Lo tecleado se juzga en pantalla, nunca por los recibos de las teclas; un valor cortado (120 caracteres) es desconocido; lo que un campo contiene no prueba llegada; una ventana igual tras el clic no es llegada (la página puede no estar dibujada aún) | 8f61d456 |
| Tecleo a 35 ms por carácter (medido en el Bloc de notas de Windows 11: a 3 ms «lista: pan» salía «lista:nnnn», a 20 ms «lista:ppan», desde 25 ms íntegro); «escribí X» sólo cuenta si el campo muestra X | 5ac16f90, 4e60cbec |
| Llegar por un clic exige que la página cambie (≥ 40 % de controles nuevos) y que la selección no se haya movido a otro elemento (s04: «Imágenes» elegida; c5: tarjeta «Colores» con Personalización a la vista); un valor elegido dentro de la página alcanzada no la desmiente | c40a2658, 13b62ac3 |
| El encabezado de la página nombra dónde está (Configuración: «Personalización > Colores») | 72093a4a |
| Clics aprendidos fijados por identidad al único control de la vista con su nombre (u7 Reloj → Alarma: 30 s → 0,3 s); tras un clic fallido el paso se busca de nuevo por identidad, nunca el mismo acto; el menú que abrió el clic en el lugar sigue valiendo | c40a2658, b05e5b3b, e63c00a1, 66c9e6e0 |
| Navegador: la dirección se confirma con Supr antes de Enter (autocompletado del historial, c4); la búsqueda y los resultados son los de la página, no la búsqueda de pestañas ni los marcadores del marco; sin `ctrl_k`; la mente recibe los rectángulos y una página que aún carga se vuelve a mirar (6 × 400 ms) | 15920d7f, 02cc24cb |
| Un buscador con texto previo se selecciona entero (`ctrl_a`) antes de escribir (Configuración: «colorespantalla») | 13b62ac3 |
| El final ve primero los valores y estados elegidos que comparten palabras con lo pedido, el valor antes que el ítem (c5: «Oscuro») | 3151339b, c40a2658 |
| Ventanas sin árbol: el buscador escrito se pulsa por su línea OCR (WhatsApp); los botones de la barra de título no son contenido; una app que arranca se espera hasta 20 s y la postlectura del clic por texto mira hasta 1,5 s (Epic) | 3151339b, 35cef19d, bfba63d0 |
| Crear o renombrar exige el nombre entero (`control:=X`) y lo tecleado; buscar exige un Enter o un clic en la sugerencia; «poné la primera», un clic que reproduce | c061bcdb, a4d5fb10 |

### Banco en vivo (última corrida de cada caso; verificación independiente)

Misión = `ms` de `computer_use.end`; turno = `latency_ms` del final. El primer turno de cada corrida incluye el
arranque en frío de la App (≈ 5–8 s de bienvenida); en caliente, turno ≈ decisión 0,5–0,7 s + misión + final 1–2 s.
Pedidos completos, corridas anteriores y comparación con la fase 4: `MEDICIONES.md` §«v2».

| Caso | Pedido | Resultado | Misión / turno | Antes |
|---|---|---|---|---|
| s01 | Calculadora 37*12 (cerrada) | **logrado** — «444» | 3,1 / 8,7 s (App en frío) | fase 4: turno 41 s |
| s02 | Reloj → Cronómetro | **logrado** | 2,3 / 4,2 s | fase 4: turno 34,9 s |
| s03 | Configuración → Bluetooth y dispositivos | **logrado** (ya estaba) | 0,4 / 2,4 s | — |
| s04 | Explorador → Descargas | **logrado** | 12,7 / 15,4 s | éxito falso, corregido |
| s05 | Panel de control → Programas | **logrado** | 2,9 / 4,9 s | fase 4: 7,5 s («Sistema y seguridad») |
| s06 | Administrador de tareas → Rendimiento | **límite honesto** — ventana de administrador | 4,5 s | 34 s |
| s07 | Paint → herramienta Texto | **logrado** | 3,9 / 6,1 s | — |
| s11 | Discord → canal Cotele | **logrado** | 1,0 / 2,9 s | fase 4: el motor falló; ruta tipada 17,2 s |
| s12 | Steam → biblioteca | **logrado** | 3,4 / 5,5 s | fase 4: turno 11,2 s |
| s14 | Discord «mandale a Ron92 …» → «no» | **logrado** — pregunta antes de enviar; «no» cancela | — | — |
| c1 | Bloc de notas «lista: pan», Enter, «leche» | **logrado** — texto verificado en el editor | 4,1 / 6,7 s | lista corrupta dada por lograda |
| c2 | Calculadora 12*12 → copiar → pegar en el Bloc de notas | **logrado** — «144» en el editor | 6,1 / 8,5 s | — |
| c3 | Explorador → Documentos y crear carpeta baxy-prueba | **logrado** (ruta tipada) | 3,3 s | el plan no llegaba |
| c4 | Opera: pestaña nueva → es.wikipedia.org → buscar Ñuñoa → Historia | **fallido** — 2/4 sub-objetivos (autocompletado de la barra); arreglo integrado sin probar en vivo | — | — |
| c5 | Configuración → Personalización → Colores + «decime si el modo es claro u oscuro» | **logrado** — «Oscuro» | 2,3 / 4,9 s | — |
| c6 | Discord chat Ron92, escribir y mandar → «sí» | **logrado** — pregunta; «sí» envía | — | — |
| c7 | Discord canal Cotele y después Steam tienda | **logrado** | 6,4 / 8,0 s | falso negativo |
| u1 | Spotify → biblioteca | **logrado** | 19,3 / 22,5 s (Spotify en frío) | — |
| u2 | Microsoft Store → Juegos | **logrado** | 14,2 s (vista UIA de 4 s) | — |
| u3 | Fotos → Favoritos | **logrado** | 4,8 / 6,8 s | — |
| u4 | Epic Games → biblioteca | **fallido** — pantalla de carga larga, clic por texto sin efecto | — | — |
| u5 | Excel → libro en blanco | **logrado** | 12 s | — |
| u6 | WhatsApp → un chat | **fallido** — el texto no llega al buscador | — | — |
| u7 | Reloj → Alarma | **logrado** | 3,0 / 4,7 s | 33 s (clic aprendido sin identidad) |
| u8 | Configuración → Sistema → Pantalla | **logrado** | 4,4 / 6,1 s | — |
| u9 | Spotify «go to Search» (inglés) | **logrado** | 8,7 / 10,7 s | — |

Total del banco principal (24 casos; u2 y u5 son extras que pasaron en su primera corrida): **21/24 correctos** (s06 cuenta como límite honesto correcto), 3 fallos (c4, u4, u6).
Corpus del lector: 165 órdenes es/en → 161 misiones verificables + 4 cubiertas por la ruta tipada (D21).

Pendiente: re-correr c4 en vivo con el Supr de la barra de direcciones; Epic (u4: carga larga) y WhatsApp (u6: el
texto no llega al buscador) quedan como límites medidos.
