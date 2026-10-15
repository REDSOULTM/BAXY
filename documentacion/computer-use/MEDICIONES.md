# Computer use — cobertura, latencia y procedimientos (medido 2026-10-06)

Medido en vivo en el PC del dueño con la App real (`Baxy.exe --conductor`, mismo turno que la UI), Qwen3.5-4B
Q4_K_M + LoRA `full3`, pantalla 1536×864 lógicos al 125 %. Trazas por misión (`BAXY_APP_TRACE`) en
`%LOCALAPPDATA%\BAXY\cu-universal-evidencia\<misión>\trace.jsonl`, fuera del repo. Resultado de cada misión:
`PROGRESO.md`.

## Cobertura por tipo de aplicación

| Tipo | Probado en vivo | Cómo ve el motor la ventana | Estado |
|---|---|---|---|
| Win32 clásico | Panel de control → «Sistema y seguridad» | árbol UIA completo (32 controles) | logrado, 2 pasos, título verificado |
| UWP / WinUI | Calculadora (12×7), Reloj → Cronómetro | árbol UIA dentro de ApplicationFrameHost | logrado; `app.open` de la Calculadora no se verifica (marco UWP) y el motor lo tolera si queda delante |
| Electron | Discord (Enter en un MD; canal de voz) | árbol UIA de Chromium (60 controles) | Enter logrado por el motor; el canal lo resuelve la operación tipada `client.channel.locate` — el 4B no lo encontró pulsando por la lista |
| CEF sin árbol | Steam → Biblioteca | 1 control + líneas OCR | logrado tras 6 arreglos generales: clic OCR de varias palabras, menú abierto por el clic, llegada `page:`, ventana tapada al abrir |
| Navegador de la persona (Opera GX) | ir a la pestaña de YouTube; cerrar todas; HBO Max | pestañas `TabItem` por UIA; categoría «navegador» | pestaña por el motor; cerrar todas y streaming por sus operaciones tipadas |

## Latencia por paso

| Parte | n | p50 | máx | Nota |
|---|---|---|---|---|
| Vista (`input.visible.controls`, UIA + OCR) | 34 | 0,67 s | 1,9 s | la primera de cada misión ≈ 1,1–1,9 s (arranque del worker y OCR completo) |
| Decisión del modelo (`computer.use.step`) | 30 | 2,7 s | 5,2 s | sólo cuando la mente no dicta el paso; ≈ 830 tokens de entrada, ≈ 130 de salida |
| Paso dictado sin modelo | 13 | < 0,02 s | | tecla, escribir, calcular, clic en el control nombrado, pestaña, entrada de menú |
| `input.visible.click` | 12 | 1,2 s | 3,2 s | incluye la postlectura (superficie antes/después) |
| `input.key.press` / `input.text.type` | 5 | 0,67 s | 0,69 s | |
| `app.open` | 3 | 1,0 s | 1,9 s | reutiliza la ventana que ya corre |

Misiones completas del motor: Discord Enter 2,9 s; Calculadora 3,6–3,9 s; pestaña de YouTube 4,9 s; Panel de
control 5,6 s; Steam 9,3 s (una decisión del modelo). El turno visible suma ≈ 1,5–2 s de comprensión y
composición.

## Memoria de procedimientos

| Caso | Aprendiendo | Reproduciendo | Ahorro |
|---|---|---|---|
| Calculadora abierta, «calculá 12×7» | 3 913 ms (modelo 67 ms) | 3 559 ms (modelo 0 ms) | −354 ms (−9 %) |

El ahorro es pequeño porque la mente ya dicta sin modelo los pasos obvios; los procedimientos sólo pesan
cuando el modelo decide (Steam: 4,5 s de modelo por misión). Dos fallos de diseño hallados y corregidos al
medir:
- se aprendía descartando los pasos fallidos (Steam aprendió un clic sin sentido): ahora una misión con un paso
  fallido no se aprende (contrato §5), salvo una apertura UWP que no verifica;
- un procedimiento sin su apertura se reproducía sobre la ventana de delante (la Calculadora habría escrito en
  el editor): ahora sólo se reproduce sobre la ventana de la aplicación (`window.requested`) o cuando el paso
  es abrirla.

## Límites medidos

- El 4B elige mal cuando el destino no está a la vista y hay que buscarlo (Discord: 6 clics por la lista sin
  hallar el canal). Las rutas tipadas del catálogo cubren esos casos; no se cambió el modelo.
- En ventanas sin árbol la llegada se comprueba por texto (`page:`): una página cuyo texto cambie poco tras
  navegar no se daría por alcanzada (falso negativo honesto, nunca falso éxito).
- «cerrá todas las pestañas de <navegador>» actúa sobre el navegador predeterminado (`APLAZADOS.md`).

## v2 (2026-10-07): universal, encadenado, rápido

