# C02 — conductor ×2 en árbol de implementación y en clon

Perfiles nuevos: `%LOCALAPPDATA%\BAXY\comprobaciones-c02` y `…-c02-clone-{1,2}`. No se reutilizó el plan pendiente de C01.

Turnos (`launch.turns.jsonl`): saludo; `¿Qué hora es?` (lectura real). BAXY no recibió operación esperada.

| Corrida | ready | admission | llama_server | terminales | prosa hora |
|---|---|---|---|---|---|
| implementación 1 | true | 200 ≠ terminal | `%LOCALAPPDATA%\BAXYRuntime\assets\llama-b9980-cuda12.4` | published_final ×2 | FAIL de producto R01: «No pude: no pude encontrarlo.» |
| implementación 2 | true | 200 | mismo | published_final ×2 | mismo R01 |
| clon 1 | true | 200 | mismo | published_final ×2 | mismo R01 |
| clon 2 | true | 200 | mismo | published_final ×2 | mismo R01 |

Manifiesto adjunto: schema `baxy-mind-runtime-v1`, hashes GGUF/llama/python. Ninguna ruta bajo `Programacion\BAXY\`.

**Lectura real independiente (launch 1):** journal `system.time` `completed` `verified=true` `utc=2026-09-03T06:57:52.1829160+00:00` `localUtcOffsetMinutes=-240`. El texto visible contradice ese hecho: R01, no éxito de C02. Conservado para C03.

Comando:

```
powershell -ExecutionPolicy Bypass -File scripts/run_baxy_conductor.ps1 -Profile %LOCALAPPDATA%\BAXY\comprobaciones-c02 -TurnsFile artifacts/comprobaciones/C02/launch.turns.jsonl -Capture <dir> -TimeoutMs 180000
```
