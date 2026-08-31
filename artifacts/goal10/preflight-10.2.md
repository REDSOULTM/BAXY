# Goal 10.2 preflight — 2026-08-31T21:02Z

Host: REDNOTE. No BAXY processes at start.

## Microphone
- waveIn devices: 2
- ConsentStore microphone: HKCU=Allow, HKLM=Allow
- Endpoints observed: "Varios micrófonos (Realtek(R) Audio)" OK; "Micrófono (Steam Streaming Microphone)" OK
- USB Audio Device microphone: Unknown (not required; Realtek capture is OK)

## Audio output
- waveOut devices: 1
- "Altavoces (Realtek(R) Audio)" OK
- Realtek High Definition Audio OK

## Permissions
- Microphone capability Allow at user and machine
- No extra owner prep required for listen

## Models (mind-runtime-v1.json)
- Path: `%LOCALAPPDATA%\BAXYRuntime\mind-runtime-v1.json` exists, schema `baxy-mind-runtime-v1`
- GGUF `D:\BAXYRuntime\assets\models\Qwen3-4B-Q4_K_M.gguf` exists
- llama-server `D:\BAXYRuntime\assets\llama-b9980-cuda12.4\llama-server.exe` exists
- Python runtime exists
- STT Parakeet int8 dir exists
- Wake manifest exists
- TTS `es_MX-claude-high.onnx` exists
- ngl=99, wake_on_start=True

## GPU
- NVIDIA GeForce RTX 3060 Laptop GPU, 6144 MiB total, 994 MiB used, 18% util
- Product VRAM ceiling remains 4 GiB (not the adapter size)

## Windows-start entry
- Startup folder: `C:\Users\usuario\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup` — no BAXY shortcut
- HKCU Run has leftover `BAXY="...\src\Baxy.App\bin\Debug\...\Baxy.exe" --tray`
- `src/` has no `--tray`, NotifyIcon, or autostart owner. That Run value is not the shipped product.

## Entry
- Development launcher `py main.py` → Release `Baxy.exe` exists
- No FALLO_DE_AMBIENTE
