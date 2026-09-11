# Candidato 705: conservar los nombres que Windows observó

La App y la mente rechazaban títulos verificados por contener palabras de su vocabulario interno. La corrección distingue el segmento exacto del nombre de la prosa que lo rodea. No cambia la respuesta del modelo, sus instrucciones ni sus parámetros.

El permiso procede del resultado de una operación de ventana con `verified` y `succeeded` verdaderos. Los pasos de misión conservan sus propios resultados. Un título escrito en otro campo, un dato del historial o una observación sin verificar no concede ese permiso. Las comprobaciones de hechos, foco, identidad solicitada y límite de longitud conservan el texto original.

Las pruebas cubren títulos con palabras técnicas y nombres de archivo, español, inglés y mezcla, comillas y nombres sin comillas, variaciones de prefijo/sufijo, jerga añadida fuera del nombre, foco invertido, procedencia inválida y pasos de misión. Un nombre observado en minúscula tampoco se convierte en un error de capitalización; la prosa restante conserva esa comprobación.

La revisión encontró que el primer patrón podía ocultar parte de un nombre compuesto con punto o guion. El límite ya está corregido y conserva la puntuación de fin de frase. **706 pruebas Python pasan, cero skips**. En App, la selección ampliada tuvo 188 aciertos y dos fallos: una expectativa de prueba que excedía la política existente y un caso de memoria sin entrada en la cola. Los 37 controles finales pasan, incluido ese caso de memoria y el control corregido que comprueba por separado el identificador completo y el veto existente. Hay pruebas repetidas entre ejecuciones; sus cantidades no se suman como casos únicos.

El primer Full falló en formato antes de suites. El segundo se interrumpió al demostrar el defecto del límite y observar tres fallos de arranque. Esos tres pasaron en la ejecución enfocada, pero eso no identifica su causa. El tercero se inició por error después de fallar el registro de huellas y fue detenido antes de suites. El **cuarto Full está en curso sobre CANDIDATE4**, con todas las huellas comprobadas antes del arranque. No se ha cambiado ningún timeout, omitido una prueba ni dado un Full incompleto por aprobado.

El replay técnico recupera **un borrador nativo correcto**, repetido doce veces en la evidencia de 694, sin editarlo. La otra formulación de 694 y la formulación con «ventanal» de 704 siguen rechazadas por la gramática de identidad. El replay de la revisión final conserva exactamente esos resultados. No se presentan las repeticiones como pruebas independientes ni se atribuye al modelo el falso veto del producto.

La fuente sigue **sin adoptar**. La regresión completa de 73 turnos está preparada como producto 706 y no se ha ejecutado. La encuesta permanece en **26 requisitos cubiertos, 716 abiertos y 0 no aplicables**. Siguen pendientes los demás bloqueos y la aceptación íntegra de C03.
