# MUSIC1090 — adjudicación de la raíz

## MUSIC1090 — estado vigente 2026-09-12T19:17:16.256353+00:00

Parcial: 4 aprobados, 0 fallidos, 8 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 189/742 | 553 | 0 | >=63 | 0/35 |

Procedencia de primeras altas: Al menos 61 primeras altas previas verificadas hoy: 28 Kiro y 33 retorno hasta1080. MUSIC1090 añade H0351 y H0567, total al menos 63; no se cuentan revalidaciones.

Siguiente acción: Registrar estos dos créditos ahora. Sellar MUSIC1091 con el registro actualizado: únicamente ocho objetos aún sin ejecutar1090, H0311 + dos variantes previous + cinco límites, sin repetir los cuatro aprobados. Música conserva la mayor masa abierta. MESSAGING1085 tiene diez literales, diez variantes y cinco límites sellados, con runner aislado y auxiliares listos para revisión raíz; arrancar después del último grupo directo de navegación. H0675 y efectos inciertos continúan aparcados. C03 activo, formal 3/11; sin suites, Fast ni Full por orden expresa del dueño.

Evidencia: `artifacts/comprobaciones/C03/MUSIC1090/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 89.16 s acumulados; pico GPU 3497.56 MiB; pico RAM 1582.75 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 3 | music1037-dev-06 | passed | Variante inglesa aprobada: avanzó al vecino correcto y publicó título, artista y estado fieles. | Aurora de cobre playing cerca de cero → Rio de cristal playing; invocación 26d94d6e-9e68-426b-9f0c-dc83b38d2dac completed, verified true, replayed false. La respuesta enumera Title, Artist y PlaybackStatus: playing. Formato escueto y técnico, pero comprensible, atiende la petición y coincide con operación, lectura posterior y UI; no exige la rúbrica una frase exacta. |
| 5 | music1086-dev-next-es | passed | Variante española aprobada: avanzó al vecino correcto y publicó sus datos observados. | Rio de cristal playing cerca de cero → Sendero azul playing; invocación 25a002ee-e85f-4e7b-a1f9-23a3f6a4af0f completed, verified true, replayed false. Final en español: Título, Artista y Estado de reproducción: playing. El término inglés del estado es poco natural, pero indica el estado real sin falsearlo; lectura posterior y UI coinciden. No se acredita sólo el efecto. |
| 1 | H0351 | passed | Cubierto: el literal ejecutó la siguiente canción y publicó resultado útil y fiel con dos variantes pertinentes aprobadas en este mismo candidato. | Aurora de cobre → Rio de cristal playing; invocación 357edf46-0873-4f88-be1a-ab09b29c3d55 completed, verified true, replayed false. Final identifica Rio de cristal, Original BAXY preparation composition y Estado de reproducción: reproduciéndose. Lectura posterior y UI coinciden. Pares 3 y 5 cambian idioma, formulación y pista de partida. |
| 2 | H0567 | passed | Cubierto: el literal ejecutó la siguiente canción y publicó resultado útil y fiel con dos variantes pertinentes aprobadas en este mismo candidato. | Rio de cristal → Sendero azul playing; invocación cb3bd7b4-8d47-403d-b607-9af61104afe5 completed, verified true, replayed false. Final identifica Sendero azul, Original BAXY preparation composition y Estado de reproducción: reproduciéndose. Lectura posterior y UI coinciden. Pares 3 y 5 cubren la misma conducta con idioma y formulación distintos. |

Recursos: 89.16 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1582.75 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. Los cambios espontáneos de canción o estado no acreditan efectos del producto. Los casos no ejecutados conservan sus datos y estado.
