# 03.09 — Surfaces (clases UML)

> **Container:** Surfaces (CLI + UI Desktop + UI Field + MCP Server).
> **Archivos:** `chat.py`, `ui/*.py`, `server.py`, `agent_runner.py`, `mcp_server.py`.

## Fig 3.09 — Surfaces classes

```mermaid
classDiagram
    class ProgressDisplay {
        enabled: bool
        _lock: Lock
        _running: bool
        _thread: Thread
        _start: float
        _frame: int
        _progress: float
        _message: str
        _mode: str
        _tools: int
        _steps: int
        _turn: int
        _max_turns: int
        start()
        stop()
        update(...)
    }
    note for ProgressDisplay "chat.py · 489 LOC archivo\nSpinner ANSI con thread propio"

    class AgentRunner {
        _inbox: Queue
        _running: bool
        _stop_event: Event
        _agent: Gemma4Agent
        _thread: Thread
        _build_lock: Lock
        _warmed_up: bool
        _server_manager: LlamaServerManager
        is_warmed_up() bool
        start()
        stop()
        submit(text, images, audios)
        agent_ready() bool
        restart()
        _build_agent()
        _autostart_llama_server()
        _run()
    }
    note for AgentRunner "552 LOC · 9 métodos\nSingleton RUNNER\nFastAPI side"

    class AgentWorker {
        _inbox: Queue
        _running: bool
        _stop_event: Event
        _agent: Gemma4Agent
        _config: AgentConfig
        _health_timer_thread: Thread
        _last_connected: bool|None
        submit(text, images, audios)
        stop()
        get_agent() Any
        get_config() Any
        _build_agent()
        _progress_forwarder(event, payload)
        run()
        pyqtSignal: state_changed
        pyqtSignal: progress
        pyqtSignal: log
        pyqtSignal: reply_ready
        pyqtSignal: llm_error
        pyqtSignal: connection_changed
        pyqtSignal: health_status
    }
    note for AgentWorker "220 LOC · 7 métodos + 7 signals\n[DUP MAYOR] vs AgentRunner — misma operación, distinto reporter"

    class ServerBootWorker {
        pyqtSignal: log
        pyqtSignal: finished_with_result
        run()
    }
    note for ServerBootWorker "~100 LOC en ui/main_window.py:81\n[DUP] vs AgentRunner._autostart_llama_server"

    class VoiceBridge {
        pyqtSignal: state_changed
        pyqtSignal: partial
        pyqtSignal: final
        pyqtSignal: failed
    }
    note for VoiceBridge "QObject · señales que reciben callbacks no-GUI y los marshallan al main thread Qt"

    class EventBusBridge {
        _attached: bool
        attach()
        detach()
        _on_bus_event(event)
        pyqtSignal: boot_stage
        pyqtSignal: vision_threshold
        pyqtSignal: activity
        pyqtSignal: agent_state
        pyqtSignal: unknown_event
    }
    note for EventBusBridge "122 LOC · 3 métodos + 5 signals\nBUS → pyqtSignal categorizado"

    class MainWindow {
        worker: AgentWorker
        bus_bridge: EventBusBridge
        hud: HudCanvas
        ... ~50 más
        __init__()
        ... 53 métodos en total
    }
    note for MainWindow "1 430 LOC clase · 53 métodos · [GOD MÁXIMO UI]\nQMainWindow dominante de toda la UI Desktop"

    class SettingsDialog {
        ... ~22 métodos
    }
    note for SettingsDialog "1 148 LOC · 22 métodos · [GOD UI]"

    class HudCanvas
    note for HudCanvas "451 LOC · 26 métodos · QWidget"

    class TriggersDialog
    note for TriggersDialog "311 LOC · 11 métodos · QDialog"

    class MemoryDialog
    note for MemoryDialog "267 LOC · 12 métodos · QDialog"

    AgentWorker ..> Gemma4Agent : self._agent
    AgentRunner ..> Gemma4Agent : self._agent
    AgentRunner ..> LlamaServerManager : self._server_manager
    AgentWorker ..> EventBus : (no, usa pyqtSignal)
    EventBusBridge --> EventBus : sync listener
    VoiceBridge ..> "voice_runner / VoiceController" : callbacks
    MainWindow *-- AgentWorker
    MainWindow *-- EventBusBridge
    MainWindow *-- VoiceBridge
    MainWindow *-- ServerBootWorker
    MainWindow *-- HudCanvas
    MainWindow *-- TriggersDialog
    MainWindow *-- MemoryDialog
    MainWindow *-- SettingsDialog
```

