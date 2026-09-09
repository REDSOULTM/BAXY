# Desarrollo: extracción literal heredada — mejora, panel no aprobado

Sesión89257 terminó0;46,14s,GPU3497,56MiB,RAM4475,62MiB;registro intacto.
**5/6 publicados útiles/fieles,1 agotamiento espontáneo.** Prosa de cancelación extensa.
No cien frescos, promoción ni Full. Antecedente interrumpido preservado aparte.

| Turno | Veredicto | Evidencia |
|---|---|---|
| t1 cierre por título | Pasa | Resuelve título real Ventana C03 de prueba,PID15012. Pide confirmar/cancelar ese cierre; no cierra aún. |
| t2 cancelar | Pasa | Dice que cancela el cierre, conservando que sólo observó la ventana. La segunda resolución t3 encuentra el mismo PID vivo. Dos frases redundantes: naturalidad mejorable. |
| t3 repetir cierre | Pasa | Nueva resolución exacta del mismo título/PID y nueva confirmación pendiente. |
| t4 confirmar | Falla | app.close realmente cierra,verified=true/windowClosed=true,journal seq8. La narración se agota con internal_code. Un efecto verificado sin respuesta final útil no pasa C03. |
| t5 hora EN | Pasa | It's 11:38 coincide con los hechos. |
| t6 tareas EN | Pasa | task.list verificado; Your to-do list is empty right now coincide con el perfil aislado. |

Journal:seq4 y6 window.resolve;seq8 app.close;seq10 system.time;seq12 task.list.
Fixture propia creada para esta captura, sin documentos. No limpieza externa antes de
seq8: BAXY es quien cierra esta vez. Captura dura menos que los intentos que pedían
proceso; no atribuir toda la diferencia a una causa sin benchmark controlado.

El título llega ahora por _explicit_arguments_from_evidence, sin extracción LLM de
un proceso inventado. La búsqueda sigue lexical; el acierto t6 no prueba promoción E5.
Auditoría t4:los seis borradores incluyen La ventana "Ventana C03 de prueba".
Python los acepta; C# los rechaza internal_code. Sospecha concreta a reproducir:
HasRepeatedWord borra comillas y compara ventana/ventana como si fueran tartamudeo.
Corregir esa frontera de tokenización, no añadir el título de prueba a una excepción.
