"""Sonda determinista de huecos del router: ¿ofrece la tool esperada?

Mide select_tool_names sin LLM (determinista) para separar huecos REALES del
router de los artefactos de no-determinismo del 4B. Uso en la cacería de
huecos de corpus (mission-eval 2026-06-10).

Metodología: editar PROBES con (tool_esperada, frase) por categoría sospechosa
y correr. "GAP" = el router no ofreció la tool esperada -> candidato a hueco de
corpus. ANTES de agregar exemplars, verificar el DISEÑO (qué tool implementa de
verdad la acción y cuál documenta el fraseo en su schema) para no etiquetar
contra el diseño.

Casos resueltos por este método: recordatorios->reminder (run5), volumen
perifrástico->audio (run4), brillo multilingüe->device_settings (run6). GOTCHA
de diseño: WiFi/BT/brillo son `device_settings` (su schema documenta
brightness_up/down "for 'subí/bajá el brillo'"), NO `system`, aunque el dataset
FT a veces etiqueta system; ambas implementan brillo pero device_settings es la
canónica.

Foco run7: CERRAR/REINICIAR apps (app.close, su descripción dice "abrir, cerrar
o encontrar un programa") y FOCUS de ventana (window: "focus"). El router los
mandaba a office/browser/session.
"""
import os
os.environ["GEMMA4_VOICE_LANG"] = ""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gemma4_agent.routing.planner import select_tool_names, plan_mission

PROBES = [
    # CERRAR apps -> app (su descripción: "abrir, cerrar o encontrar un programa")
    ("app", "encerra o Word agora"),
    ("app", "Quitte Chrome maintenant"),
    ("app", "restart Spotify"),
    ("app", "chiudi Spotify"),
    ("app", "schließe Word"),
    ("app", "ferme le navigateur"),
    ("app", "reinicia Discord"),
    ("app", "fecha o Chrome"),
    # FOCUS ventana -> window ("list windows, focus, ...")
    ("window", "porta in primo piano Calculator"),
    ("window", "bring Calculator to the front"),
    ("window", "trae Calculadora al frente"),
    # CONTROL: abrir app sigue app; crear doc sigue office
    ("app", "abre Chrome"),
    ("office", "crea un PowerPoint"),
]


def main():
    gaps = {}
    print("=== ¿router ofrece la tool esperada? ===")
    for exp, q in PROBES:
        sub = select_tool_names(q, plan_mission(q))
        has = exp in sub
        g = gaps.setdefault(exp, [0, 0])
        g[0] += 1 if has else 0
        g[1] += 1
        tag = "OK " if has else "GAP"
        print(f"  {tag} exp={exp:14} {q!r:38} -> {sub}")
    print("\n=== resumen por tool ===")
    for t, (ok, n) in gaps.items():
        print(f"  {t}: {ok}/{n} ofrecidos")


if __name__ == "__main__":
    main()
