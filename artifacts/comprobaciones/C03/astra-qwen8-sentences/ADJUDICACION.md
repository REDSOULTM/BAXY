# Contraste de longitud — desarrollo, no aceptación

Termina exit 0, 252.22 s, 3337.57 MiB VRAM, 6949.14 MiB RAM. Registro
Granite intacto. Mismo modelo, muestreo, corpus y presupuestos que purpose.

| Turno | Respuesta | Veredicto |
|---|---|---|
| 1, saludo EN | Hello! | Útil. |
| 2, doce por ocho | Noventa y seis. | Útil y correcto. |
| 3, fourteen times six | Eighty-four. | Útil y correcto. |
| 4, explicación mixed | composition_failed | Falla. |
| 5, spanglish explícito | composition_failed | Falla. |
| 6, capital de Perú | Lima. | Útil y correcto. |

4/6 útiles, igual que purpose. Mejora adicional fuera de esos seis: la
bienvenida inicial y la del reinicio se publican en español: «¡Hola! ¿En qué
puedo ayudarte?». No se suman a la aceptación ni se ocultan los dos fallos.

La suite ampliada detecta un problema al retirar el veto de una frase:
1254 pass, 1 skip, 101 subtests, 1 fail. Un recorte quitaba Dime de una orden
y sólo el filtro de longitud evitaba publicar el residuo. Se elimina ese
recorte después de esta corrida; no se reintroduce el veto global de estilo.

También se demuestra que el progreso omite el pedido original en sus tres
intentos. Se conserva posteriormente con el helper común de composición.
El test antiguo exigía esa omisión; ahora comprueba pedido como contexto y
estado in progress, sin resultado completed. Los controles de ausencia de
respuestas prescritas y de efectos inventados se conservan.
