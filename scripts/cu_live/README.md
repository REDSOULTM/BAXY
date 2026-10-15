# Arnés en vivo de computer use

Corre misiones reales en la App (`Baxy.exe --conductor`, el mismo turno que la UI) sobre el PC del dueño y deja
evidencia fuera del repo, en `%LOCALAPPDATA%\BAXY\cu-universal-evidencia\v2-<caso>\`. Allí quedan:
- `events.jsonl` (utf-8-sig): pedido y final;
- `trace.jsonl`: etapas `computer_use.*`, con la última corrida al final del archivo;
- `compose_audit.jsonl`: borradores, vetos y hechos;
- `after.png`: la pantalla al final, después de devolverle el frente a la persona (puede mostrar su ventana encima);
- `after-mision.png` y `after-mision.json`: la última ventana que BAXY tocó (o la pantalla), tomada por
  `captura_mision.ps1` con PrintWindow al terminar el conductor y ANTES de devolver el frente, sin foco ni input;
- `journal-caso.json`: las entradas del journal del perfil de esta corrida (`journal_caso.py`): vistas
  `input.visible.controls` y recibos de clic, tecla y tipeo con su estado observado, recortados. Son lecturas UIA del
  Core, no la frase de BAXY; `tocadas` lista las ventanas de primer nivel que leyó o en que actuó, la última primero.
  Cada vista trae `destacados` por informatividad (con `destacados_omitidos`), desde la segunda vista de una raíz sus
  `cambios` (nombre, estado o valor, lo que apareció y desapareció, el foco) y, si la ventana no tiene árbol (CEF),
  `texto_arriba` y `marcas_arriba` (OCR y tinta de la banda superior). Ronda 24b, banco r23.

El perfil de prueba es `%LOCALAPPDATA%\BAXY\cu-universal-perfil`. Allí está:
- `journal/missions.jsonl`: cada vista y cada recibo de clic o tecla. Al pasar 48 MiB el Core lo sella como
  `missions.<n>.jsonl` y empieza otro; conserva los 2 sellados más nuevos, que enlaza `missions.jsonl.segments`
  (`documentacion/computer-use/JOURNAL_ROTACION.md`). El arnés ya no necesita mover el journal: si lo mueve, el Core
  lo toma como un reinicio y sigue numerando por encima de los sellados que queden.

## Antes de correr

- Compilar en **Release**, porque el conductor usa el layout Release:
  - `dotnet build src/Baxy.App -c Release`
  - `dotnet publish src/Baxy.Core -c Release -r win-x64`. Un cambio en `src/Baxy.Providers.Windows` necesita también este publish de Core.
- No editar `src/` mientras corre un lote: la mente lee `src/` al arrancar cada caso.
- Nunca correr la suite completa ni la compuerta Full en paralelo con un lote, porque deja a la mente sin CPU.

## Turno con los agentes

El escritorio es uno: un lote (`lote.sh`) y los agentes que prueban en vivo se turnan con `turno.sh`, en
`%LOCALAPPDATA%\BAXY\cu-v3`. Cada lado **anuncia primero y mira después**; si mirara antes de anunciar, los dos verían
el escritorio libre en el mismo instante y correrían a la vez.

- **Agente:** `bash scripts/cu_live/turno.sh tomar <nombre> [segundos]` crea PRIMERO `agent-<nombre>.lock` y LUEGO
  espera a que no exista `live.lock` y a que ningún otro agente tenga el escritorio (`agentes.d`, que `mkdir` da a uno
  solo). Sale con 0 cuando tiene el turno y con 3 si sigue en cola (el lock queda puesto: se vuelve a llamar igual).
  Al terminar, o si se rinde, `bash scripts/cu_live/turno.sh soltar <nombre>`. Nunca se crean ni se borran los locks a
  mano, y nunca se corre `batch.sh` ni un `*LiveDesktopCheck` sin el turno.
- **Lote:** antes de cada caso espera a que no haya `agent-*.lock` vivo, escribe `live.lock` y vuelve a mirar: si un
  agente se anunció entretanto (vio el escritorio libre), borra `live.lock` y le cede el turno. Lo suelta al terminar
  el caso; un agente en cola toma el escritorio en ese hueco y el caso siguiente espera a que lo suelte.
- Un `agent-*.lock` sin tocar en `CU_TURNO_VIEJO_MIN` minutos (30) es de un agente muerto: el lote lo avisa y no lo
  espera. El agente en cola lo renueva en cada mirada; una prueba suya de más de 30 minutos llama otra vez a `tomar`.

## Uso

```bash
bash scripts/cu_live/batch.sh s01 s03 c5        # casos de cases/<id>.turns, uno por turno de conversación
bash scripts/cu_live/cu_live.sh mi-tag cases/demo.turns 5   # una sesión con varios turnos
py -3.12 scripts/cu_live/sumbench.py scripts/cu_live/logs/../<salida del lote>   # resumen caso | latencias | fin | final
py -3.12 scripts/cu_live/jsteps.py 60           # las últimas 60 operaciones del journal
py -3.12 scripts/cu_live/dialog.py <evidencia>/events.jsonl
```

### Latencia en frío y «tras la bienvenida» (`CU_TRAS_BIENVENIDA`)

Cada caso arranca la App. Por defecto (`CU_TRAS_BIENVENIDA=0`) el conductor envía el primer turno en cuanto la mente
está lista: es la latencia de **arranque en frío**, con la bienvenida quizá todavía en el carril de la mente. Con
`CU_TRAS_BIENVENIDA=1` `cu_live.sh` pasa `-AfterWelcome` a `run_baxy_conductor.ps1` (argumento `--after-welcome` del
modo conductor) y el primer turno espera a que los mensajes del arranque (la bienvenida) estén compuestos y publicados,
como lo enviaría quien la leyó; es la cifra comparable con el banco de v2. Es sólo medida: no cambia el producto ni el
uso normal. La línea `runtime` de `events.jsonl` deja dicho con cuál se corrió (`afterWelcome`) y si la bienvenida
llegó a publicarse antes del tope de 30 s (`welcomeSettled`; `false` = se envió igual). Se da siempre junto a la cifra
en frío, nunca en su lugar.

```bash
CU_TRAS_BIENVENIDA=1 bash scripts/cu_live/batch.sh s01 s03 c5
```

`batch.sh` cierra sólo lo que abrió cada caso con el **libro del lote** (`libro_lote.ps1`):

- **Falla cerrado.** `registro_dueno.py` registra el input del dueño (todo lo que no lleva la marca del simulador ni
  la de BAXY; lo inyectado sin marca, como Synergy, cuenta como del dueño) y los procesos nacidos, desde antes de la
  primera foto hasta después del último cierre: `lote.sh` arranca uno para todo el lote, `batch.sh` solo el suyo y
  `tanda.ps1` el suyo (`CU_REGISTRO`). Donde el registro no cubre, el dueño cuenta como activo.
- `lote.sh` toma al empezar la foto de todo lo abierto (`CU_LIBRO`): es del dueño y no se toca. Cada caso toma su
  propia foto antes de los estados; al terminar, `libro_lote.ps1 -Cerrar` cierra por PID exacto lo nacido durante el
  caso con **procedencia positiva**: desciende del arnés o de BAXY, o lo lanzó el shell (explorer, sihost, DcomLaunch)
  con el registro cubriendo los 3 s previos sin input del dueño. Lo demás (un actualizador de una app del dueño, la
  terminal de un agente) sólo se avisa (`sin_procedencia`). Windows Terminal y la app de Claude nunca los cierra el
  libro. Lo cierra y lo relee: si sobrevive algo, `verificado=false`.
- Office sale por COM `Quit` sólo si todos sus documentos son del arnés (en `baxy-prueba-v3` o creados por
  `documento_en_blanco`); otro proceso, sólo si el dueño no dio input en toda su vida. Una ventana nueva en un
  proceso del dueño sólo se cierra por ventana, con el registro cubriendo el caso entero sin input, y sólo en un
  proceso donde BAXY trabajó durante el caso según su diario de misiones (`CU_JOURNAL` o `-Journal`); un recordatorio,
  una llamada entrante o un aviso de actualización que la app abrió sola se avisa (`ventana_nueva_sin_baxy`) y no se
  toca.
- Las pestañas nuevas del navegador del dueño sólo se avisan (huellas de los títulos, nunca los títulos).
- Las pestañas del Bloc de notas nacidas en el caso se apartan a `cu-estado	abstate-respaldo` sólo con el mismo
  registro completo y sin input.
- Los procesos del lote que un caso no pudo cerrar quedan en `procesos_lote`: se reintentan, los estados los cierran
  en vez de llamarlos «ajenos» sólo si cada ventana es del arnés o probada del lote (`ventanas_lote`), y el barrido
  final de `lote.sh` cierra sólo esos procesos (nunca una ventana ni una pestaña).
- `lote.sh` ordena los casos con `orden_lote.py` (`CU_ORDEN=0` lo apaga): apps juntas, «cerrada» antes que
  «abierta», productor antes que consumidor (`casos.json` «requiere»), apps elevadas o tras una pantalla de cuenta al
  final y Edge aparte.
- `casos.json` «requiere»: si falta lo que el caso necesita, `base.ps1` da `no_corrio:estado_ausente` y el caso no
  corre (no cuenta contra BAXY). Que el productor corrió lo prueba `logs/v2-<id>.hecho`, que `batch.sh` escribe
  sólo después de su misión (con el código del conductor; un juez puede añadirle `"veredicto":"exito"|"fallo"`),
  nunca su foto; sin veredicto ni «comprueba», el caso corre marcado `productor_sin_verificar`. «precondicion»: si una preferencia del dueño ya cumple la orden, se invierte sólo
  con un estado reversible y se devuelve tras el caso (`base.ps1 -Devolver`); si no, el caso es la variante
  «ya estaba».
- `scripts/uso_real/tanda.ps1` usa el mismo libro alrededor de cada tanda.
`close_window.ps1 -Title <exacto> (-Antes "h1 h2" | -Libro <foto>)` cierra sólo ventanas con ese título exacto que
no estaban antes del caso; exige un título de 4 o más caracteres y nunca cierra Visual Studio Code, Opera, Windows
Terminal ni la app de Claude. `batch.sh` ya no cierra nada por título. `clear_notepad.ps1 <pid>` sólo toca las
ventanas de ese Bloc de notas que están en `propios.jsonl`, y en ellas sólo vacía pestañas sin título hechas de
textos de prueba (`textos_de_prueba.json`); una ventana con otro texto queda abierta.
- Un caso que no pudo correr por la infraestructura se repite hasta 3 veces: otro BAXY abierto, la GPU ocupada,
  `runtime_not_ready`, o el decisor no disponible con el turno sin final (`repetir.py`: `decision_unavailable` +
  `no_response` en el mismo turno). Un turno sin final con el decisor respondiendo es un silencio de BAXY y cuenta. La
  corrida repetida queda como `events.repetido-<n>.jsonl`. Si los turnos ya corrieron (decisor, Core), antes de
  repetir se cierra lo que abrió el intento y se vuelven a aplicar los estados base (`limpiar_caso`, `preparar_caso`);
  si no queda limpio, el caso es `NO_CORRIO` y no deja marca `.hecho`.
- Las ventanas de apps empaquetadas (Configuración, Calculadora, Reloj…) se listan y cierran por HWND exacto
  (`marcos.ps1`): `ApplicationFrameHost` es un solo proceso y su `MainWindowTitle` nombra sólo uno de sus marcos. Un
  marco que el caso no pudo cerrar queda en `logs/marcos-pendientes.txt` y se reintenta antes del caso siguiente.
  `ApplicationFrameHost` es un proceso de la persona: un marco nuevo se cierra sólo con la regla del libro para una
  ventana nueva en un proceso suyo (registro del dueño sobre todo el caso, sin input); si no, queda en `sin_tocar`.
- **Sobrecoste entre casos.** Las utilidades de `batch.sh` (libro, marcos, estados, verificador, exploradores,
  captura) corren en un solo PowerShell persistente (`servidor_ps.ps1`, vía `ps` de `servidor_ps.sh`), no en un
  `powershell` nuevo por llamada; `CU_SERVIDOR_PS=0` vuelve a uno por llamada, y un servidor que no responde se para
  y el lote sigue así. Las listas de ventanas saltan una ventana colgada (`IsHungAppWindow`) antes de leer su nombre:
  un Monitor de recursos colgado hacía esperar 10 s cada lista. Cada caso termina con una línea
  `tiempos: caso= conductor= arnes= | paso=s …` (2026-10-08, caso con Mapa de caracteres y conductor simulado:
  arnés 38,3 s → 22,5 s; con la ventana colgada, el libro pasaba de 34 s a 2 s y el verificador de 13,5 s a 1-2 s).
- **Tope de cada llamada del arnés** (2026-10-09, t-menu-1: «--- verify» esperó 11 min a un `explorer.exe`
  secundario colgado tras un diálogo de error de aplicación, con el lote parado hasta matarlo a mano). Toda llamada `ps`
  tiene un tope: `CU_PS_TOPE` segundos (300) y `verificar.ps1` el suyo, `CU_TOPE_VERIFY` (60). Al vencer, la llamada
  imprime una línea `"resultado":"sin_respuesta","verificado":false`, el lote dice `AVISO: <script> sin respuesta`,
  el servidor se para por su PID exacto y la próxima llamada desde el shell del lote arranca otro (hasta 5); sin
  servidor, el `powershell` de la llamada corre bajo `timeout`. Si el que vence es verify, el lote escribe
  `AVISO: verify sin respuesta (<ventanas colgadas>)` y `colgadas.ps1 -Incompleta` deja `verificacion-<fase>.json`
  con `completa=false`, `motivo=sin_respuesta` y las ventanas colgadas; el caso sigue. `verificar.ps1` escribe
  `completa=false, motivo=en_curso` al empezar, así que un corte nunca deja leer como completa ni la de una corrida
  anterior. Una ventana cuyo programa no responde (`IsHungAppWindow` o un `WM_NULL` sin respuesta en 0,5 s,
  `Get-VentanasColgadas` de `comun.ps1`) no se lee por UIA ni por COM: verify la lista en `colgadas` (título sólo si
  su proceso nació en el caso o está en `baxy-prueba*`) y marca la verificación incompleta si es de la app del caso,
  del Explorador o nacida en el caso; las ventanas del Shell se leen sólo donde su `explorer.exe` contestó una lectura
  con tope (`Get-IndicesShellQueResponden`). `libro_lote.ps1 -Cerrar` detiene por PID exacto un proceso colgado nacido
  en el caso con procedencia del lote (`Get-DecisionColgado`; lo informa como `colgado:<proceso>:<pid>:detenido:
  procedencia=…`), nunca el `explorer.exe` del shell (el de la barra de tareas), VS Code, Opera, terminales, la app de
  Claude, BAXY ni otro host del shell; uno que no sea el Explorador pide además al dueño quieto en toda su vida.
- **Libro y estados sin WMI ni el registro entero** (2026-10-09; pasada r15b: `libro_cerrar` mediana 14,6 s, p90 53 s,
  creciendo con el lote). El registro del dueño de un lote largo lleva ~55 000 procesos (4 MB): cada lectura corta su
  lista `procesos` antes de parsear (2,8 s → 0,3 s) y sólo `libro_lote.ps1 -Cerrar` la pide (`-ConProcesos`), como
  índice pid → filas para la procedencia, que antes recorría la tabla entera por cada padre (~4 s por proceso nuevo).
  La lista de procesos y el nacimiento de uno salen de una foto del kernel con la misma clave `pid:ticks` que CIM
  (2-3 s y ~2 s por llamada con WMI; `CU_PROCESOS_CIM=1` vuelve a CIM), y el pid de DcomLaunch del administrador de
  servicios. Libro `-Cerrar -Seco` con una foto vieja y el registro de r15b: 573 s → 7 s, mismas decisiones.

## Medidor de molestia (`molestia/`)

`cu_live.sh` ya no espera a que el PC quede inactivo: espera una pausa breve (2 s, tercer argumento) del input
**real** del dueño y, con `CU_MOLESTIA=1` (defecto), arranca `molestia/medidor.py`. Con `CU_MOLESTIA=0` sólo espera
esa pausa (medir latencia sin usuario simulado).

- Un usuario simulado escribe en su ventana «BAXY usuario simulado» (un EDIT Win32 abajo a la izquierda, nunca un
  Bloc de notas): 2 s a 8 car/s + 1 s de pausa, y mueve el ratón dentro de ella mientras escribe.
- Ganchos de bajo nivel: input no inyectado = dueño (pausa la atribución durante su actividad + 1 s; el caso queda
  «dueño activo» y fuera del total; del dueño sólo se guardan instantes). Marca `SIMU` = simulador (si su ventana no
  está delante, el gancho se traga la tecla y cuenta como perdida). Marca `BAXY` (0x42415859) o ninguna = BAXY/ajeno.
- Primer plano por `SetWinEventHook`; `SetCursorPos` por sondeo de 10 ms. Cada acto ajeno se marca «en pausa» si
  nadie dio input en los 400 ms previos; una ráfaga de foco/cursor queda «restaurada» si, antes de que el simulador
  vuelva a teclear, su ventana está delante y el cursor en su sitio.
- Ronda 3 del medidor (diagnóstico r4a):
  - el simulador anota cada punto **antes** de `SendInput`; un anotado explica un solo salto durante 1,5 s (con la
    máquina cargada el gancho llegaba tarde y el sondeo contaba su propia elipse como saltos ajenos);
  - la vuelta del cursor a la posición del usuario tras un salto ajeno es **restauración**, no movimiento
    (`cursor_vueltas_restauradas`). Una ráfaga evaluada sin restaurar queda `restaurada_tarde` con `retraso_ms` si
    frente y cursor vuelven después sin que el simulador los recupere (`rafagas_restauradas_tarde`,
    `retrasos_restauracion_tarde_ms`). Si el dueño dio input real desde que empezó la ráfaga (devolvió el cursor a
    mano, clicó su ventana) la vuelta no se acredita a BAXY: `rafagas_recuperadas_por_dueno`, y un salto que explica
    un movimiento real del dueño nunca es «vuelta»;
  - la tecla 0xB9 sin marca lleva fuente `uia` (la inyecta UIAutomationCore en nombre de BAXY): sigue en
    `teclas_baxy_en_ventana_usuario` y además en `teclas_uia`;
  - un aviso de primer plano cuya ventana no está delante es transitorio y nunca robo: `primer_plano_sin_frente`
    (Windows avisa aunque niegue `SetForegroundWindow`) y `primer_plano_aviso_tardio` (el aviso llegó encolado).
- La medición va desde la línea `runtime` de `events.jsonl` (justo antes del primer turno; el arranque de la App no
  cuenta y la ventana del usuario recupera el frente) hasta la parada + 2 s. Al final: 1 s de espera, comprobación
  de ventana y cursor, texto del EDIT contra lo entregado (difflib) y `<evidencia>/molestia.json` con la línea `resumen`.
- Aviso: Synergy/Deskflow/Sunshine(Vibepollo)/Moonlight inyectan input sin marca; si corren, el resumen lo dice.

```bash
py -3.12 scripts/cu_live/molestia/autoprueba.py             # sin BAXY: limpia, carga, fuera, pausa, tarde
py -3.12 scripts/cu_live/molestia/molestia_sum.py <salida de batch.sh | ids | molestia.json>   # agregado del lote
```

## Estado base antes de cada caso (`estado/`)

Antes de cada caso, `batch.sh` corre `estado/base.ps1 -Caso <id>`, que aplica en orden los estados que
`estado/casos.json` lista para ese caso. Si el caso no figura, no se toca nada. Cada estado:
- es un script propio, `estado/<estado>.ps1`;
- imprime una línea JSON (`estado`, `resultado`, `verificado`, …) después de leer el estado de vuelta;
- guarda esas líneas en `logs/v2-<id>.estado.jsonl`.

Antes de los estados del caso corre `sin_restos` y después `sin_obstaculos`. Si alguna línea trae
`"verificado":false`, el lote avisa, repara una vez (restos, estados y obstáculos otra vez) y, si sigue sin verificar,
el caso es `NO_CORRIO: <id> estado base sin verificar tras repararlo: <estados>`: no corre, no cuenta contra BAXY, no
deja `.hecho` y se cierra lo que abrieron sus estados (`CU_ESTADO_ESTRICTO=0` lo corre igual, con el aviso). Una
ventana siempre encima que el arnés no puede cerrar (el Teclado en pantalla) sale en `sin_obstaculos` como obstáculo
del caso (`encima`). Una ventana elevada sólo se cierra si el libro del lote o el del arnés prueban que la abrió el lote
o el arnés (Taskmgr o una consola MMC que BAXY abrió en un caso): primero un cierre normal y, si sigue viva, por su PID,
ambos con `taskkill` elevado y sólo donde UAC eleva sin preguntar (`ConsentPromptBehaviorAdmin=0`). Nunca una ventana
elevada de otro (una terminal de administrador de la persona, un instalador, las herramientas de otro agente), ni
terminales, intérpretes, VS Code o la app de Claude; con UAC apagado no se cierra ninguna (el arnés ya las lee). La que
no se puede cerrar queda en `elevadas_quedan` y el caso es obstruido.

Un caso que no corre (`NO_CORRIO`) deja `evidencias/v2-<id>/no_corrio.json` (motivo, hora) y aparta lo que había de
una corrida anterior a `anterior/`, que se reemplaza en cada caso no corrido (sólo la última). El juez y quien lea las
evidencias deben mirar `no_corrio.json` antes que `after.png` o `trace.jsonl`: si está, no hay corrida de este lote.

**Libro de procesos del arnés** (`%LOCALAPPDATA%\BAXY\cu-estado\procesos_arnes.jsonl`, más `documentos.jsonl`): el
libro de un lote sólo conoce su lote, así que lo que un lote o una tanda anterior no pudo cerrar entraba en la foto del
siguiente como «del dueño» (ronda 7: un Reloj delante de v3-01..04, OneNote en la vista Archivo bajo v3-08..10, Word
con su aviso de guardar bajo t-form-4). Ahora `libro_lote.ps1 -Cerrar` anota cada proceso que probó del lote
(procedencia positiva) con sus ventanas, y `app_abierta`/`documento_en_blanco` cada proceso que lanzaron; la clave es
`pid:inicio`, así que un pid reutilizado nunca nombra un proceso de la persona. `sin_restos` cierra antes de cada caso
los procesos vivos del libro: Office con `Stop-ProcesoDelLote` (cancela el aviso de guardar que dejó un caso y sale por
COM sólo si todos sus documentos son del arnés; si COM no da nada legible —medido: Word con un documento de
propiedades vacías, PowerPoint con cero presentaciones y su ventana en pantalla— se detiene por PID exacto sólo si cada
ventana con título nombra un documento que un estado creó en ese mismo proceso); otro proceso sólo por cierre normal de
sus ventanas y sólo si cada ventana que muestra está anotada para él (una ventana sin anotar puede ser de la persona:
`no_cierra:ventanas_nuevas`), nunca con `Stop-Process`. Nunca VS Code, Opera, terminales, la app de Claude, BAXY,
hosts del shell ni intérpretes del arnés. `sin_restos:seco` dice lo que haría. Lo que estaba abierto antes de este libro y nadie probó del arnés no
se toca: se informa.

**Registro del dueño:** si los ganchos de bajo nivel pierden input (Windows los quita a un proceso lento: la ronda 7
rompía cada registro a los 2-10 min y desde ahí el dueño contaba como activo en todo), el tramo no visto cuenta como
input del dueño, queda en `cortes` y los ganchos se vuelven a poner.

```bash
powershell -File scripts/cu_live/estado/base.ps1 -Caso s12          # los estados del caso
powershell -File scripts/cu_live/estado/base.ps1 -Estados calc_estandar,bloc_vacio
powershell -File scripts/cu_live/estado/base.ps1 -Lista             # los estados que existen
bash scripts/cu_live/batch.sh s12 s12@tienda c17                    # id@variante: mismo .turns, otro estado de partida
CU_SIN_ESTADO=1 bash scripts/cu_live/batch.sh s01                   # sin estado base
```

| Estado | Qué deja | Cómo |
|---|---|---|
| `calc_estandar` | Calculadora en Estándar, en grados (DEG) y con la pantalla en 0 | La Calculadora guarda el modo al cerrarse. Si está cerrada, la abre, la arregla y la cierra. Una abierta sólo se arregla si es del arnés (`propios.jsonl` o probada del lote); la del dueño no se toca (`ajena_abierta`). Usa SelectionItem e Invoke. |
| `config_busqueda_vacia` | Buscador de Configuración vacío | ValuePattern. Una Configuración cerrada ya abre vacía y no se abre. |
| `config_inicio` | Configuración en Inicio | SelectionItem sobre el primer elemento de la navegación. Si está cerrada, no se abre. |
| `reloj_por_defecto` | Reloj en Temporizador, la pestaña en que abre (medido) | SelectionItem. Si está cerrado, no se abre. |
| `explorador_descargas` / `explorador_este_equipo` | Una ventana propia del arnés del Explorador en ese lugar | Se abre con `explorer /n` y se mueve con `Navigate2`, sin foco. Su HWND queda en `%LOCALAPPDATA%\BAXY\cu-estado\propios.jsonl`. |
| `bloc_vacio` | El próximo Bloc de notas abre sin textos de prueba | Las pestañas de TabState se miden por tamaño. Se vacían sólo las pestañas sin título cuyo texto entero sale de `textos_de_prueba.json`. Un Bloc de notas ya abierto no se toca. |
| `paint_base` | Paint sin cambios sin guardar | Sólo lee. Paint abierto no se cierra. |
| `steam_biblioteca` / `steam_tienda` | Steam en esa página | `steam://open/games` y `steam://store`. La página se lee con PrintWindow y OCR local: la pestaña elegida es la azul. |
| `discord_md:<nombre>` | Discord en el MD con esa persona (s11, s13, c7: `discord_md:Ron92`), para que «andá al canal Cotele» siempre navegue | Sólo patrones UIA de navegación: el elemento «Mensajes directos» de la lista de servidores y el enlace «<nombre> (mensaje directo)». Nada se escribe ni se envía; un canal de voz nunca se invoca. Discord nunca se abre (`discord_no_abierto`). Se lee de vuelta por el título `@<nombre> - Discord` y el documento `@<nombre>`, y el foco vuelve a quien lo tenía. |
| `discord_busqueda_vacia` | Discord sin restos en sus dos buscadores: el de mensajes del chat a la vista vacío (y su panel de resultados cerrado) y el selector «Cambio Rápido» cerrado (s11, s13, c7 tras `discord_md`; s14 y c6 solo) | El botón propio «Borrar» por Invoke cierra los resultados pero deja las palabras (medido 2026-10-10), así que después el cuadro (ComboBox «Buscar <chat>», nunca el compositor) se pone en vacío por ValuePattern. El selector y un desplegable abierto no tienen patrón: un solo Escape, sólo tras leerlos abiertos y con la ventana exacta de Discord delante (`Send-EscapeEnFrente`). No cambia de chat, no escribe ni envía. Se lee de vuelta el valor del cuadro, que no queda el botón ni el selector; otros diálogos van en `dialogos`. |
| `spotify_inicio` | Spotify en Inicio, con el buscador de arriba vacío, «Tu biblioteca» plegada y ningún menú abierto (u1, u9, v8, x7, y8, c22, d9, z7) | El cuadro se vacía con su botón «Borrar campo de búsqueda» por Invoke y, si sigue con texto, poniéndole el vacío por ValuePattern (esto último sin medir en vivo; medido 2026-10-10: ir a Inicio solo no vacía un texto puesto por ValuePattern); después Invoke sobre «Inicio» y sobre «Comprimir Tu biblioteca». Plegada porque así abría en v2 (120 de 141 primeras lecturas) y así «andá a tu biblioteca» tiene algo que hacer. Un menú que siga abierto: un solo Escape con Spotify delante. Nunca un botón de canción, playlist o perfil: no reproduce, no pausa, no toca la cuenta. Spotify no se abre: cerrado da `ok` con `ventana=cerrada` (abre en Inicio); sin ventana, `spotify_sin_ventana`. Se lee de vuelta el título oculto «Inicio» de la vista, el valor del cuadro y cuál de los dos botones de la biblioteca está. |
| `steam_busqueda_vacia` | Buscador de la biblioteca de Steam vacío | `steam://open/games` lo vacía sin teclear. Deja Steam en la Biblioteca. |
| `fixtures_prueba_v3` | `Documentos\baxy-prueba-v3` con `notas.txt`, `lista.txt`, `foto.png` (64×48), `paisaje.jpg` (1920×1080), `prueba.png` (300×200), `prueba.zip` (3 archivos) y `archivo/` vacía | Todo se genera en el script, nunca se copia de datos del dueño. Un fixture vale por su contenido exacto (los bytes que el generador da en memoria; el texto de cada entrada del zip), no por su tamaño, y uno válido no se reescribe (los casos miran su fecha). Dentro de la carpeta borra sólo fixtures, nombres `baxy-*`, salidas de casos v3 (`proyecto-final.pptx`, `captura-v3.png`) y copias de un fixture (`prueba (1).png`). Lo demás lo informa como `ajenos`. |
| `documentos_sin_baxy_prueba` | No existe `Documentos\baxy-prueba` (c3) | La borra sólo si está vacía. |
| `app_abierta:<nombre del menú Inicio>` | Esa app recién abierta por el arnés | `shell:AppsFolder\<AppID>`; espera la ventana y devuelve el foco. Cierra antes la copia que abrió el arnés; una copia de la persona no se toca (`ajena_abierta`). Sólo toma como de la app una ventana cuyo proceso lo prueba la entrada del menú Inicio (AppUserModelID de una app empaquetada, ejecutable destino del acceso directo, programa asociado a un `.msc`), nunca por el título; sin prueba responde `sin_identidad`. Aprende el proceso en `cu-estado\apps.json`. |
| `app_cerrada:<proceso, nombre o *>` | Ninguna ventana de esa app abierta por el arnés | Cierra sólo lo que está en `propios.jsonl`, por ventana. Si la ventana ya no está, el proceso no se toca nunca (`cerrada_proceso_vivo`: una app de instancia única puede tener ya documentos de la persona). Sólo detiene por PID exacto el proceso que arrancó el arnés cuando su ventana sigue viva tras el cierre normal y todas las ventanas del proceso son del arnés (`estado/decisiones_comun.ps1`). Devuelve el foco sólo si cerró una ventana que estaba delante y la que Windows activó sigue delante. `*` cierra todo lo del arnés (fin de lote). |
| `documento_en_blanco:<PowerPoint\|Word\|Excel>[\|contenido]` | Esa app de Office con un documento nuevo sin guardar | Automatización COM, sin teclas. PowerPoint `Uno;Dos;Tres` = una diapositiva por título; Word `Hola mundo` = ese párrafo, seleccionado; Excel `a;b` = columna A. Con una copia de la persona abierta no hace nada. |
| `bloc_con_texto:<texto>` | Bloc de notas del arnés en una pestaña sin título con ese texto (vacío = pestaña vacía) | ValuePattern sobre el documento; si la pestaña activa no está libre, agrega una con el botón de la barra. El texto debe estar en `textos_de_prueba.json`. Va después de `app_cerrada:Notepad` y `bloc_vacio`. |
| `paint_con_lienzo:<W>x<H>[,trazo][,marca_roja]` | Paint del arnés con un lienzo conocido (vacío = lienzo nuevo por defecto) | Genera un PNG en `cu-estado\lienzos` y lo abre: la ventana se titula con ese archivo, no «Sin título». |
| `explorador_en:<carpeta>` | La ventana propia del Explorador en esa carpeta (relativa a Documentos, absoluta o `shell:`), ordenada por nombre | `Navigate2` y `ShellFolderView.SortColumns`, sin clics. |
| `archivo_abierto:<ruta>` | Un fixture de una carpeta `baxy-prueba*` abierto con su app por defecto | Como un doble clic. El título propone la app (`paisaje.jpg - Fotos`) y se aprende sólo si el proceso lo prueba, para que `app_cerrada:Fotos` lo cierre. |

