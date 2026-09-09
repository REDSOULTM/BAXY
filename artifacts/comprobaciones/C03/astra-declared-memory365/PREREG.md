# 365 — dato declarado y autorización de guardado en un solo turno

Producto364 demuestra que My name is Jordan. Remember my name. no inicia memoria
y responde una promesa sin guardado; Me llamo Álvaro y quiero que guardes mi
nombre acaba como una pregunta sobre nota privada. El journal sólo registra
memory.status y dos recall fallidos por memoria deshabilitada: no hubo save/enable.
No arreglar primero un recordatorio de confirmación que nunca llegó a existir.

Primero comprobar NaturalMemoryRequestParser y MissionInputPipeline. Ya existen
MissingNameSavePattern, DeclaredNameInputPattern, TryBindSaveInput y Save tipado
con protector privado. Heredar estas piezas para unir declaración y solicitud
explícita sobre el mismo dato, conservando orden, valor, idioma y negaciones.
No deducir permiso de un nombre solo, una hipótesis, dato de un tercero o pregunta.
No convertir el nombre en una nota pública ni añadir nombres particulares.

Comparación de mecanismo: Carter_v2 LLM_CONTEXT_MEMORY_REPORT R1/R2 separa nombre
de usuario, fuente y autorización.344/354/363 ya transportan el dato real con
privacidad y confirmación; no otro prompt del redactor para reparar un pedido
que la ruta privada omite. Mantener límites/secretos/autoridad exacta y verificar
en casos positivos/negativos antes de producto con modelo/payload sin cambios.

Baseline365:5fail6pass0skip582ms. Cuatro pedidos no producen ruta de nombre;
el orden inverso produce un historical_fact genérico en vez del selectorname.
La primera edición permite nombres compuestos, pero el control de continuación
detecta que Lina y abre Steam podría entrar como valor. Se conserva ese rojo:
focal.log1fail28pass. Se exige que el valor capturado del nombre no contenga otra
frontera de cláusula; no se persiste una instrucción como parte del nombre.

T5silencioso y T10 que niega conocer el nombre por memoria deshabilitada son
otros bloqueos364: distinguir conversación reciente de persistencia. Preservar
esa evidencia y resolverla después de la primera interpretación perdida.
