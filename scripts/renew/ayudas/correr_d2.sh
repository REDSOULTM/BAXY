# usage: correr_d2.sh TAG MIND_PREFIX [SEEDS]   decision2 s0-2 on the PC GPU, c2-e1.0, catalog lote3
cd "C:/Users/usuario/Desktop/ETC/Programacion/BAXY-Renew-ayudas"
tag=$1; mp=$2
M=F:/BAXYeval/ayudas_v1/minds; [ -d "$M/$mp-s0" ] || M=F:/BAXYeval/ft_v1/minds
R=F:/BAXYeval/ayudas_v1/runs
G=F:/BAXYeval/models/BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf
export BAXY_RENEW_BANKS='F:\BAXYeval\ayudas_v1'
for s in ${3:-0 1 2}; do
  py -3.12 -X utf8 scripts/renew/bench_decision.py pc-d2-$tag-s$s --cases 'F:/BAXYeval/renew_v1/practica/decision2.json' --src "$M/$mp-s$s" --catalog F:/BAXYeval/reales_v1/catalogos/lote3.json --gguf $G > $R/pc-d2-$tag-s$s.out 2>&1
  echo "$tag d2 s$s $(grep -o '"ok": [0-9]*, "n": [0-9]*' $R/pc-d2-$tag-s$s.out | tail -1) errores=$(grep -c '"error": "' $R/pc-d2-$tag-s$s.jsonl)"
done
