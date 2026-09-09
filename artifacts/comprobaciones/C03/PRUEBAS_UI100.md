# C03 — ocho finales en la ventana real de BAXY

2026-09-07. Fuente98, entrada `py main.py`, perfil persistente `dev-mente-v2`,
Qwen3.5-4B Q4_K_M mediante override; runtime registrado sin promover.
Ocho casos técnicos congelados en [PREREG](astra-ui100/PREREG.json), separados de
la reserva humana. Interacción mediante Computer Use `@oai/sky`, sin navegador
ni `--ui-probe`. Se conservaron el perfil y sus archivos; sólo se añadieron dos
fixtures únicos antes de arrancar.

**Ocho finales útiles y fieles observados en pantalla. Progreso redactado aún
no acreditado en la ventana. C03 continúa abierto.**

| Caso | Entrada literal | Respuesta visible literal | Adjudicación y captura |
|---|---|---|---|
| 1 | Dime la hora. | Son las 05:31. | Coincide con `system.time` verificado. [Captura](astra-ui100/01-clock-observed.jpg). |
| 2 | Lee el archivo "c03-ui100-ausente.txt" del sandbox. | No se encontró el archivo "c03-ui100-ausente.txt" en el sandbox. | Búsqueda verificada con cero resultados; conserva la causa. [Captura](astra-ui100/02-missing-progress.jpg). |
| 3 | Why couldn't you read that file? | I couldn't read the file because it wasn't found in the sandbox. | Conserva referente, causa e idioma; no ejecuta otra lectura. [Captura](astra-ui100/03-why-missing-observed.jpg). |
| 4 | Lee el contenido del archivo "c03-ui100-lectura.txt" del sandbox. | He leído el archivo "c03-ui100-lectura.txt" y su contenido es: "Lectura técnica C03: el color de control es turquesa." | Recuperación en la misma sesión; coincide con los 55 bytes UTF-8 de la fixture. [Captura](astra-ui100/04-valid-observed.jpg). |
| 5 | Read the file "c03-ui100-invalid-utf8.txt" in the sandbox. | The file read failed because the content contained invalid UTF-8 characters. | Avería inyectada, causa `invalid_utf8` del provider. [Captura](astra-ui100/05-invalid-progress-later.jpg). |
| 6 | Why couldn't you read that file? | I couldn't read the file because it contained invalid UTF-8 characters. | Conserva la segunda causa y el referente actual. [Captura](astra-ui100/06-why-invalid-visible.jpg). |
| 7 | Dime la hora, el audio y el uso de CPU. | La hora es 05:37. El volumen está en 0 y el audio está silenciado. El uso de CPU es del 46,25%. | Tres lecturas verificadas, en orden, con valores conservados. [Captura](astra-ui100/07-composite-visible.jpg). |
| 8 | Pon el volumen. | ¿A qué nivel quieres que ponga el volumen? | Aclaración necesaria; no se suministró valor ni se ejecutó cambio. [Captura](astra-ui100/08-clarification-visible.jpg). |

Bienvenida visible: «¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?»
([captura](astra-ui100/00-ready.jpg)). Los nombres de algunas capturas describen
el momento que se intentaba observar, no su resultado: `02-missing-progress`
y `05-invalid-progress-later` contienen ya el final.

## Progreso: diferencia entre composición y publicación

En el caso5 se observó `Thinking` durante la espera. El error final se publicó
en la traza a 824443,810 ms desde arranque; la solicitud de composición del aviso
de progreso empezó después, a 824450,781 ms. Casos2 y4 muestran también una
composición tardía. El `published:true` de la auditoría Python significa borrador
aceptado por ese compositor, no texto observado en la ventana. No se cuenta como
progreso visible ni se confunde el cambio visual de estado con prosa del modelo.

La inspección identifica dos fronteras seriales: `MindSidecarClient._requestLock`
y `_run_control_plane` del sidecar. `TryEmitDueMilestone` rechaza el intento mientras
`HasActiveRequest`; además fija la marca del intento antes de comprobar disponibilidad.
El caso7 sí generó una señal temprana interna desde `_emit_early_turn_signal`; su
publicación transitoria no quedó capturada. La reparación siguiente debe reutilizar
esa ruta y conservar la serialización, la veracidad de fase y el descarte de avisos
obsoletos, en vez de dar por aceptada la composición aislada99.

## Recursos, límites y trazabilidad

Monitor27634 exit0: **3504,640625 MiB GPU**, **5959,11328125 MiB RAM**, 987,44 s,
atribución GPU disponible; detenido expresamente al terminar la prueba. Incluye
App y descendientes desde que comenzó el monitor; excluye build/arranque anterior
a ese instante. [Resultado](astra-ui100/RESOURCES.json). Wake desactivado; el audio
observado estaba silenciado a volumen0. Esto no acredita altavoz ni audio físico.

`main.py` recompiló Core: SHA256 del ejecutable junto a App
`9bc4b041ab4741a54a930dc7387498b9d263de9d1f3ed8ef45858dbf94bf6632`.
El hash Core63 de informes anteriores es histórico. No cambios de fuente durante
la prueba, no Full ni promoción. El cierre de ventana se solicitó mediante su botón;
la comprobación de terminación de procesos se registra aparte.

Evidencia: [auditoría de composición](astra-ui100/compose-audit.jsonl),
[conversación bruta](astra-ui100/raw-replies.jsonl), [traza](astra-ui100/shell-trace.jsonl),
[interacciones](astra-ui100/ui-events.jsonl) y capturas con metadatos JSON contiguos.
Hubo pérdida de foco tras un envío: se volvió a enfocar antes de escribir.
El Return del caso5 no envió; se verificó que seguía pendiente y se usó el botón.
Una captura devolvió otra aplicación por oclusión: se excluyó y se trasladó a
`%LOCALAPPDATA%/BAXY/C03-private-ui-evidence/ui100-06-why-invalid-occluded.jpg`;
no se publica ni demuestra BAXY. No se interactuó con esa otra aplicación.
