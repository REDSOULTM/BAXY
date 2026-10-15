# Fallos multipaso en p7-e2e y p8-e2e: diagnóstico y propuestas de presentación

Fuentes leídas: `D:\BAXYeval\renew_v1\runs\pc\p7-e2e` y `p8-e2e` (`results.jsonl`, `events.jsonl` con cada `step`: operación, argumentos, observación; `E0xx\replies.json`, `speech.json`, `console.txt`), `D:\BAXYeval\renew_v1\e2e\practice.json`, `e2e\lib\bench.ps1`. Del repo (sólo lectura): `src/baxy_mind/mind.py`, `src/baxy_mind/data/tool_descriptions.en.v1.json`, `src/Baxy.Kernel/Operations/ProductCatalog.cs`, `src/Baxy.App/NativeTurnLoop.cs`, `src/baxy_mind/llm_server.py`, `src/Baxy.Providers.Windows/External/WindowsKnownFileAdapter.cs`. No abrí nada sellado.

Commits medidos: p7 = `bde62d76c`, p8 = `44d1f59fa`. HEAD (`9a27765a2`) ya trae, después de p8, el significado del argumento `offset` en `web.fetch` y `file.read`, y la regla 2 ampliada («cómo está algo del PC»). Las propuestas de abajo se escriben sobre HEAD.

Totales: p7 19/30, p8 17/30. Los fallos de p7 son un subconjunto de los de p8. **Pasan en p7 y fallan en p8: E018 y E022.** No hay ningún caso que falle en p7 y pase en p8.

---

## 1. Casos que fallan

Cuento como multipaso los casos que piden dos o más llamadas, o una llamada más una confirmación: E017, E018, E019, E020, E021, E022, E024, E027 y E015. E006, E014, E028 y E029 son de un paso, pero los incluyo al final de la tabla porque caen en los mismos patrones y se arreglan con las mismas propuestas.

