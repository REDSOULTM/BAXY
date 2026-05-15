---
name: glossary
triggers: ["que significa", "qué significa", "que es", "qué es", "definicion", "definición", "definir", "glossary", "vocabulario", "jerga", "siglas", "HKCR", "HKLM", "HKCU", "mmproj", "deeplink", "winget", "psutil", "pycaw", "WDDM", "GGUF", "llama.cpp", "llama-server", "MCP", "RAG", "embedding", "KV cache", "quantization", "Q4_K_M", "Q6_K", "VRAM"]
priority: medium
---

# Glossary (jerga técnica del proyecto)

Términos comunes que aparecen al usar Gemma 4 Agent y su entorno. Usar como
referencia para responder preguntas definicionales del usuario.

## Modelos y runtime

- **GGUF**: formato de archivo de modelos para llama.cpp (binario, cuantizado).
  Reemplazo de GGML. Sufijo típico: `.gguf`.
- **llama.cpp**: motor de inferencia C++ que corre modelos GGUF. Soporta CUDA,
  Metal, CPU.
- **llama-server**: binario HTTP de llama.cpp expone OpenAI-compatible API en
  puerto configurable (default Gemma 4 Agent: 8080).
- **mmproj**: archivo "multimodal projector" de llama.cpp. Proyecta tokens de
  imagen/audio al espacio del modelo de texto. Necesario para Gemma 4 vision.
- **KV cache**: caché de los key/value tensors del prefill. Permite reutilizar
  prefijo común entre turns sin recomputar.
- **prewarm**: enviar un mensaje sintético al boot para llenar el KV cache
  con el system prompt antes del primer turn real del usuario.

## Quantization

- **Q4_K_M**: cuantización de 4 bits "K-quant medium". Más rápido, menos
  calidad. ~5 GB para E4B.
- **Q5_K_M**: 5 bits. Mejor calidad que Q4. ~5.5 GB para E4B.
- **Q6_K**: 6 bits. Calidad casi nativa. ~7 GB para E4B.
- **UD-Q4_K_XL**: Unsloth Dynamic 4-bit "Pareto frontier" — calidad cerca de
  Q5 con tamaño cerca de Q4. ~4.77 GB.

## Windows Registry hives

- **HKCR**: `HKEY_CLASSES_ROOT` — asociaciones de archivos y URIs.
- **HKLM**: `HKEY_LOCAL_MACHINE` — config global del equipo (admin only).
- **HKCU**: `HKEY_CURRENT_USER` — config del usuario actual.

## Sistema y librerías

- **WDDM**: Windows Display Driver Model — reserva ~1.5 GB de VRAM para
  desktop incluso si no estás jugando. Cuenta al planear VRAM budget.
- **psutil**: librería Python para info de procesos/CPU/RAM sin spawn de
  PowerShell. ~30ms vs ~5s de tasklist.
- **pycaw**: librería Python para Core Audio Windows (volumen, mute).
- **win32gui**: pywin32 — APIs nativas de ventanas. EnumWindows ~10ms.
- **winget**: package manager oficial Windows. Install/uninstall apps.

## Patrones del agente

- **deeplink**: URI scheme tipo `steam://`, `spotify:`, `vscode://`. La forma
  más limpia de abrir apps específicas sin GUI.
- **MCP**: Model Context Protocol. JSON-RPC para que un agente exponga sus
  tools a otros. Carter, Goose, Cursor, Claude Desktop lo hablan.
- **RAG**: Retrieval-Augmented Generation. Buscar fragmentos relevantes
  antes de pasar al LLM. En Gemma 4 Agent: `knowledge(action=search)`.
- **embedding**: vector de ~384 dims que captura el significado de un texto.
  Gemma 4 Agent usa `multilingual-e5-small` para semantic router.

## Estados honestos del agente

- **COMPLETED**: la tool se ejecutó Y el verifier confirmó el efecto.
- **PARTIAL**: avanzó parcialmente; falta algo claro.
- **UNVERIFIED**: la tool dijo ok pero el verifier no pudo medir.
- **NEEDS_USER**: requiere aclaración / confirmación del usuario.
- **NEEDS_DEPENDENCY**: falta una dependencia (e.g. SoundVolumeView, Playwright).
- **FAILED**: la tool retornó error o el verifier midió divergencia.
- **BLOCKED**: el SO rechazó (UAC, permission denied, política).
