# Tres falsos vetos reparados — 793

Se adopta la reparación de tres condiciones compartidas del verificador de BAXY. “No open windows” describe un inventario vacío y deja de confundirse con una instrucción copiada; los fragmentos aislados de instrucción siguen vetados. Una cantidad que introduce los nombres observados corresponde a la página, mientras los modificadores explícitos de total conservan prioridad. La negación de representar/abarcar/cubrir todas las ventanas conserva su polaridad.

Se añadieron72 controles de significado, con cantidades, inventarios completos o parciales y formulaciones españolas e inglesas. Antes del cambio:60 fallos y148 pass en la suite ampliada. Después:947 pass en las suites específicas; validación final de21 suites **3134 pass,1 skip ambiental STT y121 subtests en21,30s**, más Fast exit0 y build Release23,74s. Los comandos exactos están en VALIDATION.json. No se acredita voz con el skip.

REPLAY.json demuestra que los cuatro primeros borradores capturados que antes se vetaban llegan ahora intactos en una sola llamada simulada, conservando los payloads originales. La [verificación real794](../INVENTORY_COMPOSER794/REPORT.md) confirma las cuatro recuperaciones con Qwen, sin pérdidas en los otros casos del panel. No se cambia el primer prompt, sampler, pesos, backend ni plazos del producto.

El candidato incorpora las reparaciones preservadas787/789/791: presupuesto ya existente512 para inventarios densos, alcance de cantidades y conservación de identidades/multiplicidades. Las seis listas que se completaron al ampliar la salida siguen correctas en una llamada. No se incorpora la eliminación de rejected_draft probada en792.

Los13 archivos están preservados en SOURCE_SNAPSHOT.json y SOURCE_PATCH.diff; programa407=5584f52ee0601dd0e6f8bba8a42cfa5ffd046ad124e7863441dc790ddcf0be93. Full final sigue pendiente; el objetivo autoriza no repetirlo por cada reparación sólo Python. Encuesta28cubiertos/714abiertos, sin crédito nuevo por estas variantes sintéticas. Se continúa por categorías completas de bloqueantes, con la selección de Qwen cerrada.
