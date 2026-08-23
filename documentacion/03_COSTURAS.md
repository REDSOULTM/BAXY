# Las costuras — por dónde se cambia BAXY

BAXY no se termina. Dentro de dos meses saldrá un STT mejor, un LLM más pequeño que
entiende igual, una cuantización que no rompe la prosa. **El código de hoy no tiene
por qué ser el de mañana.**

**BAXY entero es modular a propósito.** No sólo el LLM y la voz: la memoria, la
verificación, la automatización de aplicaciones, la capa visual, el journal — cada
pieza se cambia **una por una, sin reescribir el producto**.

Este documento dice **dónde está cada costura, qué mide su cambio, y qué hay puesto
hoy**. Cada goal que toca una pieza rellena su fila. El goal 11 no cierra con
ninguna vacía.

## Esto va en dos niveles, y confundirlos es el error

«Que todo sea modular» y «nada de sobreingeniería» sólo conviven si se separan dos
cosas que suelen ir juntas y no son la misma:

- **La forma del código** — que cada pieza tenga un borde y una responsabilidad.
  Esto **aplica a todo BAXY, sin excepción**, y no cuesta nada: es simplemente
  escribirlo bien. Sin esto, nada es sustituible jamás.
- **El mecanismo de cambio** — la medición que decide y la declaración en el
  manifiesto. Esto **sí cuesta trabajo**, así que se le pone a las piezas que de
  verdad se van a comparar contra un candidato. Ésas son las que están en el
  registro.

Dicho corto: **todo BAXY es modular; el registro es la lista de lo que además
tiene una forma medida de cambiarse.**

## Nivel 1 — la forma, que aplica a todo

Sin excepciones, en cualquier pieza que escribas:

- **Una responsabilidad por pieza.** Si al describir un fichero necesitas la
  palabra «y» tres veces, son tres piezas. `MainWindowViewModel` con 3.678 líneas
  y 169 miembros es el contraejemplo, y está dentro de este repositorio.
- **Nadie conoce las tripas de nadie.** Se depende del qué, no del cómo. Si cambiar
  el interior de A obliga a tocar B, no hay borde entre A y B.
- **Las dependencias apuntan hacia dentro.** `Contracts` no depende de nada,
  `Kernel` sólo de `Contracts`, los providers de ambos. Nunca al revés.
- **Nada global y mutable.** Un estado compartido que cualquiera toca es el
  acoplamiento que no se ve hasta que intentas cambiar algo.
- **Cero código muerto.** Lo sustituido se borra en el mismo cambio. Dos
  implementaciones vivas de lo mismo son la acumulación con otro nombre.

Esto es lo que hace que **cualquier** pieza de BAXY se pueda cambiar mañana, esté o
no en el registro. Es también, literalmente, lo que las cuatro versiones anteriores
no hicieron.

## Nivel 2 — el mecanismo de cambio

Una pieza del registro necesita tres cosas, y sin las tres no es sustituible **de
verdad**:

1. **Un borde que nombra qué hace, no cómo.** Es el nivel 1, ya lo tienes.
2. **La medición que decide si el candidato es mejor.** Esto es lo que de verdad
   hace sustituible una pieza: con un corpus y un número, cambiar de motor es una
   tarde. Con una interfaz preciosa y sin número puedes cambiarla, pero no puedes
   saber si has mejorado o empeorado — así que no la cambias nunca.
3. **La declaración en el manifiesto**, para que el cambio no pueda ser silencioso.

Lo que **no** hace falta y no se escribe: una interfaz con un solo implementador
«por si algún día», un registro de plugins, o configuración para elegir entre
implementaciones que no existen. Eso no es modularidad — es peso.

## Los tres tipos de borde, y cuál le toca a cada pieza

No todas las piezas se cambian igual. Hay exactamente tres formas, y ninguna
requiere un sistema de plugins.

### 1. Frontera de proceso — el LLM, el STT, el wake word, el TTS

