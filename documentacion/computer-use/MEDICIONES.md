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
`fable/cu-universal-v2`. Evidencia por caso en `%LOCALAPPDATA%\BAXY\cu-universal-evidencia\v2-<caso>\`
(`events.jsonl`: pedido y finales; `trace.jsonl`: ms por etapa y la línea `computer_use.end`; `model_calls.jsonl`:
llamadas al modelo). Cada fila es la **última corrida** del caso (hora local y commit del conductor); las
anteriores sólo se citan cuando enseñaron un arreglo. Columnas: *turno* = `latency_ms` del final en la
conversación (lo que espera la persona); *misión* y *modelo* = `ms` y `model_ms` de `computer_use.end` (modelo =
tiempo de decisión del motor, no la comprensión ni la composición); *pasos* = pasos de la misión. Verificación
independiente por UIA, Shell o captura, nunca por el final de BAXY.

### Casos

| Caso | Pedido | Resultado | Turno | Misión | Modelo | Pasos | Corrida |
|---|---|---|---|---|---|---|---|
| s01 | en la calculadora calculá 37*12 (cerrada) | ✓ pantalla «444», expresión «37 × 12=» | 4,4 s | 2 509 ms | 18 ms | 3 (abrir, escribir, Enter) | 00:46, c52461e5 |
| s02 | en el Reloj andá a Cronómetro | ✓ `ListItem Cronómetro [selected]`; el Reloj abrió ya en esa página | 4,6 s | 2 555 ms | 3 ms | 1 (abrir) | 01:12, 165aa153 |
| s03 | en Configuración andá a Bluetooth y dispositivos | ✓ `ListItem «Bluetooth y dispositivos» [selected]` | 3,3 s | 1 496 ms | 4 ms | 1 (clic) | 00:57, ea14333b |
| s04 | en el Explorador de archivos andá a Descargas | ✓ Shell: `Downloads \| file:///C:/Users/usuario/Downloads` | 6,4 s | 3 464 ms | 5 ms | 1 (clic; el Explorador seguía abierto) | 00:56, ea14333b |
| s05 | en el Panel de control abrí Programas | ✓ título «Programas» | 4,7 s | 2 870 ms | 12 ms | 2 | 00:53, a6c10401 |
| s06 | en el Administrador de tareas andá a Rendimiento | límite honesto: ventana de administrador, dicho con esa causa | 33,6 s | ≈31,5 s (traza) | — | 1 (`app.open` sin verificar, 30,2 s) | 01:04, b396dfe8 |
| s07 | abrí Paint y elegí la herramienta Texto | ✓ `Button Texto [on]` | 6,5 s | — (plan tipado `app.open` + `input.visible.click`, no misión) | — | 2 | 00:57, ea14333b |
| s11 | en Discord andá al canal Cotele → «no» | ✓ BUSCAR halló el canal (clic en el buscador, escribir, clic en el resultado); el clic en el canal de voz preguntó; «no» → no se unió | 6,8 s a la pregunta; 0,6 s el «no» | ≈3,1 s hasta la pregunta (traza) | 0 ms (sin llamada del motor) | 3 + el confirmado | 01:15, e8a6a560 |
| s12 | en Steam andá a la biblioteca | ✓ captura: BIBLIOTECA resaltada, «Tus colecciones» | 5,5 s | 3 836 ms | 662 ms | 2 | 01:12, 165aa153 |
| s14 | en Discord mandale a Ron92 "prueba BAXY 14" → «no» | ✓ preguntó antes de enviar; «no» → no se envió | 9,7 s a la pregunta; 0,7 s el «no» | — (ruta tipada `message.recipient.resolve` + `message.send`; resolver ≈7,9 s) | — | — | 01:17, e8a6a560 |
| c1 | abrí el Bloc de notas, escribí "lista: pan", apretá Enter y escribí "leche" | ✗ el editor quedó en «lista:nnnnleche» y la misión se dio por lograda (las comprobaciones no leen lo escrito); en arreglo | 7,9 s | 3 172 ms | 0 ms (procedimiento reproducido) | 4 en 3 sub-objetivos | 01:31, e04bc54b |
| c3 | en el Explorador de archivos andá a Documentos y creá una carpeta llamada baxy-prueba | ✗ el plan no llega a la misión (`clarification.rejected machine_slot_ask`, final `internal_code;retry_exhausted`); carpeta no creada; en arreglo | 8,5 s | — | — | 0 | 01:34, e04bc54b |
| c6 | en Discord abrí el chat con Ron92, escribí "prueba BAXY C6" y mandalo → «sí» | ✓ preguntó antes de enviar; con el «sí», enviado al MD de prueba | 3,4 s a la pregunta; 1,3 s tras el «sí» | 1 842 ms | 5 ms | 2 en 3 sub-objetivos (el chat ya estaba abierto) | 01:32, e04bc54b |
| c7 | en Discord andá al canal Cotele y después en Steam andá a la tienda → «no» | ✗ falso negativo: Discord logrado (4 pasos); Steam ya estaba en TIENDA (captura) y el clic que no cambia nada se leyó como fallo. Arreglado en e4254ef6; **re-corrida pendiente** | 11,2 s | ≈9,2 s (traza) | 1 016 ms (1 llamada) | 6 | 01:33, e04bc54b |

