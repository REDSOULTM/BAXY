---
name: glossary
triggers: ["HKCR", "HKLM", "HKCU", "mmproj", "deeplink", "winget", "psutil", "pycaw", "WDDM", "GGUF", "llama.cpp", "llama-server", "embeddings", "quantization", "Q4_K_M", "Q5_K_M", "Q6_K", "VRAM", "GGML", "prewarm"]
priority: medium
---

# Glossary (jerga técnica del proyecto)

Referencia para preguntas definicionales del usuario.

## Modelos y runtime
- **GGUF**: formato de archivo de modelos cuantizados para llama.cpp (binario, `.gguf`). Reemplaza GGML.
- **llama.cpp**: motor de inferencia C++ que corre GGUF (CUDA/Metal/CPU).
- **llama-server**: binario HTTP de llama.cpp; expone API OpenAI-compatible (default Baxy: puerto 8080).
- **mmproj**: "multimodal projector" de llama.cpp; proyecta tokens de imagen/audio al espacio del texto. Necesario para Gemma 4 vision.
- **KV cache**: caché de los key/value del prefill; reutiliza prefijo común entre turns sin recomputar.
- **prewarm**: mensaje sintético al boot que llena el KV cache con el system prompt antes del 1er turn real.

## Quantization (tamaños para E4B)
- **Q4_K_M**: 4-bit "K-quant medium". Más rápido, menos calidad. ~5 GB.
- **Q5_K_M**: 5-bit. Mejor que Q4. ~5.5 GB.
- **Q6_K**: 6-bit. Calidad casi nativa. ~7 GB.
- **UD-Q4_K_XL**: Unsloth Dynamic 4-bit "Pareto frontier" — calidad cerca de Q5, tamaño cerca de Q4. ~4.77 GB.

## Windows Registry hives
- **HKCR** = `HKEY_CLASSES_ROOT`: asociaciones de archivos y URIs.
- **HKLM** = `HKEY_LOCAL_MACHINE`: config global del equipo (admin only).
- **HKCU** = `HKEY_CURRENT_USER`: config del usuario actual.

## Sistema y librerías
- **WDDM**: Windows Display Driver Model; reserva ~1.5 GB de VRAM para desktop aun sin jugar. Contar en VRAM budget.
- **psutil**: lib Python info procesos/CPU/RAM sin spawn de PowerShell (~30ms vs ~5s de tasklist).
- **pycaw**: lib Python para Core Audio Windows (volumen, mute).
- **win32gui**: pywin32; APIs nativas de ventanas (EnumWindows ~10ms).
- **winget**: package manager oficial Windows (install/uninstall apps).

## Patrones del agente
- **deeplink**: URI scheme (`steam://`, `spotify:`, `vscode://`); forma más limpia de abrir apps sin GUI.
- **MCP**: Model Context Protocol; JSON-RPC para exponer tools entre agentes. Lo hablan Baxy, Goose, Cursor, Claude Desktop.
- **RAG**: Retrieval-Augmented Generation; busca fragmentos relevantes antes del LLM. Aquí: `knowledge(action=search)`.
- **embedding**: vector ~384-dim que captura el significado de un texto. Baxy usa `multilingual-e5-small` para el semantic router.

## Estados honestos del agente
- **COMPLETED**: tool ejecutada Y verifier confirmó el efecto.
- **PARTIAL**: avanzó parcialmente; falta algo claro.
- **UNVERIFIED**: tool dijo ok pero el verifier no pudo medir.
- **NEEDS_USER**: requiere aclaración/confirmación del usuario.
- **NEEDS_DEPENDENCY**: falta una dependencia (e.g. SoundVolumeView, Playwright).
- **FAILED**: tool retornó error o verifier midió divergencia.
- **BLOCKED**: el SO rechazó (UAC, permission denied, política).
