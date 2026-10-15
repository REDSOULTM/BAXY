# Goal — computer use v3 y BAXY completo: compañero que no molesta, universal de verdad (2026-10-08)

<objetivo>
Deja el computer use de BAXY (motor `mission.computer.use`) listo como lo pide el dueño:
- un **compañero** que hace sus cosas mientras la persona usa el PC, sin quitarle el mouse, el teclado ni la ventana;
- **universal por diseño**: cualquier app por cómo está hecha, nunca con código por app;
- **encadenado y rápido**, por voz o chat, en español, inglés y spanglish.

Y deja a **BAXY completo funcionando bien en uso real**, no sólo el computer use: entender a la primera, seguir una
corrección, no repetirse y usar la herramienta pedida (punto 9). Cierra los diez puntos de `<tareas>`, del 0 al 9, con las
pruebas de `<cierre>`.

Plazo: **máximo 2 días de reloj** desde que empiezas, y cuanto antes mejor: el tiempo importa. Anota la hora de inicio en
`documentacion/computer-use/PROGRESO_V3.md` y escribe en cada actualización el tiempo transcurrido contra el plazo.
Trabaja con todos los recursos que necesites: lanza los subagentes, workflows y worktrees que quieras, sin límite.
El dueño corre esta sesión en modo bypass y con ultracode.

Por qué importa:
- BAXY es un «compañero tipo Jarvis» (`documentacion/00_IDENTIDAD.md`).
- Si para hacer algo le quita al dueño el mouse o la ventana, falla como compañero aunque complete la tarea.
- Si sólo funciona en las 13 apps donde se midió, no es universal.
</objetivo>

<contexto>
**Lee primero, enteros:**
- `AGENTS.md`. Está desactualizado en tres puntos que debes corregir en el punto 8: dice que la rama de trabajo es `main`, que `fable/computer-use-engine` no está integrada, y cita `GUIA_AGENTES_IA/05_…`, que ya no existe.
- `documentacion/00_IDENTIDAD.md`.
- `documentacion/computer-use/CONTRATO_VISTA_ACCION.md`.
- Las últimas secciones de `documentacion/computer-use/MEDICIONES.md` y `PROGRESO.md`.
- Este goal.

**Estado de partida** (rama `codex/kiro-goal-c03` @ 1334a1ef3, publicada; `main` está atrás):
- Banco final de 72 casos en vivo: 71/72.
- Siete lotes ciegos: 68/75 a la primera.
- Respuesta típica de 4,8 s; misión de 3,1 s.
- pytest 19 254, Integración 2602, Providers 1039.
- Voz final determinista para órdenes simples y para preguntas con un único dato.

Medido en el journal del 2026-10-07, sobre 1 063 actos:
- 305 clics por patrón UIA, que no tocan el input;
- 229 clics por UIA con verificación de superficie (falta confirmar si tocan el input);
- 148 clics por OCR, que mueven el cursor real;
- 374 teclas o textos por SendInput, que exigen la ventana al frente.

**Dónde se toca el input real** (punto de partida del punto 0):
- Foco: `VisibleControlSurface.cs:BringToFront` (líneas 456–469), que se llama desde 84, 127, 186 y 611 de ese mismo archivo, desde `WindowsVisibleControlAdapter.cs` (546, 585, 941) y desde `DesktopKeyboard.cs:FrontAsync` (119). También ponen ventanas al frente:
  - `DesktopMessagingAdapter.cs:Focus` (1495);
  - `WindowsApplicationPlatform.cs:RequestForeground` (259);
  - `WindowsInstalledApplicationOpenProvider.cs:RequestForeground` (1578);
  - `WindowsCalculatorOpenProvider.cs:RequestForeground` (121);
  - `WindowsWindowControlProvider.cs` (1227).
