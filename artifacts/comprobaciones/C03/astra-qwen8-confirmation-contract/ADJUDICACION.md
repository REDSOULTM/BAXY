# Desarrollo: confirmation-contract (no aceptación)

20/21 publicados;78.19s;3651.57MiB GPU;5548.10MiB RAM;registro intacto.
C03WindowFixture PID27028 sigue abierta: no cierre ejecutado en esta captura.

| Turno | Respuesta | Adjudicación |
|---|---|---|
|t1|Son las 09:28.|Hora ES correcta.|
|t2|La hora local es 09:28. El audio está muteado con nivel de volumen al 100.|Hechos correctos, prosa técnica muteado/nivel100 sinunidad.|
|t3|It's 09:28.|Hora EN correcta.|
|t4|The local clock is 09:28. The volume is set to 100 and muted.|Hora/audio EN correctos, sinunidad volumen.|
|t5|It's 09:28. The clock shows 09:28.|Rechazado: sóloEN y repite hora.|
|t6|La hora local es 09:28. El audio está muteado con nivel de volumen 100.|Rechazado: sóloES al pedido mixto.|
|t7|Hey, ¿qué tal? Bien, ¿cómo estás?|Saludo pertinente redundante.|
|t8|Encryption is like a secret code that protects your information. When you send something, it turns into a code only the right person can read. It's like a lock that keeps your data safe from others.|Cifrado pertinente; sóloEN, rechazo mixed.|
|t9|Una copia de seguridad es como un duplicado de tus archivos o datos, en caso de que se pierdan o se dañen. Es como tener un segundo lugar donde guardar lo importante, por si algo pasa.|Definición correcta; sóloES, rechazo spanglish.|
|t10|Gravity es como una fuerza que nos mantiene pegados a la tierra, y que hace que los objetos caigan hacia el suelo. Es como si la tierra tuviera un "pulso" que atrae todo hacia su centro. Sin ella, todo flotaría y nos perderíamos en el espacio.|Rechazado: analogía pulso y flotación universal imprecisas.|
|t11|No abriré Paint.|Negación conservada.|
|t12|La capital de Perú es Lima.|Rechazado idioma: sóloES al pedidoEN. Lima correcto.|
|t13|Photosynthesis is how plants make their food using sunlight, water, and carbon dioxide. It also gives off oxygen, which is important for animals and humans to breathe.|Fotosíntesis pertinente en dos frasesEN.|
|t14|El hielo flota porque es menos denso que el agua líquida. Cuando el agua se congela, su estructura se expande, haciendo que su masa sea menos densa que el agua en estado líquido.|Densidad correcta, masa menos densa es impreciso.|
|t15|Un archivo es un documento o dato específico, como una foto, un documento o un video. Una carpeta es un contenedor que tiene archivos y otras carpetas dentro, como una carpeta de documentos.|Rechazado idioma: sóloES pese spanglish explícito.|
|t16|Tu lista de cosas por hacer incluye tareas que necesitas completar, como trabajar, estudiar, hacer compras o cuidar de alguien. Si quieres saber exactamente qué hay, dime cuál es el tema o el contexto.|Rechazado grave: inventa contenido de lista privada; no task.list.|
|t17|¿Quieres confirmar o cancelar la acción de cerrar la ventana del proceso C03WindowFixture?|Confirmación nombra acción y destino: mejora real.|
|t18|La ventana C03WindowFixture está maximizada y se ha cancelado la acción restante.|Cancelación sin parcial, pero agrega estado previo innecesario.|
|t19|composition_failed|Rechazado: composition_failed; sólo window.resolve, omite cierre pedido.|
|t20|¿Quieres confirmar algo?|Pregunta de aclaración: no había cierre pendiente tras t19. No certifica confirmación.|
|t21|It's 09:29.|Hora EN correcta.|

t17 confirma mejora de contenido con mismo modelo y petición. t19 NO es un nuevo
fallo del contrato de confirmación: raw decision seleccionó window.resolve como
acción única, la ejecutó, y las descripciones correctas de esa lectura fueron vetadas
missing_state porque el verificador seguía exigiendo el cierre pedido. No relajar
esto para dar por cumplida una lectura que omite la acción. Falta corregir selección.
t16 llegó a conversación y afirmó una lista que no había leído.
t12 read_request(pedido)=en y read_request(respuesta)=es; compose_visible_defect
ya lo rechaza wrong_language, pero respuesta directa no pasa por ese control.
Siguiente: contraste único Qwen2507 heredado en código actual, sin más wording.
