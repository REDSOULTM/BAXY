# FunctionGemma — runtime (corre en llama.cpp, igual que Baxy)

**IMPORTANTE: este modelo se corre en llama.cpp.** Es el runtime que usamos en Baxy
para todos los GGUF — mismo binario, mismas convenciones. No usar Ollama/transformers
para el campo de prueba: alineá con llama.cpp para que lo que midas sea representativo.

## Modelo específico
- Archivo: **`model/functiongemma-270m-it-UD-Q8_K_XL.gguf`** (471 MB, ya copiado acá).
- Origen: `unsloth/functiongemma-270m-it-GGUF` (ungated), cuant dinámica **Q8_K_XL**.
- Base: `google/functiongemma-270m-it` (Gemma 3 270M fine-tuneado para function-calling).
- Alternativa más liviana: `functiongemma-270m-it-Q8_0.gguf` (292 MB) — la usamos menos.

## llama.cpp
- Binario que usamos en Baxy: `C:\llamacpp-cuda\bin\llama-server.exe`
- Build: **b9090-5757c4dcb** (el mismo que sirve el E2B de Baxy). Sirve para FunctionGemma.
- Si armás un build propio: clonar ggml-org/llama.cpp, CUDA on. Cualquier build reciente
  con soporte Gemma 3/4 anda.

## Comando de arranque (el que corrimos, medido)
```bash
C:\llamacpp-cuda\bin\llama-server.exe ^
  -m model\functiongemma-270m-it-UD-Q8_K_XL.gguf ^
  --port 8082 --host 127.0.0.1 ^
  --jinja -ngl 99 -c 32768 --no-webui
```
- `--jinja` : usa el chat-template embebido de FunctionGemma (formato `<start_function_call>`).
- `-ngl 99` : todas las 19 capas a GPU (es chico).
- `-c 32768`: **necesario** si le pasás muchos tools. Con `-c 8192` y los 31 schemas de
  Baxy da **HTTP 400** (overflow). Si narrowás con el router (~6 tools), podés bajar el ctx.

## VRAM (medido, RTX 4060 Ti, ctx 32K)
| componente | VRAM |
|---|---|
| pesos del modelo | **443 MiB** |
| KV cache | ~133 MiB |
| compute buffer | ~513 MiB |
| misc/output | ~56 MiB |
| **TOTAL** | **~1.1 GB** |

(Línea del log: `CUDA0 ... 1089 = 443 + 133 + 513) + 56`.) A ctx más chico baja bastante
(KV + compute escalan con el contexto). Convive de sobra con el E2B (~3.5 GB) en 6 GB.

## Gotchas al servir vía API OpenAI de llama.cpp (medidos)
1. **Rol `developer`** (no `system`) en el mensaje de sistema:
   `"You are a model that can do function calling with the following functions"`.
2. **Sampling**: `temperature=1.0, top_k=64, top_p=0.95` (Google). Con temp=0 a veces rechaza.
3. **stop**: pasar `"stop": ["<end_function_call>"]` en el body — si no, **se va en loop**
   repitiendo el call.
4. **El call sale en `content`, NO en `tool_calls`** (llama.cpp no parsea el formato propio
   de FunctionGemma). Hay que regexear:
   `<start_function_call>call:NOMBRE{param:<escape>valor<escape>}<end_function_call>`
5. Tools compuestos (enum action) andan SI la descripción es corta/limpia y los valores del
   enum son transparentes (`memory` sí, `cpu_ram_gpu` no).

## Re-descargar el GGUF (si hace falta)
```python
from huggingface_hub import snapshot_download
snapshot_download("unsloth/functiongemma-270m-it-GGUF",
                  allow_patterns=["*UD-Q8_K_XL.gguf"], local_dir="model")
```

## Ejemplo mínimo de request (curl)
```bash
curl -s http://127.0.0.1:8082/v1/chat/completions -H "Content-Type: application/json" -d '{
  "messages":[{"role":"developer","content":"You are a model that can do function calling with the following functions"},
              {"role":"user","content":"what time is it"}],
  "tools":[{"type":"function","function":{"name":"system","description":"Get system info","parameters":{"type":"object","properties":{"action":{"type":"string","enum":["time","memory","battery"]}},"required":["action"]}}}],
  "temperature":1.0,"top_k":64,"top_p":0.95,"max_tokens":80,"stop":["<end_function_call>"]
}'
# -> content: "<start_function_call>call:system{action:<escape>time<escape>}"
```
