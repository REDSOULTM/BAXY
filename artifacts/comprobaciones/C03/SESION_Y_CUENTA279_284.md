# C03 — recuperación de sesión y conservación de cuenta279–284

Estado EN_CURSO. No aceptación ni promoción de modelo.

279 comparó schemas tipados reales con tools vacías sobre siete controles de278.
5/7 criterios semánticos: las tres aperturas del dueño se recuperan, pero win07
continúa app.installed y cmp01 sólo devuelve música, omitiendo app.open. No adoptar.
PREREG/RESULT en astra-schema279; fuente sin cambios. No truncamiento (3240–3612
tokens de prompt, contexto4096). Herencia y documentación Qwen consignadas allí.

280 guardó un dump Heap privado del proceso84328 con dotnet-dump10.0.731102,
herramienta oficial de diagnóstico, sin subir contenido. 281 detectó que la
presentación textual SOS perdía caracteres no ASCII: falló la comprobación de
longitud, por lo que no se aceptó esa extracción. 282 siguió la colección real
MainWindowViewModel.Messages, lista de121 elementos, y extrajo bytes UTF16LE.
Resultado exacto:63 mensajes del dueño,58 de BAXY; orden, longitud y horas
comprobados. No equivale a nueva captura de píxeles ni a100 turnos frescos.

Transcripción completa privada:
C:/Users/usuario/AppData/Local/BAXY/C03-owner264-heap280/TRANSCRIPT282.md
JSON SHA256 9658a77505564ec1384e58aba91ed75d03b078f865182f94b6ecc3b0ee839ef6.
No añadir dump ni transcripción completa a Git. Evidencia pública mínima:
astra-heap280/COLLECT.json y astra-transcript282/RESULT.json.
Ya se cumplió preservar conversación antes de reiniciar instancia264.

283: «quien soy» → «Hola, soy BAXY.» aunque Core entregó system.identity
verificado con userName. Comparación de una obligación dinámica de conservación
del dato, mismo primer payload y modelo local. Nueva respuesta:
«Tu nombre de usuario en el sistema es usuario.» No afirma guardar nombre personal.

284 incorpora esa obligación en llm._payload_fact_defect, reutilizando missing_name
y reintento existentes. No texto visible fijo, constante de usuario ni blacklist
de frases. Controles de nombre distinto, acentos, mayúsculas, nombres compuestos,
ausencia de dato y reintento real de compose_user_message.
Las primeras versiones de controles tenían errores de idioma y usaban
compose_visible_defect, que no es dueño del guard de payload. Se corrigieron al
límite real _compose_situation_payload→_payload_fact_defect; el test de composición
completa se conservó. Todos los logs fallidos permanecen para trazabilidad.
Control previo, guard antiguo aislado en proceso:5fail8pass30deselected0,41s.
Fuente actual: pytest tests/test_compose_contract.py tests/test_llm_transport.py
tests/test_turn_policy.py -q --tb=short →1012pass0skip5,20s. Ruff verde.
Repetición nativa con fuente adoptada, sin monkeypatch: misma respuesta correcta,
primer payload idéntico a283. astra-account284/NATIVE_RESULT.json.

Límites: no corrige selección system.identity ni memoria personal. Persisten
negaciones falsas de capacidades, conversación contextual, compuestos, resultados
ausentes y veracidad del resto de sesión. Fast integrado266/267/284 pendiente;
últimoFast262. No Full durante reparación. Cuestionario742 sigue disponible,
respuestas del dueño intocadas. Campaña final, voz, recursos, instalación,
continuidad y publicación fuera main pendientes.
