# Instalar BAXY en Windows

> Cada paso sale de los scripts y del código que se citan entre paréntesis. Lo marcado **(sin verificar)** no se ha
> probado todavía en una máquina limpia: si te funciona (o no), abre un issue y se corrige esta guía.

BAXY, el asistente local para Windows, tiene cuatro partes:

| Pieza | Qué es | De dónde sale |
|---|---|---|
| App | `Baxy.exe` (WPF, .NET 10) con la interfaz React servida por WebView2, y `baxy-core.exe` (NativeAOT) | Se compila desde `src/` |
| Mente | El paquete Python `src/baxy_mind`, que la App lanza con `python -X utf8 -m baxy_mind` | El propio repositorio, con un Python 3.12 propio |
| Servidor del modelo | `llama-server.exe` de llama.cpp **b11609** | Distribución oficial de llama.cpp (ver §3.3) |
| Modelo | `BAXY-Qwen3.5-4B-c3-Q4_K_M.gguf` (Qwen3.5-4B con el ajuste de BAXY) | Hugging Face (ver §3.2) |

Además hay piezas opcionales: la voz que habla (Supertonic 3), el reconocedor de voz (Parakeet), la palabra de
activación, el proyector de visión (`mmproj`) y el modelo de decisión de «System One». Sin ellas, BAXY funciona por
texto.

---

## 1. Requisitos

### Hardware

| Recurso | Requisito | Fuente |
|---|---|---|
| CPU / sistema | Windows x64 | `BaxyRuntimeIdentifier = win-x64` en `Directory.Build.props` |
| GPU | NVIDIA con **4 GB de VRAM** (el perfil medido usa ~3,9 GB con el modelo entero en la GPU) | `docs/construccion/catalogo-y-kernel/00_ALCANCE_DESARROLLO_VS_PRODUCTO.md`; comentario de `src/baxy_mind/llm_server.py` |
| Driver NVIDIA | Uno que soporte CUDA 12.4: **551.61 o posterior** | El llama-server aceptado es el build CUDA 12 (`llama_server.v1.json`); el mínimo es de las notas de NVIDIA para CUDA 12.4 GA |
| Sin GPU NVIDIA | Modo CPU (`--cpu`, todas las capas en la CPU). Será bastante más lento **(sin verificar en una máquina sin NVIDIA, ver §6)** | `main.py --cpu` → `BAXY_MIND_NGL=0` |
| RAM | El perfil CPU documentado es ≤ 8 GB. La visión suma ~0,7 GB, el reconocedor ~1 GB y la voz ~0,25–0,3 GB. **16 GB recomendados (sin verificar)** | `00_ALCANCE_DESARROLLO_VS_PRODUCTO.md`, `run_renew.cmd` |
| Disco | Modelo 2,74 GB; proyector de visión 0,67 GB; llama.cpp con el runtime CUDA ~1,2 GB; el reconocedor Parakeet unos 0,6 GB o más; el entorno Python (torch, onnxruntime, etc.) varios GB más. **Cuenta con unos 10 GB libres (sin verificar)** | Hugging Face, `llama_server.v1.json`, `pylock.runtime-win-x64.toml` |
| Micrófono y altavoces | Opcionales. Sólo hacen falta para hablarle y oírlo | `src/baxy_mind/voice.py`, `voice_output.py` |

### Software

