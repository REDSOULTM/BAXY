# Dos partes bilingües en una llamada: no adoptado

94.36 s, GPU 3497.56 MiB, RAM 5140.14 MiB; registro intacto.
12 turnos, 11 publicados. Se conservan todos los originales en segments.jsonl.

| Turnos | Veredicto |
|---|---|
| 1–4: hora/lecturas ES/EN | Correctos; la bienvenida t0 ya no aparece después de la respuesta. |
| 5: hora mixed | Repite íntegramente hora en ambos idiomas y junta sin puntuación. No natural. |
| 6: hora/audio mixed | Ahora publica, pero duplica todos los hechos como traducción. No cumple. |
| 7: saludo mixed | Saludo/pregunta repetidos como traducción. No mejora semántica. |
| 8: cifrado mixed | Explicación íntegramente duplicada en inglés; no spanglish natural. |
| 9: copia de seguridad | composition_failed. Hubo intentos que afirmaron estar creando la copia; no aceptados. |
| 10: gravedad mixed | Explicación duplicada como traducción. |
| 11: no abras Paint | Correcto; frase de nombre redundante. |
| 12: Perú | Correcto. |

Máximo 6/12 plenamente útiles. No adoptar el formato ni contar publicaciones como
mejora de calidad. Sólo vive en profile/sitecustomize.py de esta captura; no pasó
al producto. No se relajó ningún guard. La reparación de bienvenida sí se mantiene:
dos pruebas fallaban antes, 59 pruebas del owner pasan después y t1 queda correcto.
