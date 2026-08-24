# Handoff — Goal 10 — 2026-08-23

## Objetivo
BAXY se usa en una dosis real concentrada, no miente, se queda encendido barato.

## Estado
Hecho: bandeja, arranque con Windows (`HKCU\...\Run\BAXY` → `Baxy.exe --tray`), X oculta a bandeja, segunda instancia muestra la primera. Panel de memoria GET/POST/DELETE contra el almacén real (ver/editar/borrar + relectura).
En curso: lanzar `py main.py` ×2, dosis ≥200, soak 24 h, modos/narración/web.search en uso.
Sin empezar: reboot de Windows, idle final, compuerta Full, publicar cierre.

## Decisiones tomadas
- NotifyIcon de WinForms con `UseWindowsForms` y usings implícitos de Drawing/Forms **quitados** del resto de App, para no ensuciar WPF.
- El confirm del panel es la confirmación de esa invocación: Core pide token y el puente lo reenvía; no hay segundo diálogo.
- `py main.py` mata el proceso si CloseMainWindow sólo oculta (bandeja).

## Archivos tocados
- `src/Baxy.App/TrayPresence.cs`, `WindowsAutostart.cs`, `PresencePolicy.cs`, `App.xaml.cs`, `MainWindow.xaml.cs`
- `src/Baxy.App/MemoryPanelBridge.cs`, `FieldUiBridge.cs`
- `scripts/goal10_idle_sampler.py`, `scripts/goal10_dose_turns.ps1`

## Siguiente acción recomendada
Lanzar `py main.py` con `BAXY_APP_TRACE`, primer turno real, sampler de idle, segunda corrida en frío, dosis.
