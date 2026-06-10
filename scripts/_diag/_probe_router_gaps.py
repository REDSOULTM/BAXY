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
"""
import os
os.environ["GEMMA4_VOICE_LANG"] = ""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gemma4_agent.routing.planner import select_tool_names, plan_mission

PROBES = [
    # BRILLO -> system (la descripción de system lo reclama)
    ("system", "Diminui o brilho um pouco"),
    ("system", "sube el brillo"),
    ("system", "lower the brightness"),
    ("system", "baja el brillo de la pantalla"),
    ("system", "atenúa la pantalla"),
    ("system", "aumenta o brilho"),
    ("system", "monte la luminosité"),
    ("system", "abbassa la luminosità"),
    ("system", "mach den Bildschirm heller"),
    # CONTROL: WiFi/BT son device_settings (NO deben volverse system)
    ("device_settings", "Ativa o Wi-Fi"),
    ("device_settings", "Liga o Bluetooth"),
    ("device_settings", "turn on wifi"),
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
        print(f"  {tag} exp={exp:16} {q!r:38} -> {sub}")
    print("\n=== resumen por tool ===")
    for t, (ok, n) in gaps.items():
        print(f"  {t}: {ok}/{n} ofrecidos")


if __name__ == "__main__":
    main()
