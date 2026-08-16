# Setup óptimo de Ollama para Carter v4

Variables de entorno **del sistema Windows** (Properties → Environment Variables → System, **NO shell**) recomendadas por la investigación de optimización LLM (compass artifact 2ba2cceb, abril 2026).

> ⚠️ Estas variables afectan el **servicio Ollama**, no el cliente Python. Setearlas en el shell o en `Run_Carterv4.py` NO funciona — el servicio ya está corriendo. Hay que setearlas a nivel de SO y reiniciar Ollama tray.

## Variables recomendadas

```
OLLAMA_FLASH_ATTENTION   = 1
OLLAMA_KV_CACHE_TYPE     = q8_0
OLLAMA_KEEP_ALIVE        = 24h
OLLAMA_NUM_PARALLEL      = 1
OLLAMA_MAX_LOADED_MODELS = 2
OLLAMA_NEW_ENGINE        = 0
```

### Justificación por variable

| Variable | Valor | Razón |
|---|---|---|
| `OLLAMA_FLASH_ATTENTION` | `1` | Acelera atención ~10-20% en GPU. Default desactivado por compatibilidad con CPUs viejas. |
| `OLLAMA_KV_CACHE_TYPE` | `q8_0` | KV cache cuantizado a 8-bit. Libera ~0.6 GB en 8k context (f16: 1.18 GB → q8_0: 0.59 GB) sin pérdida perceptible para qwen3:4b. **NO usar `q4_0`** — degrada Qwen3-4B (GQA moderado, K-cache sensible). |
| `OLLAMA_KEEP_ALIVE` | `24h` | Modelo permanece residente. Latencia consistente. Carter setea `keep_alive=-1` por request, pero el default global ayuda con cold-starts. |
| `OLLAMA_NUM_PARALLEL` | `1` | Evita división de num_ctx entre slots. Carter es single-user single-turn, no necesita paralelismo. |
| `OLLAMA_MAX_LOADED_MODELS` | `2` | Permite VLM on-demand (qwen2.5-vl:3b) sin descargar el principal. Fase 2 GUI necesitará esto. |
| `OLLAMA_NEW_ENGINE` | `0` | **CRÍTICO**: el new go-runner regresa 5-10× en TTFT con Qwen3 (issues Ollama #11060, #12504). Mantener legacy. |

## Cómo aplicarlas en Windows 11

### Opción 1: GUI (recomendado para humanos)

1. `Win + R` → `sysdm.cpl` → tab **Advanced** → **Environment Variables...**
2. En **System variables** (panel inferior), click **New...** y agregar cada variable.
3. Click **OK** en todos los diálogos.
4. **Reiniciar Ollama**: tray icon → Quit → relanzar Ollama.
5. Verificar:
   ```
   curl http://127.0.0.1:11434/api/ps
   ```
   `expires_at` debe ser `0001-01-01T00:00:00Z` si keep_alive funcionó.

### Opción 2: PowerShell (one-shot)

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_FLASH_ATTENTION", "1", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_KV_CACHE_TYPE", "q8_0", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_KEEP_ALIVE", "24h", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_NUM_PARALLEL", "1", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_MAX_LOADED_MODELS", "2", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_NEW_ENGINE", "0", "User")
```

Después: cerrar Ollama tray y relanzarlo.

## Validar que funcionó

```bash
# 1. Confirmá que keep_alive está activo
curl http://127.0.0.1:11434/api/ps
# expires_at debe ser muy lejano (24h+) o "0001-01-01T00:00:00Z" (residente)

# 2. Confirmá que el engine es legacy (no new)
ollama --version
# Si dice "experimental new engine" o el log muestra "ollama runner",
# OLLAMA_NEW_ENGINE no se aplicó

# 3. Medí TTFT antes/después
python -c "
import time, urllib.request, json
t0 = time.time()
data = json.dumps({
    'model': 'qwen3:4b-instruct-2507-q4_K_M',
    'messages': [{'role':'user','content':'hola'}],
    'stream': False
}).encode()
r = urllib.request.urlopen(urllib.request.Request(
    'http://127.0.0.1:11434/api/chat', data=data,
    headers={'Content-Type':'application/json'}
), timeout=60)
elapsed = time.time() - t0
print(f'TTFT: {elapsed*1000:.0f}ms')
"
```

Esperado: TTFT < 800ms warm, < 2.5s cold. Si es >5s consistente, el engine new puede estar activo.

## Sampling parameters

Carter v4 ya aplica los sampling oficiales de Qwen3-Instruct-2507 en
`src/carter_v4/adapters/ollama.py` y `src/carter_v4/agent.py`:

```
temperature      = 0.7
top_p            = 0.8
top_k            = 20
min_p            = 0.0
presence_penalty = 1.0
repeat_penalty   = 1.0
num_predict      = 4096
stop             = ["<|im_end|>", "<|endoftext|>", "<|im_start|>"]
```

Estos van **en el body de cada request** (cliente), no en env vars.
