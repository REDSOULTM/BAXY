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
