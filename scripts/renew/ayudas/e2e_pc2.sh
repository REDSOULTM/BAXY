#!/usr/bin/env bash
# PC e2e (owner's authorization of 2026-10-19 ~15:20): two arms of the SAME build of hub/pc-ayudas, told apart only by
# BAXY_AYUDAS, interleaved by seed (A s0, B s0, A s1, ...), so the day and the desktop are the same for both.
# usage: bash e2e_pc2.sh TAG AIDS_A AIDS_B [SEEDS] [KIND]   e.g.  e2e_pc.sh l5a none turn_facts "0 1 2" e2e
#   KIND e2e (practice.json) or fal (falsedades practice, transcripts only: the 35B judge runs later with --judge-only)
set -u
TAG=$1; AIDS_A=$2; AIDS_B=$3; SEEDS=${4:-0 1 2}; KIND=${5:-e2e}
W="C:/Users/usuario/Desktop/ETC/Programacion/BAXY-Renew-ayudas"
M="F:/BAXYeval/ayudas_v1/minds"; LOG="F:/BAXYeval/ayudas_v1/runs"
NB="$W/scripts/renew/notebook"
cd "$W" || exit 1
H=$(git rev-parse --short=9 HEAD)
export BAXY_RENEW_BANKS='F:\BAXYeval\renew_v1'; unset BAXY_MIND_LLM_GGUF
llamas() { tasklist //FI "IMAGENAME eq llama-server.exe" | grep -ci llama-server; }
# The mind of this build, one copy per seed (the seed of the decision, as the notebook's arr copies).
for s in $SEEDS; do
  d="$M/pa-$H-s$s"
  if [ ! -d "$d" ]; then
    mkdir -p "$d" && cp -r src/baxy_mind "$d/" && rm -rf "$d/baxy_mind/__pycache__"
    sed -i "s/\"seed\": 0}/\"seed\": $s}/" "$d/baxy_mind/mind.py"
    grep -c "\"seed\": $s}" "$d/baxy_mind/mind.py" | grep -q '^1$' || { echo "seed patch failed $d"; exit 1; }
  fi
done
echo "e2e_pc $TAG on $H ($(git log --oneline -1 | cut -c11-70)) $(date +%H:%M); A=$AIDS_A B=$AIDS_B kind=$KIND"
while tasklist //FI "IMAGENAME eq Baxy.exe" | grep -qi baxy; do echo "a Baxy.exe is open (the owner's?): waiting"; sleep 30; done
while [ "$(llamas)" -ge 3 ]; do sleep 20; done
export BAXY_MIND_PYTHONPATH="$M/pa-$H-s0"
powershell -NoProfile -Command "& '.\scripts\run_renew.cmd' --recompilar --conductor --text 'hola' --timeout-ms 120000" > "$LOG/pc-$TAG-$KIND-warmup.log" 2>&1
echo "warm-up exit $? $(grep -a -c 'Compilaci' "$LOG/pc-$TAG-$KIND-warmup.log") build lines"
# Files the model writes at the top of the home instead of the bank's subfolder (E006/E017/E024 «notas.txt») would
# meet the next run: every top-level file of the home that was not there when this script started goes before each run
# (a copy is kept beside the logs).
HOME_SNAPSHOT="$LOG/pc-$TAG-$KIND-home-antes.txt"; ls -1A /c/Users/usuario > "$HOME_SNAPSHOT"
clean_home() {
  mkdir -p "$LOG/restos-home"
  for f in /c/Users/usuario/*; do
    [ -f "$f" ] || continue
    grep -qxF "$(basename "$f")" "$HOME_SNAPSHOT" && continue
    cp "$f" "$LOG/restos-home/$(date +%H%M%S)-$(basename "$f")" && rm -f "$f" && echo "  resto del banco quitado del home: $(basename "$f")"
  done
}
for s in $SEEDS; do
  for arm in A B; do
    # AIDS_A "-": no arm A; the same day's reference (BAXY_AYUDAS=none on this machine) is reused.
    if [ $arm = A ] && [ "$AIDS_A" = "-" ]; then continue; fi
    if [ $arm = A ]; then export BAXY_AYUDAS="$AIDS_A"; else export BAXY_AYUDAS="$AIDS_B"; fi
    export BAXY_MIND_PYTHONPATH="$M/pa-$H-s$s"
    while [ "$(llamas)" -ge 3 ]; do sleep 20; done
    while tasklist //FI "IMAGENAME eq Baxy.exe" | grep -qi baxy; do sleep 20; done
    powershell -NoProfile -Command "Get-Process steam,steamwebhelper -ErrorAction SilentlyContinue | Stop-Process -Force" 2>/dev/null
    lab="pc-$TAG-$arm-s$s"
    clean_home
    echo "$lab BAXY_AYUDAS=$BAXY_AYUDAS front before: $(powershell -NoProfile -ExecutionPolicy Bypass -File "$NB/frente_ahora.ps1"; [ $? = 0 ] && echo clean || echo DIRTY-DESKTOP)"
    since=$(date '+%Y-%m-%dT%H:%M:%S')
    if [ "$KIND" = e2e ]; then
      rm -rf "F:/BAXYeval/renew_v1/runs/$lab-e2e"
      py -3.12 -X utf8 scripts/renew/bench_e2e.py "$lab" --cases 'F:\BAXYeval\renew_v1\e2e\practice.json' > "$LOG/$lab.log" 2>&1
      echo "$lab $(date +%H:%M): $(head -1 "F:/BAXYeval/renew_v1/runs/$lab-e2e/results.jsonl" | cut -c1-200)"
      echo "$lab $(py -3.12 -X utf8 -I "$NB/e2e_frente.py" "F:/BAXYeval/renew_v1/runs/$lab-e2e/events.jsonl" || echo INVALID-SEED-dirty-front)"
      echo "$lab $(py -3.12 -X utf8 -c "
import json,sys
rows=[json.loads(l) for l in open(sys.argv[1],encoding='utf-8')]
bad=[r['id']+':'+str(r.get('status')) for r in rows[1:] if r.get('status') not in ('ok','fallo')]
print('cases not ok/fallo:', bad, 'setup_failed:', rows[0]['summary'].get('setup_failed'), 'NO:', [r['id'] for r in rows[1:] if not r.get('ok')])
" "F:/BAXYeval/renew_v1/runs/$lab-e2e/results.jsonl")"
    else
      dir="F:/BAXYeval/renew_v1/runs/$lab-falsedades"; rm -rf "$dir"
      py -3.12 -X utf8 scripts/renew/bench_falsedades.py "$lab" --no-judge --cases 'F:\BAXYeval\renew_v1\falsedades\practice.json' > "$LOG/$lab-fal.log" 2>&1
      echo "$lab $(date +%H:%M): $(tail -1 "$LOG/$lab-fal.log" | cut -c1-120); transcripts $(stat -c %s "$dir/transcripts.json" 2>/dev/null) bytes"
    fi
    powershell -NoProfile -Command "'MSConfig services: ' + @((Get-Item 'HKLM:\SOFTWARE\Microsoft\Shared Tools\MSConfig\services' -ErrorAction SilentlyContinue).Property).Count + '; 7040 since $since: ' + @(Get-WinEvent -FilterHashtable @{LogName='System'; Id=7040; StartTime=[datetime]'$since'} -ErrorAction SilentlyContinue | ForEach-Object { \$_.Message.Substring(0, [Math]::Min(90, \$_.Message.Length)) }) -join ' | '"
  done
done
unset BAXY_AYUDAS BAXY_MIND_PYTHONPATH
echo "E2E-PC-$TAG-DONE $(date +%H:%M)"