| Programa | Versión exacta | Para qué | Fuente |
|---|---|---|---|
| Windows | 10 versión 2004 (build 19041) o posterior; Windows 11 recomendado. **En Windows 10 no se ha probado (sin verificar)** | Todo | `net10.0-windows10.0.19041.0` en `Directory.Build.props` |
| Microsoft Edge WebView2 Runtime (Evergreen) | La que tenga Windows. Windows 11 ya lo trae | La interfaz. La App usa el runtime instalado (`browserExecutableFolder: null`) | `src/Baxy.App/MainWindow.xaml.cs` |
| .NET SDK | **10.0.100 exactamente**. `global.json` tiene `rollForward: disable`, así que ni siquiera vale otro 10.0.1xx | Compilar la App y el core | `global.json`, `scripts/bootstrap.ps1` |
| Visual Studio 2022 o Build Tools 2022 con la carga «Desarrollo para el escritorio con C++» (MSVC) | — | El core (`baxy-core.exe`) y el instalador se publican con NativeAOT, que en Windows necesita el enlazador de MSVC. Los scripts buscan `vswhere.exe` en `%ProgramFiles(x86)%\Microsoft Visual Studio\Installer` | `Baxy.Core.csproj` (`PublishAot`), `scripts/product_build_common.ps1` |
| Python | **CPython 3.12 x64**, con el lanzador `py` | La mente | `pylock.runtime-win-x64.toml` (`requires-python = "==3.12.*"`), `scripts/python_runtime_common.ps1` |
| pip (dentro del entorno de BAXY) | **26.1.2 exactamente**. `bootstrap.ps1` lo fija solo | Instalar el lock con hashes | `scripts/python_runtime_common.ps1` |
| Git | Cualquiera reciente | Clonar. También lo usan `build_product.ps1` y `build_setup.ps1` | — |
| Node.js / pnpm | **No hacen falta**. La interfaz ya compilada está versionada en `src/Baxy.FieldUi/dist` (50 ficheros en git). Sólo se necesitan para modificar la interfaz (`pnpm install --frozen-lockfile`, `pnpm build`) | — | `src/Baxy.FieldUi/README.md`, `main.py` |

Enlaces oficiales:

- .NET 10 SDK: https://dotnet.microsoft.com/download/dotnet/10.0 (hay que elegir la versión **10.0.100**)
- Python 3.12 para Windows: https://www.python.org/downloads/windows/
- WebView2 Runtime: https://developer.microsoft.com/microsoft-edge/webview2/
- Visual Studio Build Tools 2022: https://visualstudio.microsoft.com/downloads/

---

## 2. ¿Instalador o código fuente?

El repositorio tiene un instalador, `Baxy.Setup.exe` (`src/Baxy.Setup`). Instala la App en
`%LOCALAPPDATA%\Programs\BAXY`, crea el acceso `BAXY` en el menú Inicio y registra la desinstalación en
«Aplicaciones instaladas» (HKCU). Pero hay dos limitaciones:

1. **No se publica ya compilado.** No se encontró ninguna release con `Baxy.Setup.exe`. Hay que construirlo a partir de
   un clon limpio (§4).
2. **Sólo instala la App, el core y la interfaz.** No lleva la mente Python, ni el modelo, ni llama-server
   (`$BaxyProductPayloadPaths` en `scripts/product_build_common.ps1`). Igualmente hay que clonar el repositorio,
   preparar Python y registrar el runtime (§3.4–3.5). La App instalada lee ese registro de
   `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json` (`src/Baxy.App/MindRuntimeDiscovery.cs`).

Por eso **el camino más simple es desde el código fuente** (§3). El instalador (§4) sólo añade el acceso en el menú
Inicio y la desinstalación limpia.

---

## 3. Instalación desde el código fuente

Todos los comandos son de **PowerShell**, desde la carpeta del repositorio clonado.

### 3.1 Clonar en una carpeta que no se llame `BAXY`

> **Importante.** La App y el registro **rechazan cualquier ruta que tenga una carpeta llamada exactamente `BAXY`**
> (`IsForeignBaxyWorktree` en `MindRuntimeDiscovery.cs`; `Test-BaxyForeignWorktreePath` en
> `register_mind_runtime.ps1`). Si se clona con el nombre por defecto (`...\BAXY\src`), la mente no arranca y no
> aparece ningún error. Lo mismo pasa con los modelos: no los guardes bajo una carpeta `BAXY`. `BAXYRuntime` o
> `BAXY-src` sí valen.

