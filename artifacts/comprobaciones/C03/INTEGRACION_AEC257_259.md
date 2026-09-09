# C03 — integración de AEC3 y comprobación física, 257–259

El producto instalado ya usa el paquete AEC3 de dos señales. Conserva exactamente
la conducta de la candidata 253 en los controles y supera una prueba física de
eco. **Es progreso de integración; C03 sigue EN_CURSO.**

## Qué cambió

`src/baxy_mind/webrtc_aec.py` sustituye DTLN. Comprueba versión, hash y ruta de la
extensión instalada antes de crear un único AEC por hilo de captura. Su puente
de160 a512 muestras entrega reconocimiento, confirmación y pareja cruda alineados
a256 muestras; rechaza audio no finito, salida inválida y uso desde otro hilo.

`voice.py` reconoce con la señal lineal y confirma intervenciones con la señal
suprimida. Usa dos estados VAD independientes. La candidata conserva el inicio
de la frase antes de admitirse; terminar TTS por sí solo no autoriza un eco
pendiente. Conserva umbral VAD0,5, tres bloques para interrupción, energía y pausa
vigentes, así como la autorización de wake, colas, errores y cierre de sesión.
Sin captura acústica con AEC se mantiene un único VAD sobre la entrada existente.

El lock tiene60 paquetes: conserva idénticos los59 ajenos a DTLN, elimina
ai-edge-litert2.2.0, backports.strenum1.2.8 y ml_dtypes0.5.4, e incorpora
pywebrtc-audio0.2.0+baxy.1. Se instaló con `scripts/setup_mind_voice.ps1` y hashes.
Después de comprobar los padres activos de todos los paquetes instalados, se
retiraron las tres dependencias obsoletas del venv registrado; `pip check` pasó.

Se retiraron módulo, instalador, licencia local y pruebas exclusivas de DTLN,
con copias previas en `astra-integration257/before`. También desaparece su entrada
de activos: el AEC ahora viene en el wheel. No existía override local que migrar.
Los modelos DTLN y su evidencia histórica externa se conservan. El mapa de
contexto, la documentación del paquete y el gate de voz apuntan al dueño actual.
El manifiesto del LLM no se promovió ni cambió.

## Pruebas y comparación

| Comprobación | Resultado y límite |
|---|---|
| AEC instalado contra señales de253/254 | Ambas señales float32 exactas en13.433 bloques de12 grabaciones; guardas exactas donde fueron observadas; impulso a256 muestras. |
| Captura real del código257, entradas crudas reproducidas | Once recorridos; nueve segmentos decodificados con ASR real. Límites, PCM, textos y cancelaciones idénticos a253. Sin copia del método de captura ni sustitución del AEC/guarda. |
| Ocho ventanas fijas humanas | Se verificó PCM idéntico y se reutilizaron sus resultados253; no se contabilizan como nuevas ejecuciones de ASR. |
| Pruebas AEC/paquete/voz/lock | 138 pass,0 skips,6,18s. |
| Pruebas captura/activos/instalación/contrato gate | 33 pass,0 skips,6,18s. Total de esta tanda:171 pass,0 skips. |
| `scripts/test_source_quality.ps1` | Fast verde, build Release3,30s,0 advertencias y0 errores. |
| Smoke de supresión de eco |19,89dB en la señal de confirmación, umbral existente6dB. Distribuciones esperadas todas presentes. No certifica comprensión ni hardware. |

Los nuevos tests cubren la alineación de ambos audios, el prefijo, admisión con
confirmación tardía, rechazo de eco al terminar TTS y de confirmaciones fugaces,
actividad detectada sólo por la segunda vista y liberación del AEC si falla la
carga del segundo VAD. El primer intento tuvo tres errores en la expectativa de
cola del test nuevo: contaba22 bloques, cuando el código existente cuantiza0,7s
a21 bloques completos. Se corrigió esa expectativa; no se cambió la pausa del
producto. La salida original está conservada en `tests-attempt1.log`.

Los literales258 mantienen también los errores253: `pudier acceder` en h1-near
y `world`/`given` por `word`/`even` en h3-raw, entre otras diferencias. Las dos
cláusulas de h2-raw siguen recuperadas en dos segmentos. No se presentan como
ocho transcripciones perfectas ni como la reserva humana de aceptación.

##259 — salida y captura físicas del runtime instalado

Arranque del motor real en modo directo, micrófono WASAPI RAW, loopback, AEC3,
dos VAD, Piper y ASR baxy.2. Los wrappers sólo observan; no sustituyen el AEC ni
el método de captura. Cuatro textos187 regenerados con sus ondas efectivas
conservadas: no se llaman PCM idénticos a las pruebas anteriores.

- 1.315 bloques,42,08s,432 bloques durante habla; cuatro salidas generadas.
- Cero interrupciones falsas, cero transcripciones, cero errores de voz/driver.
- Micrófono y referencia no nulos: RMS durante salida0,006886 y910,94PCM16.
- VAD máximo lineal0,718; confirmación0,390, por debajo de su umbral0,5.
- DSP medio0,673ms, p99 1,105ms y máximo1,584ms por bloque. No incluye VAD/UI/LLM.
- Volumen restaurado exactamente a0/muted=true; todos los workers cerrados.

El detector de wake continúa unavailable con `wake_verifier_manifest_missing`,
sin bypass. Esta prueba de eco no acredita una persona hablando simultáneamente,
la UI, el modelo conversacional ni recursos conjuntos, y no certifica C08.

## Continuación del objetivo completo

El siguiente paso260 es volver a la aplicación real: UI, modelo y voz juntos,
con medición del techo conjunto de4GB y regresiones de las ocho rutas. Reutilizar
el arranque y la observación de194, quitando sus eventos sintéticos cuando se
pretenda acreditar uso real. Revisar el perfil candidato y registro antes de
promover el modelo; Qwen3.5 sigue siendo un override, no el runtime registrado.

La relectura de C03_RESPUESTA_VERAZ, líneas88–92 y133–135, conserva la aceptación
acústica propia de C08 y no pide ejecutar su campaña entera en C03. Esto no
elimina la comprobación física adicional pedida aquí ni permite ignorar un
fallo de voz que bloquee respuestas útiles. Tampoco convierte cada diferencia
literal del corpus FLEURS en un nuevo requisito de transcripción perfecta.

Quedan cien turnos humanos nuevos por congelar y evaluar100/100 útiles/fieles,
averías y recuperación aparte, ocho rutas finales, UI/voz/LLM/recursos conjuntos,
runtime e instalación reproducibles, continuidadC04–C09 y Full/publicación
validados fuera de main. Ninguno de esos pendientes se sustituye por las pruebas
de esta tanda. No hay procesos propios activos ni un bloqueo externo.