- Cursor: `VisibleControlSurface.cs:Click` (818) y `PointAt` (832), llamados desde `WindowsVisibleOcrLocator.cs:51`, `WindowsVisibleVisionLocator.cs:83` y `WindowsScrollAdapter.cs:110/114`. El último recurso de `DesktopUiaWorker.ps1:Invoke-NamedControl` (167) es `ClickPoint`.
- Teclado: `DesktopKeyboard.cs` (SendInput, 35 ms por carácter) y `DesktopKeyPress.ps1`.
- Las líneas son del 2026-10-07; confírmalas con grep.

**Arnés en vivo:** `scripts/cu_live/` (lee su `README.md`).
- `batch.sh <casos…>` y `cu_live.sh <tag> <turnos> [inactividad]`.
- Utilidades: `jsteps.py` (journal), `dialog.py`, `sumbench.py`, `benchtable.py`, `uia_dump.ps1`, `close_window.ps1`, `clear_notepad.ps1`, `idle.ps1`, `screen.ps1`, `spotify_find.ps1`.
- 127 casos en `cases/`.
- Perfil de banco: `%LOCALAPPDATA%\BAXY\cu-universal-perfil`.
- Evidencia: `%LOCALAPPDATA%\BAXY\cu-universal-evidencia\<tag>\`, con `events.jsonl` (utf-8-sig), `trace.jsonl` (la última corrida va al final), `compose_audit.jsonl` y `after.png`. Si la carpeta tiene `no_corrio.json`, el caso no corrió en ese lote y no se juzga con lo que haya allí (lo de una corrida anterior queda en `anterior/`).
- Journal: `<perfil>\journal\missions.jsonl`, con cada vista y cada recibo.
- `cu_live.sh` espera a que el PC esté inactivo. Eso contradice el punto 0: sustitúyelo por el medidor de molestia.
</contexto>

<reutiliza>
- **Build — los ensayos en vivo usan SIEMPRE Release:**
  - `dotnet build src/Baxy.App -c Release`
  - `dotnet publish src/Baxy.Core -c Release -r win-x64` (también hace falta con cambios en Providers).
  - El 2026-10-07 se perdieron 30 minutos probando un App viejo compilado en Debug.
- **Pruebas:**
  - pytest completo: `PYTHONPATH=<repo>\src C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -X utf8 -m pytest -p no:cacheprovider tests -q` (unos 8 min).
  - Pytest dirigidos de computer use: `tests/test_computer_use*.py`, `tests/test_cu_*.py`, `tests/test_compound_missions.py`, `tests/test_reading_lives_in_semantic.py` (censo: una lectura fuera de `semantic/` necesita una entrada en `scripts/inventory_reading_outside_semantic.py`), `tests/test_censo_voz_visible.py` (la prosa visible va en datos), `tests/test_compose_contract.py`.
  - Archivos con prompts fijados: `tests/test_c03_inventory_output_budget.py` y `tests/test_c03_process_scope_prompt.py`. Nunca cambies el prompt de operaciones que no sean computer use.
  - .NET: `dotnet test tests/Baxy.Integration.Tests -c Release --filter "FullyQualifiedName~ComputerUse|FullyQualifiedName~OperationFloor"` y `tests/Baxy.Providers.Windows.Tests`.
  - Compuerta: `.\scripts\test_source_quality.ps1 -Mode Full`, sola y una vez al final.
- **Lecciones ya pagadas:**
  - Un merge con conflicto en un JSON de datos de prueba se resuelve por unión por id, nunca empalmando texto.
  - Las vistas listan 60 controles: lo que está más allá se busca por nombre.
  - El eco de lo que se tecleó nunca es prueba de nada.
  - Cada regla nueva de llegada necesita su contracaso.
  - Los procedimientos aprendidos de una corrida mala envenenan las siguientes.
  - El modelo 4B se distrae con el contenido de la pantalla. Los finales deterministas (`cu_finals.floor_first`) ganan; el modelo sólo redacta lo que no cabe en una plantilla.
</reutiliza>

<tareas>
0. **Compañero que no molesta (primero y más importante).** El dueño usa el PC mientras BAXY trabaja.
   - **Medidor de molestia** antes de arreglar nada, para tener la línea base. Un «usuario simulado» escribe en su propia ventana (un Bloc de notas de prueba) y mueve el mouse dentro de ella mientras corre cada misión, con un patrón fijo: 2 s escribiendo y 1 s de pausa, para que las pausas existan.
     - Distingue el input del usuario simulado del input real del dueño (Windows marca el input inyectado: `LLKHF_INJECTED`/`LLMHF_INJECTED` en un hook de bajo nivel). Si el dueño está usando el PC, la medición se pausa y no se atribuye nada a BAXY.
     - La ventana del usuario simulado nunca es la «ventana activa» de un caso (el banco no tiene órdenes «cerralo» sobre ella).
     - Se mide:
     - caracteres del usuario perdidos o insertados;
     - teclas de BAXY que cayeron en la ventana del usuario;
     - robos de foco y tiempo con el foco robado;
     - movimientos de su cursor;
     - si al final vuelven a estar al frente su ventana y su cursor.
   - Implementa los cinco arreglos, cada uno general y con pruebas:
     1. **Texto sin teclado:** `ValuePattern.SetValue` o mensajes a la ventana destino (WM_SETTEXT/WM_CHAR al hwnd) sin traerla al frente. Mide qué apps lo aceptan; Chromium y Electron, aparte.
     2. **Clic sin mouse** siempre que exista patrón UIA. El clic por coordenadas queda como último recurso.
     3. **Si no queda otra:** esperar a una pausa del usuario (≥ ~500 ms sin input), actuar en una ráfaga corta y devolverle cursor y ventana exactamente como estaban.
     4. **Abrir apps sin robar el foco:** detrás o minimizadas; al frente sólo si la persona lo pide. Algunas apps (UWP) se activan solas al abrirse por decisión de Windows: cuenta esas activaciones aparte, devuelve el foco al usuario de inmediato e infórmalas.
   - Los actos que no tienen vía UIA (arrastrar y soltar, Shift+F10, texto en apps Electron sin patrón de valor) se califican con la regla de pausa y restauración del arreglo 3, no con «cero».
     5. **La métrica de molestia entra en `<cierre>`** junto al éxito y la latencia, y las pruebas en vivo corren con el usuario simulado activo.
   - La regla nueva de seguridad («teclas y texto sólo a la ventana de la misión», `BindToMissionWindow`) debe seguir valiendo sin traer esa ventana al frente.
1. **Amplitud real.**
   - 15–20 apps nunca usadas en el banco. Algunas: Opera (páginas web; ver reglas), PowerPoint, Outlook o Correo, Teams o Discord en llamada (sin llamar a nadie), el reproductor multimedia, Fotos (edición), el Administrador de tareas sin elevar, Visor de eventos, Mapa de caracteres, Recortes, Grabadora de sonidos, una app de terceros instalada, los diálogos «Guardar como» y «Abrir».
   - Arregla los dos fallos conocidos: en WhatsApp el texto no llega y en Epic la pantalla de carga es larga.
   - Escribe **≥ 60 órdenes ciegas nuevas antes de arreglar nada** (cases/`v3-*`), sin mirar el código de esa app.
   - Al final, un segundo lote de **≥ 30 órdenes nuevas** escrito por un subagente que no vio el repo ni los arreglos (`cases/v3h-*`), corrido una vez y sin arreglos entre medio. Es la prueba de generalización.
2. **Tipos de tarea que faltan:**
   - formularios con varios campos;
   - diálogos de archivos (escribir una ruta y un nombre, confirmar);
   - menú contextual (clic derecho por patrón o Shift+F10) y barras de menú profundas;
   - desplazarse por una lista larga hasta un elemento;
   - arrastrar y soltar;
   - tareas largas de ≥ 5 pasos que el modelo planifica (sigue apoyándote en la lectura determinista de `semantic/missions.py`).
3. **Ventanas sin árbol y botones que son sólo un ícono** (Steam, juegos, lienzos).
   - Saca todo lo posible sin modelo de visión:
     - nombre accesible, HelpText y tooltip por UIA;
     - Chromium/CEF con accesibilidad forzada, si se puede activar sin tocar los datos del dueño;
     - OCR de tooltips, sólo dentro de una pausa del usuario.
   - Mide la cobertura.
   - Investiga y deja medida, con números, la opción de un modelo de visión o de detección de íconos (CPU o VRAM). El límite de VRAM es ≤ 3,8 GB con el 4B (≈ 3,6 GB): no lo excedas. Escribe un informe de decisión para el dueño. Esa decisión es suya y no bloquea el resto.
4. **Procedimientos aprendidos seguros.**
   - Aprender sólo cuando el chequeo se cumplió con prueba fuerte (control seleccionado o llegada verificada; nunca por el texto del modelo ni por un recibo débil).
   - Caducidad.
   - Invalidar un procedimiento cuando se desvía o cuando su llegada no se repite.
   - Ningún texto aprendido se repite fuera de un campo (ya existe; mantenlo).
   - Al final del banco, audita `procedures.v1.json`: **cero procedimientos mal aprendidos**.
5. **«Ya estaba ahí» en ventanas sin árbol.** Hoy Steam ya en la biblioteca se dice como «Parece que ya estabas…» (casos `s12` y `c17` con Steam dejado antes en la biblioteca; el contracaso es `s12` con Steam en la Tienda y un clic que no cambia nada).
   - Pruébalo de forma general: firma de la página de llegada guardada con el procedimiento, o realce visual del elemento de navegación.
   - Con contracaso: un clic que no cambió nada en otra página nunca pasa.
6. **Traducción general de etiquetas.**
   - La tabla de unos 65 pares español/inglés de `semantic/missions.py` no escala.
   - Busca un mecanismo general: el modelo local traduce la etiqueta cuando no hay coincidencia, se cachea, y sólo se usa si el nombre traducido está en la pantalla.
   - Sin enviar frases del dueño a la web.
   - Meta: ≥ 20 etiquetas fuera de la tabla que funcionen en vivo o en pruebas con vistas reales.
7. **Aislamiento de las pruebas.**
   - Antes de cada caso, devuelve las apps de prueba a su estado base: Calculadora en Estándar, buscador de Configuración vacío, buscador de Steam vacío, Explorador en Descargas, Bloc de notas vacío, etc.
   - Usa scripts por estado y nunca por app dentro del producto: esto es arnés.
   - Repite el banco completo dos veces: los resultados deben coincidir (≤ 1 caso de diferencia). «El banco» es la lista fija `scripts/cu_live/cases/BANCO_72.txt`.
8. **Cierre formal.**
   - Corrige `AGENTS.md`.
   - Actualiza `CONTRATO_VISTA_ACCION.md`, `MEDICIONES.md` y `PROGRESO.md`.
   - Fusiona `--no-ff` en `codex/kiro-goal-c03`, luego `codex/kiro-goal-c03` en `main` (resuelve conflictos con cuidado: `main` está atrás), y empuja ambas (el dueño lo autoriza en este goal).
   - Compuerta Full verde en una sola corrida **sobre `main` ya fusionado**.
9. **BAXY completo funciona bien en uso real.** No sólo el computer use: todo lo que la persona escribe en la ventana oficial.
   - Semilla, ocurrió el 2026-10-07 en la ventana real:
     - Pidió «Podrias buscarme en google un top 3 peliculas de suspenso del 2026».
     - BAXY respondió con UNA película («The Eyes, una obra surcoreana…»).
     - Corrigió con «si pero quiero buscar un top 3» y luego con «ok pero lo puedes buscar en google no me importa the ice».
     - BAXY repitió la misma frase las dos veces.
   - Fallan cuatro cosas generales: no respetó la herramienta pedida («en Google» = abrir la búsqueda en el navegador del dueño, o buscar y dar el top pedido); no respetó la cantidad («top 3»); no siguió la corrección; y repitió una respuesta idéntica.
   - Método ya probado en septiembre (memoria `c03-uso-real-tandas`, `c03-uso-real-closing-plan`; informe en `../BAXY-archivo-2026-10-06/artifacts/comprobaciones/C03/USO_REAL_2026-09-23.md`):
     - tandas de mensajes reales nunca vistos, la mitad conversaciones dependientes de 3–6 turnos («sí, dale», «no, en YouTube», «súbele un poco más», correcciones);
     - escritas por un subagente que no vio el código, con variedad de hablantes (chileno, rioplatense, mexicano, España, inglés, spanglish);
     - corridas **en la ventana oficial**: `scripts/run_baxy.ps1 -UiProbe <turnos> -UiCapture <dir>` teclea en el compositor real; el driver de septiembre por WebView2 DevTools no se archivó, así que reconstrúyelo si hace falta;
     - arreglo general, verificación y una tanda nueva.
   - Punto de partida conocido: la última verificación ciega de septiembre quedó en 60–61 %, sin cerrar (memoria `c03-final-verification`). Mide primero la línea base actual.
   - Reglas que el producto ya tiene y deben seguir: lo mal dicho lo arregla BAXY (`c03-owner-ruling-misheard-input`); respuestas cortas tipo Jarvis y latencia ≈ tiempo del modelo (`c03-latency-and-concision-rule`); BAXY ayuda y nunca estorba (`c03-baxy-helps-never-drags`).
</tareas>

<reglas>
- **Visual Studio Code nunca se cierra ni se mata:** ahí vive el agente.
  - Lo primero que haces es instalar un hook `PreToolUse` en `.claude/settings.local.json`. El hook bloquea un comando de Bash o PowerShell sólo cuando lleva a la vez un verbo de cerrar o matar (`Stop-Process`, `taskkill`, `CloseMainWindow`, `WindowPattern…Close`, `kill`) **y** el blanco exacto `Code.exe`, `-Name Code`, `ProcessName -eq 'Code'` o «Visual Studio Code». Nunca bloquea por la palabra «code» suelta (romperías `codex/kiro-goal-c03`). Pruébalo contra `git merge codex/kiro-goal-c03` (debe pasar) y contra `Stop-Process -Name Code` (debe bloquearse).
  - El hook no ve lo que hacen los `.ps1` por dentro ni lo que hace BAXY: los ayudantes y el producto mantienen su propia exclusión de VS Code (proceso protegido en `VisibleControlSurface.cs`, `protected_process` en la mente).
  - Todo ayudante que cierre ventanas exige un título de 4 caracteres o más y excluye Code y Opera.
- **Generalidad:** si una prueba sólo pasa con un caso especial para esa frase o esa app, el arreglo está mal: busca la causa.
  - Prohibido nombrar apps en el código de providers.
  - Las listas de palabras van en `src/baxy_mind/semantic/` o en archivos de datos.
- **Honestidad de las pruebas:**
  - Es inaceptable borrar, saltar (skip o xfail) o debilitar tests para que pasen.
  - Nada de valores fijos ni soluciones que sólo valen para el caso.
  - Si un test está mal, dilo y corrígelo con su razón.
  - Cada éxito en vivo se verifica de forma independiente (captura, UIA o journal), nunca sólo con la frase de BAXY.
- **Riesgo:**
  - RiskPolicy pide confirmación para borrar, enviar, pagar o desinstalar.
  - Ningún clic que cambie la cuenta (seguir, guardar, me gusta, suscribirse, instalar) sin que el objetivo lo pida.
  - Los envíos de prueba van sólo a Discord: el mensaje directo con «Ron92» o el canal «Música». No mandes correos de prueba salvo que el dueño te dé la dirección del buzón de prueba.
  - Si una prueba cambia la cuenta o los datos del dueño, deshazlo y dilo.
  - Lo que queda dentro de las apps (herramienta de Paint, texto en un buscador) no hace falta restaurarlo.
- **PC del dueño:**
  - Nunca reiniciar, apagar ni cerrar sesión.
  - Cerrar sólo lo que abriste, por PID exacto o título exacto, nunca por un nombre corto.
  - Restaurar volumen y brillo.
  - Opera es el navegador del dueño:
    - antes de probar, mira si está abierto;
    - trabaja en pestañas nuevas y ciérralas por título exacto;
    - nunca restaures sesiones encima de una sesión viva.
  - El dueño puede estar usando el PC: tus pruebas no deben tocar su trabajo (precisamente lo que mide el punto 0).
- **Recursos:**
  - VRAM ≤ 3,8 GB, sin otro modelo en la GPU; antes de cualquier trabajo en GPU, comprueba batería y temperatura.
  - Nunca envíes frases ni datos del dueño a la web.
- **Git:**
  - Nunca `git add .`; nunca squash ni rebase; commits pequeños en español.
  - Cada subagente trabaja en su propio worktree y rama `fable/cu-v3-*`; tú fusionas `--no-ff`.
  - Borra cada worktree después de fusionarlo (el disco se llena).
  - Archivos con LF y sin BOM, que `dotnet format` los rechaza.
- **Nunca edites `src/` mientras corre un lote en vivo**, ni corras la suite completa en paralelo con un lote.
</reglas>

<forma_de_trabajo>
- **Al empezar y después de cada compactación**, sin excepción:
  1. lee `documentacion/computer-use/PROGRESO_V3.md`, `documentacion/computer-use/v3_criterios.json` y `git log --oneline -15`;
  2. corre la prueba de humo (`bash scripts/cu_live/batch.sh s01 s03`), salvo que ya esté corriendo un lote en vivo (mira si hay un `Baxy.exe --conductor`);
  3. sigue desde el primer criterio en `false`.
- **Primera hora:**
  - crea `v3_criterios.json` con un criterio por cada línea de `<cierre>`, todos en `false`, con el comando o la evidencia que lo prueba;
  - crea `PROGRESO_V3.md` con la hora de inicio;
  - instala el hook de VS Code;
  - mide la línea base del punto 0 y del punto 1 (lote ciego).
- **Ritmo:**
  - Paraleliza con workflows: auditoría, luego implementadores en worktrees, luego revisión adversarial de cada rama.
  - Fusiona por rondas y verifica cada ronda en vivo.
  - Mientras corre un lote en vivo, los agentes analizan, investigan o escriben, pero no ejecutan suites completas.
- **Encargos a los subagentes:** cada uno lleva el objetivo, las rutas exactas, la evidencia, las reglas que aplican, el formato del informe y un límite de tiempo. Pide resúmenes cortos.
- **Revisión adversarial con contexto nuevo** tras cada ronda, enfocada en:
  - falsos éxitos;
  - seguridad, sobre todo teclas fuera de la ventana de la misión;
  - molestia al usuario;
  - regresiones de lectura.
- **Al terminar cada punto:** marca su criterio con la evidencia (comando y salida, o ruta de la evidencia), haz commit y actualiza `PROGRESO_V3.md` con el tiempo transcurrido.
- **No pares antes de tiempo.** No cuentan como razón para detenerte:
  - un resumen que anuncia el paso siguiente sin darlo;
  - «¿sigo?»;
  - decisiones rutinarias;
  - «buen momento para reportar».

  Detente sólo si nada puede avanzar sin el dueño. Si algo queda bloqueado, dilo y sigue con todo lo demás.
- **Avisos al dueño:** cortos, en español y con cifras (logrado contra medido, latencia, molestia), cada pocas horas.
- **Contexto:** se compacta solo. Guarda el estado en los archivos antes de que eso pase y no frenes por presupuesto.
</forma_de_trabajo>

<cierre>
Todos los criterios de `v3_criterios.json` en `true`, cada uno con evidencia. Si pasan 48 h de reloj y alguno sigue en
`false`, termina de todos modos: fusiona y empuja lo que esté verde y verificado, y el informe final dice cada criterio, cumplido o
no, con su evidencia, su causa medida y lo que falta.
1. **Molestia (punto 0)**, en un banco en vivo con el usuario simulado activo:
   - **0 caracteres perdidos o insertados** en la ventana del usuario y **0 teclas de BAXY** en ella;
   - en apps con árbol de accesibilidad, **0 robos de foco y 0 movimientos de cursor**;
   - en apps sin árbol, cursor y foco sólo dentro de pausas, y restaurados en el 100 % de los casos;
   - la línea base y el resultado final, medidos con el mismo arnés y anotados en `MEDICIONES.md`.
2. **Amplitud (punto 1):**
   - ≥ 15 apps nuevas y ≥ 60 órdenes ciegas escritas antes de los arreglos;
   - primera pasada informada;
   - **≥ 95 % tras los arreglos**, con cero falsos éxitos en la verificación independiente;
   - el lote de generalización (`v3h-*`, ≥ 30 órdenes de un subagente que no vio el repo) en **≥ 90 %** a la primera;
   - WhatsApp y Epic, logrados o con una causa medida y dicha con honestidad.
3. **Tipos de tarea (punto 2):** ≥ 3 casos en vivo por tipo (formulario, diálogo de archivo, menú contextual o de barra, desplazarse hasta un elemento, arrastrar y soltar, tarea de ≥ 5 pasos), con al menos 2 de 3 logrados por tipo.
4. **Sin árbol (punto 3):** cobertura medida antes y después en ≥ 10 órdenes de ≥ 3 apps sin árbol, más el informe de decisión sobre visión con números de VRAM o CPU, latencia y precisión.
5. **Procedimientos (punto 4):** pruebas de aprendizaje con evidencia fuerte, caducidad e invalidación, y **0 procedimientos mal aprendidos** en la auditoría tras el banco final.
6. **«Ya estaba ahí» (punto 5):** s12 y c17, con Steam ya en la biblioteca, pasan; y su contracaso no pasa.
7. **Traducción (punto 6):** ≥ 20 etiquetas fuera de la tabla, funcionando y probadas.
8. **Aislamiento (punto 7):** dos corridas completas del banco con ≤ 1 caso de diferencia.
9. **Sin regresiones:** el banco de `BANCO_72.txt` sigue en ≥ 71/72, con latencia mediana ≤ 5 s por orden (medida sin el usuario simulado; con él, la espera de pausas se informa aparte).
10. **BAXY completo (punto 9):**
    - la conversación semilla («top 3 en Google») resuelta;
    - ≥ 4 tandas nuevas en la ventana oficial (≥ 25 mensajes cada una, la mitad conversaciones dependientes) con arreglos y verificación;
    - dos tandas ciegas finales, corridas una vez y sin arreglos entre medio, en **≥ 90 %** de turnos bien hechos (según 00_IDENTIDAD: entendido, herramienta correcta, sin inventar);
    - cero respuestas idénticas repetidas tras una corrección;
    - mediana ≤ 5 s en lo fácil.
11. **Cierre (punto 8):**
    - compuerta Full verde en una sola corrida sobre `main` fusionado;
    - `AGENTS.md`, el contrato, `MEDICIONES.md` y `PROGRESO.md` al día;
    - fusionado y empujado a `codex/kiro-goal-c03` y a `main`, comprobado con `git ls-remote`;
    - informe final al dueño: resultado primero, con cifras; luego lo pendiente y lo que necesita de él. Incluye la salida de `git diff --stat <commit de main al empezar> -- tests` y el número de `skip`/`xfail` en `tests/` al inicio y al final, para mostrar que no se debilitó ninguna prueba (anota el commit de `main` al empezar en `PROGRESO_V3.md`).
</cierre>