Un estado con argumento se escribe `estado:argumento`. En `casos.json`, lo que el `setup` del manifiesto v3 pide y
ningún estado puede dar está en `sin_estado` con la razón (preferencias del dueño, notas y páginas que se sincronizan
con su cuenta, el Edge del producto); `base.ps1 -Caso` la imprime en la línea del caso.

### Verificador (`verificar.ps1`)

`verificar.ps1 -Caso <id> [-Fase antes|despues] [-Antes "<pids>"]` escribe
`%LOCALAPPDATA%\BAXY\cu-universal-evidencia\v2-<id>\verificacion-<fase>.json` para que un revisor juzgue el caso sin
leer la frase de BAXY: el texto `verify` del manifiesto, las ventanas de la app del caso (título, elementos
seleccionados, interruptores activados, valores de campos, barra de estado, foco, conteo por tipo de control), los
Explorador que el caso nombra (carpeta, orden, selección), cada archivo de `baxy-prueba-v3` (tamaño, fecha, SHA-256,
dimensiones, entradas de zip, párrafos de docx con negrita y alineación, diapositivas de pptx), las pantallas y, si el
caso habla del portapapeles, su texto. Sólo lee. Nunca lee ventanas de VS Code ni Opera. Tras el caso, con o sin
manifiesto (los casos del banco no lo tienen), también vuelca las ventanas tocadas por BAXY (`journal-caso.json`), la
del frente al terminar el conductor (`after-mision.json`) y las nacidas en el caso, hasta 8, cada una con su motivo en
`app`. Privacidad: una ventana es completa sólo si es del arnés o su proceso nació durante el caso
(`-Antes`); las demás de la app (las de la persona) quedan reducidas a pestañas, botones y menús seleccionados o
activados, sin título, elementos, textos ni valores; un Explorador es completo sólo bajo `baxy-prueba*`, y otra
carpeta que el caso nombre da sólo ruta y orden. `batch.sh` lo corre antes y después de cada caso; tras el caso, `estado/apps_del_caso.ps1` cierra las
ventanas de la app del caso cuyo proceso nació durante el caso **y** el libro prueba del lote (procedencia
positiva): una app que el dueño abrió durante el caso nunca se toca (`sin_tocar`). La ventana se cierra normalmente;
su proceso sólo se detiene por PID si el dueño no dio input en toda su vida, y nunca si es Windows Terminal o la app
de Claude. Si el dueño dio input durante la vida del proceso, o si es Windows Terminal o la app de Claude, sólo se
cierra una ventana que BAXY abrió o en la que trabajó (hwnd exacto en su diario, `CU_JOURNAL`): Word, el Bloc de notas
y Windows Terminal guardan todas sus ventanas en un proceso, y un documento del dueño puede abrirse dentro del Word del
lote.