```powershell
git clone https://github.com/REDSOULTM/BAXY.git BAXY-src
cd BAXY-src
```

### 3.2 Descargar el modelo de BAXY y comprobar su SHA-256

- Página: https://huggingface.co/REDSOULTM/BAXY-Qwen3.5-4B-GGUF
- Fichero: `BAXY-Qwen3.5-4B-c3-Q4_K_M.gguf`, de 2.740.937.440 bytes
- SHA-256: `485595f734f964b4902028b4a97ef37f31d57d5c651581435917e0043e499f0e`

La ruta del modelo es libre (se registra en §3.5). Ésta sigue la convención del repositorio:

```powershell
$assets = "$env:LOCALAPPDATA\BAXYRuntime\assets"
New-Item -ItemType Directory -Force "$assets\models" | Out-Null
# Descárgalo desde la página de Hugging Face (botón de descarga del fichero) a $assets\models
(Get-FileHash "$assets\models\BAXY-Qwen3.5-4B-c3-Q4_K_M.gguf" -Algorithm SHA256).Hash.ToLower()
# Debe imprimir 485595f734f964b4902028b4a97ef37f31d57d5c651581435917e0043e499f0e
```

Enlace directo (patrón estándar de Hugging Face):
`https://huggingface.co/REDSOULTM/BAXY-Qwen3.5-4B-GGUF/resolve/main/BAXY-Qwen3.5-4B-c3-Q4_K_M.gguf`.

### 3.3 llama-server b11609, oficial y con CUDA 12

La mente sólo arranca un llama-server **declarado** en `src/baxy_mind/data/llama_server.v1.json`: compara por SHA-256
siete ficheros de su carpeta (`llama-server.exe`, `llama-server-impl.dll`, `llama-common.dll`, `llama.dll`,
`mtmd.dll`, `ggml.dll`, `ggml-base.dll`). Hay dos builds declarados:

- `b11609`: la distribución oficial de llama.cpp **b11609** para Windows x64 con CUDA 12. Es la que hay que usar.
- `b11609-baxy-cache`: la misma con un parche opcional que hay que compilar (`scripts/llama/README.md`). No hace falta.

Release: https://github.com/ggml-org/llama.cpp/releases/tag/b11609. Descarga **los dos** zip y descomprímelos en la
**misma** carpeta:

- `llama-b11609-bin-win-cuda-12.4-x64.zip`
- `cudart-llama-bin-win-cuda-12.4-x64.zip` (el runtime CUDA: `cudart64_12.dll`, `cublas64_12.dll`,
  `cublasLt64_12.dll`)

```powershell
$llama = "$assets\llama-b11609"
New-Item -ItemType Directory -Force $llama | Out-Null
Expand-Archive .\llama-b11609-bin-win-cuda-12.4-x64.zip -DestinationPath $llama
Expand-Archive .\cudart-llama-bin-win-cuda-12.4-x64.zip -DestinationPath $llama
(Get-FileHash "$llama\llama-server.exe" -Algorithm SHA256).Hash.ToLower()
# Debe imprimir a3e80f6200d12130a52fed1eb61dfb04d307cd27440c9f5efea7d20d49ecb9f0
```

Los nombres de los zip son los de la página de la release. **Que los zip descompriman los ficheros en la raíz, y no
en una subcarpeta, está sin verificar**: `llama-server.exe` tiene que quedar directamente en `$llama`.

Los otros builds de la misma release (CUDA 13, Vulkan, CPU) **no** están declarados. Seguramente sus DLL no
coincidan y la mente se niegue a arrancarlos **(sin verificar)**.

### 3.4 Preparar Python con `bootstrap.ps1`

`scripts/bootstrap.ps1` hace lo siguiente:

