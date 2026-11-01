# Computer use universal — progreso (Fase 4, objetivo 2026-10-06)

Objetivo: `documentacion/OBJETIVO_COMPUTER_USE_2026-10-06.md`. Rama `fable/computer-use-universal` (worktree
`%LOCALAPPDATA%\BAXY\cu-universal-wt`), base `codex/kiro-objetivo-c03`. Evidencia de misiones en vivo fuera del repo:
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
| 5 | abrí Configuración y activá el modo avión | **lograda** — «Activé el modo avión y se apagó el Bluetooth.»; radio Bluetooth leída `Off`; revertido con «desactivá el modo avión» → `On` | ruta tipada `system.settings.set` (D21: Windows lo verifica mejor que la pantalla) | 1,6 s | Configuración ya estaba abierta (del autor), no se tocó |
| 6 | en la calculadora calculá 12×7 | **lograda** — la Calculadora muestra «84», expresión «12 × 7=» (UIA independiente) | 2 (escribir `12*7`, Enter; dictados sin modelo) | 41 s el turno (misión 35,9 s) | final en 3.ª persona → arreglado (c727f1cf); procedimiento aprendido |
| 7 | ve a la pestaña de YouTube | **lograda** — Opera GX: `TabItem «(126) YouTube» [selected]` (UIA independiente) | 2 (traer el navegador, clic en la pestaña) | misión 4,9 s | aplicación «navegador» → ventana delantera del predeterminado |
| 8 | pon La Casa del Dragón en HBO Max | **lograda** — Opera GX reproduce un episodio (`play.hbomax.com/video/watch/…`, pestaña con sonido, subtítulos de la serie) | ruta tipada `streaming.play.named` | 23 s | sesión de Opera del autor respaldada antes y restaurada byte a byte después |
| 9 | abrí el Reloj y andá a Cronómetro (UWP que BAXY no conoce) | **lograda** — `ListItem Cronómetro [selected]` (UIA independiente) | — | 35 s el turno | final fiel: «Fui al Cronómetro y vi que estaba pausado a las 96 horas…» (el cronómetro del autor lo mostraba) |

## Cierre

- Misiones: **9/9 logradas y verificadas** en vivo (más Win32 extra: Panel de control → «Sistema y seguridad», y
  humo tras mover el lector a `semantic/missions.py`: Calculadora «84»).
- Compuerta Full verde (e46afeaf): Contracts 70, Integration 2431 (+1 skip ambiental: pruebas opt-in de runtime
  real), Kernel 212, Providers.Windows 963, Setup 477, pytest 18 735.
- Mediciones: `MEDICIONES.md` (cobertura por tipo de app, latencia por paso, ahorro de procedimientos).
- Estado del PC devuelto: volumen 60 y brillo 40 como al empezar; modo avión revertido; Steam, Discord, Opera,
  Reloj, Calculadora y Panel de control abiertos por las pruebas, cerrados; sesión de Opera del autor restaurada
  byte a byte desde la copia previa.

## v2 (2026-10-07): universal, encadenado, rápido

Pedido del autor (00:10): que BAXY use el PC como una persona, en cualquier app, con misiones encadenadas, rápido y
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

### Rondas de revisión adversarial (2–4) y corridas en caliente

Tras el banco, tres rondas de revisión adversarial (agentes en paralelo por pieza: App, mente, lector, provider;
ramas `fable/cu-w-*`, `cu-x-*`, `cu-y-*`, `cu-z-*`) más los arreglos de corridas en vivo (n2, n8, s13 y una sesión en
caliente de cuatro órdenes seguidas). Contrato al día: `CONTRATO_VISTA_ACCION.md` §4.3 («Eco de la consulta»), §5 y §7.

**Éxitos falsos cerrados**

