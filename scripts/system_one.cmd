@echo off
rem Interruptor de System One (la duda de Qwen y Laya como freno o corrector) para scripts\run_renew.cmd.
rem   scripts\system_one.cmd on      enciende (por defecto)
rem   scripts\system_one.cmd off     apaga: BAXY decide como antes, sin preguntar por duda ni consultar a Laya
rem   scripts\system_one.cmd estado  dice cómo está
rem Vale desde el próximo arranque de BAXY.
set "FLAG=%LOCALAPPDATA%\BAXY\renew\system_one.off"
if /I "%~1"=="off" (
  if not exist "%LOCALAPPDATA%\BAXY\renew" mkdir "%LOCALAPPDATA%\BAXY\renew"
  type nul > "%FLAG%"
  echo System One APAGADO. Vale desde el proximo arranque de BAXY.
  goto :eof
)
if /I "%~1"=="on" (
  if exist "%FLAG%" del "%FLAG%"
  echo System One ENCENDIDO. Vale desde el proximo arranque de BAXY.
  goto :eof
)
if exist "%FLAG%" (echo System One esta APAGADO.) else (echo System One esta ENCENDIDO.)
echo Uso: scripts\system_one.cmd on ^| off ^| estado
