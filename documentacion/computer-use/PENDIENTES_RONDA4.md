# Pendientes de la ronda 4 (computer use v3)

Integración `fable/cu-v3-ronda4` sobre `fable/cu-universal-v3` (que ya trae las rondas 1–3). `PROGRESO_V3.md` es del
líder y queda en la versión de la base; las notas de la integración viven aquí. Informes de las ramas:
`%LOCALAPPDATA%\BAXY\cu-v3\r4i\<rama>.json`; análisis de origen: `%LOCALAPPDATA%\BAXY\cu-v3\r4a\*.md`.
`fable/cu-v3-uia-sin-frente` (rama A) no se fusiona: sigue en prueba.

## Fusiones y conflictos

Orden: medidor-r3, rafaga, navegacion (todas `--no-ff`, cabezas = las de la corrección de cada informe: `22f95e485`,
`b0c47a058`, `daa4dce4a`).

- Sin conflictos de texto. El único fichero que tocan dos ramas es `src/Baxy.App/ComputerUseMission.cs`: rafaga
  cambia la cuenta de `unchangedViews` (exime sólo una vista tomada detrás tras un acto de teclado) y navegacion pone
  antes de la firma de vista el bloque de «ya estabas» con árbol. Se juntan en ese orden: el bloque de navegacion sólo
  mira un clic verificado, así que nunca decide sobre la vista detrás de una tecla que rafaga exime.
- Calculadora: rafaga no la toca (dejó M4 de molestia fuera) y navegacion quita su ráfaga (`KeysLease`,
  `HelperBurstAsync`, `WatchHelperAsync`) para pulsar por Invoke. Esas piezas siguen vivas para Spotify, el atajo de
  teclado del escritorio y el selector de canales de Discord.
- Sin rojos de fusión.

## Duplicados (ley 2)

Revisados entre rafaga y navegacion, sin duplicado que consolidar:

- **Guardas del frente.** Sólo rafaga añade guardas: el candado común `ForegroundHandBack.FrontGate` (préstamo,
  guardia de apertura y devolución del arranque), la retención tras una tecla con su vigilante (`AcquireSequenceAsync`,
  `WatchHeldAsync`) y el corte del texto por `Holds`/`UserReached`. Navegacion no añade ninguna: la Calculadora deja de
  pedir el frente.
- **Esperar y releer.** Cada espera mira una cosa distinta: la pausa de la persona (`WaitForPauseAsync`, al que
  `IPointerFallback.PauseAsync` sólo delega), el enrutado del propio clic (`SettleOwnInputAsync`, 5 ms hasta 100 ms),
  la vista posterior que suelta el frente retenido (`LookBegins`/`ReleaseHeld`), la llegada de la página tras un clic
  (navegacion reutiliza `PageLooks` × `PageLookInterval`, como `ReplayArrivalDrawnAsync` y `RedrawnAfterActAsync`) y
  el valor del campo tras `SetValue` (`Wait-ValueSet`).
- Quedan dos copias menores, anotadas y no unidas:
  - El sondeo «releer cada 40 ms hasta 300 ms» está en `Wait-ValueSet` (`DesktopUiaWorker.ps1`) y en el «Borrar» del
    `CalculatorScript`. Son dos procesos de PowerShell distintos (el worker es un fichero, el script de la Calculadora
    una constante): se unen cuando la Calculadora pase al worker con la «vía del motor» (pendiente de navegacion).
  - `cu_goals.check_searches` (mente) copia `ComputerUseSuccessCheck.SearchResultsProve` (App) para no rechazar
    el texto de una búsqueda. Para una sola regla, el App podría mandar el dato junto al check; toca el contrato.

## Arnés: turno con los agentes

`lote.sh` y los agentes tenían una carrera: el agente miraba `live.lock` y después creaba su lock, mientras el lote
miraba «sin agentes» y después escribía `live.lock`; los dos podían entrar a la vez. Ahora `scripts/cu_live/turno.sh`:

- el agente (`turno.sh tomar <nombre>`) crea PRIMERO `agent-<nombre>.lock` y LUEGO espera a que no exista
  `live.lock`; entre agentes, `agentes.d` (mkdir atómico) da el escritorio a uno solo. `turno.sh soltar <nombre>`;
- el lote espera a que no haya `agent-*.lock` vivo, escribe `live.lock` y **vuelve a mirar**: si un agente se anunció
  entretanto, cede (la otra carrera que quedaba, del lado del lote);
- un lock de agente muerto se reconoce por 30 min sin tocar (`CU_TURNO_VIEJO_MIN`), no por 5 min de espera del lote,
  que pisaba una prueba viva más larga. El agente en cola lo renueva en cada mirada.

