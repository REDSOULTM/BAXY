# 461 — interrumpido por presión de RAM; calidad integrada no medida

Fuente436 intacta. Gemma publicado/b10809 y perfil de composición460 previstos.
La guardia detuvo exclusivamente el árbol del diagnóstico a27,813s: RAM libre724,79MiB,
por debajo del límite768MiB. Pico RSS del árbol3688,37MiB; VRAM1693,79MiB.
Sólo terminó una composición preliminar no modificada; no se publicó ningún terminal
y no se alcanzó ninguna composición con el perfil candidato. No es un rechazo de
calidad de Gemma ni8fallos; ocho casos no evaluados. Runtime registrado intacto.

El servidor asignó1416,51MiB de pesos aCUDA0 y2152,50MiB aCUDA_Host pese a-ngl99.
La CPU mantiene embeddings de entrada. Fuente436 ya desactiva cachéRAM y mmapGPU;
esa receta se midió conQwen, no acredita el óptimo para embeddings de Gemma.
Siguiente: investigar asignación/mapeo de esos tensores con backend exacto;
medir perfil que reduzca RAM antes de repetir la integración. No recortar precisión,
contexto ni cerrar aplicaciones del dueño para fabricar un resultado favorable.

Captura privada: %LOCALAPPDATA%/BAXY/C03-private-product461-private.
Proceso y toda su descendencia cerrados por el arnés. Sesión2849 recogida,exit1.
NoUI/voz física ni aceptación fresca. C03 completo sigue activo.
