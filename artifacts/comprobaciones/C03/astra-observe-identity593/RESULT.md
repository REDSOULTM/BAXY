# Observación593: dos causas confirmadas, ninguna reparación aún

Los once turnos de identidad repiten exactamente592:8 finales correctos y3 fallidos. La observación delega sin modificar payloads ni respuestas; añade trazas de HTTP, retorno de la guarda y entrada de chat. No es una medición limpia de latencia.

H0012: el selector nativo conserva conocimiento, pero la guarda semántica devuelve `incomplete_effect/one`; su retorno real es `not_complete/one`. `apply_conversation_effect_presentation` convierte entonces la presentación en unsupported. El usuario no pidió un efecto. Falta distinguir una expresión conversacional ruidosa de una acción a la que le falte un argumento; no basta eliminar palabras iniciales por literal.

Las dos preguntas inglesas llegan a chat como knowledge y `response_language=en`. La historia se conserva con sus autores como datos, conforme a fuente512; tanto el borrador como su reintento JSON copian la respuesta española anterior. El reintento habla de respuesta vacía/eco aunque el defecto observado es idioma. No se elimina historia ni se relaja el veto de idioma sin una prueba comparativa.

Base Qwen2507/b9980, sin adaptador ni cambio de registro. GPU3499,559MiB/RAM2400,297MiB,64,469s de escenario con observación. Sin UI/voz. Encuesta16/726/0, sin nuevos requisitos acreditados. C03 sigue activo.
