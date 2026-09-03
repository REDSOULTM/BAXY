# Herencia consultada antes de crear un host (C01)

Ámbito: `biblioteca/00_INDICE.md`, `biblioteca/01_INVENTARIO.md` (títulos
headless/host/conductor/sin ventana), `src/Baxy.App`, `docs/AI_CONTEXT_MAP.md`.

| Pieza existente | Alcance | Por qué no basta |
|---|---|---|
| `MainWindowViewModel` | Controlador de producto: admisión de misión, mente, Core, colas, prosa | Las pruebas MindShellEndToEnd lo usan sin ventana, pero con `tests/fixtures/mind_turn_contract`, no el runtime registrado |
| `FieldUiBridge` | Rutas `/turn`, `/sessions/new`, `/upload` y proyección a WebView | Exige `Window` + `WebView2`; origen `baxy.local` |
| `FieldBridgeContract.TryAcceptTurn` | Gate listo/texto | No ejecuta el turno ni publica |
| `PresenceHost` `--from-windows-start` / `--tray` | Oculta la ventana **después** de `Show()` | Sigue creando WebView2; no es entrada de agente |
| `MissionInputPipeline` | Normaliza texto/voz | No es el recorrido UI |
| Sidecar `CreateNoWindow` | Procesos hijo | No es el host de producto |

No hay un host headless de producto en la biblioteca ni en el árbol actual.
C01 extrae `FieldProductChannel` del bridge (no un servidor HTTP nuevo) y
añade `ProductConductor` / `ProductConductorHost` como adaptador sin ventana
sobre el mismo ViewModel. `FieldUiBridge` queda como adaptador de origen.
