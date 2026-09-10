# K2 conserva herramientas y prosa; el JSON aún no acredita el plazo

El adaptador experimental conserva el razonamiento alto de K2, su muestreo práctico medido en699 y cada mensaje system por separado. Reserva4096 tokens para razonamiento y respuesta. No cambia los pesos, el runtime registrado, los contratos, los validadores ni la fuente productiva.

La comprobación sin inferencia verificó las50 peticiones históricas de696: los campos ajenos al perfil permanecen iguales, incluidos mensajes, herramientas y contratos. Un transporte simulado comprobó paso de argumentos, reintentos, presupuesto y excepción; eso no acredita cancelación física ni calidad del modelo.

| Formato real de BAXY | Resultado recibido | Tiempo |
|---|---|---:|
| Selector de herramientas, «Dime la hora.» | Propone `system.time`; razonamiento separado, sin ejecutar la operación | 2,031s |
| Decisión estructurada del mismo pedido | JSON válido que propone `system.time`, después de un reintento | 22,859s |
| Escritor con tres mensajes system, presentación sintética de Álvaro | «¡Hola Álvaro! ¿Qué has hecho hoy?» | 2,750s |

**Corrección de alcance del prerregistro:** el caso de decisión conservó `response_format`; no activó GBNF compacto, pese a lo anunciado en PREREG. La función real sólo compacta el validador semántico de efectos. Esa ruta se mide aparte en733. Se conserva el prerregistro original para que la desviación sea visible.

**El JSON no aprueba el plazo del producto.** Esta prueba llamó directamente a los roles con el límite HTTP de19s por intento, sin activar `begin_request`. El servidor canceló una generación a los19s y el transporte reintentó; el resultado final llegó a los22,859s. No se interpreta como un éxito dentro de19s.733 activa explícitamente el presupuesto total de19s.

Picos del servidor:3446,23MiB de VRAM y822,18MiB de RAM; sin infracciones del guardián de memoria. No son el consumo conjunto de BAXY, UI y voz. Driver terminal exit0, sesión15917; servidor cerrado. Ninguna adopción, promoción, cobertura de encuesta ni aceptación de producto. C03 sigue abierto.

Se preservan peticiones originales/adaptadas, respuestas y log del servidor en el directorio privado `C03-k2-contract732-private`. La revisión independiente confirmó las dos limitaciones anteriores. Siguiente evidencia: [compatibilidad de la gramática733](../K2_HORIZON_GRAMMAR733/REPORT.md).
