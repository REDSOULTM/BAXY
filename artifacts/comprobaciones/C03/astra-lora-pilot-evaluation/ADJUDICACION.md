# Adjudicación individual — primer piloto

Diagnóstico directo, no aceptación. Adjudicación manual posterior a la captura.

| Variante | Caso | Resultado | Motivo |
|---|---|---|---|
| base | day-night-es | NO APROBADO | Confunde alejarse del Sol con quedar orientado al lado opuesto; «unos 24 horas» es incorrecto. |
| base | day-night-en | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| base | day-night-mixed | NO APROBADO | Sólo español; inventa un ciclo fijo de 12 horas y que sin rotación todo sería luz. |
| base | heat-metal-es | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| base | heat-metal-en | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| base | heat-metal-mixed | NO APROBADO | Sólo español, con «del sopa» y cierre innecesario; no satisface idioma/naturalidad. |
| base | audio-holdout-0-es | NO APROBADO | Omite si está silenciado y la unidad del volumen. |
| base | audio-holdout-0-en | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| base | audio-holdout-0-mixed | NO APROBADO | Hechos correctos, pero sólo español. |
| base | audio-holdout-1-es | NO APROBADO | Omite que el audio está silenciado. |
| base | audio-holdout-1-en | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| base | audio-holdout-1-mixed | NO APROBADO | Hechos correctos, pero sólo español. |
| base | previous-t8 | NO APROBADO | Una palabra inglesa aislada no cumple la combinación natural de frases ES/EN. |
| base | previous-t9 | NO APROBADO | Backup como préstamo aislado no satisface el spanglish solicitado. |
| base | previous-t10 | NO APROBADO | Analogía de pegarse imprecisa y mezcla limitada al nombre inglés. |
| base | previous-t13 | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| base | previous-t14 | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| base | previous-t15 | NO APROBADO | Definición inicial circular y sólo español pese a pedir spanglish. |
| base | previous-t2 | NO APROBADO | Introduce la palabra inexistente «desmudado». |
| base | previous-t4 | NO APROBADO | Datos correctos, pero redacción técnica innecesaria («mute state is off») en vez de narración natural. |
| base | previous-t6 | NO APROBADO | Sólo español; no satisface spanglish. |
| pilot_lora | day-night-es | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| pilot_lora | day-night-en | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| pilot_lora | day-night-mixed | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| pilot_lora | heat-metal-es | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| pilot_lora | heat-metal-en | NO APROBADO | Explicación tautológica y poco natural: la cuchara transfiere calor desde la sopa a la cuchara, sin explicar la conducción. |
| pilot_lora | heat-metal-mixed | NO APROBADO | Mezcla forzada «El metal spoon» y «contacto directo con el calentamiento»; no logra naturalidad. |
| pilot_lora | audio-holdout-0-es | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| pilot_lora | audio-holdout-0-en | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| pilot_lora | audio-holdout-0-mixed | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| pilot_lora | audio-holdout-1-es | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| pilot_lora | audio-holdout-1-en | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| pilot_lora | audio-holdout-1-mixed | NO APROBADO | Conserva los hechos, pero sólo español. |
| pilot_lora | previous-t8 | NO APROBADO | Sólo español y sustituye cifrado por el concepto más amplio de criptografía. |
| pilot_lora | previous-t9 | NO APROBADO | Repite una traducción completa, expresamente excluida por el contrato de spanglish. |
| pilot_lora | previous-t10 | NO APROBADO | La explicación mejora, pero responde sólo en inglés. |
| pilot_lora | previous-t13 | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| pilot_lora | previous-t14 | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| pilot_lora | previous-t15 | NO APROBADO | Sólo español; además reduce archivo a documento, aunque puede contener otros datos. |
| pilot_lora | previous-t2 | NO APROBADO | Afirma audio desactivado cuando muted=false: inversión de un hecho verificado. |
| pilot_lora | previous-t4 | APROBADO | Responde de forma útil y fiel a los hechos o al concepto, en el idioma solicitado. |
| pilot_lora | previous-t6 | NO APROBADO | Hechos conservados, pero sólo español. |
