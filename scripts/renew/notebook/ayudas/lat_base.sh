#!/usr/bin/env bash
# Heartbeat study (PC 01:55): the BASE model (Qwen3.5-4B Q4_K_M, sha 00fe7986…) on the practice scenes x4 with the very
# mind copies and catalog of nb-pc1-none (2a5a0aad5, BAXY_AYUDAS=none), to compare scene by scene with c2-e1.0.
set -u
H=2a5a0aad5; L="C:/Users/usuario/Desktop/ETC/Programacion/BAXY-Renew-p1c"; S="C:/Users/usuario/AppData/Local/Temp/claude/nb/ay/logs"
CAT='D:/BAXYeval/ayudas_nb/catalog.B-a3af5c20f.json'; G='D:\BAXYeval\models\Qwen3.5-4B-Q4_K_M.gguf'; SV='D:\BAXYeval\llama\llama-server.exe'
while tasklist //FI "IMAGENAME eq Baxy.exe" | grep -qi baxy || tasklist //FI "IMAGENAME eq llama-server.exe" | grep -qi llama-server; do sleep 10; done
cd "$L" || exit 1
[ "$(git rev-parse --short=9 HEAD)" = "$H" ] || { echo "wrong HEAD $(git rev-parse --short=9 HEAD)"; exit 1; }
export BAXY_RENEW_BANKS='D:\BAXYeval\renew_v1' BAXY_AYUDAS=none; unset BAXY_MIND_PYTHONPATH BAXY_MIND_LLM_GGUF
for v in "" -pA -pB -pC; do
  lab="nb-lat-base$v-esc"
  py -3.12 -X utf8 scripts/renew/bench_escenas.py "$lab" --scenes 'D:\BAXYeval\renew_v1\escenas\practice.json' \
    --src "D:/BAXYeval/renew_v1/ab/bis/$H$v" --catalog "$CAT" --gguf "$G" --server "$SV" > "$S/$lab.log" 2>&1
  echo "$lab $(date +%H:%M): $(tail -1 "$S/$lab.log" | grep -oE '"ok": [0-9]+|"annoying": [0-9]+|"risky_alone": [0-9]+|"failures": [0-9]+' | tr '\n' ' ')"
done
echo LAT-BASE-DONE
