# Fallos del e2e de práctica que no eran del modelo (ajuste c3, 2026-10-29)

Encargo: en el e2e de práctica del notebook (`D:\BAXYeval\renew_v1\e2e\practice.nbD.json`, 30 casos) se repiten
E008, E011, E014 y E023 con varios modelos. Para cada uno: ¿la App, el proveedor o la mente entregan un resultado malo
o incompleto, o el modelo interpreta mal un dato bueno? Sólo lo primero se arregla, aquí, en la rama `ft-c3-app`
(desde `ft-c3` 80684a524).

Evidencia leída (sólo lectura, copiada del NB): `D:\BAXYeval\renew_v1\runs\{c3base-s0,s1,s2, c3-m1-sB-s0..2,
c3-m2-sA-s0..2, c3-c2c-sB-s0..2}-e2e\`: `results.jsonl` (veredicto del oráculo), `events.jsonl` (cada `step` con
operación, argumentos y la `observation` exacta que leyó el modelo), `mente\turns.jsonl` (lo que decidió el modelo y
las ayudas), `E0NN\replies.json`. Todas esas corridas son del commit 7ee83b524 (`console.txt`).

## Resumen

| Caso | Fallos (corridas) | De quién | Arreglo |
|---|---|---|---|
| E008 búsqueda web | c2c-sB s1, m1-sB s1, m2-sA s1, base s2 | **App** (guarda `query_not_said`) + proveedor intermitente | 0d062d9cd |
| E011 Calculadora | base s0, m1-sB s0, m2-sA s0 | **Proveedor** (fallo sin datos) | ade6a43fe |
| E014 Configuración > Sonido | m1-sB s0, s1, s2; base s1 | Modelo | no se toca |
| E023 lista de tareas | base s0 | Modelo | no se toca |

## E008 — «busca en internet en qué año se fundó la ONU»

**Qué recibió el modelo.** En las 12 corridas, la primera llamada `web.search {"query":"año fundación ONU"}` volvió
`{"status":"rejected","error":"query_not_said","next":"nothing ran: this search has none of the person's words ..."}`
(`events.jsonl`, turno 8 de cada corrida). Es falso: la consulta lleva «año» y «ONU», que la persona dijo.

**Causa.** `src/Baxy.App/NetworkEgress.cs`, `Unsaid`: sólo se pesaban las palabras de 4 letras o más de la consulta.
Aquí queda una sola, «fundación», que no es «fundó» (`SameWord` pide 5 letras en común o que una empiece a la otra), y
«año» y «ONU» no se miraban. El rechazo es de la App en 12 de 12; lo que varía es lo que hizo el modelo después:
- c2c-sB s1 y m2-sA s1: no volvieron a llamar y dijeron «No busqué…» (fallo del oráculo). Con el dato malo de la App.
- m1-sB s1 y base s2: repitieron la llamada con `source: encyclopedia` y Wikipedia contestó
  `{"status":"failed","error":"web_search_unavailable"}` en ~500 ms; el modelo dijo «No puedo buscar en internet».
- Las 8 que pasaron repitieron la llamada y la búsqueda funcionó.

**Arreglo (0d062d9cd, App).** Una palabra de 2 o 3 letras cuenta cuando la consulta la escribe como sigla (todas
mayúsculas: «ONU», «BBC») y la persona la dijo o un resultado la dio, exacta. Una palabra corta en minúscula o con una
sola mayúscula («de», «Los») sigue sin pesar: así no entra ninguna lista de palabras (orden del dueño en aeb21b7c2) y
el held-out de 28 frases sigue igual. Prueba: `NetworkEgressTests.AnAcronymThePersonSaidIsTheirWord` (falló sin el
cambio en la aserción de «ONU»; con él pasa, y sigue rechazando «fundación OEA» y «de Centro Box»).

**Lo que no se tocó: Wikipedia sin respuesta.** `WikipediaSearchSource.SearchAsync` devuelve null (→
`web_search_unavailable`) ante un estado HTTP no 2xx, un error de red o un cuerpo que no es su JSON, y no guarda cuál.
En 2 de 7 llamadas a `encyclopedia` falló en ~500 ms (no fue el tiempo de espera); desde el PC, 6 de 6 peticiones
iguales con el mismo User-Agent dieron 200 (curl, 2026-10-29). Con lo registrado no se sabe si fue un 429 de Wikimedia o
la red del NB: arreglarlo sería adivinar. Si vuelve a salir, conviene registrar el estado HTTP en el recibo para tener la causa.
Con el arreglo de arriba la primera llamada ya no se rechaza, así que este fallo sólo cuenta si la fuente cae de verdad.

**Cómo comprobarlo en vivo.** En una copia de `ft-c3-app` compilada en el NB:
`py -3.12 -X utf8 scripts/renew/bench_e2e.py <etiqueta> --cases 'D:\BAXYeval\renew_v1\e2e\practice.nbD.json' --only E008`
y en `events.jsonl` el primer `step` de `web.search` debe ser `completed` (ningún `query_not_said`).

## E011 — «en la calculadora suma 250 más 175 y luego multiplica el resultado por 2»

**Qué recibió el modelo.** En las 3 corridas que fallan, tras abrir la Calculadora, `calculator.expression.evaluate
{"expression":"(250+175)*2"}` volvió `{"status":"failed","error":"calculator_needs_scientific_mode"}` y nada más.
Después:
- m2-sA s0: dijo «no puedo escribir paréntesis» y se rindió.
- m1-sB s0: seis clics en el menú «Sistema» y «está en modo Estándar… no puedo evaluar expresiones con paréntesis».
- base s0: pulsó las cifras a mano (`input.visible.click` con `label` «2», «5», «0» e índices de «Dos», «Cinco»,
  «Cero»), la Calculadora quedó en «36,» y lo dijo («está 36,0»); el oráculo leyó «La pantalla muestra 36 coma».

**Causa.** `src/Baxy.Providers.Windows/External/WindowsDeviceControlAdapter.cs`: el script sabe el modo (`mode` en su
JSON) y que el teclado Estándar aplica los operadores en el orden pulsado, pero el adaptador devolvía sólo el código: el
modelo no tenía cómo seguir. El dato que faltaba existe: m1-sB s1 y s2 escribieron «250+175*2» en el mismo teclado
Estándar y obtuvieron 850 (verificado por el oráculo).

**Arreglo (ade6a43fe, proveedor).** Con la ayuda `calculator_next` (la misma de «sin ventana»), el fallo trae
`observed: {mode: "standard", next: "nothing was pressed: the Calculator is in its Standard mode, whose keypad has no
( ) nor ^ and applies each operator in the order pressed, without precedence (2+3*4 gives 20 there); an expression
written in that order without them is evaluated there"}`. Fuente del comportamiento: el README de microsoft/calculator
(el modo Estándar evalúa cada orden en cuanto se introduce). Es un hecho, no una orden: no cambia el modo ni reescribe
la expresión. La traza de la mente (`_aids_seen`) lo anota como `calculator_next`. Pruebas:
`ExternalCapabilityHandlerTests.AParenthesisOnTheStandardKeypadSaysHowThatKeypadComputes` (falló sin el cambio),
`…WithTheAidOffCarriesNoHint`, y `test_mind_aids.py::test_the_standard_keypads_next_is_traced_as_the_calculators_aid`.

**Lo que no se tocó: el clic por visión en base s0.** Los clics con `label` «2» e índice 22 («Dos») no
coincidían, así que el índice no se pulsó (regla de la auditoría P3) y la etiqueta bajó por la cascada hasta la visión
(`controlIdentity` «vision.261.678», `method` «pointer»). La visión cayó en el botón de al lado: 2→«Tres», 5→«Seis»,
0→«Separador decimal» (lo dice el `after` de cada clic: «Se muestra 3», «Se muestra 36», «36 coma»).
`WindowsVisibleVisionLocator.OtherTextAt` no cuenta las cifras sueltas como «otra etiqueta», así que no lo detectó. Es
una debilidad del proveedor de visión, pero sin la captura ni la lectura OCR de ese momento no se puede probar un
arreglo. Además, el modelo tenía el dato (cada `after` decía el número mostrado) y siguió. Con el arreglo de arriba ese
camino ya no hace falta. Queda anotado para cuando haya evidencia en vivo.

**Cómo comprobarlo en vivo.** `bench_e2e.py <etiqueta> --cases '...practice.nbD.json' --only E011`. Si el modelo
escribe paréntesis, el `step` fallido debe traer `observed.mode` y `observed.next`, y el oráculo `Test-CalcShows '850'`
debe dar OK cuando el modelo reescribe la expresión en orden. Si aun con el dato el modelo no la reescribe, ya es del
modelo.

## E014 — «abre la configuración de sonido»: del modelo

- m1-sB s0, s1, s2 (oráculo `ABSENT`): la primera decisión fue `app.open {"appId":"Realtek Audio Console"}`
  (`mente\turns.jsonl`, confianza 0,985). El catálogo que leyó (`mente\catalog.configure.json`) es el mismo que el de
  base, que eligió `app.open {"appId":"Configuración","place":"sound"}`: ofrecía `place: "sound"` y la lista de apps
  instaladas, donde Realtek es una entrada más. La App abrió lo que se le pidió y lo dijo bien. Es elección del modelo.
- base s1 (oráculo «Sistema > Sonido > Propiedades»): abrió bien Configuración en sonido, y la mirada siguiente decía
  «Lugar a la vista: sound de Configuración … es el que pidió app_open en este turno». Después el modelo pulsó
  «Altavoces» sin que nadie lo pidiera y dejó la página en Propiedades. Dato bueno, acción de más: es del modelo.

No se toca. Para el ajuste: m1-sB confunde «configuración de sonido» con la consola del fabricante (3 de 3).

## E023 — lista de tareas: del modelo

base s0 (oráculo: falta «técnico» en «No hay tareas pendientes…»). En el turno «marca comprar pilas como hecha», el
modelo listó, completó «comprar pilas» (versión 2, correcto) y volvió a listar. `task.list` devolvió
`{"tasks":[{"title":"llamar al técnico","completed":false,…}],"count":1}`, que es verdad. Luego completó también «llamar
al técnico», que nadie pidió, y repitió los dos `task.complete` (`verification: unchanged`) hasta que la mente cerró el
bucle (`same_call_next`). Al final dijo «Ya estaban ambas hechas». Todos los resultados de la App eran correctos, y la
descripción de `task_list` dice que sin `status` sólo lista las abiertas. Es del modelo. No se toca.

## Verificación (PC, 2026-10-29)

| Peldaño | Comando | Resultado |
|---|---|---|
| 1 | `dotnet test tests/Baxy.App.Tests -c Release --nologo -v:minimal` | 466 pass, 0 fallos |
| 1 | `dotnet test tests/Baxy.Providers.Windows.Tests -c Release --nologo -v:minimal` | 3505 pass, 0 fallos |
| 1 | pruebas de la mente con el Python del runtime (`test_mind_aids.py` y `test_mind_bucle.py`, `-q`) | 126 pass |
| 2 | `ruff check src/baxy_mind/mind.py tests/test_mind_aids.py` (ruff 0.15.12 del sistema; el runtime no trae ruff) | sin hallazgos |
| 2 | `dotnet build Baxy.slnx -c Release --nologo -v:minimal -m:4` | 0 advertencias, 0 errores |

No se corrió el peldaño 3 entero (pytest completo y todas las suites .NET): el cambio son dos recibos y una guarda,
cubiertos por sus pruebas dueñas, y la CPU del PC la comparte la criba. Este worktree no tiene
`scripts/test_source_quality.ps1`.

No se corrió ningún banco en vivo: lo decide la sesión líder. La rama no está subida a `hub`.

---

# Segunda vuelta: todos los fallos de los bancos de práctica del 2026-10-29

Encargo: barrer los fallos de los bancos de práctica abiertos de hoy y arreglar en código los que sean de la App, el
proveedor o la mente; lo que es conducta del modelo se anota para que lo cubran los datos (orden del dueño: «sin
semántica, sólo ft que cubra todo»). Nada sellado se abrió.

**Evidencia leída (sólo lectura).**
- e2e del NB (25 corridas de hoy, `D:\BAXYeval\renew_v1\runs\`): `c3base-s0/s1/s2`, `c3base-s0b-codigo-viejo`,
  `c3-{c2c-sB,c2c1-sA,c2cr05-sA,m1-sB,m2-sA}-s0..2`, `c3app-{base,c2c-sB}-s0..2`. Los `c3-*` y `c3base-*` son del commit
  7ee83b524; los `c3app-*`, de fe0c80d68 (con E008 y E011 arreglados).
- e2e del PC (16 corridas, `F:\BAXYeval\renew_v1\runs\c3pc-*-e2e`, commit 80684a524; `c3pc-c2cr05-sA-s1` sin
  `results.jsonl`).
- e2e de la VM Azure (4 corridas `vmc3-*`, Windows en inglés, commit 583d06817 = 7ee83b524 + llama remoto) y
  `C:\BAXYeval\vm\logs\`.
- Banco de decisión: feria (`c3-*-feria-s0..5`, 19 modelos, 114 corridas por caso) y decision2 (`c3-*-d2-s0`, 18
  modelos), con su `*.trace.jsonl`.

De cada corrida: `results.jsonl` (oráculo), `events.jsonl` (cada `step` con argumentos y la `observation` exacta que
leyó el modelo) y `mente\turns.jsonl` (lo que decidió el modelo antes de la App).

## Resumen

| Caso | Fallos | De quién | Evidencia | Arreglo |
|---|---|---|---|---|
| E017 Bloc de notas, guardar como lista.txt | 12/45 | **Proveedor** (Ctrl+S) y modelo | Ctrl+S «delivered» al Bloc de notas de Windows 11: 16 de 16 sin «Guardar como» | 2dc466867 |
| E014 configuración de sonido (VM en inglés) | 3/4 VM | **App** (lugares sólo con el nombre en español) | `mente\turns.jsonl`: el modelo pidió `{"appId":"Settings","place":"sound"}`; el `step` lleva `"appId":"Configuración"` y `app_not_found` | 00df7ffb1 |
| E010 calculadora 12 por 7 | 7/45 | PC c2c1 s1: **proveedor** (candidatos); 2: modelo; 4 VM: entorno | `app.open "calc.exe"` → `candidates` Access, Calendar, CapCut, Claude, CODEX, sin la Calculadora | 3db37d8a7 |
| E021 `python --version` | 11/45 | Modelo | el resultado traía `stdout "Python 3.10.11"`; el modelo volvió a llamar y la segunda pidió el sí | familia «salida de consola» |
| E011 calculadora (250+175)*2 | 12/45 | App, ya arreglado; VM: entorno | 0 de 6 en `c3app`; el PC (80684a524) recibió `calculator_needs_scientific_mode` sin dato; VM `setup_fallido` | ade6a43fe |
| E008 búsqueda ONU | 10/45 | App, ya arreglado | todas anteriores al arreglo (`query_not_said` en la 1.ª llamada); 0 de 6 en `c3app` | 0d062d9cd |
| E012 Bloc de notas «hola desde BAXY» | 5/45 | VM: entorno y oráculo; PC c2c05 s2: proveedor | ver abajo | anotado |
| E023 lista de tareas | 5/45 | Modelo | `task.list` dice bien «llamar al técnico» abierta; el modelo la completa sin pedido | familia «sólo la tarea nombrada» |
| E029 pizza | 5/45 | Oráculo del banco | «No pido comida…» es una negativa correcta que su regex no admite | ninguno |
| E020 archivo más grande | 2/45 | Modelo | `file.find order size` dio b.dat (120 KB) primero y sub\d.bin (80 KB); dijo que no pudo | familia «leer el orden dado» |
| E006 compras.txt | 2/45 | Modelo | `file.write` con «pan\nleche\nhuevos» en vez del texto dicho | familia «texto literal» |
| E009 hora (VM) | 1/4 VM | Modelo | sin llamada; el contexto dice la hora local (00:58) y respondió «1:58» | familia «hora del contexto» |
| Feria y decision2 | 15 casos fallan en todas | Modelo o expectativa del caso | sólo la primera decisión; un `turn.decide` por caso en la traza, sin herramienta | ninguno |

## E017 — Ctrl+S no guarda en el Bloc de notas de Windows 11 (proveedor)

**Qué recibió el modelo.** En las 8 corridas fallidas de hoy que pulsaron Ctrl+S (PC base s0, s1, s2; c2c05 s0, s2;
rpo3 s1; NB c3app-base-s0 y c3base-s0b) el recibo fue `{"status":"completed","verification":"delivered_only",
"observed":{"delivered":true,"key":"ctrl_s","sentTo":{"title":"*lista pilas, cables: Bloc de notas","process":
"Notepad"},"restored":true}}`, y la mirada siguiente mostró la ventana principal, sin diálogo, con el texto intacto
(«lista: pilas, cables», sin una «s» de más). Decenas de segundos después seguía sin diálogo: el clic en «Guardar como»
no lo encontraba y el menú «Archivo» se abría (con un diálogo modal no habría podido). Con las corridas de días
anteriores que siguen en `F:\BAXYeval\renew_v1\runs` (pc-bis2, pc-i10c, pc-l5a, pc-l8, pc-t2 ×3): **16 de 16 Ctrl+S al
Bloc de notas de Windows 11 no hicieron nada**. En la VM, con el Bloc de notas clásico, el mismo recibo abrió «Save
As» (1 de 1).

**Causa.** `src/Baxy.Providers.Windows/External/DesktopKeyboard.cs`, `PressChord`: los cuatro eventos del acorde (Ctrl
abajo, S abajo, S arriba, Ctrl arriba) iban en un solo `SendInput`. El editor del Bloc de notas de Windows 11 lee cada
tecla cuando llega a ella (medido el 2026-10-07 y anotado en `TypeText`: las teclas más rápidas de lo que las toma salen
mal y las teclas virtuales pierden su Mayúscula); cuando llegó a la S ya estaban todas arriba: ni atajo ni letra, que es
lo que se ve. Fuente externa coherente, que no prueba la causa: el Bloc de notas nuevo es WinUI y se reportan fallos de
SendInput que no pasan en otras aplicaciones (Stack Overflow, pregunta 76177119).

**Arreglo (2dc466867, proveedor).** El acorde se sostiene como lo hace una persona: cada tecla baja en orden con
el paso del teclado (35 ms, el mismo de `TypeText`) detrás, de modo que la última sigue abajo, con las anteriores,
cuando la ventana la lee; después suben todas en orden inverso. Como el acorde ya no es un único `SendInput` indivisible
(hallazgo del revisor de privacidad), cada tecla baja sólo si la ventana sigue al frente y la persona no actuó (la misma
comprobación que antes de cada carácter escrito); lo que bajó siempre sube (`finally`) y la cuenta dice que el acorde no
fue entero. Vale para todo acorde (también el Ctrl+N de «documento nuevo» y el Esc de app.open), sin nombrar ninguna
aplicación. Pruebas: `ComputerUseSpeedTests.AChordIsHeldTheKeyboardsPaceBeforeItIsReleased` y
`AChordStopsWhereTheWindowLostTheFrontAndReleasesWhatWentDown` (sin el cambio `HoldChord` no existe, así que la
demostración del fallo es el e2e).
**No está verificado en vivo**: los escritorios del PC y del NB corrían bancos. Cómo comprobarlo: con `ft-c3-app`
compilada, `bench_e2e.py <etiqueta> --cases ... --only E017` con un modelo que pulse Ctrl+S (base lo hace 3 de 3 en el
PC); la mirada siguiente al `ctrl_s` debe ser «Guardar como». Si sigue sin abrirse, la causa es otra (el frente
devuelto a los 40 ms de `SettleAsync`) y este cambio se revierte.

**Lo del modelo en E017.** Con el diálogo abierto por el menú, m1-sB s0..2, c3app-base-s0 y c3base-s0b pulsaron
«Guardar» sin escribir el nombre ni la carpeta (el campo decía «lista pilas, cables.txt» y la carpeta elegida era otra) y
dijeron «guardé … en …\BAXY-bench»: la mirada decía bien nombre y carpeta. La VM (prueba) falló porque el
Bloc de notas no quedó al frente (entorno de la VM, como en E012).

## E014 en la VM — «Settings» mandado a «Configuración» (App)

`mente\turns.jsonl` de `vmc3-base-s1`: el modelo decidió `app.open {"appId":"Settings","place":"sound"}`. En Windows en
inglés la Configuración es «Settings» en el catálogo Inicio (`vmc3-c2c1-sA-s1` la abrió con `{"appId":"Settings"}`:
`displayName` «Settings», proceso SystemSettings). El `step` lleva `"appId":"Configuración"`, `app_not_found` y un
`placeOwner` que dice «this call opened Configuración at sound». Causa: `app_places.v1.json` nombraba la aplicación sólo
«Configuración»; `ApplicationPlaces.PlacesOf("Settings")` salía vacío y `SaidApplication` (ayuda `place_owner`) cambió
el appId al único dueño de «sound», que ese Windows no lista.

Arreglo (00df7ffb1, datos, kernel y mente): los datos declaran los otros nombres del catálogo Inicio de la misma
aplicación en los idiomas de BAXY (`"names": ["Settings"]`); el kernel los registra con la misma entrada (un nombre en
blanco o ya de otra aplicación rechaza los datos enteros), `SameApplication` los reconoce y la mente los usa para
`places_note`. El texto de las herramientas no cambia (sigue nombrando «Configuración»: el prefijo entrenado queda
igual). Pruebas: `ApplicationPlacesTests.TheOtherStartNameOfAnApplicationHasItsPlaces` y `AnOtherNameBlankOrTakenIsRefused`
(3 rojas antes), `SaidApplicationTests.OtherwiseTheCallRunsAsItIs("…","Settings","sound")` (roja con los datos sin el
alias, verde con él) y `test_mind_aids.py::test_the_other_start_name_of_an_application_has_its_places` (roja contra el
árbol de HEAD).

Anotado sin tocar: la nota de `SaidApplication` dice «this call opened X at place» antes de que la llamada corra, así
que si la apertura falla el resultado dice a la vez `failed` y «opened». Y la página Sonido sólo declara lo que muestra
en español (`shows`), así que en inglés una mirada no dice si llegó.

## E010 — los candidatos de app.open sin la Calculadora (proveedor)

PC c2c1-sA s1: `app.open {"appId":"calc.exe"}` → `app_not_found` con `candidates` Access, Calendar, CapCut, Claude,
CODEX; el modelo respondió «No hay una calculadora…». Que «calc.exe» no abra nada es la regla (auditoría D1: el
ejecutable de un programa no es un nombre), pero la lista de los más cercanos es el dato con el que el modelo nombra uno
exacto, y no traía la Calculadora instalada: `InstalledApplicationResolver.Resolve` ordenaba por distancia de edición y
«.exe» la alejaba. Arreglo (3db37d8a7, proveedor): entre los más cercanos van primero los nombres con una
palabra que empieza por el comienzo de una palabra pedida (sus letras y cifras hasta el primer signo, desde 3); sigue
sin abrirse nada por eso. Prueba: `WindowsInstalledApplicationOpenProviderTests.AClosestNameThatBeginsWithWhatWasAskedComesFirst`.

Del modelo: c3app-base-s1 y PC rpo3 s1 dejaron 84 en pantalla y después cerraron la Calculadora sin que nadie lo
pidiera (`app.close`, con su sí); el oráculo no la encontró. Entorno: las 4 de la VM son `setup_fallido`.

## E012 — anotado

- VM (4): en 2, `input.text.type` → `input_window_not_in_front` y `window.focus` → `action_failed` (la sesión de la VM
  no da el frente); en 2 el texto se escribió y se leyó de vuelta (`em_replacesel`, `readback`) y el oráculo dijo
  `NO-DOCUMENT` (`Get-NotepadText` lee el estado de pestañas del Bloc de notas de Windows 11, que el clásico no tiene).
  Entorno y oráculo de la VM.
- PC c2c05 s2: recién abierto el Bloc de notas, `input.text.type` fue por teclado (`method keyboard`, `readBack false`,
  `delivered_only`) y el documento quedó «desde BAXY»: se perdió «hola ». El recibo fue honesto y el modelo dijo «no
  pude leer si quedó escrito». Es del proveedor (el editor recién abierto aún no tomaba teclas y no había campo marcado
  para leer de vuelta), pero con 1 de 16 y sin la ventana de ese momento no se puede probar un arreglo.

## E021 — del modelo

En las 11, tras el sí, `shell.command.run` volvió `completed` con `stdout "Python 3.10.11\n"` y `exitCode 0`; el modelo
llamó otra vez al mismo comando, eso pidió otro sí y el turno terminó preguntando «¿Ejecuto python --version…?». En las
que pasan, con el mismo resultado, respondió «Python 3.10.11». El dato estaba. La verificación `delivered_only` es la
regla de `OperationVisibleFacts` para una consola: dice que no se leyó su efecto, no su salida.

## Banco de decisión (feria y decision2)

Miden sólo la primera decisión; la traza tiene un `turn.decide` por caso y ningún resultado de herramienta (sólo el
historial escrito del caso), así que ningún fallo es de la App ni del proveedor. Fallan en todas las corridas: feria
FER003, FER004, FER006 y FER022 (114 de 114; la base c2e1 además FER030, 6 de 6) y decision2 P026, P031, P061, P093,
P118, P181, P187, P220, P251, P252 y P253 (18 de 18). Son del modelo o de la expectativa del caso (P220 espera el clic
sin mirar antes; P251, `window.maximize` sin `window.resolve`; FER003, la expresión con la Calculadora recién abierta en
el historial, y el modelo la vuelve a abrir). Un único error de ejecución: rpo2-sA feria s0, FER003, `TimeoutError` del
servidor del modelo.

## Familias de datos propuestas (lo del modelo)

| Familia | Casos | Qué enseña |
|---|---|---|
| salida de consola | E021 | `shell_command_run` completado con stdout: responder con la salida, sin repetir la llamada |
| sólo la tarea nombrada | E023 | completar la tarea que dijo la persona; la lista de después es información, no encargo |
| guardar como | E017 | en «Guardar como», escribir nombre y carpeta antes de «Guardar»; decir sólo la carpeta que la mirada muestra |
| no cerrar sin pedido | E010 | lo abierto para la persona se deja abierto |
| leer el orden dado | E020 | `file_find` con `order size`: el primero es el mayor; mirar una subcarpeta no invalida lo leído |
| texto literal | E006 | el texto de un archivo es el que dijo la persona, sin reformatear |
| hora del contexto | E009 | la hora local del contexto se dice tal cual |
| configuración de sonido | E014 (m1-sB) | «configuración de sonido» es Configuración en sound, no la consola del fabricante |
| negativa | E029 | (ninguna: «No pido comida» es correcta; el oráculo debería aceptar «no pido») |

## Decisiones que no se tomaron (para el dueño o la sesión líder)

- `app.close` de la Calculadora pidió el sí (E010, `unsavedChanges not_readable`). La identidad dice que cerrar va
  directo «cuando no se pierde nada»; si no poder leerlo cuenta como «se perdería algo» es una decisión de producto.
- El oráculo de E029 y los de la VM (E012 `Get-NotepadText`, `setup_fallido` de la Calculadora) son del banco, no del
  producto.

## Verificación (PC, 2026-10-29, prioridad baja)

| Peldaño | Comando | Resultado |
|---|---|---|
| 1 | `dotnet test tests/Baxy.Kernel.Tests -c Release --nologo -v:minimal` | 991 pass, 0 fallos (antes del arreglo: 3 rojas en `ApplicationPlacesTests`) |
| 1 | `dotnet test tests/Baxy.App.Tests -c Release --nologo -v:minimal` | 467 pass, 0 fallos (sin el alias: 1 roja en `SaidApplicationTests`) |
| 1 | `dotnet test tests/Baxy.Providers.Windows.Tests -c Release --nologo -v:minimal` | 3509 pass, 0 fallos (sin el cambio de candidatos: 1 roja, «But was: Access») |
| 1 | pytest con el Python del runtime: `test_mind_aids.py test_mind_maximo.py test_mind_w8_audit.py test_mind_bucle.py -q` | 184 pass (la prueba nueva, roja contra el árbol de HEAD) |
| 2 | `ruff check src/baxy_mind/mind.py tests/test_mind_aids.py` (ruff 0.15.12 del sistema) | sin hallazgos |
| 2 | `dotnet build Baxy.slnx -c Release --nologo -v:minimal -m:4` | 0 advertencias, 0 errores |

No se corrió el peldaño 3 entero ni ningún banco en vivo (los escritorios del PC y del NB corrían bancos). El arreglo de
Ctrl+S (2dc466867) es el único sin evidencia en vivo y es el primero que conviene medir: E017 con base en el PC. Revisión
del diff de proveedores por el agente `revisor-privacidad`: su hallazgo medio (un acorde ya no indivisible podía caer en
la ventana de la persona) y el bajo (teclas abajo sin `finally`) están arreglados en el mismo commit. La rama no está
subida a `hub`.

# Tercera vuelta: fallos del motor genérico de pantalla vistos al grabar F09 (2026-10-30)

Encargo: los fallos del motor de computer use que el ayudante de la familia F09 (mirar → pulsar → escribir →
comprobar) vio en vivo en el NB (`F:\BAXYeval\ft_v1\c3\familias\F09\informe.md`, «Fallos del motor vistos en vivo»,
M1–M7; capturas en `familias\F09\vivo\tanda_*.jsonl`). Cada arreglo es general (por tipo de control y estructura del
árbol, ninguna app nombrada en código) y su prueba se vio roja antes del cambio.

## Resumen

| # | Fallo | De quién | Arreglo | Estado |
|---|---|---|---|---|
| M1 | La búsqueda en un paso (`input.visible.click` con `search`) no termina en WhatsApp ni Discord | Proveedor (relectura del texto) | 34fdaced0 + 15b1e278f | arreglado, sin vivo |
| M2 | `input.text.type` en el buscador de la Microsoft Store → `input_text_not_read_back` con el texto puesto | Proveedor (misma causa) | 34fdaced0 + 15b1e278f | arreglado, sin vivo |
| M3 | El postread niega clics que actuaron: «Iniciar» del cronómetro (`postread_unread`), color de Paint (`postread_unchanged`) | Worker UIA (postread) | 68a001e21 + fcf96b814 + e5e4923fa (pruebas) | arreglado, sin vivo |
| M5 | Un control repetido (×N) tiene un solo índice | Worker UIA (vista) | dfc844072 | arreglado, sin vivo |
| M6 | `client.channel.locate` sin coincidencia deja abierto el buscador rápido de Discord | Proveedor (guion del cliente) | 840853a74 + 3e48e4bf7 | arreglado, sin vivo |
| M4 | Epic sólo por OCR: las líneas no llevan índice; dos «...» no se distinguen | Contrato de la vista | — | sólo diagnóstico |
| M7 | Desinstalar en Epic pide dos «sí» | Decisión de producto | — | sólo descrito (no se toca) |

## M1 y M2 — el texto escrito por teclado en un campo de Chromium o de una app empaquetada no se releía

**Qué se vio.** WhatsApp (`tanda_b3` whatsapp3#3): la ráfaga pulsó el Edit «Buscar un chat o iniciar uno nuevo»
(`method: target`, `focused: true`), escribió «zzqxprueba» y el subacto `input.text.type` dio
`input_text_not_read_back`; la ráfaga se paró ahí, antes de buscar el resultado. La mirada siguiente (#5) leía el campo
enfocado con `value: "zzqxprueba"`. Discord (discord3#3): igual, con el ComboBox del buscador rápido. Microsoft Store
(`tanda_a` store#4): `input.text.type` sin `window` → `input_text_not_read_back`, `foregroundProcessIdBefore` 13200 (el
marco de ApplicationFrameHost) con `sentTo.process` WinStore.App; la mirada #7 leía `Edit «Buscar» = editor de fotos`.

**Causa.** `WindowsDesktopInteractionAdapter.SendInBurstAsync` sólo sabía releer un texto de dos formas: la marca de un
control Edit de Win32 (no existe en Chromium ni en XAML) y el párrafo del cursor por TextPattern (`textcaret`), que se
limita al proceso de la ventana de delante. En la Store el campo es de otro proceso que su marco: no hay lectura y, sin
ventana nombrada, el texto queda «no releído». En los campos de Chromium el párrafo del cursor no creció con lo escrito
(en vivo no se pudo aislar si por el texto de ayuda del campo o por el ancestro con TextPattern; las dos dejan la misma
huella). La mirada, en cambio, lee el ValuePattern del control con el foco dentro del árbol de la ventana, y ahí el
texto estaba. En la ráfaga de búsqueda un subacto no verificado corta la ráfaga (`SearchBurst.RunAsync`, paso 3): de
ahí que M1 no llegara nunca a elegir el resultado.

**Arreglo (34fdaced0, revisado en 15b1e278f).** Comando nuevo del worker `focusvalue` (`Do-FocusValue`): el valor
(ValuePattern) del Edit o ComboBox que tiene el foco, sólo si está dentro del árbol de la ventana pedida (por
ascendencia, no por proceso), nunca una contraseña, acotado a 8192 caracteres y con su identidad (RuntimeId). El
adaptador lo lee antes de la primera tecla y otra vez después (hasta 3 lecturas, como el párrafo), y el texto cuenta
como releído si el valor del mismo campo creció en el texto y lo contiene una vez más (`CaretHolds`, la misma regla que
el párrafo). Sólo donde no hay valor entero de un campo se sigue usando el párrafo del cursor (Word sigue igual). El
valor no sale del adaptador: el recibo dice `readBack`, `readBackBounded` y `authority:
win32_sendinput_and_uia_value_reread`. Con una ventana nombrada, el texto queda obligado a esa relectura cuando se pudo
tomar (antes, sin marca ni párrafo, se daba por bueno por la cuenta de teclas de Windows).

**Pruebas.** `TextDeliveryTests.ATextTypedIntoADrawnFieldIsReadBackByTheFocusedFieldsValue` (Store sin ventana; campo de
Chromium con ventana nombrada y un párrafo que no crece), `ATextTheFocusedFieldsValueDoesNotHoldIsNotVerified` (nada
escrito, ya estaba, reescrito, cortado, el foco pasó a otro campo, el worker se niega) y
`TheWorkersFocusedValueReadStaysInTheWindowAndReadsOnlyAFieldsValue`. Contra el adaptador y el worker de 086ebfde3 (NB,
corrida «roja»): las dos de la primera y tres de la segunda en rojo (`input_text_not_read_back`, `authority
win32_sendinput_return_count`, se pedía el párrafo del cursor) y la del worker en rojo (no existe `Do-FocusValue`).

**Lo que no se pudo verificar en vivo.** La cola e2e del NB seguía corriendo (`cola_nb_c2cr2.fin` no existía) y el PC
está reservado: ni WhatsApp, ni Discord, ni la Store se abrieron. Queda por ver: (1) que el ValuePattern del campo de
Chromium ya tiene el texto cuando el adaptador lo relee (la mirada del F09 lo confirma después, no dentro de la
ráfaga); (2) que la ráfaga, con la relectura ya buena, llega a elegir el resultado antes de su techo de 2 s
(`SearchBurst.CapMs`): en WhatsApp la ráfaga fallida ya iba en 1985 ms; ahora el párrafo del cursor no se lee cuando hay
valor, lo que ahorra lecturas, pero si el techo corta antes de que la lista muestre el resultado el recibo dirá
`visible_search_result_not_found` con lo visto. Cómo comprobarlo: con la cola terminada, el driver del F09
(`grabador/grabar_cu.py`) con «zzqxprueba» en los dos buscadores (debe dar `visible_search_result_not_found`, ya no
`input_text_not_read_back`) y el buscador de la Store con «editor de fotos» (debe dar `completed` con
`win32_sendinput_and_uia_value_reread`).

## M3 — el postread negaba clics que sí actuaron

**Qué se vio.** Reloj (`tanda_a2` reloj2#4): clic en «Iniciar» (índice 13) → `visible_click_postread_unread`; la mirada
#6 tenía en el mismo índice `Button «Pausa»` y el grupo «Cronómetro, En marcha». Paint (paint2#6): clic en
`ListItem «Rojo oscuro»` de la paleta abierta → `visible_button_postread_unchanged`; la mirada #7 tenía
`RadioButton «Color 1: Rojo oscuro» (selected)` donde antes estaba «Color 1: Negro».

**Causa.** `Do-Postread` del worker sólo acepta como efecto que el control desaparezca o se deshabilite, que quede
seleccionado o conmutado (él o su línea del mismo nombre), que un campo tome el foco o cambie de valor, o que se abra un
diálogo modal; si no, el adaptador mira la imagen de la ventana. Un botón que cambia de nombre al pulsarse
(Iniciar → Pausa) y un elegido de la ventana que pasa a nombrar lo pulsado no eran prueba, y la imagen de esas ventanas
no se leyó (Reloj: `unread`) o no se vio cambiar en su plazo (Paint: `unchanged`).

**Arreglo (68a001e21, revisado en fcf96b814).** Antes de pulsar, el worker lee el nombre actual del control y el de los
controles que la última vista de esa ventana leyó elegidos (`selected`/`on`, a lo sumo 24; la vista guarda sus
identidades). El postread acepta dos pruebas nuevas, cada una con su clave (`PostreadHolds`): `renamed` (el mismo
control tiene otro nombre; `renamedTo` dice cuál) y `chosenNamed` (un elegido que antes no nombraba lo pulsado ahora sí,
como palabra entera; `chosenNow` dice cómo se llama). Tras la revisión de privacidad, el renombre sólo cuenta si el
nombre de antes del clic es el mismo que leyó la última mirada (uno que cambia solo, un contador, no prueba nada), y el
nombre pulsado que busca en el elegido debe tener al menos dos caracteres.

**Pruebas.** `ComputerUseListenedPressTests.AControlRenamedByItsPressOrAChosenOneThatNamesItNowHoldsTheClick` (corre el
`Do-Postread` real por su árbol sintáctico: Iniciar → Pausa, Color 1 → Rojo oscuro y cinco contracasos, más
`Test-NameSteady`) y `ComputerUseClickMethodTests.AControlRenamedByThePressOrAChosenOneNamingItHolds`. Rojas contra
086ebfde3 (los dos primeros casos dan `visible_button_postread_unchanged`; `PostreadHolds` no conocía las claves).

**Sin vivo.** Cómo comprobarlo: Reloj → Cronómetro → clic en «Iniciar» por índice (debe dar `completed` con
`renamedTo: Pausa`) y luego «Pausa»; Paint → «Colores» con `manner: open` → un color (debe dar `chosenNow: Color 1: …`).
Cerrar Reloj y Paint por PID.

## M5 — un control repetido tenía un solo índice

**Qué se vio.** Reloj, pestaña Temporizador (reloj2#13): `Button «Iniciar»` con `repeated: 2` (×3 en la proyección),
uno por temporizador, y lo mismo «Expandir» y «Mantener visible»: sólo la primera copia tenía índice e identidad.

**Causa.** `Do-View` junta en una entrada todo lo que tiene el mismo tipo, nombre y estado elegido (`Get-SeenKey`) y
cuenta las copias; sólo la primera queda en la vista y en el mapa de identidades.

**Arreglo (dfc844072).** Una copia que se puede pulsar (tipo de `$Actionable`), con identidad propia y cuyo centro no
cae dentro de una copia ya listada (ni al revés) lleva su propia entrada, con su índice y su zona. Siguen juntas (×N)
las copias de lo que no actúa (Text), las que no tienen identidad y la que está dibujada dentro de otra (el mismo
control dicho dos veces). Consecuencia: un clic sólo por etiqueta sobre un nombre repetido ya no pulsa la primera copia
en silencio (`NamedInView` exige un único control de ese nombre): el modelo tiene que dar el índice.

**Prueba.** `ComputerUseViewOrderTests.ACopyOfAnActionableControlElsewhereGetsItsOwnEntry`: corre el recorrido real de
`Do-View` sobre controles descritos. Roja contra 086ebfde3 (`Button|Iniciar|1.1|3` en una sola entrada).

**Sin vivo, y un aviso para los datos.** Las muestras del F09 que muestran «Iniciar ×3» describen la vista de antes; con
este cambio esa vista tiene tres líneas `[i] Button «Iniciar» (zona)`. Revisión de privacidad: en listas con una acción
destructiva por fila («Eliminar» ×N) el modelo elige ahora por índice y zona, sin el nombre de la fila; la confirmación
del kernel sigue reteniendo lo destructivo. Una lista con muchas copias consume el tope de la vista (60).

## M6 — el buscador rápido de Discord quedaba abierto sin coincidencia

**Qué se vio.** `tanda_b2` discord2#3: `client.channel.locate {name: zzqxprueba}` → `found: false`,
`switcherNotClosed: true`; la mirada #4 tenía el foco en un `Window` (el diálogo del buscador), no en su campo.

**Causa.** El guion (`WindowsDeviceControlAdapter.ClientChannelLocateScript`) cierra el buscador con Escape sólo si
`Dialog-Of` del foco devuelve un diálogo, y `Dialog-Of` empezaba a subir desde el padre del elemento: con el foco en el
diálogo mismo no encontraba ninguno, no se mandaba Escape y el recibo decía, con razón, `switcherNotClosed`. Es la única
lectura compatible con la evidencia (con el Escape mandado desde el campo el buscador se habría cerrado, y con el foco
ya en el diálogo la relectura de después habría dado `leftOpen` falso); no se pudo reproducir en vivo.

**Arreglo (840853a74, revisado en 3e48e4bf7).** `Dialog-Of` empieza en el propio elemento. Tras la revisión de
privacidad, el Escape sólo va al diálogo que tiene el nombre escrito (`Field-Shows $label`), nunca a otro diálogo de
Discord (una llamada, una confirmación) que tome el foco.

**Prueba.** `R24ClienteEnFrioListoPorInteraccionTests.TheSwitchersDialogHoldingTheFocusItselfIsTheDialogTheEscapeCloses`:
el `Dialog-Of` real del guion sobre elementos descritos. El mismo cuerpo contra el `Dialog-Of` de 086ebfde3 falla (sube
desde el padre del diálogo; medido en PowerShell, sin la App). En la corrida «roja» del NB esta prueba pasó porque ahí
sólo se volvieron atrás los ficheros de M1–M3 y M5.

**Sin vivo.** Cómo comprobarlo: con Discord abierto y la cola terminada, `client.channel.locate` con un nombre sin
coincidencia; el recibo no debe llevar `switcherNotClosed` y la mirada siguiente no debe tener el foco en el diálogo.

## M4 — Epic leído sólo por OCR (diagnóstico)

`tanda_a3` epic3#2: 0 controles UIA (`toolkit: unreal`); todo llega como `text` por zonas (`windows_media_ocr_lines`),
sin índice ni posición. Un clic por etiqueta va a `WindowsVisibleOcrLocator`, que busca la línea; con dos líneas
iguales («...» de dos juegos) de la misma altura no devuelve ninguna y no se pulsa nada (lo honesto: no adivina). Para
poder elegir hay que dar a cada rótulo OCR un índice (o su posición) en la vista y aceptar `index` sobre esas marcas en
el clic: es un cambio del contrato de la vista y de la proyección que lee el modelo, y en el NB no hay una cuenta con
dos juegos instalados para medirlo. No se tocó. Recomendación: decidirlo junto con una prueba en vivo con un juego
gratis instalado antes de entrenar más Epic.

## M7 — la doble confirmación al desinstalar en Epic (descrita, no cambiada)

En `tanda_a` epic#11 el primer clic en «Desinstalar» del menú «...» quedó `pending / confirmation_required`; el
«Desinstalar» del diálogo propio de Epic es otra invocación con verbo destructivo y RiskPolicy la retiene otra vez, así
que la persona dice «sí» dos veces. Es la regla del invariante 4 (la confirmación se liga a la invocación exacta): cada
clic destructivo confirma el suyo. Las dos salidas son de producto: dejarlo (las muestras del F09 lo modelan, con la
segunda pregunta nombrando el diálogo de Epic) o que la confirmación del primero cubra el diálogo que ese mismo clic
abre, lo que exigiría ligar la confirmación a una cadena de dos invocaciones. Queda para el líder o el dueño.

## Verificación (NB, prioridad baja, `-m:2`)

Todo en `D:\BAXYeval\wt\ft-c3-app` (rama ft-c3-app-nb avanzada a hub/ft-c3-app), con `start /belownormal`; guiones
`D:\BAXYeval\ft_v1\c3\F09\f09_rojo.cmd` y `f09_verde.cmd`, salidas `arreglos_rojo.log` y `arreglos_verde.log` al lado.
En el PC (reservado) sólo se editó, se hizo git y se corrieron los cuerpos PowerShell de las pruebas de M3, M5 y M6
sobre el worker y el guion (nuevo y de 086ebfde3), sin build ni la App.

| Peldaño | Comando | Resultado |
|---|---|---|
| rojo | `dotnet test tests\Baxy.Providers.Windows.Tests -c Release -m:2 --filter <las 7 pruebas nuevas>` con el adaptador, `WindowsTextDelivery`, `WindowsVisibleControlAdapter` y el worker de 086ebfde3 | 9 rojas, 5 verdes (las verdes: contracasos «cortado» y «se niega», y M6, cuyo fichero no se volvió atrás) |
| 2 | `dotnet build Baxy.slnx -c Release --nologo -v:minimal -m:2` (TreatWarningsAsErrors en Directory.Build.props), cabeza e5e4923fa | 0 advertencias, 0 errores |
| 1 | `dotnet test tests\Baxy.Providers.Windows.Tests -c Release --no-build` | 3499 pass, 0 fallos (en 840853a74 fallaron 2 pruebas viejas del postread que cargaban `Do-Postread` sin sus funciones nuevas: arregladas en e5e4923fa) |
| 1 | `dotnet test tests\Baxy.App.Tests -c Release --no-build` | 467 pass, 0 fallos |
| 1 | `dotnet test tests\Baxy.Kernel.Tests -c Release --no-build` | 991 pass, 0 fallos |

No se corrió el peldaño 3 entero (la rama no tiene `scripts/test_source_quality.ps1`; no hay cambios de Python ni de la
interfaz) ni ninguna prueba en vivo: `D:\BAXYeval\ft_v1\c3\cola_nb_c2cr2.fin` no existía al terminar (la cola e2e
del NB seguía) y el PC está reservado hasta las 10:00. Ninguno de los cinco arreglos tiene evidencia en vivo; cada
sección dice cómo comprobarlo. Revisión del diff por el agente `revisor-privacidad`: sin hallazgos altos; los medios y
bajos se arreglaron en 15b1e278f (el valor releído es del mismo campo), fcf96b814 (renombre sólo con el nombre estable
desde la mirada; elegido por palabra entera y de dos caracteres al menos) y 3e48e4bf7 (Escape sólo al diálogo con el
nombre escrito); el de las copias destructivas por índice queda anotado en M5. Push a `hub` tras el chequeo de
privacidad del PC (`privacidad.py` sin avisos; un primer aviso por un nombre de clase de ventana en una prueba se
arregló antes de subir).

## M1b — la búsqueda en un paso no elegía un resultado nombrado con más cosas (2026-10-30)

**Causa.** Con el texto ya releído (M1), `SearchBurst.ResultNaming` exigía que el nombre del resultado fuera
exactamente lo buscado; las filas de los buscadores de chat dicen más («Martina, 13:42, …», «Martina, Mensaje
directo»), así que la ráfaga miraba hasta el techo y acababa en `visible_search_result_not_found` con `seen`.

**Arreglo (cd07a749d + 9e9b65f51).** El exacto sigue primero y en la primera mirada. Si no hay exacto, vale un
resultado cuyo nombre (plegado: mayúsculas, acentos, espacios) empieza por lo buscado como unidad y sigue con coma,
dos puntos, salto de línea o guion con espacio; no vale «Martina Soto», «Martinez», «Cotele-memes» ni una pestaña
(se nombra por su página). Entre los que valen, los que la búsqueda listó tras el texto van antes que una fila que la
ventana ya mostraba. La decisión por prefijo espera a que dos miradas seguidas listen los mismos nombres (una lista
que se llena puede traer el exacto). Un nombre distinto → se pulsa (y si llega a una persona sigue pidiendo
confirmación, `visible_search_result_needs_confirmation`); varios distintos → no se pulsa nada y el recibo es
`visible_search_result_ambiguous` con `candidates` (máx. 20; `candidateCount` y `truncated` si hay más), sin
`seen`, `effectMayHaveOccurred` (el buscador quedó abierto con el texto). `choose` sigue la misma regla, así que el
nombre de un candidato copiado tal cual lo elige. Techo (2 s) igual.

**Prueba.** `SearchBurstTests`: 8 rojas antes del cambio en el NB (`m1_rojo.log`: 5 casos de la teoría, las dos filas
de chat y la ambigüedad), verdes después junto con los contracasos («Mar», «Cotele-memes», «Martina Soto», la fila de
la barra lateral, la lista que se llena, el canal de voz que pide confirmación, el exacto y `choose` ante candidatos).

**Verificación (NB, `start /belownormal`, `-m:2`, cabeza 9e9b65f51, `m1_verde.log`).** Build Release de `Baxy.slnx`
con warnings como errores: 0 advertencias. Providers.Windows 3516/3516, App 467/467, Kernel 991/991. En la corrida
anterior (cd07a749d) falló una vez `ConfirmationAuthorityTokenTests.Only_the_exact_token_grants_not_a_truncated_or_altered_one`
(ajena: cambia el último carácter base64url de 'A' a 'B', que sólo toca bits de relleno y decodifica igual); sin vivo.

**Riesgos que quedan.** Un grupo cuyo nombre empieza por el de la persona («Martina, Pedro y Juan») es una fila que
vale si es la única; el recibo nombra la fila elegida. Si cada fila expone además un hijo con el nombre exacto, el
exacto gana sin ambigüedad (comportamiento de antes). La descripción de `search` en `tool_descriptions.en.v1.json`
sigue diciendo «named exactly»: no se tocó (es entrada del modelo y de los datos del ajuste); decide el líder.

# Prueba en vivo en el PC (30-10)

REDPC, 08:24–08:58, con el escritorio cedido por el dueño. Motor real sin modelo: `baxy-core.exe` de este worktree
(Release, warnings como errores: 0 y 0) con su perfil de datos aparte (`%LOCALAPPDATA%\BAXY\c3-vivo-pc`), movido por
`F:\BAXYeval\ft_v1\c3\app_vivo\vivo_cu.py`. Es el grabador del F09 con tres pasos más: imagen de la ventana de delante,
nunca de un chat; ventana por título; n-ésima copia. Planes, recibos (`tanda_*\grabacion.jsonl`) e imágenes en
`F:\BAXYeval\ft_v1\c3\app_vivo\`. En WhatsApp y Discord cada nombre que no es de la interfaz y cada texto leído se
taparon antes de guardarse en el registro. No se abrió ningún chat ni se escribió a nadie. Lo único tecleado allí fue «zzqxprueba».

| Arreglo | ¿Visto en vivo? | Recibo obtenido | Evidencia |
|---|---|---|---|
| M3 Reloj (renombre) | sí | «Iniciar» del cronómetro → `completed`, `renamedTo: Pausa`. «Pausa» → `completed`, `renamedTo: Iniciar` | `tanda_a`, pasos 7 y 11; `reloj_9_crono_iniciado.png` (corre a 00:01:59) |
| M3 Paint (elegido) | sí | «Colores» abierta y «Rojo oscuro» → `completed`, `chosenNow: Color 1: Rojo oscuro` | `tanda_a`, paso paint 7; `paint_10_color_elegido.png` |
| M2 Microsoft Store | sí | `input.text.type` «editor de fotos», sin ventana → `completed`, `readBack: true`, `authority: win32_sendinput_and_uia_value_reread` | `tanda_a`, paso store 4; `store_6_buscador_escrito.png` |
| M5 copias con índice propio | sí | Temporizador: 4 `Button «Iniciar»` con índices 11, 14, 17 y 20, uno por temporizador. El clic en el 14 → `completed`, `renamedTo: Temporizador activado, Pausa`, y arrancó el segundo (3 min) | `tanda_a`, pasos 18–23; `reloj_22_temp_segundo_iniciado.png` |
| M1 WhatsApp | sí | Ráfaga `search: zzqxprueba` → `visible_search_result_not_found`, ya no `input_text_not_read_back`. El subacto de escribir quedó `ok` | `tanda_b`, paso whatsapp 3 |
| M1 Discord | sí, tras M6b | Antes de M6b: `visible_button_postread_unchanged`, porque el buscador seguía abierto por `locate`. Después: ráfaga → escribe en «Cambio Rápido» → `visible_search_result_not_found` | `tanda_b`, paso 6; `tanda_b2`, paso 6 |
| M6 Discord, buscador cerrado | **no; arreglado aquí (M6b)** | Con c8b75b1b5: `found: false`, `switcherNotClosed: true`, y la mirada siguiente con el foco en el `Window` del buscador. Con M6b: buscador cerrado y foco en la vista de Discord | `tanda_b`, paso 3; `tanda_b2`, paso 5; `tanda_b3`, paso 2 |
| E017 Ctrl+S en el Bloc de notas | **no; causa nueva, sin arreglar** | `ctrl_s` → `delivered`, 4 de 4 eventos, Bloc de notas delante. El título sigue «*prueba_e017…» y el disco no cambia | `tanda_e017`; `e017_archivo\` |
| E010 candidatos de app.open | sí | `app.open calc.exe` → `app_not_found`, `candidates`: [Calculadora, Photometric Calc…, Access, …] | `tanda_e010_e011`, paso e010 0 |
| E011 Calculadora | sí | «(250+175)*2» → `calculator_needs_scientific_mode` con `mode: standard` y `next`. «250+175*2» → `completed`, `value: 850`, `La expresión es 425 × 2=` | `tanda_e010_e011`, pasos 2 y 3 |
| M1b elección por prefijo | no | — | Haría falta un chat real con un nombre que empiece por lo buscado. No se hizo (orden: no abrir chats reales) |
| E008 búsqueda web | no | — | La guarda `query_not_said` es de la App y compara con lo que dijo la persona. El core sin turno no la ejerce; hace falta el e2e con modelo |
| E014 Settings | no | — | Windows del PC en español, y la Configuración del dueño estaba abierta (abrirla en Sonido movía su ventana) |

## M6b — el primer Escape sólo vacía el buscador rápido de Discord (arreglado)

**Qué se vio.** Discord 1.0.9266. Con M6 (c8b75b1b5), `locate` sin coincidencia seguía diciendo `switcherNotClosed`.
Para trazarlo, el guion real se sacó del adaptador con trazas que sólo dan booleanos y tipos de control
(`diagnostico\extraer_locate.py`) y se corrió contra Discord:

- Antes del Escape: foco en un `ComboBox` dentro del diálogo, el campo con el nombre, Discord delante.
- Tras el Escape: el campo queda vacío y el foco sigue en el `ComboBox` del diálogo. A los 2,3 s seguía igual.
- Un segundo Escape: foco en el `Document` de Discord y fuera de todo diálogo. El buscador se cerró.

Con `input.key.press escape` de BAXY pasa lo mismo: el primero vacía el campo (`value ""`) y el segundo cierra
(`tanda_b2`, pasos 9–14). Así que `Dialog-Of` no era la única causa. En la vuelta siguiente el guion encontraba el foco
en un diálogo, se paraba (`client_dialog_after_shortcut`) y el buscador quedaba abierto. Por eso la ráfaga M1 de Discord
pulsaba un botón tapado.

**Arreglo (proveedor, `WindowsDeviceControlAdapter.ClientChannelLocateScript`).** El cierre pasa a `Close-Switcher`.
Lee una sola vez el diálogo donde está el foco y manda el primer Escape sólo si ese diálogo tiene el nombre escrito y
Discord está delante. Manda un segundo Escape sólo si se cumplen las tres cosas:

- el foco sigue en ese mismo diálogo (`Automation.Compare`);
- su campo quedó vacío;
- Discord sigue delante.

La lectura lenta del campo va primero, y el frente y la identidad se comprueban justo antes de la tecla.
`Field-Shows` acepta el diálogo que debe mirar. No nombra ninguna aplicación nueva: el guion ya es el de Discord.

**Prueba.** `R24ClienteEnFrioListoPorInteraccionTests.TheSwitcherEmptiedByTheFirstEscapeIsClosedByASecondOneInTheSameDialog`
corre el `Close-Switcher` real por su árbol sintáctico. Tiene 8 casos, y en cada contracaso decide una sola guarda:

- se vacía y cierra al segundo Escape;
- un Escape basta;
- el foco pasa a otro diálogo con el campo vacío;
- el campo sigue con el nombre;
- Discord pierde el frente con el campo vacío;
- el campo no tiene el nombre;
- el foco está desde el principio en otro diálogo vacío;
- Discord no está delante.

Roja contra c8b75b1b5 con los 6 primeros casos y la aserción ajustada de la prueba de M6: 7 de 7 rojas
(`Close-Switcher missing`; `app_vivo\m6b_rojo.log`). Los dos últimos casos se añadieron tras la revisión. Verde
después: R24 38 de 38. Revisión por el agente `revisor-privacidad`:

- medio: el diálogo comprobado y el que recibía el Escape se leían por separado;
- bajo: el orden de las comprobaciones;
- medio: la prueba no aislaba cada guarda.

Los tres están arreglados antes del commit.

**En vivo con el arreglo.** `tanda_b2` y `tanda_b3`: tras `locate` la mirada no tiene el buscador (sin `ComboBox`, foco
en la vista de Discord). Pero con «zzqxprueba» el recibo fue `client_quick_switcher_not_read` en las dos, tras ~45 s
(5 vueltas, cada una abre, escribe y cierra). Sin coincidencia, Discord no lista filas nuevas, y el guion dice «no leído»
en vez de «no existe» (regla de la ronda final 29). Queda para el líder, sin tocar:

- **(a) Los 45 s** de una búsqueda sin coincidencia.
- **(b) Un riesgo, no medido aparte.** En la primera corrida (`tanda_b`, paso 3) el recibo fue `found: false` con 15
  filas leídas tras escribir un nombre que no existe. Con un filtro aplicado no debería haber ninguna. Lo probable es que
  fueran las filas recientes que Discord pintó tarde: la regla «distintas de las de antes» las tomó porque antes no se
  leyó ninguna. Si es así, `found: false` puede salir con filas sin filtrar, es decir, un falso «no está» de un canal que
  existe pero no está entre los recientes.

## E017 — la causa es el atajo en español, no la forma del acorde (sin arreglar)

**Qué se vio.** Bloc de notas 11.2607.14.0 en español, sobre un archivo de prueba (`%TEMP%\baxy-e017\prueba_e017.txt`,
ahora en `app_vivo\e017_archivo\`):

- `input.key.press ctrl_s` con la ventana → `delivered`, 4 de 4 eventos, el Bloc de notas ya delante (no hubo frente
  que devolver). El documento siguió modificado y el disco igual.
- Con `diagnostico\acorde_variantes.ps1` desde otro proceso, ninguna forma de Ctrl+S guardó: sólo teclas virtuales
  sostenidas (dos veces), teclas virtuales con código de exploración, o sólo códigos de exploración.
- El foco estaba en el editor (`RichEditD2DPT`, `HasKeyboardFocus`) y una tecla Unicode sí entró
  (`diagnostico\foco_notepad.ps1`).
- «Guardar» del menú por UIA guardó, y su `AcceleratorKey` es **Ctrl+G**.
- **Ctrl+G guardó en las dos formas**: los cuatro eventos en un solo `SendInput`, como antes de 2dc466867, y sostenido.

El menú Archivo de este Bloc de notas declara estos atajos:

| Orden del menú | Atajo |
|---|---|
| Nueva pestaña | Ctrl+U |
| Abrir | Ctrl+A |
| Guardar | Ctrl+G |
| Guardar como | Ctrl+Mayúsculas+S |
| Guardar todo | Ctrl+Alt+S |
| Cerrar pestaña | Ctrl+W |

**Causa.** En el Bloc de notas en español, guardar es Ctrl+G y Ctrl+S no hace nada. Eso explica los 16 de 16 del PC y
del NB (Windows en español) y el «Save As» de la VM, que está en inglés. El acorde de un solo `SendInput` no era la
causa. 2dc466867 (`HoldChord`) no hace daño, pero su justificación es falsa.

**No se arregló.** No hay un arreglo general claro sin una decisión de producto. La descripción de `input_key_press`
enseña «Ctrl+S/Z/F/T/W», y el modelo pulsa Ctrl+S. Salidas posibles:

- **(1)** El proveedor lee el `AcceleratorKey` de los menús de la ventana. Hace falta decidir cómo sabe que `ctrl_s`
  quería decir «guardar» sin una tabla de nombres por idioma.
- **(2)** El modelo guarda por el menú «Archivo > Guardar» con clic: datos del ajuste y descripción.
- **(3)** Una operación de guardar del documento.

Además conviene decidir si se revierte 2dc466867, como decía su propia sección, o se deja y se corrige su comentario.
Ctrl+A abre «Abrir» en este Bloc de notas: un «selecciona todo» por tecla allí abre un diálogo.

## Otras cosas vistas

- WhatsApp: con el texto ya escrito, el campo de búsqueda se llama «WhatsApp». Un clic por ese nombre con su índice dio
  `visible_control_label_mismatch` (`tanda_limpiar_wa`). El campo se vació con Ctrl+A y Retroceso tras una mirada que lo
  mostraba con el foco (`tanda_limpiar_wa2`: valor `""`).
- Al empezar, el título de WhatsApp decía «(2) WhatsApp», y al terminar «(1) WhatsApp». Tenía un chat abierto por el
  dueño (redactor de mensajes presente). Puede que traerlo al frente marcara leído un mensaje de ese chat abierto, o que
  el dueño lo leyera en el teléfono. No se puede distinguir con lo registrado.
- Un clic en «Cronómetro» ya elegido da `failed` `visible_button_postread_unchanged` con `alreadySelected: true`. Es el
  contrato de antes, el mismo que grabó el F09.

## Estado del escritorio y verificación

| Comprobación | Resultado |
|---|---|
| Procesos abiertos por la prueba | Reloj, Paint, Store, el Bloc de notas y la Calculadora: cerrados por PID |
| Temporizador de 3 min que arrancó M5 | Pausado y reiniciado: los 4 «No iniciado» (`tanda_a_restaurar2`) |
| Reloj | Vuelve a abrir en Cronómetro |
| Bloc de notas | La pestaña de prueba se cerró por su menú tras guardar; `TabState` vuelve a sus 2 ficheros de antes |
| WhatsApp | Maximizado, buscador vacío |
| Discord | Minimizado en «Amigos» |
| Ventana de delante | Claude, como al empezar (`frente_ahora.ps1`: `front claude`) |
| GPU | 999 MiB usados |
| Build | `dotnet build Baxy.slnx -c Release -m:2` → 0 advertencias, 0 errores (`app_vivo\build_final.log`) |
| `Baxy.Providers.Windows.Tests` | 3547 de 3547 |
| `Baxy.App.Tests` | 467 de 467 |

Eventos 7040 de las últimas 3 horas: 2. Son el ida y vuelta de BITS de las 07:52 y 07:54, antes de la prueba (que empezó
a las 08:24). La comprobación del registro de msconfig no se corrió: la guarda del harness la deniega.

# Cuarta vuelta: el diálogo de archivos de Windows en cualquier app (E017, 30-10 y 31-10)

Orden del dueño: «tiene que funcionar», y no sólo en el Bloc de notas: cualquier app que abra el explorador de archivos
para guardar o abrir. Todo se probó en vivo en el NB (REDNOTE) con el motor real de este worktree y sin modelo
(`vivo_dlg.py`, derivado del grabador del PC; tarea interactiva `BAXY-c3-dialogo`). Evidencia en
`F:\BAXYeval\ft_v1\c3\app_vivo\dialogo\` (planes, `nb\tanda_*\grabacion.jsonl`, volcados Win32 y UIA del diálogo, logs
rojos y verdes). Carpetas de prueba: `D:\BAXYeval\dlg_prueba\{np,paint,chrome,word}`.

## Qué fallaba (antes)

| Dónde | Paso | Recibo | Qué pasó de verdad |
|---|---|---|---|
| PC e2e `c3pc-c3r9b_1-sB-s0` | «Guardar» con el nombre «lista.txt» | `completed` (el botón desapareció) | El diálogo estaba en su última carpeta; el archivo fue a esa carpeta y no a `BAXY-bench`. BAXY dijo «guardé lista.txt en …\BAXY-bench» |
| PC e2e `c3pc-c3r9b_1-sB-s1` | `Programacion` del panel de navegación con `manner: open` | `visible_press_raised` ×2 | El nodo era una hoja: `Expand` lanza antes de hacer nada; el recibo decía «efecto dudoso» |
| PC e2e `c3pc-c3r10_1-sA-s2` | «Guardar» en `(C:)` | `visible_click_postread_unread` | Archivo MISSING |
| NB `tanda_n2` (motor sin arreglo) | «Guardar» con un nombre inválido | `completed` con `dialogOpened` | Se abrió el aviso de error del diálogo encima; nada guardado |
| NB `tanda_n2` | `ctrl_s` al Bloc de notas | `completed`, sólo «entregado» | Nada cambió (Guardar es Ctrl+G en español) |
| NB `tanda_n3` (primer arreglo) | texto con el foco en el botón «Guardar» | `completed` por teclado | Sus letras fueron teclas de acceso: la «G» pulsó &Guardar |
| NB `tanda_p1` (Paint) | «Guardar» por etiqueta | `visible_button_ambiguous` | Nada pulsado |
| NB `tanda_c1` (Chrome) | mirada a Chrome con «Guardar como» abierto | vista de Chrome «tapada por Guardar como» | Chrome dibuja el diálogo desde otro de sus procesos; la mirada nunca lo leía |

## Causa

1. **El motor no sabía qué es un diálogo de archivos.** El clic en «Guardar» se juzgaba como cualquier botón: que
   desapareciera, o que la ventana dueña quedara deshabilitada (`dialogOpened`), contaba como hecho. Ni el aviso de error
   encima ni la carpeta donde fue el archivo entraban en el recibo.
2. **La vista no decía la carpeta.** La barra de dirección es el control 58 de 60 en el Bloc de notas; con el tope de 10 o
   15 del e2e no salía nunca, y la nota de `SaveField` (que buscaba «Nombre de archivo»/«File name» y
   «Dirección:»/«Address:» por texto) tampoco salía.
3. **`manner: open` en un nodo hoja** llamaba a `Expand`, que lanza en una hoja.
4. **Un atajo que la app no tiene no cambia nada y el recibo no lo decía.**
5. **Chrome** muestra el diálogo desde otro proceso y `ModalSurface` sólo sigue diálogos del mismo proceso.

No era UIPI ni integridad (el diálogo es del mismo usuario y nivel), ni un Invoke sobre un botón dividido: el
«Guardar» de todos los diálogos medidos es un `Button` Win32 con id 1 (IDOK), y su Invoke actúa.

## Arreglo (367031bd9, nada nombra una app ni un idioma)

- **`CommonFileDialog`** reconoce el diálogo por su estructura Win32, medida en vivo en el Bloc de notas, Paint y
  Chrome: ventana `#32770` con la vista de carpetas del shell (`SHELLDLL_DefView`) y los botones IDOK (1) e IDCANCEL (2).
  El campo de nombre es el único `Edit` dentro de un `ComboBox` fuera de la barra de dirección y del buscador (o `cmb13` y
  `edt1` en el diálogo de estilo explorador). La carpeta es la ruta que muestra la miga de la barra de dirección, desde su
  unidad o recurso compartido: la etiqueta («Dirección:», «Address:», la de cualquier idioma) no se lee.
- **El recibo de confirmar es lo que hizo el diálogo.** Tras un clic en IDOK (por su identidad UIA `42.<hwnd>`, o por su
  rótulo si se pulsó de otra forma) o un Enter con el diálogo delante (salvo con el foco en otro botón), se espera hasta
  3 s a que el diálogo termine y hasta 5 s a que el archivo aparezca:

  | Final | Recibo |
  |---|---|
  | Cerrado y el archivo está | `completed` con `fileDialog: {closed: true, path, exists: true}` (un nombre sin extensión encuentra el archivo con la extensión que puso el tipo) |
  | Cerrado sin archivo | `failed` `file_dialog_file_missing` |
  | Otra ventana del diálogo encima (error, «¿reemplazar?») | `failed` `file_dialog_answered_by_another_window` con `answeredBy` |
  | Sigue abierto | `failed` `file_dialog_still_open` con `folderNow` y `nameNow` |

  Un clic cuyo post-read se perdió (`visible_click_postread_unread`) y cuyo diálogo cerró con el archivo ahí queda
  `completed`. «Guardar» por rótulo ambiguo se repite por la identidad de IDOK.
- **La vista dice el diálogo.** La mirada lleva `window.fileDialog` (`folder` o `shown`, `name`, `path`, `accept` y los
  índices si los listó). La vista que lee el modelo lo dice en una línea tras el foco, con cualquier tope:
  `Diálogo de archivos de Windows: carpeta «D:\…»; su campo de nombre [11] tiene «Sin título», que daría D:\…\Sin
  título; una ruta entera escrita en ese campo (C:\…\nombre.ext) guarda o abre ahí sin recorrer carpetas; «Guardar»
  [16] lo confirma`. Sustituye a `SaveField` (borrado).
- El diálogo de archivos que una ventana posee se mira como su diálogo modal aunque lo dibuje otro proceso (Chrome).
- `manner: open` en un nodo hoja: `visible_control_cannot_open`, sin enviar nada.
- Un atajo (Ctrl o Alt con otra tecla) mira su ventana: título, si está habilitada, sus ventanas visibles y la de delante,
  hasta 1 s. Si nada cambió: `windowChanged: false` y un `next` que dice que puede no ser el atajo de esa app en su idioma
  y que los menús muestran los suyos (`[atajo …]`).
- Un texto para una ventana cuyo foco es un botón (clase `Button`) no se teclea: `input_focus_not_a_field`.

## Cambio del contrato que lee el modelo (los datos se regeneran después)

| Dónde | Antes | Ahora |
|---|---|---|
| Vista de un diálogo de archivos | Nota tras el `Edit` «Nombre de archivo», sólo si estaban listados el campo, «Guardar» y la dirección en español o inglés | Línea `Diálogo de archivos de Windows: carpeta «…»; su campo de nombre [i] tiene «…», que daría …; una ruta entera …; «Guardar» [j] lo confirma` tras `Foco:`, siempre que la ventana sea el diálogo (ayuda `save_dialog_next`) |
| Mirada a una app cuyo diálogo es de otro proceso (Chrome) | La ventana de la app, «tapada por Guardar como» | El diálogo, como diálogo modal |
| Recibo de confirmar el diálogo | `completed` con `absentOrDisabled` o `dialogOpened` | `completed` con `fileDialog`, o `failed` con `file_dialog_answered_by_another_window`, `file_dialog_still_open` o `file_dialog_file_missing` y su `next` |
| `input_visible_click` con `manner: open` en un nodo hoja | `visible_press_raised` (efecto dudoso) | `visible_control_cannot_open` (nada enviado) |
| `input_key_press` de un atajo | `completed` `delivered_only` | Igual, más `windowChanged` y, si es `false`, `next` (ayuda nueva `shortcut_unchanged_next`) |
| `input_text_type` con el foco en un botón | `completed` por teclado | `failed` `input_focus_not_a_field` antes de teclear |

**Atajos por idioma.** La vista ya daba el atajo que declara cada entrada de menú cuando el menú está abierto (Goal v3
B3: `[atajo Ctrl+G]` en «Guardar» del Bloc de notas en español). Con el menú cerrado no se puede leer sin abrirlo: las
entradas de la barra de menús de WinUI no existen en el árbol hasta entonces. Pero **`input_key_press` no tiene
`ctrl_g`**: su `key` es una lista cerrada del catálogo (`ProductCatalog`, `ctrl_s`, `ctrl_o`…). Aunque el modelo lea
`[atajo Ctrl+G]` no puede pulsarlo; su camino es el menú por clic. Ampliar la lista a `ctrl_<letra>` es un cambio del
catálogo con su riesgo (Ctrl+letra borra o envía en algunas apps) y queda para el líder.

## Visión

No hizo falta en ningún diálogo probado: el diálogo común tiene árbol UIA completo y además se lee por Win32. La visión
(Qwen en CPU) debería entrar sólo en selectores de archivos dibujados por la propia app sin árbol accesible: el de GTK
(GIMP, Inkscape), Java Swing o selectores web dentro de una app. Ahí `CommonFileDialog` no reconoce nada (no hay
`#32770` con `SHELLDLL_DefView`) y el recibo de confirmar es el de siempre; el respaldo sería escribir la ruta entera y
comprobar el archivo, no navegar por imagen. No se implementó: no hay ninguno instalado en el NB para medirlo.

## En vivo en el NB con el arreglo (31-10): app × diálogo

Motor real de 85722532b compilado en el NB (Release, 0 advertencias y 0 errores), sin modelo. Cada fila es un recibo
real; «archivo» es lo que el arnés vio en el disco después (`exists`). Resumen de todas las tandas en
`app_vivo\dialogo\resumen_tandas.txt`.

| App (cómo se abrió el diálogo) | Diálogo | Carpeta y nombre | Recibo | Archivo | ¿Funciona? |
|---|---|---|---|---|---|
| Bloc de notas (Archivo › Guardar como, por clic) | Guardar como | ruta entera en el nombre, «Guardar» | `completed`, `fileDialog {closed, path: D:\…\np\lista.txt, exists}` | sí | **sí** (`tanda_n6`) |
| Bloc de notas | Guardar como | sólo «lista2.txt» (carpeta del diálogo), Enter | `completed`, `path: D:\…\np\lista2.txt` | sí | **sí** |
| Bloc de notas (Archivo › Abrir) | Abrir | ruta entera, «Abrir» | `completed`, `exists` | (abrió lista.txt) | **sí** |
| Bloc de notas | Guardar como | carpeta que no existe | `failed` `file_dialog_answered_by_another_window` («La ruta no existe») | no | **sí, honesto** (`tanda_n5`) |
| Bloc de notas | Guardar como | nombre inválido «mal\|nombre» | `failed` `file_dialog_answered_by_another_window` | no | **sí, honesto** (`tanda_n3`) |
| Bloc de notas | — | `ctrl_s` (no es su atajo en español) | `completed` + `windowChanged: false` + `next` | — | **sí, honesto** |
| Paint (`ctrl_shift_s`, `windowChanged: true`) | Guardar como | ruta sin extensión, «Guardar» por rótulo (ambiguo → IDOK) | `completed`, `path: …\paint\dibujo.paint` | sí | **sí** (`tanda_p2`) |
| Paint (`ctrl_o`) | Abrir | archivo que no existe, Enter | `failed` `file_dialog_answered_by_another_window` | — | **sí, honesto** |
| Paint | Abrir | tras «Aceptar», ruta con `replace`, Enter | `completed`, `exists` | (abrió dibujo.paint) | **sí** |
| Chrome (`ctrl_s`; diálogo de otro proceso) | Guardar como | la mirada ve el diálogo modal; ruta entera, «Guardar» | `completed`, `exists` | sí | **sí** (`tanda_c2`; con Enter en `tanda_c1`) |
| Chrome (`ctrl_o`) | Abrir | carpeta mostrada «Dirección: <inicio>» (no es ruta: `shown`); ruta entera, «Abrir» | `completed`, `exists` | (abrió la copia) | **sí** |
| Edge (`ctrl_s`) | Guardar como | ruta entera, «Guardar» | `completed`, `exists` | sí | **sí** (`tanda_e2`) |
| Edge (`ctrl_o`) | Abrir | ruta entera, «Abrir» | `completed`, `exists` | (abrió la copia) | **sí**; en `tanda_e1`, con el archivo aún sin guardar: `file_dialog_answered_by_another_window`, honesto |
| Word (Pestaña Archivo › Guardar como › Examinar, por clic) | Guardar como | ruta sin extensión, «Guardar» | `completed`, `path: …\word\informe.rtf` | sí | **sí** (`tanda_w5`) |
| Word (Pestaña Archivo › Abrir › Examinar) | Abrir | ruta entera, Enter | `completed`, `exists` | (abrió base.rtf) | **sí** |
| VS Code | — | — | — | — | **no probado**: un editor es ventana protegida (contrato «Seguridad v2»): BAXY no actúa en él si la persona no lo nombra; su diálogo es el mismo IFileDialog |
| Excel, PowerPoint | — | — | — | — | **no probado**: arrancan en la pantalla de inicio, sin libro; su «Examinar» abre el mismo diálogo que Word |

Variantes cubiertas: el diálogo moderno (IFileDialog) de una app Win32 clásica (Paint), de una WinUI (Bloc de notas),
de Office (Examinar) y el de Chromium dibujado desde otro proceso (Chrome, Edge); Guardar como y Abrir; confirmar por
clic, por rótulo ambiguo y por Enter; carpeta del disco y lugar sin ruta («Inicio»). «Seleccionar carpeta» no se pudo
abrir sin una app que lo pida; su estructura es la misma (`#32770`, `SHELLDLL_DefView`, IDOK). El diálogo de estilo
explorador (`GetSaveFileName` con plantilla) no apareció en ninguna app instalada: lo cubre la prueba con su árbol
(`cmb13`/`edt1`), sin vivo.

**Incidente (`tanda_w1`).** Word arrancado con `/w` abrió un documento del dueño en vez de uno nuevo y el arnés escribió
«informe de prueba» en él. No se guardó: Word se cerró sin guardar (por PID; el NB se reinició después, no por esta
prueba) y la carpeta de autorrecuperación de Word no tiene nada posterior. Desde entonces el arnés exige la ventana
esperada antes de escribir (`require_fg`, `find_window` con `required`) y Word se probó sobre un `.rtf` de prueba.

**Visto de paso, sin tocar.** El clic en «Archivo» del Bloc de notas y en «Pestaña Archivo» de Word devuelve
`visible_click_postread_unread` aunque el menú se abra (el paso siguiente lo pulsa). `app.open notepad` justo después
del reinicio del NB dio `inventory_failed` una vez. Un campo de nombre de archivo tiene `ComboBox` y `Edit` con el mismo
nombre: un clic sólo por el rótulo «Nombre de archivo:» es `visible_button_ambiguous` (con el índice va bien).

## Estado del NB al terminar

Procesos abiertos por las pruebas cerrados por PID (Bloc de notas, Paint, Chrome y Edge con perfiles de prueba en
`D:\BAXYeval\dlg_prueba`, Word); ningún `baxy-core`, `WINWORD`, `mspaint` ni `Notepad` vivos. Tarea `BAXY-c3-dialogo`
quitada. Eventos 7040 de las últimas 3 horas: los ida y vuelta de BITS e IsolationSession de cada 10 minutos, que
empezaron antes de la prueba (21:55). El worktree NB `ft-c3-app-nb` está en 85722532b.

## Pruebas (rojo antes, verde después)

| Prueba | Rojo | Verde |
|---|---|---|
| `ScreenViewProjectionTests.AFileDialog…` (2, 6 casos) | 5 de 6 rojas (`rojo_vista.log`) | 30/30 de la clase |
| `CommonFileDialogTests` (estructura, carpeta, ruta, IDOK, recibo, post-read perdido, clic ambiguo, diálogo de otro proceso, escritura en la mirada) y `ComputerUseSpeedTests.AShortcutSaysWhetherAnythingOfItsWindowChanged` | 9 rojas con `Apply` y `Shortcut` anulados (`rojo_proveedor.log`) | 50/50 |
| `ComputerUseListenedPressTests.ALeafNodeCannotOpenAndNothingIsSent` (corre `Invoke-MannerControl` real) | roja (`rojo_hoja.log`) | verde |
| `TextDeliveryTests.ATextIsNotTypedIntoAFocusedButton` | roja (`rojo_boton.log`) | verde |
| `AcceptByIdentity`, `OwnedBy` | rojos en vivo (Paint `visible_button_ambiguous`, Chrome «tapada») | verdes |

Verificación (PC, prioridad baja, afinidad 4 núcleos, `-m:2`): `dotnet build Baxy.slnx -c Release` 0 advertencias y 0
errores; `Baxy.Providers.Windows.Tests` 3626/3626, `Baxy.App.Tests` 467/467, `Baxy.Kernel.Tests` 991/991.

---

# Quinta vuelta: lo que vio el humo del 31-10 en «Guardar como» (Bloc de notas, Paint, Edge)

El humo de la noche (App de e43e08c8b, modelo c3r9b_1-sA, NB) pidió guardar lo abierto en el Bloc de notas en el
escritorio con otro nombre: quedó guardado en el escritorio con el nombre de origen, y en otra corrida la mirada no
encontró el Bloc de notas que `window.resolve` acababa de encontrar. Todo se reprodujo en vivo en el NB con el motor
real y sin modelo (arnés `vivo_dlg.py`, tarea interactiva `BAXY-c3-dlg2`, ya quitada). Evidencia en
`F:\BAXYeval\ft_v1\c3\app_vivo\dialogo2\` (planes, `tanda_*\grabacion.jsonl`, `rojo_pruebas.log`, `rojo2.log`).
Tandas `r*` y `a*`: motor viejo (85722532b, mismo envío de texto que e43e08c8b); `v*`, `n*` y `f*`: con el arreglo.

## Causas (medidas)

1. **El texto tras un clic en el árbol de navegación caía en el árbol.** El foco queda en `SysTreeView32`; el texto
   sin índice iba por teclado (sus letras mueven la selección del árbol) y el recibo era `completed` con
   `readBack: false` y `authority: win32_sendinput_return_count`: nada se comprobó (r1 paso 30, a1, a3, a4).
2. **Un nombre puesto por índice no lo tomaba el diálogo.** Con índice, el campo de nombre (un `Edit` Win32) recibía
   el texto por `ValuePattern.SetValue` de UI Automation: se releía bien, pero el diálogo guardaba con el nombre que
   ya tenía («base.txt ya existe» al pedir `sv1.txt`; en Edge, «pagina de prueba.html»). Escrito por los mensajes del
   propio control (`EM_REPLACESEL`, como escribe el teclado), el diálogo sí lo toma (todas las tandas con el arreglo y
   las de la cuarta vuelta).
3. **El escritorio elegido en el árbol no tenía ruta.** La dirección muestra «Dirección: Escritorio», sin ruta; el
   recibo de «Guardar» era `completed` con `pathKnown: false` y nada comprobado (humo, a3 y a4: Paint guardó
   «Sin título.paint» y Edge «pagina de prueba.html» en el escritorio, ambos `completed`).
4. **`window.resolve` y la mirada resolvían el nombre distinto.** `window.resolve` usa el catálogo de apps instaladas
   (el mismo que `app.open`): «Bloc de notas» → Notepad.exe. La mirada sólo miraba el ejecutable («Notepad»), su
   descripción y el título («base.txt: Bloc de notas», sin « - »), más lo aprendido de un `app.open`. Con el Bloc de
   notas abierto por la persona: `application_window_not_found` (r2). No dependía de que estuviera detrás.
5. **(visto en Paint) La mirada leía un tooltip.** Con «Guardar como» de Paint abierto, `GW_ENABLEDPOPUP` de la ventana
   deshabilitada devolvía un `tooltips_class32` del diálogo (transparente al ratón, nunca activo): tres miradas
   seguidas leyeron una ventana «» vacía (n5, con `ventanas.ps1`). El recibo de «¿reemplazar?» nombraba ese tooltip
   («Fecha de creación: …») como la ventana que respondía.

## Arreglo (nada nombra una app ni un idioma)

- Texto sin índice para un diálogo de archivos común cuyo foco no es un control de edición: va entero al campo de
  nombre del diálogo (el de `CommonFileDialog`), por sus mensajes, y se relee; el recibo lleva
  `intoField: "file_name"`. La tecla siguiente (Enter) pone antes el foco en ese campo (como tras un valor puesto sin
  foco).
- Texto sin índice para cualquier otra ventana cuyo foco es un control Win32 que no toma texto (botón, árbol, lista,
  pestañas, barra de desplazamiento, deslizador, cabecera, barra de herramientas): `input_focus_not_a_field`, nada
  enviado (generaliza la regla del botón de la cuarta vuelta).
- Texto por índice a un control que es ventana propia (`42.<hwnd>`) y es un `Edit`/RichEdit, o un combo editable a
  través de su `Edit`: por los mensajes del control (sobre su selección; entero con `replace` o si es el campo de
  nombre de un diálogo de archivos), nunca `SetValue`. Un control de varias líneas sigue sin reemplazarse entero.
- La carpeta de un diálogo cuya dirección muestra un nombre: si ese nombre, solo tras la etiqueta, es el que el shell
  da a una carpeta conocida (escritorio, documentos, descargas, imágenes, música, vídeos: `SHGetKnownFolderPath` y
  `SHGetFileInfo`, en el idioma de la persona), su ruta. Así el recibo comprueba el archivo.
- La mirada por nombre que no encuentra ventana pregunta al catálogo de apps instaladas del Core (el de `app.open` y
  `window.resolve`, vía `WindowsExternalCapabilityProvider.ResolveApplicationsWith`); el ejecutable que corre sus
  ventanas se aprende para ese nombre (como tras un `app.open` verificado) y se vuelve a buscar.
- `ModalSurface` no se queda en una ventana emergente que no toma entrada (`WS_EX_TRANSPARENT`/`WS_EX_NOACTIVATE`): la
  superficie es la ventana que la posee. El recibo del diálogo tampoco nombra una ventana así como la que respondió.

## En vivo en el NB: app × resultado

| App | Paso | Antes (motor viejo) | Después |
|---|---|---|---|
| Bloc de notas | «Escritorio» en el árbol + nombre sin índice + «Guardar» | texto al árbol, `completed` sin releer; «Guardar»: `file_dialog_still_open`, nada guardado (a1) | `em_replacesel` al campo, `completed` `exists` `…\Escritorio\c3dlg2 uno-f.txt` (f1) |
| Bloc de notas | igual, confirmado con Enter | — | Enter con el foco puesto antes en el campo: `completed` `exists` `c3dlg2 dos-f.txt` (f1) |
| Bloc de notas | nombre por índice + «Guardar» | `setvalue`; el diálogo usó el nombre viejo: «base.txt ya existe» (r1) | `em_replacesel`, `completed` `exists` `sv-f.txt` (f1, v1) |
| Bloc de notas | ruta entera sin índice | `completed` `exists` (r1) | igual (f1) |
| Bloc de notas abierto por la persona, detrás | `window.resolve` + mirada «Bloc de notas» | `application_window_not_found` (r2) | ve la ventana (v2, f2) |
| Paint | «Escritorio» + nombre sin índice + «Guardar» | texto al árbol; `completed`, `pathKnown: false`; guardó «Sin título.paint» (a3) | `completed` `exists` `c3dlg2 paint-f.paint` (f3) |
| Paint | nombre por índice | la mirada leía el tooltip vacío (n3, n5) | `completed` `exists` `dibujo-f.paint` (f3, n6) |
| Paint | nombre que ya existe | — | `file_dialog_answered_by_another_window` por «Confirmar Guardar como» (f5) |
| Edge (diálogo de otro proceso) | «Escritorio» + nombre sin índice + «Guardar» | texto al árbol; `completed`, `pathKnown: false`; guardó «pagina de prueba.html» (a4) | `completed` `exists` `c3dlg2 edge-f.html` (f4) |
| Edge | nombre por índice | `setvalue`; el diálogo usó el nombre viejo («ya existe», a4) | `completed` `exists` `edge-f.html` (f4, n4) |

Los archivos que las tandas dejaron en el escritorio del NB se movieron a `D:\BAXYeval\dlg2_prueba\restos`. Nada
quedó abierto (Bloc de notas, Paint, Edge, Calculadora y `baxy-core` cerrados por PID); la ventana «Configuración» que
ya estaba abierta en el NB no se tocó. Eventos 7040 en las últimas 3 h: 8, ninguno en la última hora.

## Pruebas (rojo antes, verde después)

| Prueba | Rojo | Verde |
|---|---|---|
| `TextDeliveryTests.ATextIsNotTypedIntoAFocusedButton` (árbol, lista, list box) | 3 rojas | verdes |
| `TextDeliveryTests.AViewedEditControlTakesTheTextByItsMessagesAndNotBySetValue` | roja (`setvalue`) | verde |
| `TextDeliveryTests.ATextForAFileDialogWhoseFocusIsNoFieldGoesIntoItsNameField` | roja (teclado al árbol) | verde |
| `CommonFileDialogTests.AKnownFolderShownByItsNameIsItsPath` (7 casos) | 3 rojas | verdes |
| `ComputerUseWindowIdentityTests.ALookByTheInstalledNameFindsTheWindowItsApplicationRuns` | roja | verde |
| `ComputerUseTiposUiaTests.APopUpThatTakesNoInputStandsForTheWindowThatOwnsIt` | roja (`rojo2.log`) | verde |
| `ATextIntoAFileDialogsNameFieldByItsIndexIsTheWholeName`, `AViewedDocumentEditIsNotReplacedWhole` | escritas tras el cambio (contrato) | verdes |

`OwnedWindowOf` sin tooltip sólo se comprobó en vivo (f5): no tiene costura de prueba.

## Lo que no se cubrió

- Sin modelo: el arnés manda las operaciones que el modelo mandaría. La App con modelo no se probó (lo decide la
  sesión principal, igual que el despliegue).
- Un foco que no es Win32 (XAML, Chromium) y no toma texto no se detecta: el texto sigue yendo por teclado con el
  recibo de siempre. Cuando el árbol del diálogo está desplazado a la carpeta actual y no muestra «Escritorio», el
  modelo tiene que subir el árbol o escribir la ruta entera (la vista ya dice que la ruta entera guarda ahí).
- La dirección de una subcarpeta de un lugar conocido sin ruta («Escritorio › x»), las bibliotecas y «Este equipo»
  siguen sin ruta (`pathKnown: false`).

---

# Sexta vuelta: «Guardar como» en los humos del 31-10 (A y B), parte App y parte modelo

Pedido de los humos: «guarda lo que tengo abierto en el Bloc de notas con Guardar como, en el escritorio, con el nombre
prueba c3 guardado.txt». Evidencia: `captura-*\dialogo\events.jsonl` de `D:\BAXYeval\deploy\c3-e43e08c8bc68\`,
`c3-7cf26e904821\` y `c3-sB-e43e08c8bc68\` (NB), y las pasadas `D:\BAXYeval\dlg2\vivo_app_{1,2,3}\`. Copia en
`F:\BAXYeval\wt\c3-dlg2-evid\`.

| Humo | Modelo + App | Operaciones del modelo tras abrir «Guardar como» | Recibos de la App | Resultado |
|---|---|---|---|---|
| 01:28 y 01:30 | sA + 3df619e01 | `input.text.type {"text":"prueba c3","index":27}` (índice de la mirada vigente) → «Guardar» → «Sí» al «¿reemplazar?» | `setvalue` `completed`, pero el diálogo usó el nombre viejo («origen c3.txt ya existe») | sobrescribió `origen c3.txt` |
| 01:40 | sA + e43e08c8b | «Escritorio» [11] → «Guardar» [34] | `completed` con `pathKnown: false` | `origen c3.txt` en el escritorio |
| 03:01 | sB + 7cf26e904 | «Escritorio» [11] → «Guardar» [34] | `completed` con `path …\Escritorio\origen c3.txt`, `exists` | `origen c3.txt` en el escritorio (lo dijo) |
| 03:18 | sB + e43e08c8b | «Escritorio» [11] → `input.text.type {"text":"prueba c3","index":27}` → «Guardar» [34] → `input.key.press {"key":"enter","consequence":"overwrite"}` a la ventana del Bloc de notas → «sí» | texto: `input_field_not_reachable`; «Guardar»: `completed`, `pathKnown: false`; Enter: al editor, el documento queda «Modificado» | `origen c3.txt` en el escritorio y un salto de línea en el documento |
| 03:47, pasada 1 | sB + 7cf26e904 (App publicada aparte) | «Escritorio» [11] → clic en «Nombre de archivo:» [26] → mirada → «Guardar» [37] | clic: `visible_button_ambiguous`; «Guardar»: `completed`, `path …\Escritorio\origen c3.txt`, `exists` | `origen c3.txt` en el escritorio (lo dijo) |
| 03:48 y 03:49, pasadas 2 y 3 | sB + 7cf26e904 | pregunta qué guardar; con «sí»: «Escritorio» [11] → `input.text.type {"text":"prueba c3","index":27}` → mirada → «Guardar» [37] | texto: `input_field_not_reachable`, nada enviado; «Guardar»: `file_dialog_answered_by_another_window` («Confirmar Guardar como»: `origen c3.txt` ya existía de la pasada 1) | nada guardado; BAXY pregunta si reemplaza |

**Por qué `input_field_not_reachable` tras «Escritorio» (03:18 y pasadas 2 y 3).** El clic en el árbol llena la lista
de archivos y la App vuelve a numerar la vista con lo que leyó después del clic: el campo de nombre pasa de [27] a
[30], y el recibo del clic lo dice (`after.changed: "[30] Edit «Nombre de archivo:» … = origen c3"`). El modelo escribe
en [27], el índice de la mirada anterior, que ahora es un elemento de la lista (`ListItem` de una carpeta del escritorio
de la persona). La App no envía nada y lo dice. Con la mirada al día, la App escribe donde debe: en el arnés, con la misma
secuencia y el índice de una mirada nueva, 7cf26e904 da `em_replacesel` y `completed` con `exists`
`…\Escritorio\c3dlg2 tres.txt` (g1). El motor viejo, en el mismo caso (g0), da `setvalue` y `pathKnown: false`.

**Parte de la App (arreglada en 7cf26e904, no hay nada nuevo que tocar):**

- Escrito con `SetValue`, el nombre no siempre lo tomaba el diálogo (01:28 y 01:30, r1). Ahora un `Edit` Win32 se
  escribe por sus mensajes.
- El recibo de «Guardar» tras «Escritorio» decía `completed` sin ruta (01:40, 03:18). Ahora lleva la ruta y comprueba
  el archivo (03:01, pasada 1).

**Parte del modelo (no se toca la App):**

- No escribe el nombre: A a las 01:40, B a las 03:01 y en la pasada 1, donde además intenta un clic en el campo con un
  rótulo que comparten dos controles.
- Escribe con el índice viejo tras un clic que cambió la vista: 03:18 y pasadas 2 y 3.
- Escribe «prueba c3» en vez del nombre pedido «prueba c3 guardado.txt»: en todos los casos en que escribe.
- Sigue después de un fallo: pulsa «Guardar» aunque la escritura falló (03:18, pasadas 2 y 3). A las 03:18 manda además
  Enter «overwrite» al documento del Bloc de notas.

Para los datos: «Guardar como con nombre» (el nombre entero pedido, con la mirada al día después de navegar, antes de
«Guardar») y «no confirmar tras un fallo de escritura».

Decisión para la sesión principal, no tomada aquí: una ayuda de la App sería que el fallo de un texto por índice en un
diálogo de archivos diga el índice actual de su campo de nombre (`next`), o que los índices de los controles que siguen
en la vista no cambien tras un acto.

«Configuración de sonido» con B («Settings»): no es de 7cf26e904 y lo lleva otro agente. Aquí no se cambia nada. Un
arreglo hecho antes de la corrección quedó sólo en local (rama `dlg2-settings-local`, 1bc73cdb4, sin subir).

---

# Séptima vuelta: un índice nombra el control que el modelo vio (clic y escritura, en cualquier ventana)

Encargo de la sesión principal tras la sexta vuelta: «un índice que manda el modelo se refiere al control que él VIO en su
última mirada, no a la posición actual». Causa medida en la sexta vuelta: tras el clic en «Escritorio» la lectura de
después renumeró la ventana (el campo de nombre pasó de [27] a [30], y la «after» recortada a 20 entradas no lo dijo); el
modelo escribió por [27] y la App tomó el [27] nuevo, una carpeta del escritorio de la persona.

## Arreglo

- La última vista guarda, además de su numeración, lo que el modelo sabe por índice (`LastView.Told`): la mirada entera
  y, tras cada acto, lo que su «after» listó con índice (`ViewDifference` dice qué índices listó). Una mirada nueva lo
  borra (el modelo vio la ventana entera).
- `ResolveSeen`: el índice nombra el control visto ahí. Ese mismo control se busca en la vista actual por su RuntimeId;
  si cambió, por AutomationId + rol + nombre (sólo si hay uno). Si está en otro índice, se actúa sobre él y el recibo
  lleva `indexAsked` e `indexNow`. Si ya no está, no se actúa sobre nada: el recibo es `visible_control_identity_stale`
  con `seen` (lo que había), `gone` y, si un único control tiene su rol y su nombre, `equivalentIndex` (y su `next` con la
  ayuda `index_label_next`). Nunca se toma lo que ocupa ahora ese índice.
- Vale para `input.visible.click` por índice (el control visto, si su rótulo lo nombra; si no, la cascada por rótulo de
  siempre), `input.text.type` por índice (escribir, reemplazar, elegir entrada) e `input.scroll` por índice, en
  cualquier ventana. El worker añade `aid` (AutomationId) a cada control de la vista.

## Pruebas (rojo antes, verde después: `rojo4.log`)

`ComputerUseAfterViewTests.AnIndexMeansTheControlTheModelSawThereNotWhatTheRenumberedViewHasThere` (escritura y clic tras
una «after» recortada: [21] es el campo, ahora en [22]), `…AnIndexWhoseControlIsGoneActsOnNothingAndSaysSo`,
`…TheSameControlIsItsRuntimeIdElseItsAutomationIdKindAndNameOnce` (5 casos),
`TextDeliveryTests.ATextByAnIndexGoesToTheControlSeenThereWhereverItIsNow` y `…WhoseControlIsGoneWritesNothing`: 5 rojas
con el código anterior, verdes con el cambio.

## En vivo en el NB: App completa publicada aparte (f344224ae, `Baxy.exe` 7d9eff7c…), sin tocar la producción

GGUF por variable: A = `BAXY-Qwen3.5-4B-ft-c3-c3r9b_1-sA-Q4_K_M.gguf` (la desplegada), B = `…-sB-Q4_K_M.gguf`.

| Modelo | Prueba | Resultado | Qué pasó |
|---|---|---|---|
| A | configuración de sonido ×3 | 3/3 abre | `app.open Configuración place sound` (A1–A3) |
| A | Guardar como (A1) | a medias | sin índice «prueba c3» → al campo de nombre (`intoField`) → «Guardar»: `prueba c3.txt` en el escritorio, comprobado; el modelo recortó el nombre |
| A | Guardar como (A2, A3) | no valen | índice 27→30 escrito y «Guardar» 34→37 bien; el «¿reemplazar?» salió por el `prueba c3.txt` que dejó A1 (el arnés no lo apartaba); se repitieron como A4 y A5 |
| A | Guardar como (A4) | **bien** | «Escritorio» → texto por [27] → `indexAsked 27, indexNow 30` → «Guardar» → `…\Escritorio\prueba c3 guardado.txt`, `exists` |
| A | Guardar como (A5) | falla, dicha | el modelo no escribe: pulsa «Editar» tres veces; BAXY dice que no pudo cambiar el nombre |
| B | Guardar como (B1) | a medias | sin «Escritorio»: guardó `prueba c3 guardado.txt` en la carpeta del diálogo; el recibo da esa ruta y la respuesta dice «en el escritorio» (del modelo) |
| B | Guardar como (B2) | a medias, dicha | clic en un rótulo «prueba c3 guardado.txt» que no existe → «Guardar» → `origen c3.txt` en el escritorio, y lo dice |
| B | Guardar como (B3) | **bien** | texto [27]→[30] y «Guardar» [34]→[37]: `…\Escritorio\prueba c3 guardado.txt`, `exists` |

Antes (App 7cf26e904, mismas pruebas con B a las 03:47): 0 de 3, dos de ellas por `input_field_not_reachable` en [27].
Con el arreglo, las cinco veces que el modelo usó un índice viejo (A2, A4, B3) se actuó sobre el control que había visto.

**Visto y no tocado (para la sesión principal):** un clic por un rótulo que no está en la ventana («prueba c3 guardado.txt»
en B2, «Editar» en A5) bajó por la cascada hasta la visión, que pulsó un punto (`method: pointer`, `controlIdentity
vision.…`) y volvió `completed`. Es la debilidad del localizador por visión ya anotada en E011: localiza rótulos que no
están. No es de esta tarea y no se tocó.

**Incidente:** a las 04:31 lancé una repetición (A4) sin la comprobación de procesos, mientras otro agente corría su
prueba en vivo (`c3-nombres`, `nb_vivo.ps1`). Mi Bloc de notas de prueba estuvo abierto unos dos minutos en su
escritorio. Lo cerré por PID, paré mi tarea y repetí a las 04:53 con el NB libre. Su prueba de 04:30 a 04:33 puede
haber tenido ese Bloc de notas delante.

---

# Octava vuelta: la visión ya no pulsa un rótulo que la ventana no tiene (E011)

Lo visto en la séptima vuelta (A5 «Editar», B2 un nombre de archivo pedido como botón, los dos en un «Guardar como» que
no tiene ninguno): la cascada bajaba hasta la visión, el modelo de visión respondía un punto y, como ni el OCR ponía otra
palabra ahí ni el árbol tenía ahí un control con ese nombre, el puntero lo pulsaba igual; con la superficie cambiada, el
recibo salía `completed`.

## Causa

`WindowsVisibleVisionLocator` sólo rechazaba un punto que caía sobre **otra** palabra (`OtherTextAt`, el caso del
carrito); un punto en blanco, en un icono o en una zona sin texto se daba por bueno y `LocatedPointPress` pasaba al
puntero en cuanto el worker decía que ahí nada llevaba el nombre (`visible_point_no_pattern`). Nada exigía que el punto
fuera el rótulo.

## Arreglo (ft-c3-vision, 015aef031)

- Un punto de la visión se pulsa sólo si es el rótulo: las palabras leídas ahí lo contienen entero
  (`LabelWrittenAt`: una racha de palabras de la línea que contiene el rótulo y está bajo el punto; otra palabra de la
  misma línea no vale), o el control que hay ahí lleva ese nombre (el worker ya sólo pulsa por su vía un control cuyo
  nombre es la etiqueta). Si ninguna de las dos, `LocatedPointPress` no deja pasar al puntero (`pointerAllowed`), nada se
  pulsa, la visión no encontró el rótulo (y lo recuerda para ese mismo dibujo) y el clic termina en
  `visible_button_not_found`.
- Ese «no encontrado» nombra, además de las entradas plegadas de siempre, los controles de la última mirada cuyo nombre
  más se parece al rótulo (`closest`, por índice; ayuda `closest_labels`, con el criterio de `ClosestTitles`).
- La prueba del cambio de superficie tras el clic ya existía (`ok = changed || targeted`) y no cambia.
- Coste: un icono sin nombre en el árbol y sin palabras debajo ya no se pulsa por visión; lo cubre la etapa del tooltip.

## Pruebas

`VisionPointLabelTests` (5): rojo con 8a7d9cd6a (el puntero pulsaba: `visible_click_postread_unread` tras una pulsación),
verde con el arreglo; `CollapsedHintTests` (3, uno nuevo). Suites en Release con avisos como errores, prioridad baja y
afinidad F: Providers.Windows 3655/3655, App 468/468, Kernel 991/991. Registros en
`F:\BAXYeval\ft_v1\c3\app_vivo\vision\`.

## En vivo en el NB (baxy-core aparte de cada commit, sin modelo de BAXY, llama-server propio sólo para la visión)

Mismo plan: el Bloc de notas abre un archivo de prueba, Ctrl+Mayús+S, mirada del diálogo, clic por «Editar», mirada,
clic por un nombre de archivo que no existe, mirada, «Cancelar».

| Clic | Antes (8a7d9cd6a) | Ahora (015aef031) |
|---|---|---|
| «Editar» | `completed`, `vision.472.296`, puntero (9,6 s) | `visible_button_not_found`, nada pulsado (7,8 s) |
| nombre de archivo como botón | `completed`, `vision.253.366`, puntero; el campo de nombre perdió el foco (8,6 s) | `visible_button_not_found`, nada pulsado, con `closest` (8,7 s) |
| «Cancelar» (control) | `completed` por el árbol | `completed` por el árbol |

Sin mirada antes del clic (primera pasada, la mirada se pidió mal): antes, «Editar» `completed` por puntero y el nombre
`visible_button_postread_unchanged` tras otra pulsación; ahora, los dos `visible_button_not_found`. Registros en
`F:\BAXYeval\ft_v1\c3\app_vivo\vision\nb\`. Lo que la prueba abrió se cerró por PID y el NB quedó sin BAXY, llama-server
ni Bloc de notas.
