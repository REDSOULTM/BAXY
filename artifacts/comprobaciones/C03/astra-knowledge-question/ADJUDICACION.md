# Petición de conocimiento conservada — desarrollo, 2026-09-06

**4/4 respuestas útiles, fieles y naturales**, con runtime Granite registrado,
por la entrada real del conductor. Proceso terminó exit 0. Casos y expectativas
preregistrados; todos siguen siendo desarrollo, nunca aceptación fresca.

| Pedido | Respuesta pública | Veredicto |
|---|---|---|
| What is fourteen times six? | 14 times 6 is 84. | Pasa: cálculo solicitado, sin definir multiplicación. |
| define DNS in one sentence | DNS stands for Domain Name System, which translates domain names into IP addresses so computers can communicate using readable names instead of numerical addresses. | Pasa: definición fiel en una frase. |
| cuánto es doce por ocho | Doce por ocho es 96. | Pasa. |
| what is the capital of Peru | The capital of Peru is Lima. | Pasa. |

Todos los estados posteriores permiten entrada, sin misión pendiente ni error
de composición. DNS llegó a recuperación tras un rechazo interno; la respuesta
publicada es correcta. Esto no demuestra cero falsos rechazos ni sustituye R07.

La modificación conserva el pedido bajo INTENT_KNOWLEDGE, que incluye entidades
y cantidades. Antes imponía «Explain the concept» y el diagnóstico Qwen3-8B
definía la multiplicación sin dar su resultado. Tres regresiones deterministas
fallan antes, pasan después; dueños completos: 366 pass y 101 subtests.
STT/V8: 17 pass, 1 skip ambiental; corpus histórico sin modificar.

Quedan el panel completo de desarrollo, los cien reservados, ocho rutas/tres
idiomas, recuperación inyectada, UI y cierre. No extrapolar cuatro aciertos.
