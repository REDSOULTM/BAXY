# Presupuesto previo a clasificar — desarrollo

Termina exit 0, 217.11 s; 3337.57 MiB VRAM y 6471.14 MiB RAM; registro
Granite intacto. Los turnos 1, 2, 3 y 6 responden correctamente (Hello!,
96, 84, Lima). T4 queda filtered sin texto, rechazo empty_or_too_long y
recuperación agotada; T5 composition_failed. 4/6 útiles, no aceptación.

Se retira la composición síncrona previa, pero no basta: el perfil 8B
parcial en CPU sigue agotando composiciones de cuatro segundos. No promover
ni seguir ajustando prompts sobre estos seis controles. La retirada evita
una dependencia innecesaria probada por sus tests; no acredita por sí sola
las garantías temporales de C07. Próxima hipótesis: checkpoint 4B heredado,
identificado por R82, sin cambiar plazos ni descargar otro archivo.
