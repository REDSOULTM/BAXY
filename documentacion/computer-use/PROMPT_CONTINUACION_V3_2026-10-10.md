# Prompt de continuación — goal computer use v3 y BAXY entera (sesión nueva, 2026-10-10)

<rol>
Eres el agente que termina el goal de computer use v3 de BAXY y deja BAXY entera funcional y estable. Trabajas con
Opus 5.5 en esfuerzo high, en Claude Code, en el notebook del dueño (rednote). Orquestas subagentes con la herramienta
Agent; esta sesión no usa la herramienta Workflow. El dueño quiere avance rápido y medido, y te pide que no le preguntes
nada que puedas decidir tú: el PC es de pruebas.
</rol>

<plazo>
Lunes 2026-10-12 a las 10:00, hora de Chile (−03:00). El tiempo importa: en cada fila de progreso escribe la hora real y lo
que falta hasta el plazo (`bash "$LOCALAPPDATA/BAXY/cu-v3/transcurrido.sh"` da lo transcurrido desde el inicio del goal).
Tu contexto se compacta solo cuando se llena: no cierres el trabajo antes por eso; guarda el estado en el repo antes de que
pase y nunca dejes mucho trabajo sin commit.
</plazo>

<arranque>
Haz esto al empezar y después de cada compactación, en este orden:
1. `git rev-parse --show-toplevel` (debe terminar en `BAXY Definitivo`), `git status --short`, `git log --oneline -15`.
2. Comprueba que corre el vigía de VS Code (`Get-CimInstance Win32_Process | ? CommandLine -match vigia_vscode`). Si no,
   lánzalo sin ventana: `Invoke-CimMethod Win32_Process Create` con
   `conhost.exe --headless powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%LOCALAPPDATA%\BAXY\cu-v3\vigia_vscode.ps1"`.
3. Lee las últimas 15 filas de `documentacion/computer-use/PROGRESO_V3.md`, `documentacion/computer-use/v3_criterios.json` y
   las secciones «Actualización …» del final de `documentacion/computer-use/HANDOFF_V3_2026-10-09.md`.
4. La primera vez lee también, enteros: `AGENTS.md`, `documentacion/00_IDENTIDAD.md`,
   `documentacion/GOAL_COMPUTER_USE_V3_2026-10-08.md` y `documentacion/computer-use/PROMPT_CIERRE_V3.md` (reglas y plan de
   cierre; este archivo cambia el plazo y la forma de trabajar).
5. Prueba de humo antes de construir nada: `ssh redpc hostname` y, si el notebook está libre,
   `bash scripts/cu_live/batch.sh s01 s03` (s01 debe dar «37 × 12 = 444»).
</arranque>

<limites_duros>
Estos límites no tienen excepción. El hook `.claude/hooks/protect_vscode.py` ya bloquea los comandos que matarían VS Code;
los demás dependen de ti.
- Visual Studio Code nunca se cierra ni se mata: ahí vives tú. El 2026-10-09 se cerró 4–5 veces y la sesión murió; una vez
  fue por agotar los recursos del escritorio con ~20 agentes.
- Nunca reinicies, apagues ni cierres sesión.
- Los envíos de prueba van sólo a Discord (MD «Ron92» o canal «Música»). Ningún clic que cambie la cuenta (iniciar sesión,
  seguir, comprar, instalar) si el objetivo no lo pide.
- VRAM ≤ 4 GB y sin modelo de visión. Idiomas: español, inglés y spanglish.
</limites_duros>

<maquinas>
- Notebook (rednote): sólo ejecuta BAXY: pasadas, bancos, tandas y corridas formales. Mientras corre BAXY aquí, aquí no se
  compila ni se prueba. Cualquier carga falsea las medidas: con carga, el encoder E5 se pasa de su tope de 0,75 s,
  llama-server no carga y los casos tardan 7–9 min.
