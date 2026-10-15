#!/usr/bin/env bash
# Buzón entre las dos sesiones de BAXY Renew (PC = redpc, notebook = rednote).
# El archivo vive en el PC; el notebook lo lee y escribe por `ssh redpc` (Tailscale).
#   scripts/buzon.sh escribir "tomo: voz que habla (Piper)"
#   scripts/buzon.sh leer [N]        # últimas N líneas (30 por defecto)
set -euo pipefail
FILE='C:/Users/usuario/BAXY-coord/buzon.md'
if [ "${COMPUTERNAME:-}" = "REDPC" ]; then who=PC; else who=NB; fi

case "${1:-leer}" in
  escribir)
    line="- $(date '+%Y-%m-%d %H:%M') [$who] ${2:?falta el texto}"
    if [ "$who" = PC ]; then
      printf '%s\n' "$line" >> "$FILE"
    else
      b64=$(printf '%s' "$line" | base64 -w0)
      ssh redpc "powershell -NoProfile -Command \"Add-Content -Encoding utf8 -Path '$FILE' -Value ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('$b64')))\""
    fi
    ;;
  leer)
    n="${2:-30}"
    if [ "$who" = PC ]; then
      tail -n "$n" "$FILE"
    else
      ssh redpc "powershell -NoProfile -Command \"[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-Content -Encoding utf8 -Tail $n '$FILE'\""
    fi
    ;;
  *) echo "uso: scripts/buzon.sh escribir \"texto\" | leer [N]" >&2; exit 2 ;;
esac