Estas piezas **no viven dentro de la aplicación**. Corren como proceso aparte y
hablan por un protocolo versionado (`baxy.local.v1`) con mensajes tipados sobre
JSONL. El lado .NET conoce el protocolo, no el motor.

Consecuencia práctica: **cambiar el LLM no recompila nada**. Se apunta a otro
binario y a otro modelo, se corre la medición, y ya. Lo mismo para el motor de STT
o el de wake word.

Es la frontera más fuerte que hay y ya está construida. No la sustituyas por
llamadas en proceso «para ganar latencia» sin medir lo que pierdes en
sustituibilidad.

### 2. Frontera de contrato — verificación, providers, operación de apps

Viven dentro de .NET, detrás de `Baxy.Contracts` y `Baxy.Kernel`, que **no
dependen de nada**. El kernel autoriza; el provider ejecuta; el kernel no sabe cómo.

Cambiar una pieza aquí es escribir la implementación nueva y **borrar la vieja en
el mismo cambio**. Sin banderas, sin dos caminos vivos, sin interfaz nueva: el
contrato ya existe.

### 3. Frontera de datos — el catálogo, los corpus, los índices

El catálogo tipado es **datos, no código**. Cambiar su forma o su tamaño no es
refactorizar: es publicar otro catálogo y volver a medir.

## Cómo se declara una pieza: el manifiesto

Éste es el mecanismo que ata todo, y ya existe en el repositorio — se inventó en
R281 como auditoría y aquí se promueve a arquitectura.

Cada pieza sustituible se **declara** en el manifiesto de runtime: su nombre, su
**SHA-256** y su configuración. Así:

```json
"expected": {
  "ggufName": "gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf",
  "ggufSha256": "cd4526...",
  "llamaServerName": "llama-server.exe",
  "llamaServerSha256": "38a9d2...",
  "gpuLayers": 99
}
```

La razón está escrita en el propio artefacto, y vale para todas las piezas:

> Registrar la identidad aquí convierte un cambio silencioso de modelo en una
> compuerta roja.

Esa frase es la regla entera. **Ninguna pieza cambia en silencio.** Si el binario
que corre no es el declarado, la compuerta se pone roja. Eso es lo que hace que la
modularidad no se convierta en caos: puedes cambiarlo todo, pero no puedes cambiar
nada sin decirlo.

**El manifiesto está versionado** desde el goal 02. Declara su esquema
(`baxy-mind-runtime-v1`) y la expectativa publicada lo registra junto a la
identidad de cada pieza, así que un cambio de esquema no puede pasar por un campo
que falta. `tests/test_registered_runtime_expectation_r281.py` compara el
manifiesto vivo contra lo publicado —esquema, GGUF y `llama-server`, nombre y
SHA-256— y se pone rojo si alguno cambió.

## El registro

Cubre el producto entero, no sólo la pila del modelo. **Está abierto pero no es
libre:** se añade una fila cuando una pieza vaya a compararse de verdad contra un
candidato, y se añade **con su medición**. Una fila sin medición es una fila
mentirosa.

### La pila que entiende y decide