- redpc (PC principal del dueño: i9-12900HX, 32 GB, RTX 4060 Ti 16 GB): compila, prueba y aloja el trabajo pesado.
  - Se entra con `ssh redpc` (PowerShell 5.1).
  - Repo desnudo `D:\BAXYWork\baxy.git` (remoto `redpc`; empuja con `GIT_LFS_SKIP_PUSH=1`) y clon `D:\BAXYWork\v3`.
  - Puente para subagentes, desde la raíz de un worktree: `bash "$LOCALAPPDATA/BAXY/cu-v3/redpc_run.sh" '<cmd PowerShell>'`.
    Empuja HEAD y los cambios sin commit a `D:\BAXYWork\wt\<rama>` y corre allí con `$PY` (python del runtime).
  - El dueño lo usa mientras trabajas, y eso es una prueba real de molestia: su input real que pare una misión es suya, no
    un fallo de BAXY.
  - No toques su propio checkout del repo en redpc, ni `C:\ProgramData\ssh`, el firewall, `sshd` o la tarea «BAXY sshd
    watchdog».
  - Para trabajos largos en redpc, lánzalos desligados (`Invoke-CimMethod Win32_Process Create`) con log.
</maquinas>

<uso_de_la_cuenta>
La cuenta tiene una ventana de uso de 5 horas. Cuando quede poco, para los subagentes (`TaskStop`) y deja sólo lo que no
gasta, que son las corridas en vivo; tras cada reinicio, úsala entera. Los subagentes cuestan bastante más que tu propio
trabajo: úsalos donde paralelizan de verdad.
</uso_de_la_cuenta>

<diagnostico>
Lo que está mal y obliga a cambiar la forma de arreglar:
- **Se apilaron capas.** Hay más de 24 rondas de reglas sobre el motor de computer use y el redactor. Es justo lo que prohíbe
  la ley 2 de AGENTS.md: «si añades una capa, retira la que sustituye».
- **El síntoma es la regresión.** La latencia del banco pasó de 4,8 s (v2) a 8,5 s, y el banco bajó frente a v2. Cada regla
  nueva arregla un caso y frena o rompe otro.
</diagnostico>

<forma_de_arreglar>
Estas reglas valen para ti y para cada subagente; cópialas en cada encargo. Existen porque el apilamiento ya costó latencia y
casos.
1. **Cada cambio retira lo que sustituye.** Una rama que añade una regla, un veto, un reintento, una espera o un camino
   alternativo quita o fusiona el que reemplaza, y declara en su último commit qué quitó (archivo:función) y su saldo neto de
   reglas y de líneas de `src/`. Un saldo positivo necesita una justificación medida; sin ella, el revisor la devuelve.
2. **Se arregla la causa donde se produce.** Si un dato llega mal (lectura, vista, recibo), se corrige en su origen. Un veto
   nuevo del redactor sólo entra si la causa no tiene arreglo en el origen, y se dice por qué.
3. **Una sola fuente de verdad.** Ninguna regla duplicada en C# y Python ni listas gemelas sin un test que las ate; si ya
   hay dos, se unifican antes de tocar la lógica.
4. **Libro de cuentas por regla.** Antes de tocar reglas del motor o del redactor, mide qué casos gana y pierde cada una
   (última pasada, banco y tandas). La de saldo neto ≤ 0 se borra, y sus tests se reescriben para el comportamiento correcto
   (nunca se debilitan).
5. **El banco y la latencia son compuerta.** Nada pasa a v3 sin una corrida del banco B (sin usuario simulado) juzgada con
   journal. No se fusiona si un caso antes logrado deja de estarlo, si aparece un falso éxito o si la mediana de latencia
   sube más de un 5 %.
6. **Rondas pequeñas y medidas en vivo.** Como mucho 4 ramas por ronda, una causa por rama. Una rama vale cuando mejora la
   medida en vivo, no cuando pasan sus tests. Mide lo fusionado antes de abrir otra ronda.
7. **Simplificar es trabajo válido y prioritario.** Una rama que sólo borra capas redundantes sin bajar casos ni subir la
   latencia va primero.
8. **Arreglos generales y honestos.** Nunca por frase ni por app (los nombres de apps, sólo en datos). Las lecturas de lo que
   dice la persona viven en `src/baxy_mind/semantic/`. Todo argumento nuevo de una operación se declara en
   `ProductCatalog.cs` con test contra el catálogo real. No borres, saltes ni debilites tests; si uno está mal, dilo con la
   evidencia y corrígelo.
</forma_de_arreglar>

<subagentes>
- Usa subagentes (Agent, `run_in_background: true`) para trabajo independiente y grande: una rama de arreglo
  (`isolation: "worktree"`), una revisión adversarial o un lote de 10–20 casos para juzgar. Lo que se resuelve con pocas
  llamadas a herramientas, hazlo tú.