## Notas sobre `server.py` (FastAPI, 1 519 LOC)

`server.py` no define clases de relevancia (solo helpers + dataclasses pydantic
para los endpoints: `TurnRequest`, `ActivityRequest`, `SettingsPayload`,
`ModelInfoResponse`). El "estado del servidor" vive en variables module-level
(`_HARDWARE_CACHE`, `_NVML`, `_last_net`, `RUNNER` import desde `agent_runner`).
Es **funcional-style** vs el OO style del UI Desktop. Anomalía consistente
con que es FastAPI (cada handler es función).

## Notas sobre `mcp_server.py` (332 LOC)

Sin clases. Implementa JSON-RPC desde cero con funciones top-level
(`handle_initialize`, `handle_list_tools`, `handle_call_tool`, etc) y un
`main()` que multiplexa stdio o HTTP. **Ya marcado como candidato a reescribir
con el SDK oficial `mcp` package.**

## Veredictos

| Clase | LOC | Métodos | Marca | Veredicto |
|---|--:|--:|---|---|
| `ProgressDisplay` (chat.py) | <100 | ~6 | — | mantener. Spinner CLI estándar. |
| `AgentRunner` | 476 | 9 + restart + _autostart | — (límite) | **colapsar con `AgentWorker`.** Patrón común con adaptador para reporter. |
| `AgentWorker` | 220 | 7 + 7 signals | `[DUP MAYOR]` | mismo veredicto. |
| `ServerBootWorker` (anidada en `ui/main_window.py:81`) | ~100 | 1 (`run`) | `[DUP]` con `AgentRunner._autostart_llama_server` | colapsar. |
| `VoiceBridge` | <50 | 4 signals | — | mantener. Adapter típico Qt. |
| `EventBusBridge` | 122 | 3 + 5 signals | — | mantener. Bien encapsulado. |
| `MainWindow` | 1 430 | 53 | `[GOD MÁXIMO UI]` | **split urgente** en sub-widgets: header, side panels, hud canvas, footer, dialogs wiring. Pero requiere refactor cuidadoso de signals. |
| `SettingsDialog` | 1 148 | 22 | `[GOD UI]` | **split** por tab/section (cada tab del dialog es probablemente independiente). |
| `HudCanvas` | 451 | 26 | `[GOD UI]` | revisar: 26 métodos en un QWidget de pintura es mucho. |
| `TriggersDialog`, `MemoryDialog` | <320 each | 11-12 | — | mantener pero verificar. |

## Hallazgos a `_findings_seed.md`

- **`AgentRunner` ≡ `AgentWorker` ≡ `ServerBootWorker` triple-duplicación de patrón "single-thread worker + boot"** — ya en findings (HIGH). Reafirmo en Fase 3.
- **`MainWindow` 53 métodos, 1 430 LOC** — ya en findings (MED). Reafirmo CRITICAL en Fase 3.
- **`SettingsDialog` 22 métodos, 1 148 LOC** — ya en findings (MED).
- **`HudCanvas` 26 métodos, 451 LOC** — no estaba en findings; agregar MED.
- **`server.py` funcional-style sin clases vs `ui/` heavy OO** — patrón aceptable pero anomalía a documentar en Fase 5.
