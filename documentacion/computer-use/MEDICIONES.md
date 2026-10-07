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

Los casos u* son aplicaciones que el motor nunca había probado. **Banco principal: 21/24 correctos** (s06 cuenta
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
