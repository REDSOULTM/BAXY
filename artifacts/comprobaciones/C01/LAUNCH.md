# Capturas launch C01 contra `d6500f8`

```powershell
py main.py --conductor --turns-file artifacts\comprobaciones\C01\launch.turns.jsonl --capture <dir> --timeout-ms 180000
```

| Corrida | commit en meta | ready | t1 | t2 | userMessageCount |
|---|---|---|---|---|---|
| scratch/launch-1 y `artifacts/comprobaciones/C01/launch-1` | d6500f810dac26089873fa3df7ae44fc5b554470 | true | published_final | published_final | 2 |
| scratch/launch-2 y `artifacts/comprobaciones/C01/launch-2` | d6500f810dac26089873fa3df7ae44fc5b554470 | true | published_final | published_final | 2 |

Ambas: manifiesto `mind-runtime-v1.json`, `admission` ≠ `terminal`, sesión continua. El perfil persistente conservó `hasPendingPlan` (no se limpia a escondidas). La prosa repetida sobre «Nota: Informe de actividad» es fallo de producto, no del conductor.
