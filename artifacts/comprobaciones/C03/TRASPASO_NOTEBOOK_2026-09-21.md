# Traspaso REDPC → notebook — 2026-09-21 (noche)

El goal C03 se cerró el 2026-09-20 a 742/742; lo que sigue es el **plan post-goal** (la comprobación:
`PLAN_POSTGOAL_2026-09-20.md`, que por decisión del dueño reabrió filas y hoy deja el registro en 671/742). El dueño
decidió (2026-09-21, ~20:30) que ese plan sigue en el **notebook desatendido, 24/7**, con una sola sesión de Claude
(Opus 5) como escritora raíz y runner sellado. Este documento dice qué se lleva, cómo se
restaura y qué tiene que hacer esa sesión hasta cerrar su «wall». El texto del GOAL para pegar está al final (§8).

## 1. Estado que se traspasa

- Rama `codex/kiro-goal-c03`, HEAD del traspaso = el commit que contiene este fichero (pusheado a `origin`).
- Registro privado **671/742 cubiertos, 71 abiertos, 0 NA; 20/35 categorías cerradas**; SHA
  `3a2ef0bc4caee5736d39d928d733c3a83864144b9f34c090d0cf212985362738`. Última tanda adjudicada: WEATHER2035.
  cien-96 100/100 sobre 0758398ed (CIEN.md). Fast verde sobre baec1159b.
- Las 71 abiertas se reparten así (calculado del registro, ids en `make_typed_panels.py`):
  - **45 las cubren las tandas tipadas pendientes** (§5): winget 7 (H0089, H0167, H0217, H0457, H0574, H0583,
    H0651), steam 4 (H0456, H0571, H0578, H0620), steam_dl 10 (H0049, H0118, H0272, H0382, H0390, H0434, H0482,
    H0659, H0671, H0680), steam_inst 8 (H0039, H0295, H0345, H0387, H0396, H0612, H0643, H0721), launch 2 (H0083,
    H0608), power 2 (H0401, H0714), wifi_place 2 (H0170, H0376), shell 2 (H0048, H0245), zip H0542, airplane
    H0107, wallpaper H0459, download H0077, pptx H0188, meme H0069, textread H0299, explorer_count H0701.
  - **14 son de lectura (Fase 3.5, Fable):** H0019, H0024, H0045, H0074, H0198, H0231, H0408, H0536, H0227, H0398,
    H0521, H0263, H0528, H0682. No se tocan en el notebook.
  - **12 necesitan el motor (Fase 4/5):** H0128, H0232, H0325, H0368, H0344 (control de Discord), H0175, H0566
    (enter dentro del cliente), H0290, H0636 (canal de Discord), H0444 (pestañas del Chrome del dueño), H0510,
    H0720 (leer el último mensaje de esa persona). No se tocan en el notebook.
- WALLPAPER2037 quedó **preparada en REDPC pero sin correr** (instrumento `C03-wallpaper2037-instrument-v1`,
  registro padre WEATHER2035). ZIP2039 está generada con un HEAD viejo (d8eb88367). Las dos se **regeneran** en el
  notebook (§5): un instrumento preparado no viaja entre máquinas.

## 2. Paquete de traspaso (fuera de git, por privacidad)

