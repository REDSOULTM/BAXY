# Fase 2 — Componentes por container (C4 Nivel 3)

> Un documento por container (o grupo de containers fuertemente relacionados).
> Cada uno tiene su propio diagrama Mermaid + tabla de componentes + tipos de
> interacción explícitos. Hallazgos de sobre-ingeniería se anotan en su lugar
> y se replican en `../_findings_seed.md`.

## Índice

| # | Archivo | Containers cubiertos | Por qué agrupados |
|--:|---|---|---|
| 01 | [observability.md](observability.md) | Event Bus + Tracing + Log Recorder + Telemetry | Los 3 sinks comparten el BUS; verlos juntos hace evidente la duplicación |
| 02 | [voice_loop.md](voice_loop.md) | Voice Loop | Subsistema cohesivo y autocontenido (paquete `voice/`) |
| 03 | [llm_lifecycle.md](llm_lifecycle.md) | LLM Lifecycle | `llama_server`, `llm_client`, `model_info`, `prewarm`, `multimodal`, `boot_progress` |
| 04 | [mission_verification.md](mission_verification.md) | Mission Outcome + Verification | Ambos son verifiers (per-mission vs per-tool); van juntos |
| 05 | [routing.md](routing.md) | Routing & Validation | Las 6 piezas que tocan `user_text` antes/después del LLM |
| 06 | [memory.md](memory.md) | Memory & Knowledge + Skills/Microagents/Personas | 3 memorias + 3 capas de prompt enrichment |
| 07 | [tools.md](tools.md) | Tools (Registry + Domain + Ops + Safety) | El monstruo. ToolRegistry (3 157 LOC, 142 métodos) merece doc propio |
| 08 | [agent_core.md](agent_core.md) | Agent Core | Depende de todos los anteriores |
| 09 | [surfaces.md](surfaces.md) | CLI + UI Desktop + UI Field + MCP Server | Las 4 superficies de entrada al agente |
| 10 | [state_config.md](state_config.md) | Sessions/Routines + State + Config/Profiles | Capa de configuración/persistencia transversal |

## Cómo leer estos diagramas

- **Cajas:** archivos o clases concretas.
- **Cajas con `( )`:** funciones puras (no clases).
- **Cajas con `[( )]`:** stores en disco (SQLite, JSON, JSONL).
- **Cajas con `(( ))`:** procesos hijos (subprocess externo).
- **Flechas sólidas:** llamada síncrona directa.
- **Flechas punteadas:** llamada asíncrona / lazy / opt-in.
- **Etiquetas en flechas:** tipo concreto de interacción (`call`, `event`, `pub/sub`, `queue`, `IO`, `subproc`).

## Hallazgos transversales

Sobre-ingeniería y duplicación detectada al escribir Fase 2, ordenada por
severidad. Cada hallazgo está además anotado en la sección correspondiente
de su `02_components/*.md` y en `../_findings_seed.md` para Fase 8:

1. **`ui/agent_thread.AgentWorker` vs `agent_runner.AgentRunner`** — dos
   clases para el mismo patrón "single-thread worker que serializa requests
   a Gemma4Agent sync". Confirmado por lectura: ambas tienen `submit()`,
   `stop()`, `_build_agent()`, queue interna, lazy build, health polling.
   Diferencia: una emite `pyqtSignal`, la otra publica al BUS. **Colapsable
   a una clase + dos adaptadores delgados**.
2. **3 sinks de "qué pasó en este turn"**: `tracing.TraceLogger` (Agent
   escribe directo a JSONL), `log_recorder.RECORDER` (BUS sync → 2 archivos
   por sesión), `telemetry.TelemetryStore` (BUS → SQLite, opt-in). Granos
   distintos pero solapan información.
3. **`safety.py` ≠ sandbox** — 67 LOC de chequeos pre-call; tools como
   `subprocess`, `shell`, `file_delete` corren en el proceso del agente.
4. **3 memorias + 3 capas de prompt enrichment + 6 piezas de routing** —
   no es redundancia (cada una tiene propósito distinto) pero es una
   superficie enorme para mantener.
