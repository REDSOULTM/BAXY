# Diagnóstico de composición nativa — desarrollo, no aceptación

12 preguntas × 2 brazos con la misma semilla por pregunta, Granite registrado,
temperature 1.0/top_p .95, sin thinking. `current` llama al compositor Python;
`direct` sólo pide respuesta breve con personalidad, idioma y tema, sin el
andamiaje de composición. No atraviesa el shell ni el catálogo; no aprueba C03.
Los payloads y todas las respuestas permanecen en results.jsonl.

No adoptar el prompt mínimo por esta prueba: **ambos fallan 12×8**, ambos
presentan la caché DNS principalmente como causa de demoras, y `direct` pide
contexto innecesario sobre router y llama criptográfico a todo checksum.
Hay mejoras locales de prosa (latencia/proxy), insuficientes para sustituir el
contrato. `current` acierta 17+26, 14×6, definición DNS/router y copia de seguridad;
su castellano incluye «cálculada» y concordancias defectuosas. Ambos convierten
la pregunta de cifrado en castellano: revisar también lectura de spanglish.

Siguiente hipótesis distinta: perfil nativo de razonamiento breve de Granite.
IBM documenta enable_thinking=True, low_effort=True; la ejecución actual fuerza
off y presupuesto cero en el servidor. Medir, sin cambiar el modelo registrado,
si el perfil nativo corrige contenido dentro de un presupuesto acotado.
Fuente primaria consultada el 2026-09-06:
https://huggingface.co/ibm-granite/granite-4.2-3b#thinking-modes
