#!/usr/bin/env bash
# Notebook writer for the mailbox that shares the file with a reader holding it (tail -F on the PC).
line="- $(date '+%Y-%m-%d %H:%M') [NB] ${1:?falta el texto}"
b64=$(printf '%s' "$line" | base64 -w0)
ssh redpc "powershell -NoProfile -ExecutionPolicy Bypass -File C:/Users/usuario/BAXY-coord/buzon_append_nb.ps1 -B64 $b64"
