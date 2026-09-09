# Prosa sin frases prescritas — desarrollo, 2026-09-06

16 turnos conocidos, Granite registrado y candidato sellado en PREREGISTRO.json.
**15/16 publicados; 9/16 útiles y fieles.** No habilita aceptación reservada.

| Turno | Veredicto | Motivo |
|---|---|---|
| 1 | Pasa | Saludo inglés propio. |
| 2 | Pasa | Explica DNS y resolución de nombres. |
| 3 | Pasa | Devuelve el saludo. |
| 4 | Pasa | Saludo y oferta social; dos párrafos innecesarios, sin defecto factual. |
| 5 | Pasa | Latencia como tiempo de viaje de señal. |
| 6 | Pasa | Explica impacto en aplicaciones en tiempo real. |
| 7 | Pasa | Caché de resoluciones para acelerar consultas posteriores. |
| 8 | Falla | «Can delay or change domain resolution» no explica con precisión el beneficio ni las condiciones de ese riesgo. |
| 9 | Pasa | Conexión cifrada a servidor remoto y acceso a red; no afirma anonimato total. |
| 10 | Falla | Circular: entender las razones para asegurar que la VPN funcione no explica su importancia. |
| 11 | Pasa | Describe un intermediario para acceder a recursos remotos. |
| 12 | Falla | Acceder a recursos por un proxy no explica por qué usar el intermediario. |
| 13 | Falla | «Direciona» no es la grafía española; no pasa naturalidad. |
| 14 | Falla | Pregunta de confirmación sin relación con la utilidad del router. |
| 15 | Falla | Arrastra la confirmación a una pregunta de aritmética. |
| 16 | Falla | Agotamiento y misión pendiente al preguntar por Lima. |

La bienvenida t0 ya no se recorta; el cambio de contrato y la eliminación de
intro fija pasan las pruebas de variantes válidas. Eso no demuestra mejora global
de conversación: esta corrida sigue fallida. No continuar afinando frases sobre
este panel como si eso resolviera la admisión de operaciones.

Hallazgo que cambia la siguiente acción: turn-audit.jsonl registra una propuesta
wifi.connect que atraviesa information_question y acaba en plan tras
action_grounding. El estado público queda awaiting_mission_resume. La protección
de preguntas informativas no reconoce «¿y para qué sirve?» ni «why…» ni «cuánto…».
Se extendió la protección existente con el lector de elipsis ya compartido y las
formas interrogativas ausentes: cinco regresiones fallan antes y pasan después;
834 pruebas de política verdes. El contraste integrado siguiente está en
`astra-question-authority`; no atribuirle resultados hasta adjudicarlo.
