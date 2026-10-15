#!/usr/bin/env bash
# usage: lote.sh <salida> <case-id>...  Corre los casos (ordenados por orden_lote.py) de uno en uno con batch.sh, turnándose con los agentes que
# prueban en el escritorio (turno.sh): antes de cada caso espera a que no haya ningún agent-*.lock vivo, escribe
# live.lock, vuelve a mirar (y cede si un agente se anunció entretanto) y lo mantiene mientras corre el caso. Un agente
# que quiera probar en vivo usa «turno.sh tomar <nombre>»: crea PRIMERO su agent-<nombre>.lock y LUEGO espera a que no
# exista live.lock; al terminar, «turno.sh soltar <nombre>».
L=$(cd "$(dirname "$0")" && pwd)
LOCKS=$(cygpath -u "$LOCALAPPDATA")/BAXY/cu-v3
CU_TURNO_DIR=$LOCKS . "$L/turno.sh"
OUT=$1; shift
# Cases of one app together, closed-app cases first, producers before consumers, elevated/gate apps and the product's
# browser last (orden_lote.py, data in estado/casos.json). CU_ORDEN=0 keeps the order given.
if [ "${CU_ORDEN:-1}" != 0 ] && [ $# -gt 1 ]; then
  ORDENADOS=$(py -3.12 "$L/orden_lote.py" "$@" | tr -d '\r')
  [ -n "$ORDENADOS" ] && set -- $ORDENADOS
  echo "orden: $*" >> "$OUT"
fi
mkdir -p "$LOCKS"
. "$L/registro.sh"
trap 'turno_lote_soltar; registro_parar' EXIT
# Owner-input record for the whole batch, started before the photo (registro_dueno.py): the ledger takes the person as
# idle only where this record covers, so the gaps between cases and the waits inside them are covered too.
SELLO=$(date +%Y%m%d-%H%M%S)
registro_iniciar "$LOCKS/registro-$SELLO.json" >> "$OUT"
# Batch ledger: photo of everything running now (the person's, never touched). batch.sh closes, after each case,
# what was born since with positive provenance; at the end the batch's own processes are swept once more.
export CU_LIBRO="$(cygpath -w "$LOCKS/libro-$SELLO.json")"
powershell -NoProfile -ExecutionPolicy Bypass -File "$L/libro_lote.ps1" -Foto -Libro "$CU_LIBRO" 2>&1 | tr -d '\r' >> "$OUT"
for id in "$@"; do
  # A recorder that died is started again on the same file before the case (registro.sh, registro_vigilar).
  registro_vigilar >> "$OUT"
  turno_lote_tomar "$id" 2>> "$OUT"
  bash "$L/batch.sh" "$id" >> "$OUT" 2>&1
  turno_lote_soltar
done
powershell -NoProfile -ExecutionPolicy Bypass -File "$L/libro_lote.ps1" -Cerrar -Libro "$CU_LIBRO" 2>&1 | tr -d '\r' >> "$OUT"
echo "lote terminado $(date +%H:%M)" >> "$OUT"