| Pieza | Borde | Qué decide el cambio | Elegido hoy | Goal | Fecha |
|---|---|---|---|---|---|
| **LLM decisor** | Proceso | **Existe y se corre**: `experiments/mind_router_spike/run_goal03_comprehension.py --gguf <candidato>` sobre `artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl` (SHA `761c1bc3…`, 124 dentro de catálogo + 36 fuera, es/en/spanglish, 24 % alcanzable por el reconocedor). Decide **cuatro columnas a la vez** y ninguna se negocia: decisión cruda correcta, tasa de punta a punta, **latencia hasta la primera señal** (p50/p90, listón 3 s) y **abstención honesta fuera de catálogo**. Un candidato que suba el acierto y baje la abstención se rechaza | **Qwen3-4B-Q4_K_M**, SHA `7485fe6f…`, elegido midiendo contra el heredado Gemma-4-E2B: decisión cruda **82/124 contra 63**, punta a punta **56/124 contra 49**, p90 **3,02 s contra 3,59 s**, 13 turnos sobre 3 s contra 34. Misma abstención (33/36 contra 34/36) | 03 | 2026-08-17 |
| **Cuantización** | Proceso | A/B de prosa española sobre el mismo modelo: seguimiento de instrucción, degeneración por repetición, palabras inventadas y latencia | **Qwen3-4B-Q4_K_M** (SHA `7485fe6f…`). No se baja: no hay GGUF más ligero del mismo modelo en disco. Q2 de Gemma 4 inventaba «fysico»/«lumínar» y rompía la persona (FunctionGemma, 2026-06); no se hereda como conclusión para Qwen3. La guarda de infinitivos inventados corre en `compose_user_message`. Corrida: `scripts/goal06_voice_sample.py` | 06 | 2026-08-23 |
| **Runtime de inferencia** | Proceso | La misma corrida de la fila de arriba con el **mismo GGUF** a ambos lados: lo que se compara es el runtime, así que el modelo se mantiene fijo y se leen latencia p50/p90 y decisión cruda. Un runtime que cambie el acierto con el mismo modelo está cambiando el decodificado, y eso hay que verlo antes de adoptarlo | llama.cpp b9980 (CUDA 12.4), `-ngl 99`, ctx 4096. Sostiene 122 turnos con p50 2,18 s y p90 3,02 s sobre Qwen3-4B. Aviso medido: `--reasoning-budget 0` no quita el *thinking*, hace que el borrador en inglés sea la respuesta | 01 → 03 | 2026-08-17 |
| **Recuperador / embeddings** | Datos | `experiments/mind_router_spike/compare_goal03_retrieval.py`: fracción de filas en que la operación esperada entra en el shortlist, más recall@1/3/5/8 y **el número de candidatos que recibe una petición fuera de catálogo**. Se rankean **operaciones, no familias** — rankear familias y repartir plazas dentro medía 73/124 contra 102/124. Y el score **no** sirve de abstención: la separación entre dentro y fuera de catálogo es de 0,026 sobre una banda de 0,05 | **e5-small multilingüe**, documentos del lado `passage:` y scores reescalados a 0–1 por consulta antes de mezclar el bonus léxico. Ofrece la esperada en **103/124** vivo (73 antes). El MiniLM-L12 de FunctionGemma se descarta: su 0,9521 es a granularidad de 31 herramientas, o sea familia, y el fallo está en la hoja dentro de la familia | 01 → 03 | 2026-08-17 |
| **Reconocedor determinista** | Contrato | **Cuatro números, y el cuarto es el que decide si vale la pena**: cuántas filas reclama, cuántas acierta, cuántas peticiones fuera de catálogo reclama por error, y **cuántas de esas mismas filas sirve el camino por modelo cuando se le quita**. Sin el cuarto no se sabe si 12.310 líneas de reglas están aportando o estorbando. La tercera sigue siendo la que veta: un reconocedor que reclama algo que no sabe hacer produce un efecto no pedido | 12.310 líneas de reglas en `effect_intent.py`. El 03B dejó la declinación del verificador de identidad **fuera** de la retirada. El 03C **no la reactiva**: suma dos hojas explícitas (cancelar la descarga de Steam, scroll) y el camino explícito pasa de 56 a **58/124**. «para la descarga que tiene steam corriendo» y «scroll down a bit» no son `_is_direct_request`, se resuelven antes de esa puerta | 03 → 03B → 03C | 2026-08-21 |
| **Forma del catálogo** | Datos | **Cobertura y cuenta a la vez, y la cobertura primero.** `measure_goal03_catalog_coverage.py` enumera lo que la persona puede pedir —una entrada por operación alcanzable, sellada por el SHA-256 de su contrato— y publica el sello **antes** de tocar nada; sin eso no se distingue consolidar de amputar. Después, pass-rate de punta a punta antes y después. `compare_goal03_catalog_form.py` compara específica contra paramétrica a cobertura constante | **169 operaciones, 158 alcanzables, 31 familias**, sello `dc0a7893…` — sin cambio, y **no se consolidó a propósito**. La paramétrica gana la recuperación (r@5 0,871 contra 0,710, rango medio 2,95 contra 10,07), pero su premisa se midió y es falsa: bajar el shortlist de 28 a 8 candidatos sólo sube el acierto condicionado del decisor de 79,6 % a 82,4 % y cuesta 12 filas de recuperación. **El decisor no está limitado por cuántos candidatos ve**, así que consolidar pagaría el riesgo de Carter (75,93 % → 62,96 %) por una ganancia que no está donde se creía | 01 → 03 | 2026-08-17 |
| **Puerta de alcance (abstención)** | Contrato | Dos números que se leen juntos y nunca uno solo: **cuántas propuestas legítimas conserva** y **cuántas peticiones fuera de catálogo rechaza**, sobre el corpus fresco. Desde el goal 03B hay un tercero que cambia cómo se leen los dos primeros: **qué hace con lo que retira**. Retirar ya no es negar la capacidad — es retenerla hasta que la persona confirme la invocación exacta — así que el sobreveto se paga en preguntas, no en respuestas perdidas. Un candidato que suba el rechazo bajando la conservación se sigue rechazando | La puerta léxica curada **sin fail-closed por verbo extra** en bluetooth/wifi (goal 04): «apagame el bluetooth» y «drop the wireless connection» ya no mueren por ausencia de lista. Veredicto ternario del 03B y contradicción near-miss del 03C intactos. No hay un sexto gate. Medición de honestidad: scorer `score_goal04_honesty.py` SHA `3e565f60…` | 03 → 03B → 03C → 04 | 2026-08-21 |
| **Verificador de identidad de operación** | Proceso | **Dos números sobre las propuestas crudas ya registradas, y ninguno se lee solo**: cuántas propuestas correctas conserva y cuántas equivocadas rechaza (`probe_current_catalog_leaf_compatibility.py`), más el efecto de punta a punta de las dos cifras juntas sobre el corpus fresco — filas servidas y abstención honesta — porque un verificador laxo se paga en preguntas inútiles y uno estricto en capacidades negadas. Compara candidatos con `probe_goal03b_second_opinion_variants.py`, que los corre lado a lado sobre la misma telemetría | El prompt de identidad de hoja (`OPERATION_IDENTITY_PROMPT`) sobre el mismo Qwen3-4B, 24 tokens y decodificado acotado por schema, **p50 0,15 s**: conserva 46 de 48 propuestas correctas y rechaza 21 de 84 equivocadas. El de producto (`OPERATION_COMPATIBILITY_PROMPT`) conserva 10 de 48 y se queda donde guarda una ejecución. Rechazado: preguntar la contrapositiva al mismo peso, que dice que sí a las dos lecturas (0 de 43 filas sobrevivían) | 03B | 2026-08-19 |
| Planificador de misiones | Contrato | | | 07 | |

