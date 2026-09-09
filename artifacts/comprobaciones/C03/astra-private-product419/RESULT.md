# 419 — detenido por RAM libre antes de los turnos

El guardia conservador de RAM libre (<768 MiB) terminó exclusivamente el árbol
del diagnóstico durante el arranque, tras publicar Core y cargar el modelo.
Cero turnos/terminales: no hay resultado semántico de los ocho casos. Se conserva
el intento fallido, sin dar la corrección418 por validada en producto todavía.
GPU propia máxima 3167,5625 MiB; RAM muestreada del árbol 3543,671875 MiB; 61,157 s.
Este pico del árbol no describe toda la RAM del sistema ni acredita voz conjunta.
No se alcanzó el límite VRAM de3800 MiB. Exit1, manifiesto intacto.

Tras la terminación sólo quedaron cuatro trabajadores de compilación del
publicado AOT, hijos de88616 (99740,67884,90316,103672); no modelo ni producto.
Se cerraron con build-server shutdown de ambos SDK. RAM libre resultante
5485224 KiB. La encuesta no se tocó. El import de los samplers sólo reutiliza
tooling existente; no hay evidencia de que él explique el consumo.

420 repetirá exactamente los mismos ocho casos y fuente418, ya con Core
publicado y servidores inactivos cerrados; nuevo perfil, mismos límites,
modelo/configuración/observer. Es restauración del entorno tras un corte
anterior a cualquier caso, no selección de una corrida favorable. Si el límite
reaparece sin compilación, estudiar distribución RAM del runtime; no rebajar
el margen ni atribuir el fallo a comprensión. No nueva fuente420.
