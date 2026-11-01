# Avisos de terceros (THIRD_PARTY_NOTICES)

> Inventario hecho leyendo los manifiestos del repositorio, con cada licencia comprobada en su fuente oficial
> (registro del paquete, repositorio o ficha del modelo) el 2026-10-31. Lo que no se pudo confirmar está marcado
> **«sin confirmar»**. Este documento no es asesoría legal.

El código propio de BAXY se publica bajo la [licencia MIT](LICENSE). Las piezas de terceros que BAXY usa,
instala o distribuye **conservan su propia licencia**, que la licencia MIT de BAXY no sustituye ni amplía.

**Los pesos de los modelos no están en el repositorio.** BAXY no descarga modelos por su cuenta
(`assets.manifest.json`: «BAXY no descarga modelos automáticamente»): cada persona los descarga aparte (ver
[docs/instalacion.md](docs/instalacion.md)) y declara su ruta. Quien los obtenga acepta la licencia de cada modelo.

Cómo leer la columna «Cómo llega»:

- **En el repo**: el fichero de terceros está versionado en este repositorio (se redistribuye al clonar).
- **En el paquete**: no está en el repo, pero el instalador o la publicación del producto lo copia.
- **Se instala**: lo instala un script desde su registro oficial (PyPI, NuGet, npm) con versión fijada.
- **Lo aporta la persona**: BAXY lo usa si existe en la máquina; no lo trae ni lo descarga.
- **Del sistema**: componente de Windows.

---

## ¿Algo impide que el código propio sea MIT?

**No se encontró nada que lo impida.**

- No hay dependencias GPL/LGPL/AGPL enlazadas ni distribuidas: ni en el lock de Python (60 paquetes de runtime y 6
  de pruebas), ni en NuGet, ni en el grafo npm de la interfaz (191 paquetes). La búsqueda de cabeceras GPL/LGPL en
  `src/`, `scripts/` y `tests/` no devolvió nada.
- Los tres parches de `runtime_wheels/` modifican código **Apache-2.0** (sherpa-onnx y pywebrtc-audio) y el de
  `scripts/llama/` modifica código **MIT** (llama.cpp). Ambas licencias son compatibles con MIT.
- Las licencias de copyleft débil del grafo (MPL-2.0 en `certifi`, `tqdm` y `lightningcss`) actúan por fichero y
  sólo sobre esos paquetes, que se usan sin modificar.