Reglas comunes:
- Steam nunca se abre: sin Steam, el estado responde `steam_no_abierto`.
- Una app tocada que se lleva el foco se lo devuelve a la ventana que lo tenía (`"foco":"devuelto"`). Si delante hay
  otra ventana, de la persona o de otro agente, no se toca (`"ajeno"`).
- Sólo se cierra lo que abrió el arnés, por PID o HWND exactos, y nunca Visual Studio Code ni Opera.
- Steam no tiene árbol UIA e ignora clics y teclas enviados por mensaje (medido el 2026-10-07). Por eso usa el
  protocolo `steam://`, que lo trae al frente un instante.
- `estado/exploradores.ps1` lo usa `batch.sh`:
  - tras cada caso, cierra por HWND los Explorador que el caso abrió en un lugar de prueba, sólo con el registro
    cubriendo el caso entero sin input del dueño (si no, `sin_tocar` y un AVISO);
  - antes de esa regla, cierra por HWND la ventana nueva que un `app.open` completado de BAXY abrió en el caso
    (`windowHandle` con `alreadyRunning:false` en su journal desde la foto), aunque el dueño haya usado el equipo:
    es procedencia positiva, como un proceso que abrió BAXY. Nunca una ventana que BAXY sólo leyó o reutilizó, ni
    una de la foto, ni nada sin journal. Si no se va, entra en `ventanas_lote` del libro del lote: `sin_restos` la
    reintenta antes del caso siguiente y `app_cerrada` la cierra en vez de llamarla ajena (pasada r18, v3-43/v3-44);
  - al final del lote, cierra la ventana propia del arnés.
