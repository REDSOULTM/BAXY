# 326 — una pregunta conversacional no es una oferta de operación

Producto325 conservó el historial y chat66 respondió ambas identidades con el
nombre humano. UserMessagePolicy lo descartó como unsolicited_catalog sólo por
«¿Quieres que lo confirmemos juntos?». Fallback67 perdió el nombre y publicó el
mismo texto genérico que322. La mejora interna324 no mejoró el resultado visible:
producto325 sigue 1/6 útil, dos silencios.

Causa: LooksLikeCatalogProposal equipara «quieres que»/«want me to» a una oferta
de operación, sin exigir que nombre una. Además compara familias contra toda la
respuesta: una explicación previa de Steam o ventanas contamina el seguimiento.

Cambio acotado propuesto: comparar las familias existentes con la cláusula de la
propuesta y exigir un objeto operativo o un verbo de acción reconocible. Completar las familias ya
ejercitadas por pruebas históricas de estado del sistema/red y aplicaciones;
no añadir una excepción para Emmanuel, identidad o «confirmemos juntos».
No cambia autoridad, selección, ejecución, modelo ni prompts.

Controles antes/después: cinco seguimientos conversacionales ES/EN, cinco ofertas
de operación reales y respuesta literal humana325 en el validador completo.
Después owners de presentación/integración, Fast y secuencia humana completa.
No confundir 156 pruebas verdes324 con calidad integral ni cambiar el criterio1/6.

El primer owners326 terminó 127 pass, 1 fail, 0 skips (4 m 3 s). El control
«¿Qué quieres que cierra?» todavía debe detectar una propuesta operativa aunque
omita el objeto. Se reutiliza el reconocedor de verbos existente para ese caso;
no se cambia ni debilita el control. Validación final focal de las dos clases
dueñas de presentación; MindShellEndToEndTests pasó en ese primer conjunto.
