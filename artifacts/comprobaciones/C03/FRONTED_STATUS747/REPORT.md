# Tópico antepuesto y lectura de estado — sonda 747

Se probaron 70 controles sintéticos de dominio: 50 pedidos de estado con el tema antepuesto y 20 límites de negación, pasado, otro dispositivo, contenido citado, explicación y acciones distintas. Se llamó sólo a funciones puras de la fuente actual; no hubo inferencia, operaciones del PC, edición de fuente ni cobertura de encuesta. Full7 siguió sobre sus mismos archivos.

La propuesta aislada conserva una propuesta nativa `system.status` si un tópico completo de alcance conocido precede a una petición explícita de observación actual. Reutiliza el vocabulario de alcances y las exclusiones existentes; no transforma el texto que recibe el modelo ni amplía el reconocedor determinista.

Resultado: **23 → 57 de 70 controles correctos**, con **34 ganancias, 0 regresiones, 13 falsos rechazos y 0 dominios incorrectos**. La propuesta **no se adopta**: no cumple el panel completo y no prueba argumentos, ejecución, prosa o producto. Esta única sonda no es una comparación de modelos.

Los 13 rechazos restantes se atribuyeron por puerta, con solapamiento:

- Cinco contienen `comprueba`: `_is_direct_request` lo reconoce, pero la lista separada `_MACHINE_STATUS_HEAD` no lo incluye.
- Seis contienen `tell me how much`: la detección de petición de explicación busca `tell me how` en cualquier posición, mientras la excepción de lectura actual sólo lo permite al principio del turno. El tópico bloquea esa excepción. `_is_explicit_meta_or_tool_denial`, effect_intent.py:6368–6402.
- Cuatro contienen `respecto a CPU/GPU` o `en cuanto a CPU/GPU`: la regla de hardware ajeno confunde esa preposición española con el artículo inglés de `a CPU`/`a GPU`. El fragmento exacto observado está en ARTICLE_COLLISION.json; `_is_machine_knowledge_or_diagnosis`, effect_intent.py:4715–4808.

La lectura de cláusulas también separa el tópico de la directiva. Reparar únicamente el voto de dominio no garantiza que la autoridad, la resolución y los argumentos preserven ese mismo alcance. No convertir un tópico semántico en una envoltura de cortesía ni quitar las guardas de todas las lecturas.

Siguiente reparación: dar una interpretación estructural común al tópico y su petición, reutilizando el alcance reconocido y manteniendo el texto original como evidencia; comprobar las puertas de meta/alcance/cabecera juntas. Preservar los negativos de tests/test_effect_intent.py:1737–1776,4205–4264 y el control de salud genérica de tests/test_price_v8_veto_damage_by_cause.py:133–151. Las variantes con unidad distinta de la del sistema no obtienen capacidad nueva: el catálogo de `system.status` no incorpora un selector de letra de unidad en esta propuesta.

PREREG.json conserva los 70 textos y el código exacto de la propuesta antes de ejecutarla; RESULT.json conserva cada resultado y las cláusulas originales. FAILURE_CAUSES.json y ARTICLE_COLLISION.json sólo atribuyen fallos ya observados. Encuesta:26 cubiertos,716 abiertos,0 no aplicables. C03 continúa en curso.
