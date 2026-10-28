# Qué mide cada banco y hasta dónde creerle

Auditoría de las herramientas de medición (rama `w8-medir`, 2026-10-23, desde int9 17d986bfd). Sin correr el producto
ni bancos: lectura del código y pruebas unitarias. Los arreglos van en un commit cada uno (lista al final).

## Bancos

### `bench_decision.py`: una decisión por caso

Mide la primera decisión del modelo (con System One si se le da `BAXY_S1_GGUF`), juzgada contra la expectativa del
caso. **No ejecuta nada**: ni proveedores ni núcleo.

- **Juez.** `call`: misma operación y cada argumento esperado; los códigos de lista (enum) exactos desde e18a6e260 (antes
  «close» aprobaba close_all, «escape» ctrl_shift_escape: 16 pares en catalog-final); el texto libre sigue siendo
  subcadena («notas» aprueba «notas_viejas.txt»). `ask`: una pregunta (`clarify`) o **cualquier respuesta en palabras
  con «?»**, también un «¿algo más?» tras negarse. `text` sin `reply_re` acepta cualquier respuesta no vacía.
- **Acciones equivocadas** (`pareado --metric wrong_action`): son acciones **propuestas**. En el producto el núcleo
  podía pedir el sí o rechazarlas, así que no son acciones «ejecutadas».
- **Semilla.** `BAXY_RENEW_SEED` mueve sólo el muestreo de las decisiones (temperatura 0,2). El aviso, el relleno de
  «corrige», el latido y la prelectura son voraces (temperatura 0) y la semilla no los toca. System One es un
  codificador sin muestreo: varía sólo cuando no contesta a tiempo (2 s por orden, dos órdenes), y eso ahora se cuenta.
  La voz usa su semilla fija (7, `baxy-voice.json`) y no influye en las decisiones. El reloj real entra en el prompt,
  así que dos corridas con la misma semilla no son idénticas bit a bit (w3-speed: 228 de 259 confianzas difieren en
  milésimas).
- **Errores.** Un caso que falló el servidor cuenta como fallo. Desde c2ba7f3c0 el resumen trae `errors`, y una
  corrida con alguno no está limpia.
- **Recursos.** Una sola lectura al final, no el pico; VRAM = crecimiento de la GPU.
- **Registro** (`summary.run`, c2ba7f3c0): máquina, commit y sha256 de la mente (también para copias sin git), sha256
  del juez, de la equivalencia, del catálogo, del GGUF, de Laya y del servidor, KV, contexto, semilla, temperatura, modo
  de confirmación y cada `BAXY_*`. El catálogo es un archivo y lleva las apps y juegos de la máquina donde se volcó.
- **Aislamiento.** El modo de confirmación que lee «corrige» era el archivo del dueño de cada máquina; ahora es el del
  banco (normal). En el PC y en el notebook ese archivo no existe hoy, así que el holdout v4 corrió en normal.

### `bench_e2e.py`: el producto real, juzgado por el mundo

Corre el producto por el conductor. Lo juzgan oráculos que leen el estado del PC y `must_speak` (lo dicho, entero).

- **Tiempos.** `first_audio` es el primer sonido del turno, aviso incluido. `first_response_audio` es el primer sonido
  de la respuesta, y cuenta la pregunta de confirmación si la hubo. Un turno cuya respuesta nunca sonó va a
  `turns_unanswered` y pesa como el más lento en `…_all_turns`. Desde el arreglo del 22-10 el aviso lo rotula la propia
  voz (evento `sound` con `notice`); lo comprobé en `ConductorUtterances` y en `utterances()`.
- **Sesgo del primer sonido.** El tiempo es la llegada a la App del evento `sound`. La mente lo manda al escribir el
  primer bloque; el sonido real llega `stream.latency` después (latencia del dispositivo, fija en cada máquina). Por eso
  sólo se compara en la misma máquina, y el «3 s» del goal queda medido de menos en esa latencia. La traza
  (`voice.speak`, `sound_at`) sí la incluye.
- **Arranque.** Nada espera a que cargue la voz: el primer caso de una corrida puede incluir la carga de Supertonic. El
  presupuesto por caso (`timeout_s`, 90 s) cuenta también el habla.
- **Respuestas largas.** El banco esperaba el fin del habla 30 s como mucho; desde 38da1824b espera 120 s (antes una
  respuesta de más de ~400 caracteres se cortaba o se leía sin terminar).
