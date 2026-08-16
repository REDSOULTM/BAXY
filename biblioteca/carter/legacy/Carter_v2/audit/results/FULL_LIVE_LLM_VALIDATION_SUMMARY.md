# Full Live LLM Validation -- Summary

## mode = `scripted` (model: scripted)
- totals: **654/654 pass**, fail=0, skipped=0
- hardware: vram_delta_mb=-239, ram_free_delta_mb=1517, duplicate_llm_load_prevented=False

| cat | name | total | pass | fail | skipped | p50_ms | p95_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| 1 | Conversación simple | 40 | 40 | 0 | 0 | 23 | 170 | 6842 |
| 2 | Identidad | 32 | 32 | 0 | 0 | 175 | 289 | 322 |
| 3 | Conocimiento general | 31 | 31 | 0 | 0 | 476 | 640 | 698 |
| 4 | Memoria y user_ref | 31 | 31 | 0 | 0 | 661 | 1049 | 1105 |
| 5 | Preferencias de estilo | 35 | 35 | 0 | 0 | 254 | 681 | 732 |
| 6 | Herramientas simples | 37 | 37 | 0 | 0 | 222 | 471 | 649 |
| 7 | Apps open/close | 33 | 33 | 0 | 0 | 194 | 635 | 820 |
| 8 | Web/browser | 36 | 36 | 0 | 0 | 280 | 490 | 599 |
| 9 | Filesystem seguro | 38 | 38 | 0 | 0 | 441 | 718 | 779 |
| 10 | Terminal | 37 | 37 | 0 | 0 | 229 | 517 | 549 |
| 11 | Safety/policy | 49 | 49 | 0 | 0 | 308 | 625 | 839 |
| 12 | Misiones compuestas | 40 | 40 | 0 | 0 | 804 | 1071 | 1287 |
| 13 | GUI/visión | 47 | 47 | 0 | 0 | 392 | 707 | 792 |
| 14 | Typos/ambigüedad | 46 | 46 | 0 | 0 | 153 | 349 | 523 |
| 15 | Latencia/placeholder | 30 | 30 | 0 | 0 | 24 | 85 | 286 |
| 16 | Multilingüe | 31 | 31 | 0 | 0 | 261 | 609 | 1005 |
| 17 | Follow-ups | 31 | 31 | 0 | 0 | 402 | 879 | 1298 |
| 18 | Regresión real | 30 | 30 | 0 | 0 | 195 | 885 | 887 |

## mode = `dry-run` (model: scripted)
- totals: **654/654 pass**, fail=0, skipped=0
- hardware: vram_delta_mb=0, ram_free_delta_mb=125, duplicate_llm_load_prevented=False

| cat | name | total | pass | fail | skipped | p50_ms | p95_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| 1 | Conversación simple | 40 | 40 | 0 | 0 | 35 | 244 | 3991 |
| 2 | Identidad | 32 | 32 | 0 | 0 | 252 | 416 | 554 |
| 3 | Conocimiento general | 31 | 31 | 0 | 0 | 601 | 840 | 887 |
| 4 | Memoria y user_ref | 31 | 31 | 0 | 0 | 872 | 1339 | 1469 |
| 5 | Preferencias de estilo | 35 | 35 | 0 | 0 | 358 | 829 | 1084 |
| 6 | Herramientas simples | 37 | 37 | 0 | 0 | 296 | 630 | 815 |
| 7 | Apps open/close | 33 | 33 | 0 | 0 | 270 | 759 | 947 |
| 8 | Web/browser | 36 | 36 | 0 | 0 | 379 | 643 | 774 |
| 9 | Filesystem seguro | 38 | 38 | 0 | 0 | 589 | 959 | 1192 |
| 10 | Terminal | 37 | 37 | 0 | 0 | 288 | 756 | 764 |
| 11 | Safety/policy | 49 | 49 | 0 | 0 | 415 | 857 | 1182 |
| 12 | Misiones compuestas | 40 | 40 | 0 | 0 | 1038 | 1369 | 1741 |
| 13 | GUI/visión | 47 | 47 | 0 | 0 | 532 | 966 | 995 |
| 14 | Typos/ambigüedad | 46 | 46 | 0 | 0 | 197 | 472 | 586 |
| 15 | Latencia/placeholder | 30 | 30 | 0 | 0 | 25 | 118 | 382 |
| 16 | Multilingüe | 31 | 31 | 0 | 0 | 339 | 689 | 805 |
| 17 | Follow-ups | 31 | 31 | 0 | 0 | 345 | 896 | 1159 |
| 18 | Regresión real | 30 | 30 | 0 | 0 | 164 | 842 | 869 |

## mode = `live-safe` (model: qwen3:8b)
- totals: **452/654 pass**, fail=3, skipped=199
- hardware: vram_delta_mb=6863, ram_free_delta_mb=-901, duplicate_llm_load_prevented=False

| cat | name | total | pass | fail | skipped | p50_ms | p95_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| 1 | Conversación simple | 40 | 40 | 0 | 0 | 450 | 1012 | 20857 |
| 2 | Identidad | 32 | 32 | 0 | 0 | 1442 | 2351 | 2746 |
| 3 | Conocimiento general | 31 | 31 | 0 | 0 | 4009 | 8856 | 13035 |
| 4 | Memoria y user_ref | 31 | 31 | 0 | 0 | 1548 | 4169 | 4608 |
| 5 | Preferencias de estilo | 35 | 35 | 0 | 0 | 1136 | 4607 | 8841 |
| 6 | Herramientas simples | 37 | 37 | 0 | 0 | 1303 | 3171 | 4814 |
| 7 | Apps open/close | 33 | 8 | 0 | 25 | 2578 | 6295 | 6295 |
| 8 | Web/browser | 36 | 0 | 0 | 36 | 0 | 0 | 0 |
| 9 | Filesystem seguro | 38 | 27 | 2 | 9 | 2516 | 4988 | 63588 |
| 10 | Terminal | 37 | 26 | 1 | 10 | 2321 | 11309 | 91711 |
| 11 | Safety/policy | 49 | 0 | 0 | 49 | 0 | 0 | 0 |
| 12 | Misiones compuestas | 40 | 21 | 0 | 19 | 3018 | 51122 | 67082 |
| 13 | GUI/visión | 47 | 0 | 0 | 47 | 0 | 0 | 0 |
| 14 | Typos/ambigüedad | 46 | 46 | 0 | 0 | 1553 | 3868 | 6041 |
| 15 | Latencia/placeholder | 30 | 30 | 0 | 0 | 373 | 619 | 811 |
| 16 | Multilingüe | 31 | 31 | 0 | 0 | 910 | 1444 | 4173 |
| 17 | Follow-ups | 31 | 31 | 0 | 0 | 924 | 1528 | 1915 |
| 18 | Regresión real | 30 | 26 | 0 | 4 | 728 | 2200 | 2823 |
