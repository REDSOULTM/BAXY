#!/usr/bin/env bash
# Resources (VRAM, RAM) of the lot candidate d7a76adf1 (built by vivo_comb.sh) with BAXY_AYUDAS unset (the kept aids),
# launcher model c2-e1.0, through the real conductor (measure_resources.py).
set -u
W="C:/Users/usuario/Desktop/ETC/Programacion/BAXY-Renew-lote"; H=d7a76adf1; S="C:/Users/usuario/AppData/Local/Temp/claude/nb/ay/logs"
while tasklist //FI "IMAGENAME eq llama-server.exe" | grep -qi llama-server || tasklist //FI "IMAGENAME eq Baxy.exe" | grep -qi baxy; do sleep 10; done
cd "$W" || exit 1
[ "$(git rev-parse --short=9 HEAD)" = "$H" ] || { echo "wrong HEAD"; exit 1; }
unset BAXY_MIND_PYTHONPATH BAXY_MIND_LLM_GGUF BAXY_AYUDAS
export BAXY_RENEW_BANKS='D:\BAXYeval\renew_v1'
LAB=nb-recursos-lote-$H
( for i in $(seq 1 60); do
    m=$(powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" | Select-Object -First 1).CommandLine")
    if [ -n "$m" ]; then echo "measured model: $(echo "$m" | grep -oE '[^ ]*\.gguf' | head -1)"; break; fi
    sleep 5
  done ) &
py -3.12 -X utf8 scripts/renew/measure_resources.py "$LAB" > "$S/$LAB.log" 2>&1
rc=$?; wait
echo "recursos exit $rc $(date +%H:%M): $(tail -6 "$S/$LAB.log" | tr '\n' ' ' | cut -c1-900)"
echo RECURSOS-DONE