| Cambio | Commit |
|---|---|
| Un lugar nombrado sólo por una consulta escrita y no enviada no es llegada; enviada, sigue siendo eco mientras su cuadro la conserve y ningún clic haya ido de los resultados al lugar (Explorador n8: «imagenes - Resultados de la búsqueda en ETC» pasaba por Imágenes) | c33f77c8, ca7ed74f |
| El eco de la búsqueda vale para `control:X:current`, `title:`, `page:` y las citas del modelo; un clic que sólo seleccionó un resultado no sale de ellos; la búsqueda como meta sólo con resultados en pantalla (`SearchResultsProve`: un `stepDone` junto a `title:`/`text:`) | f3eaa93a, b85a3287, 2c7554ec, 830a1799 |
| Lo tecleado nunca es evidencia de haber llegado (Steam: «Cuphead» del buscador citado) | d0c571ad, 286a18da |
| Un clic verificado posterior en otro lugar deshace la llegada por clic (Steam: la tienda pasaba por la biblioteca); tras el clic en el lugar sólo es entrada de menú un rótulo que no estaba escrito antes | d0c571ad, f3eaa93a |
| «ir a X» es `control:X:current`: un ítem de contenido sólo elegido (Descargas en el Inicio del Explorador) no es llegar; un mosaico de la columna izquierda es contenido si su fila sigue fuera de ella | 3c160e45, 2c7554ec, 364783b9 |
| La cabecera de la página sólo en la zona T/TL, último control de su fila y tras un clic verificado o con el título nombrándolo; nuevo átomo `header:X` (un Text arriba que apareció tras el clic que nombra X) para los modos | f3eaa93a, 2c7554ec |
| Un modo se comprueba por selección, título, página o cabecera, nunca por un clic sobre su nombre (pasaba al pulsar la tarjeta «cotele», la carpeta Descargas o el ajuste «dark»); un modo que ninguna ventana ofrece por nombre («modo avión») sólo por su interruptor encendido | 835b85f1, 017d4f31 |
| Un elemento «<lugar> <aplicación>» es el lugar (Calculadora: «Científica Calculadora») | 2a5aa710 |
| Una frase que sólo menciona el lugar no es el lugar (Configuración: la descripción del proxy por «Wi-Fi»); sólo en textos, no en títulos de pestaña | 5ca2653a, 49b7ed8e |
| Un nombre con «&» se comprueba por una pieza (la más larga ≥ 4 si la dijo la persona: «Q&A», «AT&T»); un check vacío no es ningún check | 3c160e45, 017d4f31 |
| Procedimientos: un paso aprendido que falla deja la misión a la rutina y al modelo; se olvida el que se desvió o topó con una pantalla que no respondió, se conserva ante causas ajenas (vista no disponible, ventana tapada o elevada) | 4ee7b195, f3eaa93a, 2c7554ec |

**Seguridad**

| Cambio | Commit |
|---|---|
| Clic y desplazamiento también atados a la ventana de la aplicación nombrada (antes sólo teclas y texto); nunca VS Code, consolas ni BAXY (revisión anterior) | b85a3287 |
| Enter, espacio o Supr aprendidos no se repiten con su destino grabado: los decide la mente sobre la vista actual | b85a3287 |
| Enter sobre un elemento de contenido elegido sólo si su `itemType` (nuevo en la vista, `DesktopUiaWorker`) o la celda «Carpeta de archivos» / «File folder» dentro de su fila dicen carpeta; nunca un archivo que se ejecuta (`.reg .hta .scr .cpl .jar .com .pif` sumados), ni con una desinstalación a la vista, ni sobre un elemento que se llama quitar/eliminar | 364783b9, 830a1799, 5504fbd6, 899039f1 |
| Supr sólo en la barra de direcciones del paso «ir a la dirección», armado desde la vista | 286a18da |
| Ningún interruptor en metas de lugar (ir a, buscar, hacer clic sin tipo), tampoco en los pasos sin modelo ni por su nombre escrito; los botones «Alternar…» / «Toggle…» son interruptores (Calculadora: DEG→RAD); sólo un «hacé clic en X» que nombra el interruptor lo pulsa | 286a18da, 2a5aa710, 5504fbd6, 899039f1 |
| Enter o espacio tras escribir con el foco ilegible (ninguno, `Pane`, `Custom`: WhatsApp) preguntan; «buscar X» + Enter va sin pregunta sólo si el campo con el teclado es una búsqueda; «apretá enter» con el foco ilegible pregunta | 5504fbd6, 899039f1 |
| Menús sin clic a ciegas: la entrada que nombra el objetivo, la página propia del lugar o la primera sólo con el menú en el árbol; nunca una que actúa (jugar, instalar, enviar…); ruido de OCR no es entrada; nunca el cuerpo de la ventana por su nombre | 653a0ba5, 5504fbd6 |
| Las metas destructivas siguen fuera de todo camino al motor (lector, objetivo libre, último recurso) | 29ef7ca9 (sin cambios) |

