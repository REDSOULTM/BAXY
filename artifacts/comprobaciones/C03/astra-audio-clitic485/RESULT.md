# 485 — conservación del verbo desmutear con pronombre

La lectura explícita reconocía desmutea pero no desmutéalo. La misma omisión en el
separador de cláusulas hacía que volumen + desmutéalo quedara como una sola cláusula:
seleccionaba sólo audio.volume y no avisaba de la segunda operación perdida.

Se incorpora la familia ya existente de reversión del silencio con sus pronombres,
reutilizada en el dominio de audio, sus verbos y los límites de cláusula. No se altera
el catálogo, el bool de mute, el provider, un prompt ni el muestreo. SOURCE.patch
muestra sólo este tramo, separado del WIP anterior.

Antes:4 fallos/8 pass. Después:12 pass focales. Suites effect_intent, turn_policy,
request_reading, compose_contract y llm_transport:3139 pass,0 skips,47,60s.
Fast completo verde; Release4,06s,0 advertencias/errores. Sesión73834 terminó exit0.
No Full durante reparación. No se cambió el volumen ni se reprodujo audio en esta
verificación. Falta el paso integrado de mente/contexto/argumentos sobre los turnos
reales, incluida la errata dessilencies, que esta corrección no pretende resolver.
