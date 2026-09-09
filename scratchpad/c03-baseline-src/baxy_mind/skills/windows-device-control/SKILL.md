---
name: windows-device-control
description: Inspect Windows, network, Wi-Fi, audio, applications, windows, notifications, and device state before narrowly scoped control.
operations:
  - system.status
  - system.time
  - network.status
  - audio.status
  - audio.mute
  - audio.volume
  - app.open
  - app.close
  - window.active
  - window.application.status
  - window.resolve
  - window.focus
  - window.minimize
  - window.maximize
  - window.restore
  - window.move
  - window.resize
  - notification.list.due
  - notification.dismiss
  - wifi.profile.list
  - wifi.connect
  - wifi.disconnect
  - system.settings.set
  - system.power
priority: 76
---
# Windows device control

Read state first whenever target or current state matters. Use `window.active`
for the verified foreground application; do not guess it from a screenshot. Resolve a window to
an opaque identity before focus, geometry, or visibility changes.
Use `window.application.status` for open, closed, or running questions about
any named Start-menu application; it resolves the application name and observes
visible windows without launching or focusing it. Enumerate
`wifi.profile.list` before connecting and pass only its observed profile ID;
never invent an ID or expose stored credentials. Disconnect needs no profile.
`system.settings.set` currently supports verified brightness; do not substitute
registry editing for night-light control when the public OS API is unavailable.
Power transitions and work-loss actions are terminal confirmation boundaries;
do not append later steps. Prefer the narrow operation requested and verify the
specific postcondition instead of treating command dispatch as success.
