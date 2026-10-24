# llama-server b11609 parcheado: el prefijo de las herramientas se guarda entre peticiones

`cache_tools_prefix.patch` es un parche sobre llama.cpp **b11609** (commit `fcac19079`, el mismo que
`F:\BAXYeval\llama\llama-server.exe --version`) que quita casi todo el trabajo que cada petición de la mente a
`/v1/chat/completions` hacía antes de su primer token, con las **mismas** salidas.

## Qué medía y qué cambia

Medido en CPU (`scripts/renew/medir_preproceso.py --cpu`, 2026-10-23, prompt de ~44,4k tokens y ~180
herramientas): cada petición gastaba ~130-140 ms antes de leer el prompt. Repartido con temporizadores dentro del
servidor (b11609 compilado aquí): plantilla ~42 ms (tres renderizados: el prompt y otros dos para sacar el
`generation_prompt`), tokenizar el prompt entero ~50 ms, parser PEG y gramática de las llamadas ~12 ms, JSON ~4 ms,
gramática del sampler ~3 ms.

| Pieza | Qué hace el parche | Por qué es lo mismo |
|---|---|---|
| Tokens del prompt (`tools/server/server-common.cpp`, `server_tokenize_prompt`) | Guarda los tokens de los últimos textos (hasta 8, ≥ 4 KiB). Un prompt que empieza igual que uno guardado toma sus tokens hasta el último token especial dentro de lo común y tokeniza sólo el resto. Sirve al chat (también con `--mmproj`, sin imágenes), `/completion` y `/tokenize`. | Con `parse_special`, llama.cpp parte el texto en cada token especial y tokeniza cada trozo por separado (`tokenizer_st_partition`). Sólo se corta tras un token especial que no quita espacios (sin LSTRIP/RSTRIP) y cuyo final no aparece dentro de otro token especial seguido de más texto; las posiciones de corte salen de comparar las piezas de cada token, byte a byte, con el texto. Sólo vocabularios BPE sin BOS/EOS añadidos. |
| `generation_prompt` (`common/parsers/qwen3-coder.cpp`) | Con `add_generation_prompt` y sin continuación, el renderizado «con» es el propio prompt: se renderiza una vez menos. Con continuación (`fill_call`) el resultado se sustituye después, así que no se renderiza. | El renderizado «con» tiene los mismos parámetros que el prompt ya hecho; el de la continuación b11609 lo calcula y lo pisa. |
| Parser y gramática de las llamadas (`qwen3-coder.cpp`) | Guardados para las últimas 4 combinaciones de plantilla, herramientas, `tool_choice`, `parallel_tool_calls`, formato de respuesta y razonamiento. | Dependen sólo de eso, nunca de los mensajes. |
| `tojson` de la plantilla (`common/jinja/value.cpp`) | El mismo texto, añadido a un `std::string` en vez de escrito carácter a carácter en un stream. | Misma salida; los números siguen pasando por un `ostringstream`. |

La gramática compilada del sampler (~3 ms) no se reutiliza: no vale la pena.

- `BAXY_LLAMA_CACHE=0` apaga todo: el servidor calcula como b11609 (sirve para un A/B con el mismo binario).
- `BAXY_LLAMA_CACHE_CHECK=1` calcula además cada resultado como b11609, compara, deja en el log
  `BAXY cache check: … identical` (o `differs …, using stock`) y usa el de b11609. Es más lento: sólo para verificar.
- En el log normal, una línea por prompt: `BAXY prompt cache: N tokens, K kept, M tokenized`.

## Compilar (lo que se hizo el 2026-10-23 en el PC)

