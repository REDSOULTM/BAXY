# Dependencias nativas de voz

## Cancelación de eco

`pywebrtc_audio-0.2.0+baxy.1-cp312-cp312-win_amd64.whl` expone la última trama
lineal de AEC3 además de su salida suprimida. El parche cambia el binding; no
ajusta el algoritmo ni añade otro cancelador. BAXY oye la salida lineal:
`src/baxy_mind/voice_echo.py` quita del micrófono lo que suena en el PC (la
referencia llega por loopback WASAPI con PyAudioWPatch, también fijado en el
lock) antes de la palabra de activación, el VAD y el reconocedor. Por qué la
lineal y no la suprimida está en el comentario de `EchoCanceller` (`src/baxy_mind/voice_echo.py`).

La receta `scripts/build_webrtc_runtime.py` verifica el tarball oficial 0.2.0,
el wheel original, pybind11 3.0.1, el parche `webrtc-linear-output.patch` y cada
archivo de la fuente. El wheel conserva las licencias originales, incluidas
las de WebRTC y las bibliotecas vendorizadas, y añade el aviso de modificación,
las patentes WebRTC y `pywebrtc_audio/baxy_native_build.json` con procedencia.

Reconstrucción en Windows x64, Python 3.12 y Visual Studio Build Tools 2022:

```powershell
py -3.12 scripts/build_webrtc_runtime.py --work-dir D:/BAXYBuild/webrtc --cmake "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"
```

Se enlaza el runtime de MSVC estáticamente; la extensión distribuida sólo importa
Python 3.12, WINMM y KERNEL32. No necesita un DLL de MSVC descargado aparte.
La receta descarga únicamente los tres insumos fijados que falten en el directorio
de trabajo y nunca sustituye fuentes modificadas ni un wheel diferente ya existente.
El binario final tiene SHA-256
`a23633725342f1ca3425c81a0927e3d6ef7d050452415e24b6a4cabe540416eb`.
La reconstrucción no promete identidad binaria entre compiladores o rutas diferentes;
el consumidor instala el binario fijado mediante `pylock.runtime-win-x64.toml` y
`scripts/setup_mind_voice.ps1`, sin compilador. El lock conserva59 dependencias
anteriores, añade pywebrtc-audio y retira ai-edge-litert, backports.strenum y
ml_dtypes. El cancelador ya no requiere un modelo externo ni instalador de activos.

Los tramos 255–256 comprobaron igualdad exacta de ambas señales en 13.433 bloques
de doce grabaciones de desarrollo, incluidas las señales de la prueba física 254.
El tramo257 conserva esa igualdad con el propietario real instalado. Esto
acredita equivalencia de señales, no aceptación de voz ni cierre de C03.

## Reconocimiento

`sherpa_onnx-1.13.4+baxy.2-cp312-cp312-win_amd64.whl` contiene la extensión
Python corregida para NeMo. **Esa rueda no está en el repositorio:** sherpa-onnx
compila dentro eSpeak NG, que es GPL-3.0-or-later, y aquí sólo se versionan
binarios de terceros con licencia permisiva. Va dentro del paquete de cada release,
y su código fuente completo está en los activos `*-source.zip` de la
[release 1.2.1](https://github.com/REDSOULTM/BAXY/releases/tag/v1.2.1)
(`licenses/FUENTES_GPL.md`). Para usar la voz desde el código fuente hay que
compilarla con la receta de abajo; como la compilación no es idéntica byte a byte,
después se regenera el lock con `scripts/lock_python_dependencies.ps1` para que
fije el SHA-256 de la rueda propia. Conserva el wrapper y las licencias de sherpa-onnx
1.13.4 y depende del `sherpa-onnx-core==1.13.4` oficial. Es una modificación
identificada de BAXY, no una versión publicada por el proyecto upstream.

El parche permite solicitar `decoding_method=greedy_search` por stream usando
el mismo modelo que el beam contextual. El beam predeterminado conserva su
implementación. `applied_decoding_method` acredita el método efectivo; solicitar
greedy con hotwords o un método desconocido falla explícitamente.

BAXY usa greedy para la transcripción principal y beam para las verificaciones
léxicas de activación y la corrección contextual conservadora. La versión upstream
aceptaba la opción pero la ignoraba: el helper del producto rechaza ese caso.

La normalización incorpora la corrección oficial
[PR3857](https://github.com/k2-fsa/sherpa-onnx/pull/3857), de Eoin Houstoun,
fusionada como `0967a08db705d8eec9cf5cef962c8ec57c16e4a8`. Calcula la varianza
desde valores centrados para evitar pérdidas de precisión con bandas casi
constantes. Conserva el epsilon y los modelos; afecta a ambos decodificadores.

La fuente es el commit `142807252687d81b40d6315f23470a1512a00de3` de sherpa-onnx
(tag `v1.13.4`) más `sherpa-nemo-stream-decoder.patch` y
`sherpa-nemo-normalization.patch`. El script comprueba revisión, ambos parches
exactos y hash del wheel original; recompila con VS2022 Release, Python3.12
y ONNX Runtime1.27.0 CPU, y ejecuta la suite nativa `math-test` antes de empaquetar.
El wheel incluye procedencia y hash de la extensión en
`sherpa_onnx/baxy_native_build.json`, aviso de modificación y un RECORD completo.

Reconstrucción desde Windows con Visual Studio Build Tools y Python3.12:

```powershell
py -3.12 scripts/build_sherpa_runtime.py --work-dir D:/BAXYBuild/sherpa --cmake "C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe"
```

El script conserva un wheel existente si es idéntico; si cambia, falla para que
se revise y versione el nuevo binario. La receta permite reconstruirlo, pero no
promete igualdad binaria entre versiones de compilador o rutas de compilación.
Los consumidores instalan el binario fijado, sin necesitar el compilador.

`pylock.runtime-win-x64.toml` fija su SHA-256 y ruta relativa. El generador convierte
únicamente los archivos del directorio `runtime_wheels` a rutas portables;
el verificador rechaza rutas externas y sigue exigiendo hashes completos.
`scripts/setup_mind_voice.ps1` instala el lock con `--require-hashes`.

La versión baxy.1 (sólo el parche del decodificador) se publicó en este
repositorio hasta el commit `45f98278`; el lock decide la versión instalada.
Hay regresiones de contenido y eco aún abiertas; este paquete no certifica la
fidelidad de toda la voz ni de la activación.
