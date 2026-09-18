# Decisiones del dueño — 2026-09-18 (PC principal)

Recibidas en la sesión raíz de Fable 5.1 mientras se cerraba MSGSEND1845. Prevalecen sobre la
lectura restrictiva de DECISIONES §6 del 17-09 en lo que aquí se amplía.

## 1. Los literales de mensajería a terceros también se acreditan

Texto del dueño (transcrito): «hay muchos que dicen mándale un mensaje a… o escríbele un correo a…
Recuerda que todo eso se debe de reemplazar por los canales seguros que yo te he dado. Aun así sería
el mismo test, porque en uno dice ShooterCock pero el usuario seguro de pruebas de Discord sería
Valeria. Así que aun así puedes certificar todos los turnos; certificar todo, todo de 742.»

Aplicación por la raíz:

- Todo envío de mensajería sigue yendo **sólo** al canal de pruebas propio del dueño, por
  construcción del adaptador (`ForcedTestDestination`): WhatsApp → grupo «Música», Discord →
  usuario «Valeria». Nunca al destinatario nombrado. Correo → la casilla de pruebas del dueño
  autor@example.com (mecanismo por construir).
- Un literal que nombra a un tercero («mandale hola a Lucas por whatsapp») **se acredita** cuando
  el envío al canal de pruebas fue real y verificado, hubo revisión de la raíz por caso, y el final
  dice con verdad que fue al canal de pruebas y **no** al destinatario pedido. La regla de las dos
  variantes en tanda se mantiene.
- Leer chats («léeme el último mensaje de Pedro») no es un envío: sigue como límite honesto salvo
  decisión posterior.

## 2. Canales de prueba

Reiterado por el dueño: «Música» y «Valeria» son canales creados por él exclusivamente para probar
BAXY; no hay privacidad de terceros ni contenido personal. Durante la prueba deliberada del dueño
(16:04) BAXY escribió «Música» en el chat «Letras» que él había dejado abierto adrede; la guardia de
búsqueda (commit 9eabbb1e) impide que se pulse Enter fuera del buscador.

## 3. Correo de pruebas

Casilla de pruebas del dueño para las 6 filas de Correo: autor@example.com.
