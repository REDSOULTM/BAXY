# Estado para el dueño — 2026-09-13 (relevo Fable)

## Estado al tomar el relevo (2026-09-13T01:20:15.781361+00:00)

203/742 cubiertos, 539 abiertos, 0 no aplican; 0/35 categorías cerradas; C03 formal 3/11. Sin pruebas automatizadas por tu orden: nada está verde.

## Qué hice primero

- TIME1134 índice10: registrado como fallido sin repetirlo. BAXY respondió bien («Alarm scheduled for 01:00 UTC.») y creó la alarma; falla sólo la precisión (44.270822 s frente a 44 s).
- MESSAGING1136: verificado y adoptado. La pregunta de canal ya no recibe el cuerpo del mensaje, para que no hable en primera persona del usuario. Se mide en MESSAGING1140.
- TIME1139: comprobé con tres sondas sin producto que Windows guarda las alarmas a segundos enteros aunque se le entreguen fracciones, por cmdlet y por XML.

## Decisión que te corresponde (bloquea ~20 abiertos de alarmas/recordatorios relativos)

El criterio sellado exige que la hora pedida con fracciones coincida exactamente con la hora registrada. Windows no guarda fracciones, así que ningún arreglo del provider puede cumplirlo. Me ordenaste no redondear ni reinterpretar el criterio para dar pass, así que no lo toco. Opciones: (a) el producto programa al segundo entero (redondeo hacia arriba, nunca antes de lo pedido) y publica esa hora exacta, y el criterio compara con esa hora; (b) mantener el criterio y dejar esos casos abiertos. Mientras decides, sigo con mensajería y las categorías de mayor masa.
