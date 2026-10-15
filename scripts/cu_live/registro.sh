#!/usr/bin/env bash
# Owner-input record for the batch ledger (registro_dueno.py), sourced by lote.sh and batch.sh.
# registro_iniciar <file> [continuar]: starts the recorder with this shell as its root (the recorder exits with it),
# waits for its first write and 3 s more (the ledger needs the 3 s before the photo covered), and exports CU_REGISTRO.
# With "continuar" the file is kept and the recorder takes it up (--continuar: the span nobody recorded counts as the
# person's input), and it waits for that file to be rewritten.
# registro_vigilar: between cases (lote.sh). If the recorder died (pasada r9: it exited at 12:07 with lote.sh alive and
# the ledger closed nothing for 2 h), it starts again on the SAME file and says so on stdout (the batch output).
# registro_parar: asks it to stop (file <registro>.parar) and waits up to 5 s.
# CU_REGISTRO_PY (tests only) replaces the recorder script.
registro_iniciar(){
  local reg=$1 modo=${2:-} here script antes=0
  here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  script=${CU_REGISTRO_PY:-$here/registro_dueno.py}
  rm -f "$reg.parar"
  if [ "$modo" = continuar ] && [ -s "$reg" ]; then antes=$(stat -c %Y "$reg" 2>/dev/null || echo 0); else rm -f "$reg"; modo=; fi
  py -3.12 "$script" --salida "$(cygpath -w "$reg")" --raiz "$(cat /proc/$$/winpid)" \
    --parar "$(cygpath -w "$reg.parar")" ${modo:+--continuar} > /dev/null 2>&1 &
  REGISTRO_PID=$!
  for _ in $(seq 1 150); do
    if [ -n "$modo" ]; then [ "$(stat -c %Y "$reg" 2>/dev/null || echo 0)" -gt "$antes" ] && break
    else [ -s "$reg" ] && break; fi
    sleep 0.2
  done
  [ -s "$reg" ] || { echo "AVISO: sin registro del dueno: el libro lo tratara como activo (no cierra nada suyo)"; return 1; }
  [ -n "$modo" ] || sleep 3
  export CU_REGISTRO="$(cygpath -w "$reg")"
  REGISTRO_ARCHIVO=$reg
}
registro_vigilar(){
  [ -n "${REGISTRO_ARCHIVO:-}" ] || return 0
  kill -0 "$REGISTRO_PID" 2>/dev/null && return 0
  local reg=$REGISTRO_ARCHIVO ultimo
  ultimo=$(date -r "$reg" +%H:%M:%S 2>/dev/null || echo '?')
  echo "AVISO: el registro del dueno murio (ultima escritura $ultimo): se reinicia sobre el mismo archivo $(date +%H:%M:%S); el hueco cuenta como input del dueno"
  registro_iniciar "$reg" continuar
}
registro_parar(){
  [ -n "${REGISTRO_ARCHIVO:-}" ] || return 0
  touch "$REGISTRO_ARCHIVO.parar"
  for _ in $(seq 1 25); do kill -0 "$REGISTRO_PID" 2>/dev/null || break; sleep 0.2; done
  REGISTRO_ARCHIVO=
}
