#!/usr/bin/env bash
# Sourced by batch.sh. ps <script.ps1> [args...]: runs a harness helper in the batch's persistent PowerShell
# (servidor_ps.ps1) and prints its output as «powershell -File <script> args 2>&1» would. Started by servidor_ps_iniciar
# after CU_LIBRO / CU_REGISTRO are exported (the server keeps the environment it started with); it ends when this shell
# exits (its stdin closes). Without the server (CU_SERVIDOR_PS=0) every call spawns its own powershell.
# Every call has a ceiling (2026-10-09, t-menu-1: «--- verify» waited 11 min on a hung secondary explorer.exe and the
# batch stood still until it was killed by hand): CU_PS_TOPE seconds (300), or PS_TOPE=<s> for one call
# («PS_TOPE=60 ps verificar.ps1 ...»). When it runs out, or the server dies in the middle of a call, the call prints a
# line with "verificado":false and "resultado":"sin_respuesta" (the callers that look for it stop as they would on a
# state that did not verify), an AVISO goes to stderr (the batch output), the server is stopped by its exact pid and a
# new one starts at the next call made from the batch's own shell (a call inside $(...) runs in a subshell, where a
# new server would die with it: there the call spawns its own powershell, also under the ceiling).
SERVIDOR_PS_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SERVIDOR_PS_REINICIOS=0
servidor_ps_iniciar(){
  [ "${CU_SERVIDOR_PS:-1}" = 0 ] && return 0
  local padre; padre=$(cat /proc/$$/winpid 2>/dev/null)
  coproc SERVIDOR_PS { exec powershell -NoProfile -ExecutionPolicy Bypass -File "$SERVIDOR_PS_DIR/servidor_ps.ps1" -Padre "${padre:-0}" 2>&1; }
  # Bash closes a coprocess's own descriptors in subshells ($(ps ...)): plain copies are inherited.
  exec {SERVIDOR_PS_W}>&"${SERVIDOR_PS[1]}" {SERVIDOR_PS_R}<&"${SERVIDOR_PS[0]}"
  SERVIDOR_PS_VIVO=$SERVIDOR_PS_PID
}
servidor_ps_parar(){
  # The server by its exact pid: the bash stub of the coprocess and the powershell.exe behind it (its Windows pid).
  local p=$1 w; [ -n "$p" ] || return 0
  w=$(cat "/proc/$p/winpid" 2>/dev/null)
  kill -9 "$p" 2>/dev/null
  [ -n "$w" ] && taskkill //F //PID "$w" > /dev/null 2>&1
  return 0
}
servidor_ps_revivir(){
  # In the batch's own shell only, once the server stopped answering or died: a new one (at most 5 a batch).
  [ "${CU_SERVIDOR_PS:-1}" = 0 ] && return 0
  [ -n "${SERVIDOR_PS_VIVO:-}" ] || return 0
  [ -z "${SERVIDOR_PS_CAIDO:-}" ] && kill -0 "$SERVIDOR_PS_VIVO" 2>/dev/null && return 0
  [ "${BASHPID:-$$}" = "$$" ] || return 0
  servidor_ps_parar "$SERVIDOR_PS_VIVO"; wait "$SERVIDOR_PS_VIVO" 2>/dev/null
  exec {SERVIDOR_PS_W}>&- {SERVIDOR_PS_R}<&-
  SERVIDOR_PS_VIVO=; SERVIDOR_PS_CAIDO=
  [ "$SERVIDOR_PS_REINICIOS" -ge 5 ] && return 0
  SERVIDOR_PS_REINICIOS=$((SERVIDOR_PS_REINICIOS+1))
  echo "AVISO: servidor PowerShell del arnes reiniciado ($SERVIDOR_PS_REINICIOS)" >&2
  servidor_ps_iniciar
}
servidor_ps_sin_respuesta(){
  # $1 script, $2 ceiling in seconds.
  local n; n=$(basename "$1")
  echo "AVISO: ${n%.ps1} sin respuesta tras ${2}s (tope del arnes): la llamada se corta y el lote sigue" >&2
  printf '{"estado":"servidor_ps","resultado":"sin_respuesta","verificado":false,"script":"%s","tope_s":%s}\n' "$n" "$2"
}
ps(){
  local tope=${PS_TOPE:-${CU_PS_TOPE:-300}}
  servidor_ps_revivir
  if [ -n "${SERVIDOR_PS_VIVO:-}" ] && kill -0 "$SERVIDOR_PS_VIVO" 2>/dev/null; then
    local s=$1 linea fin resta; shift
    printf '%s\n' '@@baxy-llamada@@' "$(cygpath -w "$s")" "$@" '@@baxy-args-fin@@' >&"$SERVIDOR_PS_W"
    fin=$((SECONDS+tope))
    while resta=$((fin-SECONDS)); [ "$resta" -gt 0 ] && IFS= read -r -t "$resta" linea <&"$SERVIDOR_PS_R"; do
      case $linea in '@@baxy-fin@@'*) return 0 ;; esac
      printf '%s\n' "$linea"
    done
    # Out of time, or the server died: stopped by its exact pid; the next call from the batch's shell starts another.
    servidor_ps_parar "$SERVIDOR_PS_VIVO"; SERVIDOR_PS_CAIDO=1
    servidor_ps_sin_respuesta "$s" "$tope"
    return 1
  fi
  local rc; timeout -k 5 "$tope" powershell -NoProfile -ExecutionPolicy Bypass -File "$@" 2>&1; rc=$?
  case $rc in 124|137) servidor_ps_sin_respuesta "$1" "$tope"; return 1 ;; esac
  return $rc
}
