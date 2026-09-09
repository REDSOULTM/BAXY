# 452 — interrumpido por límite de transporte del arnés

Dos respuestas de Qwen3.5 agotaron dos intentos de19s cada uno; sólo el control
inglés devolvió respuesta completa. begin_request120 no ampliaba el límite
por intento de _post. No atribuir esos cortes a calidad del modelo. Se detuvieron
los procesos propios verificados; no se ejecutó el resto de casos ni Gemma.

453 repetirá el diagnóstico previsto mediante una sola petición HTTP local
con timeout120s real, sin retry. No cambia límites del producto ni fuente436.
No hay medición final de picos por interrupción: no inventarla.
