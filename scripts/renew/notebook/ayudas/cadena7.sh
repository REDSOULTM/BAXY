#!/usr/bin/env bash
# After the lot's falsehoods s1-s2: e2e s3-s5 of A none and B lot (BAXY_AYUDAS=all, the same as unset) on d7a76adf1,
# built; one seed per call so the bench leftovers in the home (.txt written in the last day) are listed before each.
AY=/c/Users/usuario/AppData/Local/Temp/claude/nb/ay
leftovers() { find /c/Users/usuario -maxdepth 1 -type f -name '*.txt' -mmin -1440 -printf '%f '; }
until grep -q FAL-LOTE-DONE "$AY/fal_lote.log" 2>/dev/null; do sleep 20; done
for seed in 3 4 5; do
  echo "home .txt before s$seed: $(leftovers)"
  SEEDS="$seed" SKIP_BUILD=1 FAL_ARMS=" " "$AY/e2e_aid3.sh" d7a76adf1 "C:/Users/usuario/Desktop/ETC/Programacion/BAXY-Renew-lote" all lote
done
echo "home .txt after: $(leftovers)"
echo CADENA7-DONE
