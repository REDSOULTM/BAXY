# BAXY Renew — notas del notebook (REDNOTE, apoyo)

Rama `renew-nb`. El estado estructurado lo lleva el líder en `metas.json`; aquí van las notas del apoyo.

## 2026-10-15 — arranque

- Notebook: RTX 3060 Laptop 6 GB. GGUF `D:\BAXYRuntime\experiments\models\qwen35-4b-e87f1764\Qwen3.5-4B-Q4_K_M.gguf`,
  llama-server en `D:\BAXYeval\llama`, banco en `D:\BAXYeval\renew_bench`.
- `catalog.configure.json` copiado del PC a `%LOCALAPPDATA%\BAXY\renew\` (sha256 `2d3cf7e2…e693`), porque el banco
  lo lee de ahí.

## Ronda 1 medida (banco de práctica `cases.json`, 90 casos, en el notebook)

| Corrida | Código | Resultado | p50 | p90 |
|---|---|---|---|---|
| `en02v2` (PC) | antes de la ronda 1 | 85/90 | 0,74 s | 1,16 s |
| `r1-nb` (notebook) | `bd6a4ba3` (ronda 1) | 80/90 | 0,80 s | 1,27 s |

- Gana R13 y R61. Pierde R46 («skipea esta song» → `media.status`), R72 y R74 (debían preguntar; actuó), y
  R86/R88/R89/R90: pedidos imposibles (uber, rappi, transferir, llamar por teléfono) que ahora reciben una pregunta en
  vez de «eso no lo hago».
- **El mismo código anterior a la ronda 1** (`7fbf1ce38`, corrida `pre-r1-nb`) da **82/90 en el notebook**, contra
  85/90 en el PC. Fallan R13, R25, R34, R61, R72, R82, R86 y R90.
- **Conclusión:** entre corridas hay ±3 casos de ruido, porque se decide a temperatura 0,2 sin semilla fija. La ronda
  1 (80) no es peor de forma demostrable que la anterior (82) en la misma GPU.
- **Recomendación para el marco:** semilla fija (`seed` en el cuerpo de la petición) o varias corridas por variante
  antes de comparar.

## Falsedades del uso real (2026-10-15 01:45–01:55, PC)

Fuentes: `conversation.v1.jsonl`, la traza `renew/turns.jsonl` y el journal firmado `journal/missions.jsonl` del PC.

**Lo que dice el journal:** todas las acciones de esa sesión se ejecutaron y quedaron verificadas por el proveedor
(app.open Steam, ya abierto; los cuatro cambios de volumen 36→26→16→46→30; Chrome con la búsqueda; YouTube en
Opera GX; Gmail y el clic en «Recibidos»; las dos `browser.navigate` a la tienda de Steam). La ruta `conversation` del
registro no significa «sin herramientas»: es la ruta del texto final que el modelo escribe dentro del bucle.

**Las falsedades reales:**

1. **Negar lo hecho y prometer sin llamar.** Ante «no lo hiciste», el modelo respondió sin herramientas «Tienes
   razón, no lo hice. Lo siento. Voy a abrir Steam y buscar Doom Eternal ahora mismo». Las dos acciones constaban
   como verificadas en el journal.
2. **Repetir una acción ante una queja.** Ante «no lo bajaste mentiroso», volvió a bajar el volumen (26→16).
3. **Una URL inventada y contada como hecho.** Inventó la URL de la tienda con appId 1046000 y luego 281390. El
   proveedor sólo verificó la barra de direcciones, así que «te llevé a la página de Doom Eternal» no estaba
   verificado. Además, el dueño pedía el cliente de Steam, no el navegador.
4. **Un plan pendiente que se traga la orden nueva.** Con la confirmación de `app.close {"windowId":"18titans"}`
   pendiente, «cierra 18titans» y «cierra chrome» no llegaron al modelo. `MindPlanSession` pasó el texto por
   `ConfirmationReplyParser` (regex), vio que no era «sí» y re-publicó la confirmación. La redacción convirtió esos
   hechos en «No puedo cerrar Chrome porque mi última orden pendiente era…». Esto es el arnés de confirmación que el
   dueño decidió reescribir (botones Sí/No; por voz, el modelo interpreta con una herramienta, sin regex).
5. **Tono:** «¡Listo!», «Lo siento» y «¿Te gustaría…?» en casi cada respuesta, contra la identidad (sin disculpas
   ni relleno).

**Causa probable de 1–2:** entre turnos, la mente rearma el historial sólo con el texto de usuario y asistente
(`mind.decide`, `history[-13:]`). Las llamadas y los resultados verificados de los turnos anteriores se pierden, así
que ante «no lo hiciste» el modelo no tiene la evidencia y le da la razón a la persona. Arreglo candidato
(protocolo): conservar en la conversación de la mente los mensajes `tool_calls` y `role:"tool"` de los turnos
recientes. Investigación en curso (BFCL multiturno, documentación de Qwen y OpenAI, plantilla de Qwen3.5).

**El arreglo espera a que el líder selle los holdouts:** ajustar el prompt o el protocolo antes del sello
contaminaría el marco.

## Limpieza de código muerto (commit `cb1c92486`)

- Se borraron las 546 pruebas de Python, `tests/data`, `tests/fixtures`, `Baxy.Integration.Tests`, los 27 JSON
  huérfanos de `src/baxy_mind/data` y 16 scripts sin uso. En total, 858 ficheros y 321 mil líneas.
- Siguen pasando las suites de Contracts (70), Kernel (559), Setup (477) y Providers (2170). La solución compila en
  Release.
- No se tocó ningún `.cs` del arnés: el líder lo retira con el arnés nuevo.

## Voz que habla, paso A: Piper (`voice_output.py`)

- **Piper residente:** un solo `piper.exe` con `--json-input`, una línea por frase con `output_file` (CLI
  documentada de Piper).
  - Sintetizar una frase tarda 0,19 s p50 (máximo 0,27 s), contra 0,82 s lanzando un proceso por frase como
    Definitivo.
  - La voz carga al arrancar la mente en 0,65 s.
- **Salida:** se abre el dispositivo por defecto en cada frase, para seguir el cambio entre audífonos y parlantes.
  Con `latency="low"`, la latencia del dispositivo baja de 183 a 91 ms.
- **De `voice.speak` al primer sonido:** 365 ms p50 (325–528 ms), medido sola. Con llama-server cargando en
  paralelo, 466 y 576 ms. La traza `turns.jsonl` anota cada frase (`stage: voice.speak`, `sound_ms`, `sound_at`),
  para medir del texto al primer sonido.
- **Cancelación:** silencio en 47–63 ms. No queda ningún WAV en disco.
- **RAM de Piper:** 97 MB privados (105 MB de working set).
- **Mientras BAXY habla no se escucha el micrófono** (como Definitivo), para que su propia voz no lo despierte ni
  entre en un pedido. La interrupción por voz es el paso B: la evidencia de Definitivo (`PRUEBAS_AEC129_134.md`) da
  8/8 interrupciones falsas sin cancelación de eco en parlantes, y 0/8 con ella.
- Pendiente: con respuestas largas, sintetizar frase por frase adelantaría el primer sonido. Hoy son 1–2 frases.

## Perfil de 4 GB (VRAM medida con `nvidia-smi`, notebook RTX 3060 6 GB)

| Modelo | Huecos y contexto | KV | VRAM | RAM (working set / privada) |
|---|---|---|---|---|
| Q4_K_M | 2, `-kvu`, `-c 81920` (el de hoy) | q8_0 | **4648 MiB** | 3166 / 5688 MB |
| Q4_K_M | 2, `-kvu`, `-c 49152` | q8_0 | 3944 MiB | 3133 / 4979 MB |
| Q4_K_M | 1, `-c 40960` | q8_0 | 3718 MiB | 3124 / 4690 MB |
| Q4_K_M | 2, `-kvu`, `-c 81920` | q4_0 | 4008 MiB | 3166 / 5046 MB |

- **El perfil de hoy pasa de 4 GB.** Con `-kvu` el pool es compartido, así que bastan ~49k tokens en total: la
  decisión ocupa ~39k y la redacción unos cientos. Eso deja el Q4_K_M con dos huecos en 3944 MiB, sin cambiar de
  modelo.
- El IQ4_XS de unsloth (sha `658a9e7e…`, la misma familia que el Q4_K_M en uso) está en
  `D:\BAXYeval\models\Qwen3.5-4B-IQ4_XS.gguf` para medirlo.

### RAM real de llama-server

Medido con `psutil.memory_full_info`, 2026-10-15:

| Contexto | USS (RAM física privada) | Working set | Commit |
|---|---|---|---|
| `-c 49152` | 495 MB | 3240 MB | 5084 MB |
| `-c 81920` | 528 MB | 3273 MB | 5792 MB |

- **De dónde salen los otros números:**
  - Los ~2,7 GB que van del USS al working set son el GGUF mapeado en memoria: páginas de fichero compartidas que
    Windows puede recuperar.
  - El commit incluye el respaldo que WDDM reserva para la VRAM, así que no es RAM en uso.
  - Los «5,7 GB privados» del traspaso son ese commit.
- **Sin mapear el modelo:** con `--no-mmap`, llama-server no llega a arrancar en este equipo, así que se descarta.
- **Cómo medir la meta de 4 GB de RAM:** la medida honesta es el USS de llama-server más el de la mente. Conviene
  anotar también el working set, que incluye el GGUF mapeado.

## Voz que habla, paso B: interrumpir hablando encima (medido, pausado)

- **Qué se probó.** Piper en los parlantes Realtek del notebook (al 30 %) y el micrófono interno. AEC3 de
  `pywebrtc-audio`, ya instalado en el runtime, con el propio audio de Piper como referencia: es el diseño de WebRTC
  con la señal que se reproduce, sin captura loopback. Se probó BAXY solo (E1) y BAXY con otra voz encima que no está
  en la referencia (E2, voz SAPI).
  Script: `%TEMP%\claude\nb\bargein_probe.py`.
- **Corrida 1.**
  - El eco crudo tuvo una mediana de 0,051, y la salida final de AEC3 de 0,006 (unos 19 dB menos). Quedan picos:
    p95 de 0,083 y máximo de 0,218.
  - Con la otra voz encima, la salida final fue menor que el eco residual: el supresor no lineal de AEC3 se come
    también la voz de la persona cuando hablan los dos.
- **Corrida 2, con el mismo código.** El eco crudo bajó a 0,0013 de mediana, y la salida lineal quedó por encima de
  la del micrófono, es decir, el filtro no convergió. Lo más probable es que el arreglo de micrófonos Realtek aplique
  su propia cancelación de eco del driver, y que no siempre.
- **Conclusión.** En este hardware no se puede fijar un umbral honesto con energía o con el VAD de WebRTC sobre AEC3.
  Definitivo llegó a 0/8 interrupciones falsas con su cadena completa: captura WASAPI cruda con marcas de tiempo del
  dispositivo, loopback y Silero VAD.
- **Qué queda hoy.**
  - BAXY no se escucha a sí mismo: mientras habla, no oye el micrófono.
  - La App ya corta la voz cuando la persona escribe o manda un mensaje.
  - Interrumpir por voz queda pendiente, por debajo de lo que el líder repartió: herramientas, brazos y perfil de
    4 GB.
  - Siguiente intento con evidencia: Silero VAD en ONNX (sin torch) sobre la salida lineal, más la correlación con la
    referencia de Definitivo (`_looks_like_echo`).

## Herramientas de agente

Investigación y propuesta en `investigacion/herramientas-agente.md`.

- **`web.fetch` (nuevo).** Lee una página pública como texto: su título, la dirección final y el texto acotado (500
  a 20 000 caracteres).
  - Reutiliza `SearchPageReader`: sólo direcciones públicas, sin cookies ni referrer, y revisa de nuevo cada
    redirección. La prosa sale de las mismas expresiones de `SearchPageExcerpt`, sin la cabecera, los scripts, el
    menú ni el pie.
  - Es de solo lectura, como `web.search`: entra información y no sale nada de la persona, salvo la dirección.
  - Toca Kernel (`ProductCatalog`), Core (`ExternalCapabilityHandlers`), Providers (`WebBrowserAdapter`,
    `SearchPageReader`, `SearchPageExcerpt`) y las dos descripciones de la mente.
- **`shell.command.run` (cambio de riesgo).**
  - `RiskPolicy.ShellMayChange` confirma con el comando exacto todo lo que no sea demostrablemente de solo lectura.
    Lo es una tubería de cmdlets de una lista corta de lectura (más `git status`, `log`, `diff` y `show`), sin
    `> < & ; \` { } $ ( ) [ ] @`. Ante la duda, pregunta.
  - Se quitó la lista negra del proveedor, que rechazaba algunos comandos y dejaba pasar escrituras (`Set-Content`,
    `>`), borrados por .NET o con `cmd /c "del"` y envíos (`Invoke-WebRequest -Method Post`, `curl -d`,
    `Send-MailMessage`).
  - Es la postura de la identidad: se confirma lo que destruye y lo que sale al mundo, y no se niega lo peligroso,
    porque para eso está el modo. Por eso no se preguntó al dueño.
  - Pruebas: `RiskPolicyShellTests` (9 comandos de solo lectura corren directo; 24 de escritura, borrado, envío o
    código piden confirmación; el bypass corre sin preguntar) y `WebFetchReadsAPublicPageAsText`.