- Un caso que corre con el estado base sin verificar (`CU_ESTADO_ESTRICTO=0`) sale con `ESTADO_BASE_SUCIO:` en el
  lote, `estado_base_sucio` en su `.hecho` y `estado_base_sucio.json` en su evidencia: el juez no lo cuenta contra
  BAXY.
- El medidor de molestia cuenta perdidos e insertados por la distancia de edición mínima (subsecuencia común más
  larga, no difflib), y una tecla del simulador que el gancho no vio cuenta como entregada si está en la ventana.
- Los `.ps1` son UTF-8 sin BOM, y PowerShell 5.1 los lee como ANSI. Por eso un nombre con tilde se arma con
  `[char]` en el código, como en `comun.ps1`.

`cobertura_sin_arbol.ps1 [-Process a,b] [-Json] [-Detalle]` mide, por ventana abierta y sólo leyendo UIA (sin foco,
mouse ni teclas), cuántos accionables no tienen nombre y cuántos recupera cada fuente de respaldo del worker
(HelpText, LabeledBy, AutomationId legible), con la vista antes y después (contrato §8.1). Se corre con turno de
escritorio. Excluye Visual Studio Code, Opera y el shell.

## Casos

`cases/` guarda los bancos del 2026-10-07:
- `s*`, `c*`, `u*`, `n*`, `e*`, `g*`, `w1`: el banco base;
- `v*`, `x*`, `y*`, `z*`, `a*`, `b*`, `c11`–`c22`, `d*`: los lotes ciegos.

Los resultados de cada uno están en `documentacion/computer-use/MEDICIONES.md`.
