# Stack 2: TabbyAPI + Carter

Objetivo: usar `TabbyAPI/ExLlamaV2` como cerebro textual y mantener la vision separada en `Ollama + MiniCPM-V`.

## Requisitos

- GPU NVIDIA con VRAM suficiente
- Un modelo compatible con TabbyAPI en formato `EXL2`, `EXL3`, `GPTQ` o `FP16`
- Python 3.10+

## Launcher

Se incluyo [start_stack2_tabby.ps1](/c:/Users/usuario/Desktop/ETC/Programacion/Carter%20OS%20AI/start_stack2_tabby.ps1).

Ejemplo:

```powershell
.\start_stack2_tabby.ps1 `
  -InstallDeps `
  -ModelDir "D:\Modelos\Tabby" `
  -ModelName "Qwen3-14B-EXL2" `
  -Port 5000
```

Eso:

- clona `TabbyAPI` en `.runtime/tabbyAPI` si no existe
- crea `config_carter_stack2.yml`
- opcionalmente instala dependencias `.[cu12]`
- lanza TabbyAPI con logs en `backend_compare_logs/`

## Carter con Stack 2

Ejemplo de arranque:

```powershell
python carter_core.py `
  --backend openai `
  --url http://127.0.0.1:5000/v1 `
  --model Qwen3-14B-EXL2 `
  --vision-backend ollama `
  --vision-url http://127.0.0.1:11434 `
  --vision-model minicpm-v:latest `
  --no-auto-profile
```

## Notas

- El cerebro textual y el ojo ya pueden usar runtimes distintos.
- `UIA-first` ya esta integrado en Carter, por lo que la vision debe activarse solo cuando accesibilidad no alcanza.
- Si TabbyAPI no tiene un modelo cargado al inicio, Carter necesitara que el `model_name` que envias coincida con el modelo cargado por Tabby.