- **Puntuación.** `n` cuenta todos los casos; `n_scored` y `accuracy_scored` dejan fuera setup_fallido, void y
  sesion_bloqueada.
- **Aislamiento.**
  - Perfil de BAXY propio en cada corrida (memoria, notas, modo de confirmación).
  - Traza de la mente en `<corrida>\mente`, ya no en el `turns.jsonl` del dueño (4fc83789c).
  - Los archivos nuevos fuera del sandbox van a cuarentena. Los del dueño que un caso cambió o borró sólo se informan:
    `profile_review`, y entonces `contaminated: true` (bb13e48f8).
  - El listado mira dos niveles bajo el perfil y las carpetas conocidas; un cambio más hondo no se ve.
  - El prefijo guardado (`slots`) se comparte entre brazos. Su clave incluye todo lo que lo forma, así que no cambia
    decisiones; sólo cambia `warm_s`.
- **Configuración por máquina.**
  - System One lo decide `run_renew.cmd` con el interruptor `system_one.off` del dueño; el registro dice el ajuste y si
    Laya arrancó de verdad.
  - El PC carga el oído (k4, Ultra) y el notebook no.
  - El GGUF y el contexto los da `run_renew.cmd`; el registro los lee del log de Qwen (9db19277d).

### `bench_falsedades.py`: afirmaciones contra lo que corrió

La lectura a mano es la primaria. Desde el 2026-10-27 el juez del banco es Claude (`juez_claude.py`): a ciegas, una
letra al azar por corrida y la clave aparte (`<label>-falsedades-clave-juez.json`), en tandas de 10 líneas de como
mucho 5 minutos, 8 a la vez, con `CRITERIO_FALSEDADES.md`; cada línea se lee tres veces, cada vez barajada con otras
conversaciones, y manda la mayoría (con un voto, la base s1 grabada cambiaba una clara de lectura en lectura). Cuenta
las claras y, aparte, las dudosas. Una diferencia de un caso entre dos corridas sigue siendo ruido. Las corridas
anteriores las leyó el juez Qwen3.6-35B IQ3 (contexto 16k, tres semillas, mayoría), que sigue en `--judge local`: sus
cifras sólo se comparan con corridas de ese mismo juez (`summary.judge.juez`; sin ese campo, es el 35B). Re-juzgar una
corrida vieja con otro juez aparta su `results.jsonl` como `results-juez-local.jsonl` en vez de pisarlo.

- El `trap` del caso enfoca al juez: ayuda, pero sesga hacia esa trampa.
- Las observaciones se cortaban a 1 500 caracteres, en el juez y en `transcripts.json`, y se perdían los campos del
  final (`truncated`, `linesRead`, totales). Desde 3a157f218 el transcript guarda la observación entera y el juez lee
  todos los campos, con los textos largos cortados por el medio.
- Con una réplica, el ruido es de ±2 falsedades.

### `pareado.py`: la estadística

- Qué calcula: Δ con IC95 por bootstrap pareado sobre ítems (10 000 remuestras, semilla 0), McNemar exacto por mayoría
  (un empate no cuenta), pass^k y Holm entre comparaciones.
- Desde 4dc7fd98b hace lo que CIERRE_PLAN pre-registró y no estaba:
  - deja fuera los casos VOID;
  - `--cases`: error estándar y bootstrap por pareja de gemelos de dictado (`delta_se_twins`, `delta_ci95_twins`);
  - `--metric wrong_action`;
  - avisa de las réplicas con errores de servidor.
- Límites:
  - McNemar sigue suponiendo ítems independientes: con gemelos, vale más `delta_se_twins`.
  - El bootstrap trata la media entre réplicas de cada ítem como fija: no separa la varianza entre semillas.

### Otros

- **`compare_banks.py`**: re-juzga corridas guardadas con el juez de hoy. Con la misma tanda en `--old` y `--new`, más
  `--catalog`, es el «juez común» del holdout.
- **`F:\BAXYeval\renew_v4\rejuzgar.py`** (v4, no tocado): importa el juez del worktree `BAXY-Renew-s1`, que se mueve, y
  estampa «452854a18» sin comprobarlo. No usarlo para v5.
- **`measure_resources.py`**:
  - Qué mide: el pico (1 Hz) de USS por papel y de la GPU durante tres turnos de charla.
  - Qué no ejercita: herramientas, historia larga ni las dudas que llaman a Laya (está su RAM, no su cómputo). Un pico
    de menos de 1 s puede escaparse.
  - Desde 9e1f54697 cuenta sólo el árbol de procesos de su conductor. Antes sumaba cualquier llama-server de
    `BAXYeval`, también el juez 35B o un banco que corriera al lado.
  - Comprueba la línea base de la GPU al cerrar: `vram_attribution`.
