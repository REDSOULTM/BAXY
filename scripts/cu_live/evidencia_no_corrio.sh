#!/usr/bin/env bash
# Evidence of a case that did not run (batch.sh). Pasada r9: v3-49 ended NO_CORRIO, but its evidence folder still held
# the run of 2026-10-07 (after.png, trace.jsonl...), and the judge took that old run for this one.
#   evidencia_no_corrio <dir> <caso> <motivo> <archivar 1|0>
#     writes <dir>/no_corrio.json; with archivar=1 (nothing of this batch ran) everything an earlier run left (files
#     and subfolders such as molestia-control) goes to <dir>/anterior/ first, so nothing in <dir> can pass for this
#     batch's run. Only the last one is kept: an older anterior/ is replaced, so they never pile up.
#     A <dir>/anterior/ that evidencia_corre made for this same run is kept and added to, never replaced.
#   evidencia_corre <dir>
#     the case is about to run: an earlier no_corrio.json or estado_base_sucio.json goes away, and the files the App
#     and the mind append to (trace, events, turn_audit, compose_audit, model_calls, raw_replies, invalid_json, the
#     repeated attempts' events) go to <dir>/anterior/, so what is left in <dir> is only this run's (ronda 23,
#     t-drag-1: three aborted attempts and the case judged on the trace of an earlier day). So do the mission's
#     journal entries and photo (journal-caso.json, after-mision.png/.json, cu_live.sh): verificar.ps1 reads them as
#     this run's.
#   evidencia_estado_sucio <dir> <caso> <estados>
#     the case runs with its base state unverified (CU_ESTADO_ESTRICTO=0): <dir>/estado_base_sucio.json names those
#     states, so a judge does not count its failure against BAXY (pasada r18, v3-44).
evidencia_no_corrio(){
  local d=$1 caso=$2 motivo=$3 archivar=${4:-1} a f limpio=
  mkdir -p "$d"
  if [ "$archivar" = 1 ]; then
    a="$d/anterior"
    [ "$a" = "${EVIDENCIA_ANTERIOR_DE_ESTA_CORRIDA:-}" ] && [ -d "$a" ] && limpio=1
    for f in "$d"/*; do
      [ -e "$f" ] || continue
      case "$(basename "$f")" in no_corrio.json|anterior|anterior-*) continue ;; esac
      [ -n "${limpio:-}" ] || { rm -rf "$a"; mkdir -p "$a"; limpio=1; }
      mv -f "$f" "$a/"
    done
  fi
  motivo=$(printf '%s' "$motivo" | tr -d '"\\\r\n')
  printf '{"caso":"%s","no_corrio":true,"motivo":"%s","hora":"%s","evidencia_anterior":"%s"}\n' \
    "$caso" "$motivo" "$(date +%Y-%m-%dT%H:%M:%S)" "$( [ -n "$limpio" ] && basename "$a")" > "$d/no_corrio.json"
}
evidencia_corre(){
  local d=$1 f
  rm -f "$d/no_corrio.json" "$d/estado_base_sucio.json"
  EVIDENCIA_ANTERIOR_DE_ESTA_CORRIDA=
  for f in "$d"/trace.jsonl "$d"/events.jsonl "$d"/turn_audit.jsonl "$d"/compose_audit.jsonl "$d"/model_calls.jsonl \
           "$d"/raw_replies.jsonl "$d"/invalid_json "$d"/events.repetido-*.jsonl \
           "$d"/journal-caso.json "$d"/after-mision.png "$d"/after-mision.json; do
    [ -e "$f" ] || continue
    [ -n "$EVIDENCIA_ANTERIOR_DE_ESTA_CORRIDA" ] || { rm -rf "$d/anterior"; mkdir -p "$d/anterior"; EVIDENCIA_ANTERIOR_DE_ESTA_CORRIDA="$d/anterior"; }
    mv -f "$f" "$d/anterior/"
  done
}
evidencia_estado_sucio(){
  local d=$1 caso=$2 estados
  mkdir -p "$d"
  estados=$(printf '%s' "$3" | tr -d '"\\\r\n')
  printf '{"caso":"%s","estado_base_sucio":true,"estados":"%s","hora":"%s"}\n' "$caso" "$estados" "$(date +%Y-%m-%dT%H:%M:%S)" > "$d/estado_base_sucio.json"
}
