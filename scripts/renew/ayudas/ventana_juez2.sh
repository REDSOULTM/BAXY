#!/usr/bin/env bash
# The judge's order changed at 23:25: when the set in course (pc-l5a-B-s1) is judged, the first window stops and the
# sets that decide something go first; 6b (discarded) is not judged.
set -u
LOG=/f/BAXYeval/ayudas_v1/runs
until grep -q "^pc-l5a-B-s1 " $LOG/cadena-juez.log; do sleep 30; done
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -match 'ventana_juez\.sh' -or (\$_.CommandLine -match 'bench_falsedades\.py' -and \$_.CommandLine -match 'judge-only') -or (\$_.Name -eq 'llama-server.exe' -and \$_.CommandLine -match '35B') } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue }"
sleep 5
cd /c/Users/usuario/Desktop/ETC/Programacion/BAXY-Renew-ayudas || exit 1
export BAXY_RENEW_BANKS='F:\BAXYeval\renew_v1'
for lab in nb-p8-B-fals-s0 pc-l8-B-s0 nb-comb1-A-fals-s0 nb-comb1-B-fals-s0 nb-p1c-A-fals-s0 nb-p1c-B-fals-s0 \
           pc-l5a-A-s2 pc-l5a-B-s2; do
  [ -s "/f/BAXYeval/renew_v1/runs/$lab-falsedades/transcripts.json" ] || { echo "$lab: no transcripts"; continue; }
  py -3.12 -X utf8 scripts/renew/bench_falsedades.py "$lab" --judge-only --cases 'F:\BAXYeval\renew_v1\falsedades\practice.json' > $LOG/juez-$lab.log 2>&1
  echo "$lab $(date +%H:%M): $(tail -1 $LOG/juez-$lab.log | cut -c1-400)"
done
echo "VENTANA-JUEZ-DONE $(date +%H:%M)"
