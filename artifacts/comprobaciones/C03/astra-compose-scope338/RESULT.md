# 338 — dueñas verdes; producto pendiente

Baseline definitivo:14 fail,1 pass,60 deselected,0,75s. Incluye los tres borradores
españoles reales a través del compositor completo, proyección inglesa y eventos
tipados. Después de acotar can/beyond a kind conversation:

`C:/Users/usuario/AppData/Local/BAXYRuntime/python/mind-runtime-v1/Scripts/python.exe -m pytest tests/test_turn_policy.py tests/test_compose_contract.py -q -x --tb=short`

1023 pass,0fail,0skip,5,24s. Se conserva el control de capacidades/límites reales.
Sin cambios al validador, modelo, prompts, muestreo ni respuesta visible fija.

Preparación: QualityPython y py global no tienen pytest; no son fallos de BAXY.
Primer fixture usaba request, reservado por pytest9; corregido a user_text.
La primera comprobación usaba sólo compose_visible_defect y no atravesaba el
validador de payload: sustituida por _Recorder.compose_user_message para reproducir
el fallo real español. Se conservaron todos los logs, sin contabilizarlos como pases.

Límite descubierto: «What can you do? Remember my name.» también dispara
knowledge_question en otro filtro. El control inglés338 verifica sólo la proyección
de hechos; no acredita esa variante integrada. Ese defecto queda pendiente dentro
de C03 y requiere resolver la distinción entre conocimiento y aclaración operativa.

Fast338 verde: buildRelease3,77s,0errores/advertencias. Producto339 terminó:
1/6útil,0silencios frente a3370/6,1silencio. Pregunta99 recuperada a la primera;
cinco fallos continúan. Perfil nuevo por defecto, mismos seis literales,
runtime y muestreo que337. RESULT/PINS en astra-memory-product339.
No Full durante reparación.
