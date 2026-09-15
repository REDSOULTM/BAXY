# INSTALL1617 — ejecutada en parte, no adjudicable por su instrumento sellado

Fecha: 2026-09-16. Candidato BUILD1617 (HEAD 8f33d2f8: Kernel+Core+Providers+mente — lectura `game.entitlement.named` de la biblioteca autenticada de Steam y de los manifiestos; la mente la decide para «descarga/instala/desinstala X en steam»). Panel sellado de 19 casos: 15 literales de «Instalar y desinstalar software» (descargas, instalaciones y desinstalaciones de juegos nombrados en Steam), 2 variantes y 2 límites.

## Qué ocurrió

1. Casos 0–10 (once literales): la lectura se decidió, se completó y se verificó (ninguno de los títulos figura en la biblioteca del dueño; los títulos no se publican), y el modelo redactó exactamente el final buscado («<juego> no está en tu biblioteca, así que no puedes descargarlo ni instalarlo»). El compositor rechazó todos los borradores con `missing_name`: su comprobación genérica de título exige la palabra «título» cuando el resultado trae un campo `title`. Los once casos terminaron en `no_response`.
2. La raíz editó `src/baxy_mind/llm.py` durante la ejecución (exención de la lectura de biblioteca en esa comprobación). Error de disciplina de la raíz: el runner sellado detuvo el caso 11 con `sealed_input_or_source_changed` (EXIT 15, `pins_unchanged: false`) y rehusó los casos 12–18 antes de admitirlos.
3. El adjudicador sellado rechaza el conjunto: exige veredicto para todo segmento existente y el segmento 11 tiene pins cambiados («Segment pins changed»). No hay ROOT_ADJUDICATION ni REGISTRY_UPDATE; registro sin cambio (551/742).

## Decisión de raíz

El instrumento sellado no se modifica después del sellado. INSTALL1617 queda ejecutada en parte sin adjudicación: **0 créditos**. La medición vale como orientación: la lectura y la decisión funcionan; el único defecto observado es el veto genérico de título del compositor, exento para `game.entitlement.named` en INSTALL1619, que reejecuta el mismo panel con las fuentes intactas durante la ejecución.

Sin pruebas por instrucción expresa del dueño.
