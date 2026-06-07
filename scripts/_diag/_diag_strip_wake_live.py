"""Verifica strip_wake_phrase con los CASOS REALES de los logs de Baxy.

Los 3 fraseos exactos que el STT (Parakeet) produjo en la sesión 03:33 del
usuario, donde dijo "Baxy" y el STT escribió Paxi/Bixby/Max. El supresor debe
quitar el mal-oído y dejar el comando limpio para el LLM. Además: NO debe tocar
comandos reales que NO empiezan con la wake word.

Uso: python scripts/_diag/_diag_strip_wake_live.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gemma4_agent.voice.corrector import FuzzyCorrector
from gemma4_agent.voice.inventory import get_inventory

inv = get_inventory(include_discovery=False)
c = FuzzyCorrector(inv)

print("wake_words activos:", inv.get("wake_words"))
print()

# (transcript crudo del STT, esperado tras strip)  — DEBE quitar la wake
real_log_cases = [
    ("Paxi, va a la página de Red General Rayquema",
     "va a la página de Red General Rayquema"),
    ("Bixby, ¿qué juego estoy jugando?", "¿qué juego estoy jugando?"),
    ("Max ¿qué juego estoy jugando?", "¿qué juego estoy jugando?"),
    ("Baxy, abre Spotify", "abre Spotify"),
    ("baxi pon música", "pon música"),
    ("Backsy busca el clima", "busca el clima"),
    ("hey baxy minimiza todo", "minimiza todo"),
]

# Comandos que NO empiezan con la wake -> NO tocar el primer token.
no_strip_cases = [
    "busca el clima en Madrid",
    "manda un mensaje a Pedro",
    "pon música de Soda Stereo",
    "abre el navegador",
    "máximo volumen por favor",
    "pásame al siguiente tema",
]

print("=== DEBE QUITAR la wake mal-oída (caso real del log) ===")
ok = 0
for raw, expected in real_log_cases:
    got = c.strip_wake_phrase(raw)
    passed = got.strip().lower() == expected.strip().lower()
    ok += passed
    mark = "OK " if passed else "XX "
    print(f"  [{mark}] {raw!r}\n        -> {got!r}\n        exp {expected!r}")
print(f"  -> {ok}/{len(real_log_cases)} quitaron la wake correctamente\n")

print("=== NO DEBE tocar comandos sin wake al inicio ===")
ok2 = 0
for raw in no_strip_cases:
    got = c.strip_wake_phrase(raw)
    passed = got.strip() == raw.strip()  # intacto
    ok2 += passed
    mark = "OK " if passed else "XX "
    print(f"  [{mark}] {raw!r} -> {got!r}")
print(f"  -> {ok2}/{len(no_strip_cases)} quedaron intactos (sin falso strip)")

print()
print("VEREDICTO:",
      "PASS" if ok == len(real_log_cases) and ok2 == len(no_strip_cases)
      else f"PARCIAL (strip {ok}/{len(real_log_cases)}, intactos {ok2}/{len(no_strip_cases)})")
