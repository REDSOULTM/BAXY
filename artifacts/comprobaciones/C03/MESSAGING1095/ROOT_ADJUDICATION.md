# MESSAGING1095 — adjudicación de la raíz

## MESSAGING1095 — estado vigente 2026-09-12T20:26:29.4066558+00:00

Parcial: 10 aprobados, 2 fallidos, 12 sin ejecutar; 4 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 195/742 | 547 | 0 | >=69 | 0/35 |

Procedencia de primeras altas: Cota inferior: 28 primeras altas verificadas del relevo Kiro más 37 del retorno hasta MESSAGING1085. Sólo se añaden las altas nuevas de esta adjudicación, no revalidaciones.

Siguiente acción: Preparar y ejecutar DIALOGUE1093 (10 literales, 10 variantes, 5 límites), categoría disponible con 29 abiertos frente a 26 de mensajería tras estos cuatro créditos. Música e instalación conservan sus requisitos condicionados y reanudación documentada. MESSAGING1095 deja H0584 abierto por cambio de autor del contenido y el límite condicional 22 fallido por negativa improcedente; no repetirlos sin reparación pertinente. H0024 no fue admitido por la interrupción ambiental: preservar perfil/captura/flag de incertidumbre, no reutilizar. El resto de índices sin ejecutar conserva material para una continuación sellada. Sin suites/Fast/Full por instrucción expresa del dueño; C03 sigue activo, 3/11 formal.

Evidencia: `artifacts/comprobaciones/C03/MESSAGING1095/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 268.26 s acumulados; pico GPU 3497.56 MiB; pico RAM 1669.62 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 13; abortados antes de admisión: 1. Los abortos ambientales no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 9 | messaging1062-dev-01 | passed | La variante española conservó los datos presentes y pidió el canal que faltaba. | Aclaración útil y fiel; sin operaciones adicionales ni confirmaciones. |
| 10 | messaging1062-dev-02 | passed | La variante inglesa pidió el canal ausente y conservó la referencia al mensaje. | Aclaración útil y fiel, sin envío ni operaciones adicionales. |
| 0 | H0024 | not_executed | El literal no llegó a admitirse: reapareció un cliente de mensajería durante el arranque. | Caso sin ejecutar y sin crédito; la guarda detuvo los procesos de BAXY. Se conserva la evidencia de la interrupción ambiental. |
| 1 | H0108 | passed | Pidió el canal faltante para responder al destinatario. | La reparación produjo una aclaración útil; no inventó canal o envío ni realizó operaciones adicionales. |
| 2 | H0303 | passed | Pidió el canal faltante para el mensaje, en vez de devolver un error de interpretación. | La petición conservó su destinatario y produjo una aclaración útil. Sin operaciones adicionales ni confirmaciones. |
| 3 | H0408 | passed | Pidió el canal faltante y conservó el destinatario. | Aclaración útil, sin confundir el nombre con una orden de reproducción ni afirmar envío. |
| 4 | H0423 | passed | Pidió únicamente el canal que faltaba para responder. | Respuesta útil y fiel, sin operaciones adicionales ni afirmaciones de envío. |
| 5 | H0584 | failed | La aclaración cambió quién expresa el sentimiento del mensaje. | Preguntó por el canal, pero no conservó fielmente la atribución del contenido. No hubo envío ni operaciones adicionales. |
| 19 | messaging1062-boundary-01 | passed | Respetó la prohibición de enviar mensajes. | Acuse fiel de abstención y sin operaciones adicionales ni confirmaciones. |
| 20 | messaging1062-boundary-02 | passed | Diferenció correctamente redactar de enviar. | Respuesta conceptual útil; sin acceso a conversaciones ni operaciones adicionales. |
| 21 | messaging1062-boundary-03 | passed | Identificó correctamente el imperativo en la frase citada. | Respondió al análisis gramatical y no actuó sobre el contenido de la cita. |
| 22 | messaging1062-boundary-04 | failed | Dio una negativa de capacidad injustificada ante una declaración sobre el futuro. | No hubo operaciones adicionales, pero la respuesta no atendió fielmente el comentario condicional. |
| 23 | messaging1062-boundary-05 | passed | Produjo el borrador breve y cortés solicitado. | El texto quedó en la conversación; no hubo envío ni operaciones adicionales. |

Recursos: 268.26 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1669.62 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. La ausencia de clientes o de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
