# Arranque sin bloqueo de entrada — candidato 740

La entrada del sidecar usa un pipe no bloqueante en Windows. Cuando todavía no
hay bytes, el lector espera 10 ms; conserva EOF, errores reales, UTF-8 fragmentado
y el límite de tamaño. Esto permite retirar la precarga obligatoria de SciPy sin
cambiar el remuestreo de audio ni añadir otra capa de ejecución.

La comparación privada 739 mantuvo prewarm diferido en ambos brazos. Con lectura
síncrona, DSP agotó 10 s; con lectura no bloqueante terminó en 2,500 s y la caída
del dispatcher terminó en 0,781 s, dentro de sus 3 s. Es una sonda de mecanismo;
la aprobación de fuente usa después las pruebas originales sin modificaciones.

| Comprobación | Resultado |
|---|---|
| Protocolo, casos nuevos y ciclo de vida original | 52 pass; 5,47 s |
| Ampliación con procesos, captura y AEC | 89 pass, 0 fallos, 0 skips; 4,71 s |
| Declaraciones del programa STT | 17 pass, 1 skip ambiental; 1,46 s |
| Fast completo | Verde; Release 20,76 s, 0 advertencias y 0 errores |

El skip corresponde a datos ausentes de la campaña ciega y no acredita voz.
Las dos pruebas originales que fallaron en Full5 conservan sus hashes y plazos.
La de empaquetado también pasó aislada en 741, sin modificar su implementación.

Python 3.12 documenta [entrada no bloqueante para pipes Windows](https://docs.python.org/3.12/library/os.html#os.set_blocking).
El cambio evita la espera síncrona que coincidía con la carga nativa de DSP; las
pruebas no identifican por sí solas el bloqueo interno exacto de la DLL. No se
ha medido aquí el consumo conjunto de BAXY ni la calidad física de voz.

Full6 valida ahora el conjunto compartido 705, 712, 730, 738 y 740. Hasta que
termine y se revise, esta fuente continúa como candidata. C03 sigue completo y
activo: encuesta 26 cubiertos, 716 abiertos, sin cobertura añadida por estos tests.
