# usage: correr_esc.sh TAG MIND_PREFIX [SONDA=1]   escenas s0,pA,pB,pC (+ sonda de modos s0) on the PC GPU, c2-e1.0
cd "C:/Users/usuario/Desktop/ETC/Programacion/BAXY-Renew-ayudas"
tag=$1; mp=$2
M=F:/BAXYeval/ayudas_v1/minds; [ -d "$M/$mp-s0" ] || M=F:/BAXYeval/ft_v1/minds
R=F:/BAXYeval/ayudas_v1/runs
G=F:/BAXYeval/models/BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf
C=F:/BAXYeval/reales_v1/catalogos/lote3.json
export BAXY_RENEW_BANKS='F:\BAXYeval\ayudas_v1'
for p in ${PERTS:-s0 pA pB pC}; do
  py -3.12 -X utf8 scripts/renew/bench_escenas.py pc-esc-$tag-$p --scenes 'F:/BAXYeval/renew_v1/escenas/practice.json' --src "$M/$mp-$p" --catalog $C --gguf $G > $R/pc-esc-$tag-$p.out 2>&1
  echo "$tag esc $p $(tail -1 $R/pc-esc-$tag-$p.out | head -c 300)"
done
if [ "${3:-1}" = 1 ]; then
  py -3.12 -X utf8 scripts/renew/bench_decision.py pc-sonda-$tag-s0 --cases F:/BAXYeval/ft_v1/sonda_modos/sonda_modos.json --src "$M/$mp-s0" --catalog $C --gguf $G > $R/pc-sonda-$tag-s0.out 2>&1
  echo "$tag sonda"; py -3.12 -X utf8 F:/BAXYeval/ft_v1/sonda_modos/juzgar_sonda.py $R/pc-sonda-$tag-s0.jsonl --sonda F:/BAXYeval/ft_v1/sonda_modos/sonda_modos.json
fi
