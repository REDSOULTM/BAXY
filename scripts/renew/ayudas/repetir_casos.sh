#!/usr/bin/env bash
# Repeats some cases of one PC e2e arm (setup_failed ones), with the same seed, build and aids; a hung Calculator is
# closed first with CloseMainWindow (never Stop-Process CalculatorApp: it leaves hung windows).
# usage: bash repetir_casos.sh LABEL AIDS MIND_DIR CASES  e.g. ... pc-l8-B-s2 person_folder_sentence F:/BAXYeval/ayudas_v1/minds/pa-c2f13e6fb-s2 E010,E011
set -u
LAB=$1; AIDS=$2; MIND=$3; ONLY=$4
W="C:/Users/usuario/Desktop/ETC/Programacion/BAXY-Renew-ayudas"; cd "$W" || exit 1
NB="$W/scripts/renew/notebook"
export BAXY_RENEW_BANKS='F:\BAXYeval\renew_v1' BAXY_AYUDAS="$AIDS" BAXY_MIND_PYTHONPATH="$MIND"
[ -d "$BAXY_MIND_PYTHONPATH" ] || { echo "no mind copy $MIND"; exit 1; }
while tasklist //FI "IMAGENAME eq Baxy.exe" | grep -qi baxy; do sleep 20; done
powershell -NoProfile -Command "Get-Process ApplicationFrameHost -ErrorAction SilentlyContinue | Where-Object { \$_.MainWindowTitle -match 'Calculadora' } | ForEach-Object { [void]\$_.CloseMainWindow() }"
sleep 3
echo "$LAB-rep front before: $(powershell -NoProfile -ExecutionPolicy Bypass -File "$NB/frente_ahora.ps1"; [ $? = 0 ] && echo clean || echo DIRTY-DESKTOP)"
py -3.12 -X utf8 scripts/renew/bench_e2e.py "$LAB-rep" --cases 'F:\BAXYeval\renew_v1\e2e\practice.json' --only "$ONLY" > "F:/BAXYeval/ayudas_v1/runs/$LAB-rep.log" 2>&1
py -3.12 -X utf8 -c "
import json,sys
rows=[json.loads(l) for l in open(sys.argv[1],encoding='utf-8')]
print('REPETIDOS', [(r['id'], r['ok'], r.get('status')) for r in rows[1:]], 'setup_failed', rows[0]['summary'].get('setup_failed'))
" "F:/BAXYeval/renew_v1/runs/$LAB-rep-e2e/results.jsonl"
powershell -NoProfile -Command "'MSConfig services: ' + @((Get-Item 'HKLM:\SOFTWARE\Microsoft\Shared Tools\MSConfig\services' -ErrorAction SilentlyContinue).Property).Count"
