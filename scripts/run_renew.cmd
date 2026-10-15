@echo off
rem BAXY Renew en este PC: Qwen3.5-4B, la wake word k4 (WakewordBaxy) y Parakeet Ultra (TranscripcionBaxy).
rem Las rutas son de este PC; en otro, cambia las cinco de abajo.
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "PATH=C:\Program Files (x86)\Microsoft Visual Studio\Installer;%PATH%"
set "BAXY_MIND_PYTHONPATH=%ROOT%\src"
set "BAXY_MIND_LLM_GGUF=F:\BAXYeval\models\Qwen3.5-4B-Q4_K_M.gguf"
set "BAXY_MIND_LLAMA_SERVER=F:\BAXYeval\llama\llama-server.exe"
set "BAXY_RENEW_WAKE_DIR=C:\Users\usuario\Desktop\ETC\Programacion\WakewordBaxy\models\final\baxy-wake-k4"
set "BAXY_RENEW_STT_DIR=D:\TranscripcionBaxy-modelos\parakeet-ultra-sherpa-int8-oli"
py -3.12 "%ROOT%\main.py" %*
