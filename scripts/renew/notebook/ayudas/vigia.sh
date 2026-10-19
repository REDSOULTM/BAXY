#!/usr/bin/env bash
# Watches the mailbox on the PC; exits printing the new [PC] lines when any appear. Last seen count in vigia.n.
N=/c/Users/usuario/AppData/Local/Temp/claude/nb/ay/vigia.n
F='C:/Users/usuario/BAXY-coord/buzon.md'
cnt() { ssh -o ConnectTimeout=20 redpc "powershell -NoProfile -Command \"(Get-Content -Encoding utf8 '$F' | Measure-Object -Line).Lines\"" 2>/dev/null | tr -dc 0-9; }
[ -s "$N" ] || cnt > "$N"
while true; do
  c=$(cnt); old=$(cat "$N")
  if [ -n "$c" ] && [ "$c" -gt "$old" ]; then
    new=$(ssh redpc "powershell -NoProfile -Command \"[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-Content -Encoding utf8 '$F' | Select-Object -Skip $old\"")
    echo "$c" > "$N"
    if echo "$new" | grep -q '\[PC\]'; then echo "$new"; exit 0; fi
  fi
  sleep 60
done