Corridas anteriores que enseñaron un arreglo: s04 a las 00:47 (58,5 s, el escritorio tomado por la ventana del
Explorador → ea14333b); s06 a las 00:53 (36,1 s, «la pantalla dejó de cambiar» → ventana elevada dicha, b396dfe8);
s02 a las 00:47–01:08 (aclaración o «no hay elemento»: el límite «cronómetro» y el veto de conservación anulaban la
misión → fa009cf1, 165aa153); s12 a las 00:57–01:09 (la ventana de arranque de Steam buscada como la app →
b396dfe8; la Tienda pasó por la Biblioteca → fa009cf1; procedimiento aprendido de ese falso éxito → 165aa153); s11 a las 01:05–01:13 (una
tarjeta de actividad con «Cotele» pasó por el canal → 165aa153, e8a6a560); c3 a las 01:16 (falso éxito: el eco de
lo escrito en la búsqueda pasó por la carpeta → 2e06fa28); c6 a las 01:25 (envió sin preguntar → 3ae1dc88).

### Latencia por paso (últimas corridas)

| Parte | n | Rango (p50) | Fase 4 (p50) |
|---|---|---|---|
| Decisión del modelo del motor (gramática de acto primero) | 2 | 657–1 016 ms | 2,7 s |
| Paso dictado sin modelo (BUSCAR y procedimientos incluidos) | 25 | < 20 ms | < 20 ms |
| `input.visible.click` | 12 | 255–1 301 ms (456 ms) | 1,2 s |
| `input.text.type` (SendInput en proceso) | 6 | 69–131 ms | 0,67 s |
| `input.key.press` (SendInput) | 2 | 67–73 ms | 0,67 s |
| `app.open` (apertura UWP por su marco) | 4 | 832–1 224 ms | 1,0 s; UWP 30 s sin verificar |

### Fase 4 frente a v2 (mismo caso o el más cercano)

| Caso | Fase 4 (2026-10-06) | v2 (2026-10-07) |
|---|---|---|
| Calculadora cerrada, calcular | «12×7»: turno 41,0 s, misión 35,9 s (apertura UWP 30 s) | «37*12»: turno 4,4 s, misión 2,5 s (≈9× el turno) |
| Reloj → Cronómetro | turno 34,9 s | turno 4,6 s, misión 2,6 s |
| Steam → Biblioteca | turno 11,2 s, misión 9,3 s (modelo 4,6 s), 2 pasos | turno 5,5 s, misión 3,8 s (modelo 0,66 s), 2 pasos |
| Panel de control → una categoría | «Sistema y seguridad»: turno 7,5 s, misión 5,6 s, 2 pasos | «Programas»: turno 4,7 s, misión 2,9 s, 2 pasos |
| Discord → canal Cotele | el motor no lo halló (6 clics, 53,7 s); se sirvió por `client.channel.locate`, 17,2 s | el motor lo halla con BUSCAR y pregunta a los 6,8 s |
| Discord, apretar Enter | misión 2,9 s, turno 4,6 s | sin corrida v2 |

### Límites medidos en v2

- Una app que corre como administrador (Administrador de tareas) no deja leer ni pulsar sus controles a un BAXY
  sin elevar: se dice con esa causa, pero sólo tras agotar la espera de 30 s del `app.open`.
- Lo escrito no se comprueba leyendo el campo: c1 dio por lograda una lista corrupta (en arreglo).
- Un pedido encadenado que el plan reformula como pregunta no llega al motor (c3, en arreglo).
