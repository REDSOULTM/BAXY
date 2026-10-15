#!/usr/bin/env bash
# Molestia de los primitivos arrendados (punto 0, ronda 1 pendiente) con el medidor activo, sin lanzar BAXY:
# corre la prueba opt-in MolestiaPrimitivesLiveCheck (clic tras abrir detrás, flujo de teclas en ráfaga, ráfaga de
# ayudante) sobre ventanas propias mientras medidor.py escribe en la suya. Espera a que no haya ningún *.lock en
# cu-v3, pone el suyo (< 2 min) y lo borra siempre. Requiere el proyecto de pruebas compilado en Release.
#   bash scripts/cu_live/molestia/primitivos_live.sh [salida]
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
LOCKS="${LOCALAPPDATA:-C:/Users/usuario/AppData/Local}/BAXY/cu-v3"
MINE="$LOCKS/agent-primitivos.lock"
D="${1:-${TMP:-/tmp}/baxy-molestia-primitivos}"

while ls "$LOCKS"/*.lock >/dev/null 2>&1; do sleep 20; done
echo "primitivos $(date +%H:%M:%S)" > "$MINE"
trap 'rm -f "$MINE"' EXIT
rm -rf "$D"; mkdir -p "$D/ctl"
cd "$ROOT" || exit 1
BAXY_MOLESTIA_LIVE=1 BAXY_MOLESTIA_PERSON_FOREGROUND=1 BAXY_MOLESTIA_READY="$D/ready" BAXY_MOLESTIA_GO="$D/go" \
  dotnet test tests/Baxy.Providers.Windows.Tests -c Release --nologo --no-build \
  --filter "FullyQualifiedName~MolestiaPrimitivesLiveCheck" --logger "console;verbosity=detailed" > "$D/test.log" 2>&1 &
TEST=$!
for _ in $(seq 1 600); do [ -e "$D/ready" ] && break; sleep 0.1; done
py -3.12 scripts/cu_live/molestia/medidor.py medir --control "$D/ctl" --salida "$D/molestia.json" --inicio ahora --pausa 2 \
  > "$D/medidor.log" 2>&1 &
METER=$!
for _ in $(seq 1 600); do [ -e "$D/ctl/midiendo.json" ] && break; sleep 0.1; done
sleep 1
touch "$D/go"
wait $TEST
echo "prueba: salida $?"
touch "$D/ctl/parar"
for _ in $(seq 1 300); do kill -0 $METER 2>/dev/null || break; sleep 0.1; done
kill $METER 2>/dev/null
grep -E "click:|flow:|helper:|Passed|Failed|Error Message" "$D/test.log" | head -20
grep -o '"resumen": "[^"]*"' "$D/molestia.json" 2>/dev/null
