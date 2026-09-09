# 340 — continuar una petición de guardado con memoria desactivada

Problema medido:339/103 y journal337 muestran memory.save fallido con
memory_disabled, no pérdida de valor. El producto explica la causa pero abandona
la petición. Memoria336 sí persiste cuando se activa/confirma explícitamente.

Herencia: MemoryTurnSession ya lleva confirmación, recuperación y continuación
pública; MemoryOperationProtector sella y vincula argumentos a sesión/invocación.
El catálogo exige confirmación para memory.enable. Carter_v2/LLM_CONTEXT_MEMORY_REPORT.md
12–40 separa dato humano de prosa del asistente; memory.lean.md de Gemma4 exige
petición explícita para guardar. Las referencias de parámetros requeridos y
continuidad ya contrastadas en MEMORIA_CONTINUIDAD336_PREREG.md siguen aplicando.

Diseño a probar: ampliar la continuación existente, sin otro planificador.
Ante memory.save normal, de la sesión actual, fallido explícitamente por memoria
deshabilitada: conservar el pedido privado protegido y solicitar la confirmación
de memory.enable por el canal existente. No cambiar el default ni activar antes
de confirmar. Tras enable verificado, preparar una NUEVA invocación de save con
los mismos argumentos privados; guardar y continuar el objetivo público existente.
No reutilizar el intento de save ya terminal ni el token de enable para save.

Cancelación retira toda continuación. Un reinicio no ejecuta un save conservado
únicamente en RAM; recuperación de invocaciones antiguas mantiene sus reglas.
Una avería no habilita memoria por inferencia. Secretos conservan su confirmación
propia y no entran en este autoencadenamiento de guardado normal. No reofrecer enable
en bucle si un save reanudado vuelve a fallar. Todo texto visible lo formula el modelo.

Verificar: perfil inicialmente deshabilitado, cero registros antes de confirmación,
respuesta inválida sin habilitación, confirmación con IDs exactos, dos intentos save
distintos, dato recuperado tras nueva sesión, cancelación sin guardado tardío y
regresiones privadas existentes. Dueñas y Fast; luego producto y diálogo adaptativo
con confirmación explícita, separado de los seis turnos literales de regresión.
No aceptación fresca, UI gráfica, voz física ni Full durante reparación.