`D:\BAXY-traspaso-2026-09-21\` en REDPC (y su `D:\BAXY-traspaso-2026-09-21.7z`), con `MANIFEST.json`
(sha256 de cada fichero) y `README_TRASPASO.md`:

| Carpeta del paquete | Va a (en el notebook) | Qué es |
|---|---|---|
| `LOCALAPPDATA-BAXY\` | `%LOCALAPPDATA%\BAXY\` (mezclar, sobrescribiendo) | Todo lo tocado en `%LOCALAPPDATA%\BAXY` desde el 2026-09-18 14:00: registro privado (`C03-survey-requirements336-private`), instrumentos, propuestas, builds (`C03-repairs*-build`, incl. `1999` con el `build.py` oficial), perfiles de caso, `typed-fixtures-state`, `cien95`, `cien96`. Excluye `browser-session-v1`, `webview2-field`, `dev-mente-v2`, `development`, `legacy-journal-*`, `stale-2026-09-21`. |
| `scratchpad-runner\` | `C:\Users\usuario\AppData\Local\Temp\claude\d--Perfil-Escritorio-ETC-Programacion-BAXY-DEFINITIVO\250e1a56-9daa-4ae6-a51f-44fe3a271a6d\scratchpad\` | El scratchpad del runner sellado (generadores, `next_tanda.py`, `typed_case.sh`, `wait_quiet.sh`, `idle_gate.py`, `approve_*.py`, `typed_fixtures.ps1`, `app_volume.ps1`, `build_video1955.py`, `privacy_check_1743.py`, todas las tandas anteriores). Sin `memprobe/ invprobe/ policyprobe/ tmp_src1737/ patched/`. |
| `scratchpad-planner\` | `C:\Users\usuario\AppData\Local\Temp\claude\c--Users-usuario-Desktop-ETC-Programacion-BAXY-Definitivo\102cfee2-a8c3-4ccd-bcee-305afde99465\scratchpad\` | El scratchpad de la sesión planificadora: `typed\` (paneles, specs, `make_typed_panels.py`, `make_wording.py`, `authored_wording.py`), `run_cien9N.sh`, `cien_score.py`, `read_capture.py`, `repin_program_identity.py`, `run_fast_d89.ps1`, `fix_backspace.py`. `make_typed_next.py` lee de aquí (`S`), así que la ruta debe ser exactamente esa. |
| `memory\` | `C:\Users\usuario\.claude\projects\<slug del repo en el notebook>\memory\` (mezclar; conservar lo local) | La memoria de la campaña (instrumentos, trampas, decisiones del dueño). Índice `MEMORY.md`. |

El registro privado NUNCA se reconstruye desde los `REGISTRY_UPDATE.json` del repo (sólo traen ids tocados y
contadores). Verificar tras copiar: `sha256sum "%LOCALAPPDATA%\BAXY\C03-survey-requirements336-private\requirements.jsonl"`
= `3a2ef0bc…`.

## 3. Rutas: el notebook tiene que ser un espejo de REDPC

Toda la herramienta tipada (plantilla `build_video1955.py`, paneles, `redpc_*.py`, generadores) se derivó en REDPC
con el repo en `C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo` y un **junction** en
`D:\Perfil\Escritorio\ETC\Programacion\BAXY DEFINITIVO` apuntando a él (`Path.resolve()` devuelve la forma C:).
Los scripts hacen `cd /d/Perfil/...` y las pins llevan la forma C:. En el notebook el repo vive en D:\Perfil. Para
que TODO corra sin re-derivar:

1. Cerrar VS Code / Visual Studio / BAXY. `dotnet build-server shutdown`; comprobar que no queda `dotnet.exe`,
   `VBCSCompiler.exe`, `Baxy.exe`, `baxy-core.exe`, `llama-server.exe` ni `python.exe` de la mente.
2. Mover el repo: `Move-Item "D:\Perfil\Escritorio\ETC\Programacion\BAXY DEFINITIVO" "C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo"`
   (crear antes `C:\Users\usuario\Desktop\ETC\Programacion`).
3. Junction en la ruta vieja: `New-Item -ItemType Junction -Path "D:\Perfil\Escritorio\ETC\Programacion\BAXY DEFINITIVO" -Target "C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo"`.
   El manifiesto del runtime del notebook (`%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json`, python_path en
   D:\Perfil) sigue valiendo a través del junction; **no** copiar el de REDPC (es por PC; el sello lo re-ancla).
4. `git -C "C:\Users\usuario\Desktop\ETC\Programacion\BAXY Definitivo" fetch origin && git checkout codex/kiro-goal-c03 && git pull --ff-only`
   → el HEAD debe ser el commit de este fichero. `git status --short` limpio (los ficheros sueltos de REDPC
   `ComputerUse.txt` y `LEEME_DOS_EJECUTORES_OPUS.md` no viajan; no hacen falta).

Si mover el repo fuera imposible, la alternativa es la inversa de `redpc_1845.py` (bloque `notebook_<n>.py` que
reescribe `R`, el par de `BASE_RENAMES` y las claves del candidato padre) en cada derivación — más lento y frágil;
preferir el espejo.

## 4. Comprobaciones de máquina antes de la primera tanda

- `build.py` oficial: el que copian los `setup_*.sh` es `%LOCALAPPDATA%\BAXY\C03-repairs1999-build\build.py`, que
  llama a `C:/Program Files/dotnet/dotnet.exe`. Si en el notebook dotnet vive en `C:\Users\usuario\.dotnet\dotnet.exe`
  (como en `C03-repairs1311-build\build.py`), editar esa ruta en el `build.py` de `1999` UNA vez antes de la
  primera tanda (los siguientes lo copian de ahí).
- `vswhere.exe` en `C:\Program Files (x86)\Microsoft Visual Studio\Installer` (los `setup_*.sh` lo exportan y
  fallan con `NO_VSWHERE` si no está).
- Python del runtime `%LOCALAPPDATA%\BAXYRuntime\python\mind-runtime-v1\Scripts\python.exe` con `psutil`.
- Fast verde antes de tocar nada: `powershell -File <scratchpad-planner>\run_fast_d89.ps1` (o
  `scripts\test_source_quality.ps1 -Mode Fast`).
- Steam con la sesión del dueño iniciada; títulos de prueba PvZ GOTY (3590) y PICO PARK (461040), que el dueño
  autorizó a instalar/desinstalar libremente. No comprar nada; no bajar decenas de GB.
- Perfil Edge del producto (`browser-session-v1`) con las sesiones que ya tenía el notebook; no se traspasa.
- El escritorio redirigido y `typed-fixtures-state` (fixtures sólo bajo carpetas `raiz_*` propias; los restores
  mandan a la Papelera sólo lo creado después del `before`).
- RAM: el runner exige ≥4,2 GB libres antes de cada caso y 2–5 min sin entrada del usuario (`idle_gate.py`); en un
  notebook desatendido eso se cumple solo. Nunca editar `src` con algo corriendo.

## 5. Las tandas tipadas pendientes (17) y su receta

Orden y numeración (impares consecutivos; el padre registral de cada una es la anterior adjudicada):

| # | camp | cap | wording | filas | notas |
|---|---|---|---|---|---|
| 1 | wallpaper2037 | wallpaper | `generators/wording/wallpaper.json` | H0459 | regenerar (padre WEATHER2035, BEFORE 671) |
| 2 | zip2039 | zip | `zip.json` | H0542 | regenerar |
| 3 | airplane2041 | airplane | `airplane.json` | H0107 | |
| 4 | download2043 | download | `download.json` | H0077 | |
| 5 | pptx2045 | pptx | `pptx.json` | H0188 | |
| 6 | meme2047 | meme | `meme.json` | H0069 | |
| 7 | textread2049 | textread | `textread.json` | H0299 | |
| 8 | explorer2051 | explorer_count | `explorer_count.json` | H0701 | |
| 9 | shell2053 | shell | `shell.json` | H0048, H0245 | |
| 10 | power2055 | power | `power.json` | H0401, H0714 | reviewed (apagar/reiniciar se cancela en el fixture) |
| 11 | wifiplace2057 | wifi_place | `wifi_place.json` | H0170, H0376 | |
| 12 | launch2059 | launch | `launch.json` | H0083, H0608 | juego autenticado por `steam://` |
| 13 | winget2061 | winget | `winget.json` | 7 filas | reviewed (`approve_winget.py`) |
| 14 | steam2063 | steam | `steam.json` | 4 filas | reviewed (`approve_steam.py`) |
| 15 | steamdl2065 | steam_dl | `steam_dl.json` | 10 filas | descarga real de PvZ/PICO PARK |
| 16 | steaminst2067 | steam_inst | `steam_inst.json` | 8 filas | instalar/desinstalar los títulos de prueba |
| 17 | appvolume | appvolume | `appvolume.json` | — | sólo si el registro lo pide (hoy 0 abiertas): omitir |

