#!/usr/bin/env bash
# usage: batch.sh <case-id>... (cases/<id>.turns). Prints final, latency, trace, screenshot; closes only what the case opened.
# Unseen-app batch: run each case, print final/latency/trace, screenshot, then close only windows/processes the case started.
L=$(cd "$(dirname "$0")" && pwd); V="$L"
P="$L/cases"
LAD=$(cygpath -u "$LOCALAPPDATA"); CONV="$LAD/BAXY/cu-universal-perfil/conversation/conversation.v1.jsonl"; EVB="$LAD/BAXY/cu-universal-evidencia"
ps(){ powershell -NoProfile -ExecutionPolicy Bypass -File "$@" 2>&1; }
pids(){ powershell -NoProfile -Command "Get-Process | Where-Object { \$_.ProcessName -match '^(Spotify|EpicGamesLauncher|Photos|Microsoft.Photos|WinStore.App|EXCEL|WINWORD|mspaint|SystemSettings|Time|Notepad|CalculatorApp)$' } | ForEach-Object { \$_.Id }" | tr -d '\r' | sort; }
frames(){ powershell -NoProfile -Command "Get-Process ApplicationFrameHost -ErrorAction SilentlyContinue | Where-Object MainWindowTitle | ForEach-Object { \$_.MainWindowTitle }" | tr -d '\r'; }
mkdir -p "$L/logs"
for id in "$@"; do
  echo "=================== $id"
  BEFORE=$(pids)
  FRAMES=$(frames)
  bash $L/cu_live.sh v2-$id "$P/$id.turns" 20 > $L/logs/$id.log 2>&1
  PYTHONIOENCODING=utf-8 py -3.12 $L/ev.py $EVB/v2-$id/events.jsonl 2>/dev/null | grep -a '"terminal"' | sed 's/.*"final": //' | cut -c1-300
  grep -o '"latency_ms":[0-9]*' $CONV | tail -n $(wc -l < $P/$id.turns) | tr '\n' ' '; echo
  grep -h "computer_use.end\|computer.use.step\"\|computer_use.subgoal" $EVB/v2-$id/trace.jsonl 2>/dev/null | sed 's/.*"stage"://' | cut -c1-120
  echo "--- verify"
  ps $L/screen.ps1 -Out "$(cygpath -w "$EVB/v2-$id/after.png")"
  case $id in
    c3) D="/d/Perfil/Documentos/baxy-prueba"; if [ -d "$D" ]; then echo "FOLDER CREATED: $D"; rmdir "$D" && echo "removed empty test folder"; else echo "no folder at $D"; ls -d /d/Perfil/Documentos/*baxy* 2>&1 | head -3; fi;;
    s02) ps $V/state.ps1 -Title Reloj | grep -i "SELECTED" | head -3;;
    s03) ps $V/state.ps1 -Title Configuraci | grep -i "SELECTED" | head -3;;
    n8) ps $V/close_window.ps1 -Title "Imágenes - Explorador";;
    s04) powershell -NoProfile -Command "(New-Object -ComObject Shell.Application).Windows() | ForEach-Object { \$_.LocationName }"; ps $V/close_window.ps1 -Title Descargas;;
    s05) powershell -NoProfile -Command "Get-Process explorer | Where-Object MainWindowTitle | Select -Expand MainWindowTitle"; ps $V/close_window.ps1 -Title Programas;;
    s06) ps $V/close_window.ps1 -Title "Administrador de tareas";;
    s01) ps $L/calc_read.ps1 | head -1;;
    c1|c2) ps $V/state.ps1 -Title "Bloc de notas" | grep -i "WINDOW\|VALUE" | head -3;;
  esac
  NEW=$(comm -13 <(echo "$BEFORE") <(pids))
  for p in $NEW; do powershell -NoProfile -Command "if((Get-Process -Id $p -ErrorAction SilentlyContinue).ProcessName -eq 'Notepad'){ exit 0 } else { exit 1 }" && ps $V/clear_notepad.ps1 -ProcessId $p; done
  for p in $NEW; do powershell -NoProfile -Command "\$p=Get-Process -Id $p -ErrorAction SilentlyContinue; if(\$p){ 'closing '+\$p.ProcessName+' '+\$p.Id; [void]\$p.CloseMainWindow(); Start-Sleep 2; if(-not \$p.HasExited){ Stop-Process -Id $p -Force; 'stopped '+$p } }"; done
  # A frame window (Settings, Store…) the case left open is closed normally by its exact title.
  comm -13 <(echo "$FRAMES" | sort) <(frames | sort) | while read -r t; do [ ${#t} -ge 4 ] && ps $V/close_window.ps1 -Title "$t"; done
done
