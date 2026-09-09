# 428 — estado session_context_only: sólo2/4útiles, no adoptar

Baseline426T5 igualado offline y live. Cuatro nombres, misma composición/modelo.
Sustituir hechos de cuentaWindows por status/session_context_only recupera los
dos saludos ES, pero en EN dice «I have completed the session context» o «the
session context has been completed»: no es una respuesta natural/veraz al acto.
Baseline0/4útiles (3vacíos y1lecturaWindows no pedida); variante2/4. No fuente.
10,781s,GPU3173,56MiB/RAM1101,96MiB,sinviolaciones,manifiesto intacto.

El estado success/status representa una tarea completada, no el acto de
presentarse.429 compara ese mismo estado con el evento de conversación ya
existente, sin causa de tarea: TurnVisibleFacts.Event("conversation") y su
intención conversation. No nuevo prompt ni plantilla ni datos de nombre añadidos.
Cambio conceptual único: el recorrido de composición acorde al acto conversacional.
Mantener la propuesta de parser sólo como hipótesis hasta que prosa y límites pasen.
Datos privados originales intactos. Modelos cerrados; C03 sigue abierto.

- baseline | Me llamo Álvaro. | [vacío]

- session-context | Me llamo Álvaro. | Hola Álvaro, estoy listo para ayudarte.

- baseline | My name is Nina. | [vacío]

- session-context | My name is Nina. | Nina, I have completed the session context.

- baseline | Mi nombre es Ana María. | [vacío]

- session-context | Mi nombre es Ana María. | Hola Ana María, gusto en conocerte.

- baseline | My name is Jean-Luc. | [saludo seguido de cuenta Windows no solicitada; literal conservado en registro privado]

- session-context | My name is Jean-Luc. | Jean-Luc, the session context has been completed.