Receta por tanda (todo desde `S` = scratchpad-runner; `PY` = python del runtime; regenerar SIEMPRE justo antes,
con el HEAD vigente y BEFORE = cubiertos actuales; nunca dejar tandas generadas por adelantado):

```bash
cd "$S"
"$PY" -X utf8 generators/make_typed_next.py <cap> <camp> <camp_prev> <CAMP_PREV> $(git -C "$R" rev-parse --short HEAD) <BEFORE> generators/wording/<cap>.json
# → panel_<n>.py, spec_<n>.json, derive/build/setup/run_cases/write_results/decisions_fill/docs/chain/commit_<camp>
PREPARE_ONLY=1 bash setup_<camp>.sh > run_<camp>.log 2>&1        # build oficial + derive + prepare (sella el HEAD)
grep -q PREPARED_ONLY run_<camp>.log                              # si no: leer el log, arreglar, quitar C03-<camp>-instrument-v1 y -proposal, repetir
bash run_cases_<camp>.sh >> run_<camp>.log 2>&1                   # los casos, uno a uno, con wait_quiet + RAM + idle
"$PY" -X utf8 write_results<n>.py '{"0":"passed",...}' '{"i":"nota"}'  # veredictos leídos de private/run-XX/case-observations.json
bash chain_<camp>.sh "<resumen>" <créditos> <cubiertos_después> <abiertos_después> "<medida>"  # adjudica, publica, docs, commit, push
```

