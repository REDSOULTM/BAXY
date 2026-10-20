#!/usr/bin/env bash
# PC, 2026-10-20, after the owner's decision (~02:00): nothing on the PC's desktop or GPU while they play. The lot
# (pc-ayudas 1e01661bc = d7a76adf1 merged) is confirmed on the PC against its own same-day none: e2e s0-2 and
# falsedades s0, both arms on the same build; then the judge over the pending sets, each one waiting for no game.
set -u
LOG=/f/BAXYeval/ayudas_v1/runs; T=/f/BAXYeval/ayudas_v1/tools
games() { powershell -NoProfile -Command "@(Get-Process -ErrorAction SilentlyContinue | Where-Object { \$_.ProcessName -match '^Roblox' -or (\$_.Path -and \$_.Path -like '*\steamapps\common\*') }).Count"; }
wait_free() { while true; do if [ "$(games)" -eq 0 ]; then sleep 180; [ "$(games)" -eq 0 ] && return; fi; echo "  $(date +%H:%M) el dueño juega: espero"; sleep 120; done; }
wait_free
echo "libre $(date +%H:%M)"
cd /c/Users/usuario/Desktop/ETC/Programacion/BAXY-Renew-ayudas || exit 1
echo "lote: $(git log --oneline -1 | cut -c1-80)"
dotnet build src/Baxy.App -c Release --nologo -v:minimal > $LOG/app-build-lote.log 2>&1; echo "App build exit $? $(grep -E 'Warn|Error' $LOG/app-build-lote.log | tail -2 | tr '\n' ' ')"
bash $T/e2e_pc3.sh lote none all "0 1 2" e2e > $LOG/cadena-e2e-lote.log 2>&1
bash $T/e2e_pc3.sh lote none all "0" fal > $LOG/cadena-fal-lote.log 2>&1
export BAXY_RENEW_BANKS='F:\BAXYeval\renew_v1'
for lab in pc-lote-A-s0 pc-lote-B-s0 nb-comb1-B-fals-s0 nb-lote-A-fals-s1 nb-lote-B-fals-s1 nb-lote-A-fals-s2 nb-lote-B-fals-s2 nb-p1c-A-fals-s0 nb-p1c-B-fals-s0; do
  [ -s "/f/BAXYeval/renew_v1/runs/$lab-falsedades/transcripts.json" ] || { echo "$lab: no transcripts"; continue; }
  wait_free
  py -3.12 -X utf8 scripts/renew/bench_falsedades.py "$lab" --judge-only --cases 'F:\BAXYeval\renew_v1\falsedades\practice.json' > $LOG/juez-$lab.log 2>&1
  echo "$lab $(date +%H:%M): $(tail -1 $LOG/juez-$lab.log | cut -c1-400)"
done
echo "MANANA-PC-DONE $(date +%H:%M)"
