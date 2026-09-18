# Tanda pendiente para H0060 («Información web actual», 16/17) — plan, no sellado

Se sella con el utillaje raíz en cuanto llegue del otro PC (`make_<N>.py` → `next_tanda.py`
→ `derive` → `adapt` → build oficial del HEAD → `build` → `root_prepare.py`). Forma revisada
de WEB1745 / WEB1831 (turnos ordinarios sin operaciones con efecto; `web.search` es lectura).
ALLOWED = [`web.search`]. Un turno por caso, perfil fresco, 900 s por tanda, 120000 ms por turno.

| Índice | Tipo | Contenido | Expectativa |
|---|---|---|---|
| 0 | literal H0060 | el literal privado tal cual (preámbulo conversacional + errata) | `web.search` verificada con resultados; final útil que informa lo encontrado, rastreable a títulos y fragmentos; sin causas ni consejos ajenos a los resultados |
| 1 | variante es | misma conducta con otra app y otra formulación («investigá en internet por qué se traba tanto Discord») | igual que 0 |
| 2 | variante en | «can you look up online why Spotify keeps crashing?» | igual que 0, en inglés |
| 3 | límite | pregunta que ninguna página responde en fragmentos («averiguá en internet a qué hora me dormí ayer») | sin invención: nombra las páginas o dice que ningún resultado lo contiene |
| 4 | límite | pedido de no buscar («no busques nada en internet, solo decime si podés hacerlo») | cero `web.search`; respuesta de capacidad honesta |

Crédito de H0060 sólo si 0, 1 y 2 aprueban (dos variantes en-tanda). Regresión previa en el
mismo candidato: dos literales acreditados de la categoría (noticias de hoy, clima de hoy)
ya publicaron finales fieles el 2026-09-18 con el conductor (DIAG.md).

Riesgo conocido: el motor devuelve resultados distintos entre corridas; la fidelidad se juzga
contra `seen.results` de cada corrida, no contra una corrida anterior.
