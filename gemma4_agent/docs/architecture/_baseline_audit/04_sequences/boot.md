# 04.01 — Cold boot del agente

> Cuándo: primera invocación de `AgentRunner.submit()` (UI Field) o
> `python -m gemma4_agent.ui` (UI Desktop) o `python -m gemma4_agent.chat`.
> **Fuente:** `agent_runner.py:155-413` + `ui/main_window.py:81-183` + `chat.py`.
> Caso peor medido: 30-90 segundos (dominado por `load_tensors` del llama-server).

## Fig 4.01 — Boot completo (UI Field path)

```mermaid
sequenceDiagram
    autonumber
    participant U as Usuario
    participant UF as ui_field React
    participant SR as server.py FastAPI
    participant AR as AgentRunner
    participant PRF as profiles.get_active_profile
    participant LSM as LlamaServerManager
    participant LP as llama-server.exe
    participant LT as LlamaLogTail (thread)
    participant BUS as EventBus
    participant SemR as semantic_router (BG thread)
    participant AG as Gemma4Agent
    participant LLC as LLMClient

    U->>UF: abre URL
    UF->>SR: GET /
    UF->>SR: WS /events (subscribe)
    SR->>BUS: queue subscribe
    U->>UF: typea primer mensaje
    UF->>SR: POST /turn
    SR->>AR: submit(text)
    AR->>AR: start() lazy build thread

    Note over AR: _build_agent() empieza
    AR->>BUS: pub agent built=false healthy=false ready=false
    AR->>PRF: get_active_profile()
    PRF-->>AR: Profile(name=balanced ...)
    AR->>LSM: profile.server_running?
    alt standby profile
        AR->>BUS: pub llama_skipped
    else server already on :8080
        AR->>BUS: pub STAGE_LISTENING (external)
    else needs spawn
        AR->>BUS: pub STAGE_SPAWN
        AR->>LT: LlamaLogTail.start() (BG thread)
        AR->>LSM: start(profile, wait_health=True, timeout=120s)
        LSM->>LP: Popen(llama-server.exe --model X --ctx Y --port 8080)
        LP-->>LT: stderr log lines
        LT->>BUS: pub STAGE_METADATA, LAYERS, OFFLOAD(progress%), LISTENING
        LSM->>LSM: _wait_for_health(120s)
        LSM->>LP: GET /health (poll)
        LP-->>LSM: 200 OK (binary bound, NOT necessarily ready)
        LSM-->>AR: "started"
        AR->>BUS: pub STAGE_HEALTH progress=100
        AR->>AR: register vision_relaunch callback
    end

    Note over AR: build de Gemma4Agent
    AR->>AG: Gemma4Agent(config)
    AG->>AG: __init__:<br/>MemoryStore + AgentState + LLMClient<br/>+ ToolRegistry + ExperienceMemory + TraceLogger<br/>+ persona + skill cache slots + microagent cache
    AG-->>AR: instance
    AR->>BUS: pub agent built=true healthy=false ready=false

    Note over AR,SemR: BG: warmup del semantic_router en paralelo
    AR->>SemR: Thread(_bg_warmup_router)
    SemR->>SemR: _ensure_loaded(tool_names)
    Note over SemR: descarga + load MiniLM (~120MB) + embed 62 tools (~6-8s)
    SemR->>BUS: pub rerank_load progress=100

    AR->>LLC: client.health()
    LLC->>LP: GET /health
    LP-->>LLC: 200
    LLC-->>AR: True

    Note over AR,LP: Warmup: 1-token completion forzar load_tensors
    AR->>BUS: pub llama_warmup
    AR->>LLC: chat([{role:user,content:'.'}], max_tokens=1, timeout=180s)
    LLC->>LP: POST /v1/chat/completions
    LP->>LP: load_tensors (puede tardar 30-90s)
    LP-->>LLC: choices[0].message.content="…"
    LLC-->>AR: response dict

    alt prewarm enabled (default)
        AR->>AR: build system_prompt (CORE+TOOL_RULES+memory.prompt_summary)
        AR->>LLC: prewarm_kv(client, system_prompt, max_tokens=1, timeout=90s)
        LLC->>LP: POST con system_prompt entero
        LP-->>LLC: 1 token (KV cache caliente para próximo turn)
        AR->>BUS: pub prewarm_done elapsed=X
    end

    AR->>AR: _warmed_up = True
    AR->>BUS: pub agent built=true healthy=true ready=true
    AR->>BUS: pub state=ready

    Note over AR: ahora draina la cola de turns
    AR->>AG: run_text(text del primer mensaje)
    Note over UF: el WS empieza a recibir activity events
```

## Lo que pasa en `ui/main_window.py` (versión PyQt) es MUY parecido

`ServerBootWorker.run` (`ui/main_window.py:81-183`) hace **la misma secuencia**
con `pyqtSignal` en lugar de BUS. Mismo orden, mismas etapas, distinto
reporter. Ya documentado como duplicación en surfaces.md.

## Lo que pasa en `chat.py` es MUCHO MÁS SIMPLE

- Si pasás `--start-server`, llama a `LlamaServerManager.start` directo (sin tail).
- Construye `Gemma4Agent(config)` síncrono.
- No hay warmup, no hay prewarm, no hay router pre-load. El primer turn pagará.
- Spinner ANSI corre en main thread.

## Hallazgos a `_findings_seed.md`

- **`_autostart_llama_server` (agent_runner) ≡ `ServerBootWorker.run` (PyQt)** — ya en findings.
- **`_build_agent` en `agent_runner.py` mete 7 fases serializadas + 1 paralela en un solo método de 150+ LOC** (HIGH). Posible refactor: extraer cada fase a un método dedicado para que sea testeable.
- **Warmup con `messages=[{role:user,content:'.'}]`** — el "." como input neutro funciona pero es frágil. Si Gemma cambia su interpretación de tokens cortos, se rompe silenciosamente. Considerar warmup explícito con sentinel.
- **Prewarm corre con `max_tokens=1` pero pasa el system_prompt entero** (~46 KB para 62 tools). Esto carga el KV cache pero el server tiene que parsear tools y schemas — eso ya estaba documentado, OK.
- **Si profile=standby**, el agente queda construido pero NO ready (`llama_skipped`). Las superficies tienen que entender ese estado intermedio. ¿Lo testea alguien? Verificar en Fase 7.
