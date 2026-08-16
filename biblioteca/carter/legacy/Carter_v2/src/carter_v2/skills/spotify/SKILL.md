---
name: spotify
description: Spotify playback control via spogo CLI or PowerShell media keys
triggers: [spotify, música, music, canción, song, play, pause, siguiente, next, anterior, previous, volumen, volume, reproducir]
requires: {}
emoji: 🎵
source: builtin
---
# Spotify Skill

Two approaches depending on what's available:

## Option A: spogo CLI (if installed)
```
spogo play           # resume
spogo pause          # pause
spogo next           # next track
spogo prev           # previous track
spogo status         # current track info
spogo search track "nombre de canción"
spogo device list    # list available devices
```
Check if available: `where spogo`

## Option B: PowerShell media keys (always available, Spotify must be open)
```powershell
# Play/Pause
$wshell = New-Object -ComObject wscript.shell
$wshell.SendKeys([char]179)   # Play/Pause (media key)
$wshell.SendKeys([char]176)   # Next track
$wshell.SendKeys([char]177)   # Previous track
$wshell.SendKeys([char]178)   # Stop
```
Run via run_powershell action.

## Option C: Open specific content in browser
Use web_open_url with Spotify URI:
- `https://open.spotify.com/search/<query>`
- `spotify:track:<id>` (opens Spotify desktop app)

## Decision logic
1. Try spogo first (check with where spogo)
2. Fall back to PowerShell media keys if Spotify is running
3. Fall back to browser if nothing else works