| Caso | Pedido | Oráculo | p7 | p8 | Llamadas (args → observación) y punto exacto del fallo |
|---|---|---|---|---|---|
| **E017** | «abre el bloc de notas, escribe 'lista: pilas, cables' y guárdalo como lista.txt en C:\Users\usuario\BAXY-bench» | `BAXY-bench\lista.txt` contiene el texto | ✗ | ✗ | p7: `app.open{appId:"Notepad++"}` (otra app, no el Bloc de notas) → `input.visible.controls` → `input.text.type` ✓ → `file.write{relativePath:"lista.txt", folder:"home"}` → `fullPath C:\Users\usuario\lista.txt`. p8: `app.open{"Bloc de notas"}` → controls → `input.select.all` falla (efecto incierto) → `text.type` ✓ → el mismo `file.write` sin `BAXY-bench`. **Fallo: argumento equivocado (se pierde la subcarpeta).** Después **nota la diferencia y pregunta en vez de corregir**: «se guardó en C:\Users\usuario\lista.txt, no en BAXY-bench… ¿Quieres que lo mueva?». Además se salta el diálogo Guardar y usa file.write; el oráculo no lo exige. |
| **E018** | «¿cuántas líneas tiene registro.log de la carpeta BAXY-bench de mi usuario?» | la respuesta dice 137 | ✓ | ✗ | p7 (bien): `file.find{folder:"home", query:"registro.log"}` → `relativePath "BAXY-bench\registro.log"` → `file.read{fileName:"BAXY-bench\\registro.log", folder:"home"}` → `totalLines 137`. p8: `filesystem.list{limit:100}` (la carpeta de trabajo de BAXY) → `{"entries":[],"count":0}` → «No hay archivos en la carpeta de trabajo de BAXY. ¿Te refieres…?». **Fallo: herramienta equivocada en el paso 1, y luego se rinde** con una pregunta en vez de buscar con file.find. |
| **E019** | «en C:\Users\usuario\BAXY-bench crea una carpeta proyecto con las subcarpetas src, docs y tests» | existen `BAXY-bench\proyecto\{src,docs,tests}` | ✗ | ✗ | En los dos: 4× `filesystem.create.directory{relativePath:"proyecto[/src…]", folder:"home"}` → `fullPath C:\Users\usuario\proyecto\…`. **Fallo: argumento equivocado (falta `BAXY-bench/`)** y **afirma algo que el resultado contradice**: «Creé la carpeta proyecto… en C:\Users\usuario\BAXY-bench», con los cuatro `fullPath` delante. |
| **E020** | «¿cuál es el archivo más grande dentro de BAXY-bench, en mi carpeta de usuario?» | la respuesta nombra b.dat | ✗ | ✗ | En los dos: `filesystem.list{limit:100}` → vacío → «No hay archivos en mi carpeta de trabajo…». **Fallo: herramienta equivocada** (lo correcto era `file.find{folder:"home", subdirectory:"BAXY-bench", order:"size"}`) y **se rinde** con un resultado vacío que no dice de qué carpeta habla. |
| **E021** | «ejecuta python --version en la terminal y dime qué versión sale» (respuesta «sí») | la respuesta trae la versión real (3.10.11) | ✗ | ✗ | `shell.command.run{command:"python --version"}` → `needs_confirmation` → «¿Quieres ejecutar eso?» (no nombra el comando, contra la regla 8). Llega «sí» → **vuelve a llamar a `shell.command.run`, no a `confirm_pending`** → otra vez `needs_confirmation`. Después, p7 dice «No puedo ejecutar comandos en la terminal.» (falso) y p8 publica como pregunta de confirmación el XML crudo `<tool_call><function=shell_command_run>…` (ver §4). En p8 el `next` ya decía «call confirm_pending with their answer». **Fallo: repite la llamada original en vez de dar la respuesta.** |
| **E022** | «lee https://www.rfc-editor.org/rfc/rfc2324 y dime qué código devuelve una tetera» | 418 | ✓ | ✗ | p7 (bien): `web.fetch{url, maximumCharacters:5000}` → `hasMore:true, nextOffset:5000` → `web.fetch{url:finalUrl, offset:5000}` → lee §2.3.2 → «418». p8: `web.fetch{url}` → `nextOffset:4000` → **9 veces más `web.fetch{url:"…/info/rfc2324/"}` sin `offset`**, con el mismo resultado cada vez → el turno termina con `failure: decision_unavailable` y sin respuesta (probable desborde de contexto, §4). **Fallo: ignora `nextOffset` y repite la misma llamada.** |
| **E024** | «añade al final de notas.txt, en la carpeta BAXY-bench, la línea 'revisar el router'» | `BAXY-bench\notas.txt` = uno/dos/tres/revisar el router | ✗ | ✗ | p7: `file.write{relativePath:"notas.txt", folder:"home", append:true}` → `fullPath C:\Users\usuario\notas.txt` (un notas.txt que ya estaba ahí de antes: `size 74`). **Fallo: falta la subcarpeta.** p8: `file.write{notas.txt, home}` **sin `append`** → `version_conflict` → `file.read` → `known_file_ambiguous` con los candidatos `notas.txt` y `BAXY-bench\notas.txt` → `file.write{relativePath:"BAXY-bench/notas.txt"}` (ruta ya correcta), **pero sin `append` ni `expectedSha256`** → `version_conflict` 12 veces más (una con `expectedSha256:""`) → límite de 15 pasos → «hay un conflicto de versiones». **Fallo: falta un argumento (`append`) y repite la llamada; el error no dice qué cambiar.** |
| **E027** | «borra viejo.txt de la carpeta BAXY-bench» (respuesta «no») | el archivo sigue + la pregunta de confirmación se dijo en voz alta | ✗ | ✗ | `filesystem.known.trash.named{fileName:"viejo.txt", folder:"all_known"}` → `known_file_not_found` → «¿Podrías indicarme la ruta exacta?». **Fallo: argumento equivocado** (`all_known` no incluye la carpeta de usuario, ver abajo), **se salta el paso de buscar** (`file.find`) **y se rinde**. Como nunca llega a la confirmación, falla el oráculo de voz. |
| **E015** | «abre Steam y ve a la biblioteca» | el OCR de Steam muestra ≥4 títulos de una lista fija | ✗ | ✗ | p7: `app.open{Steam}` (`alreadyRunning:true`) → controls (la biblioteca ya está visible: «De tu biblioteca de Steam», lista de juegos) → `input.visible.click{label:"BIBLIOTECA"}` → `selected:true, surfaceChanged:true` → respuesta correcta. p8: el click da `visible_click_postread_invalid, effectUncertain` → vuelve a mirar → «estoy en la página principal… te la indico para que la pulses» (cuenta mal lo que muestra la vista). **Es sobre todo un problema del oráculo** (§4). |
| E006 (1 paso) | «crea compras.txt en C:\Users\usuario\BAXY-bench que diga…» | existe `BAXY-bench\compras.txt` | ✗ | ✗ | `file.write{relativePath:"compras.txt", folder:"home"}` → `C:\Users\usuario\compras.txt`. **Mismo fallo de ruta** que E017, E019 y E024. |
| E014 (1 paso + recuperación) | «abre la configuración de sonido» | la ruta de Configuración termina en «Sonido» | ✗ | ✗ | p7: 15× `app.open{appId:"Configuración del sistema", place:"sound"}` → `place_not_of_application, placeIn:["Configuración"]`, idéntico cada vez → límite de pasos. **La observación trae el appId correcto y aun así repite la llamada 15 veces.** p8: abre msconfig sin `place`, prueba clicks en «Sistema», cierra y reabre 3 veces (125 s). La descripción ya avisa «Configuración del sistema is msconfig», pero el 4B elige por el parecido del nombre. |
| E028 (1 paso) | «sube el volumen a 40» | 40 | ✗ | ✗ | `audio.volume.adjust{direction:"down", amount:100}` (p8: `amount:60`) → `level 0` → «bajó hasta 0. ¿Quieres que lo suba a 40?». **Herramienta y dirección equivocadas, y nota el error pero pregunta en vez de corregir.** La descripción de `audio.volume` ya cubre «sube el volumen al 80». |
| E029 (imposible) | «pídeme una pizza…» | dice que no puede | ✗ | ✗ | No llama a ninguna herramienta: «¿A qué dirección…?». Gana la regla 3 (falta un dato) sobre la regla 4 (eso no lo hago). No es multipaso. |

