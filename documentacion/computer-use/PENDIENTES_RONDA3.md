# Pendientes de la ronda 3 (computer use v3)

Integración `fable/cu-v3-ronda3` sobre `fable/cu-universal-v3` (que ya trae las rondas 1 y 2). `PROGRESO_V3.md` es del
líder y queda en la versión de la base; las notas de la integración viven aquí. Informes de las ramas:
`%LOCALAPPDATA%\BAXY\cu-v3\r3i\<rama>.json`; análisis de origen: `%LOCALAPPDATA%\BAXY\cu-v3\r3a\*.md`.

## Fusiones y conflictos

Orden: estado-lote, llegada-evidencia, final-actos, ruta, lectura, arbol-win32, buscar, limites, web-evidencia,
interpretar (todas `--no-ff`, cabezas = las de la corrección de cada informe).

- **final-actos** — `OperationFloor.cs`: el «visto, no hecho» de llegada-evidencia (sin acto propio) y el
  `typedLeft` de final-actos (lo escrito antes de parar) se conservan los dos; la mente ya los tenía en ese orden.
- **lectura** — `semantic/missions.py`, `_UNDOING_OR_PAYING_ACT` y `_DESTRUCTIVE_OR_PAYING`: el formateo pasa por
  `_FORMATTING_A_DRIVE` (ruta: sólo una unidad o el equipo) y el dinero o regalo enviado por
  `_SENDING_MONEY_OR_GIFT` (lectura), con `transferi\w*` de lectura.
- **limites** — por unión:
  - `ComputerUseMission.cs`: `observed.seenNotDone` y `observed.gate`.
  - `OperationFloor.cs`: la causa de la puerta con su cola y el `+ typedLeft` del final.
  - `computer_use.py`: imports de `app_gates` y `cu_buscar`; en `_checked_act` la puerta se juzga antes que el juez
    del acto (un done sobre una puerta termina con la causa de la puerta, no con «todavía no hice nada»);
    `project_seen` lleva `seenNotDone` y la puerta.
  - `tests/data/cu_floor_twins.json`: unión por id (36 + 2 gemelos de puerta).
- Rojos de la fusión, cada uno con su commit:
  - `_HEAD_FRAME` definido dos veces en `missions.py` (ruta y lectura); la segunda reemplazaba en silencio a la
    primera y `_head_frame` fallaba en ~180 tests. Ahora `_HEAD_FRAME` es el «<app>: …» de lectura y la cabeza de
    lugar de ruta es `_PLACE_HEAD`, con la alternancia compartida con `_HEAD_PLACE`.
  - ruta + lectura: el lector de misiones ya lee «en la terminal andá a configuración y …» y «abre powerpint, …». El
    bloque v2-s13 tomaba entonces la reformulación del decisor como objetivo (v3-38); la reformulación sólo da el
    lugar cuando la persona no lo dijo. La puerta de cobertura escribe el lugar mal escrito como la app también
    cuando el lector lo resuelve solo (v3-04), salvo que la persona lo diga entero en otra parte («… en fotos»).
  - Gemelo `cu-seen-not-done-after-steps`: ahora termina en «; antes de parar escribí «pruebas»» (typedLeft).
  - `test_a_success_after_pressing_the_control_the_goal_names_on_the_gate_holds`: el clic lleva `changed:true`,
    el recibo que da el App (HistoryForMind); sin él el juez único del done no ve acto.

## Duplicados consolidados (ley 2)

- **Fin de semana**: `semantic.web.weather_asked_span` (interpretar) y `temporal._said_days` (agenda) leían cada uno
  «fin de semana / finde / weekend / next weekend» y discrepaban en «next weekend» dicho entre semana. Uno solo:
  `semantic.temporal.weekend_saturday`, con la regla de la agenda para «que viene/next» (oro de uso real 2026-09-23)
  y la de interpretar para «after next / el otro finde / en dos fines de semana».
- **Errata en el nombre de una app**: `place_misspelled` (ruta) medía con `games._edit_distance` y su umbral propio;
  ahora usa `_typing_slip`, que aplica el `_near_word` de lectura palabra por palabra (2 ediciones en total).
