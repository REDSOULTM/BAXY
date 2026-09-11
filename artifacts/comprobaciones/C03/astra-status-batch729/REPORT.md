# Resultado del diagnóstico729

Se revisaron los mismos73 casos de689/704: **49 respuestas correctas y24 fallos**. El conductor terminó exit0, pero eso no acredita calidad. Fuente705+712 sigue sin adoptar y Full5 sigue rojo. La encuesta permanece26cubiertos/716abiertos/0NA; esta tanda no añade cobertura por pertenencia a una familia.

El observador corrigió únicamente el destino del log tras invalidar728. Antes de arrancar se verificaron la carpeta real, escritura y cuatro llamadas stub aisladas: mismos argumentos, misma identidad del resultado y de la excepción.729 conservó224 pares HTTP petición/respuesta y22 pares entrada/salida de decide_turn, sin errores del observador. Modelo, backend, perfiles,73entradas/orden y criterios no cambiaron.

Los24 fallos se agrupan en5 lecturas globales de ventanas sin capacidad tipada,1 fallo de composición del foco,3 respuestas sin nueva lectura,3 etiquetas de RAM que confunden capacidad utilizable con disponible,7 lecturas existentes no seleccionadas,3 errores de alcance de red y2 rankings de CPU basados en métrica o miembros incorrectos. Son categorías diagnósticas, no atribuciones automáticas al modelo.

Hay un ejemplo de separación de etapas: para H0023 el límite decide_turn devuelve window.resolve; domain_grounding lo convierte en conversación y luego se solicita aclaración. Sin embargo, la operación actual exige un proceso/título y no puede enumerar todas las ventanas. Quitar el veto no aporta la capacidad que falta. El próximo cambio sigue el contrato de inventario708 antes de volver a medir la selección.

La confusión de RAM sí aparece ya en el borrador:16.54GB total utilizable se publica como disponible aunque la lectura distingue aproximadamente1.5GB libres y17.18GB instalados. En otros casos la propuesta sale como conocimiento y se pierde la lectura fresca. La traza decide_turn ya incluye adaptación de BAXY: para culpar al LLM crudo habría que retroceder al payload y respuesta HTTP correspondientes.

Recursos máximos del árbol del diagnóstico: **3499.56MiB GPU y2468.57MiB RAM**,327.39s, sin violaciones del límite. No incluye aceptación de UI/voz física ni demuestra consumo conjunto final. La referencia704 registró50correctos/23fallos,3499.56MiB GPU,2444.07MiB RAM y272.69s; un solo par con estado del PC variable no establece causalidad ni mejora de rendimiento.

`RESULT.json` contiene el veredicto individual y hashes. Entradas/respuestas literales, criterios y razones están en el informe privado LOCALAPPDATA/BAXY/C03-status-batch729-private/REPORT.md; review.json conserva payloads/borradores por turno. Logs originales728 se preservan como diagnóstico inválido, sin mezclarlos con729.
