# NEW_ARCHITECTURE.md — Carter OS v2

## Filosofia

Zero predefined tools. 100% local. El LLM genera codigo crudo, lo ejecuta, observa el resultado, y replanifica.

## Modulos

```
carter_core.py        — Bucle OODA principal (usuario -> LLM -> sandbox -> feedback)
system_prompt.py      — Prompt maestro del agente (identidad, protocolo JSON, reglas)
dynamic_sandbox.py    — Ejecucion aislada de Python/PowerShell
runtime_context.py    — Snapshot del sistema para el LLM (no tools, solo info)
memory.py             — Memoria local SQLite (continuidad entre sesiones)
telemetry.py          — Monitor de rendimiento local
vram_manager.py       — Gestion HOT/WARM/COLD de VRAM para proteger juegos
```

## Flujo

```
Usuario escribe orden
    |
    v
CarterCore.run_task()
    |
    v
Construye historial + system prompt + contexto del sistema
    |
    v
LLM (qwen3:14b via Ollama, 100% local)
    |
    v
Parser JSON de 3 capas (json.loads -> fix_json -> regex)
    |
    v
Anti-loop: detecta repeticion de estrategia
    |
    v
Anti-mentira: rechaza TASK_COMPLETE sin verificacion
    |
    v
Sandbox ejecuta codigo aislado (Python/PowerShell)
    |
    v
Resultado -> feedback al LLM -> siguiente ciclo
    |
    v
TASK_COMPLETE con evidencia -> resultado al usuario
```

## Decisiones clave

| Decision | Razon |
|---|---|
| Sin tools predefinidos | El LLM genera TODO el codigo. Mas flexible, menos mantenimiento. |
| Ollama como runtime LLM | API HTTP simple, manejo de modelos, 100% local. |
| qwen3:14b como default | Mejor razonamiento que qwen2.5-coder, modo thinking, cabe en 16GB VRAM. |
| SQLite para memoria | Ligero, sin deps externas, suficiente para continuidad. |
| VRAM manager pasivo | Solo evicta cuando detecta juegos reales, no launchers. |
| Parser JSON tolerante | Los LLMs locales producen JSON roto. 3 capas de fallback lo manejan. |
| Anti-loop por similitud | Compara propositos con overlap de palabras. Detecta repeticion sin NLP pesado. |
| Verificacion obligatoria | TASK_COMPLETE rechazado sin evidencia real (ejecucion exitosa previa). |

## Dependencias del core

- `httpx` — Cliente HTTP para Ollama
- `sqlite3` — Memoria local (stdlib)
- `pytest` — Tests (dev only)

Todo lo demas lo instala el LLM bajo demanda con pip.
