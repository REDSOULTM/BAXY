#!/usr/bin/env bash
# Falsehoods s0 of A (e0a7d9923, l2) and B (pc-ayudas a3af5c20f, pa), each with its launcher's model c2-e1.0 and its own
# mind (seed 0); both built by ab_e2e.sh. The transcripts go to the PC, whose 35B judges.
set -u
P="C:/Users/usuario/Desktop/ETC/Programacion"; S="C:/Users/usuario/AppData/Local/Temp/claude/nb/ay/logs"
F="C:/Users/usuario/AppData/Local/Temp/claude/nb/ft"
declare -A WT=([A]="$P/BAXY-Renew-l2" [B]="$P/BAXY-Renew-pa") H=([A]=e0a7d9923 [B]=a3af5c20f)
idle() { while tasklist //FI "IMAGENAME eq Baxy.exe" | grep -qi baxy || tasklist //FI "IMAGENAME eq llama-server.exe" | grep -qi llama-server; do sleep 10; done; }
export BAXY_RENEW_BANKS='D:\BAXYeval\renew_v1'; unset BAXY_MIND_LLM_GGUF BAXY_MIND_PYTHONPATH
for arm in A B; do
  idle; cd "${WT[$arm]}" || exit 1
  lab="nb-ay-$arm-${H[$arm]}-fals-s0"; dir="D:/BAXYeval/renew_v1/runs/$lab-falsedades"; rm -rf "$dir"
  echo "$lab start $(date +%H:%M) front: $(powershell -NoProfile -ExecutionPolicy Bypass -File "$F/frente_ahora.ps1")"
  py -3.12 -X utf8 scripts/renew/bench_falsedades.py "$lab" --cases 'D:\BAXYeval\renew_v1\falsedades\practice.json' > "$S/$lab.log" 2>&1 &
  until [ -s "$dir/transcripts.json" ]; do sleep 15; done
  sleep 10
  powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.Name -match '^py' -and \$_.CommandLine -match 'bench_falsedades' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }"
  wait 2>/dev/null
  powershell -NoProfile -Command "Get-Process Baxy,Baxy.Core,llama-server -ErrorAction SilentlyContinue | Stop-Process -Force"
  echo "$lab $(date +%H:%M): transcripts $(ls -l "$dir/transcripts.json" | awk '{print $5}') bytes"
  ssh redpc "powershell -NoProfile -Command \"New-Item -ItemType Directory -Force -Path F:/BAXYeval/renew_v1/runs/$lab-falsedades | Out-Null\"" && scp -q "$dir/transcripts.json" "redpc:F:/BAXYeval/renew_v1/runs/$lab-falsedades/transcripts.json" && echo "$lab transcripts sent"
done
powershell -NoProfile -Command "'MSConfig services: ' + @((Get-Item 'HKLM:\SOFTWARE\Microsoft\Shared Tools\MSConfig\services' -ErrorAction SilentlyContinue).Property).Count"
echo FAL-AB-DONE
