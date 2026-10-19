#!/usr/bin/env bash
# After lever 8's GPU benches: lever 1c (place_unverified) e2e s0-2 paired on one binary + falsehoods s0 of A and B.
AY=/c/Users/usuario/AppData/Local/Temp/claude/nb/ay
until grep -q "PAID-person_folder_sentence-DONE" "$AY/p8.log"; do sleep 20; done
FAL_ARMS="A B" "$AY/e2e_aid.sh" ea1987fb4 "C:/Users/usuario/Desktop/ETC/Programacion/BAXY-Renew-p1c" place_unverified p1c > "$AY/p1c.log" 2>&1
echo CADENA2-DONE
