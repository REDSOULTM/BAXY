# UI109 — error visible y recuperación — 2026-09-07

Fuente108 frente a fuente103/UI107, mismos tres relojes, modelo/perfil local
y avería real acotada. [Prerregistro](astra-ui109/PREREG.json). La interfaz
muestra Error y Response error al agotar la composición; conserva entrada
utilizable y vuelve a responder después de restaurar el mismo servidor.

## Secuencia observada

| Caso | Entrada literal | Salida observada | Resultado |
|---|---|---|---|
| Sano | Dime la hora. | Son las 07:00. | Respuesta útil con estado Idle. |
| Servidor suspendido | Dime la hora. | Thinking inicial; después Error en el grafo y Response error encima del input. | Estado de error explícito y recuperable. Ninguna prosa de respuesta ni código SYSTEM en actividad. |
| Restaurado | Dime la hora. | Son las 07:02. | Respuesta útil, grafo Idle y etiqueta de error retirada. |

Capturas [sano](astra-ui109/01-healthy-visible.jpg),
[espera inicial](astra-ui109/02-suspended-thinking-initial.jpg),
[error](astra-ui109/02-suspended-error-visible.jpg),
[entrada enfocada durante error](astra-ui109/02-error-input-available.jpg),
[petición escrita todavía en error](astra-ui109/03-restored-entered.jpg),
[recuperación](astra-ui109/03-restored-visible.jpg).
Los metadatos junto a cada captura guardan hora de observación y ventana.
No se capturó continuamente toda la espera: Thinking inicial y Error terminal
son observaciones directas; la ausencia de Idle entre ellas además depende de
la proyección del estado de la cola en fuente108, no de un vídeo continuo.

La bienvenida fue «¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?».
Los tres casos usan App37276, servidor20156 y ventana3148270 en la misma sesión.
La petición de avería figura a07:01:21local; el tercer pedido a07:02:35 y su
respuesta a07:02:37. Se enfocó y escribió en el input durante el estado de error.
No se movió el foco automáticamente ni se reejecutó una operación al recuperarse.

El helper99128/PID11140 terminó exit0. Servidor stopped desde
10:00:49.515260UTC hasta10:02:09.671447UTC,80,16s; mismo tiempo de creación
y estado running después de resume. [Registro](astra-ui109/RESUMED.json).
Hereda el mecanismo psutil7.0.0 y watchdog300s de UI107, sin inyectar borradores,
modo de composición o contenido fijo. El conductor de avería sólo opera sobre
el proceso propio verificado; la interacción fue por Computer Use/Sky.

## Recursos y validación

`py main.py`, launcher4252 exit0, recompilación automática de App y Core AOT.
Las huellas posteriores reales están en
[RUNTIME_AFTER_LAUNCH](astra-ui109/RUNTIME_AFTER_LAUNCH.json), incluyendo Core
`12A2E21648EA14D059ACE672C8C44E867368016D98BC940F10D19894F95C0008`.
Qwen3.5 sigue como override, wake0, registro intacto; no promoción.

Monitor94971 exit0:169,50s, GPU3505,1484375MiB, RAM5514,2890625MiB,
atribución disponible y parada solicitada. [Recursos](astra-ui109/RESOURCES.json).
Incluye App y descendientes a partir del monitor, excluye build/arranque anterior.
Tras guardar la recuperación se detuvo el monitor y se terminó únicamente el
árbol App37276 con ruta verificada. No procesos suspendidos pendientes ni prueba
de cierre grácil. Pruebas169pass/0skips y Fast de108 en [informe](ASTRA-TRAMO-108.md).

La comparación resuelve el fallo de presentación de UI107. No acredita prosa
durante el fallo total, lector de pantalla físico, voz/audio, reserva humana100,
presupuesto simultáneo con voz o runtime promovido. La etiqueta de interfaz no
se contabiliza como respuesta humana normal útil. C03 continúa EN_CURSO.
