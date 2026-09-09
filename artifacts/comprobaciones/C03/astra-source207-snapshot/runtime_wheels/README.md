# Dependencia nativa de reconocimiento

`sherpa_onnx-1.13.4+baxy.1-cp312-cp312-win_amd64.whl` contiene la extensión
Python corregida para NeMo. Conserva el wrapper y las licencias de sherpa-onnx
1.13.4 y depende del `sherpa-onnx-core==1.13.4` oficial. Es una modificación
identificada de BAXY, no una versión publicada por el proyecto upstream.

El parche permite solicitar `decoding_method=greedy_search` por stream usando
el mismo modelo que el beam contextual. El beam predeterminado conserva su
implementación. `applied_decoding_method` acredita el método efectivo; solicitar
greedy con hotwords o un método desconocido falla explícitamente.

BAXY usa greedy para la transcripción principal y beam para las verificaciones
léxicas de activación y la corrección contextual conservadora. La versión upstream
aceptaba la opción pero la ignoraba: el helper del producto rechaza ese caso.

La fuente es el commit `142807252687d81b40d6315f23470a1512a00de3` de sherpa-onnx
(tag `v1.13.4`) más `sherpa-nemo-stream-decoder.patch`. El script comprueba revisión,
parche exacto y hash del wheel original; recompila con VS2022 Release, Python3.12
y ONNX Runtime1.27.0 CPU. El wheel incluye procedencia y hash de la extensión en
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

Evidencia: `artifacts/comprobaciones/C03/PRUEBAS_NATIVO205_206.md` (94 paridades
greedy/beam); `astra-product208` (47 lecturas y cuatro transcripciones directas
recuperadas mediante VoiceEngine). Esto no certifica activación ni audio físico.
