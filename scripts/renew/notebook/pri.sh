#!/usr/bin/env bash
# A priority job run between the blocks of another measure (PC 05:55): when the checkpoint in <remote dir> has its
# .done and queue job <id> has not run, it runs now (its id goes to cola_nb.done, so the queue skips it later).
# Usage: bash pri.sh <id> <remote dir on the PC holding ft-Q4_K_M.gguf(.done)>
set -u
F="C:/Users/usuario/AppData/Local/Temp/claude/nb/ft"; QF="$F/cola_nb.txt"; DF="$F/cola_nb.done"
id="$1"; REMOTE="$2"
grep -qxF "$id" "$DF" && exit 0
ssh -o BatchMode=yes redpc "powershell -NoProfile -Command \"if (Test-Path '$REMOTE/ft-Q4_K_M.gguf.done') { 'yes' }\"" 2>/dev/null | grep -q yes || exit 0
cmd=$(grep -m1 "^$id|" "$QF"); cmd="${cmd#*|}"
[ -n "$cmd" ] || { echo "pri: no job $id in the queue"; exit 0; }
echo "== job $id (priority, between blocks) $(date +%H:%M)"
bash -c "$cmd"
echo "== job $id exit $? $(date +%H:%M)"
echo "$id" >> "$DF"
