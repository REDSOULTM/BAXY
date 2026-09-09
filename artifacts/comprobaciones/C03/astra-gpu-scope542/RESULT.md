# C03 — alcance GPU y RAM542

Se adopta la distinción compartida entre memoria de video y RAM. La consulta inglesa de GPU de541 ya no cuenta como dos alcances incompatibles; una petición que añade RAM explícitamente sí conserva ambos. Seis variantes ES/EN y tres controles mixtos amplían la prueba dueña; ocho fallaban antes de editar, junto a43pass.

Validación: `test_system_status_scope_grounding.py test_machine_status_scope.py test_effect_intent.py`:1917pass/0skip,45,50s. `test_turn_policy.py test_generalization_product_r6_development.py test_stt_quality_evaluators.py`:1628pass/1skip ambiental,8,63s. El skip es la campaña ciega STT sin sus archivos, no una aceptación de voz. Fast verde completo; Release19,55s,0warnings/0errors. No cambio C#; no procede repetir Full por esta edición. Full final sigue pendiente.

Sólo cambia effect_intent.py y sus pruebas, más las dos declaraciones del árbol de programa actual para STT. Hash actual69586e40ec78f1ac4b183575f110f36371633b02b17d3bc52516a92cf4952086,403archivos; sellos de campañas históricas intactos. Sin cambios de modelo, runtime o prosa prefabricada.

Límite: reparación de alcance, no certificación del resultado final. La prosa española de541 confundió6287261696bytes dedicados con8GB; ese fallo es independiente y sigue abierto. También siguen memoria desactivada/capacidad, metadatos de guardado, discos plurales, curiosidades no verificadas y distinción de núcleos lógicos. Producto siguiente: comprobar los argumentos y hechos GPU reales con la fuente nueva antes de tocar su presentación.

Encuesta:3cubiertos/739abiertos/0no aplicables, sóloH0002/H0016/H0021 acreditados con casos y variantes reales541. La corrida541 conservó25finales de44; se cortó correctamente por RAM libre del sistema inferior a768MiB. GPU3499,559MiB/RAM2430,715MiB, sin UI/voz. No se atribuye aceptación a las19entradas no ejecutadas.
