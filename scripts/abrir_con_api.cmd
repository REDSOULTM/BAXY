@echo off
rem Abre BAXY de este worktree para probar el modelo por API (documentacion\MODELO_POR_API.md), con un perfil aparte: las
rem memorias y conversaciones del perfil de siempre no salen hacia la API. La clave se pega en Ajustes - Modelo.
setlocal
for %%I in ("%~dp0..") do set "ROOT=%%~fI"
if exist "%ROOT%\.venv-modelo-api\Scripts\python.exe" set "BAXY_API_EXTERNA_PYTHON=%ROOT%\.venv-modelo-api\Scripts\python.exe"
rem Laya usaria el llama-server local.
set "BAXY_S1_GGUF= "
call "%ROOT%\scripts\run_renew.cmd" --profile perfil-api
if errorlevel 1 pause
