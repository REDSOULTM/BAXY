# Adjudicación individual — astra-gemma-inherited-ready

Diagnóstico directo, no aceptación C03. Evaluación manual del asistente; hechos históricos.

| Variante | Turno | Resultado | Motivo |
|---|---|---|---|
| standard_base | t8 | NO APROBADO | Sólo inglés; además generaliza el uso de la misma clave, que no cubre el cifrado asimétrico. |
| standard_base | t9 | NO APROBADO | No respeta la petición explícita de spanglish: contesta sólo en inglés. |
| standard_base | t10 | NO APROBADO | No respeta la mezcla de idiomas: contesta sólo en inglés. |
| standard_base | t13 | APROBADO | Explicación pertinente en inglés, en dos oraciones. |
| standard_base | t14 | APROBADO | Explica la menor densidad del hielo en español; la comparación de peso debe entenderse a igual volumen. |
| standard_base | t15 | NO APROBADO | Distingue archivo y carpeta, pero ignora la petición explícita de spanglish. |
| standard_base | t2 | APROBADO | Conserva hora, volumen y ausencia de silencio; no afirma haberlos cambiado. |
| standard_base | t4 | APROBADO | Conserva la hora y el volumen solicitados, en inglés. |
| standard_base | t6 | NO APROBADO | Conserva los datos, pero responde sólo en español; no satisface spanglish. |
| inherited_lora | t8 | NO APROBADO | No respeta la mezcla de idiomas: contesta sólo en inglés. |
| inherited_lora | t9 | NO APROBADO | No respeta la petición explícita de spanglish: contesta sólo en inglés. |
| inherited_lora | t10 | NO APROBADO | No respeta la mezcla de idiomas: contesta sólo en inglés. |
| inherited_lora | t13 | APROBADO | Explicación pertinente en inglés, en dos oraciones. |
| inherited_lora | t14 | APROBADO | Explica la menor densidad del hielo en español; la comparación de peso debe entenderse a igual volumen. |
| inherited_lora | t15 | NO APROBADO | Distingue archivo y carpeta, pero ignora la petición explícita de spanglish. |
| inherited_lora | t2 | NO APROBADO | Omite si el audio está silenciado: sólo comunica hora y volumen. |
| inherited_lora | t4 | APROBADO | Conserva la hora y el volumen solicitados, en inglés. |
| inherited_lora | t6 | NO APROBADO | Omite el estado de silencio y no produce spanglish natural; «Es las» es incorrecto. |
