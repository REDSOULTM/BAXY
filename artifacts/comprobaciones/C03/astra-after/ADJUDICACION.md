# Candidato Astra, primer tramo — 16 turnos, 2026-09-06

Lectura de los 16 finales en `paired.txt` y de borradores en `compose-audit.jsonl`.
Misma población de regresión y Granite que baseline. Concurrencia con pytest
de Full: no comparar tiempos ni atribuir todos los fallos a los prompts.

**9/16 útiles y fieles; 11/16 publicados. No cumple C03.**

| Turno | Veredicto | Motivo |
|---|---|---|
| 1 | Pasa | Devuelve el saludo original en inglés. |
| 2 | Falla | Composición agotada, sin definición. Hechos de entrada: compose_unavailable. |
| 3 | Pasa | Saludo con pregunta social natural, sin veto falso. |
| 4 | Pasa | Devuelve saludo en inglés. |
| 5 | Pasa | Definición correcta de latencia. |
| 6 | Pasa | Explica su efecto en reacción y aplicaciones interactivas. |
| 7 | Pasa | Define caché DNS y su finalidad. |
| 8 | Falla | Agotamiento a partir de compose_unavailable; no responde importancia de caché. |
| 9 | Falla | Agotamiento a partir de compose_unavailable; no hay definición de VPN. |
| 10 | Falla | Final filtrado, sin texto y estado normal; los borradores proceden de error de disponibilidad. |
| 11 | Pasa | Proxy como intermediario de comunicación. |
| 12 | Falla | Redacción repetitiva y promesa ambigua de no exponer datos; no basta para explicar la finalidad con precisión. |
| 13 | Pasa con defecto | Concepto correcto: dirige datos entre redes. Falta una c en «direcciona». |
| 14 | Falla | Agotamiento; compone una falta de claridad en vez de responder utilidad del router. |
| 15 | Falla | «Twelve por ocho es doce»: idioma y resultado falsos. Los borradores ya contienen errores aritméticos. |
| 16 | Pasa | Lima. |

Conclusión limitada: saludos y seguimiento de latencia mejoran; no hay mejora
global demostrada. No consumir una aceptación nueva sobre este candidato.

Causa siguiente comprobable: Python despacha trabajo del modelo en serie, pero
el cliente cuenta el timeout de cada solicitud desde su envío. El temporizador
de progreso hace composición bloqueante mientras el turno está pendiente; puede
agotar el timeout en cola y marcar el cliente como no listo. Corregir coordinación,
no aumentar todos los plazos ni debilitar la veracidad. Fuente congelada durante
esta corrida; se conserva íntegra aunque el resultado sea desfavorable.
