# Capturas launch C01 (esta sesión)

Comando (dos veces, mismo `launch.turns.jsonl`):

```powershell
py main.py --conductor --turns-file artifacts\comprobaciones\C01\launch.turns.jsonl --capture <dir> --timeout-ms 180000
```

| Corrida | PID | ready | t1 terminal | t2 terminal | userMessageCount final |
|---|---|---|---|---|---|
| scratch/launch-1 y `artifacts/comprobaciones/C01/launch-1` | 22740 | true | published_final | published_final | 2 |
| scratch/launch-2 y `artifacts/comprobaciones/C01/launch-2` | 52508 | true | published_final | published_final | 2 |

Ambas: `meta` con manifiesto `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json`, commit `b2505da8f15820f94e47d874a66e26a927ea2e9a`, perfil `comprobaciones-c01`, `admission` distinto de `terminal`. `status=accepted` no se tomó como final. Sesión continua (1 usuario → 2). Prosa no determinista; no se exige byte a byte.

El launcher espera a WinExe (`WaitForExit`). Sin eso el job mataba `Baxy.exe` tras escribir sólo `meta`.
