#!/usr/bin/env bash
# Phase 4 (FT/proveedores goal): the new holdout's chosen decision cases run ONCE through the real product of the final
# HEAD, rebuilt (--recompilar), its own launcher's model and mind; judged by effect, receipts and reply (OK /
# EJECUTA_MAL / OTRA_OP / SIN_RESPUESTA, and revisar_falsedad); the MSConfig incident checked; files BAXY left outside
# the sandbox in quarantine; the judged rows to the PC.
# PC 2026-10-19 10:52: the desktop checked before the run and per case after it (e2e_frente_casos.py).
# Goal «ayudas»: with BAXY_AYUDAS (the kept aids) exported for the product, outputs under ayudas_v1.
# usage: AIDS=<ids> bash correr_fase4_ay.sh <holdout.json> <ids.json> <worktree> <HEAD> <label>
set -u
HO="$1"; IDS="$2"; W="$3"; H="$4"; LAB="$5"
F4="C:/Users/usuario/AppData/Local/Temp/claude/nb/fase4ay"; S="C:/Users/usuario/AppData/Local/Temp/claude/nb/reales/logs"
OUT="D:/BAXYeval/ayudas_v1/fase4"; mkdir -p "$OUT"
while tasklist //FI "IMAGENAME eq Baxy.exe" | grep -qi baxy; do sleep 10; done
while [ -e "D:/BAXYeval/ft_v1/gpu.lock" ]; do sleep 20; done
touch D:/BAXYeval/ft_v1/gpu.lock
git -C "$W" fetch -q hub && git -C "$W" checkout -q --detach "$H" || exit 1
echo "HEAD $(git -C "$W" log --oneline -1 | cut -c1-70) $(date +%H:%M)"
py -3.12 -X utf8 -I "$F4/hacer_fase4_ay.py" "$HO" "$IDS" "$OUT/$LAB-cases.json" "$OUT/$LAB-audit.json" || exit 1
cd "$W" || exit 1
export BAXY_RENEW_BANKS='D:\BAXYeval\renew_v1'; unset BAXY_MIND_LLM_GGUF BAXY_MIND_PYTHONPATH
# The lot turns its kept aids on with BAXY_AYUDAS unset (PC 23:45); AIDS only to force a list.
if [ -n "${AIDS:-}" ]; then export BAXY_AYUDAS="$AIDS"; else unset BAXY_AYUDAS; fi
echo "BAXY_AYUDAS=${BAXY_AYUDAS:-<unset: the lot>}"
powershell -NoProfile -Command "Get-Process CalculatorApp,steam,steamwebhelper -ErrorAction SilentlyContinue | Stop-Process -Force"
powershell -NoProfile -Command "& '.\scripts\run_renew.cmd' --recompilar --conductor --text 'hola' --timeout-ms 120000" > "$S/$LAB-warmup.log" 2>&1
echo "warm-up exit $? $(date +%H:%M): $(grep -a -c 'Compilaci' "$S/$LAB-warmup.log") build lines"
( for i in $(seq 1 60); do
    m=$(powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" | Select-Object -First 1).CommandLine")
    if [ -n "$m" ]; then echo "model: $(echo "$m" | grep -oE '[^ ]*\.gguf' | head -1)"; break; fi
    sleep 5
  done ) &
echo "front before: $(powershell -NoProfile -ExecutionPolicy Bypass -File "C:/Users/usuario/AppData/Local/Temp/claude/nb/ft/frente_ahora.ps1"; [ $? = 0 ] && echo clean || echo DIRTY-DESKTOP)"
t0=$(date +%s)
py -3.12 -X utf8 scripts/renew/bench_e2e.py "$LAB" --cases "$(cygpath -w "$OUT/$LAB-cases.json")" > "$S/$LAB.log" 2>&1
wait
t1=$(date +%s)
n=$(py -3.12 -c "import json;print(len(json.load(open(r'$(cygpath -w "$OUT/$LAB-cases.json")',encoding='utf-8'))))")
echo "run exit $? $(date +%H:%M): $n cases in $(( (t1 - t0) / 60 )) min ($(( (t1 - t0) / (n > 0 ? n : 1) )) s per case)"
R="D:/BAXYeval/renew_v1/runs/$LAB-e2e/results.jsonl"
echo "$(py -3.12 -X utf8 -I "C:/Users/usuario/AppData/Local/Temp/claude/nb/ft/e2e_frente_casos.py" "D:/BAXYeval/renew_v1/runs/$LAB-e2e/events.jsonl" "$OUT/$LAB-cases.json" || echo DIRTY-FRONT-CASES)"
py -3.12 -X utf8 -I "$F4/juzgar_fase4_ay.py" "$R" "$OUT/$LAB-audit.json" "$OUT/$LAB-judged.jsonl"
powershell -NoProfile -Command "'MSConfig services: ' + @((Get-Item 'HKLM:\SOFTWARE\Microsoft\Shared Tools\MSConfig\services' -ErrorAction SilentlyContinue).Property).Count; 'disabled 7040 (3h): ' + @(Get-WinEvent -FilterHashtable @{LogName='System';Id=7040;StartTime=(Get-Date).AddHours(-3)} -ErrorAction SilentlyContinue | ? { \$_.Message -match 'deshabilitado' }).Count"
echo "quarantined: $(grep -c QUARANTINED "$S/$LAB.log")"
rm -f D:/BAXYeval/ft_v1/gpu.lock
ssh redpc "powershell -NoProfile -Command \"New-Item -ItemType Directory -Force -Path F:/BAXYeval/ayudas_v1/fase4 | Out-Null\"" \
  && scp -q "$OUT/$LAB-judged.jsonl" "redpc:F:/BAXYeval/ayudas_v1/fase4/$LAB-judged.jsonl" && echo "judged sent"
echo "FASE4-$LAB-DONE"