- Como mucho 3–4 subagentes vivos a la vez.
- Cada encargo es completo: objetivo, causa medida con archivo:línea, evidencia (rutas), las reglas de `forma_de_arreglar`,
  la orden de compilar y probar sólo en redpc por el puente, el formato del informe (≤ 250 palabras: rama, sha, qué quitó,
  saldo neto, pruebas con salida exacta) y un límite de tiempo. Los textos de `%LOCALAPPDATA%\BAXY\cu-v3\workflows\*.js`
  sirven de plantilla para encargos de implementador, revisor, verificador y juez.
- Ciclo de una rama: un subagente implementa. Otro, con contexto nuevo, la revisa de forma adversarial: falsos éxitos, actos
  sobre la ventana o los datos de la persona, regresiones del banco, capas sin retirar, tests debilitados. Si encuentra
  bloqueantes, el implementador corrige y un revisor nuevo confirma sólo esos puntos. Tú integras.
- Pide a cada subagente que deje sus resultados largos en ficheros y te devuelva un resumen corto.
</subagentes>

<verificacion>
- Nada se da por hecho sin evidencia: comando y salida, captura, volcado UIA o journal del Core. La frase de BAXY nunca es
  prueba.
- Juzga las pasadas y los bancos con subagentes de sólo lectura, con el encargo de `workflows/v3-verificar-diagnosticar.js`:
  captura, UIA, archivos y el journal del paquete. Los recibos UIA del Core son evidencia independiente. Las tandas se
  juzgan con el encargo de `workflows/v3-juzgar-tandas.js`.
- Los paquetes se arman con `py -3.12 %LOCALAPPDATA%\BAXY\cu-v3\paquete.py <dir> <casos…>`. Para casos corridos antes de
  fusionar el arnés nuevo, genera antes la evidencia del journal con `scripts/cu_live/journal_caso.py <carpeta de evidencia>`.
</verificacion>

<estado_al_empezar>
2026-10-10 ~08:00. Ramas (todas también en el remoto `redpc`):
- **v3** (`fable/cu-universal-v3`, etiqueta `cu-v3-bueno-1` = c31141a51) = rondas 1–23b + **la candidata 24b**
  (24 + 24u + 24b + r25 vetos + r25 contención + el arreglo del foco 44923c0c3), fusionada el 10-10 a las 08:08 por ser
  la mejor medida: banco B 58/72, 0 falsos éxitos, 7,80 s. Pierde frente a r23b s11 e y8: son lo primero que hay que
  mirar. El checkout principal está en v3.
- **`fable/cu-v3-ronda24u`** (e7e54c433) = v3 + ronda 24 (computer use, 8 ramas, más el arnés de verificación con journal)
  + ronda 24u (uso real, 6 ramas) + los arreglos de tres tests que el Full encontró rojos (reloj de m168, dos tests de
  forma del worker que la ronda 21 dejó sin actualizar). Barrido en redpc: Kernel 440/440, Integración 3850/3851, pytest
  24 536/0.
- **`fable/cu-v3-ronda24b`** (b277aa437) = 24u + 6 ramas de la ronda 24b aprobadas tras 2–4 revisiones adversariales.
  Rechazadas, no entran: «búsqueda que lleva» (un sub-objetivo leído como independiente por una lista cerrada de palabras
  correría sin su dato y escribiría en un chat real) y «lo que la pantalla muestra» (falso «no está en este equipo»).
- **`fable/cu-v3-ronda25`** (c7792c2a3; lo que no está en v3: latencia y escribir sin clic previo) = 24b +
  la primera ronda de consolidación, que nació del libro de cuentas y del informe de latencia. Cada rama pasó una
  revisión adversarial con sondas en redpc:
  - vetos desfasados fuera (−24 líneas de src/);
  - resultado y eco sin contención ni errata salvo entrada única, con el gemelo C# igualado, y fuera el «un paso más» de
    stalled (−3);
  - arreglo del foco tras la mirada (+7 −3; sin él volvía un bucle de clics);
  - latencia: la vista recorre el árbol una vez y la bienvenida no bloquea el pedido (+6; vistas idénticas, Do-View −8 %);
  - escribir sin clic previo cuando la vista se lee detrás, y nunca al teclado sin foco probado (+11; espera ganar c1, x5
    e y4). La primera versión tenía 3 bloqueantes graves: texto al foco de una ventana de fondo, y un documento sin
    `value` tomado por vacío, con lo que el documento de Word de la persona habría recibido texto.
  - Barrido en redpc: Kernel 440/440, Integración 3972/3973, pytest 24 712/0. Providers 2102/2102 en el notebook sobre la
    24b.
