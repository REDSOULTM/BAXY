#!/usr/bin/env bash
# The live cases W1, F1, F2 (vivo_ft.json) and E001 (practice.json) s0-2 on the lot candidate d7a76adf1, rebuilt,
# with BAXY_AYUDAS unset (= the kept combination, PC 23:45); desktop checked before each run and per case after it.
set -u
H=d7a76adf1; WT="C:/Users/usuario/Desktop/ETC/Programacion/BAXY-Renew-lote"
AY="C:/Users/usuario/AppData/Local/Temp/claude/nb/ay"; F="C:/Users/usuario/AppData/Local/Temp/claude/nb/ft"; S="$AY/logs"
idle() { while tasklist //FI "IMAGENAME eq Baxy.exe" | grep -qi baxy || tasklist //FI "IMAGENAME eq llama-server.exe" | grep -qi llama-server; do sleep 10; done; }
cd "$WT" || exit 1
[ "$(git rev-parse --short=9 HEAD)" = "$H" ] || { echo "wrong HEAD"; exit 1; }
export BAXY_RENEW_BANKS='D:\BAXYeval\renew_v1'; unset BAXY_MIND_LLM_GGUF
unset BAXY_AYUDAS BAXY_MIND_PYTHONPATH
idle
powershell -NoProfile -Command "& '.\scripts\run_renew.cmd' --recompilar --conductor --text 'hola' --timeout-ms 120000" > "$S/lote-$H-warmup.log" 2>&1
echo "$H warm-up exit $? $(grep -a -c 'Compilaci' "$S/lote-$H-warmup.log") build lines, $(grep -a -c ' 0 Error' "$S/lote-$H-warmup.log") '0 Error' $(date +%H:%M)"
for seed in 0 1 2; do
  export BAXY_MIND_PYTHONPATH="D:/BAXYeval/renew_v1/ab/arr/$H-s$seed"
  for part in "vivo_ft:W1,F1,F2" "practice:E001"; do
    bank=${part%%:*}; only=${part#*:}; lab="nb-vivo-lote-$bank-s$seed"; rm -rf "D:/BAXYeval/renew_v1/runs/$lab-e2e"
    idle
    powershell -NoProfile -Command "Get-Process CalculatorApp,steam,steamwebhelper,WINWORD -ErrorAction SilentlyContinue | Stop-Process -Force"
    echo "$lab start $(date +%H:%M) front: $(powershell -NoProfile -ExecutionPolicy Bypass -File "$F/frente_ahora.ps1"; [ $? = 0 ] && echo clean || echo DIRTY-DESKTOP)"
    py -3.12 -X utf8 scripts/renew/bench_e2e.py "$lab" --cases "D:/BAXYeval/renew_v1/e2e/$bank.json" --only "$only" > "$S/$lab.log" 2>&1
    echo "$lab exit $? $(date +%H:%M): $(grep -E '^(W1|F1|F2|E001) ' "$S/$lab.log" | tr '\n' ' ') $(tail -1 "$S/$lab.log" | grep -oE '"setup_failed": \[[^]]*\]|"first_audio_p50_ms": [0-9]+' | tr '\n' ' ')"
    echo "$lab $(py -3.12 -X utf8 -I "$F/e2e_frente.py" "D:/BAXYeval/renew_v1/runs/$lab-e2e/events.jsonl" || echo INVALID-dirty-front)"
  done
done
unset BAXY_AYUDAS BAXY_MIND_PYTHONPATH
powershell -NoProfile -Command "Get-Process WINWORD -ErrorAction SilentlyContinue | Stop-Process -Force"
powershell -NoProfile -Command "'MSConfig services: ' + @((Get-Item 'HKLM:\SOFTWARE\Microsoft\Shared Tools\MSConfig\services' -ErrorAction SilentlyContinue).Property).Count"
echo VIVO-COMB-DONE
