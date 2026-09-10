# Modelo elegido para continuar C03

**Se elige Qwen3-4B-Instruct-2507 Q4_K_M, ya registrado en BAXY.** El dueño ordenó cerrar la selección al terminar792 y avanzar de inmediato con los bloqueantes de C03. La comparación792 terminó; no queda una decisión pendiente del dueño y no se abre otra campaña de modelos.

La decisión se apoya en la [referencia nativa699](K2_HORIZON_NATIVE699/REPORTE699.md): cada perfil recibió las mismas50 tareas sin instrucciones, herramientas ni schema de BAXY, con su plantilla y receta propias. En los perfiles prácticos, Qwen logró40/50 y K2 high38/50; sus medianas de respuesta completa fueron1,352s y8,828s, respectivamente. Los picos del árbol del servidor fueron3,09/3,36GiB de VRAM y0,70/0,77GiB de RAM. Una diferencia de dos aciertos en este conjunto dirigido no demuestra superioridad universal; la combinación de calidad medida, menor latencia y coste local favorece Qwen para avanzar ahora.

Los perfiles de referencia con más margen de salida también están documentados; los resultados pertenecen a los pesos cuantizados y backends medidos, sin equivalencia completa demostrada con el stack original del fabricante. La prueba737 mostró que el prompt de BAXY puede perjudicar respuestas de K2: esos fallos de integración no se usan para descartarlo ni como evidencia de capacidad nativa inferior.

Se mantiene el manifiesto registrado, SHA25613b971b3165cc84e8d8612289a4e11b3a28b908beaa69576bf566d20a183d1ed; pesos3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597. No se modifica el perfil al registrar esta elección. La optimización medida sigue dentro del objetivo de calidad, latencia y consumo, con el techo conjunto de4GiB pendiente de aceptación final del producto.

**Siguiente trabajo:** reparar los vetos que impiden entregar lecturas correctas, cubrir categorías completas de la encuesta y completar la validación restante de C03. Los revisores paralelos se limitan a causas y evidencia; la implementación y revisión final permanecen en el hilo principal. Nada de ampliar alcance ni corregir defectos que no bloqueen C03.