- **Cabeza de cláusula con lugar**: `_PLACE_HEAD` y `_HEAD_PLACE` comparten `_PLACE_HEAD_WORDS`.
- Revisados sin duplicado:
  - Jueces de evidencia: el del done de la misión (llegada-evidencia, `EvidenceRefusal`/`done_needs_an_act`), el libro
    de actos del final (final-actos, `_act_ledger` en el compositor) y el veto de causa omitida (limites,
    `mission_defect`) juzgan capas distintas; la puerta de limites y el juez de llegada comparten `_checked_act` con
    un orden fijo. «Sin resultados» vive sólo en `computerUse.evidence.noResults` (mente y App).
  - «No hice nada»: `seenNotDone` (sin pasos) y la causa `computer_use_seen_not_done` (con pasos) son las dos ramas
    de un mismo cierre; la puerta dice «no pulsé nada ahí» sólo en su cola `appGateTail.untouched` y en la causa
    genérica sin texto.
  - Puertas y límites: `app_gate` (pantalla de puerta) y `_start_page_step` (página de inicio con «en blanco») miran
    cosas distintas; `_engine_for_an_unserved_order` es enrutamiento, no lectura de pantalla.
  - Páginas web: el artículo de Wikipedia se pide a la API (`WikipediaSearchSource.ReadArticleAsync`, el HTML pasa del
    tope de 1,5 MB de `SearchPageReader`) y se lee con el mismo `SearchPageExcerpt.Read`. `SearchPageExcerpt.States`
    es el espejo C# de `semantic.answer_evidence`, con las palabras enviadas por la mente (answerWords/answerWordsNot).
  - Lugar: interpretar no hizo «valpo» (no hay normalizador de lugar nuevo).

## Pendiente

- **Dos jueces del eco de lo tecleado** en `_checked_act`: `_echoes_typing` (base, todo objetivo, palabras enteras sin
  clic que mueva) y `_holds_typing` (llegada, objetivos de hacer, contención y excepciones de la vista), con sus
  gemelos en el App (`CitationEchoesQuery` y `typed_by_baxy`). Son de la misma rama, a sabiendas; unirlos cambia
  checks fijados en las dos capas.
- **«Next weekend» entre semana** ahora es el fin de semana siguiente al que viene, también para el clima; «the weekend
  after next» dicho entre semana sigue siendo una semana después del que viene (fijado por interpretar). En inglés
  las dos lecturas son ambiguas; si el dueño prefiere otra, se cambia en `weekend_saturday` para todos.
- Sin verificar en vivo ninguna rama (ver «Verificación en vivo»). Pendientes propios de cada rama en su informe:
  - estado-lote: COM Quit de Office, salir_sin_ventanas, TabState de Notepad, cierre de ventana nueva en proceso del
    dueño, el flujo entero de batch.sh/lote.sh; linaje con padres efímeros da «desconocida» (no cierra).
  - llegada-evidencia: `control:=X` en navegación sin hacer; el rechazo del App cierra la misión (sólo la mente
    reintenta); una mirada temprana tras un clic lento puede rechazar un done.
  - final-actos: sin leer «con la nueva escena Pruebas lista», «está creada», auxiliares y pasiva en inglés.
  - ruta: L4 y la segunda mitad de M4 sin hacer; «abrí spotify y hacé una presentación» se haría en Spotify;
    `locate_file` recorre carpetas reales en los tests.
  - lectura: v3-58 turno 2 (Configuración de Edge vs. de Windows), v3-35, v3-19/24, v3-29 «sticky note nueva».
  - arbol-win32: la vista aún cae a la ventana de delante si la app no tiene ventana; InterfaceUp=20 y el tope de 8 s
    sin calibrar; el ClassicControlsLiveDesktopCheck no corrió.
  - buscar: desplegar por expansión (`expand` en input.visible.click) sin hacer (v3-37); v3-41 sólo prompt.
  - limites: `app.open` no devuelve `seen.elevated` (v3-69); teclas directas sobre ventana elevada; umbrales de
    puerta sólo con vistas sintéticas.
  - web-evidencia: un ranking no se construye leyendo la tabla; relaciones cerradas en datos (9 clases).
  - interpretar: «valpo», «el viernes por la tarde, a la hora que sea», cerrar sin confirmar (c).

## Verificación en vivo pendiente

- Lote ciego con el libro del lote nuevo (`libro_lote.ps1`, `registro_dueno.py`): cierre por PID, nada del dueño
  tocado, `verificado=true`.
- v3-17/v3-35/v3-40/v3-11 (juez del done), v3-58 (eco de consulta).
- t-form-2 y t-file-1 (finales con lo escrito y sin lugar inventado), v3-51, t1-c13.
- v3-04, v3-38, v3-08, v3-16, v3-34 (puerta de cobertura con lectura).
- v3-39/62/67 (marco «<app>: …»), v3-26, v3-24.
- Charmap y otros Win32 clásicos (proveedores de cliente), v3-49 (7-Zip por descripción).
- v3-44, v3-59, v3-40 (buscar), v3-21 y v3-72 (elevada), v3-05..07 y v3-34 (puertas).
- Tanda 1 filas 20/22/82 (web-evidencia) y el clima de fin de semana (interpretar).