- **Herramientas de archivo (rama `nb-file-tools`): seis operaciones pasan a cuatro.**
  - `file.find` sustituye a `filesystem.known.list` y `.search`: sin `query` ni `content` lista el primer nivel; con
    `query` busca por nombre (parte del nombre o patrón `*`/`?`; se retiró la lista de palabras `word`/`spreadsheet`
    que interpretaba la consulta); con `content` busca dentro de los archivos de texto (2 000 archivos, 1 MiB por
    archivo, sin binarios ni puntos de reanálisis) y da la primera línea. Cada archivo trae su `relativePath`.
  - `file.read` sustituye a `document.text.read` y `document.pdf.read`: nombre o ruta relativa, `offset` y
    `maximumCharacters` (4 000 por defecto para los dos tipos, porque la mente corta la observación a 6 000);
    dice `kind`, `characters`, `hasMore` y `nextOffset` antes del texto. Un UTF-16 con BOM ya es texto (antes el
    sondeo de bytes de control lo daba por binario). Sin coincidencia o con dos, el fallo trae los candidatos.
  - `file.write` sustituye a `filesystem.write.text` y absorbe `filesystem.sandbox.append.named` (`append`): al
    reemplazar, la versión anterior va antes a la Papelera de reciclaje (`WindowsRecycleBin`, SHFileOperation con
    deshacer; guarda una copia hasta ver crecer la papelera de esa unidad y la repone si no creció) y el resultado
    dice `previousVersionRecycled`. Se arregló `Issue(path)` con la raíz del sandbox en la rama «mismo contenido»
    (con el Escritorio en D: fallaba con `path_not_found`).
  - `file.edit` (nueva): reemplazo exacto, una vez o todas con `replaceAll`; con 0 o varias sin pedirlo no cambia
    nada y dice cuántas. Conserva codificación y BOM, rechaza un ANSI que no es UTF-8 válido, recicla la versión
    anterior y relee (sha256, apariciones).
  - Se quedan `filesystem.list`, `.search` y `.read.text`: dan los `resourceId` del sandbox que usan copy, move,
    trash y hash, y `file.find`/`file.read` no cubren el sandbox.
