"""Verifica que el encoder reentrenado (mission 2026-06-10) rutea los 4 huecos.
Determinista (sin LLM): mide select_tool_names sobre los 4 huecos consolidados."""
import os
os.environ["GEMMA4_VOICE_LANG"] = ""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from gemma4_agent.routing.planner import select_tool_names, plan_mission

GAPS = [
    ("audio", ["déjalo mudo", "leave it almost silent", "lascialo quasi senza suono",
               "mach es fast lautlos", "laisse-le presque sans son", "deixa quase sem som"]),
    ("reminder", ["recordame sacar la basura mañana", "remind me to call mom tomorrow",
                  "lembra-me de tomar o remédio", "ricordami di comprare il pane",
                  "erinnere mich daran, Brot zu kaufen", "rappelle-moi d'acheter du pain"]),
    ("device_settings", ["sube el brillo", "lower the brightness", "aumenta o brilho",
                         "monte la luminosité", "abbassa la luminosità", "mach den Bildschirm heller"]),
    ("app", ["restart Spotify", "reinicia Discord", "encerra o Word agora", "Quitte Chrome maintenant"]),
    ("window", ["porta in primo piano Calculator", "bring Calculator to the front",
                "trae Calculadora al frente"]),
]


def main():
    total = ok = 0
    for tool, qs in GAPS:
        hit = 0
        for q in qs:
            sub = select_tool_names(q, plan_mission(q))
            has = tool in sub
            hit += has
            total += 1
            ok += has
        print(f"  {tool:16} {hit}/{len(qs)} ofrecen la tool")
    print(f"== TOTAL {ok}/{total} huecos rutean correctamente ==")


if __name__ == "__main__":
    main()
