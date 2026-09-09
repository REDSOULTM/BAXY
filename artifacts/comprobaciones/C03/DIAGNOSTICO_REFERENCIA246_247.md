# C03 — referencia y recorrido acústico246–247

Fuente242 sin cambios. El turno anterior fue progreso: integración y validación
242, seguido del fallo físico243 reproducido íntegramente en244245. Este tramo
analiza únicamente señales congeladas; no abre micrófono, reproduce audio,
regenera Piper ni cambia el runtime o los criterios de admisión.

##246 — integridad de la referencia

Todas las ventanas de referencia solapadas coinciden exactamente en240 y243.
Las ocho frases generadas se localizan en su loopback. La correlación de una
plantilla de0.5s con loopback varía0.525–0.804 en240 y0.534–0.800 en243.
No se requiere igualdad con una conversión SciPy: Windows y los dispositivos
forman parte del recorrido. El retardo de la plantilla micrófono respecto a
loopback es237–347muestras(14.8–21.7ms) en240 y295–317(18.4–19.8ms) en243.
No aparece una ausencia de referencia o un desfase de más de250ms.

El primer saludo243 queda truncado tras el corte, y los tramos posteriores
comparados con el PCM completo dan cero: es la consecuencia esperada de la
cancelación, no evidencia de pérdida de referencia antes del disparo. El
matching absoluto puede elegir medio periodo con signo opuesto; no tratar cada
variación de pocos samples como deriva del reloj. La observación monotónica
no conserva los timestamps ADC nativos:246 no demuestra su origen exacto.

Consulta local actual de dispositivos: salida predeterminada sounddevice MME,
Realtek, default44100; loopback WASAPI48000,2canales. Son metadatos actuales,
no una prueba retroactiva de la configuración de240/243. No cambio de equipo.

##247 — explicación lineal con muestras reservadas

Filtro FIR offline de512coeficientes, fijo para cada clip, ajustado en bloques
alternos de4000muestras y evaluado en los otros bloques. Regularización fija,
sin barrido. El ajuste se centra en el lag246 y es no causal: diagnóstico,
no implementación ni prueba de conservación de voz humana.
Sólo las tres frases completas de cada grabación; el saludo cortado no se usa.

| Grabación/frase | R² Piper→loopback reservado | R² loopback→micrófono reservado |
|---|---:|---:|
|240/1|0.950|0.256|
|240/2|0.941|0.543|
|240/3|0.941|0.457|
|243/1|0.966|0.577|
|243/2|0.919|0.726|
|243/3|0.951|0.817|

Gran parte de la diferencia digital se explica por filtrado lineal. La segunda
ruta conserva variación residual considerable; este análisis no distingue por
sí solo ruido, reverberación larga o no linealidad. Tampoco explica directamente
el saludo que falló. No se presenta el filtro offline como solución de AEC.

El artículo de los autores de DTLN describe entrenamiento con retardos de10–100ms,
reverberación y filtrado de banda. Los~20ms observados no justifican por sí solos
una compensación o ampliar el historial. Fuente primaria consultada:
https://arxiv.org/html/2010.14337 (secciones2.3–2.4, consulta2026-09-07).

## Decisión y siguiente contraste248

No cambiar reloj, umbrales ni ganancias a partir de246247. Mantener el fallo243
abierto: DTLN512 no es aceptación acústica, aunque su integración es reproducible.
El rechazo anterior de AEC3 usó otras condiciones: señales149/127 anteriores a
RAW220, y evaluate178 crea el reconocedor con modified_beam_search antes de las
correcciones207/218. La evidencia177 muestra además un control cercano sintético
con comienzo35ms antes de la referencia; no son los humanos RAW213 actuales.
No se reutiliza la configuración alterada de ganancia0.1 ni los rechazos como
si hubieran medido la cadena actual.

248: comparación acotada del wheel original pywebrtc-audio0.2.0 ya descargado174,
AEC sólo/16kmono/delay0, sin NS/AGC añadidos, contra controles actuales RAW:
echo221/232/243 y ocho humanos213 reconstruidos exactamente como238. Preparar
el puente de bloques160↔512 con retardo documentado y par de guardas correcto,
comprobando primero la temporización nativa en fuente/controles, sin optimizarla
contra el fallo. Congelar salidas antes de ASR. Mantener mismo baxy.2 y ventanas
humanas para la adjudicación; si pierde palabras, no adoptar por quitar eco.
No descarga, instalación ni cambio de proveedor productivo para este contraste.

Herencia consultada: biblioteca/00_INDICE.md voz y01_INVENTARIO.md porAEC/loopback;
astra-webrtc174/PREREG,RESULTS,DOWNLOADS; scratchpad/c03-prepare174.py,
c03-prepare178.py,c03-evaluate178.py,c03-timing177.py y astra-timing177/RESULTS.
El DSP sigue siendo un bloqueo dentro de C03 íntegro, no el objetivo completo.