Mismo montaje (App real `--conductor`, perfil `cu-universal-perfil`, Qwen3.5-4B + `full3`), sobre la rama
`fable/cu-universal-v2` con las correcciones de la revisión (`PROGRESO.md` §«Seguridad v2» y §«Correcciones de la
revisión»). Evidencia por caso en `%LOCALAPPDATA%\BAXY\cu-universal-evidencia\v2-<caso>\` (`events.jsonl`: pedido y
finales; `trace.jsonl`: ms por etapa y la línea `computer_use.end`; `model_calls.jsonl`: llamadas al modelo). Cada
fila es la **última corrida** del caso. *Misión* = `ms` de `computer_use.end`; *turno* = `latency_ms` del final en la
conversación (lo que espera la persona); una sola cifra cuando la corrida dio sólo una. Verificación independiente
por UIA, Shell o captura, nunca por el final de BAXY.

El primer turno de cada corrida incluye el arranque en frío de la App (≈ 5–8 s de composición de la bienvenida):
en caliente, un turno ≈ decisión 0,5–0,7 s + misión + final 1–2 s.

### Banco final

| Caso | Pedido | Resultado | Misión / turno |
|---|---|---|---|
| s01 | en la calculadora calculá 37*12 (cerrada) | ✓ pantalla «444» | 3,1 s / 8,7 s (primer turno: App en frío) |
| s02 | en el Reloj andá a Cronómetro | ✓ | 2,3 s / 4,2 s |
| s03 | en Configuración andá a Bluetooth y dispositivos | ✓ (ya estaba en esa página) | 0,4 s / 2,4 s |
| s04 | en el Explorador de archivos andá a Descargas | ✓ (la corrida anterior fue un éxito falso: quedó elegida «Imágenes» → c40a2658) | 12,7 s / 15,4 s |
| s05 | en el Panel de control abrí Programas | ✓ título «Programas» | 2,9 s / 4,9 s |
| s06 | en el Administrador de tareas andá a Rendimiento | límite honesto: ventana de administrador, dicho con esa causa | 4,5 s (antes 33,6 s → d3939711) |
| s07 | abrí Paint y elegí la herramienta Texto | ✓ | 3,9 s / 6,1 s |
| s11 | en Discord andá al canal Cotele | ✓ | 1,0 s / 2,9 s |
| s12 | en Steam andá a la biblioteca | ✓ | 3,4 s / 5,5 s |
| s14 | en Discord mandale a Ron92 "…" → «no» | ✓ preguntó antes de enviar; «no» canceló | — |
| c1 | abrí el Bloc de notas, escribí "lista: pan", apretá Enter y escribí "leche" | ✓ texto verificado en el editor (antes «lista:nnnnleche» dado por logrado → 5ac16f90, 8f61d456) | 4,1 s / 6,7 s |
| c2 | Calculadora 12*12 → copiar → pegar en el Bloc de notas | ✓ «144» verificado en el editor | 6,1 s / 8,5 s |
| c3 | en el Explorador de archivos andá a Documentos y creá una carpeta llamada baxy-prueba | ✓ por la ruta tipada (14b8e238, D21) | 3,3 s |
| c4 | Opera: pestaña nueva → es.wikipedia.org → buscar Ñuñoa → sección Historia | ✗ 2/4 sub-objetivos: la barra completó la dirección con el historial. Arreglo integrado (Supr antes de Enter, 15920d7f) **sin probar en vivo** | — |
| c5 | Configuración → Personalización → Colores y decime si el modo es claro u oscuro | ✓ «Oscuro» | 2,3 s / 4,9 s |
| c6 | en Discord abrí el chat con Ron92, escribí "…" y mandalo → «sí» | ✓ preguntó antes de enviar; «sí» envió | — |
| c7 | en Discord andá al canal Cotele y después en Steam andá a la tienda | ✓ (antes falso negativo en Steam) | 6,4 s / 8,0 s |
| u1 | Spotify → biblioteca | ✓ | 19,3 s / 22,5 s (Spotify en frío) |
| u2 | Microsoft Store → Juegos | ✓ | 14,2 s (vista UIA de 4 s) |
| u3 | Fotos → Favoritos | ✓ | 4,8 s / 6,8 s |
| u4 | Epic Games → biblioteca | ✗ pantalla de carga larga; el clic por texto no tuvo efecto | — |
| u5 | Excel → libro en blanco | ✓ | 12 s |
| u6 | WhatsApp → un chat | ✗ el texto no llega al buscador | — |
| u7 | Reloj → Alarma | ✓ (antes 33 s: clic aprendido sin identidad → c40a2658) | 3,0 s / 4,7 s |
| u8 | Configuración → Sistema → Pantalla | ✓ | 4,4 s / 6,1 s |
| u9 | Spotify «go to Search» (inglés) | ✓ | 8,7 s / 10,7 s |

Los casos u* son aplicaciones que el motor nunca había probado. **Banco principal (24 casos: s01–s07, s11, s12, s14, c1–c7, u1, u3, u4, u6–u9): 21/24 correctos**; u2 y u5 pasaron en su primera corrida y quedan fuera del banco principal (s06 cuenta
como límite honesto correcto), 3 fallos: c4, u4, u6. **Corpus del lector** (`tests/test_computer_use_corpus.py`):
165 órdenes es/en → 161 misiones verificables + 4 cubiertas por la ruta tipada (D21).

Corridas anteriores que enseñaron un arreglo: s04 a las 00:47 (58,5 s, el escritorio tomado por la ventana del
Explorador → ea14333b) y después un éxito falso con otra carpeta elegida (→ c40a2658); s06 a las 00:53–01:04 (36,1 y
33,6 s: «la pantalla dejó de cambiar» → ventana elevada dicha, b396dfe8; la apertura agotaba 30 s → d3939711); s02 a
las 00:47–01:08 (aclaración o «no hay elemento»: el límite «cronómetro» y el veto de conservación anulaban la misión →
fa009cf1, 165aa153); s12 a las 00:57–01:09 (la ventana de arranque de Steam buscada como la app → b396dfe8; la Tienda
pasó por la Biblioteca → fa009cf1; procedimiento aprendido de ese falso éxito → 165aa153); s11 a las 01:05–01:13 (una
tarjeta de actividad con «Cotele» pasó por el canal → 165aa153, e8a6a560); c1 a las 01:31 (lista corrupta dada por
lograda → 5ac16f90, 8f61d456); c3 a las 01:16 (falso éxito: el eco de lo escrito en la búsqueda pasó por la carpeta →
2e06fa28) y a las 01:34 (el plan no llegaba a la misión → 14b8e238); c5 (la tarjeta «Colores» pulsada dejó
Personalización a la vista y se dio por llegada → c40a2658, 72093a4a); c6 a las 01:25 (envió sin preguntar →
3ae1dc88); c7 a las 01:33 (Steam ya en la Tienda leído como fallo); u3 (26 s de espera de apertura → 9c3f600d); u7
(33 s: clic aprendido por etiqueta → c40a2658).

### Latencia por paso (primeras corridas v2, 00:46–01:33)

| Parte | n | Rango (p50) | Fase 4 (p50) |
|---|---|---|---|
| Decisión del modelo del motor (gramática de acto primero) | 2 | 657–1 016 ms | 2,7 s |
| Paso dictado sin modelo (BUSCAR y procedimientos incluidos) | 25 | < 20 ms | < 20 ms |
| `input.visible.click` | 12 | 255–1 301 ms (456 ms) | 1,2 s |
| `input.text.type` (SendInput en proceso, a 3 ms por carácter) | 6 | 69–131 ms | 0,67 s |
| `input.key.press` (SendInput) | 2 | 67–73 ms | 0,67 s |
| `app.open` (apertura UWP por su marco) | 4 | 832–1 224 ms | 1,0 s; UWP 30 s sin verificar |

El tecleo pasó después a 35 ms por carácter (5ac16f90): un texto de *n* caracteres suma ≈ 35·*n* ms.

### Fase 4 frente a v2 (mismo caso o el más cercano)

| Caso | Fase 4 (2026-10-06) | v2 (2026-10-07, banco final) |
|---|---|---|
| Calculadora cerrada, calcular | «12×7»: turno 41,0 s, misión 35,9 s (apertura UWP 30 s) | «37*12»: misión 3,1 s, turno 8,7 s con la App en frío (4,4 s en caliente en la primera corrida) |
| Reloj → Cronómetro | turno 34,9 s | misión 2,3 s, turno 4,2 s |
| Steam → Biblioteca | turno 11,2 s, misión 9,3 s (modelo 4,6 s), 2 pasos | misión 3,4 s, turno 5,5 s |
| Panel de control → una categoría | «Sistema y seguridad»: turno 7,5 s, misión 5,6 s, 2 pasos | «Programas»: misión 2,9 s, turno 4,9 s |
| Discord → canal Cotele | el motor no lo halló (6 clics, 53,7 s); se sirvió por `client.channel.locate`, 17,2 s | el motor lo halla: misión 1,0 s, turno 2,9 s |
| Discord, apretar Enter | misión 2,9 s, turno 4,6 s | sin corrida v2 |

### Límites medidos en v2

- Navegador: la barra de direcciones completa lo escrito con una página del historial y Enter va allí (c4). El paso
  `ir a la direccion` ya pulsa Supr antes de Enter (15920d7f), sin corrida en vivo.
- Epic Games: la pantalla de carga dura más que la espera de arranque (20 s, 35cef19d) y el clic por texto no tuvo
  efecto pese a la postlectura de 1,5 s (bfba63d0) (u4).
- WhatsApp: sin árbol útil; el buscador escrito se pulsa por OCR (3151339b), pero el texto no llega a él (u6).
- Una app que corre como administrador no deja leer ni pulsar sus controles a un BAXY sin elevar: se dice con esa
  causa en 4,5 s (s06).
- Vistas lentas: la Microsoft Store tarda 4 s en dar su árbol UIA (u2); Spotify en frío, 19 s de misión (u1).

## v2 — banco final (rondas 2–4)

Mismo montaje, sobre la rama con las tres rondas de revisión adversarial y los arreglos de las corridas en caliente
(`PROGRESO.md` §«Rondas de revisión adversarial (2–4) y corridas en caliente»). Mismas definiciones de *misión* y
*turno*; verificación independiente.

Banco final en vivo (2026-10-07, 06:50–07:25, rama `fable/cu-universal-v2` tras las rondas 2–4): **34/38 correctos** (s06 cuenta como límite honesto correcto). Fallan n1 y e2 (Paint, elegir un color: un procedimiento aprendido que se desvía; tras el fallo se olvida y la corrida siguiente pasó a las 06:27), n5 (esta PC no muestra Wi-Fi; el fallo es correcto pero el final salió del suelo) y g1 (buscar un juego dentro de la biblioteca de Steam). «Respuesta» es el tiempo hasta el final de cada turno; el primer turno de cada corrida incluye el arranque de la App.

| Caso | Orden | Resultado | Misión | Respuesta | Final |
|---|---|---|---|---|---|
| s01 | en la calculadora calculá 37*12 | ✓ | 3.4 s | 5.5 s | Ya calculé 37 por 12 y la respuesta que muestra la calculadora es 444. |
| s02 | en el Reloj andá a Cronómetro | ✓ | 2.6 s | 4.4 s | Ya estoy en el cronómetro y muestra 96 horas 59 minutos 59 segundos. |
| s03 | en Configuración andá a Bluetooth y dispositivos | ✓ | 0.7 s | 2.6 s | Estoy en la sección de Bluetooth y dispositivos, donde veo que el control Xbox y el SLEVE EVO están emparejados. |
| s04 | en el Explorador de archivos andá a Descargas | ✓ | 0.8 s | 2.6 s | Ya estoy en la carpeta de Descargas y veo los archivos que hay ahí. |
| s05 | en el Panel de control abrí Programas | ✓ | 3.0 s | 4.9 s | Ya estoy en el Panel de control, en la sección de Programas. |
| s06 | en el Administrador de tareas andá a Rendimiento | ✓ límite honesto | — s | 4.6 s | No pude ir a la pestaña de Rendimiento porque la aplicación corre como administrador y Windows no permite que otra aplicación la controle. |
| s07 | abrí Paint y elegí la herramienta Texto | ✓ | 1.4 s | 3.4 s | Ya elegí la herramienta Texto en Paint y ahora puedo escribir directamente en el lienzo. |
| s11 | en Discord andá al canal Cotele / no | ✓ | 0.8 s | 2.4 / 1.4 s | Ya estoy en el canal Cotele!!!😎 / Choche. / Lo dejas ahí. |
| s12 | en Steam andá a la biblioteca | ✓ | 4.1 s | 6.0 s | Ya estoy en la biblioteca de Steam, donde veo las colecciones y los juegos instalados. |
| s14 | en Discord mandale a Ron92 "prueba BAXY 14" / no | ✓ | — s | 9.9 / 0.8 s | ¿Quieres que envíe el mensaje "prueba BAXY 14" a Ron92 en Discord? Elige confirmar o cancelar. / No se envió el mensaje a Ron92 porque la ac |
| c1 | abrí el Bloc de notas, escribí "lista: pan", apretá Enter y escribí "leche" | ✓ | 4.1 s | 6.4 s | Acabo de escribir "lista: pan" y luego "leche" en el Bloc de notas. |
| c2 | en la calculadora calculá 12*12, copiá el resultado y pegalo en el Bloc de notas | ✓ | 5.6 s | 7.7 s | Acabé de escribir 144 en el Bloc de notas. |
| c3 | en el Explorador de archivos andá a Documentos y creá una carpeta llamada baxy-prueba | ✓ | — s | 3.2 s | He abierto la carpeta Documentos y he creado la carpeta baxy-prueba. |
| c5 | abrí Configuración, andá a Personalización, entrá a Colores y decime si el modo es claro u oscuro | ✓ | 4.2 s | 6.6 s | El modo que aparece seleccionado es Oscuro. Acabé de ir a Personalización y luego a Colores para verlo. |
| c6 | en Discord abrí el chat con Ron92, escribí "prueba BAXY C6" y mandalo / sí | ✓ | 2.6 s | 4.5 / 1.3 s | ¿Quieres confirmar que envíes el mensaje "prueba BAXY C6" en el chat con Ron92 o cancelar esta acción? / Ya te envié el mensaje "prueba BAXY |
| c7 | en Discord andá al canal Cotele y después en Steam andá a la tienda / no | ✓ | 3.5 s | 5.2 / 2.0 s | Ya estoy en la tienda de Steam. / Entendido, no vamos a la tienda de Steam. |
| u1 | abrí Spotify y andá a tu biblioteca | ✓ | 8.4 s | 10.6 s | Ya estoy en tu biblioteca de Spotify viendo tus playlists. |
| u2 | en la Microsoft Store andá a Juegos | ✓ | 8.9 s | 10.8 s | Ya estoy en la sección de Juegos de la Microsoft Store. |
| u3 | abrí Fotos y andá a Favoritos | ✓ | 5.0 s | 6.9 s | Ya estoy en la carpeta de Favoritos. |
| u5 | abrí Excel y elegí libro en blanco | ✓ | 3.7 s | 5.7 s | Ya tengo el libro en blanco abierto en Excel. |
| u7 | en el Reloj andá a Alarma | ✓ | 3.3 s | 6.8 s | Lo hice en la aplicación «Reloj»; hay 2: «Alarma». |
| u8 | abrí Configuración, andá a Sistema y después a Pantalla | ✓ | 3.7 s | 6.0 s | Estoy en la pantalla de Configuración, donde ahora se muestra el brillo al 40% y la resolución en 1920 × 1080. |
| u9 | open Spotify and go to Search | ✓ | 8.0 s | 10.3 s | I'm already on the search page in Spotify. |
| n1 | abrí Paint, elegí el lápiz y después el color rojo | ✗ | — s | 6.5 s | No pude seleccionar el color rojo porque en la pantalla no apareció ningún paso o control que me indicara cómo hacerlo. |
| n2 | en la calculadora cambiá a científica | ✓ | 4.1 s | 6.0 s | Ya cambié a la científica y ahora está seleccionada. |
| n3 | en el Reloj andá a Temporizador | ✓ | 3.2 s | 5.1 s | Ya estoy en la pestaña del Temporizador y veo que el de un minuto está en marcha. |
| n4 | open Settings and go to Apps | ✓ | 1.4 s | 3.1 s | I'm already in the Apps section, where I can see the installed applications listed. |
| n5 | en Configuración andá a Red e Internet y después a Wi-Fi | ✗ (sin Wi-Fi en esta PC; final de respaldo) | — s | 9.9 s | No pude hacerlo en la aplicación «Configuración». |
| n6 | abrí Word y elegí documento en blanco | ✓ | 3.9 s | 6.0 s | Ya tengo el documento en blanco listo para escribir. |
| n7 | en Steam andá a la comunidad | ✓ | 2.6 s | 4.7 s | Ya estoy en la comunidad de Steam, donde se muestran los nuevos gráficos de la semana y los centros populares como Europa Universalis IV. |
| n8 | en el Explorador de archivos andá a Imágenes | ✓ | 2.1 s | 3.9 s | Ya estoy en la carpeta Imágenes con las fotos de la cámara y otras guardadas. |
| g1 | abrí Steam, andá a la biblioteca y buscá Cuphead | ✗ | — s | 6.1 s | No pude buscar Cuphead porque Steam dejó de responder tras hacer clic en biblioteca, y la pantalla se quedó estática. |
| e1 | open the calculator and calculate 25 times 4 | ✓ | 3.3 s | 5.4 s | I got 25 times 4 to be 100. |
| e2 | abrí Paint y pick the blue color | ✗ | — s | 10.2 s | No pude hacerlo en la aplicación «Paint». |
| e3 | in the Clock app go to Stopwatch | ✓ | 2.5 s | 4.5 s | I'm in the Stopwatch app, and the timer is paused at 96 hours, 59 minutes, and 59 seconds. |
| e4 | open File Explorer and go to Downloads | ✓ | 0.7 s | 3.0 s | I'm already in the Downloads folder, and I can see files like "<archivo>" and "<archivo>" listed there. |
| w1 | en el Reloj andá a Alarma / en el Reloj andá a Cronómetro / en Configuración andá a Bluetooth y dispositivos / en la calculadora calculá 9 por 8 | ✓ | 3.8 s | 5.5 / 2.1 / 3.0 / 5.2 s | He estado en la pestaña de la alarma del reloj. / Ya estoy en el cronómetro y muestra 96 horas 59 minutos 59 segundos. / Ya estoy en la secc |
| s13 | en Discord andá al canal Cotele / no / y ahora andá a configuración | ✓ | 0.8 s | 2.3 / 1.4 / 2.9 s | Ya estoy en el canal Cotele!!!😎 / Choche. / Lo dejas ahí. / Ya tenía la configuración de Discord abierta. |

### Medido antes del banco final

| Medida | Resultado |
|---|---|
| Sesión en caliente w1 (4 órdenes seguidas en la misma conversación) | 6,6 s (incluye el arranque), 2,2 s, 2,0 s y 5,6 s |
| c4 Opera: pestaña nueva → es.wikipedia.org → buscar Ñuñoa → sección Historia (04:30, en vivo) | cadena de 4 sub-objetivos en 28 s |
| Tecleo carácter a carácter | 35 ms por carácter (medido en el Bloc de notas: íntegro desde 25 ms) |
| Compuerta Full, suites .NET | verde: Integration 2486, Providers 1028, Setup 477, Kernel 307 |
| Compuerta Full, pytest | 18 811; sólo quedaba pendiente el censo, que luego se corrigió |

## v2 — rondas 5–12 y lotes ciegos (2026-10-07, 08:00–10:30)

Mismo montaje. Rondas de agentes en paralelo con revisión adversarial tras cada fusión (`PROGRESO.md`
§«Rondas 5–11»). Dos lotes de 12 órdenes nuevas (x, y), escritos antes de sus arreglos, miden la primera pasada.

| Medida | Resultado |
|---|---|
| Lote 39 (órdenes nuevas, punta f2118c3bc) | 4/10 |
| Lote ciego x, primera pasada | 10/12 (fallan x7 «andá a search», x12 seguimiento «ponela en modo científica») |
| Lote ciego y, primera pasada | 10/12 (fallan y1 dos modos encadenados, y2 «go to Settings, then Bluetooth & devices») |
| Banco final, 72 casos (38 del banco anterior + v + x + y), punta 19a12fb79 | **69/72** |
| Tras r11–r12 (y5, y9 arreglados y vueltos a correr en vivo) | **71/72**; el único fallo es n5, que pide Wi-Fi en un PC sin Wi-Fi |
| Respuesta por turno en el banco (85 turnos) | p50 4,8 s · p90 9,7 s · máx 17,3 s |
| Misión del motor (68 misiones logradas) | p50 3,1 s · p90 7,6 s |
| Clic por etiqueta no encontrada | 4,3 s → 1,4 s (fallo rápido con ventana quieta) |
| Dos modos encadenados en la Calculadora (y1) | 55 s → 8,2 s |

Corregidos en estas rondas, cada uno medido en vivo antes y después: elegir color en una paleta sin ese nombre (e2:
«Elegí Añil, el azul de la paleta»), pestañas de Excel/Word desde su pantalla de inicio (v5, v6), búsqueda en la
Microsoft Store (v1), pregunta al final de una cadena (v3: «El volumen está en 60», comprobado), seguimiento sin
nombrar la app (v11, x12), búsqueda en la biblioteca de Steam (g1), «andá a search» en Spotify (x7), lugares
encadenados en el Explorador (y5), un texto aprendido tecleado fuera de un campo (y9).

Falsos éxitos hallados y cerrados: x7 (una barra de direcciones de solo lectura tomada por buscador), y5 (ruta tipada
que hacía sólo la mitad y una voz que inventaba la otra), v6 (voz «ahora selecciono Títulos»). Efectos laterales
hallados: y1 pulsó «Alternar grados» de la Calculadora (DEG→RAD); ahora ningún objetivo pulsa un interruptor que no
nombra.

Banco final (punta 19a12fb79; y5 e y9 con su arreglo en la fila):

| Caso | Orden | Resultado | Misión | Respuesta | Final |
|---|---|---|---|---|---|
| s01 | en la calculadora calculá 37*12 | ✓ | 3.2 s | 5.2 s | Ya calculé 37 por 12 y la respuesta es 444. |
| s02 | en el Reloj andá a Cronómetro | ✓ | 2.7 s | 4.6 s | Ya estoy en el cronómetro y muestra 96 horas 59 minutos 59 segundos. |
| s03 | en Configuración andá a Bluetooth y dispositivos | ✓ | 3.1 s | 5.3 s | Ya estoy en la sección de Bluetooth y dispositivos, donde veo que el Xbox Wireless Controller y el SLEVE EVO están emparejados. |
| s04 | en el Explorador de archivos andá a Descargas | ✓ | 0.8 s | 2.6 s | Ya estoy en la carpeta de Descargas y veo los archivos que hay ahí. |
| s05 | en el Panel de control abrí Programas | ✓ | 2.9 s | 4.9 s | Ya estoy en el Panel de control, en la sección de Programas. |
| s06 | en el Administrador de tareas andá a Rendimiento | ✓ límite honesto | — | 4.5 s | No pude ir a la pestaña de Rendimiento porque la aplicación corre como administrador y Windows no me permite controlarla. |
| s07 | abrí Paint y elegí la herramienta Texto | ✓ | 1.4 s | 3.4 s | Ya elegí la herramienta Texto en Paint y ahora puedo escribir directamente en el lienzo. |
| s11 | en Discord andá al canal Cotele / no | ✓ | 0.8 s | 2.4 / 1.5 s | Ya estoy en el canal Cotele!!!😎 / Choche. / Lo dejas ahí. |
| s12 | en Steam andá a la biblioteca | ✓ | 2.2 s | 4.1 s | Ya estoy en la biblioteca de Steam, donde esta semana se muestra el número 1 y la lista de "MALLHALLA-CHES S". |
| s14 | en Discord mandale a Ron92 "prueba BAXY 14" / no | ✓ (pregunta; cancelado) | — | 10.0 / 0.7 s | ¿Quieres que envíe el mensaje "prueba BAXY 14" a Ron92 en Discord? Elige confirmar o cancelar. / No se envió el mensaje a Ron92 porque la acción fue cancelada. |
| c1 | abrí el Bloc de notas, escribí "lista: pan", apretá Enter y escribí "leche" | ✓ | 4.1 s | 6.4 s | Acabo de escribir "lista: pan" y luego "leche" en el Bloc de notas. |
| c2 | en la calculadora calculá 12*12, copiá el resultado y pegalo en el Bloc de notas | ✓ | 5.5 s | 7.5 s | Acabé de escribir 144 en el Bloc de notas. |
| c3 | en el Explorador de archivos andá a Documentos y creá una carpeta llamada baxy-prueba | ✓ | — | 3.2 s | He abierto la carpeta Documentos y he creado la carpeta baxy-prueba. |
| c5 | abrí Configuración, andá a Personalización, entrá a Colores y decime si el modo es claro u oscuro | ✓ | 3.7 s | 6.3 s | El modo que aparece seleccionado es Oscuro. Ya te llevé a Configuración, luego a Personalización y finalmente a Colores para ver eso. |
| c6 | en Discord abrí el chat con Ron92, escribí "prueba BAXY C6" y mandalo / sí | ✓ (confirmado) | 2.1 s | 3.7 / 1.3 s | ¿Quieres confirmar que envíes el mensaje "prueba BAXY C6" en el chat con Ron92 o cancelar esta acción? / Ya te envié el mensaje "prueba BAXY C6" en el chat con Ron92. |
| c7 | en Discord andá al canal Cotele y después en Steam andá a la tienda / no | ✓ | 3.7 s | 5.5 / 1.9 s | Ya estoy en la tienda de Steam. / Entendido, no vamos a la tienda de Steam. |
| u1 | abrí Spotify y andá a tu biblioteca | ✓ | 8.1 s | 10.5 s | Ya estoy en tu biblioteca de Spotify viendo tus playlists recientes y artistas favoritos. |
| u2 | en la Microsoft Store andá a Juegos | ✓ | 7.8 s | 12.2 s | Ya estoy en la sección de Juegos de la Microsoft Store. |
| u3 | abrí Fotos y andá a Favoritos | ✓ | 5.2 s | 7.2 s | Ya estoy en la pestaña de Favoritos y no hay nada seleccionado todavía. |
| u5 | abrí Excel y elegí libro en blanco | ✓ | 3.7 s | 5.9 s | Ya tengo el libro en blanco seleccionado y listo para usar. |
| u7 | en el Reloj andá a Alarma | ✓ | 3.1 s | 4.9 s | Ya estoy en la pantalla de la alarma, que dice 7:00. |
| u8 | abrí Configuración, andá a Sistema y después a Pantalla | ✓ | 3.8 s | 6.0 s | Estoy en la sección de Pantalla dentro de Configuración, donde se muestran opciones como el brillo y la resolución. |
| u9 | open Spotify and go to Search | ✓ | 7.2 s | 9.4 s | I'm already in the search bar of Spotify Premium. |
| n1 | abrí Paint, elegí el lápiz y después el color rojo | ✓ | 2.2 s | 4.3 s | Ya tengo el lápiz listo y el color rojo seleccionado en Paint. |
| n2 | en la calculadora cambiá a científica | ✓ | 14.7 s | 17.3 s | Acabé de cambiar a la vista científica en la calculadora. |
| n3 | en el Reloj andá a Temporizador | ✓ | 3.2 s | 5.2 s | Ya estoy en la pestaña del temporizador y el reloj muestra que está en marcha con 1 minuto. |
| n4 | open Settings and go to Apps | ✓ | 1.4 s | 3.1 s | I'm already in the Apps section. |
| n5 | en Configuración andá a Red e Internet y después a Wi-Fi | ✗ (este PC no tiene Wi-Fi) | — | 7.7 s | No pude llegar a la sección de Wi-Fi porque la pantalla se quedó quieta justo después de buscar la opción. Logré abrir Configuración y selec |
| n6 | abrí Word y elegí documento en blanco | ✓ | 4.1 s | 6.2 s | Ya tengo el documento en blanco listo para escribir. |
| n7 | en Steam andá a la comunidad | ✓ | 2.4 s | 4.3 s | Ya estoy en la comunidad de Steam, donde se muestran los nuevos gráficos y los centros populares como Europa Universalis IV. |
| n8 | en el Explorador de archivos andá a Imágenes | ✓ | 2.1 s | 4.2 s | Ya estoy en la carpeta Imágenes con las fotos de la cámara y otras guardadas. |
| g1 | abrí Steam, andá a la biblioteca y buscá Cuphead | ✓ | 4.7 s | 6.9 s | Ya estoy en la biblioteca de Steam y vi que Cuphead aparece en la lista. |
| e1 | open the calculator and calculate 25 times 4 | ✓ | 3.1 s | 5.1 s | I got 25 times 4 to be 100. |
| e2 | abrí Paint y pick the blue color | ✓ | 5.3 s | 7.4 s | Elegí Añil, el azul de la paleta. |
| e3 | in the Clock app go to Stopwatch | ✓ | 2.5 s | 4.5 s | I'm in the Stopwatch app, paused at 96 hours 59 minutes 59 seconds. |
| e4 | open File Explorer and go to Downloads | ✓ | 0.7 s | 3.0 s | I'm already in the Downloads folder, and I can see files like "<archivo>" and "<archivo>" listed there. |
| w1 | en el Reloj andá a Alarma / en el Reloj andá a Cronómetro / en Configuración andá a Bluetooth y dispositivos / en la calculadora calculá 9 por 8 | ✓ | 3.7 s | 4.6 / 2.2 / 3.1 / 5.3 s | Ya estoy en la pantalla de la alarma, donde dice 7:00. / Ya estoy en el cronómetro y muestra 96 horas 59 minutos 59 segundos. / Ya estoy en la sección de Bluetooth y dispositivos, donde veo que el controlador Xbox está emparejado y conectado al 100%. / Ya calculé 9 por 8 y la calculadora muestra 72. |
| s13 | en Discord andá al canal Cotele / no / y ahora andá a configuración | ✓ | 0.7 s | 2.3 / 1.3 / 2.6 s | Ya estoy en el canal Cotele!!!😎 / Choche. / Lo dejas ahí. / Ya tenía la configuración de Discord abierta. |
| v1 | en la Microsoft Store buscá Spotify | ✓ | 11.4 s | 13.3 s | Ya encontré Spotify en la Microsoft Store y está instalado. |
| v3 | en Configuración andá a Sistema, después a Sonido y decime el volumen | ✓ | 4.3 s | 6.5 s | El volumen de salida está en 60. Ya te llevé a la sección de Sonido dentro de Configuración. |
| v4 | en el Explorador de archivos andá a Este equipo | ✓ | 2.1 s | 4.2 s | Estoy en la carpeta Este equipo y veo que el disco M.2 Samsung (C:) está al 90% lleno. |
| v5 | en Excel andá a la pestaña Insertar | ✓ | 6.1 s | 7.8 s | Ya estoy en la pestaña Insertar del libro Libro1. |
| v6 | en Word andá a la pestaña Diseño | ✓ | 7.3 s | 9.7 s | Llegué a la pestaña Diseño de Word. |
| v7 | open Paint and choose the eraser | ✓ | 1.3 s | 3.2 s | I've got the eraser selected in Paint. |
| v8 | en Spotify andá a Inicio | ✓ | 8.4 s | 10.5 s | Ya estoy en la página de inicio de Spotify Premium. |
| v9 | en el Reloj andá a Reloj mundial | ✓ | 3.5 s | 7.9 s | Ya estoy en la pantalla del reloj mundial, que marca las 10:06 del miércoles 7 de octubre de 2026. |
| v10 | en Configuración andá a Hora e idioma y después a Idioma y región | ✓ | 3.5 s | 5.6 s | Estoy en la sección de Idioma y región, donde se ha seleccionado Español (Chile) como idioma de Windows. |
| v11 | abrí Configuración / ahora andá a Bluetooth y dispositivos / y después a Sistema | ✓ | 1.5 s | 2.2 / 3.5 / 3.8 s | Ya tenía la app Configuración abierta. / Ya he entrado en la sección de Bluetooth y dispositivos, donde ahora se ven los controladores emparejados. / Ya estoy en la sección de Sistema y puedo ver que el equipo es un ASUS TUF Gaming A15 FA506QM. |
| x1 | open the Calculator and switch to scientific mode | ✓ | 3.3 s | 5.4 s | I'm already in scientific mode on the calculator, where the display shows "Elevado a 10". |
| x2 | abrí el Reloj y andá a Temporizador | ✓ | 3.0 s | 5.2 s | Ya estoy en la pestaña del temporizador y veo que el de un minuto está en marcha con 16271 horas, 40 minutos y 32 segundos. |
| x3 | abrí Configuración y andá a Accesibilidad | ✓ | 1.5 s | 3.2 s | Ya estoy en la sección de Accesibilidad. |
| x4 | in Settings go to Personalization and then to Themes | ✓ | 2.7 s | 4.8 s | I'm now in the Themes section of Settings, where you can see options like Windows (light) and Windows (dark). |
| x5 | abrí el Bloc de notas y escribí hola BAXY | ✓ | 2.9 s | 5.0 s | Ya escribí hola BAXY en el Bloc de notas. |
| x6 | abrí el Explorador de archivos y andá a Documentos | ✓ | 2.0 s | 4.0 s | Ya estoy en la carpeta Documentos y puedo ver los archivos que hay ahí. |
| x7 | en Spotify andá a search | ✓ | 7.7 s | 9.9 s | Ya estamos en la pestaña de búsqueda de Spotify. |
| x8 | abrí la calculadora y calculá 125 más 75 | ✓ | 3.2 s | 5.5 s | Ya sumé 125 más 75 y la calculadora muestra 200. |
| x9 | en Paint elegí el bote de pintura | ✓ | 1.2 s | 2.9 s | Ya elegí el bote de pintura de relleno en Paint. |
| x10 | en Steam andá a la biblioteca y después a la tienda | ✓ | 5.0 s | 6.9 s | Ya estoy en la Tienda de Steam. |
| x11 | open Clock and go to Alarm | ✓ | 3.1 s | 5.1 s | I opened the Clock app and selected the Alarm tab, which now shows the time set for 7:00. |
| x12 | abrí la calculadora / ahora ponela en modo científica | ✓ | 2.4 s | 2.7 / 4.4 s | Abrí la calculadora y ahora está en ejecución. / Ya tengo la calculadora en modo científico. |
| y1 | abrí la calculadora, poné el modo programador y después volvé a estándar | ✓ | 5.7 s | 7.9 s | Ya cambié la calculadora al modo estándar y ahora muestra el número cero. |
| y2 | go to Settings, then Bluetooth & devices | ✓ | 1.9 s | 4.0 s | I'm already in the Bluetooth & devices section, where I can see the Xbox Wireless Controller and SLEVE EVO are paired. |
| y3 | en el Reloj andá a Cronómetro y después a Alarma | ✓ | 3.4 s | 5.3 s | Ya estoy en la pantalla de Alarma del Reloj, donde se muestra la hora de 7:00. |
| y4 | abrí el Bloc de notas y escribí: reunión a las 5 | ✓ | 3.0 s | 4.9 s | Ya escribí "reunión a las 5" en el Bloc de notas. |
| y5 | en el Explorador de archivos andá a Descargas y después a Imágenes | ✗ → ✓ tras r11 | — | 4.8 s | Has abierto correctamente la carpeta Imágenes dentro de Descargas. |
| y6 | open Paint and select the text tool | ✓ | 1.5 s | 3.3 s | I've got the Text tool ready for you to use. |
| y7 | en la calculadora calculá 9 por 9 | ✓ | 3.1 s | 5.0 s | Ya calculé 9 por 9 y la pantalla muestra 81. |
| y8 | abrí Spotify y andá a tu biblioteca | ✓ | 7.6 s | 9.9 s | Ya estoy en tu biblioteca de Spotify viendo tus playlists y canciones recientes. |
| y9 | en Configuración buscá mouse | ✗ → ✓ tras r12 | — | 3.5 s | ¿Quieres confirmar que presione Enter en el mensaje o cancelar la acción? |
| y10 | in Steam go to the store and then to the library | ✓ | 2.2 s | 4.0 s | I'm in the Steam library where Batman is listed among the favorites. |
| y11 | abrí el Reloj / y ahora andá a Temporizador | ✓ | 1.0 s | 2.5 / 3.3 s | Abrí la aplicación Reloj. / Ya he pulsado en «Temporizador» y ahora está seleccionado. |
| y12 | en Paint elegí el color verde | ✓ | 1.8 s | 3.5 s | Ya elegí el color verde en Paint. |

Compuerta Full sobre la punta del banco más r12 (76c574bd6): .NET verde (Integration 2560, Providers 1039, Setup 477,
Kernel 307, Contracts 70), formato y compilación verdes; pytest dio 14 fallos de inventarios de procesos y ventanas
(el veto de identificadores de r11 también quitaba sus PID). Acotado a abrir app, archivo o carpeta y al motor
(1f22bb5e6), la etapa pytest completa pasa: 19 051.

### Lote ciego z y ronda 13 (11:15–11:35)

Tercer lote de 12 órdenes nuevas, escrito tras publicar 1bbe01704: **11/12 a la primera** (Bloc de notas en inglés,
cadenas Reloj y Steam, Windows Update, Música, «15 por 3 más 2» = 47, lápiz y rojo en inglés, Aplicaciones de la Store,
la zona horaria leída de Configuración, seguimiento «escribí: …», spanglish «switch to Temporizador»). Falló z7 «en
Spotify andá a Inicio y después a tu biblioteca» (35 s): el panel lateral abierto junto a la página llena no contaba
como llegada (acc13d996). Tras el arreglo: z7 en 11,3 s de misión; u1, v8 y x7 siguen bien.

Efecto lateral hallado en esa corrida de z7: buscando la biblioteca, el modelo pulsó «Seguir a Tu biblioteca» (un
perfil), «Siguiendo…» (que lo deshizo) y «Guardar La biblioteca de media noche en Tu Biblioteca». La playlist se quitó
a mano de la cuenta tras comprobar el botón «Eliminar … de Tu biblioteca». Desde a9d09c445 ningún clic que cambie la
cuenta (seguir, guardar, me gusta, suscribirse, obtener o instalar) se hace si el objetivo no lo pide; un lugar que se
llama así («Tus me gusta», «Liked Songs») sigue siendo un lugar. La corrida de z7 posterior no tuvo ningún clic de ese
tipo.

### Lote ciego a (11:48–12:00)

Once órdenes nuevas centradas en cadenas y conversación: **10/11 a la primera** (Calculadora → Bloc de notas con el
resultado, Reloj → Configuración, Documentos → Descargas, goma y negro en Paint, Word en blanco → Insertar, Reloj
mundial en inglés, buscar WhatsApp en la Store, modo programador, conversación de tres turnos hasta Ethernet, buscar
Bluetooth en Configuración). Falló a3 «open Settings, go to Accessibility and then to Text size»: «Text size» no tenía
su nombre en español en la tabla de alias; añadido como dato, a3 llega en 5,7 s (11/11). Ningún clic de cuenta ni
interruptor no pedido en el lote (revisado en el journal).

### Lote ciego b y ronda 15 (12:05–12:17)

Seis órdenes nuevas (Bloc de notas con «escribí:», Personalización → Temas, «144 divided by 12» en inglés, Reloj
mundial → Alarma, Steam tienda → comunidad, texto y azul en Paint): **6/6 a la primera**. Ronda 15: vetos de voz para
«X dentro de Y» entre lugares o apps distintos de la misión y para «ahora está activado» sin ningún interruptor
pulsado (a4 sale «Ya estoy en la carpeta de Descargas.»); n5 dice ahora la causa real («no encontré esa opción en la
ventana actual») en vez de «la pantalla se quedó quieta».

Pendiente de voz (modelo 4B, en vivo 12:15): a2 añadió «donde busco la opción de Wi-Fi», tomado de un turno anterior
del mismo perfil; a12 dijo «Abrazé» por «Llegué». La misión y la verificación fueron correctas en ambos.

## Voz de los finales (rondas 16–19, 2026-10-07, 12:50–14:40)

Auditoría de los 350 finales compuestos hoy (corpus en el scratchpad de la sesión): de los 239 finales de misión
publicados, 67 % estaban bien. Defectos más frecuentes: frases raras («Ya te llevé…», «Spotify Premium»), datos
inventados o leídos de más («16270 horas», «donde busco la opción de Wi-Fi», que venía de texto que otra prueba dejó en
el buscador), frases largas, perfecto peninsular («Ya he entrado»), estado dicho como cambio («ahora está activado»),
persona equivocada («mis playlists»), palabras mal escritas («Abrazé», en un reintento a temperatura 0,7), relaciones
falsas («Descargas dentro de Documentos») y «estamos».

Arreglos, todos generales y con prueba:
- Frase determinista primero para las misiones sin pregunta, construida desde los hechos («Listo, estoy en «Juegos».»,
  «Listo, pasé por «Sistema» y ya estoy en «Almacenamiento».», «Listo, elegí «Lápiz» y «Rojo».», «Listo: 37 × 12 =
  444.», «Listo, busqué «Spotify» en «Microsoft Store».»). La mente y su gemela en la App comparten los datos.
- Respuesta determinista cuando un único hecho contesta la pregunta («Listo: el volumen está en 60.», «Listo: el modo
  está en «Oscuro».», «Listo: la zona horaria es «(UTC-04:00) Santiago».»).
- Para lo que todavía escribe el modelo: sólo este turno y sus hechos, siempre a temperatura 0, voz en primera persona
  con tuteo chileno, y vetos de palabra no fundamentada (vocabulario en datos), pretérito mal escrito, plural, perfecto
  peninsular, «abrí» con la app ya abierta, pregunta sin respuesta, «Llegué a <valor>», contención entre lugares y
  estado como cambio.

En vivo tras las rondas: lote ciego c 12/12 con 9 finales deterministas; banco amplio de 55 casos con 51 correctos
(s06 y n5 son límites honestos; s12 y c17 son Steam ya en la biblioteca, sin árbol para probar la llegada, y fallan
honestamente). Suites completas: pytest 19 219 (un fallo de censo, corregido), Integración 2602, Providers 1039.
Pendiente menor: un seguimiento de modo todavía dice «elegí la Científica Calculadora» (el nombre crudo del control).

### Rondas 20–21 y lote ciego d (14:50–15:15)

Lote ciego d, diez órdenes nuevas: 9/10 a la primera. d1 «en Configuración andá a Personalización y decime qué
tema está activo» fue a la ruta de música («tema» = canción) en vez de al motor; ahora la misión con pregunta gana
(7eb2b09ea) y responde «el tema activo es Windows (claro)». Un modo elegido por su lugar sale determinista («Listo,
estoy en «Científica».»). En Steam, cuando ya estaba en la biblioteca y la pantalla no puede probarlo, el final lo
dice con honestidad: «Parece que ya estabas en «Biblioteca», pero no pude confirmarlo en la pantalla.» pytest
completo 19 254 sin fallos; Integración de computer use y suelo 202.

## v3 (2026-10-07/09): compañero que no molesta

Goal `documentacion/GOAL_COMPUTER_USE_V3_2026-10-08.md`. Arnés: `scripts/cu_live/` con el medidor de molestia
(`molestia/medidor.py`): un usuario simulado escribe en su propia ventana («BAXY usuario simulado», un EDIT Win32 del
medidor) 2 s de cada 3 y mueve el ratón dentro de ella; ganchos de bajo nivel separan su input (marca `dwExtraInfo`
propia), el de BAXY y el input real del dueño (sin `LLKHF_INJECTED`: la medición se pausa). La medición va desde la
línea `runtime` de la App hasta el final + 2 s.

### Línea base de molestia (producto sin arreglos, `fable/cu-universal-v3` @ d5b19f156, 17:50–20:20)

`BANCO_72.txt` completo con el usuario simulado activo (42 casos en la primera corrida; los 30 restantes repetidos tras
archivar el journal lleno del perfil de prueba, ver abajo). Agregado de `molestia/molestia_sum.py`:

| Medida | Base |
|---|---|
| caracteres del usuario perdidos | **3 383** (todos los casos con un acto) |
| caracteres insertados / teclas de BAXY en su ventana | 0 / 0 |
| robos de foco | **70** en 72 casos (uno por misión, dura toda la misión: 630 s en total, 4,7–37 s por caso) |
| movimientos de cursor / clics de BAXY | 26 / 25 |
| actos fuera de una pausa del usuario | 232 |
| ráfagas restauradas | **1 / 165 (0,6 %)** |
| la ventana del usuario no vuelve al frente al final | 70 / 72 |
| casos con el dueño activo (excluidos) | 0 |

En la primera pasada ciega v3 (mismo producto, 95 casos medidos) aparecieron además **75 teclas de BAXY dentro de la
ventana del usuario** (v3-06 Outlook 21, v3-25 Visor de eventos 48, v3-35 Notas rápidas 6, v3-08 1): con la ventana
del usuario delante y la app de la misión detrás, el texto se envió al frente. Es el fallo de seguridad que corrige la
entrega dirigida de la ronda 1.

Hallazgo de entorno: a las 18:33 el journal del perfil de prueba llegó a 65 MB; con el tope de 64 MiB y 2 MiB de
reserva por escritura el Core rechazó toda operación y 56 casos seguidos salieron `runtime_not_ready`. El journal se
archivó entero y se encargó la rotación en el producto (rama `fable/cu-v3-journal`).

### Primera pasada ciega v3 (producto sin arreglos, 20:05–22:25)

72 órdenes ciegas `v3-*` en 21 apps nuevas y 24 casos de tipos de tarea `t-*`, escritos por sala limpia antes de
cualquier arreglo (commit ef9521445), corridos una vez con el usuario simulado y sus estados base
(`estado/casos.json`). Verificación independiente por captura + volcado UIA (`verificar.ps1`) + traza, nunca por la
frase de BAXY (12 verificadores; veredictos en `%LOCALAPPDATA%\BAXY\cu-v3\evid_v3_primera_pasada_veredictos.json`):

| Lote | Logrado | Límite honesto | Falso éxito | No logrado | No corrió |
|---|---|---|---|---|---|
| v3 (72) | **6** | 7 | **11** | 48 | 0 |
| tipos (24) | **0** | 0 | 1 | 22 | 1 |

Causas de los no logrados y falsos éxitos: lectura del pedido 27 (preguntar lo que el pedido ya daba, escribir la
orden entera en un buscador, rutas de archivo sin resolver), no encontró el lugar 14, clic fallido 10, estado base 9
(un caso deja un diálogo que rompe el siguiente; Outlook sin cuenta; OneNote sin sección), app elevada 5 (Administrador
de tareas: límite real de Windows), texto en la ventana equivocada 3, sin cuenta 3, tiempo 1. Finales no honestos: 27.

### Uso real: línea base de la tanda 1 (punto 9; producto sin arreglos + driver, 22:28–22:36)

32 mensajes (20 conversaciones, 16 mensajes dentro de conversaciones dependientes) escritos por sala limpia, tecleados
en el compositor real de la ventana oficial (`scripts/uso_real/tanda.ps1`, perfil aislado `uso-real-v3`). Juez
independiente con las reglas del dueño (volumen/brillo relativo pregunta la cantidad; enviar se confirma):

| Medida | t1 base |
|---|---|
| bien hechos, flexible (D71) | **23/32 (71,9 %)** |
| bien hechos, estricto | 19/32 (59,4 %) |
| repeticiones idénticas tras una corrección | 1 culpable (el top 5 inventado, repetido) |
| mediana de los fáciles | 3,7 s (17 de 26 pasan de 3 s; peores 49,9 s lo-fi en Spotify, 20 s Los Prisioneros) |

Causas por mecanismo: respuestas armadas con resúmenes de búsqueda que no traen el dato («Brasil» ganó el Mundial 2014,
un top 5 de taquilleras sacado de una galería), lugares y fechas sin interpretar («valpo», «this weekend», «viernes por
la tarde»), pedidos creativos desviados a una pregunta, confirmación de cerrar Configuración sin trabajo que perder, y
finales que no cuadran con el acto («Abrí» por «Creé», mezcla de idiomas). El informe de la tanda inflaba la latencia
del último turno de cada conversación (sumaba el saludo de la siguiente): corregido en el arnés.

### Uso real: tandas de desarrollo (ventana oficial, juez independiente)

| Tanda | Build | Flexible | Estricto | Repeticiones tras corrección | Mediana fáciles | Causas principales |
|---|---|---|---|---|---|---|
| t1 base | sin arreglos | 23/32 (71,9 %) | 19/32 | 1 | 3,7 s | inventos desde resúmenes de búsqueda, lugares/fechas sin interpretar, pedidos creativos desviados |
| t2 | rondas 1–4 | 14/30 (46,7 %) | 12/30 | 2 | 3,0 s | Spotify cortado por la tecla 0xB9 de UIA (molestia2), misión en la app equivocada, «lado a lado» → YouTube, listas |
| t3 | rondas 1–4 | — (no juzgada: regresiones aisladas por regr6) | — | — | — | Paint con un diálogo dejado por un caso, «busca en google» respondido de memoria, juegos propios vs recomendación |
| t4 | rondas 1–6 | 14/30 (46,7 %); 14/27 sin los 3 turnos tapados | 9/30 | 1 | 3,4 s | navegación verificada por host (pestaña vieja), obras inventadas (Cortázar), corrección «X, no Y», «nuevo» reutilizó un documento abierto |

Las tandas t2–t4 son más difíciles que t1 (más pasos de computer use dentro de la conversación) y corrieron con dos
ventanas elevadas «siempre visible» (Administrador de tareas y Teclado en pantalla, abiertas por pruebas a las 02:25 y
03:20) que el agente no puede cerrar sin elevación. Cada causa medida va a una ronda de arreglos (rondas 6 y 7).

### Molestia tras las rondas 1–6 (banco de 72 con el usuario simulado, 06:30–07:46 del 2026-10-08)

Mismo arnés y mismo banco que la línea base (`evid_banco_r6_molestia.txt`):

| Medida | Base | Rondas 1–6 |
|---|---|---|
| caracteres del usuario perdidos | 3 383 | **284** |
| caracteres insertados / teclas de BAXY en su ventana | 0 / 0 (75 en la pasada ciega) | **0 / 0** |
| robos de foco | 70 (630 s) | 41 (60 s) |
| movimientos de cursor | 26 | 13 |
| actos fuera de pausa | 232 | 21 |
| ráfagas restauradas | 1/165 (0,6 %) | 25/44 (57 %), 14 más restauradas tarde |
| ventana del usuario sin el frente al final | 70 | 5 |

Lo que más movió: el worker descarta la tecla 0xB9 que UIAutomationCore inyecta para ceder el primer plano y devuelve
el frente con un hotkey propio marcado (uia-sin-frente); texto dirigido sin teclado; clic por patrón; apertura y vista
sin traer la ventana; ráfagas cortas dentro de pausas con restauración exacta. Con el usuario simulado tecleando 2 s de
cada 3, 7 misiones pararon por «empezaste a usar el PC» en vez de esperar la siguiente pausa (ronda 8: reintento tras la
pausa). Éxito de ese banco con el usuario simulado activo: 54/72; el criterio de regresión se mide sin él.

### v3 sin árbol (punto 3): cobertura antes y después

Medido en dos tiempos sobre `fable/cu-universal-v3`, sin tocar `src/` ni hacer commits:

- **2026-10-08, 05:26–05:55** (@ fc9d50bc4): las 16 órdenes. Quedaron 7 con la parte de tooltip sin medir, porque el
  Administrador de tareas y el Teclado en pantalla, ambos `topmost`, tapaban.
- **2026-10-09, 01:53–02:25** (@ bd0e7e286): esas 7, más S2 y S8 repetidas para ver si son estables. Ya no había
  ninguna ventana `topmost` ajena: sólo la barra de tareas.

En el segundo tiempo se usó siempre el turno del escritorio (`turno.sh tomar/soltar evid4a`), con seis turnos de 175,
106, 111, 16, 7 y 14 s. El lote en vivo siguió corriendo entre turno y turno.

Steam y Spotify ya estaban abiertos y no se cerraron. Paint lo abrí yo tres veces y lo cerré cada vez por su PID
exacto (47428, 56180 y 9088).

La evidencia en bruto está en `%LOCALAPPDATA%\BAXY\cu-v3\evid_p3p6\` (08-10) y `...\evid_4a\` (09-10). En `evid_4a`:

- `tip_steam_{1,2,3}.txt`, `tip_otras_1.txt` y `tip_paint_2.txt`: la prueba en vivo del producto;
- `tip_probe_*.txt`: la sonda que lee la pantalla;
- `*-despues.png`: capturas de pantalla con el cursor encima del ícono;
- `t*_at_point*.txt`: qué ventana hay en cada punto;
- `cobertura_detalle.txt`;
- los scripts `turno{1..6}.sh`.

**Método** (el mismo del 08-10)

- **Antes** = el `Name` de UIA más el OCR de la ventana.
- **Después** = lo de antes, más dos fuentes:
  1. el nombre de respaldo del worker (HelpText, LabeledBy o AutomationId), con `scripts/cu_live/cobertura_sin_arbol.ps1 -Detalle`;
  2. la etapa de tooltips del producto (`WindowsVisibleTooltipLocator`), con su comprobación en vivo:

     ```
     BAXY_TOOLTIP_LIVE_CHECK=<proceso> BAXY_TOOLTIP_LIVE_CAP=40 \
       dotnet test tests/Baxy.Providers.Windows.Tests -c Release --no-build \
       --filter "FullyQualifiedName~TooltipHoverLiveCheck"
     ```

     El binario de pruebas es el Release de 2026-10-09 01:43, y su `DesktopUiaWorker.ps1` es idéntico al de `src`.
- **Controles independientes:**
  - `tip_probe.ps1`: deja el cursor sobre el ícono y lee por OCR la franja de pantalla;
  - `hover_shot.ps1`: guarda una captura de pantalla antes y después del hover;
  - `at_point.ps1`: confirma qué ventana está en el punto. Antes de cada sonda, el punto era de Steam, Spotify o
    Paint, según el caso.
- **«Sí» en el después** exige que el producto haya leído la etiqueta. Si el tooltip existe pero el producto no llega
  a ese ícono, cuenta como «no», y se anota.

**Las 16 órdenes**

| # | Orden | App | Destino | Antes | Después (fuente y lecturas) |
|---|---|---|---|---|---|
| S1 | «abrí las notificaciones de Steam» | Steam (CEF, sin árbol) | campana de la barra superior | no | **sí**, por `tooltipOcr`: «Ver notificaciones». El producto la leyó en 2 de 3 pasadas (la 1.ª dio `change_is_no_tooltip`), y la sonda en 2 de 2. Es la candidata 2, así que entra en las 6 de un clic. |
| S2 | «poné Steam en modo Big Picture» | Steam | ícono Big Picture | no | **sí**, por `tooltipOcr`: «Entrar en el modo Big Picture». El 09-10 la leyó el producto 3 de 3 veces y la sonda 2 de 2; el 08-10, 1 de 2. En total, 4 de 5 lecturas del producto. Es la candidata 3. |
| S3 | «volvé atrás en Steam» | Steam | flecha ← | no | **no**: el ícono no tiene tooltip. El producto dio `change_is_no_tooltip` 3 de 3 veces (es la candidata 5) y la sonda no vio texto nuevo 2 de 2 veces. |
| S4 | «abrí los filtros de la biblioteca de Steam» | Steam | ícono embudo | no | **no**. El tooltip existe: la sonda leyó 2 de 2 veces «Opciones de filtrado avanz[ado]». Pero el producto no lo pasa: no está entre las 40 primeras candidatas de las 64. |
| S5 | «mostrá la biblioteca de Steam en cuadrícula» | Steam | ícono rejilla | no | **no**. El tooltip existe y dice «Tus colecciones» (sonda, 2 de 2), pero el producto tampoco llega a él. Aunque llegara, la etiqueta no dice «cuadrícula». |
| S6 | «abrí la configuración de Novedades en Steam» | Steam | engranaje junto a «Novedades» | no | **no**: no tiene tooltip. El producto dio `change_is_no_tooltip` y después `tooltip_unread` (es la candidata 36 o 43), y la sonda no vio nada 2 de 2 veces. |
| S7 | «abrí Amigos y chat en Steam» | Steam | botón inferior derecho | **sí**, por OCR («Amigos y chat») | sí, igual |
| S8 | «subí al principio de la lista en Steam» | Steam | flecha ⌃ abajo a la derecha | no | **no**: no tiene tooltip, y es estable. El producto dio `tooltip_unread` 2 de 2 veces (la 1.ª pasada agotó el presupuesto antes de llegar) y la sonda no vio nada 2 de 2 veces el 09-10 y 1 de 1 el 08-10. |
| D1 | «andá a la configuración de usuario de Discord» | Discord | «Ajustes de usuario» | **sí**, por `Name` (ARIA) | sí |
| D2 | «silenciá el micrófono en Discord» | Discord | «Silenciar» | **sí**, por `Name` | sí |
| P1 | «en Spotify abrí la cola» | Spotify | «Fila de reproducción» | **sí**, por `Name` | sí |
| P2 | «conectá Spotify a otro dispositivo» | Spotify | «Conectar a un dispositivo» | **sí**, por `Name` | sí |
| P3 | «abrí el menú de Spotify (los tres puntos)» | Spotify | botón «⋯» sin nombre, en (948,40) | no | **no**: no tiene nombre de respaldo (HelpText, LabeledBy ni AutomationId) ni tooltip. El producto dio `change_is_no_tooltip`, la sonda no vio texto y la captura con el cursor encima no muestra tooltip. |
| W1 | «abrí un chat nuevo en WhatsApp» | WhatsApp | «Nuevo chat» | **sí**, por `Name` | sí |
| W2 | «mostrame más filtros de chats en WhatsApp» | WhatsApp | pestaña ▾ sin nombre | no | **sí**, por AutomationId: `additional-filters` se lee «additional filters». Es inglés en una interfaz en español (medido el 08-10). |
| A1 | «abrí el panel de capas en Paint» | Paint | botón «Capas» sin nombre, en (1474,136) | no por `Name`. El OCR sólo ve el rótulo «Capas» del grupo, fuera del botón: es parcial y no cuenta. | **no**: no tiene nombre de respaldo. El producto dio `nothing_changed` 2 de 2 veces, y la captura con el cursor encima no muestra tooltip ni realce. No se puede distinguir «sin tooltip» de «Paint no reacciona a un hover sintético». |

**Agregados**

| | 16 órdenes, 5 apps | Sólo Steam (la única ventana realmente sin árbol: 3 nodos y 0 accionables) |
|---|---|---|
| Antes | 6/16 (S7, D1, D2, P1, P2, W1) | 1/8 (S7) |
| Después | **9/16** (+S1 y +S2 por tooltip OCR, +W2 por AutomationId) | **3/8** (S7, S1, S2) |
| Sin medir | **0/16** | 0/8 |
| Con tooltip legible a la que el producto no llega | 2 (S4, S5) | 2 |
| Sin ninguna etiqueta (ni nombre de respaldo ni tooltip) | 5 (S3, S6, S8, P3, A1) | 3 |

**Cobertura del nombre de respaldo el 09-10** (`cobertura_detalle.txt`)

| App | Accionables | Sin `Name` | Recuperados | Antes → después |
|---|---|---|---|---|
| Steam | 0 (3 nodos) | 0 | 0 | 0 → 0 |
| Spotify | 108 | 4 | 0 | 104 → 104 |
| Paint | 102 | 1 | 0 | 101 → 101 |

Es lo mismo que el 08-10: el respaldo sólo recupera el AutomationId de WhatsApp.

**Fallos encontrados** (sólo descritos; `src` sin tocar)

1. **La lectura del tooltip de Steam sigue inestable.** Ahora falló la campana: el 09-10 la 1.ª pasada dio
   `change_is_no_tooltip` y las otras dos leyeron «Ver notificaciones». El 08-10 había fallado Big Picture.
   - El 09-10 no había ninguna descarga en curso, así que la hipótesis de entonces (píxeles que cambian por una
     descarga) no lo explica todo.
2. **El OCR del cambio da etiquetas falsas.** En la pasada 3 se leyeron 15 etiquetas:
   - 3 limpias: «Ver noticias de Steam», «Ver notificaciones» y «Entrar en el modo Big Picture».
   - 2 reales pero con ruido: «Ordenar por actividad reciente Ordenar por actividad reciente •» y «Mostrar solo los
     juegos listo • Instalados en este ordena'…».
   - 10 falsas:
     - 6 regiones de la lista de juegos con «Batmanw: Arkham Knight»: es el texto de la fila resaltada, no un tooltip;
     - 4 tarjetas de noticias con «NOTICIAS iYa tenemos los resultados…».

   Esas etiquetas van a `TooltipLabelCache` por firma de ventana. Una orden que nombre ese juego podría pulsar una
   región equivocada. Es un riesgo, no lo probé.
3. **Los tooltips interiores quedan fuera del alcance de un clic.**
   - En la biblioteca maximizada, Steam da 64 candidatas.
   - La prueba con tope 40 tarda 52–53 s, y una pasada agotó el presupuesto de 60 s en la candidata 27
     (`tooltip_budget_spent`).
   - El producto en un clic pasa 6 candidatas en 9 s (`MaxCandidates = 6`, `BudgetMs = 9000`), y no llega a ellos.
   - Sin una etiqueta ya guardada, el embudo y la rejilla son inalcanzables, aunque su tooltip existe y es legible
     (S4 y S5).
4. **Cursor no devuelto en 1 de 3 pasadas de Steam:** fue la que agotó el presupuesto, que terminó con
   `cursor devuelto False`.
   - `HoverAsync` llama a `burst.Restore()` en su `finally`, así que la causa no está clara. Puede que la persona
     moviera el mouse durante los 71 s.
   - En las otras 5 pasadas el cursor volvió.
5. **Sin etiqueta posible con estas fuentes:** 5 de 16 (S3, S6, S8, P3 y A1). Son íconos sin tooltip, o que no
   reaccionan al hover. Sólo los cubriría la visión (`DECISION_VISION_V3.md`) o un procedimiento aprendido.
6. **Para el criterio:**
   - De las «≥ 3 apps sin árbol», sólo Steam lo es de verdad.
   - Spotify, Paint y WhatsApp tienen árbol, pero con íconos sin nombre.
   - Discord nombra todo lo que se le pidió.

   Las 16 órdenes y las 5 apps cumplen la cantidad pedida. La parte estrictamente «sin árbol» son 8 órdenes de 1 app.

**Veredicto para el criterio 4a:** medido de punta a punta, con 0 órdenes sin medir. La cobertura pasa de **6/16 a
9/16** (en Steam, de 1/8 a 3/8), con dos límites:

- 2 órdenes más (S4 y S5) tienen un tooltip legible al que el producto no llega dentro del tope de candidatas;
- el OCR de tooltips da etiquetas falsas en Steam (10 de 15 en una pasada).

### Rondas 26–29 (2026-10-10): banco B, latencia, tandas y pasada

Todas las cifras de casos salen de jueces independientes (subagentes sin acceso al código, con journal, UIA antes y
después y capturas); los casos cuya firma (alcanzado, pasos, final) no cambia respecto de la corrida juzgada anterior
heredan su veredicto y se cuentan como «logrado por firma». Banco B = `BANCO_72` sin usuario simulado
(`banco.sh <nombre> 0`), en el notebook. La latencia es por orden, mediana (p50), con el pedido enviado 30 ms después
de quedar lista la mente («en frío»); «tras la bienvenida» envía el primer turno con la bienvenida ya dicha, como medía
v2 (`CU_TRAS_BIENVENIDA=1`).

| Corrida (código) | Logrados | Límite honesto | Falsos éxitos | p50 orden | p50 misión |
|---|---|---|---|---|---|
| bueno-1 (c24b, inicio del día) | 58/72 | — | — | 7,80 s | — |
| candidata D (apertura con una mirada) | 65/72 | — | 0 | 7,58 s | — |
| ronda 27 = `cu-v3-bueno-2` (4795aeef5) | 68/72 | 1 | 0 | 7,66 s | — |
| ronda 28 = `cu-v3-bueno-3` (e219f492c), en frío | 66/72 | 1 | 0 | **6,14 s** | 5,14 s |
| `cu-v3-bueno-3`, tras la bienvenida | (contaminada: quedó un Excel abierto) | | | **5,41 s** | 4,72 s |

- Los tres casos que bueno-3 pierde frente a bueno-2 en esa corrida son c1, u1 e y8. Repetidos: u1 3/3 e y8 3/3
  (logrados); c1 0/6 (inestable por el propio caso, no por la ronda).
- La bajada de 7,66 s a 6,14 s viene del arranque: la bienvenida ya no ocupa el carril de la mente, la primera lectura
  de UIA y los lectores del turno se pagan al arrancar y no en el primer pedido, y la apertura se confirma con una
  mirada. **La meta de ≤ 5 s no se alcanza** ni en frío (6,14 s) ni tras la bienvenida (5,41 s).
- p90 de la orden: 12,7 s en frío y 11,7 s tras la bienvenida.

**Tandas de uso real** (t1–t4, 123 turnos, en redpc por tarea programada; juez independiente por tanda; «flexible»
cuenta lo hecho bien aunque dicho distinto, regla D71):

| Código | Flexible | Estricto |
|---|---|---|
| v3 de la mañana | 90/123 (73,2 %) | 72/123 |
| candidata de la ronda 27 | 93/123 (75,6 %) | 76/123 |
| bueno-2 | 100/123 (81,3 %) | 80/123 |
| ronda 28 parcial + cierre de lo nombrado | 104/123 (84,6 %) | 84/123 |

La mediana de latencia de los turnos fáciles va de 1,98 s (t1) a 3,12 s (t4). **La meta de 90 % no se alcanza**: los 19
fallos que quedan son, por grupos, Word/Excel sin ventana atada (4), grupo de la cinta plegado en Paint (3), respuestas
de conversación inventadas o con búsqueda corta (6) y sueltos (6).

**Pasada completa sobre bueno-2** (72 órdenes ciegas v3 + 24 de tipos + 4 de WhatsApp/Epic, con usuario simulado;
14:07–16:33): **v3 18/72 (25 %) con 4 falsos éxitos** (v3-31, v3-37, v3-59, v3-70); **tipos 4/24** (t-form-1,
t-file-2, t-file-4, t-long-1); **WhatsApp/Epic 1/4** (wa-1). 67 de las 100 acaban en un «no pude» del propio motor.
Por causa (`cu-v3/libro_vetos_pasada_r27.md`): el modelo elige mal con el control a la vista (12), el control no entra
en lo que ve el modelo (7), el acto correcto se hizo y no se cierra (7), capacidad ausente como arrastre, scroll largo
o clic derecho (6), la ventana no llega al frente con el usuario simulado delante (5), la misión no ata ventana cuando
la orden no nombra aplicación (4), veto incorrecto (3), lectura del pedido (3). **La meta de 95 % no se alcanza**; es
la misma cifra que la pasada r23c (18/72): las rondas de hoy mejoraron banco, latencia y tandas, no la amplitud.
