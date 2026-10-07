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
