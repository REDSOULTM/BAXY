# Requisitos técnicos de Carter v4

Lista simple de lo que necesita una PC para correr Carter v4 localmente.

## Sistema operativo
- **Windows 10/11** (recomendado Windows 11)
- Carter usa APIs Win32 (UIA, ctypes, mss, win32gui) para GUI tools y verifiers
- Linux/Mac: la lógica funciona pero las tools GUI están limitadas (no probado oficialmente)

## Hardware mínimo

### CPU
- Cualquier CPU moderno (Intel/AMD x86_64) — Carter no es CPU-bound
- Recomendado: 4 núcleos o más para buen multitasking durante misiones

### RAM
- Mínimo: **8 GB** (modo CPU-fallback con llama3.2:3b)
- Recomendado: **16 GB** (deja headroom para Ollama + Carter + apps que abre)

### GPU (opcional pero MUY recomendada)
Carter detecta VRAM y elige perfil automáticamente:

| VRAM | Perfil auto | Modelo | Latencia |
|------|-------------|--------|----------|
| Sin GPU | `cpu_fallback` | llama3.2:3b | 15-25s (degradada) |
| 6 GB | `low_vram_6gb` | qwen3:4b-instruct-2507 Q4_K_M | 360-700ms |
| 8 GB | `balanced_8gb` | qwen3:4b-instruct-2507 Q4_K_M | 360-700ms |
| 10 GB | `balanced_10gb` | qwen3:4b-instruct-2507 Q4_K_M | 360-700ms |
| 12 GB | `high_quality_12gb` | qwen3:4b-instruct-2507 Q4_K_M | 360-700ms |
| 16 GB | `high_quality_16gb` | qwen3:4b-instruct-2507 Q4_K_M | 360-700ms |
| 24 GB | `top_tier_24gb` | qwen3:30b-a3b-instruct-2507 (MoE) | 1.5-3s |

**Cualquier GPU NVIDIA con 6+ GB de VRAM va perfecto** (GTX 1060, RTX 2060, RTX 3050+, RTX 4060 Ti, etc.)

### Disco
- Mínimo: **10 GB libres** (modelo Ollama + dependencias Python + DB de memoria)
- Recomendado: **20 GB** si querés alternar entre modelos

## Software requerido

### 1. Python 3.10+
- Carter está testeado con **Python 3.10** y **3.13**
- Bajar de python.org o Microsoft Store

### 2. Ollama
- **Obligatorio** — corre el LLM local
- Bajar de [ollama.com](https://ollama.com)
- Después de instalar: `ollama pull qwen3:4b-instruct-2507-q4_K_M` (descarga ~2.5 GB)

### 3. Dependencias Python
```bash
pip install -r Carter_v4/requirements.txt
```
Las principales son:
- `requests` (HTTP a Ollama)
- `pyautogui` + `pywin32` + `mss` + `numpy` (GUI tools)
- `uiautomation` + `rapidfuzz` (UIA cascading)
- `paddleocr` (OCR fallback, opcional)
- `sentence-transformers` (embeddings memoria, opcional)

## Variables de entorno relevantes

Para mejor performance Ollama (recomendadas, opcionales):

```powershell
[System.Environment]::SetEnvironmentVariable('OLLAMA_FLASH_ATTENTION', '1', 'User')
[System.Environment]::SetEnvironmentVariable('OLLAMA_KV_CACHE_TYPE', 'q8_0', 'User')
[System.Environment]::SetEnvironmentVariable('OLLAMA_KEEP_ALIVE', '24h', 'User')
[System.Environment]::SetEnvironmentVariable('OLLAMA_NUM_PARALLEL', '1', 'User')
[System.Environment]::SetEnvironmentVariable('OLLAMA_MAX_LOADED_MODELS', '2', 'User')
```

Variables de Carter:
- `CARTER_V4_FULL_PERMS=1` — desactiva sandbox FS (autorización del dueño)
- `CARTER_V4_DISABLE_PLANNER=1` — desactiva planner-light (default OFF desde v9c)
- `CARTER_V4_DISABLE_SKILL_STORE=1` — desactiva skill_store
- `CARTER_V4_BLOCK_SHUTDOWN=1` — bloquea system_shutdown/reboot (Run_Carterv4.py lo setea por default)

## Cómo correrlo

```powershell
# Opción 1: launcher con perms del dueño
python Run_Carterv4.py

# Opción 2: módulo directo
cd Carter_v4
python -m carter_v4.cli --full-perms

# Opción 3: tests
cd Carter_v4
python -m pytest tests/ -q
```

## Multi-monitor

✅ Carter v4 es compatible con cualquier setup de monitores (1, 2, 3 o más):
- Captura virtual screen completo (todos los monitores juntos)
- Soporta coords negativas (monitor primario a la izquierda)
- Win32 SetCursorPos directo, no depende de pyautogui que rechaza coords negativas
- Threshold de frame-diff ajustado para resoluciones altas (3840×2160, etc.)

## Lo que NO necesita Carter
- ❌ Cuenta cloud (es 100% local)
- ❌ API keys de Anthropic/OpenAI/Google
- ❌ VLM (no procesa imágenes — usa UIA + OCR + estado Win32 para "ver")
- ❌ Internet permanente (solo para `web_*` tools cuando el usuario lo pide)
- ❌ Docker / WSL (corre nativo)

## Resumen del usuario típico
> "Tengo Windows 11, una RTX 3060 de 8GB, 16GB de RAM y Python 3.10. Instalo Ollama, hago `ollama pull qwen3:4b-instruct-2507-q4_K_M`, instalo las dependencias Python, y ejecuto `python Run_Carterv4.py`. Carter responde en menos de 1 segundo."

Eso alcanza para tener a Carter funcionando con experiencia tipo Alexa local.
