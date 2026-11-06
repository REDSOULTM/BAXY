# Avisos de terceros (THIRD_PARTY_NOTICES)

> Inventario hecho leyendo los manifiestos del repositorio, con cada licencia comprobada en su fuente oficial
> (registro del paquete, repositorio o ficha del modelo) el 2026-10-31. Lo que no se pudo confirmar está marcado
> **«sin confirmar»**. Este documento no es asesoría legal. El 2026-11-06 se cotejó contra el contenido real del zip de
> la versión 1.2.0, binarios incluidos: lo hallado así va marcado **«medido en el zip»**. El 2026-11-06 se quitó del paquete 1.3.0
> lo no permisivo que no hacía falta, buscando las marcas de lo quitado en los binarios del paquete armado, salvo dentro de los bundles comprimidos de
> `Baxy.exe` y `baxy-core.exe` (`scripts/check_package_licenses.py`). Los textos
> completos están en [`licenses/`](licenses/README.md).

El código propio de BAXY se publica bajo la [licencia MIT](LICENSE). Las piezas de terceros que BAXY usa,
instala o distribuye **conservan su propia licencia**, que la licencia MIT de BAXY no sustituye ni amplía.

**Los pesos de los modelos no están en el repositorio.** BAXY no descarga modelos por su cuenta
(`assets.manifest.json`: «BAXY no descarga modelos automáticamente»): cada persona los obtiene aparte (ver
[README.md](README.md)) y declara su ruta. Quien los obtenga acepta la licencia de cada modelo.
Los paquetes de Steam y de GitHub sí los llevan: ver [«El paquete de Steam»](#el-paquete-de-steam-rama-steam-build).

Cómo leer la columna «Cómo llega»:

- **En el repo**: el fichero de terceros está versionado en este repositorio (se redistribuye al clonar).
- **En el paquete**: no está en el repo, pero el instalador o la publicación del producto lo copia.
- **Se instala**: lo instala un script desde su registro oficial (PyPI, NuGet, npm) con versión fijada.
- **Lo aporta la persona**: BAXY lo usa si existe en la máquina; no lo trae ni lo descarga.
- **Del sistema**: componente de Windows.

---

## ¿Algo impide que el código propio sea MIT?

**No se encontró nada que impida publicar el código propio como MIT, y el barrido de los binarios de 1.3.0 no halló código GPL ni LGPL** (busca lo que se quitó; una revisión a ciegas barrió además los textos de licencia y los binarios de Python).

- **1.2.0 sí lo lleva** (medido en el zip): eSpeak NG (GPL-3.0-or-later) dentro de sherpa-onnx, que declara Apache-2.0;
  libquadmath (LGPL-2.1-or-later) en la OpenBLAS de numpy, y autocommand (LGPLv3) vendorizado en setuptools. Ver obligación 0.
- **Ningún paquete distribuido declara GPL/LGPL/AGPL** en el lock de Python (28 paquetes de runtime y 11 de pruebas; scipy, sólo de pruebas y no distribuido, lleva el runtime de GCC, GPL-3.0-or-later con excepción), ni en NuGet, ni en el grafo npm
  de la interfaz (191 paquetes), y la búsqueda de cabeceras GPL/LGPL en `src/`, `scripts/` y `tests/` no devolvió nada.
- Los parches de `runtime_wheels/` modifican código **Apache-2.0** (sherpa-onnx y pywebrtc-audio) y el de
  `scripts/llama/` modifica código **MIT** (llama.cpp). Ambas licencias son compatibles con MIT.
- **Copyleft débil que sigue en el paquete: Eigen (MPL-2.0),** compilado dentro de `_sherpa_onnx…pyd` y de los binarios de ONNX Runtime (obligación 0). Actúa por fichero y
  sólo sobre Eigen, que va sin modificar. `lightningcss` (MPL-2.0) sólo compila la interfaz: no llega al paquete.
- Matiz: un parche es una obra derivada del fichero que modifica. Lo prudente es que los `.patch` y las ruedas
  parcheadas sigan bajo la licencia de su proyecto de origen (Apache-2.0 o MIT) y no se presenten como «MIT de
  BAXY». En particular, `sherpa-nemo-normalization.patch` incorpora la corrección de un contribuidor externo de
  sherpa-onnx (PR #3857), con su autoría y bajo Apache-2.0.

---

## Obligaciones y restricciones a tener en cuenta

Ordenadas por peso. Lo que es sólo atribución está al final.

### 0. Lo que se quitó en 1.3.0, y Eigen (MPL-2.0), que queda

| Pieza | Licencia | Por qué estaba | Qué se hizo |
|---|---|---|---|
| eSpeak NG y piper-phonemize, en `_sherpa_onnx…pyd` y `sherpa-onnx-c-api.dll` | [GPL-3.0-or-later](https://github.com/espeak-ng/espeak-ng/blob/master/README.md#license-information); MIT | sherpa-onnx los compila siempre que su voz está activa | `sherpa-no-espeak.patch` los deja fuera: la voz de BAXY, Supertonic, no los usa. Tampoco va `sherpa-onnx-core`, cuyo único fichero necesario, `onnxruntime.dll`, pasa a la rueda |
| libquadmath, OpenBLAS y runtime de gfortran, en `numpy.libs` | LGPL-2.1-or-later; BSD; GPL-3.0 con excepción de runtime | La rueda oficial de numpy para Windows | numpy 1.26.4 compilado de su fuente sin BLAS (`scripts/build_runtime_wheels.py`) |
| autocommand, en setuptools | LGPLv3 | setuptools venía con torch | Fuera: la mente no lo importa |
| Intel oneMKL en `torch_cpu.dll`, `libiomp5md.dll` | Licencias de Intel | Venían con torch | Fuera, con torch, torchaudio, transformers y sentence-transformers: la mente no los importa |
| `libportaudio64bit-asio.dll` | PortAudio MIT + ASIO de Steinberg, términos sin confirmar | sounddevice lo trae; sólo se carga con `SD_ENABLE_ASIO` | `build_steam.ps1` lo borra |
| certifi y tqdm | MPL-2.0 | Los pedían httpx y huggingface-hub | Fuera: `anthropic` usa `httpx2`, que valida con `truststore` |
| `google/_upb/_message.pyd`, de protobuf | BSD-3-Clause, enlazado con GCC: CRT de mingw-w64 y objetos de libgcc | ONNX Runtime lo pide para sus herramientas | `build_steam.ps1` lo borra: cargar y correr un modelo no lo importa |

- **Sólo las versiones nuevas cambian.** 1.2.0 y 1.2.1, ya publicadas, siguen llevando eSpeak NG (GPL-3.0-or-later) y 1.2.0 además libquadmath y autocommand (LGPL). La página de 1.2.0 lo corrige desde el 2026-11-06 y remite a la de 1.2.1, que trae como activos el código fuente de eSpeak NG, piper-phonemize y sherpa-onnx (`espeak-ng-ed530aa-source.zip`, `piper-phonemize-f3ff95a-source.zip`, `sherpa-onnx-1.13.4-baxy.2-source.zip`, `sherpa-onnx-1.13.4-dependencies-source.zip`); los textos `GPL-3.0.txt`, `LGPL-2.1.txt` y `FUENTES_GPL.md` de esas versiones van en su `baxy-1.2.1-licenses.zip`.
- **Lo que sherpa-onnx compila dentro en 1.3.0** (medido el 2026-11-06 con su `cmake` y las opciones de
  `scripts/build_sherpa_runtime.py`): kaldi-native-fbank, kaldi-decoder, kaldifst, OpenFst y simple-sentencepiece (Apache-2.0), kissfft
  (BSD-3-Clause), Eigen (sobre todo MPL-2.0), hclust-cpp con fastcluster (BSD-2-Clause), nlohmann/json (MIT) y pybind11
  (BSD-3-Clause). Cada texto, en `licenses/`.
- **Eigen, MPL-2.0:** kaldi-decoder lo necesita para reconocer voz y ONNX Runtime para correr los modelos, así que no se puede quitar. El de sherpa-onnx sólo incluye `Eigen/Dense`. Su `COPYING.README` dice que es «primarily MPL2» con terceros BSD y compatibles. El apartado 3.2(a) de la MPL pide decir dónde está su fuente:
  `licenses/FUENTES.md`.

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
- **Se redistribuye en los paquetes de Steam y de GitHub** (no está en el repo). El párrafo 4 pide: (a) incluir las
  restricciones del Anexo A como cláusula exigible en el acuerdo que rija ese uso y avisar a quien lo reciba: desde 1.3.0 están
  en la sección 3 del acuerdo del instalador, **literales** en inglés y traducidas en español (vale el inglés), aplicadas a la voz, a sus derivados y a lo que genere; (b) darle una copia de la licencia, `licenses/OpenRAIL-M-Supertonic-3.txt`; (c) marcar
  los ficheros modificados y (d) conservar los avisos, `licenses/ATRIBUCIONES_MODELOS.md`.
- El párrafo 7 pide además «reasonable efforts to use the latest version of the Model».
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
- La palabra de activación del paquete, v3_b2, no lleva este encoder: es una red propia entrenada imitándolo. **Medido el 2026-11-06:**
  comparada con `encoder_kroko_es.onnx`, de 944 tensores de 64 valores o más, ninguno es igual a uno de los 127 de `head.onnx`, y entre
  8749 pares de la misma forma la correlación mayor es 0,46. Eso dice que no copia sus pesos, no si imitarlo la hace adaptación.
  Su atribución va por prudencia en `licenses/ATRIBUCIONES_MODELOS.md`.
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
  redistribuir; para el uso basta con mantener la atribución en la documentación. En el paquete, en
  `licenses/ATRIBUCIONES_MODELOS.md`.

### 4. Qwen3.5-4B y el modelo ajustado de BAXY: Apache-2.0

- [`Qwen/Qwen3.5-4B`](https://huggingface.co/Qwen/Qwen3.5-4B) está bajo **Apache-2.0**
  ([LICENSE](https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/LICENSE)), sin restricciones de uso adicionales
  ni la antigua «Qwen License»; el repositorio no trae fichero `NOTICE`. El GGUF de producción y el proyector de
  visión (`mmproj-F16.gguf`) vienen de [`unsloth/Qwen3.5-4B-GGUF`](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF),
  también Apache-2.0.
- Los paquetes desde 1.2.0 llevan `BAXY-Qwen3.5-4B-ft-c3-c4c2_1-sA-Q4_K_M.gguf`, un ajuste posterior que no está en la ficha de abajo.
- El modelo de BAXY (`BAXY-Qwen3.5-4B-c3-Q4_K_M.gguf`, LoRA fusionado y cuantizado a Q4_K_M) es una **obra
  derivada** de Qwen3.5-4B. Se publica aparte en
  [huggingface.co/REDSOULTM/BAXY-Qwen3.5-4B-GGUF](https://huggingface.co/REDSOULTM/BAXY-Qwen3.5-4B-GGUF), no en este
  repositorio. Según la receta de entrenamiento (interna, no publicada en este repositorio), se entrenó con datos propios y
  sintéticos, sin conjuntos públicos.
- **Obligación al publicarlo:** incluir copia de Apache-2.0, avisar en la ficha de que se modificó el modelo
  original y conservar los avisos de Qwen. En el paquete: `licenses/Qwen3.5-4B-LICENSE.txt` y
  `licenses/ATRIBUCIONES_MODELOS.md`.

### 5. Ficheros de terceros que ya están en el repo: copiar sus avisos

- **Fuentes tipográficas (OFL-1.1)** en `src/Baxy.FieldUi/dist/assets/*.woff2` (subconjunto latino de
  `@fontsource`): Inter, JetBrains Mono y Chakra Petch. La OFL exige que cada copia redistribuida lleve el aviso de
  copyright y la licencia, y prohíbe vender las fuentes solas. Los avisos están en
  [«Avisos de los ficheros incluidos»](#avisos-de-los-ficheros-incluidos).
- **React y React DOM (MIT)** van compilados dentro de `dist/assets/index-*.js` y Vite quitó sus comentarios de
  licencia; el aviso MIT de React está en [«Avisos de los ficheros incluidos»](#avisos-de-los-ficheros-incluidos).
- **Ruedas binarias de `runtime_wheels/`** (ver tabla 6): llevan dentro sus licencias, el `NOTICE` de
  pywebrtc-audio, el aviso de patentes de WebRTC y un `BAXY-NOTICE.txt` que dice qué ficheros se cambiaron. Los `.patch` sueltos siguen sin
  cabecera (tabla 6). **Falta** el aviso BSD-3-Clause de **pybind11** (con el que se compiló la
  extensión de pywebrtc-audio). La extensión de sherpa-onnx también lo lleva (medido en el zip): su aviso está en
  `licenses/pybind11-LICENSE.txt`.
- **Modelo de identificación de idioma de py3langid 0.3.0 (BSD-3-Clause)** en `src/baxy_mind/data/langid/`
  (`model.plzma`, de langid.py de Marco Lui y Timothy Baldwin; fork de Adrien Barbaresi): la voz elige con él si cada
  respuesta se dice en español o en inglés. Va con su `LICENSE` y un `PROVENANCE.txt` (versión, origen, sha256); el
  código de clasificación es propio (`language_id.py`), no se copió el `langid.py` del paquete.

### 6. Vídeos e imagen del avatar: términos de Higgsfield (sin licencia abierta)

- Los 37 clips de `src/Baxy.FieldUi/public/clips` (y su copia en `dist/clips`), los fondos `public/bg/*.jpg` y el
  icono (`baxy-icon-64.png`, `Baxy.App/Assets/baxy.ico`, hecho «desde el arte de Higgsfield») se generaron con
  Higgsfield. **No tienen licencia abierta**: su uso se rige por los Términos de Uso de Higgsfield.
- Según el [centro de ayuda de Higgsfield](https://higgsfield.ai/creator-hub/help-center/account/who-owns-my-generations-and-can-i-use-them-commercially),
  la empresa no reclama la propiedad de lo generado y permite el uso comercial sin atribución, pero **prohíbe usar
  esas salidas para entrenar o mejorar modelos de IA**
  ([Términos de Uso](https://higgsfield.ai/terms-of-use-agreement) del 23 de octubre de 2026, 4.4 y 5.2(iv)), y otras personas
  pueden generar resultados parecidos. Su apartado 5.5 pide declarar que son generados donde la ley lo exija y no quitar sus
  marcas de procedencia.
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
| .NET SDK / runtime | SDK `10.0.100` (`global.json`), `net10.0-windows10.0.19041.0` | MIT | [dotnet/runtime](https://github.com/dotnet/runtime/blob/main/LICENSE.TXT) | Se instala (SDK); **en el paquete** (`build_product.ps1` publica *self-contained*) | Al publicar *self-contained* se redistribuye el runtime: sus avisos están en `licenses/dotnet-*`, los de la versión 10.0.14 que lleva el paquete. |
| WPF / Windows Desktop | la del SDK | MIT | [dotnet/wpf](https://github.com/dotnet/wpf/blob/main/LICENSE.TXT) | En el paquete | Igual que el runtime. |
| Proyecciones del Windows SDK (`Microsoft.Windows.SDK.NET.Ref`) | 10.0.19041.x (implícita) | Licencia del Windows SDK (propietaria) | [aka.ms/WinSDKLicenseURL](https://aka.ms/WinSDKLicenseURL) | En el paquete | **Redistribuible:** la [lista REDIST del SDK](https://learn.microsoft.com/en-us/legal/windows-sdk/redist) (2024-10-21) dice que estos ficheros «may be distributed unmodified as a NuGet package, or as part of your program in order to enable your application to call WinRT Apis». El de `Baxy.exe` es byte a byte el del NuGet 10.0.19041.57. La licencia del SDK, apartado 2.a, pide además añadir funciones propias, que quien lo reciba acepte términos que lo protejan igual, mostrar el copyright propio e indemnizar a Microsoft por lo que se distribuya. |
| Microsoft.Web.WebView2 | 1.0.4078.44 | BSD-3-Clause (texto de Microsoft) + `NOTICE.txt` de terceros | `LICENSE.txt` y `NOTICE.txt` dentro del [paquete NuGet](https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.4078.44) | Se instala; **en el paquete** (`WebView2Loader.dll` y ensamblados, `Baxy.Setup/PackageContract.cs`) | `LICENSE.txt` y `NOTICE.txt` van en `licenses/WebView2-*`. El runtime Edge WebView2 es **del sistema**. |
| Microsoft.NET.Test.Sdk | 17.9.0 | MIT | [microsoft/vstest](https://github.com/microsoft/vstest/blob/main/LICENSE) | Se instala (sólo pruebas) | No se distribuye. |
| NUnit | 4.1.0 | MIT | [nunit/nunit](https://github.com/nunit/nunit/blob/main/LICENSE.txt) | Se instala (sólo pruebas) | No se distribuye. |
| NUnit3TestAdapter | 4.5.0 | MIT | [nunit3-vs-adapter](https://github.com/nunit/nunit3-vs-adapter/blob/main/LICENSE) | Se instala (sólo pruebas) | No se distribuye. |

### 2. Python (runtime de la mente y la voz)

Se instalan desde PyPI con `--require-hashes` (`pylock.runtime-win-x64.toml`, `scripts/setup_mind_voice.ps1`), salvo
sherpa-onnx, numpy y silero-vad, de la tabla 6, que vienen del repo. Licencia leída de los metadatos PyPI de **esa versión
exacta** y, cuando faltaban, del repositorio del proyecto.

| Paquete | Versión | Licencia (SPDX) | Paquete | Versión | Licencia (SPDX) |
|---|---|---|---|---|---|
| annotated-types | 0.8.0 | MIT | onnxruntime | 1.27.0 | MIT |
| anthropic | 2.6.0 | Apache-2.0 | opentelemetry-api | 1.45.2 | Apache-2.0 |
| anyio | 4.14.2 | MIT | packaging | 26.2 | Apache-2.0 OR BSD-2-Clause |
| cffi | 2.1.0 | MIT-0 | protobuf | 7.35.1 | BSD-3-Clause |
| docstring-parser | 0.18.0 | MIT | pycparser | 3.0 | BSD-3-Clause |
| flatbuffers | 25.12.19 | Apache-2.0 | pydantic | 2.14.3 | MIT |
| h11 | 0.16.0 | MIT | pydantic-core | 2.50.4 | MIT |
| httpcore2 | 2.16.0 | BSD-3-Clause | pypdf | 6.18.1 | BSD-3-Clause |
| httpx2 | 2.16.0 | BSD-3-Clause | **sherpa-onnx** | 1.13.4+baxy.3 | Apache-2.0 (tabla 6) |
| idna | 3.18 | BSD-3-Clause | **silero-vad** | 6.2.1+baxy.1 | MIT (tabla 6; incluye `silero_vad.onnx`) |
| jiter | 0.18.0 | MIT | sniffio | 1.3.1 | MIT OR Apache-2.0 |
| kaldi-native-fbank | 1.22.3 | Apache-2.0 | sounddevice | 0.5.5 | MIT (incluye PortAudio, licencia tipo MIT) |
| **numpy** | 1.26.4+baxy.1 | BSD-3-Clause (tabla 6) | truststore | 0.10.5 | MIT |
| typing-extensions | 4.16.0 | PSF-2.0 | typing-inspection | 0.4.5 | MIT |

Notas:

- **Lock regenerado el 2026-11-06 con `lock_python_dependencies.ps1`: de 69 a 28 paquetes;** el paquete armado lleva 27, sin protobuf. Son los que
  necesitan la mente, el texto de los PDF y el modelo por API. El resto sólo lo piden scripts de investigación (`requirements-research-win-x64.txt`) y no va en el paquete.
- **Sin el texto de su licencia en la rueda** (medido en el zip de 1.2.0): flatbuffers, Apache-2.0: va en `licenses/Apache-2.0.txt`.
  onnxruntime lo trae en su carpeta, no en `dist-info`.
- **PortAudio de sounddevice:** el paquete sólo lleva `libportaudio64bit.dll`, sin ASIO. Su
  [README](https://github.com/spatialaudio/portaudio-binaries#copyright) da PortAudio como MIT; el texto, en `licenses/PortAudio-LICENSE.txt`.
- **`pydantic_core` y `jiter` llevan crates de Rust** con otras licencias además de MIT y Apache-2.0, sobre todo Unicode-3.0, y `foldhash`
  con Zlib, según las listas CycloneDX de sus ruedas: `licenses/CRATES_RUST.md`. **Sin copiar:** el aviso de copyright de cada crate.
- **La cancelación de eco no va en el paquete, y no es de 1.3.0:** `voice_echo.py` importa `pyaudiowpatch` y `pywebrtc_audio`, que salieron del
  lock en `22b470dd0`. Sin ellos, la voz sigue con el eco apagado. Sus filas de abajo describen la rueda que queda en el repo.
- **El Python embebido lleva OpenSSL 3.0.16** (`libcrypto-3.dll`, `libssl-3.dll`, Apache-2.0), expat, libmpdec y zlib, que su
  `LICENSE.txt` no cita: `licenses/OpenSSL-LICENSE.txt` y `Python-Licenses-and-Acknowledgements.txt`, la lista oficial de CPython
  para esa versión.
- `livekit-wakeword` se usó para entrenar wake words (`scripts/baxy-wakeword-production.yaml`, con VoxCPM,
  Apache-2.0, como TTS de entrenamiento). La mente no lo importa en tiempo de ejecución.

**Pruebas y calidad** (sólo desarrollo, no se distribuyen): pytest 9.1.1 (MIT), pluggy 1.6.0 (MIT), iniconfig 2.3.0
(MIT), colorama 0.4.6, jinja2 3.1.6, markupsafe 3.0.3, psutil 7.2.2 y pygments 2.20.0 (BSD), scipy 1.17.1 (BSD-3-Clause, con OpenBLAS y el runtime de GCC en `scipy.libs`), numpy y packaging (como arriba), ruff 0.15.22 (MIT).

**Scripts de investigación** (los bancos de medición internos, que no se publican en este repositorio; no son runtime): usaban modelos de embeddings
[`intfloat/multilingual-e5-small`](https://huggingface.co/intfloat/multilingual-e5-small) (MIT) y
[`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
(Apache-2.0), que descarga la biblioteca al ejecutarlos. Sus paquetes están en `requirements-research-win-x64.txt`: entre ellos, torch
lleva Intel oneMKL dentro, sin su licencia en la rueda, y setuptools lleva autocommand (LGPLv3). Nada de eso se distribuye.

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
| llama.cpp (`llama-server`) | build **b11609** (commit `fcac19079`), distribuciones oficiales Windows x64 CUDA 12.4 y Vulkan; hashes en `src/baxy_mind/data/llama_server.v1.json` | MIT | [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/LICENSE) | Lo aporta la persona (la release oficial); el paquete de tiendas lleva las dos carpetas | Atribución si se redistribuye: el aviso va en `licenses/LICENSE-llama.cpp.txt` del paquete. `stb_image`, en `mtmd.dll`, y `subprocess.h`, en `llama-common.dll`, son de dominio público o Unlicense según sus cabeceras. llama-server lleva compilados [cpp-httplib y BoringSSL](https://github.com/ggml-org/llama.cpp/blob/fcac19079/vendor/cpp-httplib/CMakeLists.txt) y nlohmann/json: `licenses/cpp-httplib-LICENSE.txt`, `BoringSSL-LICENSE.txt` y `nlohmann-json-LICENSE.txt`. `libomp.dll` (LLVM OpenMP, Apache-2.0 WITH LLVM-exception) lleva su licencia al lado: `LICENSE-LLVM-OpenMP`. |
| llama.cpp parcheado (`b11609-baxy-cache`) | `scripts/llama/cache_tools_prefix.patch` | MIT (obra derivada) | ídem | **El parche, en el repo**; el binario lo compila la persona | Conservar el aviso MIT de llama.cpp. |
| Runtime CUDA 12 (`cudart64_12`, `cublas64_12`, `cublasLt64_12`) | el de la release b11609 | NVIDIA CUDA EULA (redistribuible con condiciones) | [CUDA EULA](https://docs.nvidia.com/cuda/eula/index.html) | Lo aporta la persona (zip `cudart-llama-bin-win-cuda-12.4-x64` de llama.cpp); **en el paquete** de Steam y de GitHub, carpeta `llama` | Ver [«Runtime CUDA 12»](#runtime-cuda-12-en-el-paquete). |
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
| Silero VAD v6 | `silero_vad.onnx` dentro de la rueda `silero-vad` 6.2.1+baxy.1 (tabla 6) | MIT | [snakers4/silero-vad](https://github.com/snakers4/silero-vad/blob/master/LICENSE) | **En el repo** | Ninguna extra. |
| ONNX Runtime | 1.27.0 (rueda Python; también la usa sherpa-onnx) | MIT; lleva Eigen (MPL-2.0) y lo demás de su `ThirdPartyNotices.txt` | [microsoft/onnxruntime](https://github.com/microsoft/onnxruntime/blob/main/LICENSE) | Se instala | Eigen: `licenses/FUENTES.md`. |
| WebRTC AEC3 (vía pywebrtc-audio) | vendorizado en la rueda | BSD-3-Clause + concesión de patentes de WebRTC | `LICENSE` y `WEBRTC-PATENTS` dentro de la rueda | **En el repo** (rueda parcheada) | Ya incluidos en la rueda (tabla 6). |
| Windows OCR (`Windows.Media.Ocr`) | API de Windows | Términos de Windows | — | Del sistema | Ninguna. |
| Tesseract OCR (alternativa si falla Windows OCR) | la que haya instalada | Apache-2.0 | [tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract/blob/main/LICENSE) | Lo aporta la persona | Ninguna mientras no se redistribuya. |
| Voces SAPI/OneCore de Windows (degradación) | del sistema | Términos de Windows | — | Del sistema | Ninguna. |
| Clips, fondos e icono del avatar | 37 `.mp4`, 2 `.jpg`, `.png`, `.ico` | Términos de Higgsfield (no es licencia abierta) | [Higgsfield](https://higgsfield.ai/creator-hub/help-center/account/who-owns-my-generations-and-can-i-use-them-commercially) | **En el repo** | **Obligación 6.** |

Lo que no aparece en este repositorio: `mpv` y `yt-dlp` no se invocan (sólo aparece «mpv» en un comentario de
`CoreProcessClient.cs`), no hay voces Piper en el runtime (sólo una ruta antigua en el manifiesto de activos; desde 1.3.0 el sherpa-onnx
de BAXY tampoco podría cargarlas: obligación 0) y LiveKit
sólo aparece como herramienta de entrenamiento y en comentarios.

### 5. Python, .NET y Edge que la persona instala

CPython 3.12 (PSF-2.0), el SDK de .NET 10 (MIT) y el runtime Edge WebView2 (términos de Microsoft) los instala la
persona desde sus fuentes oficiales; `scripts/bootstrap.ps1` sólo comprueba que existan. Fuera de los paquetes de Steam y de
GitHub, BAXY no los redistribuye.

### 6. Ruedas parcheadas y parches (`runtime_wheels/`, `scripts/llama/`)

Todas son **obras derivadas** de proyectos permisivos y deben seguir bajo la licencia de su origen.

| Fichero | Origen | Licencia | Qué cambia | Avisos incluidos | Falta |
|---|---|---|---|---|---|
| `sherpa_onnx-1.13.4+baxy.3-cp312-cp312-win_amd64.whl` | sherpa-onnx `v1.13.4` (commit `14280725…`) | Apache-2.0 ([LICENSE](https://github.com/k2-fsa/sherpa-onnx/blob/master/LICENSE)) | Decodificación greedy por stream con el modelo NeMo; normalización estable (PR #3857 de upstream); sin eSpeak NG ni piper-phonemize; lleva `onnxruntime.dll` de la rueda oficial `sherpa-onnx-core` | `licenses/LICENSE`, `BAXY-NOTICE.txt` (qué cambió), `baxy_native_build.json` (procedencia) | El aviso de pybind11 está en `licenses/pybind11-LICENSE.txt`. |
| `numpy-1.26.4+baxy.1-cp312-cp312-win_amd64.whl` | [numpy 1.26.4](https://pypi.org/project/numpy/1.26.4/), su fuente sin cambios | BSD-3-Clause y lo que numpy agrupa | Compilado sin BLAS: sin OpenBLAS, gfortran ni libquadmath | `LICENSE.txt`, `bundled/`, `BAXY-NOTICE.txt` | pocketfft y msun: en `licenses/`. |
| `silero_vad-6.2.1+baxy.1-py3-none-any.whl` | [silero-vad 6.2.1](https://pypi.org/project/silero-vad/6.2.1/), los mismos ficheros | MIT | Sin sus requisitos de torch y torchaudio | Los de la rueda, `BAXY-NOTICE.txt` | — |
| `sherpa-no-espeak.patch` | sobre sherpa-onnx | Apache-2.0 | Opción `SHERPA_ONNX_ENABLE_ESPEAK` en sus `CMakeLists.txt` y `offline-tts-impl.cc` | Los ficheros cambiados, en `BAXY-NOTICE.txt` de la rueda y en el README del activo de fuente | Ninguna cabecera en el `.patch`: su SHA-256 está fijado. |
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
4. ~~Windows SDK projections~~: resuelto el 2026-11-06, la lista REDIST las nombra (ver la tabla de .NET).
5. ~~torchaudio, BSD de 2 o 3 cláusulas~~: fuera del paquete desde 1.3.0.
6. **CUDA EULA:** revisada el 2026-11-06 (ver [«Runtime CUDA 12»](#runtime-cuda-12-en-el-paquete)). En GitHub, desde 1.3.0, parte
   aparte sólo para NVIDIA. Sigue abierta la duda del apartado 2.1 en el paquete único de Steam.
7. ~~Coherencia del lock~~: resuelto el 2026-11-04 (ver la nota del lock de Python).
8. **eSpeak NG (GPL), libquadmath y autocommand (LGPL):** fuera del paquete desde 1.3.0 (obligación 0). Siguen en 1.2.0 y 1.2.1, ya publicadas (ver la tabla de arriba), y las ruedas con eSpeak NG siguen en la historia de git.
9. **Intel** en torch y **ASIO** en sounddevice: fuera del paquete desde 1.3.0.
10. **Acuerdos:** desde 1.3.0 el acuerdo del instalador da BAXY para **cualquier uso, personal o comercial**, con copia y
    redistribución, sin restricción propia: las únicas son las de las licencias de terceros. Lleva el Anexo A literal de OpenRAIL-M
    aplicado sólo a la voz, sus derivados y lo que genere; la cláusula expresa de que no limita las licencias de terceros; CUDA
    (sólo para BAXY, sin ingeniería inversa, apartado 1.1.2 de su EULA), Microsoft, Eigen (MPL-2.0) y los medios de Higgsfield
    (fuera de la MIT). **Sin revisión jurídica.** El EULA de Steam (`documentacion/steam/EULA.md`) sigue diciendo «uso personal»:
    no se cambió (otro canal, con sus propias condiciones).

## El paquete de Steam (rama `steam-build`)

`scripts/build_steam.ps1` arma un paquete que **redistribuye** lo que antes «aportaba la persona». Cambia la columna
«Cómo llega» de estas piezas a **En el paquete de Steam**, con sus obligaciones al redistribuir:

| Pieza | Licencia | Qué exige al redistribuirla |
|---|---|---|
| CPython 3.12.10 embebido (python.org) | PSF-2.0 | Su `LICENSE.txt`, copiado a `licenses/Python-LICENSE.txt` |
| Lock de runtime (27 de sus 28 paquetes desde 1.3.0: protobuf no va) | Las de la tabla de Python | Las licencias que trae cada paquete dentro de `Lib/site-packages` |
| llama.cpp b11609 (oficial, CUDA) | MIT | Su aviso MIT, en `licenses/LICENSE-llama.cpp.txt` |
| Runtime CUDA 12 | NVIDIA CUDA EULA | Ver [«Runtime CUDA 12»](#runtime-cuda-12-en-el-paquete) |
| Modelo de BAXY y proyector de visión | Apache-2.0 | Copia de Apache-2.0 y aviso de modificación (obligación 4), en `licenses/` |
| Parakeet Ultra int8 | CC-BY-4.0 | Atribución a cada eslabón (obligación 3) |
| Voz de BAXY (Supertonic 3) | OpenRAIL-M | Las restricciones del Anexo A en la EULA de BAXY (la del instalador: `src/Baxy.Installer/Assets/license/`) y avisar que la voz es sintética (obligación 1) |
| Palabra de activación v3_b2 | Red propia, entrenada imitando al encoder Kroko y a k5; no lleva sus pesos (dicho por quien la entrenó y comparado el 2026-11-06 con `encoder_kroko_es.onnx`: obligación 2) | Por prudencia, la atribución y la licencia de Kroko (obligación 2), hasta confirmar si cuenta como adaptación (punto 1 de lo pendiente) |
| .NET 10 *self-contained* y WebView2 | MIT / BSD-3-Clause | Sus avisos de terceros |
| Runtime de Visual C++ (`vcruntime140*`, `msvcp140*`) | Licencia de Visual Studio, código redistribuible | Sólo los ficheros de la carpeta redistribuible, junto al ejecutable; Microsoft admite este despliegue y deja sus actualizaciones a cargo de BAXY. [Lo limita a quien tiene licencia de Visual Studio](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files). |

## Runtime CUDA 12 en el paquete

Los paquetes de Steam y de GitHub llevan en la carpeta `llama` `cudart64_12.dll` (versión de fichero 6.14.11.12040),
`cublas64_12.dll` y `cublasLt64_12.dll` (6.14.11.1245), los de la distribución de llama.cpp b11609. **Estos ficheros no están bajo la licencia MIT
de BAXY:** se rigen por la [EULA de CUDA Toolkit de NVIDIA](https://docs.nvidia.com/cuda/eula/index.html). Comprobado el
2026-11-06 en la [versión 12.4.1](https://docs.nvidia.com/cuda/archive/12.4.1/eula/index.html) (última actualización del
texto: 12 de enero de 2024) y en la vigente, v13.5 (26 de enero de 2026), con la misma redacción en todo lo citado aquí:

- **Se pueden redistribuir.** El Anexo A (2.6) los lista: «CUDA Runtime», `cudart.dll`; «CUDA BLAS Library», `cublas.dll`,
  `cublasLt.dll`, «including certain variations of these files that have version number or architecture specific
  information embedded in the file name», con el ejemplo `cudart64_90.dll`. Que `64_12` sea una de esas variaciones es la
  lectura de este documento, con ese ejemplo como apoyo; la EULA no lo define más.
- **Condiciones (1.1.1, 1.1.2 y 1.2), entre otras de la EULA, que pasan a quien lo redistribuya:** van incorporados en código
  objeto a una aplicación con funciones propias, sólo los usa esa aplicación, no se distribuyen sueltos, no se modifican ni se
  descompilan, y sus avisos se conservan. Tampoco se pueden usar aparte de BAXY. NVIDIA no patrocina ni respalda a BAXY. **1.1.2 pide
  además que los términos de la aplicación sean coherentes con la EULA: esa cláusula en el acuerdo es una propuesta pendiente del
  dueño,** y hasta entonces estas condiciones sólo se dicen aquí.
- **Esa parte aparte es un fichero público de la release,** aunque sólo la use el instalador, y lleva la carpeta entera, con su
  `llama-server`: si eso basta para «no se distribuyen sueltos» no lo dice la EULA. Sólo NVIDIA lo cierra.
- **Apartado 2.1:** el SDK se licencia para aplicaciones «only for use in systems with NVIDIA GPUs». **Desde 1.3.0, en GitHub, la
  carpeta `llama` va en una parte aparte (`baxy-<versión>-nvidia.zip.*`) que el instalador sólo baja si Windows le da una tarjeta
  NVIDIA (PCI 10DE):** en un equipo con AMD o Intel estos ficheros no llegan, y BAXY calcula con `llama-vulkan`. En 1.2.0 el paquete
  era uno solo y sí llegaban, sin cargarse. **El paquete de Steam sigue siendo uno solo,** con esa duda de lectura abierta. Sólo
  NVIDIA la cierra: su dirección para preguntas sobre esta EULA está en el apartado 2.5. Este documento no es asesoría legal.
- **Avisos:** el Anexo B (2.7) dice que algunas rutinas de cuBLAS se rigen además por las licencias de abajo, cuya cláusula
  para binarios exige reproducir estos avisos con la distribución. El aviso de 1.1.2 sobre código de muestra no aplica: no se
  distribuye código de muestra.

```text
Some of the cuBLAS library routines were written by or derived from code written by Vasily Volkov and are subject to the Modified Berkeley Software Distribution License as follows:
Copyright (c) 2007-2009, Regents of the University of California
All rights reserved.
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:
* Redistributions of source code must retain the above copyright
notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above
copyright notice, this list of conditions and the following
disclaimer in the documentation and/or other materials provided
with the distribution.
* Neither the name of the University of California, Berkeley nor
the names of its contributors may be used to endorse or promote
products derived from this software without specific prior
written permission.
THIS SOFTWARE IS PROVIDED BY THE AUTHOR "AS IS" AND ANY EXPRESS OR
IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

Some of the cuBLAS library routines were written by or derived from code written by Davide Barbieri and are subject to the Modified Berkeley Software Distribution License as follows:
Copyright (c) 2008-2009 Davide Barbieri @ University of Rome Tor Vergata.
All rights reserved.
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:
* Redistributions of source code must retain the above copyright
notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above
copyright notice, this list of conditions and the following
disclaimer in the documentation and/or other materials provided
with the distribution.
* The name of the author may not be used to endorse or promote
products derived from this software without specific prior
written permission.
THIS SOFTWARE IS PROVIDED BY THE AUTHOR "AS IS" AND ANY EXPRESS OR
IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

Some of the cuBLAS library routines were derived from code developed by the University of Tennessee and are subject to the Modified Berkeley Software Distribution License as follows:
Copyright (c) 2010 The University of Tennessee.
All rights reserved.
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:
* Redistributions of source code must retain the above copyright
notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above
copyright notice, this list of conditions and the following
disclaimer listed in this license in the documentation and/or
other materials provided with the distribution.
* Neither the name of the copyright holders nor the names of its
contributors may be used to endorse or promote products derived
from this software without specific prior written permission.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

Some of the cuBLAS library routines were written by or derived from code written by Jonathan Hogg and are subject to the Modified Berkeley Software Distribution License as follows:
Copyright (c) 2012, The Science and Technology Facilities Council (STFC).
All rights reserved.
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:
* Redistributions of source code must retain the above copyright
notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above
copyright notice, this list of conditions and the following
disclaimer in the documentation and/or other materials provided
with the distribution.
* Neither the name of the STFC nor the names of its contributors
may be used to endorse or promote products derived from this
software without specific prior written permission.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE STFC BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

Some of the cuBLAS library routines were written by or derived from code written by Ahmad M. Abdelfattah, David Keyes, and Hatem Ltaief, and are subject to the Apache License, Version 2.0, as follows:
-- (C) Copyright 2013 King Abdullah University of Science and Technology
Authors:
Ahmad Abdelfattah (ahmad.ahmad@kaust.edu.sa)
David Keyes (david.keyes@kaust.edu.sa)
Hatem Ltaief (hatem.ltaief@kaust.edu.sa)
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:
* Redistributions of source code must retain the above copyright
notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright
notice, this list of conditions and the following disclaimer in the
documentation and/or other materials provided with the distribution.
* Neither the name of the King Abdullah University of Science and
Technology nor the names of its contributors may be used to endorse
or promote products derived from this software without specific prior
written permission.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
HOLDERS OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE

Some of the cuBLAS library routines uses code from OpenAI, which is subject to the following license:
License URL
https://github.com/openai/openai-gemm/blob/master/LICENSE
License Text
The MIT License
Copyright (c) 2016 OpenAI (http://openai.com), 2016 Google Inc.
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
```

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

Los textos completos que pide un paquete binario de BAXY están en [`licenses/`](licenses/README.md). La versión de CC-BY-SA
sigue por confirmar. OpenMDW-1.1 no hace falta mientras Nemotron no vaya en el paquete.