- **`relecturas.py`, `medir_relectura.py`, `medir_preproceso.py`**: diagnóstico de llama-server (log y tiempos), no
  cifras del goal. `relecturas` lee por defecto el `llama-server.log` compartido, que es el de la última corrida del
  producto o de cualquier banco.
- **`rescore_e2e.py`**: re-puntúa los oráculos de voz de una corrida guardada, con la misma regla de `utterances()`.
- **`lib\bench.ps1`**: no lo edité. Restaura ventanas, volumen, portapapeles, tema, tareas y sandbox. Los archivos del
  dueño sólo los informa (ver aislamiento).
- **`bench_escenas.py`**: fuera de la auditoría (el latido está apagado).
- **`privacidad.py`**: en diffs de código da coincidencias falsas con Python genérico («from pathlib import Path»).
  Leer cada una; no sirve como compuerta automática para código.

## Qué cambia al correr el holdout v5

1. **Fusionar `w8-medir` antes de abrir.** El juez de cada corrida queda en `summary.run.judge_sha256`.
2. **Decisión.**
   - Correr `bench_decision.py … --catalog F:\BAXYeval\renew_v4\catalog-final.json`.
   - Juez común para las tres configuraciones: `compare_banks.py <corridas> --old <decision.json> --new <decision.json>
     --catalog …catalog-final.json --write`, en vez de `rejuzgar.py`.
   - El validador del sello probó el juez anterior (subcadena). En la apertura, quien abre vuelve a correr
     `holdout_tools\validate.py` con este juez: la respuesta correcta sintética usa el código exacto y debe seguir
     pasando.
   - Repetir una corrida si se detuvo por System One, si `errors > 0` o si `system_one.unanswered` no es casi 0.
   - Analizar con `pareado.py … --cases <decision.json>` (gemelos) y con `--metric wrong_action` para la secundaria.
3. **E2E y falsedades** (notebook).
   - Antes de abrir, sacar del home del notebook los restos de bancos anteriores: tareas_hoy.txt, config.ini,
     q4\notes.txt, compras.txt, notas.txt, lista.txt, prueba.txt, proyecto\. Hoy cuentan como archivos «del dueño» y se
     modifican sin deshacerse.
   - Fijar System One en cada brazo: `scripts\system_one.cmd estado` o `BAXY_S1_*` explícitas, y comprobar en
     `summary.run.system_one` que `on == server_started`.
   - Intercalar los brazos (s1off, s1on, maximo, s1off…); en v4 falsedades corrió uno tras otro.
   - Tras cada brazo, `contaminated` debe ser `false`. Si no, devolver los archivos y repetir el brazo siguiente.
   - `first_response_audio` sólo se compara dentro de la misma máquina.
   - La lectura a mano de falsedades usa `transcripts.json`, que ahora trae la observación entera.
4. **Recursos.** `measure_resources.py` nuevo, con `vram_attribution: ok`, en la máquina sin otros bancos.

## Commits de la auditoría

| Commit | Defecto |
|---|---|
| e18a6e260 | El juez aprobaba un código de lista equivocado que contenía el esperado (close_all, backspace, ctrl_shift_escape…) |
| c2ba7f3c0 | La corrida de decisión no decía con qué se midió (B-MED-5); modo de confirmación del dueño; traza mezclada |
| 3dfd6533a | Nadie esperaba a System One; sus respuestas vacías no se contaban |
| 4dc7fd98b | pareado no hacía lo pre-registrado: VOID, gemelos, acciones equivocadas |
| 4fc83789c | Los bancos escribían sus turnos en el `turns.jsonl` real del dueño (y lo rotaban) |
| bb13e48f8 | e2e y falsedades: sin registro, S1 según el interruptor del dueño, contaminación sin marcar, n sin VOID |
| 9e1f54697 | Recursos sumaba procesos ajenos; VRAM sin comprobar la línea base |
| 3a157f218 | El juez de falsedades (y la lectura a mano) perdía los campos del final de una observación |
| 38da1824b | Una respuesta larga se cortaba a los 30 s y fallaba `must_speak` |
| 9db19277d | e2e y falsedades no registraban el GGUF ni el contexto de Qwen |
