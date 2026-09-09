# Borrador del selector frente a conversación

Dos procesos nuevos con los mismos siete casos ya consumidos, catálogo y perfil registrado. Sólo el hook privado suprime initial_reply en el tratamiento. Baseline4/7 útiles; generación5/7. La fuente no se editó durante las dos corridas.

La prosa interna desaparece y el nombre inglés pasa de My name is Jordan a Your name is Jordan. La definición aún añade una inversión incorrecta sobre quién escucha al silenciar; no se aprueba. El recuerdo inglés sigue repitiendo Morgan, escrito por el asistente, por encima de Jordan, escrito por el usuario. Ese caso nunca tenía initial_reply: es otra frontera, no una regresión del tratamiento. Los demás controles se conservan.

22 peticiones HTTP frente a26: se añaden cuatro generaciones con identidad/política/idioma reales de conversación. En la definición, HTTP4 del tratamiento contiene esos tres sistemas y ninguna herramienta, con T0/seed0/max256. La latencia de ese turno pasa3,562→4,641s; nombre inglés1,797→2,063s. No se infiere una mejora de velocidad del total44,422→44,016s, dominado por otros pasos. RAM1768,617→1778,184MiB; GPU3497,559MiB ambos. Manifiesto intacto.

Se adopta retirar el transporte redundante de prosa desde el selector, sin sustituirlo por plantillas visibles ni un filtro de palabras. La generación existente sigue siendo dueña de la respuesta. Herencia: tests/test_turn_policy.py418–481 documentaban el ahorro y las guardas;505 conserva esos controles. Qwen documenta la selección con instrucciones y plantilla propias (https://qwen.readthedocs.io/en/stable/framework/function_call.html); esto no acredita su prosa interna como respuesta de BAXY. El hallazgo causal local es el salto del payload correcto mediante initial_reply. No se atribuye incapacidad general a ningún modelo.

506 retirará la ruta sin mantener parámetros/propagación muertos; pruebas dueñas y Fast antes de volver al producto. C03 sigue íntegramente activo; esta prueba no es UI, audio físico ni aceptación.
