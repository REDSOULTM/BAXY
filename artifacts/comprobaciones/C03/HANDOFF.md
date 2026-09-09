# Handoff C03 — fuente 641, diagnóstico hasta 645

## 643–645: causa contextual delimitada, sin promoción

641–642 publicadas en b20bff2472ede886a7edea4a947849328e574672, origin/Goal-c03 confirmado. 642 acredita 15/20, nueva lectura inglesa de cantidad; 3455 dueñas +121 subpruebas /0 skips y Fast exit0. Fuente registrada, main y modelo intactos. Encuesta 25/717/0.

643 demuestra que sustituir el texto actual por cuatro mensajes de contexto recupera dos candidatos ingleses pero pierde network.status en un cambio de tema. No se adopta. El control de ficheros se corrige explícitamente en ADJUDICATION.json: filesystem.list, puestos 7→10; el nombre file.list del resultado crudo era un error de anotación.

644 aísla la disponibilidad de window.application.status manteniendo historia y parámetros: 3/10→6/10 selecciones correctas. Corrige tres inglesas, no las españolas ni la prohibición. Es candidata introducida para diagnóstico, no recuperación implementada ni producto. 645 prueba sólo una regla general de contexto/lectura nueva con las mismas candidatas: 5/10→6/10; siguen los defectos españoles y de prohibición. El control inglés coherente varía entre corridas incluso con el mismo payload: no atribuir toda diferencia entre campañas a la regla. No se adopta ni se continúa ajustando frases de prompt sobre estos mismos fallos.

Siguiente trabajo: resolver la referencia de la petición antes de recuperar, conservando el texto original y la frontera de autorización. Reutilizar la lectura contextual existente; comprobar si basta una expansión acotada basada en peticiones del usuario, sin revivir acciones anteriores ni introducir estado paralelo. Aún no hay diseño o fuente adoptados. Leer `request_reading.py:622`, `__main__.py:535,5952` y `_previous_user_request`; evaluar cambios de tema, varios referentes y negación junto con nombres nuevos ES/EN. La pérdida posterior de argumentos en t18 y la clasificación inglesa `has` son defectos distintos. No cerrar por disponibilidad de candidata solamente.

643 no ejecutó modelo ni efectos. 644/645 sólo servidor, sin dispatch: GPU 3497,559 MiB; RAM 741,863/731,832 MiB; 31,437/41,281 s; sin infracciones y registro intacto. No sumar esos números a crédito de UI/voz. Full630 sigue siendo línea base histórica; faltan encuesta, rutas de prosa, UI real, loopback/AEC, recuperación y Full final. Ninguna decisión pendiente del dueño.
