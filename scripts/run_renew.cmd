@echo off
rem BAXY Renew: Qwen3.5-4B, la wake word k4 (WakewordBaxy), Parakeet Ultra (TranscripcionBaxy) y la voz de BAXY (Supertonic 3, scripts\voice\make_baxy_voice.py).
rem Las rutas son de cada maquina; en una tercera, agrega su bloque.
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
set "PATH=C:\Program Files (x86)\Microsoft Visual Studio\Installer;%PATH%"
rem Un banco puede medir otra copia de la mente (decision 20: los brazos de make_arms_d20.py) definiendo antes la variable.
if not defined BAXY_MIND_PYTHONPATH set "BAXY_MIND_PYTHONPATH=%ROOT%\src"
if /I "%COMPUTERNAME%"=="REDNOTE" (
  rem Notebook: el mismo GGUF (sha 00fe7986) en D:, llama-server b11609 copiado del PC. Sin k4 ni Ultra: la voz de entrada no se usa aqui.
  set "BAXY_MIND_LLM_GGUF=D:\BAXYRuntime\experiments\models\qwen35-4b-e87f1764\Qwen3.5-4B-Q4_K_M.gguf"
  set "BAXY_MIND_LLAMA_SERVER=D:\BAXYeval\llama\llama-server.exe"
  set "BAXY_RENEW_TTS_DIR=D:\BAXYRuntime\assets\voice\baxy-supertonic"
) else (
  set "BAXY_MIND_LLM_GGUF=F:\BAXYeval\models\Qwen3.5-4B-Q4_K_M.gguf"
  set "BAXY_MIND_LLAMA_SERVER=F:\BAXYeval\llama\llama-server.exe"
  rem Un banco puede apagar el oido (k4 y Ultra quedan fuera de la medicion del arnes) definiendo antes la variable.
  if not defined BAXY_RENEW_WAKE_DIR set "BAXY_RENEW_WAKE_DIR=C:\Users\usuario\Desktop\ETC\Programacion\WakewordBaxy\models\final\baxy-wake-k4"
  if not defined BAXY_RENEW_STT_DIR set "BAXY_RENEW_STT_DIR=D:\TranscripcionBaxy-modelos\parakeet-ultra-sherpa-int8-oli"
  set "BAXY_RENEW_TTS_DIR=%LOCALAPPDATA%\BAXYRuntime\assets\voice\baxy-supertonic"
)
py -3.12 "%ROOT%\main.py" %*
