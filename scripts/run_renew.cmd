@echo off
rem BAXY Renew: Qwen3.5-4B, la wake word k4 (WakewordBaxy), Parakeet Ultra (TranscripcionBaxy) y la voz de BAXY (Supertonic 3, scripts\voice\make_baxy_voice.py).
rem Las rutas son de cada maquina; en una tercera, agrega su bloque.
rem Un banco (o el ajuste fino) puede elegir otro GGUF definiendo antes BAXY_MIND_LLM_GGUF.
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "PATH=C:\Program Files (x86)\Microsoft Visual Studio\Installer;%PATH%"
rem Un banco puede medir otra copia de la mente (decision 20: los brazos de make_arms_d20.py) definiendo antes la variable.
if not defined BAXY_MIND_PYTHONPATH set "BAXY_MIND_PYTHONPATH=%ROOT%\src"
if /I "%COMPUTERNAME%"=="REDNOTE" (
  rem Notebook: el mismo GGUF que el PC en D:, llama-server b11609 copiado del PC. Sin k4 ni Ultra: la voz de entrada no se usa aqui.
  rem Modelo: Qwen3.5-4B con el ajuste fino de BAXY (ciclo 2, Q4_K_M, sha256 8a4b6ce3...; artifacts/renew/ft/RECETA.md). El base era sha 00fe7986.
  if not defined BAXY_MIND_LLM_GGUF set "BAXY_MIND_LLM_GGUF=D:\BAXYeval\models\BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf"
  set "BAXY_MIND_LLAMA_SERVER=D:\BAXYeval\llama\llama-server.exe"
  set "BAXY_RENEW_TTS_DIR=D:\BAXYRuntime\assets\voice\baxy-supertonic"
) else (
  if not defined BAXY_MIND_LLM_GGUF set "BAXY_MIND_LLM_GGUF=F:\BAXYeval\models\BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf"
  set "BAXY_MIND_LLAMA_SERVER=F:\BAXYeval\llama\llama-server.exe"
  rem Un banco puede apagar el oido (k4 y Ultra quedan fuera de la medicion del arnes) definiendo antes la variable.
  if not defined BAXY_RENEW_WAKE_DIR set "BAXY_RENEW_WAKE_DIR=C:\Users\usuario\Desktop\ETC\Programacion\WakewordBaxy\models\final\baxy-wake-k4"
  if not defined BAXY_RENEW_STT_DIR set "BAXY_RENEW_STT_DIR=D:\TranscripcionBaxy-modelos\parakeet-ultra-sherpa-int8-oli"
  set "BAXY_RENEW_TTS_DIR=%LOCALAPPDATA%\BAXYRuntime\assets\voice\baxy-supertonic"
  rem PLAN_GENERAL A5: el proyector de Qwen3.5-4B en CPU en el mismo llama-server, y el escalon de vision del clic apuntado
  rem a el, sin VRAM y con ~0,7 GB de RAM. Sin el archivo, nada cambia.
  if exist "F:\BAXYeval\models\Qwen3.5-4B-mmproj-F16.gguf" (
    set "BAXY_MIND_MMPROJ=F:\BAXYeval\models\Qwen3.5-4B-mmproj-F16.gguf"
    set "BAXY_MIND_LLAMA_PORT=8077"
    set "BAXY_VISION_ENDPOINT=http://127.0.0.1:8077/v1/chat/completions"
    set "BAXY_VISION_MODEL=baxy"
  )
)
py -3.12 "%ROOT%\main.py" %*
