#!/usr/bin/env bash
# PC 02:12: aid beat_no_pending (d16e13bf2, in the heartbeat message) on the practice scenes x4, same mind copies and
# catalog for every arm: none / beat_no_pending / the lot / the lot + beat_no_pending, interleaved per variant.
set -u
H=d16e13bf2; L="C:/Users/usuario/Desktop/ETC/Programacion/BAXY-Renew-lote"; S="C:/Users/usuario/AppData/Local/Temp/claude/nb/ay/logs"
CAT='D:/BAXYeval/ayudas_nb/catalog.B-a3af5c20f.json'; G='D:\BAXYeval\models\BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf'; SV='D:\BAXYeval\llama\llama-server.exe'
LOT=calculator_next,accessible_scope,work_folder,place_unverified,person_folder_sentence
while tasklist //FI "IMAGENAME eq Baxy.exe" | grep -qi baxy || tasklist //FI "IMAGENAME eq llama-server.exe" | grep -qi llama-server; do sleep 10; done
cd "$L" || exit 1
export BAXY_RENEW_BANKS='D:\BAXYeval\renew_v1'; unset BAXY_MIND_PYTHONPATH BAXY_MIND_LLM_GGUF
declare -A ARM=([none]=none [bnp]=beat_no_pending [lot]=$LOT [lotbnp]=$LOT,beat_no_pending)
for v in "" -pA -pB -pC; do
  for arm in none bnp lot lotbnp; do
    export BAXY_AYUDAS="${ARM[$arm]}"; lab="nb-beat-$arm$v-esc"
    py -3.12 -X utf8 scripts/renew/bench_escenas.py "$lab" --scenes 'D:\BAXYeval\renew_v1\escenas\practice.json' \
      --src "D:/BAXYeval/renew_v1/ab/bis/$H$v" --catalog "$CAT" --gguf "$G" --server "$SV" > "$S/$lab.log" 2>&1
    echo "$lab $(date +%H:%M): $(tail -1 "$S/$lab.log" | grep -oE '"ok": [0-9]+|"annoying": [0-9]+|"risky_alone": [0-9]+|"failures": [0-9]+' | tr '\n' ' ')"
  done
done
unset BAXY_AYUDAS
echo ESC-BEAT-DONE