Un caso se aprueba sólo con evidencia: operaciones esperadas completadas y verificadas (o cero operaciones en los
límites), final fiel en el idioma del pedido, cero violaciones, pins intactos. Nunca inventar un efecto en el final.
Después de cada tanda: `git log --oneline -1`, `PUSHED` en el log y la fila en `HANDOFF.md`.

Si los `setup_*.sh` generados fallan por el HEAD («prepared HEAD must equal git HEAD»): commitear los docs antes de
preparar; por «directories already exist»: mover el instrumento viejo a `%LOCALAPPDATA%\BAXY\stale-<fecha>\`; por
«concurrent processes»: `dotnet build-server shutdown` + `Stop-Process VBCSCompiler` y esperar a los nodos de MSBuild.

### Regla de reparación (dueño, 2026-09-21)

- **Fallo de adaptador o de fixture** (la operación existe, la mente la pidió bien, el Windows/el instrumento
  falló): se arregla en `src`, tests, Fast verde, commit, y se **re-mide** la tanda (nueva numeración, mismo panel:
  `generators/make_rerun.py`).
- **Fallo de lectura** (la mente no entendió la forma, preguntó de más, o negó): **NO se parcha con otro regex.**
  Se anota en `artifacts/comprobaciones/C03/SEMANTICA_CORPUS_PENDIENTE.md` (literal → lo que hizo → lo que debía
  hacer → fila) y la fila queda abierta para la Fase 3.5. La tanda se adjudica con honestidad (crédito parcial o
  cero) y se sigue con la siguiente.
- Cambio de mente o de App → cien nueva (`run_cien9N.sh` + `cien_score.py` contra la anterior; 100 published_final,
  0 operaciones) documentada en CIEN.md antes de la siguiente tanda.

### 5b. Lo que dejó la prueba del dueño (2026-09-21 23:46–00:06) — obligatorio para el notebook

Auditoría completa, turno a turno, en `PRUEBA_DUENO_2026-09-21_NOCHE.md` (60 turnos: 22 bien, 38 mal). El registro
privado de esa conversación viaja en el paquete como `private-logs/conversation.v1.jsonl` (turnos 111–231). Tres
cosas salen de ahí para el notebook, ANTES de las tandas tipadas (van primero porque tocan la App/mente y las tandas
se sellan sobre el HEAD resultante):

1. **Arreglos de adaptador/estado/presentación (sí los hace el notebook):**
   - Final que afirma un efecto sin operación (turno 189 «Claro, ya le hice click» con cero operaciones): veto duro
     en el compositor/App — sin operación completada no hay afirmación de efecto; se responde el límite honesto.
   - «para la canción» justo después de reproducir en YouTube → «No estoy escuchando nada» (148): el estado de
     reproducción del turno anterior tiene que persistir y `media.stop` (o el cierre del reproductor) aplicarse.
   - Texto de confirmación mal formado «¿confirmar o cancelar la cerrado de Edge?» (151).
   - Fallo del compositor de 45 s «no_response; retry_exhausted» (195): tope corto y respuesta de límite inmediata.
   - «activa mi micrófono» → «no pude observar el efecto» (205): la post-lectura de reactivar el micrófono.
   - «BAXY, cierra BAXY» → «no tiene ventana abierta» (211): cerrarse a sí misma o decir la verdad de cómo cerrarla.
   Cada uno con su test, Fast verde, cien nueva (cambió mente/App) y re-medición sellada si toca una lectura acreditada.
2. **Medida contextual (nueva, la pide el dueño):** las tandas midieron literales sueltos y en conversación BAXY
   se rompe (pregunta lo ya contestado, pierde la anáfora, no une la respuesta a su propia pregunta con el pedido).
   El notebook construye `artifacts/comprobaciones/C03/contexto/dueno-2026-09-21.turns.jsonl` (la conversación del
   dueño como guion del conductor, esperado por turno = la tabla de la auditoría) y la corre antes y después de sus
   arreglos (cifra «turnos bien / 60», documentada en CIEN.md como `ctx-dueno-NN`), y después arma los bancos
   contextuales por categoría del §«Medida contextual» de la auditoría (`contexto/<categoria>.turns.jsonl`, 15–25
   turnos con dependencias reales, sólo efectos reversibles) y los corre como `cien-ctx-NN`. Los fallos de lectura o
   de contexto que aparezcan NO se parchan: van al corpus (`SEMANTICA_CORPUS_PENDIENTE.md`) con el guion y el turno.
3. **Corpus para Fable:** todo lo L/C/K de la auditoría ya está en `SEMANTICA_CORPUS_PENDIENTE.md`; el notebook añade
   lo que salga de sus tandas y de los bancos contextuales.

## 6. Cierre del wall del notebook

1. Los arreglos del §5b.1 hechos y medidos; `ctx-dueno` antes/después; las 16 tandas corridas y adjudicadas (la 17
   sólo si hiciera falta); registro esperado ≈ 716/742 si todas acreditan (los 26 restantes son de Fase 3.5 y
   Fase 4/5, y NO se fuerzan); los bancos contextuales por categoría corridos al menos una vez con su cifra.
2. `repin_program_identity.py "<motivo>" <repo>` y **Full verde** (`scripts/test_source_quality.ps1 -Mode Full`,
   tier pytest con el python del runtime), sin skip/xfail/umbrales.
3. cien final 100/100 sobre el HEAD final, documentada.
4. `HANDOFF.md` (bloque REANUDACIÓN con cifras y la acción inmediata = «Fase 3.5, Fable, prompt
   `PROMPT_FABLE_SEMANTICA_2026-09-23.md`»), `CHECKPOINT.md`, `ESTADO_PARA_DUENO_<fecha>.md`,
   `CURRENT_CATEGORY_COUNTS.md`, `SEMANTICA_CORPUS_PENDIENTE.md` completo, memoria de la campaña, push.
5. **No** fusionar a `main`: la fusión es la Fase 9, después de las Fases 3.5 (semántica), 4 (motor) y 5 (banco).

## 7. Lo que no hay que hacer (plan §7, vigente)

Sin squash/rebase, sin `git add .`, sin `reset --hard`, sin `clean`; no cambiar riesgos del catálogo; ningún
mensaje/correo a terceros reales (sólo Música, Ron92 y la casilla 302); no comprar; no bajar decenas de GB; no
relajar pruebas; no editar `src` con algo corriendo; no inventar efectos; fixtures sólo en `raiz_*`; no tocar
`fable/computer-use-engine`; no parchar lecturas con regex (§5).

## 8. GOAL para pegar en la sesión del notebook

```
Eres la única sesión de Claude (Opus 5) sobre el repositorio de BAXY en el notebook del dueño, rama
`codex/kiro-goal-c03`: escritora raíz y runner sellado del PLAN POST-GOAL C03 (la comprobación posterior al cierre
del goal C03 el 2026-09-20; el plan reabrió filas por decisión del dueño). El dueño trabaja en otra máquina y este
notebook está desatendido 24/7: no esperes respuestas suyas; con permisos totales, decide tú y deja evidencia.

