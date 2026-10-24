# Plan de cierre de la fase 2 (holdout v5), escrito antes de abrir nada

Pre-registro del análisis del holdout v5 (`F:\BAXYeval\renew_v5\holdout`, sellado el 2026-10-23; sha256 en
`metas.json` → `maximo.holdout_v5`), fijado el 2026-10-24 antes de abrirlo. Se abre una vez, sobre el HEAD final; tras la
corrida única se publican las cifras y el banco deja de ser holdout. Sigue `MEDIR.md` («Qué cambia al correr el holdout
v5») y `CIERRE_PLAN.md` (v4) en todo lo que aquí no se cambia.

## Qué se congela antes de abrir

- HEAD final de la fase 2 (hoy candidato `int10d` 71c72bcc2 o su sucesor): suites verdes en las dos máquinas sobre ese
  mismo commit (PC: Kernel, Contracts, App, Setup, pytest; NB: Providers entero). Se anota abajo, en «Al congelar».
- Laya `layam-long-s1-Q8_0.gguf` (sha256 12658256…bdbf) y umbrales 0,4 / 0,6 / corrige en las tres configuraciones
  (la palanca 7 del NB no encontró par mejor). Qwen `BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf` (8a4b6ce3…).
- Jueces: los de `scripts/renew/` del HEAD final (`bench_decision.py`, `catalog_equivalence.json`, `bench_e2e.py`,
  `bench_falsedades.py`). Ningún cambio de puntuación después de abrir.

## Las tres configuraciones

| Nombre | Código | System One | Catálogo de decisión |
|---|---|---|---|
| `inicio` | `pc-system-one` 86991ca9d (la mente con semilla: `F:\BAXYeval\renew_v4\arr\86991ca9d-s{0,1,2}`) | encendido | `renew_v4\catalog-base.json` |
| `maximo` | `renew-maximo` 452854a18 (fin de la fase 1) | encendido | `renew_v4\catalog-final.json` |
| `final` | HEAD final de la fase 2 | encendido | `renew_v4\catalog-v5final.json` |

`catalog-v5final.json` = `catalog-final.json` con las capacidades volcadas del HEAD final y sin los 17 nombres de
herramientas del sistema que el producto final no lista (ayuda `system_tools_unlisted`; son exactamente los 17 que
faltan en el catálogo vivo de este PC de int10c, `pc-i10c-e2e-s0-e2e\mente\catalog.configure.json`). Juegos y el resto de
aplicaciones, los de `catalog-final.json`, para que las tres configuraciones vean las mismas apps salvo lo que el
producto final cambia a propósito. En e2e y falsedades cada configuración usa el catálogo que su producto envía.

## Bancos y reparto

| Banco | Dónde | Réplicas por configuración | Métrica primaria | Secundarias |
|---|---|---|---|---|
| Decisión (720) | PC, semillas 0, 1, 2 | 3 | aciertos (juez común) | acciones equivocadas (`--metric wrong_action`), pass^3, p50 |
| E2E (76) | PC semilla 0, NB semilla 1 | 2 | casos cumplidos | pass^2, por área; primera respuesta sólo dentro de una máquina |
| Falsedades (36) | PC semilla 0, NB semilla 1 | 2 | falsedades claras leídas a mano (`CRITERIO_FALSEDADES.md`) | dudosas |

- **Intercalado**: dentro de cada banco y máquina, por semilla: `inicio`, `maximo`, `final`; nunca una configuración
  entera tras otra.
- **Decisión**: se corre con el `bench_decision.py` del HEAD final para las tres (pasa `pending` a la mente, como pide
  `SEALED-decision.md`) y `--src` de cada configuración; antes de la primera corrida, `holdout_tools\validate.py` con ese
  juez debe dar PROBLEMAS: 0. Juez común: `compare_banks.py … --write` con el `catalog-v5final.json`. Una corrida con
  `errors > 0` o con `system_one.unanswered` mayor que 2 se repite entera.
- **E2E y falsedades**: S1 explícito por `BAXY_S1_*` y comprobado en `summary.run.system_one`; `contaminated` debe ser
  `false` tras cada brazo (si no, se devuelven los archivos y se repite el brazo siguiente). En `inicio`, la semilla entra
  por la copia `arr\86991ca9d-s{n}`. En el NB, copia F:→D: hecha tras extraer, con el sha256 del original y de la copia.
- **Lectura a mano de falsedades** a ciegas: un agente lee `transcripts.json` con las configuraciones renombradas al azar
  (A/B/C, la clave la guarda la sesión principal y se revela después de contar).

