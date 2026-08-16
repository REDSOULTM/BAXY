# Skipped Live Validation -- Summary

## mode = `web-live` (model: scripted)
- totals: **36/36 pass**, fail=0, skipped=0
- hardware: vram_delta_mb=57, ram_free_delta_mb=-2346, duplicate_llm_load_prevented=False, backend_reused=False
- safety: pre_pids=493, post_pids=485, pre_steam=1, steam_killed_by_us=0, delta_killed=43

| cat | name | total | pass | fail | skipped | p50_ms | p95_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| 8 | Web/browser | 36 | 36 | 0 | 0 | 2782 | 9139 | 24439 |

## mode = `compound-live` (model: scripted)
- totals: **19/19 pass**, fail=0, skipped=0
- hardware: vram_delta_mb=-6, ram_free_delta_mb=1010, duplicate_llm_load_prevented=False, backend_reused=False
- safety: pre_pids=485, post_pids=467, pre_steam=1, steam_killed_by_us=0, delta_killed=9

| cat | name | total | pass | fail | skipped | p50_ms | p95_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| 12 | Misiones compuestas | 19 | 19 | 0 | 0 | 3286 | 5762 | 6761 |

## mode = `gui-vision-live` (model: scripted)
- totals: **47/47 pass**, fail=0, skipped=0
- hardware: vram_delta_mb=106, ram_free_delta_mb=2738, duplicate_llm_load_prevented=False, backend_reused=False
- safety: pre_pids=467, post_pids=462, pre_steam=1, steam_killed_by_us=0, delta_killed=7

| cat | name | total | pass | fail | skipped | p50_ms | p95_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| 13 | GUI/visión | 47 | 47 | 0 | 0 | 2322 | 44757 | 54266 |

## mode = `steam-live` (model: scripted)
- totals: **4/4 pass**, fail=0, skipped=0
- hardware: vram_delta_mb=238, ram_free_delta_mb=-1596, duplicate_llm_load_prevented=False, backend_reused=False
- safety: pre_pids=462, post_pids=462, pre_steam=1, steam_killed_by_us=0, delta_killed=7

| cat | name | total | pass | fail | skipped | p50_ms | p95_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| 18 | Regresión real | 4 | 4 | 0 | 0 | 11005 | 43025 | 43025 |

## mode = `dry-run` (model: scripted)
- totals: **5/5 pass**, fail=0, skipped=0
- hardware: vram_delta_mb=0, ram_free_delta_mb=-59, duplicate_llm_load_prevented=False, backend_reused=False
- safety: pre_pids=445, post_pids=445, pre_steam=1, steam_killed_by_us=0, delta_killed=1

| cat | name | total | pass | fail | skipped | p50_ms | p95_ms | max_ms |
|---|---|---|---|---|---|---|---|---|
| 8 | Web/browser | 5 | 5 | 0 | 0 | 232 | 4285 | 4285 |
