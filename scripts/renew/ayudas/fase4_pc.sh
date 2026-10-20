#!/usr/bin/env bash
# Phase 4 on the PC's GPU, ONCE: the sealed holdout of the goal «ayudas» (SEALED_AYUDAS.md), decision and scenes, with the
# final lot's mind and with the starting product's (BAXY_AYUDAS=none) in the same session, as the FT goal measured the
# base beside the final. The seals are checked first; nothing of the holdout is printed but counts.
# usage: bash fase4_pc.sh LOT_MIND_DIR LOT_AIDS          e.g. fase4_pc.sh F:/BAXYeval/ayudas_v1/minds/pa-<sha>-s0 all
set -u
MIND=$1; AIDS=$2
H=F:/BAXYeval/ayudas_v1/holdout; LOG=/f/BAXYeval/ayudas_v1/runs
[ "$(sha256sum $H/decision_ayudas.sealed.json | cut -c1-64)" = 74efc33cd9426add786ee801b5cae50ef2f176acaebbc80494613b47bdb42381 ] || { echo "SELLO ROTO decision"; exit 1; }
[ "$(sha256sum $H/escenas_ayudas.sealed.json | cut -c1-64)" = fa4d11b9c4f9e71715bf51dce4bd601c3fd074807e04f780b85ef9995bc62425 ] || { echo "SELLO ROTO escenas"; exit 1; }
echo "sellos intactos $(date +%H:%M)"
cd /c/Users/usuario/Desktop/ETC/Programacion/BAXY-Renew-ayudas || exit 1
export BAXY_RENEW_BANKS='F:\BAXYeval\ayudas_v1'
G=F:/BAXYeval/models/BAXY-Qwen3.5-4B-ft-c2e1-Q4_K_M.gguf; C=F:/BAXYeval/reales_v1/catalogos/lote3.json
for arm in lote none; do
  if [ $arm = lote ]; then export BAXY_AYUDAS="$AIDS"; else export BAXY_AYUDAS=none; fi
  py -3.12 -X utf8 scripts/renew/bench_decision.py pc-fase4-dec-$arm --cases $H/decision_ayudas.sealed.json --src "$MIND" --catalog $C --gguf $G > $LOG/pc-fase4-dec-$arm.out 2>&1
  echo "decision $arm: $(grep -o '"ok": [0-9]*, "n": [0-9]*' $LOG/pc-fase4-dec-$arm.out | tail -1) errores=$(grep -c '"error": "' $LOG/pc-fase4-dec-$arm.jsonl)"
  py -3.12 -X utf8 scripts/renew/bench_escenas.py pc-fase4-esc-$arm --scenes $H/escenas_ayudas.sealed.json --src "$MIND" --catalog $C --gguf $G > $LOG/pc-fase4-esc-$arm.out 2>&1
  echo "escenas $arm: $(tail -1 $LOG/pc-fase4-esc-$arm.out | grep -o '"ok": [0-9]*, "n": [0-9]*, [^}]*annoying": [0-9]*' | head -1)"
done
# Per family, counts only (ids are shuffled: the number tells nothing).
py -3.12 -X utf8 - <<'EOF'
import json
for arm in ("lote", "none"):
    s = json.loads(open(f"F:/BAXYeval/ayudas_v1/runs/pc-fase4-dec-{arm}.jsonl", encoding="utf-8").readline())["summary"]
    print(arm, s["ok"], "/", s["n"], {k: f"{v[0]}/{v[1]}" for k, v in sorted(s["families"].items())})
EOF
echo "FASE4-PC-DONE $(date +%H:%M)"
