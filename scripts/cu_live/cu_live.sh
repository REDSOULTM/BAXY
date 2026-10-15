#!/usr/bin/env bash
# One live mission in the real App (conductor, same turn as the UI) from this checkout.
# usage: cu_live.sh <tag> <turns-file> [pausa-dueño-s]
# env: CU_PROFILE (default %LOCALAPPDATA%\BAXY\cu-universal-perfil), CU_EVIDENCE (default %LOCALAPPDATA%\BAXY\cu-universal-evidencia)
#      CU_MOLESTIA=1 (defecto) mide la molestia con el usuario simulado (molestia/medidor.py -> <evidencia>/molestia.json);
#      CU_MOLESTIA=0 lo apaga (latencia sin usuario simulado). En ambos casos sólo se espera a que el input REAL del
#      dueño haga una pausa de [pausa-dueño-s] (2 s por defecto), no a que el PC quede inactivo.
#      CU_TRAS_BIENVENIDA=1 (sólo medida; defecto 0): el primer turno se envía con la bienvenida ya compuesta y
#      publicada (conductor --after-welcome), no en cuanto la mente está lista. Da la latencia «tras la bienvenida»;
#      apagada da la de arranque en frío. La línea «runtime» de events.jsonl dice cuál fue (afterWelcome, welcomeSettled).
# Build first in RELEASE (the conductor runs the Release layout): dotnet build src/Baxy.App -c Release; dotnet publish src/Baxy.Core -c Release -r win-x64
set -u
TAG=$1; TURNS=$2; PAUSA=${3:-2}; MOL=${CU_MOLESTIA:-1}
SP=$(cd "$(dirname "$0")" && pwd)
WTU=$(cd "$SP/../.." && pwd)
WT=$(cygpath -w "$WTU")
LAD=$(cygpath -u "$LOCALAPPDATA")
PROFILE_W=${CU_PROFILE:-$(cygpath -w "$LAD/BAXY/cu-universal-perfil")}
EVBASE=${CU_EVIDENCE:-$LAD/BAXY/cu-universal-evidencia}
EV="$EVBASE/$TAG"
# Time of each part of the live case, printed as one «tiempos_cu_live:» line (batch.sh adds it to its «tiempos:»).
T0=${EPOCHREALTIME/[.,]/}
t_seg(){ local d=$(( ${EPOCHREALTIME/[.,]/} - $1 )); printf '%d.%d' $(( d/1000000 )) $(( d%1000000/100000 )); }
# Gates, one powershell a look (idle.ps1: BAXY processes, fullscreen, battery; it was three powershells before):
# - el Core del caso anterior puede tardar unos segundos en salir: se espera hasta 30 s antes de abortar;
# - sólo cabe un 4B en la GPU: se espera (hasta 5 min) a que la VRAM ocupada baje de 1,5 GB y se anota quién la ocupa;
# - batería y pantalla completa (hasta 20 min). La inactividad ya no se exige: el dueño puede estar usando el PC.
# Each wait looks at every gate again: what passed before the wait is not taken as still true after it.
nb=0; nv=0; ni=0
while :; do
  S=$(powershell -NoProfile -ExecutionPolicy Bypass -File "$SP/idle.ps1" 2>/dev/null | tail -1 | tr -d '\r')
  baxy=$(echo "$S" | sed -n 's/.*"baxy":\([0-9]*\).*/\1/p')
  # Unreadable: taken as BAXY alive (fail closed, as the Get-Process look it replaces).
  if [ "${baxy:-1}" != 0 ]; then
    nb=$((nb+1)); [ $nb -ge 15 ] && { echo "ABORT: BAXY already running"; exit 3; }
    sleep 2; continue
  fi
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -dc '0-9')
  if [ -n "$used" ] && [ "$used" -gt 1500 ]; then
    echo "waiting vram: ${used} MiB $(nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null | tr '\n' ';')"
    nv=$((nv+1)); [ $nv -ge 30 ] && { echo "ABORT: GPU busy"; exit 5; }
    sleep 10; continue
  fi
  fs=$(echo "$S" | grep -c '"fullscreen":true'); bat=$(echo "$S" | sed -n 's/.*"battery":\([0-9]*\).*/\1/p')
  if [ "$fs" != 0 ] || [ "${bat:-100}" -lt 25 ]; then
    echo "waiting: $S"
    ni=$((ni+1)); [ $ni -ge 80 ] && { echo "ABORT: fullscreen or low battery"; exit 4; }
    sleep 15; continue
  fi
  break
done
T_PUERTAS=$(t_seg $T0); T1=${EPOCHREALTIME/[.,]/}
mkdir -p "$EV"
rm -f "$EV/molestia.json"
CTL="$EV/molestia-control"
if [ "$MOL" = 1 ]; then
  rm -rf "$CTL"; mkdir -p "$CTL"
  # El medidor espera la pausa del dueño, muestra la ventana del usuario simulado y empieza a medir cuando la App
  # escribe la línea «runtime» de events.jsonl (justo antes del primer turno); para con el archivo «parar».
  py -3.12 "$SP/molestia/medidor.py" medir --control "$(cygpath -w "$CTL")" --salida "$(cygpath -w "$EV/molestia.json")" \
    --inicio "eventos:$(cygpath -w "$EV/events.jsonl")" --pausa "$PAUSA" > "$EV/molestia.log" 2>&1 &
  MPID=$!
  # Volume and brightness are read while the meter waits for the owner's pause (read only: no input, no focus).
  VB=$(powershell -NoProfile -ExecutionPolicy Bypass -File "$SP/volumen_brillo.ps1" -Leer | tr -d '\r')
  while [ ! -f "$CTL/listo.json" ]; do
    if ! kill -0 $MPID 2>/dev/null; then echo "ABORT: PC in use ($(tail -1 "$EV/molestia.log"))"; exit 4; fi
    sleep 0.2
  done
  echo "gate ok: $S molestia=on $(cat "$CTL/listo.json")"