1. Comprueba que existe el .NET SDK 10.0.100.
2. Crea un Python 3.12 aislado en `%LOCALAPPDATA%\BAXYRuntime\python\mind-runtime-v1` (con `py -3.12 -m venv`).
3. Fija pip 26.1.2.
4. Instala `pylock.runtime-win-x64.toml` con `--require-hashes --only-binary=:all:` (`setup_mind_voice.ps1`). Las
   ruedas propias de BAXY (`sherpa_onnx-1.13.4+baxy.2`, `pywebrtc_audio-0.2.0+baxy.1`) vienen en `runtime_wheels/` y
   no hace falta compilar nada.
5. Registra el runtime.

Una trampa: `bootstrap.ps1` busca los activos con el inventario viejo de `assets.manifest.json`. Ese inventario espera
otros modelos (`Qwen3-4B-Q4_K_M.gguf`, llama.cpp `b9980`) y **trata como obligatorio un reconocedor Parakeet**. Para
que encuentre los tuyos, pásaselos por variables de entorno en la misma consola:

```powershell
$env:BAXY_MIND_LLM_GGUF     = "$assets\models\BAXY-Qwen3.5-4B-c3-Q4_K_M.gguf"
$env:BAXY_MIND_LLAMA_SERVER = "$assets\llama-b11609\llama-server.exe"
$env:BAXY_MIND_STT_DIR      = "$assets\stt\sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"   # ver §3.6; obligatorio para bootstrap
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1
```

Si sale bien, termina con `BAXY arranca: runtime Python, manifiesto y activos obligatorios quedaron verificados.`

Sin GPU NVIDIA, añade `-Cpu` para registrar `ngl = 0`.

### 3.5 Registrar la voz, el oído y la visión (opcional)

`bootstrap.ps1` sólo registra el modelo y el servidor. Para añadir las piezas opcionales, vuelve a registrar con
`scripts/register_mind_runtime.ps1`. Cada parámetro es opcional y la pieza que no se da queda apagada:

```powershell
$py = "$env:LOCALAPPDATA\BAXYRuntime\python\mind-runtime-v1\Scripts\python.exe"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\register_mind_runtime.ps1 `
  -Python $py `
  -Gguf "$assets\models\BAXY-Qwen3.5-4B-c3-Q4_K_M.gguf" `
  -LlamaServer "$assets\llama-b11609\llama-server.exe" `
  -VoiceDirectory "$assets\voice\baxy-supertonic" `
  -SttDirectory "$assets\stt\sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8" `
  -VisionProjector "$assets\models\mmproj-F16.gguf"
# -GpuLayers 0 para CPU (por defecto 99). -WakeDirectory y -SystemOneGguf: ver §3.6.
```

El registro guarda el SHA-256 de cada fichero y de cada carpeta. La App los vuelve a comprobar en cada arranque: si
cambias un fichero, vuelve a registrar.

### 3.6 De dónde sale cada pieza opcional