- **Diferido:** el plan propio (Qwen3.5-4B saca 17,6 en DeepPlanning y el bucle es de 6 pasos). Unir `reminder.*` con
  `notification.*` en `schedule` lo lleva otra sesión.

## Cómo se exponen las herramientas: cuatro brazos

Banco de práctica 2 (`renew_v1/practica/decision2.json`, 270 casos), Q4_K_M, semilla 0, en el notebook.

| Brazo | Qué ve el modelo | Aciertos | p50 | Calentamiento | Sólo A acierta / sólo el brazo (McNemar exacto) |
|---|---|---|---|---|---|
| A, el de hoy | 189 herramientas con «Use when / Do not use when / Examples» y la lista de 522 apps | **220 (81,5 %)** | 0,80 s | 16,8 s | — |
| B, compacto | sólo la primera frase, sin apps | 210 (77,8 %) | 0,69 s | 8,3 s | 18 / 8 (p = 0,076) |
| C, guía a demanda | B más `skill_read` (la guía completa de una herramienta, en el mismo turno) | 213 (78,9 %) | 0,67 s | 8,4 s | 14 / 7 (p = 0,19) |
| D, sin apps | A sin la lista de apps de `app.open` | 214 (79,3 %) | 0,69 s | 8,4 s | 16 / 10 (p = 0,33) |

