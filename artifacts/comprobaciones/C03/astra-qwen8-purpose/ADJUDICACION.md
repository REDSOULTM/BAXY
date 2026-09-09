# Contraste de propósito — desarrollo, no aceptación

Modelo, muestreo, corpus y presupuestos iguales a astra-qwen8-product.
Único cambio de producto: la proyección conserva kind y state=in progress.
Termina exit 0 en 254.25 s; pico 3337.57 MiB VRAM y 6828.86 MiB RAM.
Registro Granite intacto, sin promoción. Telemetría del árbol disponible.

| Turno | Respuesta | Veredicto |
|---|---|---|
| 1, saludo EN | Hello! | Útil. |
| 2, doce por ocho | Noventa y seis. | Útil y correcto. |
| 3, fourteen times six | Eighty-four. | Útil y correcto. |
| 4, explicación mixed | composition_failed | Falla. |
| 5, spanglish explícito | composition_failed | Falla. |
| 6, capital de Perú | Lima. | Útil y correcto. |

4/6 útiles frente a 3/6 antes. Se recupera t2; las dos explicaciones siguen
sin respuesta. La diferencia de duración es descriptiva de estas corridas,
no una certificación de latencia. No hay aceptación reservada.

La bienvenida de la sesión reiniciada ahora sí saluda: «¡Hola! Soy Baxy,
tu compañero. ¿En qué puedo ayudarte?». Se rechaza como too_many_sentences.
Es un falso rechazo: el contrato C03 acepta formulaciones equivalentes.
El progreso ES sigue exigiendo literalmente sigo; EN exige still o working.
Esto mantiene rigidez de estilo y queda pendiente de reparar con conservación
de las comprobaciones de efectos no verificados, sin aceptar cualquier prosa.