README del arnés y comentarios de los `*LiveDesktopCheck` al día; pruebas en `tests/test_cu_live_estados_v3.py`.

## Validación

Sobre `68bb4f2c3` (las tres fusiones y el turno), sin suite completa ni Full:

- `dotnet build src/Baxy.App -c Release`: 0 errores, 0 avisos; `dotnet publish src/Baxy.Core -c Release -r win-x64`:
  0 errores.
- pytest (mind-runtime-v1, `PYTHONPATH=<worktree>\src`, `-X utf8 -p no:cacheprovider`) sobre
  `test_computer_use*.py test_cu_*.py test_compound_missions.py test_reading_lives_in_semantic.py
  test_censo_voz_visible.py test_compose_contract.py test_c03_inventory_output_budget.py
  test_c03_process_scope_prompt.py test_c03_m1*.py` más los de los informes (`test_c03_m128_historial_decisor.py`,
  `test_c03_m107_suelo_acciones.py`, `test_cu_v2_carpeta_en_carpeta_conocida.py`, los `test_cu_live_*` y
  `test_cu_v3_*`): **5032 passed**, 0 skips.
- `scripts/inventory_reading_outside_semantic.py --check`: exit 0.
- `dotnet test tests/Baxy.Integration.Tests -c Release --filter
  "FullyQualifiedName~ComputerUse|FullyQualifiedName~OperationFloor|FullyQualifiedName~M107|FullyQualifiedName~MindShellEndToEnd"`:
  **585/585**.
- `dotnet test tests/Baxy.Providers.Windows.Tests -c Release --blame-hang-timeout 120s`: **1379/1379**.
- `dotnet test tests/Baxy.Kernel.Tests -c Release`: **362/362**; `tests/Baxy.Contracts.Tests`: **70/70**.

## Pendiente

- Rama A (`fable/cu-v3-uia-sin-frente`): la tecla 0xB9 y M1 de UIA siguen sin integrar.
- rafaga: relectura UIA del campo para reanudar tras el tecleo de la persona (hoy se corta como interrumpido);
  s11 (el desplegable que se cierra al perder la activación) sin resolver; `LookHoldCapMs=500` y la suposición de
  que `SetCursorPos` no genera Raw Input, sin medir; riesgos de M3 (menú emergente cerrado al devolver el frente,
  base vieja o «cambió» falso con una ventana que se redibuja).
- navegacion: la «vía del motor» de la Calculadora (los clics de computer use siguen sin pasar por el teclado por
  Invoke); los nombres de los paréntesis de `keypad_keys.v1.json` sin ver en vivo; tope del 10 % y miradas a 400 ms
  sin calibrar («ya estabas» tarda ~2,4 s); la línea de `mind_unavailable` con intención error sale de «result»:
  confirmar con el dueño (M75).
- medidor-r3: `discord_md` con nombres del journal, no de un volcado UIA vivo; la capa de ajustes que deja s13 queda
  `no_verificado`; `-Reintentar` reintenta el HWND guardado sin mirar el título; un estado base que no se verifica en
  la repetición da `NO_CORRIO` (más estricto que el primer intento).

## Verificación en vivo pendiente

Nada de esta ronda se probó en el escritorio (todas las ramas encontraron `live.lock` puesto). Con `turno.sh tomar`:

- medidor-r3: `molestia/autoprueba.py --solo limpia,carga,fuera,pausa,tarde` (5 PASS); `estado/base.ps1 -Estados
  discord_md:Ron92`; `marcos.ps1 -Listar` y `batch.sh v11 g1` (marco cerrado por HWND); `batch.sh s13` con el decisor
  ocupado («se repite … desde el estado base» o `NO_CORRIO`); Calculadora abierta a mano durante un caso → `sin_tocar`.
- rafaga: c6 (un solo `input.text.type`, 14 caracteres; con la persona tecleando, `input_user_interrupted`); g1
  (`frontHeld:true`, vista con `window.foreground:true`, frente devuelto en < 1,5 s); w1 t4 sin
  `input_window_not_in_front`; M2 (v11, y11, s13) sin robo de frente; M3: frente devuelto 0–100 ms tras el clic.
- navegacion: Calculadora (`nav_calc_live.ps1` del scratchpad: dos veces `method=invoke`, `value=42`, «Borrar» lee 0);
  w1/n2/x1/x12/y1 sin teclas de BAXY; v8 → `computer_use_already_there_unconfirmed` sin teclear «inicio»; «ir a
  Biblioteca» con procedimiento → reached; «ir a wikipedia» en Opera escribe en la barra; s02 con el decisor caído →
  línea al momento.
- El propio turno: un lote corriendo y un agente con `turno.sh tomar` → el agente entra entre dos casos y el caso
  siguiente espera a su `soltar`.
