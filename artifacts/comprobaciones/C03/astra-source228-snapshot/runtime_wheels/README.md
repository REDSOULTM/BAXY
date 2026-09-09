# Dependencia nativa de reconocimiento

`sherpa_onnx-1.13.4+baxy.2-cp312-cp312-win_amd64.whl` contiene la extensión
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

La versión baxy.1 se conserva como rollback y evidencia de205–208; el lock decide
la versión instalada. Los paquetes de observación215/216 no se distribuyen aquí.

Evidencia: `artifacts/comprobaciones/C03/PRUEBAS_NORMALIZACION215_217.md` demuestra
la causa numérica, la recuperación de tres vacíos y los límites de calidad en126
lecturas. Hay regresiones de contenido y eco aún abiertas; este paquete no
certifica fidelidad de toda la voz, activación ni cierre de C03. La integración
del paquete se registra en `astra-runtime218` y sus pruebas posteriores.
