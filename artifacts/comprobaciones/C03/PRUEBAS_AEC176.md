# C03 — pérdida entre salida lineal y supresión residual —176

La salida final de la compilación diagnóstica coincide bit a bit (PCM16) con
la wheel174 en los tres controles. La observación no cambió esa salida.
Build9568 exit0; evaluación83450 exit0. Visual Studio17 2022, x64, Release;
wheel316.966bytes SHA718f8681940df85abb3535790721b3fc735a564a0e7fbb82f5ed747401816e69.
No se instala en el runtime ni se modifica código de producto.

## Qué se observó

La API existente EchoControl::ProcessCapture permite exportar la salida lineal.
Se activa sólo export_linear_aec_output y se lee esa señal junto a GetMetrics.
No se cambian delay, filtros, supresión, detector de BAXY ni señales de entrada.
El diff reproducible está en astra-linear176/diagnostic.patch; fuente upstream
descargada174 y compilación176 permanecen fuera del repositorio por ruta/hash.

| Control | Etapa | Bloques de habla | Mayor secuencia sin guard | Parakeet crudo | Normalizado |
|---|---|---:|---:|---|---|
| native_echo149 | final | 0 | 0 | no ejecutado | no ejecutado |
| native_echo149 | linear | 119 | 6 | no ejecutado | no ejecutado |
| near_only | final | 87 | 9 | Hola, aquí Paxi. ¿En qué te puedo ayudar hoy? | Hola, aquí Baxi. ¿En qué te puedo ayudar hoy? |
| near_only | linear | 87 | 9 | Hola, aquí Paxi. ¿En qué te puedo ayudar hoy? | Hola, aquí Paxi. ¿En qué te puedo ayudar hoy? |
| physical_echo_plus_synthetic_near | final | 67 | 8 | Exactly. | Exactly. |
| physical_echo_plus_synthetic_near | linear | 117 | 13 | ¿En qué te puedo ayudar? | ¿En qué te puedo ayudar? |

En mezcla, la salida lineal conserva «¿En qué te puedo ayudar?» y la residual
produce «Exactly.» ante Parakeet. La primera tampoco recupera saludo/nombre/hoy.
Esto localiza pérdida adicional entre etapas; no prueba que cada palabra ausente
se deba a la misma causa ni autoriza alimentar STT con una señal aún incompleta.
La salida lineal del eco149 conserva119bloques de habla frente a0residuales:
quitar la supresión dejaría nuevamente eco. No adoptar ese atajo.

Los ASR176 reciben floats nativos antes de exportar WAV;174/175 leen PCM16.
Variantes de nombre en el control cercano no se atribuyen a diferencias del
cancelador porque la salida PCM16 es idéntica. Todos los resultados se conservan.

## Métricas y límite causal

En la mezcla127/129 la demora estimada pasa de0ms a48ms entre25,5 y26s;
ERLE reportado permanece~0,176dB hasta27,5s y crece después. Eso describe
convergencia tardía; no prueba por sí solo la causa de la pérdida de palabras.
La alineación127/129 viene de streamReadyUtc y es aproximada.149 sí usa los
arrays nativos exactos pero no contiene voz cercana independiente.

Lectura de aec_state.cc93–100/283–312 descarta cambiar a ciegas
conservative_initial_phase: prolonga adaptación (no una reparación demostrada).
echo_remover.cc selecciona Y/E según UseLinearFilterOutput y calcula G con
nearend_spectrum/echo_spectrum/R2 antes de ApplyGain. Configuración de supresión
no se toca hasta contrastar esos estados y la relación temporal del control.

## Continuación concreta

Analizar la referencia y la voz cercana129 con sus tiempos reales de señal,
comparar comienzo de far-end con near_start y demora/ERLE176. No usar speaking
como comienzo acústico: OutputStream ya mostró latencia al abrir. Determinar
si el fallo es anterior a una estimación útil y contrastar protección de doble
habla con fuente upstream. Reutilizar build176 (no recomprar contexto ni paquetes).
No repetir UI/otra corrida de voces sólo para buscar un pase.174/175/176 son
experimentos de componente, no aceptación de doble habla ni del producto.

Fuente172/manifest intactos; ningún proceso propio pendiente. No Full.
C03 EN_CURSO y todos sus criterios finales siguen íntegros.
