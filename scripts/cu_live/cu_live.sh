#!/usr/bin/env bash
# One live mission in the real App (conductor, same turn as the UI) from this checkout.
# usage: cu_live.sh <tag> <turns-file> [min-idle-s]
# env: CU_PROFILE (default %LOCALAPPDATA%\BAXY\cu-universal-perfil), CU_EVIDENCE (default %LOCALAPPDATA%\BAXY\cu-universal-evidencia)
# Build first in RELEASE (the conductor runs the Release layout): dotnet build src/Baxy.App -c Release; dotnet publish src/Baxy.Core -c Release -r win-x64
set -u
TAG=$1; TURNS=$2; MINIDLE=${3:-90}
SP=$(cd "$(dirname "$0")" && pwd)
WTU=$(cd "$SP/../.." && pwd)
WT=$(cygpath -w "$WTU")
LAD=$(cygpath -u "$LOCALAPPDATA")
PROFILE_W=${CU_PROFILE:-$(cygpath -w "$LAD/BAXY/cu-universal-perfil")}
EVBASE=${CU_EVIDENCE:-$LAD/BAXY/cu-universal-evidencia}
EV="$EVBASE/$TAG"
if powershell -NoProfile -Command "@(Get-Process Baxy,baxy-core -ErrorAction SilentlyContinue).Count" | grep -qv '^0'; then echo "ABORT: BAXY already running"; exit 3; fi
for i in $(seq 1 80); do
  S=$(powershell -NoProfile -ExecutionPolicy Bypass -File "$SP/idle.ps1" 2>/dev/null | tail -1)
  idle=$(echo "$S" | sed 's/.*"idle":\([0-9.]*\).*/\1/'); fs=$(echo "$S" | grep -c '"fullscreen":true'); bat=$(echo "$S" | sed 's/.*"battery":\([0-9]*\).*/\1/')
  ok=$(awk -v a="$idle" -v m="$MINIDLE" 'BEGIN{print (a>=m)?1:0}')
  if [ "$ok" = 1 ] && [ "$fs" = 0 ] && [ "${bat:-100}" -ge 25 ]; then break; fi
  echo "waiting: $S"; sleep 15
  if [ $i = 80 ]; then echo "ABORT: PC in use"; exit 4; fi
done
echo "gate ok: $S"
VOL=$(powershell -NoProfile -ExecutionPolicy Bypass -File "$WTU/scripts/semantic_replay_state.ps1" volume get)
BRI=$(powershell -NoProfile -ExecutionPolicy Bypass -File "$WTU/scripts/semantic_replay_state.ps1" brightness get)
echo "state before: $VOL $BRI"
export BAXY_APP_TRACE="$EV/trace.jsonl"
export BAXY_MIND_MODEL_CALL_AUDIT_PATH="$EV/model_calls.jsonl"
export BAXY_MIND_LLM_INVALID_JSON_DIR="$EV/invalid_json"
export BAXY_MIND_RAW_REPLY_AUDIT_PATH="$EV/raw_replies.jsonl"
export BAXY_MIND_TURN_AUDIT_PATH="$EV/turn_audit.jsonl"
export BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH="$EV/compose_audit.jsonl"
export BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT=1
mkdir -p "$EV"
export BAXY_MIND_PYTHONPATH="$WT\src"
START=$(date +%s)
powershell -NoProfile -ExecutionPolicy Bypass -File "$WTU/scripts/run_baxy_conductor.ps1" -Profile "$PROFILE_W" -Capture "$EV" -TurnsFile "$(cygpath -w "$TURNS")" -TimeoutMs 240000
CODE=$?
END=$(date +%s)
lvl=$(echo "$VOL" | sed 's/.*"level":\([0-9]*\).*/\1/'); mut=$(echo "$VOL" | grep -c '"muted":true'); b=$(echo "$BRI" | sed 's/.*\[\([0-9]*\).*/\1/')
powershell -NoProfile -ExecutionPolicy Bypass -File "$WTU/scripts/semantic_replay_state.ps1" volume set $lvl >/dev/null
powershell -NoProfile -ExecutionPolicy Bypass -File "$WTU/scripts/semantic_replay_state.ps1" volume mute $mut >/dev/null
[ -n "$b" ] && powershell -NoProfile -ExecutionPolicy Bypass -File "$WTU/scripts/semantic_replay_state.ps1" brightness set $b >/dev/null
echo "state after restore: $(powershell -NoProfile -ExecutionPolicy Bypass -File "$WTU/scripts/semantic_replay_state.ps1" volume get) $(powershell -NoProfile -ExecutionPolicy Bypass -File "$WTU/scripts/semantic_replay_state.ps1" brightness get)"
echo "conductor exit=$CODE wall=$((END-START))s evidence=$EV"
