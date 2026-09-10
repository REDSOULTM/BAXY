# La integración debe respetar el modelo y explicar el contrato de BAXY

La preocupación del dueño está respaldada por evidencia: evaluar K2 dentro de todas las capas actuales de BAXY mezclaría la capacidad del modelo con problemas de adaptación. No está demostrado que todas esas capas estén ajustadas a Qwen. Sí se encontraron decisiones heredadas sobre razonamiento, mensajes system y formato estructurado que necesitan tratamiento por modelo.

Ya existe una referencia nativa de699: seis perfiles con50 tareas completas cada uno, sin BAXY.731 aisló una opción concreta: el mismo K2 high pasó de38/50 a19/50 al añadir `enable_thinking=false`, con3 mejoras y22 pérdidas. Esa comparación conserva pesos/backend/muestreo/contexto y usa un control histórico de una semilla; no es un ranking universal. [Prueba731](../K2_HORIZON_ADAPTER731/REPORT.md).

732–734 comprueban fronteras de integración; no son nuevas tandas de calidad de50 casos ni completan la comparación del producto. El adaptador sigue siendo experimental y el runtime registrado no se ha sustituido.

| Frontera | Evidencia | Estado |
|---|---|---|
| Perfil nativo, razonamiento y separación de mensajes | Preflight50 payloads y controles reales732 | Verificado en ese alcance |
| Herramientas nativas | `system.time` correctamente propuesto, razonamiento separado | Control técnico correcto; sin ejecución |
| Gramática compacta del guardia | Tres finales vacíos; JSON forzado dentro del razonamiento733 | Incompatible con ese perfil |
| Esquema original sin explicarlo al modelo | Dos timeouts y un recuento incorrecto733 | No cumple |
| Esquema original con instrucción contractual734 | Dos JSON finales, ambos con recuento incorrecto; un timeout | No cumple |

734 conserva el esquema exacto durante la conversión interna a GBNF, lo restaura en el transporte K2 y añade un único mensaje de serialización que contiene ese mismo esquema. Conserva la política original, historia, catálogo, semilla de reintento, validadores y presupuesto total de19s. La comprobación con un transporte de prueba verificó que no se muta la entrada y que el schema añadido coincide exactamente con el original. La traza real confirmó input con GBNF, wire con schema, dos mensajes system y razonamiento high.

| Pedido | Resultado real del guardia | Tiempo |
|---|---|---:|
| «Dime la hora.» | Lectura externa completa, cero efectos | 7,891s |
| «What time is it?» | Lectura externa completa, cero efectos | 4,640s |
| «Dime the current time, por favor.» | Timeout del presupuesto local | 19s |

Los dos JSON finales contienen `{"request_type":"external_read","effect_count":"zero"}`. BAXY requiere contar la lectura pedida; estas respuestas no aprueban. La traza muestra que K2 reconoce la necesidad de información actual pero distingue una consulta de una acción con efectos. Esto señala una posible ambigüedad del contrato de clasificación que debe revisarse, no un motivo para aceptar cero ni para retirar el guardia.

**Cambio de estrategia:** detener los ajustes pequeños de parámetros/formato, porque los dos perfiles de schema no cumplieron ninguno de los tres casos. Revisar la definición compartida de qué cuenta como efecto y su consecuencia en el producto; después medir una categoría completa con variantes. No añadir respuestas esperadas por frase, no recuperar razonamiento como prosa visible y no relajar plazos.

Picos734 del servidor:3446,23MiB de VRAM y799,79MiB de RAM. Son consumos del servidor del modelo, no de BAXY completo con interfaz y voz. Sesión22979 terminal exit0; servidor cerrado; fuente y manifiesto intactos. Los fallos semánticos/timeouts cuentan como fallos aunque el conductor termine exit0. Ninguna promoción, adopción o cobertura de encuesta.

El método de comparación que se conserva es: **modelo nativo → adaptación propia → integración de BAXY por etapas**, atribuyendo el primer cambio incorrecto. Qwen sigue provisional y K2 continúa bajo evaluación. C03 está abierto:26 requisitos cubiertos,716 abiertos y0 no aplicables; Full5 conserva sus dos fallos originales. [Detalles732](../K2_HORIZON_CONTRACT732/REPORT.md) · [Gramática733](../K2_HORIZON_GRAMMAR733/REPORT.md).
