# NEXT_STEPS.md — Mejoras futuras para Carter OS v2

## Prioridad alta

### 1. Modelo mas capaz
- qwen3:14b es funcional pero tiene limitaciones en razonamiento complejo
- Evaluar qwen3:30b-a3b (MoE, ~20GB) si cabe en VRAM
- Evaluar devstral si hay mejoras en code generation
- Alternativa: conectar a un modelo cloud como fallback optional (opt-in)

### 2. Modo offline estricto
- Agregar flag `--offline` que bloquee acceso a internet desde el sandbox
- Implementar via firewall rules o proxy null en el subproceso
- Util para tareas sensibles donde no se quiere que el codigo generado haga requests

### 3. Streaming de respuesta del LLM
- Actualmente espera la respuesta completa
- Con streaming, se puede mostrar progreso y cancelar temprano
- Ollama soporta streaming nativamente

## Prioridad media

### 4. Sandbox AppContainer (Windows)
- El sandbox actual usa solo sanitizacion de env + cwd aislado
- AppContainer real daria aislamiento de filesystem y red
- Requiere elevacion de privilegios (admin)
- Dejar como opcion opt-in: `--sandbox-strict`

### 5. Vision con modelo multimodal
- Actualmente el prompt instruye a tomar screenshots con PIL
- Pero la vision requiere un modelo multimodal cargado en Ollama
- Evaluar: llava, bakllava, o qwen2-vl si caben en VRAM junto con qwen3

### 6. Memoria con embeddings ligeros
- El keyword overlap actual funciona pero no captura semantica
- Evaluar sentence-transformers con modelo tiny (~30MB)
- O usar TF-IDF con scikit-learn (ya instalado en muchos entornos)

### 7. Paralelizacion de tareas
- Actualmente Carter ejecuta una tarea a la vez
- Agregar modo "background task" donde una tarea siga corriendo
- Util para: descargas largas, builds, monitoring

## Prioridad baja

### 8. Voice stack (proyecto separado)
- Si se quiere voice, reimplementar como capa separada
- Whisper + VAD + pyttsx3 como minimo viable
- NO integrar en el core — mantener como plugin/extension

### 9. GUI web
- Si se necesita GUI, hacerla como app web local (Flask/FastAPI)
- WebSocket para streaming de logs y resultados
- NO CustomTkinter — demasiado acoplamiento

### 10. Plugin system
- Permitir que el usuario registre "context providers" custom
- Ej: un plugin que inyecte info de Docker, o de un cluster k8s
- Sin ser tools — solo informacion para el prompt
