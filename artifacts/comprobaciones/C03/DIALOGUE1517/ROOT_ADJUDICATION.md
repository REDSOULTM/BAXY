# DIALOGUE1517 — adjudicación de la raíz

## DIALOGUE1517 — estado vigente 2026-09-15T02:16:57.827901+00:00

Parcial: 3 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 507/742 | 235 | 0 | >=381 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 381 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); DIALOGUE1517 añade 0. No se cuentan revalidaciones.

Siguiente acción: DIALOGUE1517: 6 ejecutados, 3 aprobados, 3 fallidos, 0 créditos (índices []); Entrada incompleta, ruido y control de diálogo 26/34. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/DIALOGUE1517/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 100.22 s acumulados; pico GPU 3497.56 MiB; pico RAM 1701.45 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0205 | failed | Falló: el validador rechazó la pregunta correcta del aclarador por un límite de palabra tras «refer» («referís») y el turno cayó en la aclaración genérica, que adivinó el referente sin decir que sólo llegó esa parte. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; la pregunta publicada salió de la recuperación genérica y adivinó el referente. |
| 1 | dialogue1517-dev-01 | failed | Falló: el validador rechazó la pregunta correcta del aclarador por un límite de palabra tras «refer» («referís») y el turno cayó en la aclaración genérica, que adivinó el referente sin decir que sólo llegó esa parte. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; la pregunta publicada salió de la recuperación genérica y adivinó el referente. |
| 2 | dialogue1517-dev-02 | failed | Falló: el validador rechazó la pregunta correcta del aclarador por un límite de palabra tras «refer» («referís») y el turno cayó en la aclaración genérica, que adivinó el referente sin decir que sólo llegó esa parte. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; la pregunta publicada salió de la recuperación genérica y adivinó el referente. |
| 3 | dialogue1517-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | dialogue1517-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | dialogue1517-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 100.22 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1701.45 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