| Pieza | Variable / parámetro | Qué debe tener la carpeta | De dónde sale |
|---|---|---|---|
| **Voz de BAXY** (Supertonic 3, CPU) | `BAXY_RENEW_TTS_DIR` / `-VoiceDirectory` | `duration_predictor.int8.onnx`, `text_encoder.int8.onnx`, `vector_estimator.int8.onnx`, `vocoder.int8.onnx`, `tts.json`, `unicode_indexer.bin`, `voice.bin`, `baxy-voice.json` | Se **construye** con `scripts/voice/make_baxy_voice.py` a partir de la release de sherpa-onnx `sherpa-onnx-supertonic-3-tts-int8-2026-05-11` (abajo) |
| **Reconocedor** (Parakeet, CPU) | `BAXY_RENEW_STT_DIR` / `-SttDirectory` (y `BAXY_MIND_STT_DIR` para `bootstrap.ps1`) | `encoder.int8.onnx`, `decoder.int8.onnx`, `joiner.int8.onnx`, `tokens.txt` | El producto se midió con «Parakeet Ultra», una variante propia que **no se publica**. La alternativa documentada es el bundle oficial `sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` (abajo). **Que la mente funcione igual con él está sin verificar** (carga los mismos cuatro ficheros, `voice.py`) |
| **Activación por voz** («BAXY», detector k4) | `BAXY_RENEW_WAKE_DIR` / `-WakeDirectory` | `config.json`, `baxy_wake_runtime.py` y los ONNX que nombra | **No se publica ni se puede descargar.** Sin ella, se le habla con el botón del micrófono (modo directo de `voice.py`) |
| **Proyector de visión** (clic por visión, en CPU) | `BAXY_MIND_MMPROJ` / `-VisionProjector` | El fichero `.gguf` | No está en el repositorio de BAXY. La ficha de Hugging Face dice que BAXY usa el `mmproj` de Qwen3.5-4B. La documentación (`docs/construccion/catalogo-y-kernel/computer-use/DECISION_VISION_V3.md`) cita `https://huggingface.co/unsloth/Qwen3.5-4B-GGUF`, que tiene `mmproj-F16.gguf` (672.423.616 bytes). **Que sea exactamente el que se usó está sin verificar** |
| **System One** (modelo de decisión «Laya») | `BAXY_S1_GGUF` / `-SystemOneGguf` | El fichero `.gguf` | **No se publica.** Sin él, System One no consulta a ese modelo |

**Voz de BAXY, paso a paso:**

```powershell
# 1) Descarga y descomprime la release de sherpa-onnx (tar de Windows; con .bz2 está sin verificar):
#    https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/sherpa-onnx-supertonic-3-tts-int8-2026-05-11.tar.bz2
tar -xf .\sherpa-onnx-supertonic-3-tts-int8-2026-05-11.tar.bz2 -C $assets
# 2) Construye la voz de BAXY (necesita numpy: usa el Python de BAXY):
& $py -X utf8 .\scripts\voice\make_baxy_voice.py "$assets\sherpa-onnx-supertonic-3-tts-int8-2026-05-11" "$assets\voice\baxy-supertonic"
```

El modelo Supertonic 3 tiene licencia OpenRAIL-M: al distribuirlo hay que incluir la licencia y avisar de que la voz
es sintética (`make_baxy_voice.py`).

**Reconocedor Parakeet oficial:**

```powershell
# https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2
New-Item -ItemType Directory -Force "$assets\stt" | Out-Null
tar -xf .\sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2 -C "$assets\stt"
```

Las dos URL de sherpa-onnx son las que da su documentación oficial. **Los ficheros no se descargaron para comprobarlos
(sin verificar).**

### 3.7 Arrancar

```powershell
py -3.12 main.py
```

`main.py` hace esto:

1. Cierra una ventana de BAXY anterior de este mismo clon.
2. Compila la App y publica el core sólo si cambió el código .NET. La primera vez tarda varios minutos.
3. Lanza `Baxy.exe` con un perfil de datos aislado (`%LOCALAPPDATA%\BAXY\dev-mente-v2`).

Opciones:

- `--cpu`: el modelo corre en la CPU.
- `--sin-mente`: sólo la parte determinista, sin modelo.
- `--recompilar`: fuerza una compilación aunque no haya cambios.

> **No uses `scripts\run_renew.cmd` tal cual.** Es el lanzador de las máquinas de desarrollo y fija sus rutas; esas variables
> mandan sobre el registro, así que en otro PC la mente no encontraría nada. Si
> quieres un lanzador propio, cópialo y cambia las rutas.

---

## 4. Instalador `Baxy.Setup.exe` (opcional)

