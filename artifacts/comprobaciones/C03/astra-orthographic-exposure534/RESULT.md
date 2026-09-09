# Auditoría de frescura: diferencias de escritura

Las auditorías532/533 no encontraron nuevas coincidencias con su normalización anterior:532 revisó3041fuentes de código, pruebas y paneles;533 revisó408logs privados con10998filas, todos estables y sin líneas malformadas.

534 añade una exclusión conservadora: comparar palabras en el mismo orden después de quitar diferencias de mayúsculas, tildes y puntuación. Una pregunta sin signos o una orden con otra tilde no se convierte por ello en un caso nuevo. Se reutilizaron las rutas exactas de532/533 y los tres corpus heredados de518;3452fuentes estables y0errores de lectura/parsing.

De los112no coincidentes anteriores,43tienen coincidencias de esta clase. Quedan69candidatos,66con original completo:63españoles,1inglés y2entradas sin idioma determinado. Todavía deben revisarse duplicados, contexto y alcance de las ocho rutas. No se ejecutó BAXY, no hay reserva congelada ni certificación de frescura por un simple no-match. Persisten los límites de extracción y revisión semántica declarados.

Se consultó al dueño porque el único saludo humano del grupo también está consumido: o bien acreditar la bienvenida automática al arrancar en las sesiones de reserva, o incorporar saludos nuevos escritos por él. Su objetivo actualizado exige esta consulta ante material insuficiente para una exigencia. No se suplió la carencia con traducciones o plantillas.

Detalle y hashes en RESULT.json; textos y coincidencias permanecen privados. Un error de sintaxis del instrumento previo a la ejecución se conserva en PREFLIGHT_FAILURE.txt; se corrigió antes de abrir fuentes.
