# Tramo311 — referencia a la persona

UI309 terminó con exit0 de la sonda, pero el DOM no mostró respuesta al literal
«quien soy». El selector eligió conversación, sin system.identity; Python aceptó
seis veces «Tú eres el usuario que está hablando conmigo.». La App recompuso y
agotó sus intentos. No es un pase de identidad ni un bloqueo de arranque.

Primera frontera de publicación defectuosa: UserMessagePolicy contiene un veto
por la mera subcadena «el usuario»/«the user»/«los usuarios», con excepción literal
para «usuario admin». Es distinto del problema de selección, aún abierto.

Herencia: biblioteca/carter/la-razon-de-carter/11_lecciones_v1_a_v4.md, apartados
2.2 y3.1: conservar comprobaciones estructurales y retirar lo que se sustituye.
Se reutiliza la guarda existente de atribución de pedidos, sin nueva capa ni LLM.
La comparación se limita a las mismas respuestas: veto de sustantivo frente a
atribución de deseo/pedido/discurso a tercera persona. No cambia prompt/modelo.

Aceptación: referencia directa y explicaciones de cuentas ES/EN pasan al primer
intento de ModelMessageComposer; narraciones reales siguen rechazadas, incluso
insertadas en otra oración. No se exige que una referencia genérica al usuario
resuelva su nombre. El límite Python equivalente se inspecciona antes de declarar
paridad. Las pruebas añadidas son controles técnicos, no aceptación humana.

El primer baseline encontró DLL bloqueadas por la instancia310 abierta; su log
se conserva. El baseline sólo del proyecto de pruebas usa las referencias ya
compiladas, sin modificar esa instancia. Validación de nueva fuente requerirá
recompilación y comprobación integrada, sin Full durante reparación.
