# Continuidad del inventario de ventanas — C03 / 746

Revisión de contratos durante Full7, sin editar fuente ni ejecutar misiones. El contrato C# de la fuente730 sigue idéntico: las cuatro huellas comprobadas están en `PINS.json`. Sus pruebas dueñas dieron 41 passes de provider, 37 de catálogo y 5 de Core; son controles de contrato y enumeración controlada, no aceptación de prosa ni de una misión de usuario.

`window.resolve` admite process="*" con byTitle=false para inventario global. limit va de 1 a 50 (por defecto 20); offset empieza en 0. La respuesta distingue el tamaño de la página (`count`), las ventanas observadas (`observedCount`) y un total sólo conocido si `complete=true`. `complete=false` conserva `totalCount=null`. `nextOffset` recorre únicamente lo observado.

Cada petición enumera de nuevo. Dos páginas sucesivas pueden proceder de estados distintos del escritorio; no forman una instantánea estable. La visibilidad del estilo Windows no demuestra que una ventana esté descubierta en pantalla. Los identificadores son efímeros: una acción posterior requiere elección, identidad y verificación propias. Core sólo publica éxito de esta lectura si el provider devuelve Succeeded y Verified; eso no sustituye las pruebas contra un provider defectuoso de C04.

Reanudación C03: conectar la interpretación del inventario global con el selector tipado y conservar estas cantidades/límites en la prosa, tanto en español como inglés y mezcla. El campo `count` de una página no debe convertirse en el total del escritorio. No atribuir procesos en segundo plano ni afirmar que las páginas son estables. No añadir caché o sesión de instantánea a esta reparación.

Reanudación C04 (G05.01): verificar sobre ventanas reales lectura, selección de un identificador y ejecución posterior, incluyendo desaparición/cambio de identidad entre lectura y acción. La fila conserva PENDIENTE.

Reanudación C05 (G07.01): comprobar que un plan con más de una lectura no concatena páginas cambiantes como inventario exhaustivo o como autoridad duradera para actuar. Cada paso mantiene su verificación. La fila conserva PENDIENTE. No se ejecutaron C04 ni C05.

Publicación C03: G04.06 y G06.06 vuelven a PENDIENTE mientras existen cambios propios candidatos sin publicar y Full7 continúa. Las publicaciones anteriores permanecen como evidencia histórica, pero no demuestran el estado actual. No se modifica el estado de filas ajenas. Encuesta: 26 cubiertos, 716 abiertos y 0 no aplicables; C03 sigue EN_CURSO.
