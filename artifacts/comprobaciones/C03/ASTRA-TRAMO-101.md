# C03 — señal temprana antes del trabajo serial

Hipótesis previa a editar: UI100 demuestra finales útiles8/8 pero el temporizador
no puede componer durante una petición activa. La señal `turn.signal` existente
sí atraviesa el protocolo mientras la respuesta terminal sigue pendiente.
Se extenderá esa ruta a la decisión por modelo y a la planificación por modelo,
con hechos de fase y un presupuesto opcional de composición de2,5s compartido
entre intentos. Un fallo del aviso no debe fallar el pedido principal ni reiniciar
su deadline. No se cambia modelo, prompt, muestreo, catálogo ni concurrencia.

Herencia: `_emit_early_turn_signal` ya sirve a efectos compuestos explícitos;
`test_preclassification_progress_cannot_exhaust_an_answerable_turn` conserva la
regresión que impide gastar el turno en avisos de conversaciones ya reconocidas.
Fuente98/99 conserva fase y elimina el objetivo futuro del prompt de progreso.
Se reutilizan las tres piezas. La marca del intento App debe registrarse sólo
cuando puede iniciarse, y las señales recibidas deben pertenecer a una petición
pendiente y al mismo turno/fase al publicarse.

Contraste actual,2026-09-07: [SemaphoreSlim.WaitAsync](https://learn.microsoft.com/en-us/dotnet/api/system.threading.semaphoreslim.waitasync?view=net-10.0)
espera disponibilidad del semáforo; no permite que otra composición entre durante
la ocupación. [Threading de Python3.12](https://docs.python.org/3.12/library/threading.html)
permite trabajo concurrente de E/S, pero añadir un hilo no hace independientes los
deadlines y cachés mutables del runtime. La inspección local confirma tanto el
semáforo App como `_SerialRequestLane`. Se conserva esa serialización y se prueba
la emisión en sus fronteras, sin servidor/modelo adicional.

Criterio: aviso fiel antes del final en la ventana real; finales y recuperación
UI100 conservados. Pruebas dueñas con controles de timeout, camino rápido y señal
obsoleta; luego Fast. No Full, reserva humana ni promoción en este tramo.

Estado inicial: fuente98 sin nuevas ediciones. UI100 cerrado en bandeja por diseño;
se terminó exclusivamente su árbol verificado mediante taskkill. Monitor27634exit0,
987,44s,GPU3504,640625MiB,RAM5959,11328125MiB. No procesos propios activos.

Implementado: timeout opcional local a compose_user_message, compartido por todos
sus POST/reintentos y subordinado al deadline del pedido; no modifica el presupuesto
principal. _emit_early_turn_signal transporta fase/trace y tolera fallo opcional.
Se llama antes de retrieval/decisión por modelo y antes de planificación por modelo;
los caminos de conversación ya reconocidos y las operaciones rápidas no lo añaden.
App no cuenta como intento una cola ocupada y comprueba petición/turno/fase vigentes.

Validación:233 integración pass/0skips/2m10s, handle70536exit0. Incluye transporte
real a fixture que emite primero una señal de petición retirada y luego la vigente:
sólo la segunda llega al consumidor. Se conservan203 contrastes de fase/hechos/App.
1179pytest pass/0skips/6,63s en seis suites; Fast80125 en ejecución al registrar.

La ampliación Python detectó dos pendientes anteriores: una expectativa de Goal06
todavía exigía objetivo futuro en progreso, incompatible con98; ahora exige estado
e idioma y ausencia de ese objetivo en todos los intentos. La otra reveló que la
exención de explicación de errores de78 admitía una negativa vacía como «I don't
do that» ante una definición. Se restringe a respuestas con contenido adicional al
marcador de fallo existente; se conservan ambas explicaciones útiles de UI100.
Sin vocabulario nuevo de veto. Controles ES/EN de negativa vacía y causas explicadas.
Durante los tests se corrigieron expectativa de idioma situado en sistema durante
reintento y uso de `request`, reservado por pytest, como parámetro. Fallos y logs
conservados en TEMP/c03-progress101-python*. No cambios de umbral ni skips.

Fast80125 exit0, Release19,24s, cero avisos/errores. UI102 preparado; no lanzado aún.
