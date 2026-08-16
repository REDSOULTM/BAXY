# MIGRATED_GOOD_PARTS.md — Lo que se rescato del proyecto anterior

## Del proyecto viejo (Agente De Mastering)

### 1. VRAM Manager (HOT/WARM/COLD)
- **Original**: 300+ LOC con llama-cpp-python, deteccion de juegos, idle timeout
- **Nuevo**: ~200 LOC sobre Ollama API, misma logica de estados
- **Cambio**: Removido steamwebhelper de indicadores (falso positivo)
- **Archivo**: `vram_manager.py`

### 2. Memoria local SQLite
- **Original**: `rag_memory.py` con hash embeddings 384D
- **Nuevo**: `memory.py` con keyword overlap (mas simple, misma utilidad)
- **Cambio**: Sin embeddings vectoriales, usa interseccion de palabras normalizada
- **Archivo**: `memory.py`

### 3. Telemetria local
- **Original**: `monitor.py` con baseline training, anomaly detection
- **Nuevo**: `telemetry.py` con metricas por tarea y anomalias simples
- **Cambio**: Sin threads de sampling, solo metricas de tareas del agente
- **Archivo**: `telemetry.py`

### 4. App Discovery como Runtime Context
- **Original**: `app_discovery.py` + `software_launcher.py` con 59 tools, registry, manifests
- **Nuevo**: `runtime_context.py` — snapshot pasivo del sistema inyectado al prompt
- **Cambio**: No es un sistema de tools, es informacion para el LLM
- **Archivo**: `runtime_context.py`

### 5. Sanitizacion de entorno
- **Original**: En sandbox_manager.py con AppContainer
- **Nuevo**: En `dynamic_sandbox.py` con regex de variables sensibles
- **Cambio**: Sin AppContainer (requiere admin), mismo efecto practico
- **Archivo**: `dynamic_sandbox.py`

## Del proyecto nuevo (Carter v1)

### 6. Parser JSON tolerante de 3 capas
- `json.loads` -> `_try_fix_json` (escapa newlines en strings) -> `_extract_raw_code`
- Critico para LLMs locales que producen JSON roto

### 7. Anti-loop por similitud de propositos
- Compara los ultimos 3 propositos con overlap de palabras
- Inyecta mensaje forzando cambio de estrategia

### 8. Anti-mentira / verificacion obligatoria
- Rechaza TASK_COMPLETE sin ejecucion exitosa previa en la tarea actual
- Fuerza al LLM a verificar con codigo antes de declarar exito

### 9. Anti-fabricacion
- Instruye al LLM a buscar datos (App IDs, URLs, rutas) con codigo
- En vez de inventarlos, consulta APIs publicas o el sistema local

### 10. Strip de tags `<think>` de qwen3
- qwen3 emite razonamiento en `<think>...</think>` antes del JSON
- Se limpia automaticamente antes del parseo