## Análisis (`pareado.py` del HEAD final)

- Comparaciones: `final` frente a `maximo` (lo que ganó la fase 2) y `final` frente a `inicio` (toda la misión).
- Decisión: Δ con IC95 por bootstrap pareado sobre los 720 ítems, McNemar exacto por mayoría, Holm entre las dos
  comparaciones; gemelos de dictado con error agrupado por pareja (`--cases`). Igual para acciones equivocadas.
- E2E y falsedades: descriptivo con IC (potencia baja por diseño; guarda de regresión).
- Se informa todo, gane o pierda. Nada se reajusta después de abrir.

## Exclusiones fijadas ahora

Un caso `setup_fallido`, `void` o `sesion_bloqueada` queda fuera (no es fallo del producto). Una corrida VOID entera (una
ventana ajena, el frente sostenido por una ventana invisible) se repite antes de mirar sus aciertos. Nada más se excluye.

## Orden del cierre

1. Congelar el HEAD final; suites en las dos máquinas; volcar `catalog-v5final.json`; anotar «Al congelar».
2. Recursos del HEAD final con `measure_resources.py` y el oído real cargado (NB), `vram_attribution: ok`.
3. Comprobar el sha256 de los 7z contra `metas.json`, extraer en `renew_v5\holdout\abierto\` y correr el plan: primero la
   decisión en el PC; e2e y falsedades a la vez en el NB; e2e y falsedades del PC al terminar la decisión.
4. Prueba en vivo en el PC (el dueño cedió el PC), restaurando todo al terminar.
5. `INFORME_MAXIMO.md` (sección fase 2) y mensaje al dueño.

## Cambios aceptados del NB (buzón 2026-10-24 00:50), antes de abrir

1. En el NB, e2e y falsedades corren una tras otra, no a la vez.
2. Recursos en el NB con las rutas WAKE/STT del notebook (`measure_resources.py` tal cual no carga el oído en REDNOTE).
3. `nb-vad-sin-torch` y `nb-laya-t6` entran en el HEAD final.
4. Arnés común en e2e y falsedades: los `scripts/renew` del HEAD final se copian a los worktrees de `inicio` y `maximo`
   antes de correrlos (como `bench_decision.py` en decisión).
5. Una corrida con el frente sostenido por una ventana invisible (GameInputSvc) es VOID y se repite entera.

## Al congelar (2026-10-24 ~09:30), antes de extraer los 7z y sin haber visto ningún caso

- **HEAD final**: `int10f` 19be8b42a = int10c 46d4901d5 + `nb-vad-sin-torch` + `nb-laya-t6` (= int10e d7168fb7b) +
  `nb-core-motivo` (sólo diagnóstico) + `nb-f019-boton` (regla `named_control` de answer_check). `int10d` (sin
  `named_folder_theirs`) se descartó con datos: perdía E020 3/3 y no arreglaba E027.
- **Suites sobre 19be8b42a**: PC pytest 648, Kernel 741, Contracts 74, App 189, Setup 477, Providers 3067; NB pytest 647
  (1 omitida), App 189, Providers 3067 (sobre int10e; int10f no toca Providers).
- **Recursos** (NB, int10e, oído real): VRAM 3986 MiB (`vram_attribution` ok), producto con voz 3634 MiB.
- **Catálogos**: `catalog-base.json` 4441e3b8…5495; `catalog-final.json` b3184bed…315f; `catalog-v5final.json`
  b33d2b3a…41b1 (180 capacidades del HEAD final; 583 apps = las 600 de catalog-final menos las 17 herramientas).
- **7z comprobados** contra `metas.json`: decision.7z d7d2fcb8…86a5, e2e_falsedades.7z a3f201b8…c2ca.
- **Arnés común probado** en el PC: `inicio` y `maximo` con `scripts/renew` de int10f, decision3 de práctica sin errores
  (246 y 245, S1 sin consultas sin respuesta) y e2e E001-E002 2/2 cada uno con S1 encendido.
- **Regla del buzón**: el buzón está en el perfil del dueño (`C:\Users\usuario\BAXY-coord`) y el bench del PC lo cuenta como
  archivo del dueño cambiado; mientras el PC corre e2e o falsedades del holdout nadie escribe en él.
- **Límites conocidos antes de abrir** (práctica): E027 pregunta por texto antes de proponer el borrado en 2 de 3
  semillas desde w9-dudas (seguro; puede pedir el sí dos veces); `engine_no_answer` intermitente al abrir Steam en frío.
