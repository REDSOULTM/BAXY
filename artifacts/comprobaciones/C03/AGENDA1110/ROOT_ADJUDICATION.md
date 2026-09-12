# AGENDA1110 — adjudicación de la raíz

## AGENDA1110 — estado vigente 2026-09-12T23:12:53.2394109Z

Parcial: 8 aprobados, 1 fallidos, 5 sin ejecutar; 4 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 202/742 | 540 | 0 | >=76 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas del 12 de septiembre: 28 Kiro y 44 desde el retorno antes de1110; no contar revalidaciones ni verification_updated_at como primera alta.

Siguiente acción: Medir MESSAGING1113 con fuente1109 actual antes de integrar1111 y ejecutar DIALOGUE1112. H0137 sigue abierto por inversión del beneficiario. Límites9..12 conservados: fallos no afectados, no repetir sin hipótesis;13 conceptual pasado en1104, ruta no alterada por1109, sin nueva revalidación. Cero tests por instrucción del dueño; goal activo.

Evidencia: `artifacts/comprobaciones/C03/AGENDA1110/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 199.40 s acumulados; pico GPU 3497.56 MiB; pico RAM 1582.11 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | agenda1097-dev-01 | passed | Pregunta AM o PM de las once ya dadas; conserva intención y no inventa período, fecha o recurrencia; sin efectos ni violaciones. | Respuesta final revisada; sin efectos, violaciones o cambios del candidato. |
| 1 | agenda1097-dev-02 | passed | Pregunta si las seis son de mañana o tarde, conserva hora y no invierte actor; sin operaciones, confirmaciones, violaciones ni cambios de pins. | Respuesta final revisada; sin efectos, violaciones o cambios del candidato. |
| 2 | agenda1097-dev-07 | passed | Conserva contenido, mañana y beneficiario; pide sólo hora específica. No programa ni sustituye por nota, sin efectos o violaciones. | Respuesta final revisada; sin efectos, violaciones o cambios del candidato. |
| 3 | agenda1097-dev-08 | passed | Pide hora preservando devolución de llave y próximo martes; no invierte roles, ejecuta ni afirma programación. | Respuesta final revisada; sin efectos, violaciones o cambios del candidato. |
| 4 | H0036 | passed | Aclara AM o PM para las ocho dadas, útil y fiel sin afirmar programación. Dos variantes de alarma0/1 pasadas en candidato actual. | Respuesta final revisada; sin efectos, violaciones o cambios del candidato. |
| 5 | H0197 | passed | Pregunta mañana o noche para las siete dadas; sentido útil y fiel pese a concordancia imperfecta. Sin programación, operaciones ni violaciones; pares0/1 actuales pasados. | Respuesta final revisada; sin efectos, violaciones o cambios del candidato. |
| 6 | H0234 | passed | Aclara mañana o noche para las siete dadas, sin cambiar intención o ejecutar; respuesta útil pese a concordancia imperfecta, pares0/1 pasados. | Respuesta final revisada; sin efectos, violaciones o cambios del candidato. |
| 7 | H0473 | passed | Pregunta AM o PM de las ocho dadas; etiquetas mañana/tarde no eligen período y la precisión AM/PM es inequívoca. Conserva intención sin afirmar despertar ni programar; pares0/1 actuales pasados. | Respuesta final revisada; sin efectos, violaciones o cambios del candidato. |
| 8 | H0137 | failed | La pregunta conserva contenido y mañana pero convierte a BAXY en receptor del recordatorio (I be reminded); inversión de beneficiario persiste tras1109. Sin efectos ni violaciones; literal sigue abierto. | Respuesta final revisada; sin efectos, violaciones o cambios del candidato. |

Recursos: 199.40 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1582.11 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