**Datos del entorno que explican parte de lo anterior** (detalle en §4): `all_known` = Escritorio + Documentos + Descargas, **sin** la carpeta de usuario (`WindowsKnownFileAdapter.cs:1029-1033`). Sin embargo, `file.find` lo presenta como «Desktop, Documents, Downloads, the user's home folder, or all». Y el banco no limpia `C:\Users\usuario\` (sólo vigila Escritorio, Documentos y Descargas), así que los archivos que el modelo escribió ahí se acumulan de corrida en corrida.

---

## 2. Patrones

| # | Patrón | Casos | Qué hace el modelo |
|---|---|---|---|
| **A** | **Subcarpeta nombrada que se pierde en la ruta** | E006, E017, E019, E024-p7 (y E027 por `all_known`) | Convierte «C:\Users\usuario\BAXY-bench» en `folder:"home"`, pone sólo el nombre del archivo en `relativePath` y tira `BAXY-bench`. 0 de 5 cuando la carpeta viene del pedido. 2 de 2 cuando la ruta la dio una herramienta (E018-p7 con file.find, E024-p8 con los candidatos): **copia bien una ruta que ve en un resultado y compone mal una que tiene que armar.** |
| **B** | **«Carpeta BAXY-bench» confundida con la carpeta de trabajo de BAXY** | E018-p8, E020 (×2) | Elige `filesystem.list` (el sandbox) porque el nombre contiene «BAXY». El resultado vacío no dice de qué carpeta habla, así que el modelo se rinde y pregunta. |
| **C** | **Repetir la misma llamada ignorando lo que dice el resultado** | E014-p7 (×15), E022-p8 (×10), E024-p8 (×13), E021 (×2), E014-p8 | El error o el resultado traen el dato para avanzar (`placeIn`, `nextOffset`, los candidatos), o no traen ninguno (`version_conflict` a secas), y el modelo vuelve a mandar la llamada idéntica. A temperatura 0.2 con seed fija, una conversación que ya repitió se refuerza sola (*self-reinforcement*). El resumen «[En este turno: …]» no muestra que son llamadas iguales con resultados iguales. |
| **D** | **Notar que el resultado no es lo pedido y preguntar en vez de corregir; o afirmar lo pedido aunque el resultado diga otra cosa** | E017, E028 (preguntan), E019 (afirma BAXY-bench con `fullPath` en contra), E015-p8 | La regla 2 manda contar sólo lo que muestran los resultados, pero no manda comparar el resultado con el pedido ni corregir. |
| **E** | **La confirmación vuelve como una llamada nueva a la herramienta original** | E021 (×2), y es el riesgo detrás de E027 y E030 | Tras «sí», el modelo reproduce lo que vio en el entrenamiento (la persona aprueba → llama a la herramienta). `confirm_pending` es una herramienta genérica entre 187, y la respuesta llega como un mensaje de usuario más, lejos del resultado `needs_confirmation`. |
| **F** | **Paginación no seguida** | E022-p8 | Parte de C: tiene `nextOffset` y no lo usa. En p8 `offset` no tenía significado en el argumento (en HEAD ya lo tiene). |

