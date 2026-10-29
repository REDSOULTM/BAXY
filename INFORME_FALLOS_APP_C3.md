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
la red del NB: arreglarlo sería adivinar. Si vuelve a salir, el siguiente paso es registrar el estado HTTP en el recibo.
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
| 1 | runtime python `-m pytest tests/test_mind_aids.py tests/test_mind_bucle.py -q` | 126 pass |
| 2 | `ruff check src/baxy_mind/mind.py tests/test_mind_aids.py` (ruff 0.15.12 del sistema; el runtime no trae ruff) | sin hallazgos |
| 2 | `dotnet build Baxy.slnx -c Release --nologo -v:minimal -m:4` | 0 advertencias, 0 errores |

No se corrió el peldaño 3 entero (pytest completo y todas las suites .NET): el cambio son dos recibos y una guarda,
cubiertos por sus pruebas dueñas, y la CPU del PC la comparte la criba. Este worktree no tiene
`scripts/test_source_quality.ps1`.

No se corrió ningún banco en vivo: lo decide la sesión líder. La rama no está subida a `hub`.
