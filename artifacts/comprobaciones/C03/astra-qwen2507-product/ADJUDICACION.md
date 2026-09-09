# Qwen3-4B-Instruct-2507 heredado — desarrollo

Mismo checkpoint/archivo que R82, SHA 3605803b…; estaba en la ruta histórica
de experiments/models. No se descargó nada. Diagnóstico ngl99/q8; registro
Granite intacto. Termina exit 0 en 59.83 s; 3497.56 MiB VRAM y 4861.17 MiB
RAM del árbol. No promoción ni aceptación de los otros roles.

| Turno | Respuesta | Veredicto |
|---|---|---|
| 1, Hello | Hey, welcome! How can I help you today? | Útil. |
| 2, doce por ocho | 96 | Correcto. |
| 3, fourteen times six | 84 | Correcto. |
| 4, Explain encryption, pero en simple | Pregunta si se quiere criptografía general, AES o RSA. | Falla: aclaración innecesaria y pérdida de mixed. |
| 5, spanglish explícito | Explica transformación, clave y acceso en ES/EN. | Útil y fiel; la analogía se repite parcialmente. |
| 6, capital de Perú | The capital of Peru is Lima. | Correcto. |

5/6 útiles, 6/6 publicados, sin agotamientos. El estilo de t5 es mejorable;
no se confunde publicar seis mensajes con responder bien a los seis pedidos.
paired.json conserva la prosa íntegra. La diferencia de duración sólo describe
estos perfiles/corridas; C07 deberá certificar sus propias métricas.

La lectura general omitía Explain y el clasificador cerraba sólo explicaciones
de hardware, why o difference. Cuatro regresiones de explicaciones completas
fallaron antes. Tras generalizar la envoltura existente a explain/explica/
explicame y conservar sus controles de catálogo: 1246 pass/101 subtests.
Prueba siguiente: astra-qwen2507-explanation. El fallo arguments-06 histórico
(app.open: abre la calculadora) sigue siendo condición para cualquier promoción.