**Universalidad**

| Cambio | Commit |
|---|---|
| Los modos detrás de la navegación: BUSCAR pulsa «Abrir navegación» / «Open Navigation» / «Más opciones» antes de los atajos a ciegas («Menú» o «More» solos no); «cambiá a X», «pasá al modo X», «switch to X mode» (live n2: Calculadora → Científica) | 185e5bdb, 286a18da, 835b85f1 |
| Las apps de Windows por su nombre inglés y con «app» («the Clock app»); ~60 pares de lugares en ambos idiomas; el modelo elige el control por su significado | 3c160e45 |
| «la vista de X» va a X; nombres con «&»; fuera de los alias las palabras de menú que son actos | 017d4f31 |
| Un elemento de contenido elegido se abre con Enter (con las condiciones de Seguridad) | 3c160e45 |
| En una conversación, una orden que nombra su aplicación y se lee sola es su misión, no la del decisor de contexto (sesión en caliente) | 2782fdf6 |
| Un seguimiento que el decisor reformula dentro de la aplicación es la misión, no un clic suelto; la aplicación es la dicha tras el último «en» (v2-s13) | 3271304d, 32012164, 835b85f1 |
| Si el control del propio lugar falló, el lugar se busca como lo ofrece la ventana (sólo nombres sin tipo); un botón de búsqueda que abrió su cuadro se escribe (Discord: buscador rápido) | 264f59fc, a4cfabc6, 5504fbd6 |
| Dos controles con el nombre: el único ítem de navegación es el lugar; si no, se busca | 286a18da, 5504fbd6 |
| Cuadrícula frente a navegación por tamaño: sólo un mosaico del mismo tamaño (±25 %) hace contenido (Reloj: «Alarma» junto a las alarmas de la página) | 755f4433 |
| Sin árbol, una palabra del host que empieza o termina con el lugar lo nombra (steamcommunity) | 653a0ba5 |
| Provider: el cursor en píxeles físicos (a 125 % el clic caía tres filas más abajo) y la ventana de un proceso siempre visible y usable (`ChooseProcessWindow`) | 00263487, f3eaa93a |

**Velocidad y voz**

| Cambio | Commit |
|---|---|
| Tecleo a 35 ms por carácter, medido (ver «Correcciones de la revisión») | 5ac16f90 |
| Vistas atadas al proceso sin ocho reintentos sobre el marco oculto de explorer.exe (~1,8 s por vista en n8) | 00263487 |
| El final con la voz de BAXY (00_IDENTIDAD): una frase, primera persona, el estado observable; el fallo plano con su causa | d32e03b9, 286a18da |
| El final de «ir a X» nunca dice que puso o cambió algo (Reloj: «Alarma» contada como alarma puesta) | e6c8001f |

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

Esta tabla es la de la primera revisión. c4 se volvió a correr en vivo a las 04:30 con el Supr de la barra de
direcciones (cadena de 4 sub-objetivos, 28 s). El banco final de 38 casos tras las rondas 2–4, con la compuerta Full,
está en `MEDICIONES.md` §«v2 — banco final (rondas 2–4)». Epic (u4: carga larga) y WhatsApp (u6: el texto no llega
al buscador) quedaban como límites medidos.

### Rondas 5–11 (2026-10-07, 08:00–09:30)

Corridas en vivo de casos nuevos (v1–v11, e2, g1, n1, x7, x12, y1) y revisiones adversariales r8 y r10 sobre
`fable/cu-universal-v2` desde 86011aeae. Cada cambio con su prueba de unidad o su contracaso; la tabla del banco final
la añade `MEDICIONES.md`.

