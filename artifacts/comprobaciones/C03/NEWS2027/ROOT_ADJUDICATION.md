# NEWS2027 — adjudicación de la raíz

## NEWS2027 — estado vigente 2026-09-21T14:03:34.564035+00:00

Parcial: 2 aprobados, 6 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 660/742 | 82 | 0 | >=636 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 636 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); NEWS2027 añade 0. No se cuentan revalidaciones.

Siguiente acción: NEWS2027: 8 ejecutados, 2 aprobados, 6 fallidos, 0 créditos (índices []). Siguiente: WEATHER2029/2031 (las ocho filas de clima restantes) y las tipadas de la Fase 5.

Evidencia: `artifacts/comprobaciones/C03/NEWS2027/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 348.25 s acumulados; pico GPU 3492.93 MiB; pico RAM 2539.16 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0033 | failed | Falló: buscó en la web, preguntó, o el final no citó titulares leídos con su fuente. | Turno ordinario: la lectura de titulares se completó y verificó; el final no se publicó (todos los borradores vetados); pins intactos. |
| 1 | H0374 | failed | Falló: buscó en la web, preguntó, o el final no citó titulares leídos con su fuente. | Turno ordinario: lectura verificada; final no publicado (borradores vetados); pins intactos. |
| 2 | H0509 | failed | Falló: buscó en la web, preguntó, o el final no citó titulares leídos con su fuente. | Turno ordinario: lectura verificada; final no publicado (borradores vetados); pins intactos. |
| 3 | news2027-dev-01 | failed | Falló: buscó en la web, preguntó, o el final no citó titulares leídos con su fuente. | Turno ordinario: lectura verificada; final no publicado (borradores vetados); pins intactos. |
| 4 | news2027-dev-02 | failed | Falló: buscó en la web, preguntó, o el final no citó titulares leídos con su fuente. | Turno ordinario: lectura verificada; final no publicado (borradores vetados); pins intactos. |
| 5 | news2027-dev-03 | failed | Falló: buscó en la web, preguntó, o el final no citó titulares leídos con su fuente. | Turno ordinario: lectura verificada; final no publicado (borradores vetados); pins intactos. |
| 6 | news2027-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | news2027-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 348.25 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2539.16 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
