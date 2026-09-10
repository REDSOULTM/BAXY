# Método y atribuciones de la comparación736

La puntuación dentro de BAXY mide el sistema completo. No demuestra por sí sola la capacidad del modelo: el catálogo ofrecido, los prompts, la plantilla, los límites de tiempo y los validadores pueden cambiar el resultado.

## Qué se comparó realmente

- **Modelo separado, 699:** seis perfiles sobre los mismos 50 casos; 300 respuestas, sin sistema, catálogo ni reglas de BAXY. Cada perfil conserva su configuración documentada. Qwen práctico obtuvo 40/50 y K2 high práctico 38/50. Esos resultados no acreditan el producto ni prueban una diferencia universal entre modelos. Véase [informe699](../K2_HORIZON_NATIVE699/REPORTE699.md).
- **Una transformación, 731:** otros 50 casos con K2, conservando el control699 y añadiendo únicamente `enable_thinking=False`. El resultado cayó de 38/50 a 19/50 (20 con el caso fronterizo). Esa configuración no se adopta. Véase [informe731](../K2_HORIZON_ADAPTER731/REPORT.md).
- **Producto, 736:** se registraron 73 peticiones por modelo, con perfiles prácticos nativos. K2 se cortó por RAM libre global tras50 finales; Qwen completó73. Código, scripts, panel y binarios App/Core coinciden. Se comparan los50 casos completados por ambos y se conservan23 pendientes de K2. No es una división de25 casos para uno y25 para otro. Tampoco permite calcular una caída de acierto contra699: los paneles de tareas son distintos.

El adaptador conserva los mensajes separados, el razonamiento high de K2 y su muestreo T1/p0,95; Qwen conserva su perfil propio. Ambos comparten la adaptación de serialización declarada. Se registran tanto la entrada de BAXY como la petición **efectiva** enviada al servidor: no deben confundirse. Los presupuestos de tiempo del producto siguen intactos.

## Hallazgos ya comprobados

**Una respuesta correcta puede ser rechazada por BAXY.** En H0104/t3, la lectura real identifica una ventana y confirma su foco. El modelo conserva ambos hechos, pero su frase que empieza por «Activa está…» se rechaza como `missing_fact`. El replay local muestra que cambiar sólo a «Está activa…» tampoco basta: el reconocimiento del sujeto también limita las formulaciones admitidas. Dos formulaciones alternativas con los mismos hechos sí pasan. La primera transformación dañina observada está en el validador de prosa. No se ha adoptado una reparación ni acreditado cobertura. Evidencia: [replay y hashes](k2/FOCUS_ATTRIBUTION.json); los textos y payloads completos permanecen en el directorio privado de736.

**La ausencia de final no equivale a una mala elección de herramienta.** En H0023, H0103 y disk-used-es, el modelo recibió y seleccionó la operación pertinente. El replay del veto de dominio reproduce las tres conversiones de acción válida a conversación sin operaciones. Ese filtro léxico es la primera pérdida semántica demostrada; el timeout posterior de `conversation_reply` sucede cuando la propuesta ya fue retirada. La auditoría del fallo no guardó los estados intermedios, por lo que se contrastó con fuente y reproducción local. Evidencia y límites del replay: [DOMAIN_ATTRIBUTION.json](k2/DOMAIN_ATTRIBUTION.json).

**También hay defectos que ya llegan desde el servidor.** En H0207/t10 y H0384/t11, un cierre literal `</ifm|think>` aparece en `message.content` de la respuesta HTTP y llega intacto al texto publicado. La composición no lo insertó. No aparece en las 50 respuestas nativas del perfil K2 high práctico699. Esa diferencia no demuestra por sí sola si la causa es generación, prompt o parser. La petición efectiva de736 usa T1/max4096/high; los valores T0/max256/thinkingFalse del log de entrada fueron sustituidos por el adaptador.

**Los plazos también forman parte de la integración.** Muchas llamadas de prosa tienen unos cuatro segundos efectivos; las reparaciones reciben el remanente. Se registra timeout por separado de respuesta semánticamente incorrecta. No se amplían plazos durante la comparación.

## Límites y siguiente paso

Las dos ejecuciones terminaron: K2 con corte de protección, Qwen sin corte. No se cambiaron fuentes ni adaptadores entre brazos. Los hechos del PC se juzgaron contra la lectura fresca de cada petición, no contra valores de una ejecución anterior. El resultado y los límites están en REPORT.md; no se presenta la categoría de K2 como completa.

El observador adicional de RAM mide servidor y árbol real de BAXY, excluyendo compiladores. En ambos modelos empezó con la App ya activa: no acredita el arranque. RAM residente y memoria privada comprometida son magnitudes distintas. Ninguna de estas pruebas sin ventana visible acredita interfaz, voz física o todo el presupuesto conjunto del producto. Tras el corte de K2 se liberó memoria global; Qwen arrancó con más RAM disponible.

La ruta nativa de selección salta el guardia semántico antiguo, pero existen otros puntos de entrada: en H0359 el selector devolvió conversación y una cifra de batería sin solicitar lectura. Después de terminar `decide_turn`, la presentación conversacional de `__main__.py` volvió a llamar al guardia. Este agotó el tiempo sin devolver clasificación. Aquí ya existe un fallo previo de la propuesta nativa; el guardia no es quien la convirtió inicialmente en conversación. No se generalizan los probes aislados733/734 a todas las peticiones.

C03 sigue abierto. Fast735 pasó; Full5 conserva dos fallos en sus plazos originales. Encuesta: 26 cubiertos, 716 abiertos, 0 no aplicables. Esta comparación no añade cobertura ni promueve un modelo.
