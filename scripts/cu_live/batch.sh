#!/usr/bin/env bash
# usage: batch.sh <case-id>... (cases/<id>.turns). Prints final, latency, trace, screenshot; closes only what the case opened
# (libro_lote.ps1: by process born after the case photo, exact PID, read back).
# Unseen-app batch: run each case, print final/latency/trace, screenshot, then close only windows/processes the case started.
# Before each case the test apps go back to their base state (estado/base.ps1 -Caso <id>, map in estado/casos.json;
# a case not in the map is not touched). An id like s12@tienda runs cases/s12.turns from the states listed for
# "s12@tienda". CU_SIN_ESTADO=1 skips the base states.
L=$(cd "$(dirname "$0")" && pwd); V="$L"
P="$L/cases"
LAD=$(cygpath -u "$LOCALAPPDATA"); CONV="$LAD/BAXY/cu-universal-perfil/conversation/conversation.v1.jsonl"; EVB="$LAD/BAXY/cu-universal-evidencia"
# BAXY's mission journal of the bench profile: libro_lote.ps1 closes a new window of the person's process only where
# BAXY worked during the case.
export CU_JOURNAL="${CU_JOURNAL:-$(cygpath -w "$LAD/BAXY/cu-universal-perfil/journal/missions.jsonl")}"
# Harness helpers run through ps (servidor_ps.sh): one persistent PowerShell for the whole batch.sh once
# servidor_ps_iniciar ran, a new powershell per call before that (CU_SERVIDOR_PS=0: always).
. "$L/servidor_ps.sh"
# A case that does not run leaves no_corrio.json in its evidence folder, and an earlier run's files moved aside.
. "$L/evidencia_no_corrio.sh"
# Time of each harness step of a case, printed as one «tiempos:» line at its end (EPOCHREALTIME: no process).
T_PASOS=""; T_INI=${EPOCHREALTIME/[.,]/}; T_ULT=$T_INI
t_seg(){ printf '%d.%d' $(( $1/1000000 )) $(( $1%1000000/100000 )); }
t_paso(){ local t=${EPOCHREALTIME/[.,]/}; T_PASOS+=" $1=$(t_seg $((t-T_ULT)))"; T_ULT=$t; }
t_informe(){
  local t=${EPOCHREALTIME/[.,]/} w
  w=$(grep -ao 'conductor exit=[0-9]* wall=[0-9]*s' "$L/logs/$tag.log" 2>/dev/null | tail -1 | sed 's/.*wall=\([0-9]*\)s/\1/')
  # The parts of cu_live.sh (gates, meter and volume, conductor, close) when the case ran it.
  case $T_PASOS in *" cu_live="*) c=$(grep -ao '^tiempos_cu_live: .*' "$L/logs/$tag.log" 2>/dev/null | tail -1 | cut -d' ' -f2- | tr -d '\r') ;; *) c= ;; esac
  echo "tiempos: caso=$(t_seg $((t-T_INI)))s conductor=${w:-0}s arnes=$(t_seg $((t-T_INI-${w:-0}*1000000)))s |$T_PASOS${c:+ | cu_live: $c}"
  T_PASOS=""; T_INI=$t; T_ULT=$t
}
# Frame windows of packaged apps (Settings, Calculator...) by exact HWND (marcos.ps1; ApplicationFrameHost's
# MainWindowTitle names only one of them). A frame a case could not close is retried before the next case's states.
frames(){ ps "$L/marcos.ps1" -Listar | tr -d '\r'; }
MARCOS_PEND="$(cygpath -w "$L/logs/marcos-pendientes.txt")"
mkdir -p "$L/logs"
# Batch ledger (libro_lote.ps1): lote.sh exports CU_LIBRO with the photo of the batch start; run alone, batch.sh takes
# its own. Whatever is born after it is the batch's (unless the person's input started it) and is closed by exact PID.
PROPIO_LIBRO=0
. "$L/registro.sh"
# The owner-input record (registro_dueno.py): lote.sh starts one for the whole batch; run alone, batch.sh starts its own
# before its photo. Without it the ledger treats the person as active and closes nothing that could be theirs.
if [ -z "${CU_REGISTRO:-}" ]; then
  trap 'registro_parar' EXIT
  registro_iniciar "$L/logs/registro-$(date +%Y%m%d-%H%M%S).json"
