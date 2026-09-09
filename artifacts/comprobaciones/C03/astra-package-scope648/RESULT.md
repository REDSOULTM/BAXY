# 648 — el conteo de un paquete incluye todos sus procesos

647 observó dos ventanas de WhatsApp. La comprobación independiente que contaba sólo WhatsApp.Root.exe encontraba una, porque otra ventana pertenece a msedgewebview2.exe con exactamente el mismo AUMID del paquete. Al agrupar los handles de las instantáneas por esa identidad, ambas contienen dos. La consulta de identidad se hizo después de647; los procesos mantienen nombres y tiempos de creación compatibles con ambas instantáneas. No se presenta esa identidad como una captura simultánea. Un PID ajeno ya había terminado; se conserva el error y no se atribuye a ningún actor.

No cambia el provider ni la fuente. El error era usar el nombre del ejecutable como comprobación independiente de una identidad empaquetada. Futuras instantáneas deben registrar AUMID junto al HWND/PID en el momento de captura. Sin nuevas ventanas, activación, mensajes, modelo ni crédito de UI/voz.
