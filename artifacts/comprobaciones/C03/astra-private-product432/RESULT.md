# 432 — aplicación aclarada en T3; recorrido 5/8 útil, aún incompleto

Fuente431, mismo desarrollo426 y nuevo perfil privado aislado. Ocho admisiones200
y ocho terminales publicados;5/8 útiles frente a4/8 en426. Sin composition_failed.
T3 llega a la aclaración existente por aplicación. T5 ahora pregunta por el PC,
todavía incorrectamente; T6 arrastra esa aclaración y pregunta permiso sin destino.
No se declara resuelta toda la secuencia de apertura. T7 conserva el error de sujeto.

49,344s; RAM2377,1484375MiB (2,32GiB), GPU3177,5625MiB (3,10GiB); sin violaciones,
exit0 y manifiesto intacto. Perfil425 de memoria sigue vigente; no reducción nueva
de pesos/contexto/precisión. No certifica mínimo global, UI ni audio físico conjunto.
Se conservaron todos los eventos, no sólo los terminales, en la captura privada.

- T1 | My name is Jordan. Remember my name.
  Jordan, I'm ready to enable your private local memory. Do you want to confirm this action or cancel it?
  Útil: Confirma habilitación exacta; previamente explica fallo por memoria deshabilitada. No guardar sin esa confirmación.

- T2 | confirm
  The memory has been saved successfully.
  Útil: Habilita y guarda el nombre autorizado; no basta esta frase para acreditar journal.

- T3 | Abre una aplicación.
  ¿Qué aplicación deseas abrir?
  Útil: Pregunta por la aplicación, sin inventar destino.

- T4 | What name have you saved in private memory?
  I saved the name Jordan in private memory.
  Útil: Recupera Jordan de memoria privada pese a aclaración pública pendiente.

- T5 | Me llamo Álvaro.
  ¿Qué necesitas exactamente con tu PC?
  Fallo: Pregunta qué necesita del PC en vez de responder a una presentación.

- T6 | Abre una aplicación.
  ¿Quieres que abra la aplicación que tienes en mente?
  Fallo: Pide permiso genérico en vez del nombre de aplicación; hereda aclaración T5.

- T7 | ¿Qué nombre tienes guardado en tu memoria privada?
  Mi nombre es Jordan.
  Fallo: El dato Jordan es correcto, pero «Mi nombre» atribuye el nombre a BAXY.

- T8 | ¿Cómo me llamo?
  Tu nombre es Álvaro.
  Útil: Nombre de la conversación Álvaro, distinto del persistido Jordan.

