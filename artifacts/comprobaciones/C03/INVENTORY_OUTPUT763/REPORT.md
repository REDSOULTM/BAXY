# Lista completa observada después del corte

La petición exacta capturada en762 termina en4,141s con20 entradas y alcance20/24, sin inventar fechas de apertura. Son727 tokens de entrada y174 de salida, stop normal:407ms de prefill y3717ms de generación (46,81tokens/s). La lectura manual y el verificador de ventanas actual aceptan su contenido. Sigue siendo un fallo frente al límite original de cuatro segundos; no se transforma en un éxito de producto.

Se permitió observar15s, conservando payload, sampler y límite256 de salida. El directorio del servidor coincide con el del intérprete registrado; el resto del entorno heredado no se certifica idéntico. Una muestra no acredita estabilidad de latencia. El servidor alcanzó3495,56MiB de VRAM y718,11MiB de RAM residente, sin guarda activada; no es BAXY con UI/voz.

La selección de tiempo en MindSidecarClient ya reserva nueve segundos al modelo para respuestas densas, pero sólo cuenta requiredFacts. Este inventario llega dentro de situation y recibe cuatro. Siguiente reparación: reconocer ese volumen observado con la política existente, validar y medir la entrega real antes de acreditarla. No ampliar el límite global ni cambiar el modelo.

Errata conservada: RESULT.json dice calls_planned=2 por una constante heredada; PREREG, planned.json, resultados y petición ejecutada muestran exactamente una llamada. ADJUDICATION.json deja la corrección sin reescribir los bytes originales. Encuesta26/716/0; C03 activo.
