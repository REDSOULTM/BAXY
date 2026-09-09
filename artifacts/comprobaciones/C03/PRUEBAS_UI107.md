# UI107 — avería real, recuperación y confirmación — 2026-09-07

Fuente103 sin cambios, `py main.py` sin recompilar, Qwen3.5 local con override
y wake0. Siete entradas técnicas fijadas en [PREREG](astra-ui107/PREREG.json).
No son reserva humana ni aceptación de audio. App4888, servidor19948 y la misma
sesión visible de la interfaz se conservaron durante los siete casos.

## Entradas, respuestas y efectos observados

| Caso | Entrada literal | Respuesta visible | Adjudicación |
|---|---|---|---|
| 1 | Dime la hora. | Son las 06:36. | Útil; estado sano. |
| 2 | Dime la hora. | SYSTEM: composition_failed | Error diagnosticable, pero presentación insuficiente: código interno con el grafo en Idle. No prosa útil. |
| 3 | Dime la hora. | Son las 06:39. | Recuperación real, mismo servidor y App tras reanudar. |
| 4 | cierra la ventana titulada Ventana C03 de prueba | ¿Quieres confirmar que cierre la ventana titulada Ventana C03 de prueba o cancelar la acción? | Identifica acción y ventana exactas; no afirma cierre. |
| 5 | cancelar | Se canceló la solicitud de cerrar la ventana "Ventana C03 de prueba". | Ventana16126532 y proceso31896 siguen presentes. |
| 6 | cierra la ventana titulada Ventana C03 de prueba | ¿Quieres confirmar que cierre la ventana titulada Ventana C03 de prueba o cancelar la acción? | Nueva solicitud explícita tras cancelar. |
| 7 | confirmar | Se cerró la ventana titulada Ventana C03 de prueba. | Ventana y proceso31896 ausentes antes de cualquier limpieza. |

Capturas finales: [01](astra-ui107/01-healthy-visible.jpg),
[02](astra-ui107/02-suspended-failure-visible.jpg),
[03](astra-ui107/03-restored-visible.jpg),
[04](astra-ui107/04-close-confirmation-visible.jpg),
[05](astra-ui107/05-cancel-visible.jpg),
[06](astra-ui107/06-close-confirmation-visible.jpg),
[07](astra-ui107/07-confirm-visible.jpg).
Cada entrada conserva además su captura antes del envío y metadatos de observación.

La fixture es una ventana vacía propia, con binario y hash prerregistrados;
se abrió por Computer Use. La cancelación conserva el mismo objeto devuelto por
Sky: [inventario](astra-ui107/05-fixture-after-cancel.json). Tras confirmar no
queda esa ventana ([inventario](astra-ui107/07-fixture-after-confirm.json)) ni
su proceso ([comprobación](astra-ui107/07-fixture-process.json)). No fue necesario
cerrar la fixture desde el conductor. Estas observaciones no sustituyen la
regresión contractual de confirmaciones para invocaciones distintas.

## Avería y restauración

`scratchpad/c03-suspend-ui107.py` verificó rutas, relación de descendencia e
identidad de los PID antes de suspender sólo el servidor propio. `psutil`7.0.0,
suspensión de todos los hilos en Windows; contraste previo con documentación
primaria [suspend/resume](https://psutil.io/api/#psutil.Process.suspend), consultada
2026-09-07. La documentación publicada corresponde a8.0dev; la versión local
y el mecanismo realmente utilizado constan en el registro.

Suspensión09:37:02.452240UTC, reanudación09:38:48.617811UTC,106,17s;
estado stopped → running e identidad conservada en
[RESUMED](astra-ui107/RESUMED.json). Helper91163 exit0. No inyección de borradores
ni modo `BAXY_COMPOSITION_INJECTION`. El error apareció a06:37:55local, con
entrada y envío utilizables; el siguiente reloj respondió después de restaurar
sin reiniciar BAXY. Hay recuperación, pero el caso2 **no acredita presentación
útil del fallo**: `composition_failed` e Idle son un bloqueo de C03 pendiente.

## Recursos y estado de cierre

Monitor22512 exit0:781,48s, GPU3497,52734375MiB, RAM5847,5MiB;
atribución disponible, parada solicitada. [Recursos](astra-ui107/RESOURCES.json).
Incluye App y descendientes desde el inicio del monitor, excluye arranque previo;
no incluye una prueba de voz simultánea. Registro de runtime sin promover.

Después de guardar el resultado y verificar la ausencia de la fixture se detuvo
el monitor; se terminó únicamente el árbol App4888 con ruta previamente
verificada. No acredita cierre grácil. No cambios de producto, nuevos tests ni
Full en esta comprobación; las pruebas dueñas97/Fast de fuente103 siguen como
validación de fuente. C03 continúa EN_CURSO.
