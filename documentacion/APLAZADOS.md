# Aplazados

Lo que se vio de pasada durante los goals 01–10 y **no se persiguió**, porque
no bloqueaba: fragilidades teóricas, caminos de error que nadie ha recorrido,
«esto podría fallar si…».

No es una lista de pendientes que se ignora. Es la entrada del **goal 11**, que
existe para vaciarla: cada línea acaba arreglada, medida y descartada, o
declarada limitación ambiental con su degradado.

## Cómo se anota

Una línea por hallazgo. Con esto basta:

- **Dónde** — fichero y línea, o el componente.
- **Qué podría pasar** — el fallo concreto, no la categoría.
- **Qué lo dispararía** — la condición que haría que ocurriera de verdad.
- **Goal** que lo vio.

No inviertas tiempo en investigarlo: si lo estás investigando, ya dejó de ser un
aplazado y se convirtió en trabajo. Anótalo en una línea y sigue.

Si al anotarlo te das cuenta de que **sí bloquea** —de que alguien lo va a ver
mañana usando BAXY con normalidad— entonces no es de aquí: arréglalo en tu
goal.

## Anotaciones

<!-- Una línea por hallazgo. Formato libre, pero que se entienda sin contexto. -->

- **`src/Baxy.App/MainWindowViewModel.cs`** — quedan ~1.050 líneas de máquina de estados del turno (ejecución de plan multipaso + flujo de confirmación de memoria) sin descomponer, porque comparten `_pendingMindPlan`, `_planStore` y `AddMessage`; separarlas pide un colaborador con estado, no una extracción. No bloquea: compila y pasa. *Goal 01.*
- **`%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json`** — el runtime del BAXY actual apunta a `Programacion\BAXY\legacy\models\artifacts\`, o sea al repositorio del cuarto intento. Si alguien borra o mueve `BAXY`, este repositorio se queda sin modelo, sin llama-server y sin wake word. Lo dispararía cualquier limpieza de la carpeta `Programacion`. *Goal 01.*
- **Tesseract 5.4.0** — instalado y en PATH, pero sólo con `eng` y `osd`: **falta `spa.traineddata`**. El escalón OCR de la cascada leería español con el modelo inglés. Lo dispararía cualquier `ocr.read` sobre una ventana en español. *Goal 01 → lo necesita el 07.*
- **Wake word apagado** — `wake_manifest` es `null` y `wake_on_start` es `false` en el runtime, aunque `baxy.onnx` funciona (máx 0,916 en positivo, 0 disparos en negativo). Falta escribir su manifiesto. *Goal 01 → lo necesita el 09.*
- **STT y nombres propios** — Parakeet transcribe «BAXY» como «Maxi» / «Bacxi» / «Báxi» sobre voz humana real. El problema está documentado en `biasing_options.md` y sigue abierto; no bloquea porque el wake word es acústico y no depende de la transcripción. *Goal 01 → lo necesita el 09.*
- **`llama-server --reasoning-budget 0`** — en b9980 con la plantilla de Gemma 4 no quita el *thinking*: deja de separarlo y el borrador en inglés pasa a ser la respuesta visible. Lo dispararía usar esa bandera para recortar latencia. *Goal 01 → lo necesita el 06 y el 08.*
- **`Baxy.Setup`** — 13.194 líneas de producción y 10.068 de pruebas (17,8 % de `src/`) para una instalación certificada que está fuera de alcance. No se tira porque funciona, pero distorsiona cualquier cuenta de tamaño del repositorio. *Goal 01.*
- **13 GGUF de FunctionGemma** (5,8 GB) y **17 GB en `Probando Gemma 4/models/`** — iteraciones de fine-tuning que ya no se van a usar. No bloquea nada; es espacio en disco. *Goal 01.*
- **La poda de la importación dejó fuera 453 ficheros** que `Programacion\BAXY` sí versionaba. El goal 02 recuperó los 11 que las pruebas leían; los ~440 restantes (sobre todo `artifacts/development`, `product`, `research`, `fixes`, `holdout`) siguen ausentes. Lo dispararía cualquier prueba o documento futuro que cite uno. Se ve con `git ls-files` en los dos repositorios y `Compare-Object`. *Goal 02.*
- **Dos entradas de campaña perdidas para siempre** — `artifacts/development/bge_m3_operation_recovery_r160_attested.json` no está en ninguna carpeta de esta máquina, y el checkpoint `D:\BAXYRuntime\experiments\mtop-operation-compatibility-verifier-v16` de R208 tampoco (sólo queda `r242-cuda`). Sus preregistros publicados sí están y se auditan por sello; lo que no se puede es reconstruirlos. *Goal 02.*
- **`baxy_legacy_checkpoint` sigue colgando** — `artifacts/corpus_cutoff/source_manifest.json` declara también el commit `ee06786b…`, que no está en este repositorio. Hoy no lo pide nadie porque resuelve rutas bajo `/legacy/` y ese directorio no existe aquí. Lo dispararía traer `legacy/` de vuelta. *Goal 02.*
- **`experiments/mind_router_spike/.venv`** — el venv 3.10 que creó el goal 01 sigue en disco y ya no lo usa nadie: `FindPython` resuelve el intérprete del sistema. Es espacio, no un fallo. *Goal 02.*
- **`git config core.longpaths` no viaja con el repositorio** — sin él, `git worktree`/`clone` fallan con `Filename too long` sobre los artefactos de nombre largo, aunque Windows tenga `LongPathsEnabled=1`. Es provisión de máquina y está en `documentacion/base/00_COMPUERTA.md` §11; no hay forma de declararlo desde el árbol. *Goal 02.*
