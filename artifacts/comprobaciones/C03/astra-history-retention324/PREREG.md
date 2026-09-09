#324 — conservar datos conversacionales al aclarar

319/322: después del silencio de107 la App conservó una aclaración pendiente.
Al recibir109, BuildMindHistory no se llamó y turn.decide recibió history:[],
aunque Messages todavía contenía el nombre humano. Esto no era truncamiento.

323 repitió el payload conversacional real322 con el mismo modelo, instrucciones,
muestreo y límite, normalizando el prefijo system como hace producción. Antes:
afirmó que no sabía quién era el usuario. Con sólo el diálogo real repuesto:
«Yo soy BAXY, tu compañero en el PC. Y tú te llamas Emmanuel. 😎».
No se usó el resolvedor contextual320 ni se modificó un prompt. La referencia
a un control de tema nuevo en criteria323 quedó heredada del script320:323 sólo
comparó los dos payloads del mismo turno y no prueba regresiones de otros temas.

Cambio propuesto: transportar siempre la historia ya acotada de Messages a la
primera lectura. pendingClarification:false sigue separando esa lectura de la
reanudación autorizada de un objetivo. El mecanismo existente conserva/retoma
la invocación pendiente sólo cuando corresponde; no se toca su autorización.

Regresión: introducir nonce en turno de usuario, crear una aclaración, preguntar
por el nonce y comprobar que cruza el proceso. No basta mirar Messages localmente.
También conservar los controles de nuevo pedido independiente y fragmento que
retoma el objetivo exacto. La aserción histórica de history vacío en ese fragmento
debe sustituirse por historia conservada y pendingClarification:false, manteniendo
la secuencia exacta de tres lecturas y el objetivo retomado.

Aceptación de la tanda: pruebas dueñas, Fast integrado, mismo producto de seis
literales319/322. Se adjudica cada respuesta; no se declara memoria resuelta si
sólo mejora la última identidad. BAXY queda cerrado según petición del dueño.
