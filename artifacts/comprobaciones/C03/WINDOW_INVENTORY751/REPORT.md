# Inventario de ventanas: selección y cantidades verificadas

La lectura global ya existía en el kernel, adoptada en748 y validada por Full7, pero Python sólo podía extraer títulos concretos y rechazaba muchas peticiones plurales. Esta reparación conecta las peticiones completas de inventario con `window.resolve`, usando `process="*"` y `byTitle=false`. Conserva límites explícitos entre1 y50, números escritos con palabras, preguntas de cantidad, cambios de orden y mezcla ES/EN. Un título, proceso, filtro, cita, negación u otra acción no se convierten en un inventario global por esta vía.

El validador de prosa distingue las ventanas devueltas en la página, la cantidad observada y el total conocido sólo cuando la enumeración es completa. Una página vacía no prueba un escritorio vacío. Se admiten tanto cantidades separadas como expresiones de subconjunto («dos de siete ventanas»); un total desconocido no se convierte en un número exacto. La narración recibe el contrato de lectura, conservando cualquier filtro de proceso o título. No se añade una respuesta visible fija ni una regla específica para un modelo.

Las143 nuevas pruebas ejercitan selección, argumentos, composición, paginación y el reintento de prosa con respuestas simuladas. Las pruebas que parametrizan Qwen/K2 verifican el mismo contrato del compositor; **no ejecutan esos modelos ni comparan su calidad**.

| Validación | Resultado |
|---|---|
| Primera corrida del nuevo conjunto | 135 pass / 4 fail; tópico inglés separado y determinante del inventario |
| Fallos reparados, sin cambiar sus expectativas | 4 pass / 135 deselected |
| Dueñas de ventanas, decisiones, preservación y planes | 4194 pass / 0 fail / 0 skips, más121 subtests;68,31s |
| Integridad y reparación750 | 108 pass / 1 skip ambiental;3,51s |
| Dueñas finales tras precisar el alcance del texto de contrato | 355 pass / 1 skip ambiental;3,97s |
| Fast inicial | exit0; Release18,18s,0advertencias/0errores |
| Fast final | exit0; Release1,47s,0advertencias/0errores |

Las corridas se solapan y no se suman como pruebas independientes. El skip de STT corresponde a entradas privadas ausentes de una campaña ciega. Comandos, secuencia y huellas están en `VALIDATION.json`. Los cambios de pins sólo actualizan programas vigentes; los resultados históricos V8 y los sellos de audio permanecen intactos.

La fuente final de ocho archivos queda fijada en `SOURCE_PINS.json`, y el árbol de407 archivos Python es `86dadf1b2b828862303f26908ca4f3d4c56315ab82aefe410dd549d2eab95111`. Se adopta en el commit que contiene `ADOPTION.json`. Este tramo cambia sólo Python: el objetivo vigente exige Full para adopciones compartidas C#/Python y para el cierre, no para cada edición Python.

No se han ejecutado nuevas inferencias, efectos, UI o voz. La encuesta sigue en26cubiertos/716abiertos/0no aplicables. Falta comprobar las reparaciones750–751 con la categoría real de73turnos del producto, además de los demás requisitos de C03. Persisten las dos formas de foco documentadas en738 y la continuidad de paginación de746; no se atribuye a esta reparación su cierre.
