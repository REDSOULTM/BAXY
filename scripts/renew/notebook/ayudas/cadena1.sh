#!/usr/bin/env bash
# After the A/B e2e: falsehoods s0 A/B, then lever 7's GPU benches.
AY=/c/Users/usuario/AppData/Local/Temp/claude/nb/ay
until grep -q AB-DONE "$AY/ab.log"; do sleep 20; done
"$AY/fal_ab.sh" > "$AY/fal.log" 2>&1
CAT='D:/BAXYeval/ayudas_nb/catalog.B-a3af5c20f.json' "$AY/p7.sh" > "$AY/p7.log" 2>&1
echo CADENA1-DONE
