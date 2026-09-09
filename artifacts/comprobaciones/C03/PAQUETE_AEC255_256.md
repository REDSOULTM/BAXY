# C03 — paquete nativo de AEC3, tramos 255–256

La candidata de dos señales de 253–254 ya tiene un wheel identificado y una
receta de reconstrucción. **Todavía no se ha conectado al producto ni al lock.**
La fuente de captura 242 sigue usando DTLN512. C03 permanece EN_CURSO.

## Cambio y procedencia

`scripts/build_webrtc_runtime.py` parte del tarball oficial pywebrtc-audio 0.2.0
ya descargado en 174. Comprueba sus bytes, el wheel original y pybind11 3.0.1.
`runtime_wheels/webrtc-linear-output.patch` conserva de 176 sólo la exportación
lineal necesaria, sin las métricas de diagnóstico. No cambia el DSP, los pesos,
las ganancias ni los umbrales. Se mantiene un único AEC3.

El wheel `pywebrtc_audio-0.2.0+baxy.1-cp312-cp312-win_amd64.whl` pesa 430.727 bytes:

- SHA-256 del wheel: `a23633725342f1ca3425c81a0927e3d6ef7d050452415e24b6a4cabe540416eb`.
- Extensión: `3679265e7761c1a77e51f598ebb33e819f11e9a6e53a4d0f95b0da6f83382ef2`.
- Parche: `548763188c319936ae00475b03885e75bf986d1917b8bba8b86ed1746f0fe020`.

Compilación Windows x64, Python 3.12.10, VS2022 y CMake 3.31.6-msvc6, Release.
Se enlaza MSVC estáticamente para no distribuir un DLL adicional. `dumpbin`
comprueba que la extensión sólo importa python312.dll, WINMM.dll y KERNEL32.dll.
Se conservan wrapper, tipado, licencias y avisos originales, incluidas las
dependencias vendorizadas; se añaden patentes WebRTC y procedencia del cambio.
La receta no promete igualdad binaria entre rutas o compiladores diferentes.

## Comparación que permite avanzar

El puente es exactamente la clase de `webrtc_aligned254.py`, cambiando solamente
el Native importado. Se utiliza una instalación aislada del wheel nuevo en
`D:/BAXYRuntime/experiments/voice/webrtc255/python`; no se modifica el entorno
registrado del producto.

255 demuestra igualdad float32 exacta de ambas salidas y de la guarda en los
12.117 bloques de los once controles de 253. 256 completa los 1.316 bloques de la
grabación física 254: ambas salidas idénticas y las 60 consultas efectivas de la
guarda también idénticas. Total: **13.433 bloques y doce grabaciones**.
El impulso vuelve a alinear las tres señales a 256 muestras de retardo.

El coste del DSP aislado quedó alrededor de 0,36–0,38 ms por bloque de 512 muestras;
no es una medición de la aplicación completa ni del presupuesto conjunto.
La igualdad de audio conserva los resultados y también las limitaciones de 253:
errores de reconocimiento abiertos, controles de desarrollo y ausencia de una
persona hablando simultáneamente en la prueba física. No se repitió ASR sobre
entradas idénticas ni se convirtió esta prueba en aceptación de C03 o C08.

## Fallos del instrumento conservados

El primer build no pasó el hash del parche aplicado: Git convirtió LF a CRLF.
La receta controla `core.autocrlf=false` y sólo normaliza un archivo existente
si su contenido normalizado coincide exactamente con el parche esperado.
El intento fallido está en `astra-integration255/build-attempt1.log`.

La primera comparación 255 llegó a los once controles completos y falló al
interpretar el centinela -1 de la guarda física como booleano True. El observador
254 usa -1 para «no se consultó la guarda». 256 corrige esa interpretación y
compara únicamente sus resultados observados 0/1. No se modifica la grabación,
el DSP ni el criterio de igualdad; 255 y sus resultados parciales se conservan.

## Validación y siguiente integración

- `python -m pytest tests/test_webrtc_runtime_package.py -q`: **6 pass, 0 skips**,
  0,30 s, con el Python registrado. Comprueba identidad, procedencia, licencias,
  RECORD completo y rechazo de fuentes modificadas/rutas de archivo inseguras.
- Suite nativa upstream `tests/test_echo_canceller.py`, importando el wheel nuevo
  aislado: **14 pass, 0 skips**, 0,24 s. Incluye procesamiento, reducción de eco,
  validación de parámetros y reset.
- `scripts/test_source_quality.ps1`: **Fast verde**; build Release 3,25 s,
  0 advertencias y 0 errores. No se ejecutó Full durante esta reparación.
- El build nativo vendorizado emitió 310 C4005, 14 C4244 y un C4715. Este último
  corresponde a `agc2/rnn_vad/rnn_fc.cc::GetActivationFunction`, en el componente
  AGC que BAXY no usa en su EchoCanceller. No se ocultan como build sin warnings
  ni se añaden supresiones; el DSP AEC quedó idéntico en las comparaciones.

`INTEGRATION_INVENTORY.json` confirma que no hay override local de activos.
Las dependencias activas que desaparecerán con DTLN son ai-edge-litert,
backports.strenum y ml_dtypes. ONNX Runtime menciona ml_dtypes sólo en su extra
de cuantización, que no está solicitado. El lock seguirá conservando los otros
59 paquetes y añadirá pywebrtc-audio: previsión de 60, pendiente de resolver.

Siguiente tramo 257: reemplazar el propietario DTLN por el puente AEC3 de dos
señales y conectar dos estados VAD independientes en `voice.py`, conservando
prefijo, admisión, wake, colas y fallos. Actualizar dependencias, retirar el
instalador/descriptor DTLN obsoletos y validar la integración real por paridad y
pruebas dueñas. Se conserva el snapshot previo de los archivos en
`astra-integration255/before` y no se borran modelos ni evidencia histórica.

El cierre íntegro sigue exigiendo ocho rutas, cien turnos humanos frescos
congelados y 100/100 útiles/fieles, averías y recuperación, UI/voz/LLM con techo
conjunto de 4 GB, runtime e instalación reproducibles, continuidad C04–C09,
Full completo y publicación validada fuera de main.
