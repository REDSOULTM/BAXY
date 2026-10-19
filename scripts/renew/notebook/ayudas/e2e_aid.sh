#!/usr/bin/env bash
# One aid in e2e s0-2, paired on ONE binary (PC 16:32): A = BAXY_AYUDAS=none, B = BAXY_AYUDAS=<id>, both the mind copy
# of the same commit, c2-e1.0, the same bench; interleaved A s0, B s0, ...; desktop checked before each run and per case.
# Then falsehoods s0 of B (and of A when FAL_A=1); transcripts to the PC. Usage: e2e_aid.sh <commit> <worktree> <id> <tag>
set -u
H="$1"; WT="$2"; AID="$3"; TAG="$4"
AY="C:/Users/usuario/AppData/Local/Temp/claude/nb/ay"; F="C:/Users/usuario/AppData/Local/Temp/claude/nb/ft"
R="C:/Users/usuario/AppData/Local/Temp/claude/nb/reales"; S="$AY/logs"; mkdir -p "$S"
idle() { while tasklist //FI "IMAGENAME eq Baxy.exe" | grep -qi baxy || tasklist //FI "IMAGENAME eq llama-server.exe" | grep -qi llama-server; do sleep 10; done; }
idle; cd "$WT" || exit 1
[ "$(git rev-parse --short=9 HEAD)" = "$H" ] || { echo "wrong HEAD"; exit 1; }
[ -z "$(git status --porcelain -- src scripts main.py)" ] || { echo "dirty worktree"; git status --porcelain | head; exit 1; }
for seed in 0 1 2; do
  d="D:/BAXYeval/renew_v1/ab/arr/$H-s$seed"
  if [ ! -d "$d" ]; then mkdir -p "$d"; git archive "$H" src/baxy_mind | tar -x -C "$d" --strip-components=1
    sed -i "s/\"seed\": 0}/\"seed\": $seed}/" "$d/baxy_mind/mind.py"; fi
done
export BAXY_RENEW_BANKS='D:\BAXYeval\renew_v1'; unset BAXY_MIND_LLM_GGUF BAXY_MIND_PYTHONPATH
export BAXY_AYUDAS=none
powershell -NoProfile -Command "Get-Process CalculatorApp,steam,steamwebhelper -ErrorAction SilentlyContinue | Stop-Process -Force"
powershell -NoProfile -Command "& '.\scripts\run_renew.cmd' --recompilar --conductor --text 'hola' --timeout-ms 120000" > "$S/$TAG-warmup.log" 2>&1
echo "$TAG $H warm-up exit $? $(grep -a -c 'Compilaci' "$S/$TAG-warmup.log") build lines, $(grep -a -c ' 0 Error' "$S/$TAG-warmup.log") '0 Error' $(date +%H:%M)"
declare -A SET=([A]=none [B]="$AID")
for seed in ${SEEDS:-0 1 2}; do
  for arm in A B; do
    idle
    export BAXY_AYUDAS="${SET[$arm]}" BAXY_MIND_PYTHONPATH="D:/BAXYeval/renew_v1/ab/arr/$H-s$seed"
    lab="nb-$TAG-$arm-s$seed-e2e"; rm -rf "D:/BAXYeval/renew_v1/runs/$lab-e2e"
    powershell -NoProfile -Command "Get-Process CalculatorApp,steam,steamwebhelper -ErrorAction SilentlyContinue | Stop-Process -Force"
    ( for i in $(seq 1 40); do
        m=$(powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" | Select-Object -First 1).CommandLine")
        if [ -n "$m" ]; then echo "$lab model: $(echo "$m" | grep -oE '[^ ]*\.gguf' | head -1)"; break; fi
        sleep 5
      done ) &
    echo "$lab BAXY_AYUDAS=$BAXY_AYUDAS start $(date +%H:%M) front before: $(powershell -NoProfile -ExecutionPolicy Bypass -File "$F/frente_ahora.ps1"; [ $? = 0 ] && echo clean || echo DIRTY-DESKTOP)"
    py -3.12 -X utf8 scripts/renew/bench_e2e.py "$lab" --cases 'D:\BAXYeval\renew_v1\e2e\practice.json' > "$S/$lab.log" 2>&1
    rc=$?; wait
    echo "$lab exit $rc $(date +%H:%M): $(py -3.12 -X utf8 -I "$R/e2e_line.py" "$S/$lab.log" 2>&1 | cut -c1-700)"
    echo "$lab $(py -3.12 -X utf8 -I "$F/e2e_frente.py" "D:/BAXYeval/renew_v1/runs/$lab-e2e/events.jsonl" || echo INVALID-SEED-dirty-front)"
    echo "$lab $(py -3.12 -X utf8 -I "$F/e2e_frente_casos.py" "D:/BAXYeval/renew_v1/runs/$lab-e2e/events.jsonl" "D:/BAXYeval/renew_v1/e2e/practice.json" 2>&1 | tail -1)"
    unset BAXY_MIND_PYTHONPATH
  done
  echo "SEED $seed paired: $(py -3.12 -X utf8 -I "$AY/pareado_ab.py" "nb-$TAG-A" "nb-$TAG-B" $seed 2>&1)"
  echo "SEED-DONE $seed $(date +%H:%M)"
done
for arm in ${FAL_ARMS:-B}; do
  idle; export BAXY_AYUDAS="${SET[$arm]}" BAXY_MIND_PYTHONPATH="D:/BAXYeval/renew_v1/ab/arr/$H-s0"
  lab="nb-$TAG-$arm-fals-s0"; dir="D:/BAXYeval/renew_v1/runs/$lab-falsedades"; rm -rf "$dir"
  echo "$lab BAXY_AYUDAS=$BAXY_AYUDAS start $(date +%H:%M) front: $(powershell -NoProfile -ExecutionPolicy Bypass -File "$F/frente_ahora.ps1")"
  rm -f "$S/$lab.stop"; powershell -NoProfile -ExecutionPolicy Bypass -File "C:/Users/usuario/AppData/Local/Temp/claude/nb/ay/guardia_juegos.ps1" -Stop "$S/$lab.stop" -Log "$S/$lab.juegos.txt" &
  GUARD=$!
  py -3.12 -X utf8 scripts/renew/bench_falsedades.py "$lab" --cases 'D:\BAXYeval\renew_v1\falsedades\practice.json' --no-judge > "$S/$lab.log" 2>&1 &
  BENCH=$!
  until [ -s "$dir/transcripts.json" ] || ! kill -0 $BENCH 2>/dev/null; do sleep 15; done
  [ -s "$dir/transcripts.json" ] || echo "$lab BENCH-DIED without transcripts: $(tail -1 "$S/$lab.log")"
  sleep 10
  powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.Name -match '^py' -and \$_.CommandLine -match 'bench_falsedades' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }"
  wait $BENCH 2>/dev/null
  powershell -NoProfile -Command "Get-Process Baxy,Baxy.Core,llama-server -ErrorAction SilentlyContinue | Stop-Process -Force"
  touch "$S/$lab.stop"; wait $GUARD 2>/dev/null; echo "$lab games closed: $(cat "$S/$lab.juegos.txt" 2>/dev/null | tr '
' ' ')"
  echo "$lab $(date +%H:%M): transcripts $(ls -l "$dir/transcripts.json" | awk '{print $5}') bytes"
  ssh redpc "powershell -NoProfile -Command \"New-Item -ItemType Directory -Force -Path F:/BAXYeval/renew_v1/runs/$lab-falsedades | Out-Null\"" && scp -q "$dir/transcripts.json" "redpc:F:/BAXYeval/renew_v1/runs/$lab-falsedades/transcripts.json" && echo "$lab transcripts sent"
  unset BAXY_MIND_PYTHONPATH
done
unset BAXY_AYUDAS
powershell -NoProfile -Command "'MSConfig services: ' + @((Get-Item 'HKLM:\SOFTWARE\Microsoft\Shared Tools\MSConfig\services' -ErrorAction SilentlyContinue).Property).Count"
echo "E2E-AID-$TAG-DONE"
