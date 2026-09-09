# 329–330 — separar admisión de continuidad y guardado

329 demostró que basta quitar el veto temporal espurio para que el modelo pida el
nombre; no hizo falta otro prompt.330 aplica una delimitación estructural, todavía
sujeta a la repetición completa331. Ninguno de esos tramos implementa persistencia.

Fronteras relevantes para el siguiente cambio:

- NaturalMemoryRequestParser.NameSavePattern admite un valor explícito junto a
  «recuerda que me llamo»/«remember my name is». Una declaración sola tiene
  AskToSave; desde299 conversa sin persistencia implícita.
- VM:763 publica ClarifySave y sale; no registra cuál dato pidió. MemoryTurnSession
  sólo tiene confirmación y operación por reconciliar, no un valor faltante.
- MissionInput.cs:248 tiene PrivateCompoundMissionParser: separadores fuertes y
  un segmento privado más continuación pública. MemoryTurnSession.PublicAfterMemory
  puede continuar un pedido después del guardado verificado. Reusar estos dueños.
- El texto103 combina declaración de nombre y saludo con coma; el separador
  «, dime» no está entre los separadores fuertes. No guardar el saludo como parte
  del nombre ni perderlo al añadir persistencia.
- VM:2103 impide ejecutar memory.* por una propuesta de la mente sin canal privado.
  No quitar esa frontera para facilitar la prueba. La operación final requiere
  autenticación, validación de datos sensibles y postlectura verificable.

No adoptado: anteponer «recuerda que» a cualquier respuesta posterior. Eso podría
guardar una queja, otro tema o una instrucción como si fuese el valor solicitado.
La continuidad debe vincular la petición explícita con el dato, conservar
interrupciones conversacionales pertinentes y cerrarse al cancelar/cambiar sesión.
Evitar una segunda maquinaria de diálogo paralela a las que ya existen.

Próxima decisión de esfuerzo alto: tras331, elegir el mínimo cambio en esos dueños
que conserve intención y valor sin ampliar permisos. El guardado debe probarse en
perfil privado, y el recuerdo tras nueva sesión debe distinguirse de recordar sólo
por historial. Las fuentes oficiales de formularios/slots apoyan esta separación;
no se adoptan servicios remotos ni una dependencia para implementarla.