**Lectura del pedido**

| Medido | Regla | Commit |
|---|---|---|
| v3 «… después a Sonido y decime el volumen»: la cola no se leía y el pedido fue entero al motor | un verbo de decir con la cosa sola («decime el X», «tell me the X») es la pregunta final; nunca dentro de comillas abiertas ni tras «escribí:» | 34637135f, c0de06ccd |
| v11 «y después a Sistema»: la reformulación «haz clic en «Sistema»» buscaba el nombre con comillas | las comillas que delimitan un nombre se quitan en clic, ir a, activar/desactivar y seleccionar | 34637135f |
| «poné el modo programador y después volvé a estándar» iba entera al modelo (55 s, pasos agotados) | volver a un modo o lugar es cambiar a él («volvé a abrir X» sigue siendo repetir); la cadena de modos son dos sub-metas con su comprobación | 443d05fbd |
| «go to Settings, then Bluetooth & devices» quedaba sin leer | ir a una aplicación nombrada entera como primera cláusula es abrirla; el nombre con «&» tras «then» es el lugar (el clic va al ítem de navegación, nunca al interruptor «Bluetooth») | 443d05fbd |
| x12 «abrí la calculadora» → «ahora ponela en modo científica»: el motor corrió sin aplicación | un seguimiento sin aplicación que se lee como paso con comprobación ocurre en la aplicación del pedido anterior (`follow_up_in_application`) | 5b87b5506 |
| r10: «abrí la calculadora» → «cuál es la capital de Francia» → «andá a historial» heredaba Calculadora | hereda sólo del pedido inmediato (se saltan un sí/no pelado y un paso que ya heredó); nunca reemplaza una pregunta, una charla o un límite que pregunta del decisor | fca0a1c61 |
| r8: «explorador de archivos» se leía como un archivo nombrado | `names_a_file` quita el nombre de la propia aplicación | c0de06ccd |

**Llegada y verificación**

| Medido | Regla | Commit |
|---|---|---|
| x7 «andá a search» | ir a la búsqueda añade `focus:search`: foco en un Edit/ComboBox editable que no lo tenía en la primera mirada, tras un clic o tecla de buscar y sin texto escrito; nunca un campo de sólo lectura o de dirección | e0f3b2f50 |
| v1: 185 ms tras el Enter la página listaba 17 de 52 controles y el modelo respondió `none` | un `none` sobre una vista que se encogió tras un acto verificado se vuelve a mirar (400 ms × 6, una vez por acto); vale también para el `none` con su código por defecto | ab63d5219, 3417ca073 |
| e2: «blue» y «azul» no encontrados pararon la misión por pantalla quieta antes de probar «Añil» | un clic que no encontró nada no cuenta como acto que dejó la pantalla igual | 0f33b81d7 |
| e2 «pick the blue color»: la paleta de Paint no tiene «Azul», sólo «Añil», «Turquesa»… | un color básico se cumple con un clic verificado, por nombre entero, en un tono de su familia (`semantic/colours.py`); nunca un control que cambia la herramienta; el final nombra el tono elegido | 1f61746f5 |
| n1/e2: la paleta quedaba fuera de los 60 controles listados; un «red» dentro de «Rectángulo redondeado» cumplía el check | el nombre fuera de la lista se busca por etiqueta en todo el árbol; elegir se prueba con el nombre entero (`control:=X`) | 0fd618ca7 |
| Paint lista cada entrada de galería dos veces con un nombre (`visible_button_ambiguous`) | controles homónimos en una sola línea de descendencia son un objetivo (gana el que se invoca); la etiqueta prueba primero el nombre que la ventana escribe; en la Tienda el campo que recibe texto gana a su grupo | 04ff3b1f2, 7541da93c |
| v11: un clic en «No hay resultados para «X»» se aprendió como procedimiento | un clic en un texto o campo que repite lo buscado dentro de una frase más larga no cuenta (`ClickEchoesQuery`) | 34637135f |
| v5/v6: Excel y Word en su página de inicio; el modelo pulsó Inicio, Cuenta y «Agregar un servicio» | para una pestaña ausente sin documento abierto se crea el documento desde la única oferta «en blanco» (nunca un reciente, nunca dos veces); si el pedido nombra un archivo para con `computer_use_no_document_open` | bede4e390 |
| «en la Microsoft Store buscá Spotify»: el historial emergente se tomó por la app y se pulsó una entrada | la ventana de una app en `ApplicationFrameHost` es su marco; un campo que el recibo dice pulsado conserva el cursor | a9905a3ac |

