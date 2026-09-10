# Comparación 737: efecto del prompt de redacción sobre K2

La pregunta es si la redacción que BAXY pide al modelo mejora o deteriora su
respuesta a hechos ya observados. Esta comparación permite atribuir cambios al
componente completo de mensajes del redactor. No identifica por sí sola qué
frase del prompt los provoca, ni evalúa las demás capas de BAXY.

Se toman los 57 casos de la campaña Qwen736 que tuvieron una observación tipada
reciente y una primera redacción capturada. Se incluyen tanto aciertos como
fallos. Los otros 16 casos carecían de esa observación y no entran en este
experimento. Esa selección limita las conclusiones a la redacción con hechos
disponibles; no representa las ocho rutas de C03.

Cada caso se ejecuta dos veces sobre el mismo K2:

- `native_high`: pregunta original y JSON de hechos, en un mensaje de usuario.
- `baxy_prompt_high`: mensajes exactos del redactor de BAXY capturados en736,
  incluida la misma pregunta y el mismo objeto de hechos.

Se alterna el orden por caso. Ambos brazos conservan pesos Q4_K_M, ejecutable,
bibliotecas CUDA, plantilla nativa, esfuerzo alto, temperatura1, top_p0,95,
top_k0, seed0, contexto8192, máximo32768 de salida y streaming. El caché de
peticiones está desactivado. No ejecutan selector, kernel, provider ni validador
de prosa. El preflight comprobó las114 plantillas con prefijo de razonamiento
alto y un máximo de1232 tokens de entrada.

IFM recomienda razonamiento alto, temperatura1, top_p0,95 y un presupuesto de
salida de al menos32768 tokens. Los modos medio y bajo son intercambios de
precisión por velocidad, no su receta recomendada de evaluación.
[Documentación oficial de IFM](https://huggingface.co/IFM/K2-Horizon-3.7B#best-practices).
El contexto8192, la cuantización Q4 y este backend local son desviaciones
prácticas respecto de la referencia BF16/SGLang. El ensayo no demuestra paridad
numérica con ella ni un máximo de32768 tokens utilizables sin cambios de contexto.

La adjudicación inspecciona toda la respuesta final contra la pregunta y los
hechos suministrados. Dar primero una cifra correcta no compensa una afirmación
falsa añadida después. La longitud por sí sola no cuenta como fallo. Se separan:

- `P`: respuesta fiel y útil para la pregunta.
- `F`: afirmación incorrecta o sin respaldo, o idioma inservible.
- `I`: los hechos suministrados no establecen el alcance pedido. No se atribuye
  exclusivamente al modelo la carencia del provider o del payload.
- `E`: error de entrega o salida incompleta. No es un fallo semántico adjudicado.

La categoría `I` identifica una carencia anterior a la redacción. Puede coexistir
con errores adicionales del texto: se detallan en la razón por caso y no se
perdonan por pertenecer a esa categoría. Por ejemplo, un ranking de segundos
acumulados no mide CPU actual, y alterar además una cifra sigue siendo un error.

Se informa la calidad de la respuesta completa y, aparte, si una respuesta
correcta se completó antes de4 segundos. Es una referencia diagnóstica por
streaming: los plazos del producto no cambian y su aceptación requiere volver a
la ruta real sin streaming. El límite offline120 segundos se comprueba al
recibir líneas SSE y con timeout de socket; no es un límite estricto de reloj.
Si falta `usage` tras un error, el contexto es desconocido aunque el campo
original `context_shift_possible` indique false.

Una sola ejecución por brazo/caso con temperatura1 permite observar diferencias
en estos casos; no cuantifica la variabilidad entre semillas ni demuestra que
un prompt mejore siempre. Los resultados no promueven modelo, no adoptan fuente
y no añaden cobertura de encuesta, UI, voz ni presupuesto conjunto del producto.

Las preguntas, respuestas completas, razonamiento, mensajes HTTP y hechos
permanecen locales en `%LOCALAPPDATA%/BAXY/C03-facts-prompt737-private/`.
El informe público usa identificadores y adjudicaciones. Los hashes permiten
vincular cada conclusión con esos registros sin publicar contenido privado.