### La pila de voz

| Pieza | Borde | Qué decide el cambio | Elegido hoy | Goal | Fecha |
|---|---|---|---|---|---|
| **Wake word** | Proceso | Corpus positivo y negativo con voz real: máximo de score en cada uno y falsos disparos por hora. Medido hoy sobre el modelo heredado: positivo **0,916**, negativo **0,225 con 0 disparos**, RTF 0,026 | `baxy.onnx` (openWakeWord: mel → embedding → cabeza) + verificador logreg. **Funciona pero está apagado**: `wake_manifest` es `null` | 01 → 09 | 2026-08-16 |
| **STT** | Proceso | WER en español, inglés y spanglish, RTF y **recuperación de nombres propios** — que es donde está el fallo, no en la palabra común | Parakeet TDT 0.6b v3 int8: RTF 0,065–0,087, 1 error en 47 palabras de español. Pero transcribe «BAXY» como «Maxi» / «Bacxi» | 01 → 09 | 2026-08-16 |
| **TTS** | Proceso | | | 09 | |

### La pila que actúa sobre la máquina

| Pieza | Borde | Qué decide el cambio | Elegido hoy | Goal | Fecha |
|---|---|---|---|---|---|
| Verificación de efectos | Contrato | **Matriz `documentacion/base/05_MATRIZ_EJECUCION.json`:** 170 operaciones del catálogo tipado, cada una con postlectura directa del estado reivindicado o razón de no verificable. Un observador candidato se mide contra las mismas filas: mismas observaciones, mismo degradado honesto. Un recibo simulado (`Verified=true`, `actualEffectsExecuted=0`) no cuenta. Tres provocaciones de ejecutor mentiroso (audio, app.open, note.create) tienen que seguir en `failed` / no «Listo» | Postlecturas directas por operación: Core Audio `GetStatus` aparte del setter, inventario HWND/proceso aparte del lanzador, reapertura de nota/CAS. Cero registro de estrategias. `VerifierContractId` es identidad de catálogo | 05 | 2026-08-21 |
| Automatización de apps (UIA) | Contrato | | Sólo `WindowsDeviceControlAdapter.cs` toca UIA en C#; el UIA real vive en `DesktopClickVisible.ps1` y `DesktopSelectAll.ps1`, ya sin nombre de aplicación | 01 → 07 | 2026-08-16 |
| OCR | Proceso | | Tesseract 5.4.0 vía `CaptureVisionAdapter.cs`. **Le falta `spa.traineddata`**: hoy sólo tiene `eng` y `osd` | 01 → 07 | 2026-08-16 |
| Motor de visión | Proceso | | | 07 | |

