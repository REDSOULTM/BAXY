# 531 — expectativas actuales y evidencia histórica

Full526 contiene8fallos adicionales a los15resueltos en528 y2de530. Diagnóstico529: el contrato vivo permite abstenerse (r277); el control de misión incompleta levanta PlannerContractError para recuperación (09.5.11C); la declaración de runtime aún nombra Granite aunque sólo difieren nombre/hash del GGUF respecto a Qwen registrado; los pins actuales de V8 y del árbol de programas STT preceden a las fuentes adoptadas. Un template tiene CRLF de checkout y su forma LF coincide con el hash histórico publicado.

Reparar expectativas vivas y adaptador de diagnóstico a contratos ya adoptados. Recalcular únicamente las declaraciones explícitamente actuales de código/runtime, conservando sellos, corpus, cifras y veredictos históricos. Comprobar en disco GGUF y servidor contra el manifiesto antes de declarar el runtime. Restaurar sólo el template cuyo hash LF coincide exactamente con TEMPLATE_COMPARISON.json y proteger sus bytes en .gitattributes. Esto no promueve un candidato ni acredita voz/hardware.

Validación: todas las dueñas de los8fallos, Ruff y Fast al finalizar junto con530. No omisiones nuevas ni umbrales relajados. Los sellos históricos de r277/V8/wake se conservan y sus tests deben pasar. Si algún pin representa aceptación histórica, no cambiarlo como expectativa actual.

Encuesta:0cubiertos/742abiertos/0no aplicables; una declaración o test de contrato no sustituye adjudicación de conducta generalizada.