else
  py -3.12 "$SP/molestia/medidor.py" espera --pausa "$PAUSA" || { echo "ABORT: PC in use"; exit 4; }
  echo "gate ok: $S molestia=off"
fi
# Volume and brightness read in one powershell (volumen_brillo.ps1) and given back after the case in another one.
[ "$MOL" = 1 ] || VB=$(powershell -NoProfile -ExecutionPolicy Bypass -File "$SP/volumen_brillo.ps1" -Leer | tr -d '\r')
VOL=${VB%% *}; BRI=${VB#* }
T_MEDIDOR=$(t_seg $T1)
echo "state before: $VOL $BRI"
export BAXY_APP_TRACE="$EV/trace.jsonl"
export BAXY_MIND_MODEL_CALL_AUDIT_PATH="$EV/model_calls.jsonl"
export BAXY_MIND_LLM_INVALID_JSON_DIR="$EV/invalid_json"
export BAXY_MIND_RAW_REPLY_AUDIT_PATH="$EV/raw_replies.jsonl"
export BAXY_MIND_TURN_AUDIT_PATH="$EV/turn_audit.jsonl"
export BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH="$EV/compose_audit.jsonl"
export BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT=1
export BAXY_MIND_PYTHONPATH="$WT\src"
START=$(date +%s)
TRAS=""; [ "${CU_TRAS_BIENVENIDA:-0}" = 1 ] && TRAS="-AfterWelcome"
# Owner order (2026-10-10): every test runs in bypass mode; the cases listed in cases/MODO_NORMAL.txt (one per family
# that confirms) run in Normal to check the confirmation question shows and is faithful. The Core rereads the
# setting from the profile on every invocation (ConfirmationModeStore).
MODO=bypass; grep -qx "${TAG#v2-}" <(tr -d '\r' < "$SP/cases/MODO_NORMAL.txt") && MODO=normal
printf %s "$MODO" > "$(cygpath -u "$PROFILE_W")/confirmation-mode"; echo "modo=$MODO"
powershell -NoProfile -ExecutionPolicy Bypass -File "$WTU/scripts/run_baxy_conductor.ps1" -Profile "$PROFILE_W" -Capture "$EV" -TurnsFile "$(cygpath -w "$TURNS")" -TimeoutMs 240000 $TRAS
CODE=$?
END=$(date +%s)
T2=${EPOCHREALTIME/[.,]/}
lvl=$(echo "$VOL" | sed 's/.*"level":\([0-9]*\).*/\1/'); mut=$(echo "$VOL" | grep -c '"muted":true'); b=$(echo "$BRI" | sed 's/.*\[\([0-9]*\).*/\1/')
# Evidence of the mission taken now, before the meter gives the front back to the person's window (BANCO_72 r23: after.png,
# taken later by batch.sh, showed Discord over the result): the profile journal's entries of this run (journal_caso.py,
# <ev>/journal-caso.json: BAXY's UIA reads and receipts, not its reply) and a photo of the last window BAXY touched,
# by PrintWindow, without focus or input, or of the screen (captura_mision.ps1, <ev>/after-mision.png and .json). The
# simulated user's own window is never the one photographed.
EXCL=""; [ "$MOL" = 1 ] && EXCL=$(sed -n 's/.*"hwnd": *\([0-9]*\).*/\1/p' "$CTL/listo.json" 2>/dev/null)
py -3.12 "$SP/journal_caso.py" "$(cygpath -w "$EV")" --journal "$PROFILE_W\journal\missions.jsonl" 2>&1 | tr -d '\r' | tail -1
powershell -NoProfile -ExecutionPolicy Bypass -File "$SP/captura_mision.ps1" -Dir "$(cygpath -w "$EV")" -Excluir "$EXCL" 2>&1 | tr -d '\r' | tail -1
T_CAPTURA=$(t_seg $T2); T2=${EPOCHREALTIME/[.,]/}
devolver(){ powershell -NoProfile -ExecutionPolicy Bypass -File "$SP/volumen_brillo.ps1" -Devolver -Nivel "$lvl" -Silencio "$mut" ${b:+-Brillo "$b"} | tr -d '\r'; }
if [ "$MOL" = 1 ]; then
  touch "$CTL/parar"
  # Given back during the meter's 3 s tail (TAIL_S + FINAL_WAIT_S): a volume or brightness set is no input and no focus.
  RESTO=$(devolver)
  for i in $(seq 1 100); do kill -0 $MPID 2>/dev/null || break; sleep 0.2; done
  if kill -0 $MPID 2>/dev/null; then
    WPID=$(sed 's/.*"pid": *\([0-9]*\).*/\1/' "$CTL/listo.json")
    echo "medidor colgado: se cierra por PID exacto $WPID"; taskkill //PID "$WPID" //F
  fi
  tail -1 "$EV/molestia.log"
else
  RESTO=$(devolver)
fi
echo "state after restore: $RESTO"
echo "conductor exit=$CODE wall=$((END-START))s evidence=$EV"
echo "tiempos_cu_live: puertas=$T_PUERTAS medidor_y_volumen=$T_MEDIDOR conductor=$((END-START)) captura_mision=$T_CAPTURA cierre=$(t_seg $T2)"
