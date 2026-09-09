# 429 — conversación recupera4/4 saludos; fuente aún no adoptada

Baseline428status igualado offline/live. Misma información; sólo se usa el
evento/intención de conversación existente en lugar de estado de tarea.
2/4→4/4útiles: ES saluda usando el nombre humano; EN «Nice to meet you» con nombre.
No cuentaWindows, cambio de nombre de BAXY ni persistencia afirmada.
7,984s,GPU3173,56MiB/RAM1100,05MiB,sinviolaciones,manifiesto intacto.
No prueba el dispatch de producto ni los límites de reconocimiento del mensaje.

La posible reutilización de DeclaredNameInputPattern necesita cautela: su valor
admite cualquier secuencia de letras/espacios, no demuestra que un nombre
seguido de una orden sin puntuación sea una sola declaración. No se adopta un
atajo de C# que pueda tragarse una petición añadida. Ninguna fuente nueva.

Antes de añadir gramática,430 contrasta el identificador nativo de la operación:
baxy_system__identity frente baxy_system__windows_account. Sólo cambia el nombre
en el esquema tools, conservando la operación canónica/descripcion/contrato y
payload restante. El formato ya usa un mapa reversible entre identificadores
de función y catálogo. No hay propuesta de renombrar kernel/journal ni añadir
operaciones. Si no mejora sin regresiones, descartar; no cadena de alias.
Primaria b9980/docs/function-calling.md confirma el mecanismo de nombres y
tools; efecto semántico es hipótesis local. Fuente410 ya aclaró descripción y
mejoró recuperación, pero426/427 muestran que aún se confunde persona/cuenta.
Esta prueba mide ese dato nuevo, no repite el texto del catálogo.

- baseline | Me llamo Álvaro. | Hola Álvaro, estoy listo para ayudarte.

- conversation | Me llamo Álvaro. | Hola Álvaro, ¿en qué puedo ayudarte hoy?

- baseline | My name is Nina. | Nina, I have completed the session context.

- conversation | My name is Nina. | Nice to meet you, Nina.

- baseline | Mi nombre es Ana María. | Hola Ana María, gusto en conocerte.

- conversation | Mi nombre es Ana María. | Hola Ana María, ¿en qué puedo ayudarte hoy?

- baseline | My name is Jean-Luc. | Jean-Luc, the session context has been completed.

- conversation | My name is Jean-Luc. | Nice to meet you, Jean-Luc.
