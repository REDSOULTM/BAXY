#!/usr/bin/env bash
# Lever 7 (modes_sentence, prefix) on the notebook GPU (PC 15:25): its base of the day and the lever, same mind copy
# (hub/pc-ayudas-6 d2571e455), same catalog, only BAXY_AYUDAS changes (none vs modes_sentence). Prefix tokens, decision2 s0-2,
# scenes unchanged + 3 perturbations, modes probe s0 (rows to the PC, which judges). Interleaved base/lever per bench.
set -u
H=d2571e455; L="C:/Users/usuario/Desktop/ETC/Programacion/BAXY-Renew-p7"; AY="C:/Users/usuario/AppData/Local/Temp/claude/nb/ay"
S="$AY/logs"; CAT="${CAT:?CAT}"; G='D:\BAXYeval\models\BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf'; SV='D:\BAXYeval\llama\llama-server.exe'
idle() { while tasklist //FI "IMAGENAME eq Baxy.exe" | grep -qi baxy || tasklist //FI "IMAGENAME eq llama-server.exe" | grep -qi llama-server; do sleep 10; done; }
cd "$L" || exit 1
[ "$(git rev-parse --short=9 HEAD)" = "$H" ] || { echo "wrong HEAD"; exit 1; }
for seed in 0 1 2; do
  d="D:/BAXYeval/renew_v1/ab/arr/$H-s$seed"; rm -rf "$d"; mkdir -p "$d"
  git archive "$H" src/baxy_mind | tar -x -C "$d" --strip-components=1
  sed -i "s/\"seed\": 0}/\"seed\": $seed}/" "$d/baxy_mind/mind.py"
done
d="D:/BAXYeval/renew_v1/ab/bis/$H"; rm -rf "$d"; mkdir -p "$d"; git archive "$H" src/baxy_mind | tar -x -C "$d" --strip-components=1
py -3.12 -X utf8 -I C:/Users/usuario/AppData/Local/Temp/claude/nb/reales/pert2.py "$H" | wc -l | sed 's/^/perturbations: /'
export BAXY_RENEW_BANKS='D:\BAXYeval\renew_v1'; unset BAXY_MIND_PYTHONPATH BAXY_MIND_LLM_GGUF
GA=(--gguf "$G" --server "$SV")
idle
echo "prefix $(date +%H:%M): $(py -3.12 -X utf8 "$AY/prefijo.py" "D:/BAXYeval/renew_v1/ab/arr/$H-s0" "$CAT" "$G" "$SV" none modes_sentence 2>&1 | grep prefix | tr '\n' ' ')"
for seed in ${DEC_SEEDS:-0 1 2}; do
  for arm in none modes_sentence; do
    idle; export BAXY_AYUDAS=$arm; lab="nb-p7-$arm-s$seed-dec"
    py -3.12 -X utf8 scripts/renew/bench_decision.py "$lab" --cases 'D:\BAXYeval\renew_v1\practica\decision2.json' \
      --src "D:/BAXYeval/renew_v1/ab/arr/$H-s$seed" --catalog "$CAT" "${GA[@]}" > "$S/$lab.log" 2>&1
    echo "$lab $(date +%H:%M): $(tail -1 "$S/$lab.log" | grep -o '"ok": [0-9]*, "n": [0-9]*') errors $(grep -c '"error": *"[^"]' D:/BAXYeval/renew_v1/runs/$lab.jsonl 2>/dev/null)"
  done
done
for v in "" -pA -pB -pC; do
  for arm in none modes_sentence; do
    idle; export BAXY_AYUDAS=$arm; lab="nb-p7-$arm$v-esc"
    py -3.12 -X utf8 scripts/renew/bench_escenas.py "$lab" --scenes 'D:\BAXYeval\renew_v1\escenas\practice.json' \
      --src "D:/BAXYeval/renew_v1/ab/bis/$H$v" --catalog "$CAT" "${GA[@]}" > "$S/$lab.log" 2>&1
    echo "$lab $(date +%H:%M): $(tail -1 "$S/$lab.log" | grep -oE '"ok": [0-9]+|"annoying": [0-9]+|"risky_alone": [0-9]+|"failures": [0-9]+' | tr '\n' ' ')"
  done
done
for arm in none modes_sentence; do
  idle; export BAXY_AYUDAS=$arm; lab="nb-p7-sonda-$arm-s0"
  py -3.12 -X utf8 scripts/renew/bench_decision.py "$lab" --cases 'D:\BAXYeval\ft_v1\sonda_modos\sonda_modos.json' \
    --src "D:/BAXYeval/renew_v1/ab/arr/$H-s0" --catalog "$CAT" "${GA[@]}" > "$S/$lab.log" 2>&1
  echo "$lab $(date +%H:%M): $(tail -1 "$S/$lab.log" | grep -o '"n": [0-9]*') errors $(grep -c '"error": *"[^"]' "D:/BAXYeval/renew_v1/runs/$lab.jsonl" 2>/dev/null)"
  scp -q "D:/BAXYeval/renew_v1/runs/$lab.jsonl" "redpc:F:/BAXYeval/ft_v1/runs/$lab.jsonl" && echo "$lab sent"
done
unset BAXY_AYUDAS
echo P7-DONE
