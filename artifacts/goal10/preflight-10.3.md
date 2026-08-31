# Goal 10.3 preflight — 2026-08-31T22:21Z

Host: REDNOTE. No BAXY process at preflight. Stale `status.v1.json` from 10.2 idle (`ready=false`, `terminal=starting`, 21:48Z) is leftover, not a live shell.

Frozen families: `conversation`, `media.play`, `audio.volume`, `system.status`, `system.settings`.

## Audio output
- waveOut devices: 1
- Realtek High Definition Audio OK (plus NVIDIA/AMD/Steam virtual devices OK)
- Default render endpoint via pycaw: scalar=1.0 (100 %), **muted=true**
- Mute does not block volume scalar postread nor SMTC play verification

## Reversible settings
- WMI `WmiMonitorBrightness` + `WmiMonitorBrightnessMethods` present
- Current brightness: 100 (0–100 levels)

## Media app + playable content
- Spotify Store package `SpotifyAB.SpotifyMusic` installed
- Autologin saved credentials present (signed-in account; username not copied here)
- SMTC sessions at preflight: 0
- Fallback: Microsoft Edge and Google Chrome present (YouTube path)
- Play path: Spotify `media.play.query` / `media.play.exact`

## Models (from 10.2)
- `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json` schema `baxy-mind-runtime-v1`
- GGUF `D:\BAXYRuntime\assets\models\Qwen3-4B-Q4_K_M.gguf` exists
- llama-server `D:\BAXYRuntime\assets\llama-b9980-cuda12.4\llama-server.exe` exists

## Entry
- `py main.py` → Release `Baxy.exe`
- Development data root: `%LOCALAPPDATA%\BAXY\dev-mente-v2`

## Verdict
No `FALLO_DE_AMBIENTE`. In-scope families can run physically.

## Revalidation — 2026-08-31T22:55Z
The machine-readable JSON first probe marked `audio_volume_readable` false via a PowerShell COM `Read` error and set `verdict=FALLO_DE_AMBIENTE`. That probe is not the product path.

Re-read with pycaw `GetSpeakers().EndpointVolume`:
- device: `Altavoces (Realtek(R) Audio)`
- scalar: 1.0 (100 %)
- muted: true
- mute still does not block scalar postread

Also confirmed at revalidation:
- WMI brightness 100
- Spotify Store exe present
- GGUF + llama-server + `mind-runtime-v1` schema present
- `main.py` present
- leftover outbox on `%LOCALAPPDATA%\BAXY\dev-mente-v2`: 1 entry `memory.forget` (will prompt recovery on next launch; cancel is prep, not a counted turn)
- presence `status.v1.json` may be stale from the aborted live 10.3 attempt (22:46Z)

No `FALLO_DE_AMBIENTE`. Do not invent the 50 real turns; owner spontaneous input is still missing.
