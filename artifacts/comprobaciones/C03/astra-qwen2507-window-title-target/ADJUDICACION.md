# Desarrollo: reconocimiento de título — no aprobado

6/6 publicados; **2/6 útiles y fieles**, con terminología mejorable en t2.
Sesión60914 terminó0: 58,26s, GPU3497,56MiB, RAM4499,39MiB; registro intacto.
No aceptación, promoción ni Full. Fuente de esta corrida sellada en PREREG.json.

| Turno | Veredicto | Evidencia |
|---|---|---|
| t1 cierre por título | Falla | Ahora conserva app.close y pasa a plan, pero pide el nombre de proceso pese al título completo. No resuelve la ventana ni pide confirmar el cierre. |
| t2 cancelar | Pasa | «La clarificación fue cancelada.» Estado pendiente retirado, sin afirmar un cierre. Terminología poco natural; no prueba la cancelación de una acción preparada. |
| t3 repetir cierre | Falla | Mismo plan y pregunta innecesaria por proceso. |
| t4 confirmar | Falla | Sigue pidiendo proceso; aún no hay acción preparada que confirmar. |
| t5 hora EN | Pasa | It's 10:54, consistente con los hechos de composición. |
| t6 tareas EN | Falla | Misma negativa falsa de acceso; selección deriva de unsupported a aclaración de reminder.list. No task.list ejecutado. |

Fixture C03TitleFixture PID38428 seguía viva al recoger la captura.
El cambio de reconocimiento conserva el efecto final y elimina el veto demostrado,
pero **no resuelve todavía el caso visible**. No confundir eso con cierre por título.

Nueva causa trazada: extract_plan_arguments_batch conserva purpose/schema pero omite
la descripción canónica de la operación. byTitle sólo se explica allí. Además,
planner._value_is_grounded trataba byTitle como un encendido/apagado y exigía palabras
de activación, pudiendo retirar ese campo opcional. El siguiente contraste conserva
la descripción y valida el selector contra el tipo de identificación solicitado.
No cambio de modelo, sampler, umbral ni prosa fija.