Objetivo (cerrado cuando lo demuestres, no antes): (a) los seis arreglos de adaptador/estado/presentación del
§5b.1 de `artifacts/comprobaciones/C03/TRASPASO_NOTEBOOK_2026-09-21.md` (el primero, el veto al efecto inventado,
es el más grave), con la conversación del dueño (`PRUEBA_DUENO_2026-09-21_NOCHE.md`) convertida en guion del
conductor y medida antes y después; (b) correr y adjudicar con honestidad las 16 tandas tipadas pendientes del §5
(wallpaper2037 … steaminst2067); (c) los bancos contextuales por categoría (§5b.2) corridos con su cifra; (d) Full
verde con los sellos re-anclados, una cien final 100/100, los documentos de estado y la memoria al día, todo
commiteado y pusheado. Principio del dueño (turno 164 de su prueba): BAXY debe generalizar, no ajustarse a los 742. Las 71 filas abiertas del registro son 45 tipadas (tuyas), 14 de lectura
(Fase 3.5, de Fable, NO las toques) y 12 del motor (Fase 4/5, NO las toques). Tu wall termina ANTES de la
Fase 3.5 y del computer use; no fusiones a main.

Empieza leyendo, no adivinando: `AGENTS.md` entero, `artifacts/comprobaciones/C03/TRASPASO_NOTEBOOK_2026-09-21.md`
(este traspaso: paquete, rutas espejo, comprobaciones de máquina, receta y regla de reparación),
`PLAN_POSTGOAL_2026-09-20.md` (§3, §7 y la Fase 3.5), `DECISIONES_DUENO_2026-09-20.md`, `HANDOFF.md` (primer
bloque) y la memoria traspasada. Restaura el paquete `BAXY-traspaso-2026-09-21` exactamente como dice el §2,
haz el espejo de rutas del §3 y las comprobaciones del §4 antes de la primera tanda. Verifica el SHA del registro.

Método: una tanda por vez, regenerada justo antes con el HEAD vigente; build oficial; prepare; casos con las
puertas del runner; veredictos leídos de las observaciones privadas; adjudicación; publicación; docs; commit;
push. Fallo de adaptador/fixture → arreglar, Fast verde, re-medir. Fallo de lectura → NO más regex: anotar en
`SEMANTICA_CORPUS_PENDIENTE.md`, fila abierta, seguir. Cambio de mente o App → cien nueva antes de seguir.

Reglas duras: nunca `git add .`, squash, rebase, reset --hard ni clean; nunca editar `src` con algo corriendo;
nunca relajar pruebas ni sellos; nunca inventar efectos; ningún mensaje/correo a terceros reales; no comprar;
no bajar decenas de GB; Steam sólo con PvZ GOTY (3590) y PICO PARK (461040); no tocar `fable/computer-use-engine`.

Reporta con cifras, no con narrativa: registro N/742, tandas hechas/pendientes, cien, Full. Si algo queda fuera,
dilo y por qué. No marques completado por cansancio ni por un fallo aislado.
```
