"""Verifica que los huecos que B2 expuso (2026-06-10) se arreglaron tras el
reentreno, sin regresión. Determinista, sin LLM."""
import os
os.environ["GEMMA4_VOICE_LANG"] = ""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from gemma4_agent.routing.planner import select_tool_names, plan_mission

GAPS = [
    ("app", ["find Photoshop", "trova Photoshop", "find the calculator", "finde Discord",
             "esci da Spotify", "esci da Chrome", "exit Chrome", "beende Spotify"]),
    ("system", ["what is the CPU usage", "what is the battery level",
                "qual è l uso della CPU", "wie ist die CPU auslastung"]),
    ("clipboard", ["incollalo", "paste it", "füg es ein", "colá esto"]),
]
# control: NO deben romperse (preguntas de mundo siguen a web)
CONTROL = [("quién es Einstein", "web"), ("qué es python", None),
           ("abrí Spotify", "app"), ("sube el volumen", "audio")]


def main():
    tot = ok = 0
    for tool, qs in GAPS:
        hit = 0
        for q in qs:
            sub = select_tool_names(q, plan_mission(q))
            has = tool in sub
            hit += has; tot += 1; ok += has
            if not has:
                print(f"  GAP [{tool}] {q!r} -> {[t for t in sub if t not in ('session','safety','state')][:3]}")
        print(f"  {tool}: {hit}/{len(qs)}")
    print(f"== huecos: {ok}/{tot} ==")
    print("-- control (no romper) --")
    for q, exp in CONTROL:
        sub = select_tool_names(q, plan_mission(q))
        if exp is None:
            note = "[] esperado" if not [t for t in sub if t not in ('session','safety','state','verify')] else f"-> {sub}"
        else:
            note = "OK" if exp in sub else f"ROTO -> {sub}"
        print(f"  {q!r:22} {note}")


if __name__ == "__main__":
    main()
