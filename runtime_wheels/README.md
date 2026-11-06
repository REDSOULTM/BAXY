# Dependencias nativas de voz

## Cancelación de eco

Esta rueda y PyAudioWPatch no están en el lock desde `22b470dd0`: el paquete funciona con el eco apagado.
`pywebrtc_audio-0.2.0+baxy.1-cp312-cp312-win_amd64.whl` expone la última trama
lineal de AEC3 además de su salida suprimida. El parche cambia el binding; no
ajusta el algoritmo ni añade otro cancelador. BAXY oye la salida lineal:
`src/baxy_mind/voice_echo.py` quita del micrófono lo que suena en el PC (la
referencia llega por loopback WASAPI con PyAudioWPatch) antes de la palabra de activación, el VAD y el reconocedor. Por qué la
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
`scripts/setup_mind_voice.ps1`, sin compilador. Fuera del lock desde `22b470dd0`: quien lo use lo instala a mano. El cancelador ya no requiere un modelo externo ni instalador de activos.

Los tramos 255–256 comprobaron igualdad exacta de ambas señales en 13.433 bloques
de doce grabaciones de desarrollo, incluidas las señales de la prueba física 254.
El tramo257 conserva esa igualdad con el propietario real instalado. Esto
acredita equivalencia de señales, no aceptación de voz ni cierre de C03.

## Reconocimiento

`sherpa_onnx-1.13.4+baxy.3-cp312-cp312-win_amd64.whl` contiene la extensión
Python corregida para NeMo, compilada sin eSpeak NG (GPL-3.0-or-later) ni
piper-phonemize. Conserva el wrapper y las licencias de sherpa-onnx 1.13.4 y lleva
el `onnxruntime.dll` de `sherpa-onnx-core==1.13.4`, el único DLL que importa la
extensión. Es una modificación identificada de BAXY, no una versión publicada por
el proyecto upstream. Sólo carga Supertonic y Pocket: VITS, Matcha, Kokoro, Kitten
y ZipVoice necesitaban eSpeak NG y aquí no están.

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
(tag `v1.13.4`) más `sherpa-nemo-stream-decoder.patch`,
`sherpa-nemo-normalization.patch` y `sherpa-no-espeak.patch`. El script comprueba revisión, los parches
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

Las versiones baxy.1 y baxy.2, con eSpeak NG dentro, salieron del árbol en 1.3.0; siguen en la historia
de git. El lock decide la versión instalada.

Hay regresiones de contenido y eco aún abiertas; este paquete no certifica la
fidelidad de toda la voz ni de la activación.

## numpy y silero-vad

`scripts/build_runtime_wheels.py` hace las dos, identificadas con su versión local:

- `numpy-1.26.4+baxy.1-cp312-cp312-win_amd64.whl`: la misma fuente de numpy 1.26.4, compilada sin BLAS
  (`allow-noblas`, [numpy#24703](https://github.com/numpy/numpy/issues/24703)). Lleva los avisos de la fuente salvo
  `tools/wheels/LICENSE_*`, que describen las oficiales; svml y x86-simd-sort no se compilan aquí; pocketfft y msun, en `licenses/`. La rueda oficial para Windows lleva OpenBLAS, el
  runtime de gfortran y libquadmath (LGPL-2.1-or-later). Medido el 2026-11-06 con la voz real: mismos WAV, mismos textos, mismas
  decisiones de actividad de voz, activación e idioma. Las características de `voice_turn.features` para 8 s pasan de 4,4 a 12,4 ms.
- `silero_vad-6.2.1+baxy.1-py3-none-any.whl`: la rueda oficial, sin sus requisitos de torch y torchaudio. `voice.Vad` sólo lee su
  `silero_vad.onnx`, sin importar el paquete.

`scripts/check_package_licenses.py` hace fallar el armado si vuelve algo de lo que se quitó.