---

## 3. Propuestas (pocas y de alto impacto)

Una nota sobre dónde poner cada cosa. El propio `mind.py` dice que la plantilla de Qwen3.5 pone las herramientas **antes** del texto de sistema. Las descripciones quedan entonces a unos 36 mil tokens del final: el prefijo medido en los logs de llama-server del notebook, `%LOCALAPPDATA%\BAXY\renew\bench-nb-r4.log`, ronda los 35 900 tokens. Lo que más pesa en un 4B es lo que queda cerca del final: el último resultado y el resumen «[En este turno…]». Lo menos eficaz es una frase más dentro de una descripción. Por eso priorizo **la redacción de los resultados y el resumen del turno**, después las reglas del sistema y al final las descripciones (Liu et al., *Lost in the Middle*, https://arxiv.org/abs/2307.03172).

### P1 — Resultados que dicen qué hacer después (`next` con valores concretos)
**Arregla:** E014, E022-p8, E024-p8, E027, E020/E018-p8 (patrones C y F, y en parte B).
**Fuentes:** Anthropic, *Writing effective tools for agents* (https://www.anthropic.com/engineering/writing-tools-for-agents): «If you choose to truncate responses, be sure to steer agents with helpful instructions» y «prompt-engineer your error responses to clearly communicate specific and actionable improvements». El modelo de Qwen3.5 y la guía de Qwen sobre function calling (https://qwen.readthedocs.io/en/latest/framework/function_call.html) dicen que el modelo no siempre sigue el protocolo, así que lo que necesita para seguir tiene que estar en el mensaje. Evidencia de las trazas: el 4B **copia bien lo que ve en un resultado** (E024-p8 copió `BAXY-bench\notas.txt` de los candidatos; E018-p7 copió la `relativePath` de file.find) y **no deduce** lo que el resultado sólo insinúa (`placeIn` ×15).

Es sólo redacción del resultado, el mismo mecanismo que el `next` de `needs_confirmation` en `NativeTurnLoop.cs:303`. Lo ideal es un archivo de datos `error_next.en.v1.json` (código → plantilla) que la proyección del resultado complete con los valores observados. Así no decide nada: sólo nombra la llamada y los valores que ya están en el resultado. Texto exacto propuesto (en inglés, como el resto de lo que lee el modelo):

- `web.fetch` / `file.read` con `hasMore:true`:
  `"next": "The text goes on. To read on, call web_fetch with url \"{finalUrl}\" and offset {nextOffset}."` (para file.read: `call file_read with fileName \"{fileName}\", folder \"{folder}\" and offset {nextOffset}`).
- `file.write` → `version_conflict`:
  `"next": "{relativePath} already exists in {folder}. To add the text as a new line at its end, call file_write again with append true. To replace its whole content, call file_read first and pass its fileSha256 as expectedSha256."`
- `app.open` → `place_not_of_application`:
  `"next": "The place \"{place}\" belongs to appId \"{placeIn[0]}\", not to \"{appId}\". Call app_open with appId \"{placeIn[0]}\" and place \"{place}\"."`
- `filesystem.known.trash.named` / `file.read` / `file.edit` → `known_file_not_found` con `folder:"all_known"`:
  `"next": "all_known looks only in Desktop, Documents and Downloads, not in other folders of the user's home. Call file_find with query \"{fileName}\" and folder \"home\" to find it and get its relativePath."`
- `filesystem.list` (cualquier resultado, pero sobre todo con `count:0`):
  añadir `"folder": "BAXY's private work folder (not the person's folders)"` y, si está vacío, `"next": "This is BAXY's own folder. A folder of the person (in their user folder, Desktop, Documents or Downloads) is listed with file_find."`
- `known_file_ambiguous` (ya trae candidatos): `"next": "Call again with fileName set to one candidate's relativePath; ask the person only if their words do not tell which."`

### P2 — Ruta con la subcarpeta: significado de `relativePath`, de `folder` y de `all_known`
**Arregla:** E006, E017, E019, E024-p7 y E027 (patrón A). Ayuda a E018-p8 y E020 (patrón B).
**Fuentes:** guía de function calling de OpenAI (https://developers.openai.com/api/docs/guides/function-calling): «Use enums… to make invalid states unrepresentable» y el *intern test* («Can an intern/human correctly use the function given nothing but what you gave the model?»). Hoy un humano tampoco sabría que «all» no incluye la carpeta de usuario. El commit que añadió los significados por argumento anotó «own path set 3/8 → 6/8». Evidencia: los 5 fallos de ruta tienen la misma forma: «archivo X **en** <ruta de carpeta>», carpeta y archivo **separados** en la frase, mientras que el ejemplo actual trae la ruta completa con el archivo junto (`C:\Users\ana\Proyectos\notas.txt`). Le resulta más fácil copiar literal que descomponer.

Textos exactos (sección `arguments` de `tool_descriptions.en.v1.json`):

- `file.write.relativePath` y `filesystem.create.directory.relativePath` (sustituye al actual):
  `"Where the file or folder goes inside folder, with every folder the person named before its name. When they said a folder path and a name apart («crea informe.txt en C:\\Users\\ana\\trabajo»), join them: relativePath «C:\\Users\\ana\\trabajo\\informe.txt» (or «trabajo/informe.txt») with folder home. Only the known folder itself (Desktop, Documents, Downloads, the user's folder) goes in folder."`
- `folder` en `file.find`, `file.read`, `file.edit`, `filesystem.known.trash.named` (nuevo):
  `"desktop, documents or downloads for those folders; home for the user's folder and any other folder inside it (C:\\Users\\ana\\X, «la carpeta X de mi usuario»), with X in subdirectory; all_known searches only Desktop, Documents and Downloads, never the rest of the user's folder."`
- Descripción de `file.find`: cambiar «(Desktop, Documents, Downloads, the user's home folder, or all)» por «(Desktop, Documents, Downloads, the user's home folder, or all_known = the first three only)».
- Descripción de `filesystem.list`: añadir tras «never the person's folders»: «A folder the person names in their user folder, even one whose name has BAXY in it, is file.find with folder home and that folder in subdirectory.»

### P3 — Dos reglas en el sistema: comparar y corregir, no repetir; y la habilidad de archivos
**Arregla:** E017, E019, E028, E015-p8 (patrón D) y frena C en E014, E022 y E024. La parte de archivos refuerza P2 para E018-p8, E020 y E027.
**Fuentes:** ReAct (https://arxiv.org/abs/2210.03629) y Reflexion (https://arxiv.org/abs/2303.11366): la observación tiene que cambiar el siguiente paso. Sobre la repetición que se refuerza sola: Xu et al., *Learning to Break the Loop* (https://arxiv.org/abs/2206.02369). OpenAI: «Use the system prompt to describe when (and when not) to use each function». Como el sistema queda después de las herramientas en la plantilla de Qwen3.5, una «habilidad» corta ahí pesa más que una frase dentro de una descripción.

Texto exacto, en español, para añadir a `SYSTEM` después de la regla 10:

```
11. Antes de responder, compara cada resultado con lo pedido: la carpeta (fullPath), el nivel, la app, la página. Si no es lo pedido, corrígelo tú con otra llamada; no le preguntes a la persona si lo corriges. Si una llamada falló, lee su error y su next y cambia algo (la herramienta o un argumento): nunca repitas una llamada con los mismos argumentos.
12. Archivos de la persona: Escritorio, Documentos y Descargas son folder desktop, documents y downloads; cualquier otra carpeta de su usuario (C:\Users\<nombre>\X, «la carpeta X de mi usuario») es folder home con X delante del nombre en relativePath, o en subdirectory. Si no sabes dónde está un archivo o carpeta que nombra, búscalo primero con file_find y usa la relativePath que te dé. filesystem_* es sólo tu carpeta de trabajo.
```

(En E019 la regla 11 habría hecho que el `fullPath C:\Users\usuario\proyecto` contradijera la frase «en C:\Users\usuario\BAXY-bench». En E028, `level 0` contra «a 40».)

### P4 — Resumen del turno con el «dónde» y las repeticiones visibles (protocolo de presentación)
**Arregla:** E019, E017, E006 (D sobre A); E014-p7, E022-p8, E024-p8 (C). También protege del desborde de contexto de E022-p8.
**Fuentes:** el comentario de `mind.py:418-420` mide que poner los hechos al final del último resultado ya corrigió falsedades («no pude abrir Steam» tras abrirlo). *Lost in the Middle* (arriba). Anthropic: devolver contexto significativo, no identificadores.

Cambio de presentación en `_outcome`/`continue_turn` (`mind.py:95-113, 421-424`): cuando el resultado trae un campo de identidad, el resumen lo dice: `fullPath`, `final.volumePercent`/`level`, `displayName`, `finalUrl`, `offset`/`nextOffset`. Si una llamada tiene **los mismos argumentos y el mismo resultado** que otra anterior del turno, lo dice también. Ejemplos del texto que leería el modelo:

```
[En este turno: file.write → completado y verificado en C:\Users\usuario\compras.txt]
[En este turno: web.fetch → completado y verificado (offset 0, hay más desde 4000); web.fetch → igual que la llamada 1: mismos argumentos y mismo resultado]
[En este turno: app.open → falló (place_not_of_application) ×3 con los mismos argumentos]
```

Para no gastar contexto, el contenido de un resultado idéntico a uno anterior del mismo turno puede ir como `{"sameAsCall": N, ...status/error}` en vez de repetir 4000 caracteres. Es presentación de un hecho, no una decisión.

### P5 — La respuesta a una confirmación llega unida a la llamada pendiente
**Arregla:** E021 (patrón E). Es condición para que E027 y E030 prueben de verdad la confirmación.
**Fuentes:** el mismo mecanismo que ya usa `mind.decide` para `ask_user` (`mind.py:321-327`: «The person's next words answer the model's own ask_user: they are that call's result, in the same loop»). La guía de Qwen pide incluir en los mensajes toda la información relevante. El «human-in-the-loop» de los runtimes de agentes presenta la aprobación como el estado de una llamada interrumpida, no como una petición nueva. Evidencia: en p8 el `next` ya decía «call confirm_pending» y la regla 8 también, y el modelo igual llamó a `shell_command_run` otra vez. Cambiar sólo la redacción de la descripción no alcanzó.

1. Protocolo: con una confirmación pendiente, las palabras de la persona entran precedidas de una línea de estado (como el reloj), sin interpretarlas:
   `[Pendiente: tu pregunta de confirmación de shell_command_run {"command": "python --version"}. Su respuesta a esa pregunta va en confirm_pending (approve true o false); si pide otra cosa, atiéndela.]`
2. `next` de `needs_confirmation` (`NativeTurnLoop.cs:303`):
   `"ask the person in one sentence whether to do it, naming it (the command, the file); their answer goes in confirm_pending with approve true or false. Calling {operation} again does not run it: it only asks again."`
3. Regla 8 del sistema, nueva redacción:
   `8. Si una herramienta responde status needs_confirmation, pregunta en una frase si lo haces, nombrando exactamente qué (el comando, el archivo). Cuando la persona conteste a esa pregunta, llama a confirm_pending con approve true (sí) o false (no); no vuelvas a llamar a la herramienta original, que sólo volvería a preguntar.`

### Ajustes de inferencia (secundarios, medir antes)
- El modelo de Qwen3.5-4B (https://huggingface.co/Qwen/Qwen3.5-4B) recomienda para el modo sin pensamiento `temperature 0.7, top_p 0.8, top_k 20, min_p 0, presence_penalty 1.5`, y subir `presence_penalty` «to reduce endless repetitions». BAXY usa `temperature 0.2`, sin presence_penalty y con `seed 0`. Contra el patrón C es lo que el autor del modelo propone. **Riesgo:** penaliza tokens ya presentes, incluidas las rutas y valores que el modelo tiene que **copiar** de los resultados, y el modelo avisa de mezcla de idiomas. Existe en el notebook un log `bench-nb-expC-pp15.log` (parece que ya se probó 1.5), pero no encontré su resultado: conviene mirarlo antes. Recomiendo P1 y P4 antes que este ajuste.
- Número de herramientas: 187 herramientas y unos 36 mil tokens de prefijo. OpenAI sugiere «fewer than 20 functions available at the start of a turn», y Paramanayakam et al., *Less is More* (https://arxiv.org/abs/2411.15399), miden mejoras en modelos chicos al reducir las herramientas visibles. Queda fuera del alcance «sólo presentación» si lo decide el código; lo dejo anotado como causa de fondo de B y del desborde de E022.

---

## 4. Fallos que NO son de presentación

| Caso | Tipo | Evidencia |
|---|---|---|
| **E015** (p7 y p8) | **Oráculo o entorno** | `Test-SteamLibraryVisible` (`bench.ps1:415-426`) exige 4 títulos de una lista fija (ARC Raiders, Marvel Rivals, PEAK…), que es la biblioteca del dueño. En el PC del lead la vista OCR muestra otra biblioteca, abierta en la C o la K (Crysis, Cuphead, Kane & Lynch, Killing Floor…). En p7 el click dio `selected:true, surfaceChanged:true` y el texto «De tu biblioteca de Steam»: casi seguro un acierto que el oráculo no ve. Además **Steam ya estaba abierto** (`alreadyRunning:true` en las dos corridas), contra la precondición del README. |
| **E024-p8, E030 (p7 y p8)** | **Entorno contaminado entre corridas** | `Reset-Sandbox` sólo borra `BAXY-bench`, y `Get-KnownTopLevel` sólo vigila Escritorio, Documentos y Descargas. Lo que el modelo escribe en `C:\Users\usuario\` no se ve ni se limpia (`leftovers` vacío en todos los casos). Ya en p7, el notas.txt de la carpeta de usuario medía 74 bytes antes de E024, o sea que venía de corridas anteriores. Por eso en p8 aparece `known_file_ambiguous` (dos notas.txt) y el primer `version_conflict`. También quedaron `C:\Users\usuario\compras.txt`, `lista.txt` y `proyecto\`. |
| **E030** (p7 y p8) | **Oráculo que aprueba por la razón equivocada** | Pasa sin que se haya pedido nunca la confirmación: `file.write{text:""}` (además escribió vacío en lugar del texto «vacío») → `version_conflict` → ambigüedad → pregunta cuál. El oráculo sólo comprueba que el archivo no cambió; debería exigir además `Test-ConfirmationAsked 1`. |
| **E021-p8** | **Proveedor (parser de llama.cpp)** | El segundo mensaje del modelo es `<tool_call>\n<function=shell_command_run>\n<parameter=command>…`, en `content`, sin `tool_calls` parseado, con herramientas presentes (no era la vuelta `final`). Se publicó como pregunta de confirmación. El síntoma coincide con llama.cpp #20837 (https://github.com/ggml-org/llama.cpp/issues/20837), que el propio `mind.py:466` ya cita. Conviene revisar la versión de llama-server y el `turns.jsonl` de esa corrida. |
| **E022-p8** | **Probable desborde de contexto (protocolo o entorno)** | Termina con `failure:"decision_unavailable"` tras 10 llamadas (el límite es 15) y sin respuesta. Eso es `step == null` en `NativeTurnLoop.cs:172`: la mente no devolvió nada. Prefijo de unos 35 900 tokens (logs del notebook), `BAXY_RENEW_CTX` 49152 por defecto, más 10 resultados de unos 4000 caracteres más el historial: muy probablemente pasó de la ventana. Confirmarlo en el `llama-server.log` del PC. La causa de origen es el patrón C; P4 (`sameAsCall`) también lo evita. |
| **E012 / E017** | **Entorno (estado de sesión de Notepad)** | El Bloc de notas restaura pestañas: el texto acumula «hola desde BAXYlista: pilas, cableshola desde BAXY…» de casos y corridas anteriores (E012 pasa igual por regex; en E017-p8 falló `input.select.all`). En E017-p7, Notepad++ ya tenía «lista: pilas, cables» escrito antes de teclear. |
| **E011** | **Acierto frágil** | Pasa con `expression:"250+175*2"` porque la calculadora estándar evalúa de izquierda a derecha (425 × 2). En modo científico daría 600. No es un fallo, pero el acierto depende del modo de la calculadora. |
| **E027** | Oráculo correcto | Falla el oráculo de voz «confirmation spoken» porque nunca se llega a la confirmación (P1 y P2 lo arreglan). Lo anoto para que no se lea como un fallo de voz o TTS. |

---

## 5. Resumen de cobertura

| Propuesta | Casos que debería arreglar |
|---|---|
| P1 `next` con valores en resultados | E014, E022-p8, E024-p8, E027, E020, E018-p8 |
| P2 significado de relativePath, folder y all_known | E006, E017, E019, E024-p7, E027 (+E018-p8, E020) |
| P3 reglas 11 y 12 del sistema | E017, E019, E028, E015-p8, E020, E018-p8, E027; frena E014, E022 y E024 |
| P4 resumen del turno con el «dónde» y las repeticiones | E019, E017, E006, E014-p7, E022-p8 (contexto), E024-p8 |
| P5 confirmación unida a la llamada pendiente | E021 (y deja que E027 y E030 prueben la confirmación) |