- **Las guías se quedan.** El compacto pierde justo donde importan: preguntar (3/10 contra 5/10) y los errores de
  dictado (4/10 contra 6/10).
- **Las skills a demanda no le sirven a este modelo tal cual.** En 270 casos el 4B no llamó `skill_read` ni una vez.
  El índice corto con la guía bajo pedido, que el dueño pidió medir contra «todas en el prompt», queda medido: un
  modelo de 4B no consulta por su cuenta.
- **La lista de apps se queda.**
  - Confirmado en un segundo banco (`renew_bench/cases.json`, 90 casos): sin la lista, 79/90 contra 83/90, y dos de
    los casos perdidos son `app.open` (R09, R12).
  - Sumando los dos bancos, sólo A acierta 21 casos y sólo D acierta 11.
  - **Corrección:** la lista son 2943 tokens de un prefijo de 34 257 (8,6 %, medido con `/apply-template` y
    `/tokenize`), no «la mitad». Las diferencias de calentamiento y p50 entre brazos venían del orden de las corridas:
    la primera carga el GGUF con el disco en frío. En el banco de 90, D calienta en 16,0 s contra 17,7 s, y su p50 es
    0,835 s contra 0,852 s.
- **La VRAM no depende del brazo** (4666 MiB en los cuatro): la fija el pool de KV (`-c`). Un prefijo más corto sólo
  permite pedir un `-c` menor.
