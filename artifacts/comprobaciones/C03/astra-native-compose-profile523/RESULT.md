# Perfil documentado de Qwen2507 para el redactor

Se recogieron27 respuestas nativas: nueve payloads exactos521 con el perfil registrado y la receta documentada a semillas0/17. Las27 terminaron por EOS, sin cortes. El log de llama.cpp acredita9 llamadas a temperatura0 y18 a0,7/top_p0,8/top_k20/min_p0; no se presume aplicación sólo porque HTTP devolvió200.

Guardado y capacidad siguen fallando con los tres perfiles: el primero conserva prosa de metadatos y el segundo niega tener memoria local al verla desactivada. Progreso conserva la referencia al usuario y la ausencia de resultados. La aclaración admite variaciones válidas y la deshabilitación conserva la corrección520. No se adopta el perfil ni se inicia otro barrido de palabras o temperaturas.

RAM720,629MiB/GPU3497,559MiB10,921s sólo del servidor y descendientes, no de BAXY completo. Registro intacto, sin violaciones; driver99282exit0, servidor terminado deliberadamente al recoger todo. No son casos frescos ni prueba de UI/voz.

524 retoma Qwen3.5-4B porque437 usó el perfil determinista genérico y el código de composición anterior. Ahora se comparará con su receta oficial no pensante, conservando sus controles de nombre que entonces fallaron. La revisión usa backend compatibleb10865 y no modifica el registro. Es una comparación por candidato, no obligación de darle parámetros idénticos a Qwen2507.
