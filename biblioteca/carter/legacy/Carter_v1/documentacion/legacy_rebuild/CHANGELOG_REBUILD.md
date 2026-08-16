# CHANGELOG_REBUILD.md — Registro de cambios del rebuild

## Fase 0 — Git y estructura
- Inicializado repositorio git
- Creado `.gitignore` para Python/Windows/modelos/logs
- Commit checkpoint del estado pre-rebuild
- Rama de trabajo: `rebuild/v2-from-scratch`

## Fase 1 — Auditoria y clasificacion
- Auditado proyecto viejo (Agente De Mastering): 30+ modulos, 59 tools, 577 tests, ~22K LOC
- Auditado proyecto nuevo (Carter v1): 3 archivos, prototype funcional
- Clasificado todo en A) Conservar, B) Reinterpretar, C) Eliminar
- Entregable: `documentacion/REBUILD_DECISIONS.md`

## Fase 2 — Arquitectura nueva desde cero

### system_prompt.py (reescrito)
- Prompt limpio con JSON estricto
- Reglas anti-fabricacion (buscar antes de inventar)
- Verificacion obligatoria (no mentir)
- Anti-loop documentado en prompt
- Vision bajo demanda

### dynamic_sandbox.py (reescrito)
- Ejecucion Python/PowerShell aislada
- Kill tree en Windows
- Entorno sanitizado sin secrets
- Deteccion de TASK_COMPLETE y SCREENSHOT_CAPTURED
- Max output con truncado inteligente

### carter_core.py (reescrito desde cero)
- Bucle OODA limpio
- Parser JSON de 3 capas con strip de <think> tags
- Anti-loop con deteccion de similitud
- Anti-mentira: rechaza TASK_COMPLETE sin verificacion
- Tracking de successes por tarea (no global)
- Integracion con memory, telemetry, vram_manager
- REPL con comando `stats` para telemetria
- UTF-8 forzado en Windows

### runtime_context.py (nuevo)
- Snapshot del sistema: OS, CPU, RAM, usuario, paths
- Deteccion de software instalado (Steam, Chrome, VS Code, Git, etc)
- Reemplaza el viejo sistema de 59 tools como contexto pasivo

### memory.py (nuevo)
- SQLite local para continuidad entre sesiones
- Categorias: task, fact, error, preference
- Busqueda por keyword overlap (sin embeddings pesados)
- Pruning automatico (max 500 entries)

### telemetry.py (nuevo)
- Metricas por tarea: ciclos, tiempo, errores, latencia LLM
- Historial acotado (ultimas 100 tareas)
- Deteccion de anomalias simples
- Thread-safe

### vram_manager.py (nuevo)
- Estados HOT/WARM/COLD sobre Ollama API
- Watchdog que detecta juegos activos
- Fix: steamwebhelper removido de indicadores (falso positivo)
- Eviccion por idle timeout (10 min)

## Fase 6 — Tests
- 50 tests de regresion cubriendo:
  - Parser JSON (9 tests)
  - Strip de think tags (3 tests)
  - Fix de JSON roto (5 tests)
  - Sandbox Python (4 tests)
  - Sandbox PowerShell (2 tests)
  - Aislamiento del sandbox (3 tests)
  - ExecutionResult (9 tests)
  - Anti-loop (5 tests)
  - Runtime context (2 tests)
  - Memoria local (4 tests)
  - Telemetria (3 tests)
  - VRAM manager (2 tests)
- Todos pasando: 50/50

## Fase 8 — Next Steps (prioridad alta y media)

### [ALTA] Modo offline estricto
- `--offline` flag en CLI bloquea HTTP/HTTPS desde el sandbox
- Implementado via proxy null (`HTTP_PROXY=http://0.0.0.0:0`) inyectado en el env del subproceso
- Elimina `REQUESTS_CA_BUNDLE` y `CURL_CA_BUNDLE` del env

### [ALTA] Streaming de respuesta del LLM
- `LLMClient.chat(stream=True)` usa `httpx.stream()` para recibir tokens SSE
- Imprime tokens en tiempo real: muestra `[CARTER pensando...]` durante el bloque `<think>`, luego el JSON
- `run_task()` usa stream=True por defecto

### [MEDIA] AppContainer opt-in (`--sandbox-strict`)
- Intenta lanzar subproceso en AppContainer de Windows via ctypes
- Fallback automatico al sandbox estandar si falla (sin admin / error de perfil)
- Con AppContainer: Job Object limita memoria a 512MB y mata el proceso al cerrar el job

### [MEDIA] Vision multimodal auto-deteccion
- `detect_vision_model()` consulta `/api/tags` de Ollama al inicio
- Busca por keywords: llava, bakllava, moondream, qwen2-vl, qwen2.5-vl, minicpm-v, cogvlm, internvl
- `--vision-model` flag para override manual
- Auto-configurado en `CarterCore.__init__` si `vision_model is None`

### [MEDIA] Memoria con TF-IDF ligero
- `memory.py` reemplaza keyword overlap con TF-IDF + similitud coseno
- Implementado con stdlib (`math`), sin dependencias externas
- IDF pondera terminos raros mas alto; similitud coseno rankea por relevancia real

### [MEDIA] Paralelizacion de tareas en segundo plano
- `run_task_background(input)` lanza tarea en hilo daemon, retorna `task_id` inmediatamente
- `get_background_task(task_id)` / `list_background_tasks()` para consultar estado
- REPL: comando `bg` lista tareas, `bg:<tarea>` lanza en segundo plano

## Fase 7 — Documentacion
- `REBUILD_DECISIONS.md` — Clasificacion A/B/C
- `NEW_ARCHITECTURE.md` — Modulos, flujo, decisiones
- `MIGRATED_GOOD_PARTS.md` — Lo rescatado y como cambio
- `REJECTED_OLD_PARTS.md` — Lo eliminado y por que
- `NEXT_STEPS.md` — Mejoras futuras priorizadas
- `CHANGELOG_REBUILD.md` — Este archivo