El rastro dice cuántas alternativas trae el chequeo de cada sub-objetivo (fd5eeb144).

**Seguridad**

| Medido | Regla | Commit |
|---|---|---|
| r8: un archivo «Documento en blanco» del Explorador habría recibido Enter | la oferta «en blanco» sólo fuera de listas, cuadrículas y árboles (salvo el de plantillas) y nunca en una vista de archivos; Enter sólo con el foco en la oferta | c0de06ccd |
| r10: en la vista de detalles una fila contiene el Edit de renombrar con su mismo nombre | el campo homónimo sólo gana dentro de una caja (Group, Pane, Custom, ComboBox), nunca dentro de una fila | ed3c2f99d |
| r8: Configuración y la Tienda comparten el pid de `ApplicationFrameHost` | la vista nombra el proceso alojado (`ViewProcess`); la misión nunca adopta el pid del anfitrión | c0de06ccd |
| y1 «poné el modo programador»: el modelo pulsó «Alternar grados» (DEG→RAD) | un objetivo que activa o elige una cosa nunca pulsa otro interruptor (`changes_a_setting`) | 3417ca073 |
| g1 Steam «buscá Cuphead»: el cuadro es sólo una lupa, sin árbol | escribir tras el clic en la línea OCR de una búsqueda sólo con el foco probado y ningún campo ajeno con el teclado; si no, `computer_use_search_focus_unproven`, dicho como causa | e1415883d, 37c05f631 |

**Velocidad**

Medido sobre ~50 misiones en vivo: 250 s en total; vistas 43 %, apertura de apps 17 %, asentamiento y huecos 17 %,
clics correctos 13 %, clics fallidos 7 %, modelo 1 %.

| Medido | Regla | Commit |
|---|---|---|
| 13 clics `visible_button_not_found` a 4,2–4,4 s cada uno | fallo rápido: ventana quieta 750 ms (vigilada cada 200 ms) ⇒ «no está», ~1,3 s; mira la ventana del clic, no la del frente, y el primer clic tras un cambio de pantalla conserva la espera entera | 54409a25e, dac875b9c |
| 11 de 27 transiciones entre sub-objetivos volvían a mirar | la vista que cumplió un sub-objetivo es la primera del siguiente si no se hizo nada y es la misma aplicación | 54409a25e |

**Voz final**

| Medido | Regla | Commit |
|---|---|---|
| 8 turnos con borradores vetados, 5 en el suelo rígido («Lo hice en la aplicación «Reloj»; hay 2: …») | la hora que la ventana escribió cuenta como observada; una misión fallida recibe voz de fallo en primera persona; suelo natural («Listo, estoy en «Reloj mundial».») | bac43fce0 |
| la App seguía con el suelo rígido cuando la mente no daba final | un solo suelo para App y mente (`operation_floor.v1.json` «computerUse», gemelos en `tests/data/cu_floor_twins.json`); veto de elecciones inventadas al sólo navegar, también en presente o futuro | ea2fdcbb8, c34646d74 |
| v6 «ahora selecciono Títulos» | un valor que la ventana marca sin que la misión lo pulsara no es su elección | a7a1490f7 |

**Trampa de proceso.** El conductor de las corridas en vivo lanza la App de la compilación Release
(`build_layout.ps1`); un `dotnet build -c Debug` no la toca, así que durante ~30 min las corridas en vivo midieron
una App vieja. Tras cambiar código de la App hay que rehacer el layout Release, y tras cambiar el provider, volver a
publicar Core.
