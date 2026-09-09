# C03 — spoken-clock: desarrollo, no cierre

2026-09-06.21/21publicados,68.25s,GPU3497.56MiB,RAM5405.79MiB,registro intacto.
Mismas21entradas/modelo/perfil funcional de desarrollo;sin nueva aceptación ni
inyecciones repetidas. Fuentes:paired.json,compose-audit.jsonl,journal del perfil.

| Turno | Adjudicación |
|---|---|
| t1 | CORREGIDO: Son las 10 y 16 conserva el reloj10:16 y se publica. |
| t2 | Hora/audio correctos, redacción técnica. |
| t3 | Hora inglesa correcta. |
| t4 | Estado de hora/audio correcto; is set to100 describe configuración, no afirma que BAXY la cambió. |
| t5 | Hora correcta con mezcla mínima amigos; tratamiento plural innecesario. |
| t6 | Datos correctos, mutado incorrecto y mezcla inconsistente. |
| t7 | Saludo demasiado recargado con pregunta no pedida. |
| t8 | Definición pertinente, analogía extensa; cifrado no garantiza impedir todo uso indebido. |
| t9 | Concepto de backup correcto, analogía final poco útil. |
| t10 | Gramática un atracción/sueltes defectuosa y generalización hacia abajo. |
| t11 | Respeta prohibición de abrir Paint. |
| t12 | Lima, correcta. |
| t13 | Dos frases con analogía eat the sun's energy imprecisa. |
| t14 | Empieza correctamente y termina con bloque de aire, explicación engañosa. |
| t15 | No cumple spanglish explícito; definición circular de archivo. |
| t16 | task.list real,resultado vacío verificado, respuesta fiel. |
| t17 | Confirmación identifica cierre y proceso. |
| t18 | FALLA GRAVE de prosa: canceló, pero el reintento afirma que cerró la ventana. |
| t19 | Vuelve a resolver la ventana aún abierta y solicita confirmación de cierre. |
| t20 | Cierre real verificado PID9476/journalsequence28,windowClosed=true; jerga se resolvió persiste. |
| t21 | Hora correcta después del cierre. |

La equivalencia de hora oral mejora t1. Cancelación NO resuelta de forma estable:
el primer borrador t18 describía correctamente cancelación y no ejecución, pero
filtraba win_6e9a8eda5a1f6a186788496d7f41e0b1. Fue rechazado internal_code.
El reintento conservó los mismos hechos, pero invirtió el resultado y publicó
cerró correctamente. No fue efecto real: t19 resolvió otra vez la ventana y sólo
t20 ejecutó app.close. No atribuir la inversión al cambio del verificador de hora;
esa vulnerabilidad de composición/retry ya existía y esta corrida la expone.

El payload conserva cancelledRequest/cancelledAction y state=remaining steps
cancelled, pero outcome=completed por traducción genérica de polarity=success.
Esa ambigüedad es una hipótesis concreta para revisar. No se cambió todavía ni se
demostró que cambiarla elimine el fallo. El primer borrador también expone necesidad
de minimizar identificadores opacos antes de pedir prosa. No añadir un filtro de
la frase literal cerró correctamente. Captura cancel-action t18 había pasado;
esta segunda captura invalida cualquier afirmación de cancelación estable.
