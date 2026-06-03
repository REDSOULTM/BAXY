# 03.01 — Observability (clases UML)

> **Container:** Observability.
> **Archivos:** `events_bus.py`, `tracing.py`, `log_recorder.py`, `telemetry.py`.

## Fig 3.01 — Observability

```mermaid
classDiagram
    class EventBus {
        _subscribers: set[Queue]
        _listeners: list[Callable]
        _lock: Lock
        subscribe() Queue
        unsubscribe(q)
        add_listener(fn)
        remove_listener(fn)
        publish(event)
        subscriber_count() int
    }
    note for EventBus "99 LOC · 7 métodos públicos\nMÍNIMO HONESTO — mantener tal cual"

    class TraceLogger {
        path: Path
        enabled: bool
        new_turn_id() str
        event(turn_id, kind, **payload)
    }
    note for TraceLogger "@dataclass · 67 LOC\nINVOCADO DIRECTAMENTE por Gemma4Agent\n(no via BUS) — DUPLICA con LogRecorder"

    class LogRecorder {
        _lock: RLock
        _session_id: str
        _session_label: str
        _dir: Path
        _full: TextIO
        _chat: TextIO
        _installed: bool
        install()
        uninstall()
        current_session() str
        _switch_to(session_id, label)
        _close_handles()
        _write_full(payload)
        _write_chat(src, msg, ts)
        _on_event(event)
        _handle(event)
    }
    note for LogRecorder "220 LOC · 10 métodos\nSingleton RECORDER\nEscucha BUS sync → 2 archivos por sesión"

    class TelemetryStore {
        _db_path: Path
        _lock: RLock
        _enabled: bool
        _bus_listener_attached: bool
        _init_done: bool
        enable_if_configured() bool
        disable()
        enabled: bool [property]
        record_turn(ttft_ms, tokens, tps, vram, ...)
        record_session(kind, profile, payload)
        record_voice(kind, duration, rtf, ...)
        record_incident(kind, severity, payload)
        rotate(keep_days) int
        summarize_last_24h() dict
        export_json(dst) dict
        _ensure_initialized() bool
        _connect() Connection
        _init_schema(conn)
        _on_bus_event(event)
    }
    note for TelemetryStore "443 LOC · 15 métodos [GOD]\nSingleton TELEMETRY (se construye en IMPORT)\nOpt-in GEMMA4_TELEMETRY=1 default OFF"

    EventBus --o LogRecorder : sync listener
    EventBus --o TelemetryStore : sync listener (if enabled)
    EventBus --o "ui.bus_bridge.EventBusBridge" : sync listener
    EventBus --o "server.WS /events" : queue subscribe

    Gemma4Agent ..> TraceLogger : DIRECT call (bypassa BUS)
    Gemma4Agent ..> EventBus : pub
```

## Veredictos

| Clase | LOC | Métodos | Marca | Veredicto |
|---|--:|--:|---|---|
| `EventBus` | 99 | 7 | — | **mantener tal cual.** Diseño honesto, API mínima. |
| `TraceLogger` | 67 | 2 | `[DUP]` con `LogRecorder/full.log` | **eliminar** y migrar Gemma4Agent a publicar al BUS. Ahorro: 67 LOC + un canal de IO menos. |
| `LogRecorder` | 220 | 10 | — | mantener. Es el "sink" honesto que justifica el BUS sync listener. |
| `TelemetryStore` | 443 | 15 | `[GOD]` | **reducir radicalmente o eliminar.** 4 tablas + 12 índices + WAL + housekeeping para feature opt-in que probablemente nadie usa. Si vale, 1 tabla flat alcanza (60 LOC). |

## Hallazgos a `_findings_seed.md`

- **TraceLogger duplica LogRecorder.** Severity HIGH. Ahorro 67 LOC + 1 canal.
- **TelemetryStore sobre-ingeniado.** Severity MED. Hipotético ahorro 350+ LOC si se reduce a 1 tabla flat o se elimina.
- **TELEMETRY singleton construido en import-time.** Severity MED. Side effects ocultos (instancia `AgentConfig.from_env()` que aplica profile).