Sólo cambian `llama-server.exe`, `llama-server-impl.dll` y `llama-common.dll`. `llama.dll`, `mtmd.dll`, los `ggml*.dll`
(CPU y `ggml-cuda.dll`), `libomp.dll` y el runtime CUDA 12 (`cudart64_12.dll`, `cublas64_12.dll`, `cublasLt64_12.dll`)
se quedan los de la distribución b11609: los núcleos que calculan, el muestreo (`llama.dll`) y la visión (`mtmd.dll`)
son los mismos bytes. Por eso no hace falta CUDA para compilar (en el PC sólo hay CUDA 13) y la carpeta funciona con el
driver que ya mueve la b11609. Las tres piezas nuevas llaman a las de siempre por su API de C (y las pocas funciones C++
exportadas tienen el mismo nombre decorado: se comprobó con `dumpbin /exports`).

```powershell
git clone --depth 1 --branch b11609 https://github.com/ggml-org/llama.cpp D:\BAXYWork\llama-src
git -C D:\BAXYWork\llama-src apply <repo>\scripts\llama\cache_tools_prefix.patch
# en un «x64 Native Tools» de Visual Studio 2022 (cl 19.44), con prioridad baja (start /belownormal):
cmake -S D:\BAXYWork\llama-src -B D:\BAXYWork\llama-build -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON `
  -DGGML_BACKEND_DL=ON -DGGML_NATIVE=OFF -DGGML_OPENMP=OFF -DGGML_CUDA=OFF -DLLAMA_OPENSSL=OFF `
  -DLLAMA_USE_PREBUILT_UI=OFF -DLLAMA_BUILD_UI=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF `
  -DLLAMA_BUILD_NUMBER=11609 -DLLAMA_BUILD_COMMIT=fcac19079
cmake --build D:\BAXYWork\llama-build --target llama-server -j 4
robocopy F:\BAXYeval\llama F:\BAXYeval\llama-patch /E
foreach ($f in 'llama-server.exe','llama-server-impl.dll','llama-common.dll') {
  Copy-Item "D:\BAXYWork\llama-build\bin\$f" F:\BAXYeval\llama-patch\ -Force }