Se construye desde un clon **limpio** (sin cambios ni ficheros sin seguimiento: los tres scripts se niegan si
`git status` no está vacío), con el SDK 10.0.100 y MSVC:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_product.ps1      # Release; versión 1.1.0 por defecto
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\package_product.ps1    # zip determinista + SHA256SUMS
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_setup.ps1        # Baxy.Setup.exe con el zip embebido
```

Las salidas quedan en `artifacts\product\build\` y en `artifacts\setup\build\local-win-x64\`.

- Instalar: ejecuta `Baxy.Setup.exe` sin argumentos. Copia la versión a `%LOCALAPPDATA%\Programs\BAXY\versions`,
  deja allí una copia estable de `Baxy.Setup.exe` y crea el acceso `BAXY` en el menú Inicio.
- Abrir lo instalado: `Baxy.Setup.exe --launch`. Volver a la versión anterior: `Baxy.Setup.exe --rollback`.
- La mente sigue necesitando §3.2–3.5: el registro de `%LOCALAPPDATA%\BAXYRuntime` apunta al `src` del clon, que
  **no se puede borrar**.

**El instalador no se ha probado de punta a punta en una máquina limpia (sin verificar).**

---

## 5. Primer arranque: cómo saber que funcionó

1. **Antes de abrir nada**, comprueba el registro:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap.ps1 -CheckOnly
   ```
   Hay que poner las mismas variables de §3.4, porque el inventario es el viejo. Debe decir
   `BAXY arranca: los activos obligatorios y el runtime registrado son validos.`
2. **Al abrir**, la ventana muestra el arranque con las piezas que informa la mente (`voice.status`: stt, wake, tts)
   y el modelo listo (`src/Baxy.FieldUi/README.md`).
   - La primera vez el modelo lee el catálogo de herramientas (~44 mil tokens) y guarda ese prefijo en disco. En GPU
     tarda unos 18 s (`scripts/llama/README.md`). Los siguientes arranques lo reutilizan.
3. **Prueba por texto**: escribe una petición sencilla (por ejemplo, «¿qué hora es?»). Debe responder con una frase
   escrita por el modelo. Si registraste la voz, también la dice en voz alta.
4. **Prueba por voz**: si registraste el reconocedor, pulsa el micrófono y habla. Si además tienes la palabra de
   activación, di «BAXY» y luego la petición.
