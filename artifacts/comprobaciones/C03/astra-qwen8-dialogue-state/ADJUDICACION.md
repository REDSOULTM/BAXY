# C03 — estado real de conversación

21/21 publicados, 121.64s, 3651.57 MiB. NO aceptación: idioma, utilidad y
confirmación todavía incompletos. Cifrado ya entra explicit_conversation,
knowledge/mixed, cero operaciones y responde al concepto; no vuelve a backup.
El ? del saludo era la causa, no una mala clasificación semántica del modelo.

T5 sólo inglés y duplicado; t6 sólo español; t8 explica sólo en inglés; t9 usa
backup pero acaba con analogía torpe; t10 repite y exagera irse al espacio;
t15 sólo español ante Spanglish explícito. T13 y14 conservan explicación correcta,
t16 lista privada vacía verificada, t21 reloj correcto tras diálogo fallido.

T17/T19 producen plan app.close, pero faltan argumentos del predecesor:
window.resolve exige nombre de PROCESO, no nombre visible de aplicación.
La Calc existe (CalculatorApp PID8328, ventana en ApplicationFrameHost), pero
se pregunta por proceso. No hubo window.resolve ni app.close en el journal.
T18 cancela aclaración; T20 confirmar se interpreta package.install.commit y
pregunta por paquete. No hubo confirmación exacta ni cierre, no contar esa ruta.

No se tocó el registro ni main. Próximo contraste: misma misión incierta del
perfil noun-prose, con hechos estructurados ya probados (84 Python/81 .NET).
