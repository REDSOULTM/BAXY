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
- **`%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json`** — el runtime apunta a `Programacion\BAXY\legacy\models\artifacts\` para `llama_server`, o sea al repositorio del cuarto intento; si alguien borra o mueve `BAXY`, este repositorio se queda sin motor de inferencia y sin wake word. Lo dispararía cualquier limpieza de la carpeta `Programacion`. **El goal 03 cerró dos tercios de esto**: `python_path` apuntaba a `Programacion\BAXY\src` —o sea que toda medición hecha aquí ejecutaba el `baxy_mind` del intento anterior— y ahora apunta a este repositorio; y `gguf` apunta a `D:\BAXYRuntimessets\models\Qwen3-4B-Q4_K_M.gguf`. Queda `llama_server`. *Goal 01 → parcialmente cerrado por el 03.*
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
- **`tests/data/historical_messages.jsonl` ya está versionado, y son datos privados.** El goal 02 lo comprometió porque decenas de pruebas .NET y Python lo leen por esa ruta, `.gitattributes` fija sus finales de línea, sus dos hermanos del mismo corpus ya estaban rastreados y sin él un clon limpio no puede pasar la compuerta. Pero `TURN_EVIDENCE_DATA_NOTICE.md` lo declara **dato privado local que no debe publicarse como dataset**, y el remoto `origin` es GitHub: **no debe empujarse a un remoto público**. Decidir si se queda así, se mueve a LFS o se sustituye por un derivado sin texto. *Goal 02.*
- **La puerta de dominio curada cuesta 26 de 82 decisiones correctas** — `src/baxy_mind/effect_intent.py`, `_curated_domain_is_grounded`. Es una lista de vocabulario por familia y falla en paráfrasis fresca y en inglés: veta `bluetooth.radio.set` para «apagame el bluetooth» y `wifi.disconnect` para «drop the wireless connection». **No se toca porque es lo único que sostiene los cero efectos no pedidos**: sin ella la comprensión sube a 66,9 % y 20 de 36 peticiones fuera de catálogo ejecutan algo. Lo que falta es un detector de fuera de dominio que no sea vocabulario ni score — los datos ya están mapeados en `src/baxy_mind/data/mtop_turn_evidence_map.v1.json`, que declara `ood_intents`. Medido en `documentacion/base/03_COMPRENSION.md` §6. *Goal 03.*
- **El relleno de argumentos acierta 30,8 % y pregunta lo que ya está dicho** — 14 de 26 filas con el valor inequívoco en el texto contestan con una pregunta inútil: «abrime la carpeta de descargas» pregunta «¿abrir la carpeta de descargas?». No depende del decisor (Gemma 34,6 %, Qwen3 30,8 %) ni lo movió este goal. Lo dispararía cualquier petición con argumentos; hoy no bloquea porque la operación se elige antes. *Goal 03.*
- **49 de 158 operaciones siguen sin ninguna regla de dominio curada** — la puerta devuelve `None` para ellas y sólo `filesystem.` tiene un suelo genérico. Lo dispararía una propuesta del modelo sobre una de esas familias ante una petición fuera de catálogo, como el `window.active` que «prende las luces del living» recuperó. *Goal 03.*
- **`_post_native_tool_selection` quedó sin usar por defecto** — el contrato de tool-call forzado se midió y se rechazó (+3 decisiones crudas, −8 abstenciones honestas), y ahora sólo lo enciende `BAXY_MIND_NATIVE_TOOL_POLICY=1`. Borrarlo entero toca `decide_turn` en varias ramas y merece su propio cambio; no bloquea porque ninguna ruta de producto lo alcanza. *Goal 03.*
- **El sello `wake-validation-program-tree` cubre todo `src/baxy_mind`** — cinco programas de `experiments/stt_quality` congelan el árbol de `experiments/voice_latency`, `scripts` y `src/baxy_mind` antes de abrir un holdout ciego de STT. Cualquier cambio de la política de turno, del planner o del cliente LLM lo pone rojo aunque el evaluador de STT no ejecute nada de eso. Repinado en este goal de `22f3bd4e…` a `b62972b6…`; lo dispararía el siguiente goal que toque el mente. *Goal 03.*
- **Los primeros ~15 s tras arrancar, la recuperación es léxica** — `PlannerCatalog` se publica con ranking por solapamiento de tokens y se promociona a E5 cuando el worker del encoder termina de cargar. Es correcto para un producto que arranca con Windows y se queda, pero un turno en esa ventana recupera peor. Lo dispararía pedirle algo a BAXY nada más encender. *Goal 03.*
- **El corpus fresco del goal 03 lo escribió el modelo que hizo el goal** — 160 filas de autoría propia. Su independencia del reconocedor sí está medida (24 % de alcance), pero no es una población recogida de uso real. Lo dispararía tratar su 46,0 % como el número de producto en vez de como el número de este instrumento. *Goal 03.*
- **El reconocedor determinista sirve 26 de las 38 filas que reclama, y sus 12 errores son silenciosos** — resuelve una hermana y nadie se entera: «dejame el sonido a la mitad» acaba en `audio.status`. Se conserva porque el camino por modelo sirve 24 de esas mismas 38, o sea que gana por dos, y responde en 7 ms contra 2 s. Lo que falta es que **decline cuando duda**: un oráculo que eligiera por fila daría 29 de 38. Lo dispararía cualquier paráfrasis que caiga dentro de su gramática por accidente. *Goal 03.*
- **Las operaciones de argumento libre son sumideros de alcance** — `task.create`, `note.create`, `message.send` y `web.search` aceptan cualquier texto, así que `task.create("pedir un taxi")` es válido contra su schema. Once de cada veinte peticiones fuera de catálogo aterrizan ahí, y por eso ninguna abstención basada en contratos puede ser completa. Lo dispararía cualquier petición fuera de catálogo con forma de encargo. Medido en `documentacion/base/03_COMPRENSION.md` §6. *Goal 03.*
- **MTOP quedó descargado en `D:\BAXYRuntime\datasets\mtop-v1`** (8,6 MB de zip, 30 MB extraídos, SHA-256 verificado contra el declarado en el árbol) y su corpus de desarrollo construido. El test oficial sigue sellado y sin abrir. No bloquea nada; es espacio en disco y un activo para quien retome el alcance. *Goal 03.*
- **`.gitattributes` declara `* text=auto eol=lf` y Python en Windows escribe CRLF** — cualquier fichero regenerado con `write_text` sale con CRLF y su SHA-256 muere en el primer checkout limpio, que es el fallo que R277 diagnosticó. Y la mitad de `artifacts/` está comprometida con CRLF **en el índice** sin declaración `-text`, así que renormalizarla mueve hashes publicados. No hay nada en el árbol que avise: lo dispararía cualquier goal que regenere un fichero sellado. *Goal 03.*
- **`git config core.longpaths` no viaja con el repositorio** — sin él, `git worktree`/`clone` fallan con `Filename too long` sobre los artefactos de nombre largo, aunque Windows tenga `LongPathsEnabled=1`. Es provisión de máquina y está en `documentacion/base/00_COMPUERTA.md` §11; no hay forma de declararlo desde el árbol. *Goal 02.*
