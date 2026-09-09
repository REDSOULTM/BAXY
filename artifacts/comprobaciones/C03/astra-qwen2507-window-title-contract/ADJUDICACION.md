# Desarrollo: contrato de argumentos por título — no aprobado

6/6 publicados; **2/6 útiles y fieles**, mismo resultado visible que title-target.
Sesión49000 terminó0:71,28s,GPU3499,56MiB,RAM4850,39MiB;registro intacto.
No mejora visible por conservar descripción y selector. No repetir esta estrategia
con otra redacción del prompt ni interpretar tests verdes como éxito de la conducta.

| Turno | Veredicto | Motivo |
|---|---|---|
| t1 | Falla | Pide el proceso aunque tiene título. Batch propone process="null",byTitle=true,limit1. El texto null no está en el pedido y se rechaza correctamente. |
| t2 | Pasa | Cancela aclaración, sin afirmar cierre. Terminología poco natural. |
| t3 | Falla | Mismo process="null" y pregunta innecesaria. |
| t4 | Falla | Continúa aclarando; batch vuelve a process="null",limit10. No confirmación preparada. |
| t5 | Pasa | It's 11:03 coincide con system.time verificado (14:03 UTC,offset−180). |
| t6 | Falla | Niega acceso a tareas; no task.list ejecutado. |

argument-batches.jsonl conserva payload completo y salida del modelo: ahora sí recibe
la descripción de byTitle pero inventa el literal null en el campo process. Ya no es
hipótesis de descripción omitida. Journal sólo registra memory.status y system.time;
no window.resolve ni app.close. Fixture propia seguía viva tras la captura.

Se retienen las garantías estructurales (descripción canónica, selector y opcionales
válidos), pero falta resolver la extracción del título y las otras regresiones.
Siguiente vía distinta: reutilizar la extracción literal ya existente para las
relaciones de identidad explícitas, sin pedir al modelo que invente un proceso,
o revisar el contrato de destino. No autoriza atribuir al usuario un título nuevo,
elegir ventana activa ni omitir confirmación. C03 sigue EN_CURSO.
