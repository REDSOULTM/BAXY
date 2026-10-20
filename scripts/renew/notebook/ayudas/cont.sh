#!/usr/bin/env bash
# PC 02:05: the continuation probes of levers 2, 3 and 1c (P) on the notebook GPU, d7a76adf1 mind copies s0-2, the PC's
# lote3 catalog, c2-e1.0; after the heartbeat base runs.
AY=/c/Users/usuario/AppData/Local/Temp/claude/nb/ay
until grep -q LAT-BASE-DONE "$AY/lat_base.log" 2>/dev/null; do sleep 15; done
while tasklist //FI "IMAGENAME eq llama-server.exe" | grep -qi llama-server || tasklist //FI "IMAGENAME eq Baxy.exe" | grep -qi baxy; do sleep 10; done
export BAXYEVAL=D:/BAXYeval
for N in 0 1 2; do
  py -3.12 -X utf8 "$AY/cont/continuacion.py" nb-cont-s$N --levers 2,3,P --src "D:/BAXYeval/renew_v1/ab/arr/d7a76adf1-s$N" \
    --catalog D:/BAXYeval/reales_v1/catalogos/lote3.json --gguf 'D:\BAXYeval\models\BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf' \
    --server 'D:\BAXYeval\llama\llama-server.exe' > "$AY/logs/nb-cont-s$N.log" 2>&1
  echo "s$N exit $? $(date +%H:%M)"; grep -a "TALLY" "$AY/logs/nb-cont-s$N.log"
done
echo CONT-DONE