### El producto alrededor

| Pieza | Borde | Qué decide el cambio | Elegido hoy | Goal | Fecha |
|---|---|---|---|---|---|
| Almacén de memoria | Contrato | | | 10 | |
| Journal de invocaciones | Contrato | Tres números sobre el mismo `invocationId`: (1) un `failed` con `effectMayHaveOccurred` se asienta y la segunda ejecución es replay — el handler no corre; (2) `pending` no asienta y el mismo id reintenta; (3) un token de confirmación no autoriza otro `invocationId`. Integridad HMAC/ancla ya la miden `FileInvocationJournalTests` | `FileInvocationJournal` JSONL + HMAC; replay de respuestas terminales. `pending` (reintentable y `confirmation_required`) no se journala como terminal | 05 | 2026-08-21 |
| Capa visual (bandeja / WebView) | Contrato | | | 10 | |
| Instalación y arranque | Contrato | | | 10 | |

**Las columnas:**

- **Borde** — cuál de los tres tipos de arriba. Determina qué cuesta cambiarla.
- **Qué decide el cambio** — el corpus o banco, el número que hay que batir, y
  dónde está el procedimiento. **Es la columna importante.** Sin ella la pieza no
  es sustituible aunque tenga el mejor borde del mundo.
- **Elegido hoy** — qué está puesto y por qué ganó.
- **Goal** — quién rellenó la fila.
- **Fecha** — cuándo se midió. Una medición de hace ocho meses decidió entre
  candidatos que hoy ya no son los mejores: la fecha es lo que avisa de que toca
  volver a mirar.

## Cómo se sustituye una pieza, dentro de dos meses o de dos años

1. Se lee la fila: qué medición decide.
2. Se corre esa medición sobre el candidato nuevo, **sin tocar el umbral**. Si el
   resultado no llega, la respuesta es otro candidato, no un umbral más laxo.
3. Si gana, entra — se actualiza el manifiesto con su nombre y su hash, y la
   implementación anterior **se borra en el mismo cambio**.
4. Se actualiza la fila con lo elegido y la fecha.

Nada de esto exige reabrir el producto ni volver a discutir la arquitectura. Ése es
el punto entero: que mejorar BAXY sea una tarde, no una quinta reescritura.
