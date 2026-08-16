# Carter Model Storage Cleanup Plan

**Estado actual:** `~/.ollama/models` ocupa **97.45 GB**, disco C: tiene **64.15 GB libres**.
Política Carter: mantener **≥ 25 GB libres** para sistema + cache + nuevas pulls.

## Modelos a mantener (stack ganador post-tournament — see `MODEL_TOURNAMENT_REPORT.md`)

| modelo | tamaño | uso | perfil |
|---|---:|---|---|
| `qwen3:1.7b` | 1.4 GB | fallback CPU/iGPU/6GB | CPU/6GB |
| `qwen3:4b` | 2.6 GB | texto 6GB/8GB | 6/8 GB |
| `qwen3:8b` | 5.2 GB | texto baseline 10–16GB | 10/12/16 GB |
| `qwen3:14b` | 9.3 GB | texto power 16/24GB | 16/24 GB |
| `qwen2.5:32b` Q4 | 19 GB | razonamiento 24GB+ | 24 GB+ |
| `granite3.3:8b` | 4.9 GB | alternativa tools 8GB | 8/10 GB |
| `llama3.1:8b` | 4.9 GB | baseline tools | 10/12/16 GB |
| `qwen2.5-coder:14b` | 9.0 GB | on-demand código | 16/24 GB |
| `devstral:24b` | 14 GB | on-demand código agéntico | 24 GB+ |
| `qwen2.5vl:7b` | 6.0 GB | visión grounding | 12/16/24 GB |
| `minicpm-v` | 5.5 GB | visión + OCR ligero | 8/10/12 GB |
| `moondream` | 1.7 GB | visión ultra-ligero | 6/CPU |

**Total mantener:** ~83.5 GB.

## Modelos candidatos a borrar

| modelo | tamaño | razón | espacio liberado | restauración |
|---|---:|---|---:|---|
| `carter-base` | 9.3 GB | Variante custom de qwen3:14b sin métrica documentada y sin tag de origen reproducible. Reemplazada por `qwen3:14b` directo. | 9.3 GB | `ollama create carter-base -f Modelfile` desde backup en `Carter_v2/backups/` si existe. |
| `carter-fast` | 9.3 GB | Misma razón. | 9.3 GB | igual. |
| `llava-llama3:latest` | 5.5 GB | OCR/describe inferior a `minicpm-v`; redundante con `llava:7b` para describe. | 5.5 GB | `ollama pull llava-llama3` |
| `phi4:latest` | 9.1 GB | Sin tool-calling en Carter (catálogo `_NO_TOOLS_MODELS`). Sólo investigación. | 9.1 GB (opcional) | `ollama pull phi4` |
| `gemma3:12b` | 8.1 GB | Sin tool-calling para Carter; opciones VLM ya cubiertas por qwen2.5vl + minicpm-v. | 8.1 GB (opcional) | `ollama pull gemma3:12b` |

### Plan de limpieza por fases

**Fase A — borrado conservador (libera ~24.1 GB, no impacta Carter):**
```powershell
ollama rm carter-base
ollama rm carter-fast
ollama rm llava-llama3:latest
```
Disco libre estimado tras Fase A: **88.25 GB** ✓ permite pulls de `mistral-small:24b` o `gpt-oss:20b`.

**Fase B — opcional (libera 17.2 GB extra):**
```powershell
ollama rm phi4
ollama rm gemma3:12b
```
Solo si se confirma en M11 que no aportan valor. Marcar `KEEP` si se quieren mantener para experimentos visuales (gemma3:12b sí tiene visión nativa multimodal).

### Verificación

```powershell
# Antes
$before = (Get-ChildItem "$env:USERPROFILE\.ollama\models" -Recurse -File).Length | Measure-Object -Sum
"{0:N2} GB before" -f ($before.Sum/1GB)

# Tras Fase A
ollama list

# Después
$after = (Get-ChildItem "$env:USERPROFILE\.ollama\models" -Recurse -File).Length | Measure-Object -Sum
"{0:N2} GB after" -f ($after.Sum/1GB)
```

### Restauración (rollback de la limpieza)

Todos los modelos de Fase A y B son re-descargables desde el registry oficial.
**No se requiere backup binario.** Para `carter-base` / `carter-fast`, si se
recupera un Modelfile desde `Carter_v2/backups/` se puede reproducir; si no, la
recomendación es **adoptar `qwen3:14b` directo** (lo que estos custom envuelven).

## Política operativa post-cleanup

- Disco objetivo libre: **≥ 30 GB** sostenido.
- Cualquier nuevo pull debe verificar `Get-PSDrive C` antes y abortar si tras
  pull quedaría < 25 GB.
- `model_benchmark.py --auto-pull` honra esta regla por diseño.