fi
if [ -z "${CU_LIBRO:-}" ]; then
  export CU_LIBRO="$(cygpath -w "$L/logs/libro-$(date +%Y%m%d-%H%M%S).json")"; PROPIO_LIBRO=1
  ps "$L/libro_lote.ps1" -Foto -Libro "$CU_LIBRO" | tr -d '\r'
fi
# Base-state failures that survived a repair in this batch (reparar.py; lote.sh runs one batch.sh a case, same ledger).
REPARAR_REG="${CU_LIBRO%.json}.permanentes.json"
servidor_ps_iniciar
# An owner preference an earlier run could not give back (its -Devolver failed: OBS was open) is retried first.
if [ "${CU_SIN_ESTADO:-0}" != 1 ]; then
  PEND=$(ps "$L/estado/base.ps1" -DevolverPendientes | tr -d '\r')
  [ -n "$PEND" ] && echo "$PEND"
  echo "$PEND" | grep -q '"verificado":false' && echo "AVISO: una preferencia del dueno sigue sin devolver (preferencias/pendientes.jsonl)"
fi
t_paso inicio
# The verifier reads UIA and the Shell of every window of the case's app: a program that stopped answering held it 11 min
# (t-menu-1, 2026-10-09). It gets its own ceiling (CU_TOPE_VERIFY, 60 s; every other helper has CU_PS_TOPE, 300 s,
# servidor_ps.sh); when it runs out the batch says which windows hang, the verification file is written as incomplete
# (never as a success: colgadas.ps1 -Incompleta) and the case goes on.
TOPE_VERIFY=${CU_TOPE_VERIFY:-60}
verificar_fase(){
  # $1 antes|despues; prints the verifier's output (its file path) unless it is the before phase.
  local f=$1 out col res
  out=$(PS_TOPE=$TOPE_VERIFY ps "$L/verificar.ps1" -Caso "$id" -Fase "$f" -Antes "$APPS" | tr -d '\r')
  if printf '%s\n' "$out" | grep -q '"resultado":"sin_respuesta"'; then
    col=$(PS_TOPE=30 ps "$L/colgadas.ps1" -Antes "$APPS" -Incompleta "$(cygpath -w "$EVB/$tag/verificacion-$f.json")" -Caso "$id" -Fase "$f" -Tope "$TOPE_VERIFY" | tr -d '\r' | grep '^{"estado":"colgadas"' | tail -1)
    res=$(printf '%s' "$col" | sed -n 's/.*"resumen":"\(.*\)"}$/\1/p')
    echo "AVISO: verify sin respuesta (${res:-no se pudo leer que ventana cuelga}): verificacion-$f.json queda incompleta y el caso sigue"
    return 1
  fi
  [ "$f" = antes ] || printf '%s\n' "$out"
  return 0
}
# Case preparation (before the first run, and again before a run repeated after its turns already acted): a frame an
# earlier case left, the base states, and the evidence taken before the case (APPS, verificar antes, EXPL, FRAMES).
# Returns 1 when the case must not run (casos.json "requiere" without what it needs), 2 when its base state could not
# be verified even after one repair (NOVERIF names what failed). Sets ESTADO.
preparar_caso(){
  ESTADO=""; NOVERIF=""
  if [ "${CU_SIN_ESTADO:-0}" != 1 ]; then
    PEND=$(ps "$L/marcos.ps1" -Reintentar -Pendientes "$MARCOS_PEND" | tr -d '\r')
    echo "$PEND" | grep -qE '"cerradas":\[[0-9]|"verificado":false' && echo "$PEND"
    t_paso marcos_pendientes
    for rep in 1 2; do
      echo "--- estado base"
      # Leftovers of an earlier case, batch or tanda (round 7: a Reloj in front, a OneNote in its File view, a Word
      # with its save prompt): what the persistent harness book proves the harness's is closed first (sin_restos).
      RESTOS=$(ps "$L/estado/base.ps1" -Estados sin_restos | tr -d '\r')
      echo "$RESTOS" | tee -a "$L/logs/$tag.estado.jsonl"
      t_paso sin_restos
      ESTADO=$(ps "$L/estado/base.ps1" -Caso "$id" | tr -d '\r')
      t_paso estado_base
      echo "$ESTADO" | tee -a "$L/logs/$tag.estado.jsonl"
      # What an earlier case left over this one: an always-on-top window or a dialog is named as the case's obstacle
      # (encima, dialogos); a dialog over a batch or harness window is cancelled, and an elevated window the batch or
      # the harness is proven to have started is closed by its PID (elevadas); anybody else's is never touched.
      OBST=$(ps "$L/estado/base.ps1" -Estados sin_obstaculos | tr -d '\r')
      echo "$OBST" | tee -a "$L/logs/$tag.estado.jsonl"
      echo "$OBST" | grep -q '"verificado":false' && echo "AVISO: obstaculo: una ventana siempre encima o un dialogo tapa la pantalla antes de $id (ver encima/dialogos)"
      # A case that needs what an earlier case leaves (casos.json "requiere") and does not have it is not run: it
      # does not count against BAXY.
      echo "$ESTADO" | grep -q 'no_corrio:estado_ausente' && return 1
      NOVERIF=$(printf '%s\n%s\n%s\n' "$RESTOS" "$ESTADO" "$OBST" | grep '"verificado":false' | sed -n 's/.*"estado":"\([^"]*\)".*/\1/p' | sort -u | tr '\n' ' ')
      NOVERIF=${NOVERIF% }
      [ -z "$NOVERIF" ] && break
      echo "AVISO: estado base sin verificar para $id: $NOVERIF"
      PASADA=$(printf '%s\n%s\n%s\n' "$RESTOS" "$ESTADO" "$OBST")
      # A failure the repair left exactly as it was goes to the batch's registry (reparar.py anotar).
      if [ "$rep" = 2 ]; then
        printf '%s\n@@reparado@@\n%s\n' "$PASADA1" "$PASADA" | py -3.12 "$L/reparar.py" anotar --registro "$REPARAR_REG" > /dev/null 2>&1
        break
      fi
      # Only an obstacle the harness cannot close (elevated, always on top): repeating the states changes nothing.
      [ "$NOVERIF" = sin_obstaculos ] && break
      # Pasada r9 + r11: the repair fixed 0 of 129 failing states. It is not repeated when every failure is permanent
      # (reparar.py: the person's window, a refused leftover, a state that threw, or one that already survived a repair
      # in this batch); the state still does not verify and the case is handled as before. Unknown answer: repaired.
      PERM=$(printf '%s\n' "$PASADA" | py -3.12 "$L/reparar.py" decidir --registro "$REPARAR_REG" 2>/dev/null | tr -d '\r')
      case $PERM in permanente*) echo "--- no se repara: causa permanente (${PERM#permanente })"; break ;; esac
      PASADA1=$PASADA
      echo "--- se repara una vez (restos, estados y obstaculos otra vez)"
    done
    echo "$ESTADO" | grep -q '"productor_sin_verificar":true' && echo "PRODUCTOR_SIN_VERIFICAR: $id depende de un caso sin veredicto (si ese fallo, $id no cuenta contra BAXY)"
    echo "$ESTADO" | grep -q '"variante":"ya_estaba"' && echo "VARIANTE: $id se juzga como «ya estaba» (la preferencia del dueno ya cumple la orden)"
  fi
  # Independent evidence for the reviewer (verificar.ps1): app windows (UIA) and test files, before and after the case.
  APPS=$(ps "$L/estado/apps_del_caso.ps1" -Listar | tr -d '\r')
  verificar_fase antes
  t_paso verificar_antes
  EXPL=$(ps "$L/estado/exploradores.ps1" -Listar | tr -d '\r')
  FRAMES=$(frames)
  t_paso exploradores_marcos
  # A case that does not start from its base state is not run (CU_ESTADO_ESTRICTO=0: it runs, with the AVISO): its
  # result would be judged on what an earlier run left, not on BAXY.
  [ -n "$NOVERIF" ] && [ "${CU_ESTADO_ESTRICTO:-1}" != 0 ] && return 2
  # CU_ESTADO_ESTRICTO=0 runs it anyway (pasada r18, v3-44: app_cerrada ajena_abierta, then judged a product failure):
  # its line says so, and so do its marker (.hecho) and its evidence folder, so no judge counts it against BAXY.
  [ -n "$NOVERIF" ] && echo "ESTADO_BASE_SUCIO: $id corre con el estado base sin verificar: $NOVERIF (un fallo no cuenta contra BAXY)"
  return 0
}
# What a case opened is closed after it, and after a run that is going to be repeated. Sets LIMPIO=0 when something
# stayed: a process or a frame of the case still open, a new frame left alone because the person used the PC, an
# owner preference not given back.
limpiar_caso(){
  LIMPIO=1
  # Everything born since the case photo (states, mission: PowerPoint, OneNote, Edge, Paint, Spotify, Notepad...) is
  # closed by exact PID and read back when its provenance is the batch's; new windows in the person's processes only by
  # window and only if the owner-input record (CU_REGISTRO) covers the case with no input; new tabs in the person's
  # browser are reported, never closed (libro_lote.ps1).
  echo "--- libro"
  CIERRE=$(ps "$L/libro_lote.ps1" -Cerrar -Libro "$FOTO" | tr -d '\r')
  echo "$CIERRE" | tee -a "$L/logs/$tag.estado.jsonl"
  echo "$CIERRE" | grep -q '"verificado":false' && { LIMPIO=0; echo "AVISO: el caso $id dejo algo abierto (ver sobreviven)"; }
  echo "$CIERRE" | grep -q 'navegador_del_dueno' && echo "AVISO: el navegador del dueno cambio durante $id (no se toca)"
  t_paso libro_cerrar
  # A frame window (Settings, Store...) the case left open is closed by its exact HWND (marcos.ps1), under the
  # ledger's rule for a new window in a process of the person: only when the record covers the case with no input.
  MARCOS=$(ps "$L/marcos.ps1" -CerrarNuevos -Antes "$FRAMES" -Libro "$FOTO" -Pendientes "$MARCOS_PEND" | tr -d '\r')
  echo "$MARCOS" | tee -a "$L/logs/$tag.estado.jsonl"
  echo "$MARCOS" | grep -q '"verificado":false' && { LIMPIO=0; echo "AVISO: el caso $id dejo una ventana de app empaquetada abierta (se reintenta antes del proximo caso)"; }
  echo "$MARCOS" | grep -q '"sin_tocar":\[[0-9]' && { LIMPIO=0; echo "AVISO: una ventana de app empaquetada nueva queda abierta: el dueno uso el equipo durante $id (no se toca)"; }
  t_paso marcos_cerrar
  # Explorer windows the case opened on a test place are closed by exact HWND, only when the owner-input record covers
  # the case with no input (the person's are never touched).
  EXPLC=$(ps "$L/estado/exploradores.ps1" -CerrarNuevos -Antes "$EXPL" -Libro "$FOTO" | tr -d '\r')
  echo "$EXPLC" | tee -a "$L/logs/$tag.estado.jsonl"
  echo "$EXPLC" | grep -q '"sin_tocar":\[[0-9]' && { LIMPIO=0; echo "AVISO: una ventana nueva del Explorador queda abierta: el dueno uso el equipo durante $id (no se toca)"; }
  echo "$EXPLC" | grep -q '"sobreviven":\[[0-9]' && { LIMPIO=0; echo "AVISO: una ventana del Explorador que abrio BAXY en $id no se cerro (se reintenta antes del proximo caso)"; }
  # Windows of the case's own app(s) (v3 manifest) whose process the case started and the ledger proves the batch's.
  APPSC=$(ps "$L/estado/apps_del_caso.ps1" -Caso "$id" -Antes "$APPS" | tr -d '\r')
  echo "$APPSC" | tee -a "$L/logs/$tag.estado.jsonl"
  echo "$APPSC" | grep -q '"sin_tocar":\["' && { LIMPIO=0; echo "AVISO: una ventana de la app de $id no es probadamente del lote ni de BAXY (puede ser del dueno: no se toca)"; }
  t_paso exploradores_apps_cerrar
  # An owner preference the case inverted (casos.json "precondicion") is given back now that its app is closed.
  if [ "${CU_SIN_ESTADO:-0}" != 1 ]; then
    DEV=$(ps "$L/estado/base.ps1" -Caso "$id" -Devolver | tr -d '\r')
    [ -n "$DEV" ] && echo "$DEV" | tee -a "$L/logs/$tag.estado.jsonl"
    echo "$DEV" | grep -q '"verificado":false' && { LIMPIO=0; echo "AVISO: la preferencia del dueno de $id no se devolvio (se reintenta al empezar el proximo lote)"; }
  fi
  t_paso devolver
  return 0
}
for id in "$@"; do
  echo "=================== $id"
  tid=${id%%@*}; tag="v2-${id//@/-}"
  # Photo of the case start, before the base states: what the states and the mission open is closed after the case.
  EVIDENCIA_ANTERIOR_DE_ESTA_CORRIDA=
  FOTO="$(cygpath -w "$L/logs/$tag.foto.json")"; rm -f "$L/logs/$tag.foto.json" "$L/logs/$tag.hecho" "$L/logs/$tag.estado.jsonl"
  ps "$L/libro_lote.ps1" -Foto -Libro "$FOTO" > /dev/null
  t_paso foto
  preparar_caso; RC=$?
  if [ "$RC" = 1 ]; then evidencia_no_corrio "$EVB/$tag" "$id" "estado ausente" 1; echo "NO_CORRIO: $id estado ausente (no cuenta contra BAXY)"; t_informe; continue; fi
  if [ "$RC" = 2 ]; then
    # What the states opened for it is closed like after a case (no .hecho: nothing ran).
    echo "NO_CORRIO: $id estado base sin verificar tras repararlo: $NOVERIF (no cuenta contra BAXY)"
    evidencia_no_corrio "$EVB/$tag" "$id" "estado base sin verificar: $NOVERIF" 1
    limpiar_caso; t_informe; continue
  fi
  evidencia_corre "$EVB/$tag"
  # Otro BAXY con el mutex de la App (exit 2) o vivo al empezar (exit 3): ningun turno corrio; se espera y se repite.
  # El decisor no disponible con el turno sin final, o el Core sin arrancar (repetir.py, no cuenta contra BAXY): los
  # turnos anteriores ya pudieron actuar (s13: el turno 1 ya fue al canal), asi que antes de repetir se cierra lo que
  # abrio el intento (limpiar_caso) y se vuelve al estado base (preparar_caso). Si no queda limpio el caso NO_CORRIO:
  # repetirlo sobre un estado sucio daria un exito falso («ya estaba»). Hasta 3 intentos; la evidencia del intento
  # repetido queda como events.repetido-<n>.jsonl.
  # Ronda 23 (t-drag-1, r21): los 3 intentos abortados por la infraestructura (o el decisor ausente en el tercero) son
  # NO_CORRIO, nunca un caso juzgado; si ningun intento llego a correr un turno (CORRIO=0) lo que quede de antes se
  # archiva en anterior/.
  NOCORRIO=""; MOTIVO=""; CORRIO=0
  for intento in 1 2 3; do
    bash "$L/cu_live.sh" "$tag" "$P/$tid.turns" > "$L/logs/$tag.log" 2>&1
    t_paso cu_live
    if grep -aqE 'ABORT: BAXY already running|ABORT: GPU busy|conductor exit=2 ' "$L/logs/$tag.log"; then
      MOTIVO="otro BAXY abierto o la GPU ocupada"
      [ "$intento" = 3 ] && { NOCORRIO="infraestructura: $MOTIVO en los 3 intentos"; break; }
      echo "otro BAXY abierto: se repite $id (intento $intento)"; sleep 20; continue
    fi
    CORRIO=1
    MOTIVO=$(py -3.12 "$L/repetir.py" "$EVB/$tag/events.jsonl") || break
    MOTIVO=${MOTIVO%$'\r'}
    [ "$intento" = 3 ] && { echo "AVISO: $id sigue sin decisor tras 3 intentos ($MOTIVO): no cuenta contra BAXY"; NOCORRIO="infraestructura: sin decisor en los 3 intentos"; break; }
    cp -f "$EVB/$tag/events.jsonl" "$EVB/$tag/events.repetido-$intento.jsonl" 2>/dev/null
    echo "infraestructura ($MOTIVO): se repite $id (intento $intento) desde el estado base"
    limpiar_caso
    if [ "$LIMPIO" != 1 ]; then NOCORRIO="no volvio al estado base para repetirlo"; break; fi
    sleep 20
    preparar_caso; RC=$?
    if [ "$RC" = 1 ]; then NOCORRIO="estado ausente al repetirlo"; break; fi
    if [ "$RC" = 2 ] || [ -n "$NOVERIF" ]; then NOCORRIO="estado base sin verificar al repetirlo ($NOVERIF)"; break; fi
  done
  if [ -n "$NOCORRIO" ]; then
    # No marker (.hecho): a case that needs this one does not run on a result nobody can judge.
    echo "NO_CORRIO: $id $NOCORRIO ($MOTIVO; no cuenta contra BAXY)"
    # An attempt that ran a turn is kept, marked as not to be judged; with none run, the rest goes to anterior/.
    evidencia_no_corrio "$EVB/$tag" "$id" "$NOCORRIO ($MOTIVO)" "$(( CORRIO ? 0 : 1 ))"
  else
  # Marker for the cases that need what this one leaves (casos.json "requiere", base.ps1): written only now, after
  # its mission ran, with the conductor's exit code. A judge may add "veredicto":"exito"|"fallo" to it later; without
  # it the dependent case runs flagged productor_sin_verificar.
  CEX=$(grep -ao 'conductor exit=[0-9]*' "$L/logs/$tag.log" | tail -1 | cut -d= -f2)
  SUCIO=""; [ -n "$NOVERIF" ] && SUCIO=",\"estado_base_sucio\":\"$(printf '%s' "$NOVERIF" | tr -d '"\\\r\n')\""
  printf '{"caso":"%s","conductor_exit":%s,"veredicto":null%s}\n' "$id" "${CEX:-null}" "$SUCIO" > "$L/logs/$tag.hecho"
  [ -n "$NOVERIF" ] && evidencia_estado_sucio "$EVB/$tag" "$id" "$NOVERIF"
  PYTHONIOENCODING=utf-8 py -3.12 "$L/ev.py" "$EVB/$tag/events.jsonl" 2>/dev/null | grep -a '"terminal"' | sed 's/.*"final": //' | cut -c1-300
  grep -o '"latency_ms":[0-9]*' "$CONV" | tail -n "$(wc -l < "$P/$tid.turns")" | tr '\n' ' '; echo
  py -3.12 "$L/molestia/molestia_sum.py" --linea "$(cygpath -w "$EVB/$tag/molestia.json")"
  grep -h "computer_use.end\|computer_use.stop\|computer.use.step\"\|computer_use.subgoal" "$EVB/$tag/trace.jsonl" 2>/dev/null | sed 's/.*"stage"://' | cut -c1-120
  t_paso informe
  echo "--- verify"
  verificar_fase despues
  t_paso verificar_despues
  ps "$L/screen.ps1" -Out "$(cygpath -w "$EVB/$tag/after.png")"
  case $tid in
    c3) D="/d/Perfil/Documentos/baxy-prueba"; if [ -d "$D" ]; then echo "FOLDER CREATED: $D"; rmdir "$D" && echo "removed empty test folder"; else echo "no folder at $D"; ls -d /d/Perfil/Documentos/*baxy* 2>&1 | head -3; fi;;
    s02) ps "$V/state.ps1" -Title Reloj | grep -i "SELECTED" | head -3;;
    s03) ps "$V/state.ps1" -Title Configuraci | grep -i "SELECTED" | head -3;;
    # Nothing is closed here by a title (review r10a: «Descargas» also named the person's Downloads folder or a
    # browser's downloads page): limpiar_caso closes what the case opened by exact window or PID (exploradores.ps1,
    # marcos.ps1, libro_lote.ps1).
    s04) powershell -NoProfile -Command "(New-Object -ComObject Shell.Application).Windows() | ForEach-Object { \$_.LocationName }";;
    s05) powershell -NoProfile -Command "Get-Process explorer | Where-Object MainWindowTitle | Select -Expand MainWindowTitle";;
    s01) ps "$L/calc_read.ps1" | head -1;;
    c1|c2) ps "$V/state.ps1" -Title "Bloc de notas" | grep -i "WINDOW\|VALUE" | head -3;;
  esac
  fi
  t_paso captura_extra
  limpiar_caso
  t_informe
done
# The harness's own Explorer window (estado/explorador_*) is closed at the end of the batch.
[ "${CU_SIN_ESTADO:-0}" != 1 ] && ps "$L/estado/exploradores.ps1" -Limpiar
# ... and every app window the harness opened for a state (app_abierta, documento_en_blanco...).
[ "${CU_SIN_ESTADO:-0}" != 1 ] && ps "$L/estado/base.ps1" -Estados 'app_cerrada:*'
# Run alone, the batch sweeps its own ledger last (lote.sh does it once for the whole batch).
[ "$PROPIO_LIBRO" = 1 ] && ps "$L/libro_lote.ps1" -Cerrar -Libro "$CU_LIBRO" | tr -d '\r'
true
