#!/usr/bin/env bash
# Turno del escritorio entre el lote (lote.sh) y los agentes que prueban en vivo. Cada lado ANUNCIA primero y MIRA
# después (si los dos miraran antes de anunciar, los dos verían el escritorio libre y correrían a la vez):
# - el agente crea su agent-<nombre>.lock y sólo entonces espera a que no exista live.lock (y a que ningún otro agente
#   tenga el escritorio: agentes.d, que mkdir crea de forma atómica para uno solo);
# - el lote, antes de cada caso, espera a que no haya agent-*.lock, escribe live.lock y vuelve a mirar: si un agente
#   se anunció entretanto, borra live.lock y le cede el turno.
# Un agent-*.lock sin tocar en CU_TURNO_VIEJO_MIN minutos (30) es de un agente muerto: se avisa y no se espera. El
# agente que espera lo renueva en cada mirada; una prueba suya de más de 30 min lo renueva con «turno.sh tomar» otra vez.
#
# Uso de un agente:
#   bash scripts/cu_live/turno.sh tomar <nombre> [segundos]   # 0: tiene el turno; 3: sigue en cola (lock puesto),
#                                                              # se vuelve a llamar igual; nunca se borra a mano
#   bash scripts/cu_live/turno.sh soltar <nombre>              # siempre al terminar, también si se rinde
# lote.sh lo carga con «. turno.sh» y usa turno_lote_tomar <caso> / turno_lote_soltar.
TURNO_DIR=${CU_TURNO_DIR:-$(cygpath -u "$LOCALAPPDATA")/BAXY/cu-v3}
TURNO_VIEJO_MIN=${CU_TURNO_VIEJO_MIN:-30}

# The agent locks that are still alive (touched within TURNO_VIEJO_MIN minutes), one path a line; the dead ones are
# reported on stderr once per call and ignored.
turno_agentes_vivos(){
  local f
  for f in "$TURNO_DIR"/agent-*.lock; do
    [ -e "$f" ] || continue
    if [ -n "$(find "$f" -mmin +"$TURNO_VIEJO_MIN" 2>/dev/null)" ]; then
      echo "aviso: lock de agente sin tocar en ${TURNO_VIEJO_MIN} min, no se espera: $f" >&2
      continue
    fi
    echo "$f"
  done
}

turno_lote_tomar(){
  local caso=$1
  mkdir -p "$TURNO_DIR"
  while :; do
    while [ -n "$(turno_agentes_vivos 2>/dev/null)" ]; do sleep 5; done
    echo "$caso $(date +%H:%M:%S)" > "$TURNO_DIR/live.lock"
    # Announced; an agent that announced itself before this line saw no live.lock and may be on the desktop now.
    [ -z "$(turno_agentes_vivos)" ] && return 0
    rm -f "$TURNO_DIR/live.lock"
  done
}

turno_lote_soltar(){ rm -f "$TURNO_DIR/live.lock"; }

turno_agente_tomar(){
  local nombre=$1 segundos=${2:-540} lock dueno
  lock="$TURNO_DIR/agent-$nombre.lock"
  mkdir -p "$TURNO_DIR"
  local fin=$((SECONDS + segundos))
  while :; do
    # First the announcement (renewed on every look, so a waiting agent never reads as dead), then the look.
    echo "$nombre $(date +%H:%M:%S)" > "$lock"
    if [ ! -e "$TURNO_DIR/live.lock" ]; then
      if mkdir "$TURNO_DIR/agentes.d" 2>/dev/null; then
        echo "$nombre" > "$TURNO_DIR/agentes.d/dueno"
        return 0
      fi
      dueno=$(cat "$TURNO_DIR/agentes.d/dueno" 2>/dev/null)
      [ "$dueno" = "$nombre" ] && return 0
      # The desktop held by an agent whose lock is gone or dead: it is freed for the next look.
      if [ -n "$dueno" ] && ! turno_agentes_vivos 2>/dev/null | grep -qx "$TURNO_DIR/agent-$dueno.lock"; then
        rm -rf "$TURNO_DIR/agentes.d"
        continue
      fi
    fi
    [ $SECONDS -ge $fin ] && return 3
    sleep 5
  done
}

turno_agente_soltar(){
  local nombre=$1
  [ "$(cat "$TURNO_DIR/agentes.d/dueno" 2>/dev/null)" = "$nombre" ] && rm -rf "$TURNO_DIR/agentes.d"
  rm -f "$TURNO_DIR/agent-$nombre.lock"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  case "${1:-}" in
    tomar) [ -n "${2:-}" ] || { echo "uso: turno.sh tomar <nombre> [segundos]" >&2; exit 2; }
           turno_agente_tomar "$2" "${3:-540}"; r=$?
           [ $r = 0 ] && echo "turno: $2" || echo "en cola: $2 (lock puesto; llamar otra vez o soltar)"; exit $r ;;
    soltar) [ -n "${2:-}" ] || { echo "uso: turno.sh soltar <nombre>" >&2; exit 2; }
            turno_agente_soltar "$2"; echo "soltado: $2" ;;
    *) echo "uso: turno.sh tomar <nombre> [segundos] | soltar <nombre>" >&2; exit 2 ;;
  esac
fi