- Matiz: un parche es una obra derivada del fichero que modifica. Lo prudente es que los `.patch` y las ruedas
  parcheadas sigan bajo la licencia de su proyecto de origen (Apache-2.0 o MIT) y no se presenten como «MIT de
  BAXY». En particular, `sherpa-nemo-normalization.patch` incorpora la corrección de un contribuidor externo de
  sherpa-onnx (PR #3857), con su autoría y bajo Apache-2.0.

---

## Obligaciones y restricciones a tener en cuenta

Ordenadas por peso. Lo que es sólo atribución está al final.

### 1. Voz de Supertonic 3: OpenRAIL-M, con restricciones de uso

- **Licencia del modelo:** BigScience Open RAIL-M (2022-08-18), declarada por Supertone en la ficha del modelo
  ([LICENSE](https://huggingface.co/Supertone/supertonic-3/blob/main/LICENSE)). No es una licencia OSI. El
  código de muestra de Supertone es MIT, pero BAXY no lo usa: sintetiza con la implementación de sherpa-onnx.
- **Restricciones de uso (Anexo A), heredadas por cualquier derivado:** prohibido usarlo para infringir la ley,
  dañar a menores, desinformar para dañar, difundir datos personales para dañar, difamar o acosar, suplantar a
  personas sin su consentimiento (deepfakes), tomar decisiones totalmente automatizadas que afecten derechos,
  discriminar, explotar vulnerabilidades, dar consejo médico, o usos de justicia, policía, migración o asilo.
  Además, el apartado (e) prohíbe difundir contenido generado **sin declarar de forma expresa e inteligible que lo
  generó una máquina**.
- **La voz de BAXY es un derivado.** El paquete de voz mezcla tres estilos de Supertonic
  (`scripts/voice/make_baxy_voice.py`) y su `baxy-voice.json` ya lo anota: «its use restrictions apply and speech
  must be disclosed as synthetic».
- **Si algún día se redistribuye** el modelo o la voz derivada (no se hace hoy: no está en el repo): hay que
  incluir las restricciones del Anexo A como cláusula exigible en la licencia que rija ese uso, avisar a quien lo
  reciba, darle una copia de la licencia, marcar los ficheros modificados y conservar los avisos.
- **Para el producto:** conviene que la documentación y la interfaz digan que la voz es sintética y que el README
  enlace estas restricciones, porque quien use BAXY usa el modelo.

### 2. Encoder Kroko del detector de palabra de activación: CC-BY-SA (copyleft de datos/modelos)

- El detector «k4» (paquete externo `baxy-wake-k4`, no está en el repo) usa como encoder
  `encoder_kroko_es.onnx`, sacado de `sherpa-onnx-streaming-zipformer-es-kroko-2025-08-06`, más una cabeza propia
  (`head.onnx`) entrenada sobre sus salidas.
- Kroko declara que sus modelos comunitarios son **CC-BY-SA**
  ([ficha](https://huggingface.co/Banafo/Kroko-ASR)); el motor es Apache-2.0 y hay modelos comerciales aparte.
  **Sin confirmar:** la versión exacta de CC-BY-SA (el fichero `LICENSE` del repositorio de la ficha está vacío)
  y si una cabeza entrenada sobre los embeddings cuenta como adaptación.
- **Obligación si se redistribuye el paquete wake:** atribuir a Kroko/Banafo, enlazar la licencia, indicar
  cambios y, por ShareAlike, publicar el encoder (y lo que se considere adaptación) bajo la misma CC-BY-SA. No
  afecta al código MIT de BAXY, que sólo carga el modelo.

### 3. Parakeet (reconocimiento de voz): CC-BY-4.0, atribución en cadena

- El reconocedor de producción es **Parakeet Ultra** int8 para sherpa-onnx. Cadena de origen, todo CC-BY-4.0:
  [`nvidia/parakeet-tdt-0.6b-v3`](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) (NVIDIA) →
  [`moondream/parakeet-ultra`](https://huggingface.co/moondream/parakeet-ultra) (post-entrenamiento) →
  [`Olicorne/parakeet-tdt-0.6b-v3-ultra-onnx`](https://huggingface.co/Olicorne/parakeet-tdt-0.6b-v3-ultra-onnx)
  (encoder) y
  [`tpmaerk/parakeet-ultra-sherpa-onnx-int8`](https://huggingface.co/tpmaerk/parakeet-ultra-sherpa-onnx-int8)
  (decoder, joiner, tokens). El bundle alternativo `sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` deriva del mismo
  v3.
- **Obligación:** atribuir a cada eslabón, enlazar [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) e
  indicar si se cambió algo (el bundle se armó copiando metadatos de un eslabón al otro, sin tocar pesos). Aplica al
  redistribuir; para el uso basta con mantener la atribución en la documentación.

### 4. Qwen3.5-4B y el modelo ajustado de BAXY: Apache-2.0

- [`Qwen/Qwen3.5-4B`](https://huggingface.co/Qwen/Qwen3.5-4B) está bajo **Apache-2.0**
  ([LICENSE](https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/LICENSE)), sin restricciones de uso adicionales
  ni la antigua «Qwen License»; el repositorio no trae fichero `NOTICE`. El GGUF de producción y el proyector de
  visión (`mmproj-F16.gguf`) vienen de [`unsloth/Qwen3.5-4B-GGUF`](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF),
  también Apache-2.0.
- El modelo de BAXY (`BAXY-Qwen3.5-4B-c3-Q4_K_M.gguf`, LoRA fusionado y cuantizado a Q4_K_M) es una **obra
  derivada** de Qwen3.5-4B. Se publica aparte en
  [huggingface.co/REDSOULTM/BAXY-Qwen3.5-4B-GGUF](https://huggingface.co/REDSOULTM/BAXY-Qwen3.5-4B-GGUF), no en este
  repositorio. Según [la receta](docs/construccion/modelo-propio/ft/RECETA.md), se entrenó con datos propios y
  sintéticos, sin conjuntos públicos.
- **Obligación al publicarlo:** incluir copia de Apache-2.0, avisar en la ficha de que se modificó el modelo
  original y conservar los avisos de Qwen.

### 5. Ficheros de terceros que ya están en el repo: copiar sus avisos

- **Fuentes tipográficas (OFL-1.1)** en `src/Baxy.FieldUi/dist/assets/*.woff2` (subconjunto latino de
  `@fontsource`): Inter, JetBrains Mono y Chakra Petch. La OFL exige que cada copia redistribuida lleve el aviso de
  copyright y la licencia, y prohíbe vender las fuentes solas. Los avisos están en
  [«Avisos de los ficheros incluidos»](#avisos-de-los-ficheros-incluidos).
- **React y React DOM (MIT)** van compilados dentro de `dist/assets/index-*.js` y Vite quitó sus comentarios de
  licencia; el aviso MIT de React está en [«Avisos de los ficheros incluidos»](#avisos-de-los-ficheros-incluidos).
- **Ruedas binarias de `runtime_wheels/`** (ver tabla 6): llevan dentro sus licencias, el `NOTICE` de
  pywebrtc-audio, el aviso de patentes de WebRTC y un `BAXY-NOTICE.txt` que dice qué se cambió. Así se cumplen los
  apartados 4(a)-(d) de Apache-2.0. **Falta** el aviso BSD-3-Clause de **pybind11** (con el que se compiló la
  extensión de pywebrtc-audio). **Sin confirmar** si la extensión de sherpa-onnx también lo necesita.

### 6. Vídeos e imagen del avatar: términos de Higgsfield (sin licencia abierta)

- Los 37 clips de `src/Baxy.FieldUi/public/clips` (y su copia en `dist/clips`), los fondos `public/bg/*.jpg` y el
  icono (`baxy-icon-64.png`, `Baxy.App/Assets/baxy.ico`, hecho «desde el arte de Higgsfield») se generaron con
  Higgsfield. **No tienen licencia abierta**: su uso se rige por los Términos de Uso de Higgsfield.
- Según el [centro de ayuda de Higgsfield](https://higgsfield.ai/creator-hub/help-center/account/who-owns-my-generations-and-can-i-use-them-commercially),
  la empresa no reclama la propiedad de lo generado y permite el uso comercial sin atribución, pero **prohíbe usar
  esas salidas para entrenar o mejorar modelos de IA**, y otras personas pueden generar resultados parecidos.
  **Sin confirmar:** la versión de los términos vigente cuando se generaron los clips. Las fuentes no coinciden en
  la fecha.
- **Estos medios no se licencian bajo MIT**: los ficheros de `src/Baxy.FieldUi/public/clips`,
  `src/Baxy.FieldUi/dist/clips`, `src/Baxy.FieldUi/public/bg`, `baxy-icon-64.png` y `src/Baxy.App/Assets/baxy.ico`
  se rigen por los términos de Higgsfield, y no se pueden usar para entrenar modelos de IA.

### 7. Atribución y copia de licencia (permisivas)

Para el resto (MIT, BSD, Apache-2.0, ISC, PSF, OFL) la obligación es conservar el aviso de copyright y el texto de
la licencia **al redistribuir binarios**. Apache-2.0 añade: conservar el `NOTICE` si existe, marcar los ficheros
modificados y respetar la cláusula de patentes. Lo que sólo se instala desde su registro oficial ya lleva sus
licencias dentro del paquete.

---

## Tablas por grupo

### 1. .NET y NuGet

| Pieza | Versión fijada | Licencia (SPDX) | Fuente de la licencia | Cómo llega | Notas |
|---|---|---|---|---|---|
| .NET SDK / runtime | SDK `10.0.100` (`global.json`), `net10.0-windows10.0.19041.0` | MIT | [dotnet/runtime](https://github.com/dotnet/runtime/blob/main/LICENSE.TXT) | Se instala (SDK); **en el paquete** (`build_product.ps1` publica *self-contained*) | Al publicar *self-contained* se redistribuye el runtime: incluir su `THIRD-PARTY-NOTICES`. |
| WPF / Windows Desktop | la del SDK | MIT | [dotnet/wpf](https://github.com/dotnet/wpf/blob/main/LICENSE.TXT) | En el paquete | Igual que el runtime. |
| Proyecciones del Windows SDK (`Microsoft.Windows.SDK.NET.Ref`) | 10.0.19041.x (implícita) | Licencia del Windows SDK (propietaria) | [aka.ms/WinSDKLicenseURL](https://aka.ms/WinSDKLicenseURL) | En el paquete | **Sin confirmar** que la redistribución de `Microsoft.Windows.SDK.NET.dll` quede cubierta como «código distribuible». |
| Microsoft.Web.WebView2 | 1.0.4078.44 | BSD-3-Clause (texto de Microsoft) + `NOTICE.txt` de terceros | `LICENSE.txt` y `NOTICE.txt` dentro del [paquete NuGet](https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.4078.44) | Se instala; **en el paquete** (`WebView2Loader.dll` y ensamblados, `Baxy.Setup/PackageContract.cs`) | Conservar `LICENSE.txt` y `NOTICE.txt` en el paquete. El runtime Edge WebView2 es **del sistema**. |
| Microsoft.NET.Test.Sdk | 17.9.0 | MIT | [microsoft/vstest](https://github.com/microsoft/vstest/blob/main/LICENSE) | Se instala (sólo pruebas) | No se distribuye. |
| NUnit | 4.1.0 | MIT | [nunit/nunit](https://github.com/nunit/nunit/blob/main/LICENSE.txt) | Se instala (sólo pruebas) | No se distribuye. |
| NUnit3TestAdapter | 4.5.0 | MIT | [nunit3-vs-adapter](https://github.com/nunit/nunit3-vs-adapter/blob/main/LICENSE) | Se instala (sólo pruebas) | No se distribuye. |

### 2. Python (runtime de la mente y la voz)

Se instalan desde PyPI con `--require-hashes` (`pylock.runtime-win-x64.toml`, `scripts/setup_mind_voice.ps1`), salvo
las dos ruedas parcheadas de la tabla 6, que vienen del repo. Licencia leída de los metadatos PyPI de **esa versión
exacta** y, cuando faltaban, del repositorio del proyecto.

| Paquete | Versión | Licencia (SPDX) | Paquete | Versión | Licencia (SPDX) |
|---|---|---|---|---|---|
| annotated-doc | 0.0.4 | MIT | pycaw | 20251023 | MIT ([código fuente](https://github.com/AndreMiras/pycaw/blob/main/LICENSE); PyPI no la declara) |
| anyio | 4.14.2 | MIT | pycparser | 3.0 | BSD-3-Clause |
| certifi | 2026.6.17 | **MPL-2.0** | pygments | 2.20.0 | BSD-2-Clause |
| cffi | 2.1.0 | MIT-0 | **pywebrtc-audio** | 0.2.0+baxy.1 | Apache-2.0 (parcheada, ver tabla 6) |
| click | 8.4.2 | BSD-3-Clause | pywin32 | 311 | PSF-2.0 |
| colorama | 0.4.6 | BSD-3-Clause | pyyaml | 6.0.3 | MIT |
| comtypes | 1.4.16 | MIT | rapidfuzz | 3.14.5 | MIT |
| filelock | 3.31.0 | MIT | regex | 2026.7.19 | Apache-2.0 AND CNRI-Python |
| flatbuffers | `25.12.19` | Apache-2.0 | rich | 15.0.0 | MIT |
| fsspec | 2026.6.0 | BSD-3-Clause | safetensors | 0.8.0 | Apache-2.0 |
| h11 | 0.16.0 | MIT | scikit-learn | 1.9.0 | BSD-3-Clause |
| hf-xet | 1.5.2 | Apache-2.0 | scipy | 1.17.1 | BSD-3-Clause (ver nota) |
| httpcore | 1.0.9 | BSD-3-Clause | sentence-transformers | 5.6.0 | Apache-2.0 |
| httpx | 0.28.1 | BSD-3-Clause | setuptools | 83.0.0 | MIT |
| huggingface-hub | 1.24.0 | Apache-2.0 | shellingham | 1.5.4 | ISC |
| idna | 3.18 | BSD-3-Clause | **sherpa-onnx** | 1.13.4+baxy.2 | Apache-2.0 (parcheada, ver tabla 6) |
| jellyfish | 1.2.1 | MIT | sherpa-onnx-core | 1.13.4 | Apache-2.0 |
| jinja2 | 3.1.6 | BSD-3-Clause | silero-vad | 6.2.1 | MIT (incluye `silero_vad.onnx`) |
| joblib | 1.5.3 | BSD-3-Clause | sounddevice | 0.5.5 | MIT (incluye PortAudio, licencia tipo MIT) |
| livekit-wakeword | 0.2.1 | Apache-2.0 | sympy | 1.14.0 | BSD-3-Clause |
| markdown-it-py | 4.2.0 | MIT | threadpoolctl | 3.6.0 | BSD-3-Clause |
| markupsafe | 3.0.3 | BSD-3-Clause | tokenizers | 0.22.2 | Apache-2.0 |
| mdurl | 0.1.2 | MIT | torch | 2.13.0 | BSD-3-Clause; la rueda declara `Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT` |
| mpmath | 1.3.0 | BSD-3-Clause | torchaudio | 2.11.0 | BSD (clasificador; **sin confirmar** si es 2 o 3 cláusulas) |
| narwhals | 2.24.0 | MIT | tqdm | 4.69.0 | **MPL-2.0 AND MIT** |
| networkx | 3.6.1 | BSD-3-Clause | transformers | 5.14.1 | Apache-2.0 |
| numpy | 1.26.4 | BSD-3-Clause (ver nota) | typer | 0.27.0 | MIT |
| onnxruntime | 1.27.0 | MIT | typing-extensions | 4.16.0 | PSF-2.0 |
| packaging | 26.2 | Apache-2.0 OR BSD-2-Clause | protobuf | 7.35.1 | BSD-3-Clause |
| psutil | 7.2.2 | BSD-3-Clause | pyaudiowpatch | 0.2.12.8 | Apache-2.0 ([código fuente](https://github.com/s0d3s/PyAudioWPatch/blob/master/LICENSE.txt); incluye PortAudio) |

Notas:

- **numpy y scipy** para Windows traen OpenBLAS y el runtime de gfortran. Este último va bajo GPL-3.0 **con la
  excepción de biblioteca de runtime de GCC**, que no extiende la GPL a quien lo usa. Va dentro de la rueda
  oficial y BAXY no lo redistribuye aparte.
- **`kaldi-native-fbank==1.22.3`** (Apache-2.0, [código fuente](https://github.com/csukuangfj/kaldi-native-fbank/blob/master/LICENSE))
  figura en `src/baxy_mind/requirements-voice.txt` y lo importa el detector wake externo, pero **no está en
  `constraints-runtime-win-x64.txt` ni en `pylock.runtime-win-x64.toml`**. Hay que revisar esa incoherencia del lock
  (no es un problema de licencia).
- `livekit-wakeword` se usó para entrenar wake words (`scripts/baxy-wakeword-production.yaml`, con VoxCPM,
  Apache-2.0, como TTS de entrenamiento). La mente no lo importa en tiempo de ejecución.

**Pruebas y calidad** (sólo desarrollo, no se distribuyen): pytest 9.1.1 (MIT), pluggy 1.6.0 (MIT), iniconfig 2.3.0
(MIT), colorama, packaging y pygments (como arriba), ruff 0.15.22 (MIT).

**Scripts de investigación** (`scripts/renew/…`, no son runtime): usan modelos de embeddings
[`intfloat/multilingual-e5-small`](https://huggingface.co/intfloat/multilingual-e5-small) (MIT) y
[`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
(Apache-2.0), que descarga la biblioteca al ejecutarlos.

### 3. Interfaz FieldUi (npm, resumen)

Grafo fijado por `src/Baxy.FieldUi/pnpm-lock.yaml`: **191 paquetes**, de los que sólo 6 llegan al producto (React,
React DOM, scheduler y las tres fuentes). El resto son herramientas de compilación y pruebas (Vite, TypeScript,
ESLint, Playwright…). Licencias leídas del `package.json` de cada paquete instalado y, para los binarios de otras
plataformas, del registro npm.

| Licencia | Paquetes |
|---|---|
| MIT | 137 |
| Apache-2.0 | 18 |
| MPL-2.0 | 12 (`lightningcss` y sus 11 binarios por plataforma; sólo compilación) |
| ISC | 10 |
| BSD-2-Clause | 6 |
| OFL-1.1 | 3 (`@fontsource/inter`, `@fontsource/chakra-petch`, `@fontsource/jetbrains-mono`) |
| BSD-3-Clause | 2 |
| CC-BY-4.0 | 1 (`caniuse-lite`, datos de navegadores; sólo compilación) |
| BlueOak-1.0.0 | 1 (`minimatch`; permisiva) |
| 0BSD | 1 (`tslib`) |

Ninguna es copyleft fuerte. Las no permisivas «clásicas» son MPL-2.0 (copyleft débil por fichero) y CC-BY-4.0
(atribución), y las dos sólo intervienen al compilar: no llegan a `dist/`.

| Lo que sí va en `dist/` (en el repo) | Versión | Licencia | Fuente |
|---|---|---|---|
| react / react-dom | 19.2.6 | MIT | [facebook/react](https://github.com/facebook/react/blob/main/LICENSE) |
| scheduler | 0.27.0 | MIT | ídem |
| Inter (vía `@fontsource/inter`) | 5.3.0 | OFL-1.1 (empaquetado de Fontsource: MIT) | [rsms/inter](https://github.com/rsms/inter/blob/master/LICENSE.txt) |
| Chakra Petch (vía `@fontsource/chakra-petch`) | 5.3.0 | OFL-1.1 | [cadsondemak/Chakra-Petch](https://github.com/cadsondemak/Chakra-Petch/blob/master/OFL.txt) |
| JetBrains Mono (vía `@fontsource/jetbrains-mono`) | 5.3.0 | OFL-1.1 | [JetBrains/JetBrainsMono](https://github.com/JetBrains/JetBrainsMono/blob/master/OFL.txt) |

No hay bibliotecas de iconos. Los iconos y el arte del avatar son medios generados con Higgsfield (obligación 6).

### 4. Modelos, motores nativos y medios

| Pieza | Versión / fichero | Licencia | Fuente de la licencia | Cómo llega | Obligaciones |
|---|---|---|---|---|---|
| llama.cpp (`llama-server`) | build **b11609** (commit `fcac19079`), distribución oficial Windows x64 CUDA 12.4; hashes en `src/baxy_mind/data/llama_server.v1.json` | MIT | [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/LICENSE) | Lo aporta la persona (la release oficial) | Atribución si se redistribuye. |
| llama.cpp parcheado (`b11609-baxy-cache`) | `scripts/llama/cache_tools_prefix.patch` | MIT (obra derivada) | ídem | **El parche, en el repo**; el binario lo compila la persona | Conservar el aviso MIT de llama.cpp. |
| Runtime CUDA 12 (`cudart64_12`, `cublas64_12`, `cublasLt64_12`) | el de la release b11609 | NVIDIA CUDA EULA (redistribuible con condiciones) | [CUDA EULA](https://docs.nvidia.com/cuda/eula/index.html) | Lo aporta la persona (zip `cudart-llama-bin-win-cuda-12.4-x64` de llama.cpp) | BAXY no lo redistribuye. **Sin confirmar** el detalle si algún día se empaqueta. |
| Qwen3.5-4B (modelo base) | `Qwen3.5-4B-Q4_K_M.gguf` de `unsloth/Qwen3.5-4B-GGUF` | Apache-2.0 | [Qwen/Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/LICENSE) | Lo aporta la persona | Obligación 4. |
| Modelo ajustado de BAXY | `BAXY-Qwen3.5-4B-c3-Q4_K_M.gguf` | Apache-2.0 (derivado) | ídem | Se descarga de [Hugging Face](https://huggingface.co/REDSOULTM/BAXY-Qwen3.5-4B-GGUF) | Obligación 4. |
| Visión: proyector Qwen3.5-4B | `Qwen3.5-4B-mmproj-F16.gguf` (en CPU, mismo llama-server) | Apache-2.0 | [unsloth/Qwen3.5-4B-GGUF](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF) | Lo aporta la persona; opcional | Atribución. |
| Laya (System One, decisor en CPU) | `layam-long-s1-Q8_0.gguf`, ajustado de `laya-multilingual` (322M) | Apache-2.0; su base mmBERT es MIT | [convaiinnovations/laya-multilingual](https://huggingface.co/convaiinnovations/laya-multilingual), [jhu-clsp/mmBERT-base](https://huggingface.co/jhu-clsp/mmBERT-base) | Lo aporta la persona; opcional | Atribución. **Sin confirmar** que la base sea exactamente esta ficha: el código dice «laya-multilingual 322M», que coincide con ella. Lo sirve un `llama-server` con la ruta `/v1/systemone`, que no es la de b11609 estándar: **sin confirmar** el origen y la licencia de ese binario. |
| Gemma 4 E2B (candidato anterior en `assets.manifest.json`) | `gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf` | Apache-2.0 | [google/gemma-4-E2B-it](https://huggingface.co/google/gemma-4-E2B-it) | Lo aporta la persona; sólo como alternativa | Atribución. |
| Supertonic 3 (voz) | `sherpa-onnx-supertonic-3-tts-int8-2026-05-11` + mezcla propia `baxy-supertonic` | **OpenRAIL-M** | [Supertone/supertonic-3](https://huggingface.co/Supertone/supertonic-3/blob/main/LICENSE) | Lo aporta la persona | **Obligación 1** (restricciones de uso y declarar que la voz es sintética). |
| Parakeet Ultra (reconocimiento) | `parakeet-ultra-sherpa-int8-oli` (int8, sherpa-onnx) | CC-BY-4.0 | ver obligación 3 | Lo aporta la persona | Obligación 3. |
| Parakeet TDT 0.6B v3 (alternativa) | `sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` | CC-BY-4.0 | [nvidia/parakeet-tdt-0.6b-v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) | Lo aporta la persona | Atribución a NVIDIA. |
| Nemotron 3.5 ASR streaming (opcional) | `sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-560ms-int8-2026-06-11` | OpenMDW-1.1 (permisiva) | [nvidia/nemotron-3.5-asr-streaming-0.6b](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b), [texto](https://openmdw.ai/license/1-1/) | Lo aporta la persona; opcional | Al redistribuir: copia de la licencia y avisos de origen. El script `install_nemotron_streaming_stt.ps1` que cita el manifiesto no existe en esta rama. |
| Palabra de activación «k4» | paquete externo `baxy-wake-k4`: `encoder_kroko_es.onnx` + `head.onnx` propio, ejecutado con onnxruntime y kaldi-native-fbank | Encoder: **CC-BY-SA** (Kroko); cabeza: propia | [Banafo/Kroko-ASR](https://huggingface.co/Banafo/Kroko-ASR) | Lo aporta la persona | **Obligación 2.** |
| Silero VAD v6 | `silero_vad.onnx` dentro de la rueda `silero-vad` 6.2.1 | MIT | [snakers4/silero-vad](https://github.com/snakers4/silero-vad/blob/master/LICENSE) | Se instala | Ninguna extra. |
| ONNX Runtime | 1.27.0 (rueda Python; también la usa sherpa-onnx) | MIT | [microsoft/onnxruntime](https://github.com/microsoft/onnxruntime/blob/main/LICENSE) | Se instala | Ninguna extra. |
| WebRTC AEC3 (vía pywebrtc-audio) | vendorizado en la rueda | BSD-3-Clause + concesión de patentes de WebRTC | `LICENSE` y `WEBRTC-PATENTS` dentro de la rueda | **En el repo** (rueda parcheada) | Ya incluidos en la rueda (tabla 6). |
| Windows OCR (`Windows.Media.Ocr`) | API de Windows | Términos de Windows | — | Del sistema | Ninguna. |
| Tesseract OCR (alternativa si falla Windows OCR) | la que haya instalada | Apache-2.0 | [tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE) | Lo aporta la persona | Ninguna mientras no se redistribuya. |
| Voces SAPI/OneCore de Windows (degradación) | del sistema | Términos de Windows | — | Del sistema | Ninguna. |
| Clips, fondos e icono del avatar | 37 `.mp4`, 2 `.jpg`, `.png`, `.ico` | Términos de Higgsfield (no es licencia abierta) | [Higgsfield](https://higgsfield.ai/creator-hub/help-center/account/who-owns-my-generations-and-can-i-use-them-commercially) | **En el repo** | **Obligación 6.** |

Lo que no aparece en este repositorio: `mpv` y `yt-dlp` no se invocan (sólo aparece «mpv» en un comentario de
`CoreProcessClient.cs`), no hay Piper en el runtime (sólo una ruta antigua en el manifiesto de activos) y LiveKit
sólo aparece como herramienta de entrenamiento y en comentarios.

### 5. Python, .NET y Edge que la persona instala

CPython 3.12 (PSF-2.0), el SDK de .NET 10 (MIT) y el runtime Edge WebView2 (términos de Microsoft) los instala la
persona desde sus fuentes oficiales; `scripts/bootstrap.ps1` sólo comprueba que existan. BAXY no los redistribuye.

### 6. Ruedas parcheadas y parches (`runtime_wheels/`, `scripts/llama/`)

Todas son **obras derivadas** de proyectos permisivos y deben seguir bajo la licencia de su origen.

| Fichero | Origen | Licencia | Qué cambia | Avisos incluidos | Falta |
|---|---|---|---|---|---|
| `sherpa_onnx-1.13.4+baxy.2-cp312-cp312-win_amd64.whl` | sherpa-onnx `v1.13.4` (commit `14280725…`) | Apache-2.0 ([LICENSE](https://github.com/k2-fsa/sherpa-onnx/blob/master/LICENSE)) | Decodificación greedy por stream con el modelo NeMo; normalización estable (PR #3857 de upstream) | `licenses/LICENSE`, `BAXY-NOTICE.txt` (qué cambió), `baxy_native_build.json` (procedencia) | **Sin confirmar** si debe añadir el aviso de pybind11. |
| `sherpa_onnx-1.13.4+baxy.1-…whl` | ídem | Apache-2.0 | Versión anterior, guardada como vuelta atrás | Igual | — |
| `sherpa-nemo-stream-decoder.patch` | sobre sherpa-onnx | Apache-2.0 | Ficheros `offline-recognizer-transducer-nemo-impl.h` y relacionados | — | Una cabecera que diga «modificado por BAXY, Apache-2.0» (apartado 4(b) de Apache). |
| `sherpa-nemo-normalization.patch` | sobre sherpa-onnx; incorpora el commit upstream `0967a08d` (PR #3857, autor externo) | Apache-2.0 | `math.cc` y `math-test.cc` | — | Ídem, citando el PR de origen. |
| `pywebrtc_audio-0.2.0+baxy.1-cp312-cp312-win_amd64.whl` | pywebrtc-audio 0.2.0 | Apache-2.0 ([LICENSE](https://github.com/strands-labs/pywebrtc-audio/blob/main/LICENSE)) + vendorizados: WebRTC (BSD-3-Clause + patentes), Abseil (Apache-2.0), JsonCpp (MIT o dominio público), rnnoise (BSD-3-Clause), PFFFT (tipo BSD), Ooura FFT (permisiva propia) | Expone la señal lineal de AEC3; el DSP no cambia | `licenses/LICENSE` (con la sección de terceros), `licenses/NOTICE`, `licenses/WEBRTC-PATENTS`, `BAXY-NOTICE.txt` | El aviso BSD-3-Clause de **pybind11 3.0.1**, con el que se compiló. |
| `webrtc-linear-output.patch` | sobre `bindings/webrtc_audio_bindings.cpp` de pywebrtc-audio | Apache-2.0 | Binding | — | Cabecera de modificación. |
| `scripts/llama/cache_tools_prefix.patch` | llama.cpp b11609 | MIT | Caché del prefijo de herramientas en `llama-server` | — | Ninguna obligatoria; conviene una cabecera MIT de llama.cpp. |

---

## Pendiente o sin confirmar

1. **Kroko (wake word):** versión exacta de CC-BY-SA y si la cabeza `head.onnx` cuenta como adaptación.
2. **Higgsfield:** versión de los Términos de Uso vigente al generar los clips; decidir cómo excluir esos medios de
   la licencia MIT.
3. **Laya / System One:** que la base sea `convaiinnovations/laya-multilingual` y de dónde sale el `llama-server`
   con `/v1/systemone`.
4. **Windows SDK projections** (`Microsoft.Windows.SDK.NET.dll`) en la publicación *self-contained*: que la
   licencia del SDK permita redistribuirlas.
5. **pybind11** en la rueda de sherpa-onnx; torchaudio, BSD de 2 o 3 cláusulas.
6. **CUDA EULA**, sólo si algún día el paquete incluye el runtime CUDA.
7. **Coherencia del lock:** `kaldi-native-fbank` está en `requirements-voice.txt` y no en el lock.

## Avisos de los ficheros incluidos

Ficheros de terceros que van dentro de este repositorio (la interfaz compilada en `src/Baxy.FieldUi/dist/`):

**React, React DOM y scheduler** (MIT)

```text
MIT License

Copyright (c) Meta Platforms, Inc. and affiliates.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

**Fuentes** (SIL Open Font License 1.1, texto oficial en <https://openfontlicense.org/open-font-license-official-text/>)

- Inter: Copyright (c) 2016 The Inter Project Authors (<https://github.com/rsms/inter>).
- JetBrains Mono: Copyright 2020 The JetBrains Mono Project Authors (<https://github.com/JetBrains/JetBrainsMono>).
- Chakra Petch: Copyright 2018 The Chakra Petch Project Authors (<https://github.com/cadsondemak/Chakra-Petch>).

Las ruedas de `runtime_wheels/` llevan dentro sus propias licencias y avisos (tabla 6).

Al redistribuir un paquete binario de BAXY hay que añadir además el texto completo de: Apache-2.0, MIT (con los
avisos de llama.cpp, .NET y ONNX Runtime), BSD-3-Clause (WebView2, WebRTC, pybind11), CC-BY-4.0, CC-BY-SA (versión
por confirmar), OpenRAIL-M (con su Anexo A) y OpenMDW-1.1.
