# C03 — continuidad y reloj de la referencia AEC — 2026-09-07

Fuente136 candidata:130tests/0skips y Fast verdes, DSP137 bitidéntico al prototipo.
Eso no demuestra temporización integrada.138 falla físicamente,139 con observación
pasa; no se elige139 para borrar138. Sin promoción ni cierre.

## 138/139: resultado físico y datos de temporización

138 sin wrappers: driver10271/captura20182exit0, speaking1,578s,2barge_in,
ningún error del proveedor. AEC activo y hash bb683ab3… durante ready. Captura
42,39s, volumen0/muted=true restaurado exactamente. No contenido completo acreditado.

139 observa AEC/VAD, relojes/latencia/backlog del InputStream y bloques de cada
callback de loopback. No VAD extra ni modificación de resultados; las copias y
consultas pueden alterar tiempos.21812/46130exit0, speaking5,578s/0barge, captura
35,17s/restauración exacta. Se guardan261frames de micrófono y234callbacks de512
muestras de referencia. Datos privados timing139.json/npz; índice TIMING_INDEX.json.

140 coteja por hash el último bloque de referencia que consumió cada frame con
los bloques reales del productor. Sobre referencias con RMS≥20PCM:125frames,
122avances normales de un bloque,2repeticiones del mismo bloque y1salto de tres
bloques (omite dos). En toda la secuencia identificable hay6repeticiones y un
salto de24bloques. Los primeros ceros sin callback aún no se pueden identificar
por hash; no inventarles posición. El contador callbacksSeen también observa
56lecturas sin callback nuevo, pero no todas prueban una repetición identificable.

Micrófono reporta latencia32ms; loopback64ms. read_available varía0–1536muestras.
Los relojes de ambos streams difieren en mediana~7µs al consultarlos seguidos.
La causa demostrada: **latest512 no entrega una secuencia continua**. Un filtro
adaptativo consume otro historial si el hilo lector cambia de ritmo. Todavía no
se atribuye cada corte138 a un frame concreto porque138 no grabó esas entradas.

## 141/142: medir timestamps antes de diseñar su uso

La documentación de [sounddevice0.5.5, streams](https://python-sounddevice.readthedocs.io/en/0.5.5/api/streams.html)
define los timestamps ADC del callback y el número de frames disponibles en lectura
bloqueante. No garantiza que cada backend los implemente con igual precisión.
Se consultó2026-09-07, misma versión instalada.141/142 sólo guardan metadatos de
relojes durante3,5s, sin PCM, reproducción ni cambio de volumen.

141 usa el input predeterminado MME Realtek.109callbacks: **ADC y currentTime son
cero en todos**, aunque Stream.time sea válido. Loopback WASAPI:114/114ADC no cero,
paso mediano32,014ms y currentTime−ADC10,667ms. Exit0. No fundamentar sincronización
en los timestamps MME ausentes ni asumir que Stream.time es el tiempo de la muestra.

142 cambia sólo la captura al dispositivo predeterminado de Windows WASAPI,
mismo Realtek físico (índice12 en esta máquina), con modo compartido y
[auto_convert](https://python-sounddevice.readthedocs.io/en/0.5.5/api/platform-specific-settings.html)
para16kHz sobre formato del sistema48kHz. El SDK permite esa conversión; no se
modifica el formato global del dispositivo.109/109timestamps ADC válidos en mic,
112/112en loopback; cero flags de error. Medianas de pasos32,026 y32,049ms, con
jitter de varios ms. Relojes Stream.time separados por~6µs; callback perfCounter
menos currentTime alrededor50µs. Es evidencia de una base común utilizable aquí,
no de precisión perfecta ni de compatibilidad ya probada en todos los PCs. Exit0.
Se conserva la medición completa en astra-clocks141/142, sin guardar voz ambiente.

## Cambio siguiente, todavía no aplicado

Reemplazar lectura MME/latest por captura WASAPI con timestamp y referencia
consumida por posición de muestra. Anclar ambos orígenes una vez con los timestamps
medidos y avanzar512muestras por frame; no realinear cada frame con el reloj de
planificación. Esperar de forma acotada los datos de referencia necesarios, con
cancelación y error honesto ante pérdida/overflow, sin repetir ni saltar muestras.
La correlación requiere el historial que corresponde al frame, no el más reciente.

El callback debe hacer trabajo acotado; sacar la primera importación scipy fuera
del callback y sustituir la copia completa del ring si se cambia su almacenamiento.
No sumar otro AEC. Estado Speex y par crudo anterior de136 permanecen como dueños
del DSP. La ruta use_pcm_source sólo aparece en scripts/goal09_voice_launch.py y
pruebas Goal09: no tiene reloj de micrófono y no debe alinearse inventando timestamps
con el audio real del escritorio. Debe declarar AEC no aplicado para esa entrada.
Esto no acredita aceptación física de un diagnóstico con PCM inyectado.

143 debe probar continuidad bajo ráfagas del productor/lector, ajuste inicial,
cancelación/overflow y cierre de dispositivos; luego medir físicamente sin wrappers.
No cambiar umbrales de barge-in ni aceptar una corrida favorable aislada. Full
queda para cierre integrado de C03. Reserva100/runtime/UI/voz humana y los demás
requisitos del goal siguen íntegros.
