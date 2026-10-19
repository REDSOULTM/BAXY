#!/usr/bin/env bash
# The scenes gate (PC 08:33): the mean "ok" of a checkpoint's four scene runs (unchanged, pA, pB, pC) below the floor
# rejects it (its $D/rejected is written, so its e2e, decision2 and falsehoods are skipped).
# Usage: bash puerta_escenas.sh <name> <floor>
set -u
NAME="$1"; FLOOR="$2"; S="C:/Users/usuario/AppData/Local/Temp/claude/nb/reales/logs"; D="D:/BAXYeval/ft_v1/ckpt/$NAME"
oks=""
for v in "" -pA -pB -pC; do
  ok=$(tail -1 "$S/nb-lam-$NAME$v-esc.log" 2>/dev/null | grep -oE '"ok": [0-9]+' | grep -oE '[0-9]+')
  [ -n "$ok" ] || { echo "$NAME scenes gate: run $v missing, not judged"; exit 1; }
  oks="$oks $ok"
done
mean=$(echo "$oks" | awk '{s=0; for (i=1; i<=NF; i++) s+=$i; printf "%.2f", s/NF}')
if awk -v m="$mean" -v f="$FLOOR" 'BEGIN { exit !(m < f) }'; then
  touch "$D/rejected"
  echo "$NAME REJECTED by the scenes gate: mean $mean (runs$oks) below $FLOOR"
else
  echo "$NAME scenes gate passed: mean $mean (runs$oks), floor $FLOOR"
fi
