# Desarrollo: cierre por título — no aprobado

6 turnos publicados, **1/6 útil y fiel**. No aceptación reservada.
Sesión 81116 terminó exit0; 98,41 s; GPU atribuida 3499,56 MiB;
RAM 4596,71 MiB. Registro Granite intacto; Qwen4B por override de diagnóstico.
Core NativeAOT recién publicado, fuente/exe sellados en PREREG.json.

| Turno | Veredicto | Evidencia y motivo |
|---|---|---|
| t1 cierre por título | Falla | voice.cancel y voice.speak agotaron sus límites antes de decidir. Shell devolvió unavailable; la composición convirtió la causa en «el sistema no tiene acceso a la mente». No cierre ni confirmación. |
| t2 cancelar | Falla | Sin plan pendiente por el fallo anterior. «El pedido está fuera de lo que hago» no explica el estado ni responde útilmente. |
| t3 repetir cierre | Falla | Modelo propuso window.resolve; domain_grounding lo retiró. _window_domain no reconoce una ventana identificada por título nuevo. Rechazo de capacidad incorrecto. |
| t4 confirmar | Falla | «Confirmado» sin confirmación pendiente ni acción preparada. No acredita cierre. |
| t5 hora EN | Pasa | It's 10:48, conserva clock=10:48 en los hechos de composición. |
| t6 tareas EN | Falla | Selección unsupported, recuperación a aclaración reminder.list; publicación afirma no tener acceso a las tareas. No task.list verificado. |

La fixture propia C03TitleFixture PID38428 seguía viva tras terminar la captura.
No se cerró ninguna ventana de usuario. No se alcanzó window.resolve ni byTitle:
los 14 tests del proveedor y 23 de integración no certifican la selección del modelo.
Paired/turn-audit/compose-audit/shell-trace conservan todos los intentos.

Siguiente hipótesis acotada: reconocer la relación gramatical ventana→título,
independiente del nombre de aplicación, y conservar app.close como efecto final.
Resolver el título sigue siendo una lectura verificada; no sustituirlo por la
ventana activa. Timeout de voz y selección de tareas siguen pendientes, no aprobados.