- El código de los brazos se retiró de `mind.py`, porque el ganador es el código actual.

## Perfil de 4 GB con el brazo ganador (banco de práctica 2, 270 casos)

| Modelo | Huecos y contexto | Aciertos | p50 | p90 | VRAM | Working set / commit de llama-server |
|---|---|---|---|---|---|---|
| Q4_K_M | 2, `-kvu`, `-c 81920` (el de hoy) | 220 (81,5 %) | 0,80 s | 1,66 s | 4666 MiB | 3422 / 5887 MB |
| Q4_K_M | **1, `-c 49152`** | **227 (84,1 %)** | 0,78 s | 1,61 s | **3912 MiB** | 3339 / 5100 MB |
| IQ4_XS | 1, `-c 49152` | 227 (84,1 %) | 0,75 s | 1,44 s | 3658 MiB | 3130 / 4838 MB |

- **Los dos caben en 4 GB sin perder aciertos.** El mismo Q4_K_M basta con un hueco: la mente nueva ya no usa el
  hueco 1, porque no hay redacción ni extracción de argumentos aparte.
- **Sobre los 7 casos de diferencia:** pasar de 220 a 227 es ruido de cambiar la disposición de la caché, no una
  mejora real del hueco único (ver la tabla de McNemar de arriba).
- **El IQ4_XS deja 254 MiB más de margen** con los mismos aciertos y algo más de velocidad. Es la reserva si el
  arnés crece.
- **El contexto alcanza:** el prefijo de ~34k tokens, más el historial (24 000 caracteres, ~7k tokens), más el
  turno, entran en 49 152. La lista de apps se queda, porque quitarla cuesta aciertos.