5. **Registros**, en `%LOCALAPPDATA%\BAXY\renew\`:
   - `llama-server.log`: el servidor del modelo. Ahí se ve si cargó en la GPU y cuánta memoria usó.
   - `mind-stderr.log`: los errores de la mente, con prefijos `baxy_mind_renew_failure:` y `baxy_mind_renew_voice:`.
   - `turns.jsonl`: los turnos.

---

## 6. Idiomas

- **Lo que entiende y responde**: español, inglés y su mezcla (spanglish). El sistema le pide hablar «en el idioma de la persona»
  (`src/baxy_mind/mind.py`), y la ficha del modelo declara español e inglés.
- **Reconocedor de voz**: Parakeet TDT 0.6b v3 es multilingüe. Se midió en español, inglés y frases mezcladas
  (`docs/construccion/catalogo-y-kernel/03_COSTURAS.md`, fila STT).
- **Voz que habla**: la receta de `make_baxy_voice.py` fija `"lang": "es"` y no cambia de idioma dentro de una frase.
  Una respuesta en inglés se lee con la voz configurada en español; los nombres en inglés se reescriben con
  `data/speech_respellings.v1.json`. **Cómo suena una respuesta entera en inglés está sin verificar.**
- **Interfaz**: sólo en español. No se encontró traducción en `src/Baxy.FieldUi`.

---

## 7. Problemas comunes

| Síntoma | Causa | Qué hacer |
|---|---|---|
| La App abre pero BAXY no responde con el modelo y no hay error claro | El registro no es válido: falta un fichero, cambió un hash (Python actualizado, modelo movido o reemplazado) o alguna ruta pasa por una carpeta llamada `BAXY` | Ejecuta `bootstrap.ps1 -CheckOnly`: dice qué falla (`runtime_asset_hash_mismatch`, `runtime_piece_invalid`…). Vuelve a registrar (§3.5). Renombra cualquier carpeta `BAXY` de la ruta (§3.1) |
| `mind-stderr.log`: `llama-server not declared in llama_server.v1.json … (llama.dll 1a2b… , …)` | El llama-server no es la b11609 oficial con CUDA 12, la carpeta mezcla ficheros de dos builds, o faltan DLL | Usa exactamente los dos zip de §3.3 en una carpeta nueva y comprueba el hash de `llama-server.exe` |
| `baxy_mind_renew_failure: BAXY_MIND_LLM_GGUF and BAXY_MIND_LLAMA_SERVER are required` | La mente arrancó sin modelo ni servidor | Registra (§3.4–3.5) o define las dos variables antes de `main.py` |
| `llama-server exited with …` o el arranque falla con `proceso_salio`; en `llama-server.log`, errores de memoria de CUDA | Falta VRAM: otra aplicación ocupa la GPU, o la tarjeta tiene menos de ~4 GB libres | Cierra lo que use la GPU, o arranca en CPU (`py -3.12 main.py --cpu` o registra con `-GpuLayers 0`). Un valor intermedio de `-GpuLayers` reparte el modelo entre GPU y CPU **(rendimiento sin verificar)**. No bajes el contexto (`BAXY_RENEW_CTX`, por defecto 53248) por debajo de lo que ocupa el catálogo (~44–46 mil tokens) |
| `BAXY_MIND_LLAMA_PORT 8077 is in use on the loopback` | Con el proyector de visión registrado, el servidor usa el puerto fijo 8077 (`MindRuntimeDiscovery.cs`) y otro programa lo tiene | Libera el puerto, o define `BAXY_MIND_LLAMA_PORT` con otro puerto antes de arrancar, o apaga la visión con `BAXY_VISION_OFF=1` |
| La compilación falla al resolver el SDK | `global.json` exige 10.0.100 sin `rollForward` | Instala el SDK 10.0.100 (puede convivir con otros). `dotnet --version` en la carpeta del repositorio debe decir `10.0.100` |
| La compilación falla al publicar `baxy-core` (NativeAOT, enlazador) | Falta MSVC | Instala Build Tools 2022 con «Desarrollo para el escritorio con C++» |
| `mind_runtime_setup_failed: python_must_be_cpython_3_12_win_x64` | El Python no es CPython 3.12 de 64 bits | Instala Python 3.12 x64 de python.org y vuelve a ejecutar `bootstrap.ps1` |
| `mind_runtime_setup_failed: pip_must_be_26_1_2` | Se llamó a `setup_mind_voice.ps1` sin pasar por `bootstrap.ps1` | Usa `bootstrap.ps1`, que fija pip 26.1.2 |
| `bootstrap.ps1` dice `[FALTA] conversation_model` / `llama_server` / `stt_parakeet` | Busca con el inventario viejo de `assets.manifest.json` | Define `BAXY_MIND_LLM_GGUF`, `BAXY_MIND_LLAMA_SERVER` y `BAXY_MIND_STT_DIR` (§3.4), o decláralos en `%LOCALAPPDATA%\BAXYRuntime\assets.local.json` (esquema `baxy-assets-local-v1`) |
| No se pinta la interfaz; error al iniciar WebView2 | Falta el WebView2 Runtime, o otra instancia muerta tiene tomada su carpeta de datos (`%LOCALAPPDATA%\BAXY\webview2-field`) | Instala el runtime Evergreen. Cierra la instancia anterior (icono de la bandeja → «Salir») |
| El micrófono no funciona; `mind-stderr.log`: `baxy_mind_renew_voice: microphone: …` | BAXY usa el micrófono predeterminado de Windows. Puede que Windows no deje usarlo a las aplicaciones de escritorio | Revisa Configuración → Privacidad → Micrófono **(sin verificar que sea la causa)**. Para usar otro dispositivo, define `BAXY_RENEW_MIC` con el índice de entrada (`voice.py`) |
| `baxy_mind_renew_voice: BAXY_RENEW_WAKE_DIR has no wake word` | No hay palabra de activación (no se publica) | Es normal: habla con el botón del micrófono |
| `BAXY_RENEW_STT_DIR has no recognizer` | La carpeta del reconocedor no tiene `tokens.txt` | Revisa §3.6 |
| No se oye la voz | Falta algún fichero de la voz (`BAXY_RENEW_TTS_DIR has no …`), o la voz está silenciada en Ajustes | La voz sale por la salida predeterminada de Windows (mapeador MME, `voice_output.py`). Revisa la carpeta de §3.6 y Ajustes → Voz |
| BAXY sigue abierto tras cerrar su ventana | Se cierra a la bandeja | Icono de la bandeja → «Salir» |
| `build_product.ps1` / `build_setup.ps1`: `The Git worktree is dirty` | Hay cambios o ficheros sin seguimiento | Construye desde un clon limpio |

---

## 8. Desinstalación

**Si usaste el instalador** (§4):

- En «Aplicaciones instaladas» de Windows, o con
  `"%LOCALAPPDATA%\Programs\BAXY\Baxy.Setup.exe" --uninstall`. Esto conserva los datos.
- Sin ventanas, conservando los datos: `--uninstall --keep-data --quiet`.
- Para borrar también los datos de BAXY (`%LOCALAPPDATA%\BAXY`):
  `--uninstall --purge-data --confirm-purge-data --quiet` (`src/Baxy.Setup/SetupCommand.cs`).

**En los dos casos**, el desinstalador no toca lo que se instaló aparte. Eso se borra a mano, con BAXY cerrado
(bandeja → «Salir»):

- `%LOCALAPPDATA%\BAXYRuntime`: el Python de BAXY, el registro `mind-runtime-v1.json` y los modelos si los pusiste
  ahí.
- `%LOCALAPPDATA%\BAXY`, si no lo purgó el instalador: datos, perfil de desarrollo, registros y la carpeta de WebView2.
- La carpeta del clon.
- Si activaste el arranque con Windows, desactívalo antes desde la App. Se guarda como un valor en la clave `Run` del
  usuario (`WindowsAutostartRegistration.cs`). **Dónde está la opción en la interfaz está sin verificar.**

---

## 9. Variables de entorno de referencia

Todas son opcionales si el runtime está registrado. Si se definen, mandan sobre el registro.

| Variable | Para qué |
|---|---|
| `BAXY_MIND_PYTHON` | El `python.exe` de la mente |
| `BAXY_MIND_PYTHONPATH` | La carpeta `src` que contiene `baxy_mind` |
| `BAXY_MIND_LLM_GGUF` | El modelo |
| `BAXY_MIND_LLAMA_SERVER` | `llama-server.exe` (tiene que estar declarado) |
| `BAXY_MIND_NGL` | Capas del modelo en la GPU (99 = todas, 0 = CPU) |
| `BAXY_MIND_MMPROJ` | El proyector de visión |
| `BAXY_VISION_OFF=1` | Apaga la visión |
| `BAXY_MIND_LLAMA_PORT` | Puerto fijo del servidor (8077 con visión) |
| `BAXY_RENEW_TTS_DIR`, `BAXY_RENEW_STT_DIR`, `BAXY_RENEW_WAKE_DIR` | La voz, el reconocedor y el detector de activación |
| `BAXY_RENEW_MIC` | Índice del micrófono |
| `BAXY_RENEW_CTX` | Contexto del modelo (53248) |
| `BAXY_RENEW_KV` | Tipo de la caché KV (`q8_0`) |
| `BAXY_S1_GGUF`, `BAXY_S1_THREADS` | El modelo de System One y sus hilos |
| `BAXY_MIND_DISABLED=1` | Sin mente |
