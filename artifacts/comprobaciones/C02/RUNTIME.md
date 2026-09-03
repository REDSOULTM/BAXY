# C02 — runtime declarado

## Manifiesto vivo (tras re-registro C02)

Ruta: `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json`
Schema: `baxy-mind-runtime-v1` (versionado, sin secretos).

| Activo | Ruta | SHA-256 |
|---|---|---|
| python | `%LOCALAPPDATA%\BAXYRuntime\python\mind-runtime-v1\Scripts\python.exe` | `0b471133e110cfb53a061cad528ce8e517d7b9ac41a0a396c39ad795a487fc14` |
| python_path | `BAXY Definitivo\src` | — |
| gguf | `D:\BAXYRuntime\assets\models\Qwen3-4B-Q4_K_M.gguf` | `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5` |
| llama_server | `%LOCALAPPDATA%\BAXYRuntime\assets\llama-b9980-cuda12.4\llama-server.exe` | `38a9d28ea414442590486459a7d1f5e32655db83148b7a114b79cd1ad242946e` |
| stt | `~\.gemma4\models\sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` | `5a70e0862ca0ed713a2bb1bfd50bf4886ae027815c8634a3800da7bdec6ab28f` |
| wake | `%LOCALAPPDATA%\BAXYRuntime\assets\wake\baxy-wakeword-v1.json` | `fefb95176c5db615e0d61b85744729fe242444697bc9c3315ad17a73fa3f6dfe` |
| tts | `~\.gemma4\models\piper\es_MX-claude-high.onnx` | `3ef40a71ea63852cd8ab7e6fa7d2ecdcfa67a0b47c9c48e3f10e02ee02083ea0` |

Antes: `llama_server` = `Programacion\BAXY\legacy\models\artifacts\llama-b9980\llama-server.exe`.
Copia byte a byte (mismo SHA) a LOCALAPPDATA y `D:\BAXYRuntime\assets\llama-b9980-cuda12.4`. El repositorio hermano no se modificó.

`assets.manifest.json` ya no lista `${REPOSITORY_ROOT}\legacy\...`. Candidatos: BAXY_ASSETS_ROOT, LOCALAPPDATA\BAXYRuntime, D:\BAXYRuntime, `~\.gemma4`.

## Aprovisionamiento de un clon limpio

1. `git clone` del commit publicado (sólo ficheros rastreados). `git config core.longpaths true` en la máquina.
2. `.\scripts\bootstrap.ps1` (dependencias; no descarga modelos).
3. Activos externos **declarados**: GGUF en `D:\BAXYRuntime\assets\models\`, llama-server en `%LOCALAPPDATA%\BAXYRuntime\assets\llama-b9980-cuda12.4` (o D:\ equivalente), Python runtime en `%LOCALAPPDATA%\BAXYRuntime\python`, STT/TTS en `~\.gemma4` si ya están.
4. `.\scripts\register_mind_runtime.ps1` — falla si llama/python/gguf/stt viven bajo `\BAXY\`.
5. No copiar la carpeta de desarrollo «hasta que funcione». No usar `Programacion\BAXY` como runtime.
