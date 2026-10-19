#!/usr/bin/env bash
# After 1c: lever 8 (person_folder_sentence) e2e, arm B only on the same binary ea1987fb4 (already built), paired against
# 1c's A none of today; then falsehoods s0 of B.
AY=/c/Users/usuario/AppData/Local/Temp/claude/nb/ay
until grep -q "E2E-AID-p1c-DONE" "$AY/p1c.log"; do sleep 20; done
SKIP_BUILD=1 ARMS=B A_PREFIX=nb-p1c-A FAL_ARMS=B "$AY/e2e_aid2.sh" ea1987fb4 "C:/Users/usuario/Desktop/ETC/Programacion/BAXY-Renew-p1c" person_folder_sentence p8 > "$AY/p8e2e.log" 2>&1
echo CADENA3-DONE
