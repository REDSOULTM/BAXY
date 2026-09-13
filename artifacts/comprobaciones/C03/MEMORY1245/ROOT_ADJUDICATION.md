# MEMORY1245 — adjudicación de la raíz

## MEMORY1245 — estado vigente 2026-09-13T19:56:32.461937+00:00

Parcial: 6 aprobados, 10 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 334/742 | 408 | 0 | >=208 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 205 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; MEMORY1245 añade 3. No se cuentan revalidaciones.

Siguiente acción: MEMORY1245 completa: 16 ejecutados, 7 aprobados, 9 fallidos, 3 créditos (H0226, H0337, H0667: afirmaciones personales acusadas sin persistir) con sus dos pares. Memoria personal queda 3/10. Causa medida de los 8 fallos de guardado: la memoria privada está desactivada en un perfil fresco (memory_disabled) y la App pide confirmar la activación; esa confirmación es de la App, no del kernel, y el instrumento de un turno no la responde. Siguiente: MEMORY1247 con un comando de host `turn.memory-confirm` (host y runner de dos fases) para H0157, H0149, H0452, H0506; recuerdos (H0604, H0173) siguen fuera (perfil fresco sin nada que recordar); H0174 falló en el modelo.

Evidencia: `artifacts/comprobaciones/C03/MEMORY1245/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 257.34 s acumulados; pico GPU 3497.56 MiB; pico RAM 1923.91 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 16; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0157 | failed | Falló: la memoria privada está desactivada en un perfil fresco y la activación exige una confirmación que el instrumento de un turno no da. | Final publicado (pregunta de activación); memory.save fallida con memory_disabled (perfil fresco: memoria privada desactivada por defecto); el runner detuvo el caso al ver la composición de confirmación (violación registrada, exit 15); pins intactos. |
| 1 | H0149 | failed | Falló: la memoria privada está desactivada en un perfil fresco y la activación exige una confirmación que el instrumento de un turno no da. | Final publicado (pregunta de activación); memory.save fallida con memory_disabled (perfil fresco: memoria privada desactivada por defecto); el runner detuvo el caso al ver la composición de confirmación (violación registrada, exit 15); pins intactos. |
| 2 | H0452 | failed | Falló: la memoria privada está desactivada en un perfil fresco y la activación exige una confirmación que el instrumento de un turno no da. | Final publicado (pregunta de activación); memory.save fallida con memory_disabled (perfil fresco: memoria privada desactivada por defecto); el runner detuvo el caso al ver la composición de confirmación (violación registrada, exit 15); pins intactos. |
| 3 | H0506 | failed | Falló: la memoria privada está desactivada en un perfil fresco y la activación exige una confirmación que el instrumento de un turno no da. | Final publicado (pregunta de activación); memory.save fallida con memory_disabled (perfil fresco: memoria privada desactivada por defecto); el runner detuvo el caso al ver la composición de confirmación (violación registrada, exit 15); pins intactos. |
| 4 | H0226 | passed | Acusó el dato sin persistirlo ni prometer memoria; dos pares aprobados. | Final publicado; ninguna operación de memoria; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0337 | passed | Acusó el dato sin persistirlo ni prometer memoria; dos pares aprobados. | Final publicado; ninguna operación de memoria; cero confirmaciones y violaciones; pins intactos. |
| 6 | H0667 | passed | Acusó el dato sin persistirlo ni prometer memoria; dos pares aprobados. | Final publicado; ninguna operación de memoria; cero confirmaciones y violaciones; pins intactos. |
| 7 | H0174 | failed | Falló: tomó la afirmación como un pedido y preguntó un lugar. | Final publicado; ninguna operación de memoria; cero confirmaciones y violaciones; pins intactos. |
| 8 | memory1245-dev-01 | failed | Falló: la memoria privada está desactivada en un perfil fresco y la activación exige una confirmación que el instrumento de un turno no da. | Final publicado (pregunta de activación); memory.save fallida con memory_disabled (perfil fresco: memoria privada desactivada por defecto); el runner detuvo el caso al ver la composición de confirmación (violación registrada, exit 15); pins intactos. |
| 9 | memory1245-dev-02 | failed | Falló: la memoria privada está desactivada en un perfil fresco y la activación exige una confirmación que el instrumento de un turno no da. | Final publicado (pregunta de activación); memory.save fallida con memory_disabled (perfil fresco: memoria privada desactivada por defecto); el runner detuvo el caso al ver la composición de confirmación (violación registrada, exit 15); pins intactos. |
| 10 | memory1245-dev-03 | failed | Falló: la memoria privada está desactivada en un perfil fresco y la activación exige una confirmación que el instrumento de un turno no da. | Final publicado (pregunta de activación); memory.save fallida con memory_disabled (perfil fresco: memoria privada desactivada por defecto); el runner detuvo el caso al ver la composición de confirmación (violación registrada, exit 15); pins intactos. |
| 11 | memory1245-dev-04 | failed | Falló: la memoria privada está desactivada en un perfil fresco y la activación exige una confirmación que el instrumento de un turno no da. | Final publicado (pregunta de activación); memory.save fallida con memory_disabled (perfil fresco: memoria privada desactivada por defecto); el runner detuvo el caso al ver la composición de confirmación (violación registrada, exit 15); pins intactos. |
| 12 | memory1245-dev-05 | passed | Variante original aprobada: acusó el dato sin persistirlo. | Final publicado; ninguna operación de memoria; cero confirmaciones y violaciones; pins intactos. |
| 13 | memory1245-dev-06 | passed | Variante original aprobada: acusó el dato sin persistirlo. | Final publicado; ninguna operación de memoria; cero confirmaciones y violaciones; pins intactos. |
| 14 | memory1245-boundary-01 | failed | Límite fallido: describió mal cómo recuerda. | Final publicado; ninguna operación de memoria; cero confirmaciones y violaciones; pins intactos. |
| 15 | memory1245-boundary-02 | passed | Límite aprobado: usó el nombre sin guardarlo. | Final publicado; ninguna operación de memoria; cero confirmaciones y violaciones; pins intactos. |

Recursos: 257.34 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1923.91 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
