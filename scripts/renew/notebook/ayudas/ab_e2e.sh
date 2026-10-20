#!/usr/bin/env bash
# Goal AYUDAS, first step (PC 15:08): paired e2e s0-2 of levers 1-4 together. A = e0a7d9923 (worktree l2), B = hub/pc-ayudas
# a3af5c20f (worktree pa), both with their launcher's model c2-e1.0 and the SAME bench (nb-ayudas bench_e2e.py with
# utterances(), copied as scripts/renew/bench_e2e_ay.py; bench.ps1 c684edba). Interleaved A s0, B s0, A s1, ...; the desktop
# checked before each run (frente_ahora.ps1) and per case after it (e2e_frente.py). Never two Baxy.exe.
set -u
P="C:/Users/usuario/Desktop/ETC/Programacion"; AY="C:/Users/usuario/AppData/Local/Temp/claude/nb/ay"
F="C:/Users/usuario/AppData/Local/Temp/claude/nb/ft"; R="C:/Users/usuario/AppData/Local/Temp/claude/nb/reales"; S="$AY/logs"
mkdir -p "$S"
declare -A WT=([A]="$P/BAXY-Renew-l2" [B]="$P/BAXY-Renew-pa") H=([A]=e0a7d9923 [B]=a3af5c20f)
SEEDS="${SEEDS:-0 1 2}"
idle() { while tasklist //FI "IMAGENAME eq Baxy.exe" | grep -qi baxy || tasklist //FI "IMAGENAME eq llama-server.exe" | grep -qi llama-server; do sleep 10; done; }
idle
export BAXY_RENEW_BANKS='D:\BAXYeval\renew_v1'; unset BAXY_MIND_LLM_GGUF BAXY_MIND_PYTHONPATH
for arm in A B; do
  cd "${WT[$arm]}" || exit 1
  [ "$(git rev-parse --short=9 HEAD)" = "${H[$arm]}" ] || { echo "$arm wrong HEAD"; exit 1; }
  for seed in 0 1 2; do
    d="D:/BAXYeval/renew_v1/ab/arr/${H[$arm]}-s$seed"; rm -rf "$d"; mkdir -p "$d"
    git archive "${H[$arm]}" src/baxy_mind | tar -x -C "$d" --strip-components=1
    sed -i "s/\"seed\": 0}/\"seed\": $seed}/" "$d/baxy_mind/mind.py"
    grep -c "\"seed\": $seed}" "$d/baxy_mind/mind.py" | sed "s/^/$arm s$seed seed lines: /"
  done
  if [ "${SKIP_BUILD:-0}" != 1 ]; then
    powershell -NoProfile -Command "Get-Process CalculatorApp,steam,steamwebhelper -ErrorAction SilentlyContinue | Stop-Process -Force"
    powershell -NoProfile -Command "& '.\scripts\run_renew.cmd' --recompilar --conductor --text 'hola' --timeout-ms 120000" > "$S/$arm-warmup.log" 2>&1
    echo "$arm ${H[$arm]} warm-up exit $? $(grep -a -c 'Compilaci' "$S/$arm-warmup.log") build lines $(date +%H:%M)"
    idle
  fi
done
for seed in $SEEDS; do
  for arm in A B; do
    cd "${WT[$arm]}" || exit 1
    export BAXY_MIND_PYTHONPATH="D:/BAXYeval/renew_v1/ab/arr/${H[$arm]}-s$seed"
    lab="nb-ay-$arm-${H[$arm]}-s$seed-e2e"; rm -rf "D:/BAXYeval/renew_v1/runs/$lab-e2e"
    idle
    powershell -NoProfile -Command "Get-Process CalculatorApp,steam,steamwebhelper -ErrorAction SilentlyContinue | Stop-Process -Force"
    ( for i in $(seq 1 40); do
        m=$(powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" | Select-Object -First 1).CommandLine")
        if [ -n "$m" ]; then echo "$lab model: $(echo "$m" | grep -oE '[^ ]*\.gguf' | head -1)"; break; fi
        sleep 5
      done ) &
    echo "$lab start $(date +%H:%M) front before: $(powershell -NoProfile -ExecutionPolicy Bypass -File "$F/frente_ahora.ps1"; [ $? = 0 ] && echo clean || echo DIRTY-DESKTOP)"
    py -3.12 -X utf8 scripts/renew/bench_e2e_ay.py "$lab" --cases 'D:\BAXYeval\renew_v1\e2e\practice.json' > "$S/$lab.log" 2>&1
    rc=$?; wait
    echo "$lab exit $rc $(date +%H:%M): $(py -3.12 -X utf8 -I "$R/e2e_line.py" "$S/$lab.log" 2>&1 | cut -c1-700)"
    echo "$lab $(py -3.12 -X utf8 -I "$F/e2e_frente.py" "D:/BAXYeval/renew_v1/runs/$lab-e2e/events.jsonl" || echo INVALID-SEED-dirty-front)"
    echo "$lab $(py -3.12 -X utf8 -I "$F/e2e_frente_casos.py" "D:/BAXYeval/renew_v1/runs/$lab-e2e/events.jsonl" "D:/BAXYeval/renew_v1/e2e/practice.json" 2>&1 | tail -1)"
    unset BAXY_MIND_PYTHONPATH
  done
  echo "SEED $seed paired: $(py -3.12 -X utf8 -I "$AY/pareado_ab.py" nb-ay-A-e0a7d9923 nb-ay-B-a3af5c20f $seed 2>&1)"
  echo "SEED-DONE $seed $(date +%H:%M)"
done
powershell -NoProfile -Command "'MSConfig services: ' + @((Get-Item 'HKLM:\SOFTWARE\Microsoft\Shared Tools\MSConfig\services' -ErrorAction SilentlyContinue).Property).Count"
echo AB-DONE