```

En el PC el build Release entero (CPU, 214 pasos) tardó ~30 min a `-j 4`; tras tocar el parche, sólo se recompilan los
ficheros cambiados.

`LLAMA_USE_PREBUILT_UI=OFF` evita la descarga de la interfaz web desde Hugging Face: el parcheado no trae la web de
`/` (la mente no la usa), por eso su `llama-server-impl.dll` pesa ~3,5 MB y no ~9,2 MB. `llama-server.exe` es, como en
la b11609 (9 KB), sólo el lanzador de `llama-server-impl.dll` (~10 KB). `--version` dice `built with MSVC 19.44` en vez de Clang. SHA-256 de la carpeta del PC:
`llama-server.exe` 2de27411…, `llama-server-impl.dll` 8fe19709…, `llama-common.dll` a5f07844…; los otros 52 ficheros
son byte a byte los de `F:\BAXYeval\llama\`.

## Usarlo

`src/baxy_mind/__main__.py` ya toma el servidor de `BAXY_MIND_LLAMA_SERVER`, y `scripts/run_renew.cmd` ahora la respeta
si viene definida (antes la fijaba siempre a la b11609):

```bat
set "BAXY_MIND_LLAMA_SERVER=F:\BAXYeval\llama-patch\llama-server.exe"
scripts\run_renew.cmd
```

La clave del prefijo guardado (`LlmServer.prefix_key`) incluye el binario: el primer arranque con el parcheado vuelve a
leer el prefijo una vez (~18 s en GPU) y lo guarda para los siguientes.

## Verificación en CPU (PC, 2026-10-23)

Todo con `-ngl 0 -dev none -t 4`, prioridad por debajo de lo normal, un servidor cada vez, y las carpetas de prueba
sin `ggml-cuda.dll` (la b11609 y la parcheada con sus 3 piezas): la GPU no se tocó. `verificar_parche.py` hace las
tres pasadas; sus ficheros se quedaron en `D:\BAXYWork\verify`.

1. **Mismas respuestas.** Una sesión real de la mente (`capture`: configure, warm-up con su aviso, 8 turnos con los
   resultados de sus llamadas, el prefill entre turnos y un latido) contra la b11609, y sus peticiones repetidas
   (`replay`) contra la b11609, la parcheada y la parcheada con `BAXY_LLAMA_CACHE_CHECK=1`, las tres desde el slot que
   guardó el warm-up. Con el catálogo entero el warm-up en CPU lee ~44k tokens a 11-46 tok/s (más de hora y media con
   el PC en uso), así que esta pasada usa 18 operaciones de `catalog-final.json` (`--only`; prompt de ~10,4k tokens):
   el camino del parche es el mismo, cambia sólo el largo. `--only app.open,app.close,app.installed,audio.volume,`
   `audio.volume.adjust,audio.mute,calculator.expression.evaluate,web.search,weather.current,system.time,input.text.type,`
   `window.focus,note.create,memory.save,media.play.youtube,clipboard.write.text,file.find,wifi.status` (sin espacios).
2. **Mismos prompts y tokens a tamaño real.** `identity`: las 20 peticiones de chat de esa sesión con las ~180
   herramientas del catálogo entero (44.290-46.077 tokens), renderizadas, tokenizadas y rechazadas por un contexto de
   8192 en cada servidor.
3. **Tiempo antes del primer token**: `scripts/renew/medir_preproceso.py --cpu` contra cada uno, dos rondas alternas.

| Comprobación | Peticiones | Resultado |
|---|---|---|
| b11609 ↔ parcheada: código HTTP, texto, llamadas y argumentos, mensaje parseado, logprobs (top 3 por token), `prompt_n`/`cache_n`/`predicted_n` | 45 (18 chats, 7 `/completion`, 13 `/tokenize`, 7 `/apply-template`); 589 logprobs | **idénticas** |
| b11609 ↔ parcheada en modo comprobación | las mismas 45 | **idénticas**; en su log 25 `prompt tokens identical`, 22 `parser and grammar identical`, 0 `differ` |
| b11609 ↔ parcheada con `--mmproj` (visión en CPU, camino de mtmd) en modo comprobación | las mismas 45 | **idénticas** (rápida y en modo comprobación); en su log 18 `prompt tokens identical to mtmd's`, 0 `differ`. Una primera pasada de la b11609 con `--mmproj` cayó con `bad allocation` (falta de RAM: otra sesión tenía 4 GB en un llama-server de CPU) y se repitió |
| Prompt renderizado y tokens a tamaño real (`identity`), b11609 ↔ parcheada y ↔ modo comprobación | 20 cuerpos de 44-46k tokens | **idénticos**; en modo comprobación 40 `prompt tokens identical`, 37 `parser and grammar identical`, 0 `differ` |
| Tokens guardados en la sesión | — | cada turno toma del caché todo menos los 93-209 tokens nuevos; el latido (otro texto de sistema) toma 9.572 de 10.609, cortando tras el `</tool_call>` de las instrucciones de la plantilla |

Tiempo (p50 de 12, ms; el PC en uso por su dueño y por otra sesión, por eso la b11609 sale más lenta que el 2026-10-23
temprano: 134-148 ms):

| `medir_preproceso.py --cpu` (3 rondas alternas) | b11609 | parcheada | ahorro |
|---|---|---|---|
| chat (herramientas y gramática) | 186,5 / 187,9 / 172,0 | 55,6 / 55,0 / 51,0 | **~128 ms (−70 %)** |
| chat_none | 174,8 / 175,5 / 166,2 | 46,9 / 47,4 / 39,3 | ~128 ms |
| template (`/apply-template`) | 84,1 / 87,0 / 77,8 | 44,0 / 42,4 / 42,7 | ~40 ms |
| tokenize | 112,6 / 107,5 / 99,4 | 14,8 / 15,5 / 13,4 | ~92 ms |
| completion_text | 85,5 / 104,6 / 82,9 | 8,8 / 5,5 / 4,0 | ~85 ms |
| completion_ids | 18,5 / 18,3 / 17,1 | 18,8 / 20,4 / 18,0 | — |