- **Medido** (banco B sin usuario simulado, jueces independientes con journal; veredictos en `%LOCALAPPDATA%\BAXY\cu-v3\`):
  | corrida | logrados | límite honesto | no logrados | falsos éxitos | mediana de latencia |
  |---|---|---|---|---|---|
  | r23b (v3 actual) | 55/72 | 1 | 15 | 1 (v1) | 8,5 s |
  | 24u (`bancoB_c24u_veredictos.json`) | 56/72 | 1 | 14 | 1 (u5) | 8,52 s, p90 14,6 s |
  | 24b + r25 vetos y contención (`bancoB_c24b_veredictos.json`) | **58/72** | 1 | 13 | **0** | **7,80 s**, p90 12,2 s |
  | ronda 25 completa (`bancoB_c25_veredictos.json`) | 56/72 | 2 | 14 | 0 | 7,84 s, p90 13,7 s |
  - Las cifras ya corrigen c3: los jueces lo dieron por falso éxito, pero la carpeta sí se creaba («FOLDER CREATED» en el
    log del arnés, que después la borra). En una creación de archivos, `reachedState:false` significa «no existía antes».
    El paquete ahora trae `verify_arnes` (con `BANCO_LOG=<log del lote>`) y el encargo del juez lo explica. Hay una rama
    sin revisar que renombra el campo a `alreadyInState` (`fable/cu-v3-r26-creado-solo-si-llego`, 84b2fbb6b): toca el
    contrato del recibo, así que no la fusiones sin revisión y sólo si aporta.
  - v2 cerró con 71/72 y 4,84 s de mediana de misión: casi todo lo que falta son regresiones de v3.
  - **Diagnóstico medido del apilamiento:** `cu-v3/libro_de_cuentas_reglas.md` (862 reglas desde v2, 375 con gemelo
    C#/Python, 438 candidatas a borrar o fusionar, 26 priorizadas con archivo:línea, tests y contracaso) y
    `cu-v3/latencia_v2_v3.md` (de dónde salen los +2–3,7 s y 5 recortes medidos). **Son el punto de partida del sábado.**
  - Pasadas v3 (72 órdenes ciegas en apps nuevas): r18 16/72, r23 21/72, r23c 18/72. Tipos de tarea 3–4/24. WhatsApp/Epic
    3/4. Tandas de uso real t1–t4, ya no ciegas: 88/123 (71,5 %) en el notebook y 92/123 (74,8 %) en redpc.
  - Molestia (banco con usuario simulado, r23): 255 caracteres perdidos (base 3 383), 0 escritos en la ventana de la
    persona, 61 robos de foco (62 s), 52,6 % de ráfagas restauradas.
- **Ensayo del Full sobre v3 (02:24–02:49):** todo verde salvo 2 tests de Providers (ya arreglados en la 24u). Pytest no
  llegó a correr porque el Full para en el primer rojo: el primer Full de verdad está por hacer.
- **Criterios:** los 7 cumplidos de `v3_criterios.json`. Además hay evidencia para el 4a (6/16 → 9/16, en MEDICIONES) y el
  2e (WhatsApp y Epic logrados en r23c): márcalos con su evidencia.
- **Avisos del entorno:**
  - la suite completa de Providers se cuelga por SSH en redpc, porque la sesión no tiene escritorio: córrela en el
    notebook o con filtros y timeout;
  - `LiveCoreExercisesRestorableOperationsTwice` sólo falla por SSH;
  - el caso n6 deja abierto en Word un documento de la persona (en Descargas, sin modificar a las 06:45
    del 10-10): cambia su base a un documento de prueba y comprueba que el de la persona nunca se toca.
</estado_al_empezar>

<herramientas>
- Pasada completa (v3 + tipos + WhatsApp/Epic, ~1,8 min/caso con el notebook libre): `bash "$LOCALAPPDATA/BAXY/cu-v3/pasada.sh" <tag>`.
- Banco: `bash "$LOCALAPPDATA/BAXY/cu-v3/banco.sh" <tag> <1 con usuario simulado | 0 sin él>`.
- Tandas en el notebook: `bash "$LOCALAPPDATA/BAXY/cu-v3/tandas.sh" <tag> t1 t2 t3 t4`.
- Tandas en redpc, en la sesión del dueño:
  - tarea programada «BAXYWork tandas», que corre `D:\BAXYWork\live_tandas.ps1 -Tag X -Tandas t1,t2,t3,t4`;
  - antes, actualiza `D:\BAXYWork\v3` con `D:\BAXYWork\build_v3.ps1` tras empujar v3;
  - después, copia los resultados con `scp redpc:D:/BAXYWork/tandas_<tag>/...`.
- Molestia: `py -3.12 scripts/cu_live/molestia/molestia_sum.py <salida del lote>`. Resúmenes de jueces: `sumj.py` y
  `anal.py` en `%LOCALAPPDATA%\BAXY\cu-v3\`.
- Antes de cada pasada o banco, cierra por PID las apps que dejó la anterior (Excel, Word, Edge, Paint, Calculadora…). El
  arnés no cierra los «documentos ajenos» y entonces marca el caso NO_CORRIO. Si es un documento de la persona en Word, mira
  antes que esté guardada (`Documents.Saved`) y que el archivo no haya cambiado.
- Empaqueta con `BANCO_LOG=<log del lote>` para que el juez vea `verify_arnes`, congela la evidencia
  (`cu-universal-evidencia/v2-<caso>` → `cu-v3/evidencia_<tag>/`) antes de la corrida siguiente y reescribe las rutas del
  paquete (`py -3.12 %LOCALAPPDATA%\BAXY\cu-v3\repath.py <paquete> <ruta vieja> <ruta nueva>`). El juez acepta
  `args.ev` para esa carpeta.
</herramientas>

<plan>
1. **Ahora:**
   - corre en el notebook, sin agentes, el primer Full de verdad sobre v3 (`scripts/test_source_quality.ps1 -Mode Full`);
     arregla sus rojos sin debilitar tests;
   - decide con medida qué entra de la ronda 25 que no está en v3. La rama de latencia quitó la espera tras la bienvenida
     (de 18 a 10 primeros turnos) pero subió la primera lectura (1 193 → 1 672 ms). La rama de escribir ganó c1 y perdió
     y4/y9. En el banco 25, u5 se perdió por un Excel que quedó abierto: ojo con la base. Fusiona en v3 cada rama sola y
     mide el banco B; sólo entra la que mejore;
   - mira s11 (Discord: pulsa el texto del buscador del MD y dice «parece que ya estabas en cotele», un final que no es
     honesto) e y8 («tu biblioteca» leída como documento).
2. **Sábado:** ciclos con las dos máquinas. El notebook corre pasada, banco B y tandas; redpc hace las rondas y las tandas en
   vivo. Orden:
   - (a) consolidación, siguiendo `libro_de_cuentas_reglas.md` (puntos 2 y 6–26 que quedan; la ronda 25 hizo el 1, el 3,
     el 5 y parte del 4) y los recortes 3–5 de `latencia_v2_v3.md`, hasta recuperar la latencia del banco (≤ 5 s);
   - (b) falsos éxitos;
   - (c) regresiones del banco frente a v2;
   - (d) finales que niegan lo logrado, destino mal elegido y listas de la web.

   Barrido completo de pruebas en redpc tras cada integración (`D:\BAXYWork\suites.ps1`).
3. **Congela el domingo hacia las 18:00.** Corridas formales en el notebook, sin subagentes cargándolo (PROMPT_CIERRE_V3 §6):
   - Full sobre v3 hasta verde;
   - vaciar procedimientos del perfil de prueba (`scripts/cu_live/vaciar_procedimientos.py`);
   - pasada final;
   - `desellar_v3h.py` + lote v3h, una sola vez;
   - banco A (`banco.sh A 1`) y banco B (`banco.sh B 0`);
   - tandas selladas b1/b2: comprueba su sha256 y no las leas antes;
   - `audit_procedures.py`;
   - docs (AGENTS.md ≤ 10 000 caracteres);
   - `main` = `origin/main` 50d5c7ed6 (el `main` local, 5f572ee1b, NO vale), fusiones `--no-ff` v3 → `codex/kiro-goal-c03`
     → `main`. Ensayo del 10-10 a las 08:50: v3 comparte el historial saneado de `origin/main` (base 92310260f; `main` sólo
     tiene encima la licencia MIT y `docs/PUBLICACION_Y_DATOS_PRIVADOS.md`) y la fusión sale limpia salvo `.gitignore`
     (quedan las dos partes). Antes del push, lee esa nota y comprueba que v3 no añade evidencia privada: ningún archivo
     de los patrones de su `.gitignore` en el árbol ni en `git log` desde la base. Si apareciera alguno, para y avisa al
     dueño: publicarlo no tiene vuelta atrás;
   - Full sobre main;
   - push de las dos ramas, comprobado con `git ls-remote origin`;
   - informe final publicado como artefacto: cifras reales por criterio, `git diff --stat 50d5c7ed6 -- tests` y
     skip/xfail 18/0 al inicio y al final.
</plan>

<estrategia_de_exito>
El riesgo mayor no es un caso difícil: es llegar al lunes sin cierre formal. Por eso:
1. **El cierre va primero.** El goal se cierra con Full verde sobre `main` fusionado, push comprobado e informe con cifras
   reales, aunque alguna meta numérica no se alcance. Una meta no alcanzada se informa con su cifra y su causa medida; un
   cierre que no llega no se informa con nada.
2. **Un estado bueno conocido, siempre.** Cada vez que una medida de v3 iguala o mejora a la anterior, ponle una etiqueta
   (`git tag cu-v3-bueno-<n>`) y anótala en PROGRESO. Si una integración empeora la medida, vuelve a la etiqueta con un
   revert `--no-ff`, nunca con reset.
3. **Ensaya el cierre el sábado, en redpc.** En una rama desechable, haz la fusión v3 → `codex/kiro-goal-c03` → `main` y
   corre el Full allí (`D:\BAXYWork\suites.ps1` o `scripts/test_source_quality.ps1 -Mode Full`). Los conflictos y los rojos
   que aparezcan son trabajo del sábado, no del domingo por la noche.
4. **Hitos con hora y su plan B:**
   - sábado 12:00: rondas 24/24u/24b en v3 o descartadas, con banco B medido. Plan B: v3 sin ellas.
   - sábado 20:00: consolidación (libro de cuentas, reglas de saldo ≤ 0 borradas) y ensayo del cierre en redpc hecho.
   - domingo 12:00: últimas rondas fusionadas. Lo que no esté medido en vivo a esa hora no entra.
   - domingo 18:00: congelación. Desde aquí sólo corridas formales y arreglos de rojos del Full.
   - lunes 06:00: `main` fusionado, Full verde y push hechos; quedan 4 h de margen para el informe y los imprevistos.
5. **Lo que ya mató sesiones, prevenido:** VS Code cerrado (vigía y hook, pocos agentes en el notebook); disco lleno de
   worktrees de agentes (borra cada uno al fusionar; mira el espacio libre de C: antes de cada ronda); reinicio pendiente de
   Windows Update (compruébalo antes de una corrida larga); batería y GPU (`power_wait.sh` antes de cada trabajo de GPU);
   contexto lleno (estado en el repo, commit frecuente).
6. **Valor por hora.** Elige el trabajo que más sube el banco B o baja los falsos éxitos por hora de trabajo. Los casos
   sueltos y caros (una app concreta sin árbol) van después de las palancas generales.
</estrategia_de_exito>

<cuando_parar_y_cuando_no>
- Sigue sin pararte. Estas no son razones para detenerte:
  - un resumen que anuncia el paso siguiente sin darlo;
  - ofrecer seguir o preguntar «¿sigo?»;
  - listar decisiones que no bloquean;
  - informar porque cumpliste un hito.
- Detente sólo si nada puede avanzar sin el dueño, y dile qué necesitas. Si algo queda bloqueado, anótalo y sigue con lo
  demás.
- Informa al dueño en español, corto, con cifras y con honestidad: si una meta no se alcanza, da la cifra real y su causa
  medida.
- Escribe cada avance en PROGRESO_V3.md con la hora real y mantén el handoff al día (`docs/AI_HANDOFF_TEMPLATE.md`).
</cuando_parar_y_cuando_no>
