# H2 del PC: las 12 tareas que `final` falla en las dos semillas del holdout v5 (diagnóstico, 2026-10-24)

Leído con las trazas de `ho5-final-s0-e2e-e2e` (PC) y `ho5-final-s1-e2e-e2e` (portátil), código int10f 19be8b42a. Sólo lectura;
cada arreglo va en su rama corta con prueba que falla antes. El v5 ya es material de práctica.

| Caso | Área | Qué pasó (s0 / s1) | Causa | De quién | Arreglo (rama) |
|---|---|---|---|---|---|
| V5E045 | confirmación | la llamada buena (s1) o casi buena (s0) se rechaza y se escribe en `Documentos\Turnos\…` | `SaidFolders.cs:57` corta la ruta relativa en el espacio («Documentos\Turnos Farmacia» → Documents\Turnos, que no existe); `Longest` sólo alarga rutas completas | App (said_folder) | rutas relativas con el mismo `Longest` (portátil, `SaidFolders.cs` es del portátil) |
| V5E047 | confirmación | trash.named correcto rechazado → subdirectory «Facturas» → no encontrado; el núcleo nunca pide el sí | lo mismo; además el `next` del adaptador no dice que la subcarpeta no existe | App + proveedor | lo mismo (portátil) + `next` de subcarpeta inexistente (w10-archivos) |
| V5E046 | confirmación | ninguna llamada: «no puedo borrar carpetas» (falso) y pregunta por texto | `filesystem.known.trash.named` sí borra carpetas, pero su descripción sólo dice «file» y `fileName` no tiene descripción | modelo, con la descripción | descripción (toca el prefijo: pendiente de decision3) |
| V5E051 | confirmación | «en la terminal, crea listo.flag»: file_write directo, sin consola ni sí | el modelo no sigue el medio nombrado; la descripción de shell.command.run no dice `home` | modelo, con la descripción | descripción del catálogo (toca el prefijo) |
| V5E052 | confirmación | dictado «factura marzo punto pdf»: el archivo es `factura-marzo.pdf`, no encontrado antes de pedir el sí | el adaptador sólo acepta el nombre exacto y no ofrece nombres casi iguales | proveedor | `near_names` (w10-archivos) |
| V5E066 | ya_lo_hiciste | `input_text_type` sin `window`: en el PC el texto fue a la ventana de delante (Claude), en el portátil `protected_window` | la descripción y el `next` de protected_window no nombran la vía `input_visible_controls(application)` → `input_text_type(window)` | modelo + proveedor | `next` (w10-teclado) |
| V5E060 | multiturno | s0: `schedule.alarms` sin title → `notification_scheduler_failed` («Windows couldn't create it», falso); s1: 18:45 en vez de 6:45 | el proveedor exige `title` y el catálogo no; el catch convierte el error de argumento en fallo del programador. s1: el oráculo no acepta 18:45 (la frase no dice am/pm) | proveedor; s1 banco | title opcional y código de argumento propio (w10-alarma) |
| V5E061 | multiturno | s0: el frente lo tenía una ventana de DisplayFusion de V5E011; s1: «cámbialo» editó con file.edit otro archivo del disco (`Sin título.txt` ajeno) | s0 banco (ventana que quedó tras el cleanup); s1 nada dice que el texto tecleado vive en la ventana y no en un archivo | banco + modelo | `typed_in_window` (w10-teclado), `next` de file.edit (w10-archivos) |
| V5E062 | multiturno | dictado «hasta el setenta»: volumen de una app «VLC»/«video» falla dos veces; s1 afirma «quedó en 70» | `_founded` exige «70» escrito: la corrección de System One (audio_volume, 0,86) quedó sin fundamento | mente | número en palabras (w10-numeros b2f5ce3af) |
| V5E016 | comunes | «qué hora ve alguien en Tokio»: 23:28 en vez de 03:28 (+1 día) | el núcleo deja la cuenta al modelo y le da sólo el desfase; el modelo suma a la hora local | modelo, con la app | `place_clock`: hora y fecha del lugar en el resultado (w10-hora) |
| V5E008, V5E018 | comunes | «en qué año se inauguró el Metro»: responde 1968/1917 de los fragmentos sin abrir la página; inicio abría metro.cl y decía 1975 (2/2) | nada dice que sólo se leyeron fragmentos; posible regresión de una ayuda entre 452854a18 y 19be8b42a | modelo, con la app | `snippets_only` + bisección (w10-busqueda) |

H1 tal como se planteó (la capa de duda pregunta antes del borrado) **no aparece** en ninguna de las cinco confirmaciones del
PC: ninguna fila `doubt_ask`. La duda sí falla por otra vía, encontrada por el portátil en V5E023: el token «=input» con el «=»
solo como rival (otra tokenización del mismo texto) cuenta como duda; arreglo en w10-duda c27986969, en medida.

Banco: V5E011 dejó «Configuración de Monitor en DisplayFusion» al frente el resto de la corrida s0 (V5E019, 022, 025, 050,
058, 061 lo muestran en `foregroundHeldBy`); `Restore-BenchState` sólo cierra lo nuevo respecto de la foto del caso. El
oráculo 2 de V5E066 aprueba una pregunta y castiga un «no» honesto; el de V5E060 no acepta 18:45.
