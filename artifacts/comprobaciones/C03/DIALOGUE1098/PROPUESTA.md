# DIALOGUE1098 — reparación propuesta, aún sin adoptar

Cuatro cambios coordinados de `llm.py` permiten pedir el referente o propósito ausente en la respuesta a una observación: prompt, comprobación de preguntas y orientación del reintento. También separan una avería al interpretar el turno de las actividades narradas por la persona cuando no se intentó ninguna operación. No añaden detector de fragmentos, respuestas visibles fijas ni presupuesto de generación.

Raíz leyó el diff, el diagnóstico y las restricciones existentes. La propuesta aún no está integrada ni medida. No demuestra que los cinco literales de fragmentos pasen, ni repara las otras familias de DIALOGUE1093: negativas breves, números o marcadores. La comparación de las variantes mostró rutas diferentes, no un fallo general de idioma.

Privado: `C:/Users/usuario/AppData/Local/BAXY/C03-dialogue1098-repair`. Patch SHA256 `f1472e57f427b7b1e13f6fc0ee7ffa0c541904e7bdb02fd22efaf573368021ac`; fuente propuesta SHA256 `1e27ffc265c2334fa6babbaad3524fa5edcb83493560af42d241f5faa2abf3c5`. Reanudar con integración revisada y panel sellado del mecanismo afectado. Sin pruebas por instrucción del dueño; no se afirma validación funcional.
