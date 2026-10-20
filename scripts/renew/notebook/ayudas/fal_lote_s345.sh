#!/usr/bin/env bash
# Falsehoods s3, s4 and s5 of A (BAXY_AYUDAS=none) and B (unset: the lot's aids) on the lot candidate d7a76adf1, built;
# interleaved A s3, B s3, ... B s5; --no-judge, game guard; transcripts to the PC (PC 02:52).
set -u
H=d7a76adf1; WT="C:/Users/usuario/Desktop/ETC/Programacion/BAXY-Renew-lote"
AY="C:/Users/usuario/AppData/Local/Temp/claude/nb/ay"; F="C:/Users/usuario/AppData/Local/Temp/claude/nb/ft"; S="$AY/logs"
idle() { while tasklist //FI "IMAGENAME eq Baxy.exe" | grep -qi baxy || tasklist //FI "IMAGENAME eq llama-server.exe" | grep -qi llama-server; do sleep 10; done; }
cd "$WT" || exit 1
[ "$(git rev-parse --short=9 HEAD)" = "$H" ] || { echo "wrong HEAD"; exit 1; }
export BAXY_RENEW_BANKS='D:\BAXYeval\renew_v1'; unset BAXY_MIND_LLM_GGUF
for seed in 3 4 5; do
  for arm in A B; do
    idle
    if [ $arm = A ]; then export BAXY_AYUDAS=none; else unset BAXY_AYUDAS; fi
    export BAXY_MIND_PYTHONPATH="D:/BAXYeval/renew_v1/ab/arr/$H-s$seed"
    lab="nb-lote-$arm-fals-s$seed"; dir="D:/BAXYeval/renew_v1/runs/$lab-falsedades"; rm -rf "$dir"
    echo "$lab BAXY_AYUDAS=${BAXY_AYUDAS:-<unset>} start $(date +%H:%M) front: $(powershell -NoProfile -ExecutionPolicy Bypass -File "$F/frente_ahora.ps1")"
    rm -f "$S/$lab.stop"; powershell -NoProfile -ExecutionPolicy Bypass -File "$AY/guardia_juegos.ps1" -Stop "$S/$lab.stop" -Log "$S/$lab.juegos.txt" &
    GUARD=$!
    py -3.12 -X utf8 scripts/renew/bench_falsedades.py "$lab" --cases 'D:\BAXYeval\renew_v1\falsedades\practice.json' --no-judge > "$S/$lab.log" 2>&1 &
    BENCH=$!
    until [ -s "$dir/transcripts.json" ] || ! kill -0 $BENCH 2>/dev/null; do sleep 15; done
    [ -s "$dir/transcripts.json" ] || echo "$lab BENCH-DIED without transcripts: $(tail -1 "$S/$lab.log")"
    sleep 10
    powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.Name -match '^py' -and \$_.CommandLine -match 'bench_falsedades' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }"
    wait $BENCH 2>/dev/null
    powershell -NoProfile -Command "Get-Process Baxy,Baxy.Core,llama-server -ErrorAction SilentlyContinue | Stop-Process -Force"
    touch "$S/$lab.stop"; wait $GUARD 2>/dev/null
    echo "$lab games closed: $(cat "$S/$lab.juegos.txt" 2>/dev/null | tr '\n' ' ')"
    echo "$lab $(date +%H:%M): transcripts $(ls -l "$dir/transcripts.json" 2>/dev/null | awk '{print $5}') bytes"
    ssh redpc "powershell -NoProfile -Command \"New-Item -ItemType Directory -Force -Path F:/BAXYeval/renew_v1/runs/$lab-falsedades | Out-Null\"" && scp -q "$dir/transcripts.json" "redpc:F:/BAXYeval/renew_v1/runs/$lab-falsedades/transcripts.json" && echo "$lab transcripts sent"
  done
done
unset BAXY_AYUDAS BAXY_MIND_PYTHONPATH
powershell -NoProfile -Command "'MSConfig services: ' + @((Get-Item 'HKLM:\SOFTWARE\Microsoft\Shared Tools\MSConfig\services' -ErrorAction SilentlyContinue).Property).Count"
echo FAL-LOTE-DONE
