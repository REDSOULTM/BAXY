# Corrección de alcance: el guardia antiguo no frena la ruta nativa

La inspección completa corrige la prioridad anunciada en734. En llm.py7356–7378, con native_tool_policy habilitado y catálogo no vacío, la selección nativa retorna antes del guardia semántico. El constructor lo habilita por defecto5184–5190. __main__.py2055–2078 usa también la selección nativa para revisar rechazos. Los fallos directos de733/734 existen, pero no acreditan un defecto alcanzado por esas rutas actuales.

Dos pruebas dueñas verifican explícitamente que el guardia no se llama para una lectura nativa correcta ni para conocimiento estable:2pass/0fail/0skip,1,12s. La selección adicional -k native_tool pasó4/0/0,1,32s y se conserva separada. No se ha reparado ni reinstalado la ruta antigua; cualquier necesidad restante debe demostrarse en ejecución.

Se prepara736: misma categoría completa73, mismo código/hook/adaptadores/DLL, perfiles prácticos699 propios, mismo contrato de serialización, runtime externo local y plazos del producto intactos. K2 primero y luego Qwen. Se registrarán propuestas, payloads efectivos, argumentos/verificadores/publicación y cualquier llamada real al guardia antiguo. No son nuevos modelos base: esa referencia ya existe699. No modificar fuente o adaptadores entre brazos.

Fast1 falló sólo por tres espacios de formato en inicializadores del test C# añadido730. Se separaron las propiedades en líneas; ninguna expectativa cambió. Fast2 en sesión64673. El Full5 continúa rojo por los dos timeouts originales; no adopción ni promoción. Encuesta26/716/0; C03 activo.
