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
  set "VISION_MMPROJ=D:\BAXYeval\models\Qwen3.5-4B-mmproj-F16.gguf"
) else (
  if not defined BAXY_MIND_LLM_GGUF set "BAXY_MIND_LLM_GGUF=F:\BAXYeval\models\BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf"
  set "BAXY_MIND_LLAMA_SERVER=F:\BAXYeval\llama\llama-server.exe"
  rem Un banco puede apagar el oido (k4 y Ultra quedan fuera de la medicion del arnes) definiendo antes la variable.
  if not defined BAXY_RENEW_WAKE_DIR set "BAXY_RENEW_WAKE_DIR=C:\Users\usuario\Desktop\ETC\Programacion\WakewordBaxy\models\final\baxy-wake-k4"
  if not defined BAXY_RENEW_STT_DIR set "BAXY_RENEW_STT_DIR=D:\TranscripcionBaxy-modelos\parakeet-ultra-sherpa-int8-oli"
  set "BAXY_RENEW_TTS_DIR=%LOCALAPPDATA%\BAXYRuntime\assets\voice\baxy-supertonic"
  set "VISION_MMPROJ=F:\BAXYeval\models\Qwen3.5-4B-mmproj-F16.gguf"
)
rem PLAN_GENERAL A5: el proyector de Qwen3.5-4B en CPU en el mismo llama-server, y el escalon de vision del clic apuntado
rem a el, sin VRAM y con ~0,7 GB de RAM. La pregunta va al unico slot, cuyo estado se guarda a disco antes y se
rem restaura despues, unos 2 s; el archivo se borra al restaurarlo. Se apaga definiendo antes BAXY_VISION_OFF=1.
if defined BAXY_VISION_OFF goto run
if not exist "%VISION_MMPROJ%" goto run
set "BAXY_MIND_MMPROJ=%VISION_MMPROJ%"
set "BAXY_MIND_LLAMA_PORT=8077"
set "BAXY_VISION_ENDPOINT=http://127.0.0.1:8077/v1/chat/completions"
set "BAXY_VISION_MODEL=baxy"
set "BAXY_VISION_SLOT=0"
rem Un banco guarda el slot en otro disco definiendo antes la variable (el C: del PC se lleno el 2026-10-22).
if not defined BAXY_VISION_SLOT_DIR set "BAXY_VISION_SLOT_DIR=%LOCALAPPDATA%\BAXY\renew\slots"
:run
rem System One (rama pc-system-one): la duda de Qwen (capa 0) y Laya como freno o corrector (capa 2). Encendido si no
rem existe el interruptor %LOCALAPPDATA%\BAXY\renew\system_one.off (scripts\system_one.cmd on ^| off ^| estado). Umbrales medidos en
rem la fase 0: preguntar bajo 0,4 de confianza; consultar a Laya bajo 0,6; si Laya elige otra operacion inofensiva,
rem Qwen la rellena y se ejecuta (BAXY_S1_CORRECT); si es riesgosa, BAXY pregunta.
if not exist "%LOCALAPPDATA%\BAXY\renew\system_one.off" (
  if not defined BAXY_S1_DOUBT set "BAXY_S1_DOUBT=0.4"
  if not defined BAXY_S1_VETO set "BAXY_S1_VETO=0.6"
  if not defined BAXY_S1_CORRECT set "BAXY_S1_CORRECT=1"
  if /I "%COMPUTERNAME%"=="REDNOTE" (
    if not defined BAXY_S1_GGUF set "BAXY_S1_GGUF=D:\BAXYeval\s1\tuned\layam-long-s1-Q8_0.gguf"
  ) else (
    if not defined BAXY_S1_GGUF set "BAXY_S1_GGUF=D:\BAXYRuntime\candidates\systemone\tuned\layam-long-s1-Q8_0.gguf"
  )
)
py -3.12 "%ROOT%\main.py" %*
