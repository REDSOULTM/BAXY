# Sonda 716: observador dirigido al launcher

Se extrajo por AST el cuerpo literal de la prueba de caída del dispatcher, sin modificarlo ni ampliar sus 3 segundos. Venció el plazo sin saludo ni fallo forzado. El intento de pila apuntó al launcher del entorno virtual: py-spy no encontró la versión de Python. No proporciona una pila causal.

El proceso propio fue retirado y la búsqueda posterior por hash del script no encontró hijos restantes. El código 0 del conductor sólo indica que guardó su diagnóstico; la prueba temporal falló. No hubo cambio de fuente, adopción ni cobertura. La sonda 717 corrige exclusivamente la elección del intérprete observado después del plazo.