Antes, con el PC más tranquilo: chat 141,7 → 44,7 ms. Lo que queda en la parcheada son los dos renderizados de la
plantilla (~2 × 9 ms), el JSON del cuerpo (~4 ms) y el resto del camino HTTP. En la sesión repetida (prompt de
~10k tokens) el tiempo fuera de `prompt_ms + predicted_ms` de cada petición con generación bajó de 60,5 a 30,8 ms (p50
de 25; incluye el cálculo de logprobs, igual en los dos). Por turno con una herramienta (decidir + continuar) en el
prompt real: ~260 ms menos en este CPU.

## A/B en la GPU del notebook

No hecho: en el PC la GPU es del dueño. En el notebook (REDNOTE), con la GPU libre:

1. Copiar la carpeta: `robocopy D:\BAXYeval\llama D:\BAXYeval\llama-patch /E` y encima los tres ficheros de
   `F:\BAXYeval\llama-patch\` del PC (`llama-server.exe`, `llama-server-impl.dll`, `llama-common.dll`).
2. Tiempo antes del primer token en GPU, cada servidor por separado (GPU, warm-up restaurado):
   `py -3.12 -X utf8 scripts\renew\medir_preproceso.py --server D:\BAXYeval\llama\llama-server.exe` y lo mismo con
   `--server D:\BAXYeval\llama-patch\llama-server.exe` (`--gguf D:\BAXYeval\models\BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf`
   y el `--catalog` del notebook). Esperado: `chat` ~90-130 ms menos; `prompt_ms` y `predicted_ms` iguales.
3. Mismas respuestas en GPU con el catálogo entero (minutos, no horas):
   ```bat
   set V=scripts\llama\verificar_parche.py
   py -3.12 -X utf8 %V% capture D:\BAXYeval\llama D:\BAXYWork\cap.json --ngl 99 --work D:\BAXYWork --gguf D:\BAXYeval\models\BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf --catalog <catálogo>
   py -3.12 -X utf8 %V% replay D:\BAXYeval\llama D:\BAXYWork\cap.json D:\BAXYWork\r_stock.json --ngl 99 --work D:\BAXYWork --gguf ...
   py -3.12 -X utf8 %V% replay D:\BAXYeval\llama-patch D:\BAXYWork\cap.json D:\BAXYWork\r_patch.json --ngl 99 --work D:\BAXYWork --gguf ...
   py -3.12 -X utf8 %V% replay D:\BAXYeval\llama-patch D:\BAXYWork\cap.json D:\BAXYWork\r_check.json --ngl 99 --work D:\BAXYWork --gguf ... --env BAXY_LLAMA_CACHE_CHECK=1
   py -3.12 -X utf8 %V% compare D:\BAXYWork\r_stock.json D:\BAXYWork\r_patch.json
   py -3.12 -X utf8 %V% compare D:\BAXYWork\r_stock.json D:\BAXYWork\r_check.json
   findstr /C:"BAXY cache check" D:\BAXYWork\r_check.server.log | findstr /C:"differ"
   ```
   Las dos comparaciones deben decir `ALL IDENTICAL` y el último `findstr` no debe imprimir nada. Con `--mmproj` en los
   `replay` se prueba también el camino de la visión.
4. En el producto: `set "BAXY_MIND_LLAMA_SERVER=D:\BAXYeval\llama-patch\llama-server.exe"` antes de
   `scripts\run_renew.cmd`; en la traza, `turn.decide`/`turn.continue` con `ms − prompt_ms − predicted_ms` ~90-130 ms
   menos que con la b11609, y decision2/falsedades con las mismas decisiones (semilla fija). Volver atrás: abrir una
   consola nueva sin la variable, o `BAXY_LLAMA_CACHE=0` para el mismo binario con el cálculo de la b11609.
