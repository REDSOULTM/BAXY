# Handoff — Goal 10.2 presencia y recursos — 2026-08-31

## Objetivo
BAXY disponible sin fricción: bandeja, arranque con Windows, entrada sólo tras readiness, idle 15 min atribuido sin secuestrar el PC.

## Estado
Hecho: bandeja Win32 `BAXY.Presence.Tray`, HKCU Run `BAXY` → `Baxy.exe --from-windows-start`, input/voice gated until ready, cold start + restart recover voz/mente/UI, 15 min idle with listen on. Owner tests 26+5 two times, 0 fail 0 skip.
En curso: nada.
Sin empezar: `10.3_USO_REAL_A.md`.

## Decisiones tomadas
- Autostart = HKCU Run, not Startup folder; no Windows reboot. Launching the Run command starts BAXY (status under `%LOCALAPPDATA%\BAXY\1` when `BAXY_DATA_DIR` is unset).
- Tray is a message-only window + Shell_NotifyIcon; close hides to tray; Salir shuts down (`ShutdownMode=OnExplicitShutdown`).
- Keep-warm / `process_lifecycle` unchanged. Idle measured the live llama-server; no unload-on-idle path.
- Process attribution: descendants of Baxy.exe with start-time ≥ root, python only under `BAXYRuntime`. System Python312 excluded.
- Overlapping VoiceStart/Stop serialized with `_voiceCommandBusy`.

## Archivos tocados
- `src/Baxy.App/Presence*.cs`, `WindowsAutostartRegistration.cs`, `OwnedProcessReader.cs` — tray, autostart, idle samples, status.v1.json
- `src/Baxy.App/App.xaml(.cs)`, `MainWindow.xaml.cs` — hide-to-tray, presence host
- `src/Baxy.App/FieldBridgeContract.cs`, `FieldUiBridge.cs` — `/turn` and `/voice` reject `agent_not_ready`
- `src/Baxy.App/MainWindowViewModel.cs` — FirstWakeUtc, mind/mic publish, voice busy latch
- `src/Baxy.App/CoreProcessClient.cs` — injectable exe for dead-child bound
- `main.py` — kill leftover development Baxy if hide-to-tray ignores CloseMainWindow
- `tests/Baxy.Integration.Tests/Presence*.cs`

## Archivos relevantes aún sin tocar
- `documentacion/sprints/10.3_USO_REAL_A.md` — next prompt, not this session
- Goal 09 wake/STT/TTS — no recailbration

## Hipótesis
Confirmadas: no NotifyIcon/autostart in src before this goal → defect, now shipped. Corrupt outbox still fail-closes (`CorruptDefaultOutboxLeavesTheShellUnavailable`). Keep-warm llama-server stays in the idle tree.
Descartadas: transplant vram_manager/Ollama/unload-on-idle; soak 24 h; FindWindow on WS_POPUP (not enumerable).

## Comandos ejecutados y resultado
- `dotnet test tests\Baxy.Integration.Tests ... --filter Presence*|VoiceListen|CorruptDefaultOutbox` → `26 passed, 0 fail, 0 skip` twice (327 ms / 350 ms)
- `py -3.12 -m pytest tests/test_process_lifecycle.py -q` → `5 passed` twice
- Live `py main.py`: tray hwnd queryable, ready/input/mind/listen; cold-start 46.5 s; restart 28.9 s; autostart exe `--from-windows-start` ready in `%LOCALAPPDATA%\BAXY\1`
- Idle 904 s listen on, 39 samples, working_set not monotonic, handles −36, adapter GPU 4132→991 MiB
- Evidence: `artifacts/goal10/{preflight-10.2.md,launch-1.json,cold-start.json,restart.json,idle-15min.json,idle-15min.summary.json,autostart-launch.json}`
- No ejecutado: Full — not this session’s close

## Problemas pendientes
- nvidia-smi compute-apps does not attribute MiB to llama-server (vram_bytes=0 per pid); adapter-level used as the VRAM ceiling check
- First acoustic wake during idle was null (listen armed; no “Baxy” spoken)

## Siguiente acción recomendada
`documentacion/sprints/10.3_USO_REAL_A.md` (sesión nueva, un pegado).
